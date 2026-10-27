# -*- coding: utf-8 -*-
"""Processus de validation RELAX NG (relaxng_worker), sans Qt : protocole JSON
par ligne, conversion des résultats, lancement par « editeur_tei.py
--relaxng-worker » comme dans une version autonome."""
from __future__ import annotations

import importlib.util
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
        ValidationIssue(27, 0, "ERROR", "Invalid attribute", "RELAXNGV", "RNG_ERR", "/projet/xml/s02.xml"),
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


def test_an_assembled_edition_is_validated_with_its_parts(tmp_path, schema):
    (tmp_path / "part.xml").write_text("<p>\n<x/></p>", encoding="utf-8")
    master = tmp_path / "edition.xml"
    master.write_text('<root xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="part.xml"/></root>',
                      encoding="utf-8")
    request = {"id": 7, "op": "validate", "xml": master.read_text(encoding="utf-8"), "schema": str(schema),
               "base_url": str(master), "parts": {}}
    result = result_from_dict(handle_request(request)["result"])
    assert [(Path(i.file).name, i.line) for i in result.issues] == [("part.xml", 2)]
    # Le texte non enregistré de la partie est celui qui est validé.
    request["parts"] = {str(tmp_path / "part.xml"): "<p>b</p>"}
    assert result_from_dict(handle_request(request)["result"]).valid


def test_parts_must_be_texts(schema):
    response = handle_request({"id": 8, "op": "validate", "xml": "<root/>", "schema": str(schema),
                               "parts": {"a.xml": 3}})
    assert response["id"] == 8 and response["error"]


# --- Règles Schematron (V0.9.2.3) -------------------------------------------------

SCHEMATRON = """<?xml version="1.0"?>
<schema xmlns="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2">
  <pattern>
    <rule context="p">
      <assert test="string-length(.) &gt; 1">Paragraphe trop court.</assert>
    </rule>
  </pattern>
</schema>
"""
needs_saxon = pytest.mark.skipif(importlib.util.find_spec("saxonche") is None,
                                 reason="Saxon (saxonche) n'est pas installé")


def test_schematron_results_survive_a_json_round_trip():
    result = ValidationResult(True, True, True, False, (
        ValidationIssue(2, 0, "ERROR", "Paragraphe trop court.", "SCHEMATRON", "court", "/projet/s02.xml"),
    ), "", schematron_rules=("/projet/regles.sch", "/projet/tei_all.rng"),
        schematron_errors=(("/projet/fautive.sch", "fautive.sch:3: XPST0003 …"),), schematron_error="")
    assert result_from_dict(json.loads(json.dumps(result_to_dict(result)))) == result
    # Une réponse d'une version précédente, sans ces champs.
    old = result_to_dict(ValidationResult(True, True, True, True, ()))
    for name in ("schematron_rules", "schematron_errors", "schematron_error"):
        old.pop(name)
    assert result_from_dict(old) == ValidationResult(True, True, True, True, ())


@needs_saxon
def test_a_request_can_name_schematron_sources(tmp_path, schema):
    rules = tmp_path / "regles.sch"
    rules.write_text(SCHEMATRON, encoding="utf-8")
    request = {"id": 9, "op": "validate", "xml": "<root>\n<p>a</p>\n</root>", "schema": str(schema),
               "schematron": [str(rules)]}
    result = result_from_dict(handle_request(request)["result"])
    assert not result.valid and [(i.domain, i.line) for i in result.issues] == [("SCHEMATRON", 2)]
    assert result.schematron_rules == (str(rules),)
    # Sans RNG : les règles seules.
    request["schema"] = ""
    assert result_from_dict(handle_request(request)["result"]).issues[0].message == "Paragraphe trop court."


@pytest.mark.parametrize("sources", ["regles.sch", [3], {"a": "b"}])
def test_schematron_sources_must_be_a_list_of_paths(schema, sources):
    response = handle_request({"id": 10, "op": "validate", "xml": "<root/>", "schema": str(schema),
                               "schematron": sources})
    assert response["id"] == 10 and response["error"]


@needs_saxon
def test_the_worker_reports_where_an_incorrect_rule_is(tmp_path, schema):
    # Comme dans Varians (validation_worker) : la sortie d'erreur du
    # processus est un fichier, nommé par VARIANS_STDERR_LOG ; sous Windows,
    # Saxon n'écrit qu'à cet endroit le détail d'une erreur de compilation.
    rules = tmp_path / "fautive.sch"
    rules.write_text(SCHEMATRON.replace("string-length(.) &gt; 1", "string-length(. &gt; 1"), encoding="utf-8")
    log = tmp_path / "stderr.log"
    request = {"id": 1, "op": "validate", "xml": "<root><p>a</p></root>", "schema": str(schema),
               "schematron": [str(rules)]}
    with open(log, "wb") as errors:
        process = subprocess.run(
            [sys.executable, str(ROOT / "editeur_tei.py"), "--relaxng-worker"],
            input=(json.dumps(request) + "\n").encode("utf-8"), stdout=subprocess.PIPE, stderr=errors,
            timeout=120, cwd=str(tmp_path), env=dict(os.environ, VARIANS_STDERR_LOG=str(log)))
    assert process.returncode == 0, log.read_text(encoding="utf-8", errors="replace")
    result = result_from_dict(json.loads(process.stdout.splitlines()[0])["result"])
    assert result.valid and result.issues == ()
    [(source, detail)] = result.schematron_errors
    assert source == str(rules) and detail.startswith("fautive.sch:5: XPST0003")
