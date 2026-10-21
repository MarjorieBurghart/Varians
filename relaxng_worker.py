# -*- coding: utf-8 -*-
"""Processus de validation RELAX NG, sans Qt (voir validation_worker).

Compiler un gros schéma (TEI_ALL : une dizaine de secondes) bloque tout le
processus qui le fait : lxml garde le verrou de Python pendant la compilation.
Varians valide donc dans ce processus à part, lancé une fois par session en se
relançant lui-même avec l'option ``--relaxng-worker`` (``python editeur_tei.py
--relaxng-worker`` depuis les sources, l'exécutable de l'application dans une
version autonome). Les schémas compilés restent en cache (relaxng_validation)
jusqu'à la fin du processus.

Une requête JSON par ligne sur le descripteur 0, une réponse par ligne sur le
descripteur 1 :

- ``{"id": 1, "op": "validate", "xml": "…", "schema": "chemin.rng",
  "base_url": "chemin.xml"}`` → ``{"id": 1, "result": {…}, "compilations": n}`` ;
  avec ``"parts": {"chemin": "texte"}`` (même vide), l'édition est validée
  assemblée par XInclude, le texte des parties ouvertes remplaçant celui des
  fichiers (``relaxng_validation.validate_document``) ;
- ``{"id": 2, "op": "ping"}`` → ``{"id": 2, "ok": true, "pid": …,
  "qt_loaded": false}`` ;
- une requête incorrecte → ``{"id": …, "error": "…"}``.

Les descripteurs sont lus directement : ``sys.stdin`` et ``sys.stdout``
peuvent être absents dans une application Windows sans console.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict

from relaxng_validation import ValidationIssue, ValidationResult, relaxng_cache_info, validate_document


def result_to_dict(result):
    """``ValidationResult`` → dictionnaire sérialisable en JSON."""
    data = asdict(result)
    data["issues"] = [asdict(issue) for issue in result.issues]
    return data


def result_from_dict(data):
    """Inverse de ``result_to_dict``."""
    issues = tuple(ValidationIssue(**issue) for issue in data.get("issues", ()))
    return ValidationResult(bool(data["available"]), bool(data["schema_loaded"]), bool(data["well_formed"]),
                            bool(data["valid"]), issues, str(data.get("error", "")))


def handle_request(request):
    """Réponse à une requête déjà décodée."""
    if not isinstance(request, dict):
        return {"id": None, "error": "request must be a JSON object"}
    request_id = request.get("id")
    op = request.get("op")
    if op == "ping":
        return {"id": request_id, "ok": True, "pid": os.getpid(), "qt_loaded": "PySide6" in sys.modules}
    if op == "validate":
        xml_text, schema = request.get("xml"), request.get("schema")
        if not isinstance(xml_text, str) or not isinstance(schema, str) or not schema:
            return {"id": request_id, "error": "validate needs 'xml' and 'schema'"}
        parts = request.get("parts")
        if parts is not None and not (isinstance(parts, dict) and all(
                isinstance(path, str) and isinstance(text, str) for path, text in parts.items())):
            return {"id": request_id, "error": "'parts' must map paths to texts"}
        result = validate_document(xml_text, schema, request.get("base_url") or None, parts)
        return {"id": request_id, "result": result_to_dict(result),
                "compilations": relaxng_cache_info()["compilations"]}
    return {"id": request_id, "error": f"unknown op: {op!r}"}


def serve(input_fd=0, output_fd=1):
    """Répond à chaque ligne reçue jusqu'à la fin de l'entrée."""
    reader = os.fdopen(input_fd, "rb", closefd=False)
    writer = os.fdopen(output_fd, "wb", closefd=False)
    for line in reader:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line.decode("utf-8"))
        except ValueError as exc:
            response = {"id": None, "error": f"invalid JSON: {exc}"}
        else:
            try:
                response = handle_request(request)
            except Exception as exc:                  # jamais d'arrêt sur une requête
                request_id = request.get("id") if isinstance(request, dict) else None
                response = {"id": request_id, "error": f"{type(exc).__name__}: {exc}"}
        writer.write(json.dumps(response, ensure_ascii=False).encode("utf-8") + b"\n")
        writer.flush()
    return 0


if __name__ == "__main__":
    sys.exit(serve())
