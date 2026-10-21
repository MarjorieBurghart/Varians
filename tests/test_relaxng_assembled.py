# -*- coding: utf-8 -*-
"""Validation RELAX NG d'une édition assemblée par XInclude
(relaxng_validation.validate_assembled), sans Qt : chaque erreur est
rapportée dans son fichier, à sa ligne."""
from __future__ import annotations

import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from relaxng_validation import (ValidationIssue, _unique_issues, clear_relaxng_cache, validate_assembled,
                                validate_document, validate_relaxng)

DATA = Path(__file__).resolve().parent / "data" / "sermons"
# Tout élément et tout attribut sont permis, sauf l'attribut « typ » et les
# éléments XInclude : l'erreur volontaire du sermon 2 (<quote typ="thema">)
# est la seule du document assemblé.
PERMISSIVE = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><ref name="any"/></start>
  <define name="any">
    <element>
      <anyName><except><nsName ns="http://www.w3.org/2001/XInclude"/></except></anyName>
      <zeroOrMore><attribute><anyName><except><name ns="">typ</name></except></anyName></attribute></zeroOrMore>
      <mixed><zeroOrMore><ref name="any"/></zeroOrMore></mixed>
    </element>
  </define>
</grammar>
"""


@pytest.fixture
def schema(tmp_path):
    path = tmp_path / "permissive.rng"
    path.write_text(PERMISSIVE, encoding="utf-8")
    clear_relaxng_cache()
    yield path
    clear_relaxng_cache()


@pytest.fixture
def sermons(tmp_path):
    shutil.copytree(DATA, tmp_path / "sermons")
    return tmp_path / "sermons" / "xml"


def _validate(sermons, schema, parts=None, master_text=None):
    master = sermons / "edition.xml"
    text = master.read_text(encoding="utf-8") if master_text is None else master_text
    return validate_assembled(text, schema, master, parts)


def _located(result):
    return [(Path(i.file).name if i.file else "", i.line, i.message) for i in result.issues]


def test_an_error_in_a_part_is_reported_in_that_part(sermons, schema):
    result = _validate(sermons, schema)
    assert result.well_formed and not result.valid
    # libxml2 ajoute des erreurs en cascade (« Element p has extra content »…),
    # chacune à sa place.
    assert ("s02.xml", 27, "Invalid attribute typ for element quote") in _located(result)
    issue = next(i for i in result.issues if "typ" in i.message)
    assert Path(issue.file) == sermons / "sermons" / "s02.xml"


def test_without_assembly_the_inclusions_are_errors(sermons, schema):
    master = sermons / "edition.xml"
    result = validate_relaxng(master.read_text(encoding="utf-8"), schema, base_url=master)
    assert [(i.file, i.line) for i in result.issues][:1] == [("", 34)]          # premier xi:include


def test_an_error_in_the_edition_has_no_file(sermons, schema):
    s02 = sermons / "sermons" / "s02.xml"
    fixed = s02.read_text(encoding="utf-8").replace('typ="thema"', 'type="thema"')
    master_text = (sermons / "edition.xml").read_text(encoding="utf-8").replace(
        '<div type="praefatio"', '<div typ="praefatio"')
    result = _validate(sermons, schema, {s02: fixed}, master_text)
    assert ("", 27, "Invalid attribute typ for element div") in _located(result)
    assert all(i.file == "" for i in result.issues)


def test_the_unsaved_text_of_a_part_is_validated(sermons, schema):
    s02 = sermons / "sermons" / "s02.xml"
    fixed = s02.read_text(encoding="utf-8").replace('typ="thema"', 'type="thema"')
    assert _validate(sermons, schema, {s02: fixed}).valid
    s01 = sermons / "sermons" / "s01.xml"
    broken = s01.read_text(encoding="utf-8").replace('<head>', '<head typ="x">')
    located = _located(_validate(sermons, schema, {s02: fixed, s01: broken}))
    assert ("s01.xml", 3, "Invalid attribute typ for element head") in located
    assert "s02.xml" not in {name for name, _line, _message in located}


def test_the_same_error_in_two_files_is_kept_twice():
    # libxml2 s'arrête souvent à la première erreur d'un contenu : le
    # dédoublonnage est vérifié directement.
    entry = SimpleNamespace(line=1, column=0, level_name="ERROR", message="Invalid attribute typ",
                            domain_name="RELAXNGV", type_name="RNG_ERR")
    files = iter(["/p/a.xml", "/p/b.xml", "/p/a.xml"])
    issues = _unique_issues([entry, entry, entry], lambda _entry: next(files))
    assert [i.file for i in issues] == ["/p/a.xml", "/p/b.xml"]


def test_assembly_problems_are_issues_at_their_place(tmp_path, schema):
    (tmp_path / "bad.xml").write_text("<div>\n<p>\n</div>", encoding="utf-8")
    master = tmp_path / "edition.xml"
    master.write_text('<TEI xmlns:xi="http://www.w3.org/2001/XInclude">\n'
                      '<xi:include href="absent.xml"/>\n<xi:include href="bad.xml"/></TEI>', encoding="utf-8")
    result = validate_assembled(master.read_text(encoding="utf-8"), schema, master)
    assert result.well_formed and not result.valid
    assert [(Path(i.file).name if i.file else "", i.line, i.domain, i.type_name) for i in result.issues] == [
        ("", 2, "XINCLUDE", "missing"),
        ("bad.xml", 3, "XINCLUDE", "malformed"),
    ]
    assert "absent.xml" in result.issues[0].message


def test_a_malformed_edition_is_not_well_formed(tmp_path, schema):
    master = tmp_path / "edition.xml"
    master.write_text("<TEI>\n<text>", encoding="utf-8")
    result = validate_assembled(master.read_text(encoding="utf-8"), schema, master)
    expected = validate_relaxng(master.read_text(encoding="utf-8"), schema, base_url=master)
    assert result == expected and not result.well_formed


def test_a_missing_schema(sermons, tmp_path):
    result = _validate(sermons, tmp_path / "absent.rng")
    assert not result.schema_loaded and "absent.rng" in result.error


def test_validate_document_assembles_only_when_parts_are_given(sermons, schema):
    master = sermons / "edition.xml"
    text = master.read_text(encoding="utf-8")
    assert validate_document(text, schema, master) == validate_relaxng(text, schema, base_url=master)
    assert validate_document(text, schema, master, {}) == validate_assembled(text, schema, master, {})


def test_issues_of_older_callers_have_no_file():
    assert ValidationIssue(1, 2, "ERROR", "m").file == ""
