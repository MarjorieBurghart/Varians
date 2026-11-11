# -*- coding: utf-8 -*-
"""Aperçu des vues en XSLT 2.0 ou 3.0 par Saxon (V0.9.4.4), sans Qt.

L'aperçu d'une vue en 1.0 est fait par lxml, dans Varians. Une feuille 2.0
ou 3.0 (``fragment_units.stylesheet_needs_saxon``) est confiée à Saxon, dans
un processus à part qui reste ouvert : Varians relancé avec l'option
``--preview-worker`` (comme ``--relaxng-worker`` et ``--transform-worker``),
sans PySide6. La fenêtre ne se fige pas, une feuille qui boucle est arrêtée
au bout de ``PREVIEW_TIMEOUT_SEC`` (le processus est alors relancé), et un
plantage de Saxon, code natif, n'emporte pas Varians.

Protocole : une requête JSON par ligne sur l'entrée du processus, une
réponse JSON par ligne sur sa sortie, avec le même ``id``.

- ``{"op": "ping"}`` → ``{"ok": true, "engine", "qt_loaded", "gui_loaded"}`` ;
- ``{"op": "transform", "xml", "xslt", "params", "base", "edit_markers"}``
  → ``{"ok": true, "html", "compiled", "engine"}`` ou ``{"ok": false,
  "code", "error"}``.

Comme l'aperçu en 1.0 : Saxon ne lit que des fichiers locaux
(``xslt_engines.saxon_without_network``, pour tout le processus), rien
n'est jamais écrit (``xsl:result-document`` est gardé en mémoire, puis
oublié), les paramètres sont sans type (``xs:untypedAtomic``). Le texte
donné à la feuille garde l'adresse de son fichier (``base``) : un
``doc()`` relatif y trouve ses fichiers. Les feuilles compilées sont
gardées tant que leur fichier (date, taille) ne change pas ; avec
``edit_markers``, c'est la feuille enveloppe des crayons qui est compilée
(``fragment_units.edit_stylesheet``, en 3.0)."""
from __future__ import annotations

import atexit
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass
from pathlib import Path

_APPLICATION_DIR = Path(__file__).resolve().parent

PREVIEW_TIMEOUT_SEC = 60
# Feuilles compilées gardées par le processus (les plus anciennes partent).
CACHE_SIZE = 8


