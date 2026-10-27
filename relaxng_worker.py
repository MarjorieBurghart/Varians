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
  fichiers (``relaxng_validation.validate_document``) ; avec
  ``"schematron": ["chemin", …]`` (V0.9.2.3), les règles Schematron de ces
  sources sont appliquées ensuite (``"schema"`` peut alors être vide) ; une
  source peut être ``["chemin", "phase"]`` (V0.9.2.4) ;
- ``{"id": 3, "op": "check_schematron", "text": "…", "path": "regles.sch"}``
  (V0.9.2.4) → ``{"id": 3, "result": {…}}`` : la vérification du texte d'un
  fichier Schematron (``schematron_check.check``) ;
- ``{"id": 2, "op": "ping"}`` → ``{"id": 2, "ok": true, "pid": …,
  "qt_loaded": false}`` ;
- une requête incorrecte → ``{"id": …, "error": "…"}``.

Les descripteurs sont lus directement : ``sys.stdin`` et ``sys.stdout``
peuvent être absents dans une application Windows sans console. La sortie
d'erreur est le fichier que nomme la variable ``VARIANS_STDERR_LOG`` (voir
validation_worker) : Saxon y écrit le détail d'une règle incorrecte.
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
    data["schematron_errors"] = [asdict(issue) for issue in result.schematron_errors]
    return data


def _rules_error(item):
    """Une règle incorrecte reçue : un ``ValidationIssue``, ou la forme
    ``(source, détail)`` de la V0.9.2.3."""
    if isinstance(item, dict):
        return ValidationIssue(**item)
    source, detail = item
    return ValidationIssue(0, 0, "ERROR", str(detail), "SCHEMATRON_RULES", "compile", str(source))


def _valid_sources(sources):
    """Vrai pour une liste de chemins ou de couples ``[chemin, phase]``."""
    return isinstance(sources, list) and all(
        (isinstance(item, str) and item) or (
            isinstance(item, list) and len(item) == 2 and all(isinstance(part, str) for part in item) and item[0])
        for item in sources)


def result_from_dict(data):
    """Inverse de ``result_to_dict``."""
    issues = tuple(ValidationIssue(**issue) for issue in data.get("issues", ()))
    return ValidationResult(bool(data["available"]), bool(data["schema_loaded"]), bool(data["well_formed"]),
                            bool(data["valid"]), issues, str(data.get("error", "")),
                            schematron_rules=tuple(str(path) for path in data.get("schematron_rules", ())),
                            schematron_errors=tuple(_rules_error(item) for item in data.get("schematron_errors", ())),
                            schematron_error=str(data.get("schematron_error", "")))


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
        sources = request.get("schematron")
        if sources is not None and not _valid_sources(sources):
            return {"id": request_id, "error": "'schematron' must be a list of paths or [path, phase]"}
        if not isinstance(xml_text, str) or not isinstance(schema, str) or not (schema or sources):
            return {"id": request_id, "error": "validate needs 'xml' and 'schema'"}
        parts = request.get("parts")
        if parts is not None and not (isinstance(parts, dict) and all(
                isinstance(path, str) and isinstance(text, str) for path, text in parts.items())):
            return {"id": request_id, "error": "'parts' must map paths to texts"}
        result = validate_document(xml_text, schema or None, request.get("base_url") or None, parts, sources)
        return {"id": request_id, "result": result_to_dict(result),
                "compilations": relaxng_cache_info()["compilations"]}
    if op == "check_schematron":
        text, path = request.get("text"), request.get("path")
        if not isinstance(text, str) or not isinstance(path, str) or not path:
            return {"id": request_id, "error": "check_schematron needs 'text' and 'path'"}
        from schematron_check import check
        return {"id": request_id, "result": result_to_dict(check(text, path))}
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
