# -*- coding: utf-8 -*-
"""Client du processus d'une transformation XSLT (voir transform_worker).

``TransformRunner.start(request)`` lance Varians en processus de
transformation (``--transform-worker``), lui envoie la requête
(``xslt_scenarios.scenario_request``) et émet ``finished`` avec le compte
rendu (``xslt_engines.TransformResult``) quand il a fini. La fenêtre n'est
jamais bloquée.

- ``cancel`` arrête le processus : le compte rendu porte ``cancelled`` ;
- un processus qui ne démarre pas, s'arrête sans répondre ou répond mal
  donne ``worker_failed``, avec ce qu'il a écrit sur sa sortie d'erreur.

La sortie d'erreur du processus est un fichier, donné dès sa création et
nommé dans la requête (``stderr_log``) : Saxon y écrit le lieu de ses
erreurs (voir transform_worker).

``finished`` est émis une fois par exécution, toujours dans le fil principal
et jamais pendant ``start``.

Le processus est attendu par un fil (``subprocess``), comme celui de la
validation (V0.9.4.6) : sous macOS, Qt apprend la fin d'un ``QProcess`` par
le signal SIGCHLD, que Saxon (Java), chargé dans Varians quand Varians
valide lui-même des règles Schematron, remet à son état par défaut ; la fin
des transformations n'arrivait alors plus. Un fil qui attend son processus
ne dépend pas de ce signal.
"""
from __future__ import annotations

import itertools
import json
import os
import subprocess
import threading

import shiboken6
from PySide6.QtCore import QObject, Qt, Signal, Slot

import error_log
from transform_worker import failed_worker, new_stderr_log, read_answer, worker_command
from xslt_engines import TransformResult

_journal = error_log.logger("transformation")
# Exécutions en cours : clé → TransformRunner (le fil n'a que la clé).
_waiting = {}
_keys = itertools.count(1)


class _Relay(QObject):
    """Ramène dans le fil principal la fin d'un processus attendu par un fil.
    Créé une fois, dans le fil principal, et jamais détruit : un fil peut
    toujours y émettre, même si l'exécution a disparu entre-temps."""

    arrived = Signal(object)

    def __init__(self):
        super().__init__()
        # Toujours par la boucle d'événements, même émis du fil principal.
        self.arrived.connect(self._dispatch, Qt.ConnectionType.QueuedConnection)

    @Slot(object)
    def _dispatch(self, payload):
        key, output, failure = payload
        runner = _waiting.pop(key, None)
        if runner is not None and shiboken6.isValid(runner):
            runner._arrived(key, output, failure)


_relay = None


def _main_relay():
    global _relay
    if _relay is None:
        _relay = _Relay()
    return _relay


def _wait(process, data, key, relay):
    """Fil d'attente : envoie la requête, lit la réponse jusqu'à la fin du
    processus, puis la transmet au fil principal."""
    try:
        output, _ = process.communicate(data)
    except (OSError, ValueError):
        output = b""
        try:
            process.wait()
        except OSError:
            pass
    relay.arrived.emit((key, output or b"", None))


def _kill(process):
    try:
        process.kill()
    except OSError:
        pass                                  # déjà terminé


class TransformRunner(QObject):
    """Une exécution à la fois, dans son propre processus."""

    finished = Signal(object)

    def __init__(self, command=None, parent=None):
        super().__init__(parent)
        self._command = list(command or worker_command())
        self._process = None
        self._key = None
        self._stderr_log = None
        self._cancelled = False
        self._done = True
        # Fenêtre fermée pendant une exécution : le processus est arrêté.
        held = self._held = {"process": None}
        self.destroyed.connect(lambda *_: held["process"] is not None and _kill(held["process"]))

    def running(self):
        """Vrai de ``start`` jusqu'à l'émission de ``finished`` ; ``start``
        refuse alors une seconde exécution."""
        return not self._done

    def start(self, request):
        """Lance l'exécution de ``request`` (une seule à la fois)."""
        if self.running():
            raise RuntimeError("une transformation est déjà en cours")
        relay = _main_relay()
        self._cancelled = False
        self._done = False
        self._key = key = next(_keys)
        _waiting[key] = self
        self._stderr_log = new_stderr_log()
        data = json.dumps(dict(request, stderr_log=self._stderr_log), ensure_ascii=False).encode("utf-8")
        try:
            with open(self._stderr_log, "wb") as errors:
                process = subprocess.Popen(
                    self._command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        except (OSError, ValueError) as exc:
            relay.arrived.emit((key, b"", str(exc) or type(exc).__name__))
            return
        self._process = self._held["process"] = process
        threading.Thread(target=_wait, args=(process, data, key, relay),
                         name="transform-runner", daemon=True).start()

    def cancel(self):
        """Arrête l'exécution en cours."""
        if self.running() and self._process is not None:
            self._cancelled = True
            _kill(self._process)

    def _arrived(self, key, output, failure):
        if self._done or key != self._key:
            return
        if failure is not None:
            self._deliver(failed_worker(failure))
        elif self._cancelled:
            self._deliver(TransformResult(False, error_code="cancelled"))
        else:
            self._deliver(read_answer(output, self._stderr_log))

    def _deliver(self, result):
        if result.error_code == "worker_failed":
            _journal.warning("Processus de transformation en échec : %s", result.error)
        self._done = True
        self._process = self._held["process"] = None
        if self._stderr_log is not None:
            try:
                os.unlink(self._stderr_log)
            except OSError:
                pass                          # encore ouvert par le processus (Windows) : fichier temporaire
            self._stderr_log = None
        self.finished.emit(result)