class PreviewError(Exception):
    """Échec d'un aperçu : ``code`` (ceux de ``xslt_engines.ERROR_CODES``,
    plus ``timeout`` et ``worker_failed``) et texte."""

    def __init__(self, code, detail=""):
        super().__init__(detail or code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class PreviewResult:
    """HTML produit par la feuille ; ``compiled`` : la feuille a été
    compilée pour cet aperçu (elle ne l'est plus tant qu'elle ne change
    pas) ; ``engine`` : « Saxon » et sa version."""
    html: str
    compiled: bool
    engine: str


def worker_command():
    """Commande qui relance Varians en processus d'aperçu Saxon."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():     # PyInstaller…, Nuitka
        return [sys.executable, "--preview-worker"]
    return [sys.executable, str(_APPLICATION_DIR / "editeur_tei.py"), "--preview-worker"]


# --- Processus -------------------------------------------------------------------

class _Worker:
    """Ce que le processus garde d'une requête à l'autre."""

    def __init__(self, stderr_log=None):
        import xslt_engines
        self.engines = xslt_engines
        self.processor = xslt_engines._saxon_processor()
        xslt_engines.saxon_without_network(self.processor)
        self.engine = "Saxon " + xslt_engines._saxon_version()
        self.stderr_log = Path(stderr_log) if stderr_log else None
        self.folder = Path(tempfile.mkdtemp(prefix="varians-preview-"))
        self.cache = {}

    def stderr_size(self):
        try:
            return self.stderr_log.stat().st_size if self.stderr_log is not None else 0
        except OSError:
            return 0

    def stderr_since(self, start):
        if self.stderr_log is None:
            return ""
        try:
            with open(self.stderr_log, "rb") as stream:
                stream.seek(start)
                return stream.read().decode("utf-8", errors="replace")
        except OSError:
            return ""

    def executable(self, xslt, edit_markers, start):
        """La feuille compilée (enveloppe des crayons comprise), et si elle
        vient d'être compilée."""
        from saxonche import PySaxonApiError
        from fragment_units import edit_stylesheet
        try:
            stat = xslt.stat()
        except OSError as exc:
            raise self.engines.TransformError("xslt_missing", f"{xslt}: {exc.strerror or exc}") from exc
        key = (str(xslt), bool(edit_markers))
        signature = (stat.st_mtime_ns, stat.st_size)
        cached = self.cache.get(key)
        if cached is not None and cached[0] == signature:
            return cached[1], False
        path = xslt
        if edit_markers:
            path = self.folder / f"enveloppe-{len(self.cache)}-{abs(hash(key))}.xsl"
            path.write_text(edit_stylesheet(xslt, version="3.0"), encoding="utf-8")
        try:
            executable = self.processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(path))
        except PySaxonApiError as exc:
            raise self.engines._saxon_failure(exc, self.stderr_since(start), xslt, "xslt_invalid") from exc
        executable.set_save_xsl_message(True)
        executable.set_capture_result_documents(True)
        self.cache.pop(key, None)
        self.cache[key] = (signature, executable)
        while len(self.cache) > CACHE_SIZE:
            self.cache.pop(next(iter(self.cache)))
        return executable, True

    def transform(self, request):
        from saxonche import PySaxonApiError
        start = self.stderr_size()
        xslt = Path(request["xslt"]).expanduser().resolve()
        executable, compiled = self.executable(xslt, request.get("edit_markers", True), start)
        builder = self.processor.new_document_builder()
        if request.get("base"):
            builder.set_base_uri(Path(request["base"]).expanduser().resolve().as_uri())
        try:
            source = builder.parse_xml(xml_text=request.get("xml") or "")
        except PySaxonApiError as exc:
            raise self.engines._saxon_failure(exc, self.stderr_since(start), request.get("base") or "source",
                                              "source_malformed") from exc
        for name, value in (request.get("params") or {}).items():
            executable.set_parameter(str(name), self.processor.make_atomic_value("untypedAtomic", str(value)))
        try:
            html = executable.transform_to_string(xdm_node=source)
        except PySaxonApiError as exc:
            self.forget(xslt)
            raise self.engines._saxon_failure(exc, self.stderr_since(start), xslt, "transform_failed") from exc
        finally:
            executable.clear_xsl_messages()
        if executable.get_result_documents():
            # Fichiers gardés en mémoire, jamais écrits ; SaxonC ne réutilise
            # pas sans risque une feuille qui en a gardé.
            self.forget(xslt)
        return {"ok": True, "html": html or "", "compiled": compiled, "engine": self.engine}

    def forget(self, xslt):
        for key in [key for key in self.cache if key[0] == str(xslt)]:
            del self.cache[key]

    def answer(self, request):
        if request.get("op") == "ping":
            return {"ok": True, "engine": self.engine, "qt_loaded": "PySide6" in sys.modules,
                    "gui_loaded": "PySide6.QtGui" in sys.modules or "PySide6.QtWidgets" in sys.modules}
        if request.get("op") == "transform":
            try:
                return self.transform(request)
            except self.engines.TransformError as exc:
                return {"ok": False, "code": exc.code, "error": exc.detail}
        return {"ok": False, "code": "internal", "error": f"unknown op {request.get('op')!r}"}


def serve(input_fd=0, output_fd=1, stderr_log=None):
    """Répond aux requêtes, une par ligne, jusqu'à la fin de l'entrée."""
    reader = os.fdopen(input_fd, "rb", closefd=False)
    writer = os.fdopen(output_fd, "wb", closefd=False)
    worker = None
    for line in reader:
        try:
            request = json.loads(line.decode("utf-8"))
            if not isinstance(request, dict):
                raise ValueError("request must be a JSON object")
        except ValueError as exc:
            answer = {"ok": False, "code": "internal", "error": f"invalid request: {exc}"}
            request = {}
        else:
            if worker is None:
                try:
                    worker = _Worker(stderr_log)
                except Exception as exc:             # Saxon absent ou qui ne démarre pas
                    code = getattr(exc, "code", "saxon_missing")
                    answer = {"ok": False, "code": code, "error": str(exc)}
                    worker = None
                else:
                    answer = worker.answer(request)
            else:
                answer = worker.answer(request)
        answer["id"] = request.get("id")
        writer.write(json.dumps(answer, ensure_ascii=False).encode("utf-8") + b"\n")
        writer.flush()
    return 0


