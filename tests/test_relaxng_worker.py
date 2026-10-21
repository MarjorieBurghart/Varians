# -*- coding: utf-8 -*-
"""Processus de validation RELAX NG (relaxng_worker), sans Qt : protocole JSON
par ligne, conversion des résultats, lancement par « editeur_tei.py
--relaxng-worker » comme dans une version autonome."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from relaxng_validation import ValidationIssue, ValidationResult, clear_relaxng_cache
from relaxng_worker import handle_request, result_from_dict, result_to_dict, serve

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><element name="root"><zeroOrMore><element name="p"><text/></element></zeroOrMore></element></start>
</grammar>
"""


@pytest.fixture
def schema(tmp_path):
    path = tmp_path / "essai.rng"
    path.write_text(SCHEMA, encoding="utf-8")
    clear_relaxng_cache()
    yield path
    clear_relaxng_cache()


def _validate(schema, xml, request_id=1):
    return handle_request({"id": request_id, "op": "validate", "xml": xml, "schema": str(schema),
                           "base_url": None})


def test_results_survive_a_json_round_trip():
    result = ValidationResult(True, True, True, False, (
        ValidationIssue(3, 7, "ERROR", "Did not expect element x there", "RELAXNGV", "RNG_ERR"),
        ValidationIssue(4, 1, "WARNING", "é « accents »"),
    ), "")
    assert result_from_dict(json.loads(json.dumps(result_to_dict(result)))) == result


def test_a_valid_document(schema):
    response = _validate(schema, "<root><p>a</p></root>")
    assert response["id"] == 1
    result = result_from_dict(response["result"])
    assert result.schema_loaded and result.well_formed and result.valid and result.issues == ()


def test_an_invalid_document_keeps_its_issues(schema):
    result = result_from_dict(_validate(schema, "<root>\n<x/>\n</root>")["result"])
    assert result.well_formed and not result.valid
    assert result.issues and result.issues[0].line == 2


def test_a_malformed_document(schema):
    result = result_from_dict(_validate(schema, "<root><p></root>")["result"])
    assert not result.well_formed and result.issues


def test_a_missing_schema(tmp_path):
    result = result_from_dict(_validate(tmp_path / "absent.rng", "<root/>")["result"])
    assert not result.schema_loaded and "absent.rng" in result.error


def test_the_compiled_schema_is_reused(schema):
    first = _validate(schema, "<root/>", 1)
    second = _validate(schema, "<root><p>b</p></root>", 2)
    assert first["compilations"] == second["compilations"] == 1


@pytest.mark.parametrize("request_, expected_id", [
    ("pas un objet", None),
    ({"id": 4, "op": "validate", "schema": "s.rng"}, 4),             # xml manquant
    ({"id": 5, "op": "validate", "xml": "<a/>", "schema": ""}, 5),    # schéma vide
    ({"id": 6, "op": "inconnue"}, 6),
])
def test_incorrect_requests_get_an_error(request_, expected_id):
    response = handle_request(request_)
    assert response["id"] == expected_id and response["error"]


def test_serve_answers_each_line_then_stops_at_end_of_input(schema):
    requests = [{"id": 1, "op": "ping"},
                {"id": 2, "op": "validate", "xml": "<root/>", "schema": str(schema)}]
    data = b"".join(json.dumps(r).encode("utf-8") + b"\n" for r in requests) + b"{incorrect\n"
    in_read, in_write = os.pipe()
    out_read, out_write = os.pipe()
    os.write(in_write, data)
    os.close(in_write)
    try:
        assert serve(in_read, out_write) == 0
    finally:
        os.close(in_read)
        os.close(out_write)
    with os.fdopen(out_read, "rb") as output:
        responses = [json.loads(line) for line in output.read().splitlines()]
    assert [r.get("id") for r in responses] == [1, 2, None]
    assert responses[0]["ok"] is True
    assert result_from_dict(responses[1]["result"]).valid
    assert "error" in responses[2]


def test_varians_itself_starts_the_worker_without_loading_qt(schema):
    # Même chemin qu'une version autonome : l'application relancée avec
    # --relaxng-worker, et non un fichier .py lancé à part.
    process = subprocess.run(
        [sys.executable, str(ROOT / "editeur_tei.py"), "--relaxng-worker"],
        input=(json.dumps({"id": 1, "op": "ping"}) + "\n"
               + json.dumps({"id": 2, "op": "validate", "xml": "<root/>", "schema": str(schema)}) + "\n"
               ).encode("utf-8"),
        capture_output=True, timeout=60, cwd=str(schema.parent))
    assert process.returncode == 0, process.stderr.decode("utf-8", "replace")
    ping, validation = (json.loads(line) for line in process.stdout.splitlines())
    assert ping["ok"] is True and ping["qt_loaded"] is False
    assert result_from_dict(validation["result"]).valid
