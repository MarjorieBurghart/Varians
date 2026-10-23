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
requête incorrecte reçoit aussi un compte rendu (``error_code`` internal).

Les descripteurs sont lus directement : ``sys.stdin`` et ``sys.stdout``
peuvent être absents dans une application Windows sans console.
"""
from __future__ import annotations

import json
import os
import sys

from xslt_engines import TransformResult, run


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
            result = run(request)
        else:
            result = TransformResult(False, error_code="internal", error="request must be a JSON object")
    answer = dict(result.to_dict(), qt_loaded="PySide6" in sys.modules)
    with os.fdopen(output_fd, "wb", closefd=False) as writer:
        writer.write(json.dumps(answer, ensure_ascii=False).encode("utf-8"))
        writer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