# --- Client ----------------------------------------------------------------------

class SaxonPreviewClient:
    """Le processus d'aperçu, vu de Varians : lancé à la première demande,
    relancé s'il s'est arrêté ou s'il a dépassé le délai. Une demande à la
    fois (verrou) : l'aperçu les fait depuis son propre fil."""

    def __init__(self, command=None):
        self.command = list(command or worker_command())
        self._lock = threading.Lock()
        self._process = None
        self._answers = None
        self._log = None
        self._next = 0

    def _start(self):
        handle, log = tempfile.mkstemp(prefix="varians-preview-", suffix=".log")
        os.close(handle)
        self._log = log
        with open(log, "wb") as errors:
            self._process = subprocess.Popen(
                self.command + [log], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=errors,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        answers = queue.Queue()
        self._answers = answers

        def read(stream=self._process.stdout):
            for line in stream:
                answers.put(line)
            answers.put(None)                       # fin : le processus s'est arrêté

        threading.Thread(target=read, name="varians-preview-reader", daemon=True).start()

    def _stop(self):
        process, self._process = self._process, None
        if process is not None:
            try:
                process.kill()
                process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                pass
        if self._log:
            try:
                os.unlink(self._log)
            except OSError:
                pass
            self._log = None

    def _stderr_tail(self):
        try:
            return Path(self._log).read_text(encoding="utf-8", errors="replace").strip()[-2000:]
        except (OSError, TypeError):
            return ""

    def _ask(self, request, timeout):
        with self._lock:
            if self._process is None or self._process.poll() is not None:
                self._stop()
                self._start()
            self._next += 1
            request = dict(request, id=self._next)
            try:
                self._process.stdin.write(json.dumps(request, ensure_ascii=False).encode("utf-8") + b"\n")
                self._process.stdin.flush()
            except OSError as exc:
                detail = self._stderr_tail() or str(exc)
                self._stop()
                raise PreviewError("worker_failed", detail) from exc
            while True:
                try:
                    line = self._answers.get(timeout=timeout)
                except queue.Empty:
                    self._stop()
                    raise PreviewError("timeout", str(timeout)) from None
                if line is None:
                    detail = self._stderr_tail() or "no answer"
                    self._stop()
                    raise PreviewError("worker_failed", detail)
                try:
                    answer = json.loads(line.decode("utf-8"))
                except ValueError:
                    continue
                if answer.get("id") == request["id"]:
                    return answer

    def ping(self, timeout=PREVIEW_TIMEOUT_SEC):
        return self._ask({"op": "ping"}, timeout)

    def transform(self, xml_text, xslt, params, base="", edit_markers=True, timeout=PREVIEW_TIMEOUT_SEC):
        """HTML de ``xslt`` appliquée à ``xml_text`` (``PreviewResult``) ;
        ``PreviewError`` en cas d'échec."""
        answer = self._ask({"op": "transform", "xml": xml_text, "xslt": str(xslt),
                            "params": {str(k): str(v) for k, v in (params or {}).items()},
                            "base": str(base or ""), "edit_markers": bool(edit_markers)}, timeout)
        if not answer.get("ok"):
            raise PreviewError(answer.get("code") or "internal", answer.get("error") or "")
        return PreviewResult(answer.get("html") or "", bool(answer.get("compiled")), answer.get("engine") or "Saxon")

    def close(self):
        with self._lock:
            self._stop()


_CLIENT = None


def client():
    """Le processus d'aperçu de Varians, partagé ; arrêté à la sortie."""
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = SaxonPreviewClient()
        atexit.register(_CLIENT.close)
    return _CLIENT


if __name__ == "__main__":
    sys.exit(serve(stderr_log=sys.argv[-1] if len(sys.argv) > 1 and sys.argv[-1].endswith(".log") else None))
