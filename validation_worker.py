# -*- coding: utf-8 -*-
"""Client du processus de validation RELAX NG (voir relaxng_worker).

Le processus est lancé au premier besoin, une seule fois pour toute
l'application : c'est Varians lui-même, relancé avec l'option
``--relaxng-worker`` (depuis les sources comme dans une version autonome).
Les requêtes partent par son entrée standard et les réponses reviennent par
un fil d'exécution qui ne fait qu'attendre sur le tube : la fenêtre n'est
jamais bloquée par la compilation d'un gros schéma.

- ``validate_async`` : la réponse arrive plus tard, dans le fil principal ;
- ``validate`` : attend la réponse en laissant tourner la boucle
  d'événements (la fenêtre se redessine, les animations avancent), mais en
  ignorant clics et frappes, pour qu'aucune action ne parte au milieu.

Avec ``parts`` (``{chemin: texte}``, même vide), l'édition est validée
assemblée par XInclude (``relaxng_validation.validate_document``) ; avec
``schematron`` (V0.9.2.3), les règles Schematron de ces sources sont
appliquées ensuite, et le schéma RELAX NG peut manquer (None). La sortie
d'erreur du processus est un fichier temporaire (``stderr_log``, nommé par
la variable ``VARIANS_STDERR_LOG``), où Saxon écrit le détail d'une règle
incorrecte ; il est effacé à l'arrêt du processus.

``check_schematron`` et ``check_schematron_async`` (V0.9.2.4) vérifient de
la même façon le texte d'un fichier Schematron (``schematron_check``).

**Repli** : si le processus ne démarre pas ou s'arrête, la validation se fait
dans Varians même, comme avant la V0.8.9.2 (la fenêtre est alors bloquée
pendant la compilation), et les requêtes en cours ne sont pas perdues.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QEventLoop, QObject, QTimer, Qt, Signal
from PySide6.QtWidgets import QApplication

from relaxng_validation import STDERR_LOG, validate_document
from relaxng_worker import result_from_dict

_APPLICATION_DIR = Path(__file__).resolve().parent
# Attente maximale d'une validation demandée, au-delà de laquelle Varians
# valide lui-même (processus bloqué).
SYNC_TIMEOUT_MSEC = 300_000
_BLOCKED_EVENTS = frozenset({
    QEvent.Type.MouseButtonPress, QEvent.Type.MouseButtonRelease, QEvent.Type.MouseButtonDblClick,
    QEvent.Type.KeyPress, QEvent.Type.KeyRelease, QEvent.Type.Wheel, QEvent.Type.Shortcut,
    QEvent.Type.ShortcutOverride, QEvent.Type.ContextMenu, QEvent.Type.Close,
})


def default_worker_command():
    """Commande qui relance Varians en processus de validation."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():     # PyInstaller…, Nuitka
        return [sys.executable, "--relaxng-worker"]
    return [sys.executable, str(_APPLICATION_DIR / "editeur_tei.py"), "--relaxng-worker"]


@dataclass
class _Pending:
    request: dict
    owner: object = None
    callback: object = None          # None : attendue par validate()


class _InputBlocker(QObject):
    """Ignore clics et frappes pendant une validation demandée."""

    def eventFilter(self, _watched, event):
        return event.type() in _BLOCKED_EVENTS


