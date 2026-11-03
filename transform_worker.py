# -*- coding: utf-8 -*-
"""Processus d'une transformation XSLT (scénarios, V0.9.2.0), sans Qt.

Chaque exécution d'un scénario a son propre processus : Varians relancé avec
l'option ``--transform-worker`` (``python editeur_tei.py --transform-worker``
depuis les sources, l'exécutable de l'application dans une version
autonome), comme pour ``relaxng_worker``. La fenêtre reste réactive,
« Annuler » arrête simplement le processus, et un plantage de Saxon (code
natif) ou une boucle sans fin n'emporte pas Varians.

Le processus lit sur le descripteur 0, jusqu'à la fin de l'entrée, une
requête JSON (``xslt_scenarios.scenario_request``), l'exécute
(``xslt_engines.run``) et écrit sur le descripteur 1 le compte rendu en JSON
(``TransformResult.to_dict``, plus ``qt_loaded``), puis s'arrête. Une
requête ``op: "check"`` (V0.9.2.1) compile seulement la feuille
(``xslt_engines.check``). Une requête incorrecte reçoit aussi un compte
rendu (``error_code`` internal).

Les descripteurs sont lus directement : ``sys.stdin`` et ``sys.stdout``
peuvent être absents dans une application Windows sans console.

La sortie d'erreur du processus est un fichier, donné dès sa création, dont
le chemin est dans la requête (``stderr_log``) : Saxon y écrit ses erreurs
avec leur lieu, et c'est la seule façon sûre de les lire sous Windows.
``run_in_process`` fait ainsi sans Qt ; ``transform_runner`` de même, avec
QProcess.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import xslt_engines
from xslt_engines import TransformResult, check, run

_APPLICATION_DIR = Path(__file__).resolve().parent


def worker_command():
    """Commande qui relance Varians en processus de transformation."""
    if getattr(sys, "frozen", False) or "__compiled__" in globals():     # PyInstaller…, Nuitka
        return [sys.executable, "--transform-worker"]
    return [sys.executable, str(_APPLICATION_DIR / "editeur_tei.py"), "--transform-worker"]


def new_stderr_log():
    """Fichier vide qui recevra la sortie d'erreur d'un processus."""
    handle, path = tempfile.mkstemp(prefix="varians-transform-", suffix=".log")
    os.close(handle)
    return path


def failed_worker(detail):
    return TransformResult(False, error_code="worker_failed", error=detail)


def read_answer(output, stderr_log):
    """Compte rendu d'après la réponse du processus (``worker_failed``, avec
    la fin de sa sortie d'erreur, s'il n'a pas répondu)."""
    try:
        return TransformResult.from_dict(json.loads(output.decode("utf-8")))
    except (ValueError, KeyError, TypeError, AttributeError):
        try:
            errors = Path(stderr_log).read_text(encoding="utf-8", errors="replace").strip()
        except OSError:
            errors = ""
        return failed_worker(errors[-2000:] or "no answer")


def run_in_process(request, command=None, timeout=None):
    """Exécute ``request`` dans un processus de transformation et rend son
    compte rendu (sans Qt ; Varians passe par ``transform_runner``)."""
    stderr_log = new_stderr_log()
    try:
        with open(stderr_log, "wb") as errors:
            try:
                completed = subprocess.run(
                    command or worker_command(), input=json.dumps(dict(request, stderr_log=stderr_log)).encode("utf-8"),
                    stdout=subprocess.PIPE, stderr=errors, timeout=timeout,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return failed_worker(str(exc))
        return read_answer(completed.stdout, stderr_log)
    finally:
        try:
            os.unlink(stderr_log)
        except OSError:
            pass


def serve(input_fd=0, output_fd=1):
    """Exécute la requête reçue et écrit son compte rendu."""
    with os.fdopen(input_fd, "rb", closefd=False) as reader:
        data = reader.read()
    try:
        request = json.loads(data.decode("utf-8"))
    except ValueError as exc:
        result = TransformResult(False, error_code="internal", error=f"invalid JSON: {exc}")
    else:
        if isinstance(request, dict):
            # Vérifier une feuille ne consulte pas le réseau (red team, B5) ;
            # appelée hors du processus de transformation (tests), le réglage
            # précédent est ensuite rendu.
            previous = xslt_engines.CHECKS_LOCAL_ONLY
            xslt_engines.CHECKS_LOCAL_ONLY = request.get("op") == "check"
            try:
                result = check(request) if request.get("op") == "check" else run(request)
            finally:
                xslt_engines.CHECKS_LOCAL_ONLY = previous
        else:
            result = TransformResult(False, error_code="internal", error="request must be a JSON object")
    answer = dict(result.to_dict(), qt_loaded="PySide6" in sys.modules)
    with os.fdopen(output_fd, "wb", closefd=False) as writer:
        writer.write(json.dumps(answer, ensure_ascii=False).encode("utf-8"))
        writer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
