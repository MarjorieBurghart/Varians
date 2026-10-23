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

``finished`` est émis une fois par exécution, toujours dans le fil principal.
"""
from __future__ import annotations

import json
import os

from PySide6.QtCore import QObject, QProcess, Signal

from transform_worker import failed_worker, new_stderr_log, read_answer, worker_command
from xslt_engines import TransformResult


class TransformRunner(QObject):
    """Une exécution à la fois, dans son propre processus."""

    finished = Signal(object)

    def __init__(self, command=None, parent=None):
        super().__init__(parent)
        self._command = list(command or worker_command())
        self._process = None
        self._stderr_log = None
        self._cancelled = False
        self._done = True

    def running(self):
        return not self._done

    def start(self, request):
        """Lance l'exécution de ``request`` (une seule à la fois)."""
        if self.running():
            raise RuntimeError("une transformation est déjà en cours")
        self._cancelled = False
        self._done = False
        process = QProcess(self)
        self._process = process
        process.finished.connect(self._on_finished)
        process.errorOccurred.connect(self._on_error)
        process.setProgram(self._command[0])
        process.setArguments(self._command[1:])
        self._stderr_log = new_stderr_log()
        process.setStandardErrorFile(self._stderr_log)
        process.start()
        request = dict(request, stderr_log=self._stderr_log)
        process.write(json.dumps(request, ensure_ascii=False).encode("utf-8"))
        process.closeWriteChannel()

    def cancel(self):
        """Arrête l'exécution en cours."""
        if self.running() and self._process is not None:
            self._cancelled = True
            self._process.kill()

    def _on_error(self, error):
        # Un processus qui ne démarre pas n'émet pas ``finished``.
        if error == QProcess.ProcessError.FailedToStart:
            self._deliver(failed_worker(self._process.errorString()))

    def _on_finished(self, exit_code, exit_status):
        if self._cancelled:
            self._deliver(TransformResult(False, error_code="cancelled"))
            return
        self._deliver(read_answer(bytes(self._process.readAllStandardOutput()), self._stderr_log))

    def _deliver(self, result):
        if self._done:
            return
        self._done = True
        process, self._process = self._process, None
        if process is not None:
            process.deleteLater()
        if self._stderr_log is not None:
            try:
                os.unlink(self._stderr_log)
            except OSError:
                pass                          # encore ouvert par le processus (Windows) : fichier temporaire
            self._stderr_log = None
        self.finished.emit(result)