class RelaxNGWorkerClient(QObject):
    """Requêtes de validation vers le processus séparé (voir le module)."""

    busyChanged = Signal(bool)
    # Le processus est indisponible : raison, émise une seule fois.
    fellBack = Signal(str)
    _received = Signal(object)
    _delivered = Signal(int)

    def __init__(self, command=None, parent=None):
        super().__init__(parent)
        self._command = list(command) if command else default_worker_command()
        self._process = None
        self._outgoing = None
        self.stderr_log = None
        self._next_id = 0
        self._pending = {}
        self._results = {}
        self._stopping = False
        self.fallback_reason = ""
        self.compilations = None
        self._received.connect(self._on_received)

    @property
    def uses_process(self):
        return not self.fallback_reason

    @property
    def busy(self):
        return bool(self._pending)

    # --- Requêtes ---------------------------------------------------------------

    def validate_async(self, xml_text, schema_path, base_url, owner, callback, parts=None, schematron=None):
        """Valide sans attendre ; ``callback(result)`` est appelé dans le fil
        principal, sauf si ``owner`` (un QObject) a été détruit entre-temps."""
        return self._submit(_validate_request(xml_text, schema_path, base_url, parts, schematron), owner, callback)

    def validate(self, xml_text, schema_path, base_url=None, parts=None, schematron=None):
        """Valide et renvoie le résultat ; la fenêtre continue de se redessiner
        pendant l'attente, sans traiter clics ni frappes."""
        return self._wait(_validate_request(xml_text, schema_path, base_url, parts, schematron))

    def check_schematron_async(self, text, path, owner, callback):
        """Vérifie sans attendre le texte du fichier Schematron *path* (voir
        ``validate_async``)."""
        return self._submit(_check_request(text, path), owner, callback)

    def check_schematron(self, text, path):
        """Vérifie le texte du fichier Schematron *path* et rend le résultat
        (voir ``validate``)."""
        return self._wait(_check_request(text, path))

    def _wait(self, request):
        if QCoreApplication.instance() is None:             # pas de boucle d'événements
            return self._validate_here(request)
        request_id = self._submit(request, None, None)
        if request_id not in self._results:
            self._wait_for(request_id)
        return self._results.pop(request_id)

    def _submit(self, request, owner, callback):
        self._next_id += 1
        request_id = self._next_id
        request = dict(request, id=request_id)
        entry = _Pending(request, owner, callback)
        if not self._ensure_process():
            self._deliver(request_id, entry, self._validate_here(request), was_pending=False)
            return request_id
        was_busy = self.busy
        self._pending[request_id] = entry
        if not was_busy:
            self.busyChanged.emit(True)
        self._outgoing.put((json.dumps(request, ensure_ascii=False) + "\n").encode("utf-8"))
        return request_id

    def _wait_for(self, request_id):
        loop = QEventLoop()

        def arrived(delivered_id):
            if delivered_id == request_id:
                loop.quit()

        self._delivered.connect(arrived)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(loop.quit)
        timeout.start(SYNC_TIMEOUT_MSEC)
        blocker = _InputBlocker()
        app = QCoreApplication.instance()
        app.installEventFilter(blocker)
        if isinstance(app, QApplication):
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            if request_id not in self._results:
                loop.exec()
        finally:
            if isinstance(app, QApplication):
                QApplication.restoreOverrideCursor()
            app.removeEventFilter(blocker)
            self._delivered.disconnect(arrived)
            timeout.stop()
        if request_id not in self._results:                 # processus bloqué
            self._fall_back("timeout")

    # --- Processus ----------------------------------------------------------------

    def _ensure_process(self):
        if self.fallback_reason:
            return False
        if self._process is not None:
            return True
        try:
            handle, self.stderr_log = tempfile.mkstemp(prefix="varians-validation-", suffix=".log")
            with os.fdopen(handle, "wb") as errors:
                self._process = subprocess.Popen(
                    self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                    env=dict(os.environ, **{STDERR_LOG: self.stderr_log}),
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, ValueError) as exc:
            self._fall_back(str(exc))
            return False
        self._outgoing = queue.Queue()
        threading.Thread(target=self._write_loop, args=(self._process.stdin, self._outgoing),
                         name="relaxng-worker-writer", daemon=True).start()
        threading.Thread(target=self._read_loop, args=(self._process.stdout,),
                         name="relaxng-worker-reader", daemon=True).start()
        return True

    @staticmethod
    def _write_loop(stdin, outgoing):
        """Fil d'écriture : une requête volumineuse n'attend jamais dans le fil
        principal que le processus la lise."""
        while True:
            data = outgoing.get()
            if data is None:
                break
            try:
                stdin.write(data)
                stdin.flush()
            except (OSError, ValueError):
                break
        try:
            stdin.close()
        except (OSError, ValueError):
            pass

    def _read_loop(self, stdout):
        """Fil de lecture : transmet chaque réponse au fil principal, puis
        ``None`` quand le processus s'arrête."""
        try:
            for line in stdout:
                try:
                    data = json.loads(line)
                except ValueError:
                    continue
                if not shiboken6.isValid(self):
                    return
                self._received.emit(data)
        except (OSError, ValueError):
            pass
        if shiboken6.isValid(self):
            self._received.emit(None)

    def _on_received(self, data):
        if data is None:
            if not self._stopping and not self.fallback_reason:
                code = self._process.poll() if self._process is not None else None
                self._fall_back(f"process ended ({code})")
            return
        entry = self._pending.pop(data.get("id"), None)
        if entry is None:
            return
        if "result" in data:
            self.compilations = data.get("compilations")
            result = result_from_dict(data["result"])
        else:                                               # requête refusée : valider ici
            result = self._validate_here(entry.request)
        self._deliver(entry.request["id"], entry, result, was_pending=True)

    def _deliver(self, request_id, entry, result, *, was_pending):
        """Remet le résultat (à ``validate`` ou au rappel), puis signale la fin
        de l'activité quand plus aucune requête n'attend le processus."""
        if entry.callback is None:
            self._results[request_id] = result
        elif entry.owner is None or shiboken6.isValid(entry.owner):
            entry.callback(result)
        if was_pending and not self._pending:
            self.busyChanged.emit(False)
        self._delivered.emit(request_id)

    @staticmethod
    def _validate_here(request):
        if request["op"] == "check_schematron":
            from schematron_check import check
            return check(request["text"], request["path"])
        return validate_document(request["xml"], request["schema"] or None, request.get("base_url") or None,
                                 request.get("parts"), request.get("schematron"))

    def _fall_back(self, reason):
        """Le processus est indisponible : valider désormais dans Varians, y
        compris les requêtes en attente."""
        if not self.fallback_reason:
            self.fallback_reason = reason or "unavailable"
            self.fellBack.emit(self.fallback_reason)
        self._stop_process()
        for request_id in sorted(self._pending):
            entry = self._pending.pop(request_id)
            self._deliver(request_id, entry, self._validate_here(entry.request), was_pending=True)

    def _stop_process(self, timeout=3.0):
        process, self._process = self._process, None
        if process is not None:
            if self._outgoing is not None:
                self._outgoing.put(None)                    # fin de l'entrée : arrêt propre
            try:
                process.wait(timeout)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout)
        log, self.stderr_log = self.stderr_log, None
        if log is not None:
            try:
                os.unlink(log)
            except OSError:
                pass

    def shutdown(self):
        """Arrête le processus (fermeture de Varians) ; une validation en cours
        n'est pas attendue."""
        self._stopping = True
        if self.busy and self._process is not None:
            self._process.kill()
        self._stop_process()


def _validate_request(xml_text, schema_path, base_url, parts, schematron):
    request = {"op": "validate", "xml": xml_text, "schema": str(schema_path) if schema_path else "",
               "base_url": str(base_url) if base_url else None}
    if parts is not None:
        request["parts"] = {str(path): text for path, text in parts.items()}
    if schematron:
        # Une source avec sa phase (SchematronSource) : [chemin, phase].
        request["schematron"] = [[str(getattr(source, "path", source)), getattr(source, "phase", "")]
                                 for source in schematron]
    return request


def _check_request(text, path):
    return {"op": "check_schematron", "text": text, "path": str(path)}


_client = None


def worker_client():
    """Le client unique de l'application, arrêté à sa fermeture."""
    global _client
    if _client is None or not shiboken6.isValid(_client):
        app = QCoreApplication.instance()
        _client = RelaxNGWorkerClient(parent=app)
        if app is not None:
            app.aboutToQuit.connect(_client.shutdown)
    return _client
