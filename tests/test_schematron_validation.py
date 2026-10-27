# -*- coding: utf-8 -*-
"""Validation RELAX NG puis Schematron (V0.9.2.3,
``relaxng_validation.validate_document(…, schematron=…)``), sans Qt ; tests
ignorés sans Saxon, sauf celui de son absence.

Les règles sont appliquées au même arbre que le RNG, s'il est bien formé et
que le RNG a pu être chargé ; une erreur Schematron rend le document
invalide, un avertissement ou une information non.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import schematron
from relaxng_validation import clear_relaxng_cache, validate_document
from xslt_scenarios import saxon_available

needs_saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
# Une racine <r>, des <p> et des <lg> ; un <x> est une erreur RELAX NG.
RNG = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><element name="r">
    <zeroOrMore><choice>
      <element name="p"><optional><attribute name="n"/></optional><text/></element>
      <element name="lg"><zeroOrMore><element name="l"><text/></element></zeroOrMore></element>
    </choice></zeroOrMore>
  </element></start>
</grammar>
"""
SCH = f"""<?xml version="1.0"?>
<schema xmlns="{SCH_NS}" queryBinding="xslt2">
  <pattern>
    <rule context="lg"><assert test="l">Groupe sans vers.</assert></rule>
    <rule context="p"><assert test="@n" role="warning">Paragraphe sans numéro.</assert></rule>
  </pattern>
</schema>
"""


@pytest.fixture(autouse=True)
def fresh_caches():
    clear_relaxng_cache()
    schematron.clear_cache()
    yield
    clear_relaxng_cache()
    schematron.clear_cache()


@pytest.fixture
def files(tmp_path):
    (tmp_path / "essai.rng").write_text(RNG, encoding="utf-8")
    (tmp_path / "regles.sch").write_text(SCH, encoding="utf-8")
    return tmp_path


def _validate(files, xml, schema="essai.rng", sources=("regles.sch",), parts=None, base="edition.xml"):
    return validate_document(xml, files / schema if schema else None, files / base, parts,
                             schematron=[files / source for source in sources])


def _located(result):
    return [(issue.domain, issue.line, issue.level) for issue in result.issues]


@needs_saxon
def test_a_schematron_error_makes_the_document_invalid(files):
    result = _validate(files, '<r>\n<p n="1">a</p>\n<lg/>\n</r>')
    assert result.schema_loaded and result.well_formed and not result.valid
    assert _located(result) == [("SCHEMATRON", 3, "ERROR")]
    assert result.issues[0].message == "Groupe sans vers."
    assert result.schematron_rules == (str(files / "regles.sch"),)
    assert result.schematron_errors == () and result.schematron_error == ""


@needs_saxon
def test_rng_errors_come_first(files):
    result = _validate(files, "<r>\n<x/>\n<lg/>\n</r>")
    assert not result.valid
    assert [(domain, line) for domain, line, _level in _located(result)] == [("RELAXNGV", 2), ("SCHEMATRON", 3)]


@needs_saxon
def test_warnings_alone_leave_the_document_valid(files):
    result = _validate(files, "<r>\n<p>a</p>\n<lg><l>v</l></lg>\n</r>")
    assert result.valid
    assert _located(result) == [("SCHEMATRON", 2, "WARNING")]


@needs_saxon
def test_the_rng_of_the_validation_can_be_a_source_without_rules(files):
    result = _validate(files, "<r><lg/></r>", sources=("essai.rng", "regles.sch"))
    assert result.schematron_rules == (str(files / "regles.sch"),) and not result.valid


@needs_saxon
def test_a_malformed_document_is_not_checked_by_the_rules(files):
    result = _validate(files, "<r><lg></r>")
    assert not result.well_formed and result.schematron_rules == ()
    assert all(issue.domain != "SCHEMATRON" for issue in result.issues)


@needs_saxon
def test_a_rng_that_cannot_be_loaded_stops_before_the_rules(files):
    result = _validate(files, "<r><lg/></r>", schema="absent.rng")
    assert not result.schema_loaded and result.schematron_rules == () and result.issues == ()


@needs_saxon
def test_rules_without_rng_check_a_well_formed_document(files):
    result = _validate(files, "<r>\n<lg/>\n<x/>\n</r>", schema=None)
    assert result.schema_loaded and result.well_formed and not result.valid
    assert _located(result) == [("SCHEMATRON", 2, "ERROR")]
    assert _validate(files, "<r><lg><l/></lg></r>", schema=None).valid
    malformed = _validate(files, "<r><lg></r>", schema=None)
    assert not malformed.well_formed and not malformed.valid and malformed.issues


@needs_saxon
def test_the_rules_check_the_assembled_edition_with_unsaved_parts(files):
    (files / "s01.xml").write_text("<lg><l>v</l></lg>\n", encoding="utf-8")
    master = '<r xmlns:xi="http://www.w3.org/2001/XInclude">\n<p n="1">a</p>\n<xi:include href="s01.xml"/>\n</r>'
    (files / "edition.xml").write_text(master, encoding="utf-8")
    assert _validate(files, master, parts={}).valid
    # Le texte non enregistré de la partie est celui qui est vérifié.
    result = _validate(files, master, parts={str(files / "s01.xml"): "\n\n<lg/>\n"})
    assert not result.valid
    assert [(Path(issue.file).name, issue.line, issue.domain) for issue in result.issues] == [
        ("s01.xml", 3, "SCHEMATRON")]


@needs_saxon
def test_an_assembled_edition_without_rng_is_also_checked(files):
    (files / "s01.xml").write_text("<lg/>\n", encoding="utf-8")
    master = '<r xmlns:xi="http://www.w3.org/2001/XInclude">\n<xi:include href="s01.xml"/>\n</r>'
    result = _validate(files, master, schema=None, parts={})
    assert [(Path(issue.file).name, issue.line) for issue in result.issues] == [("s01.xml", 1)]


@needs_saxon
def test_incorrect_rules_do_not_make_the_document_invalid(files):
    (files / "fautive.sch").write_text(SCH.replace('test="l"', 'test="l["'), encoding="utf-8")
    result = _validate(files, "<r><lg/></r>", sources=("fautive.sch",))
    assert result.valid and result.issues == () and result.schematron_rules == ()
    [(source, detail)] = result.schematron_errors
    assert source == str(files / "fautive.sch") and detail


def test_without_saxon_the_rng_validation_goes_on(files, monkeypatch):
    import xslt_engines
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    monkeypatch.setitem(sys.modules, "saxonche", None)
    result = _validate(files, "<r><lg/></r>")
    assert result.valid and result.issues == () and result.schematron_error == "saxon_missing"


def test_without_sources_nothing_changes(files):
    result = validate_document("<r><lg/></r>", files / "essai.rng", files / "edition.xml")
    assert result.valid and result.schematron_rules == () and result.schematron_errors == ()
    assert result.schematron_error == ""
