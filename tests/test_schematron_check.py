# -*- coding: utf-8 -*-
"""Vérification d'un fichier Schematron (V0.9.2.4, ``schematron_check``) et
reconnaissance de sa racine (``xml_roots.schematron_info``), sans Qt ; les
tests de la compilation sont ignorés sans Saxon.

Le texte vérifié est celui de l'éditeur, même non enregistré : bonne
formation, structure d'après le schéma ISO livré, inclusions, puis
compilation par SchXslt2 et Saxon (assemblage, expressions XPath)."""
from __future__ import annotations

import sys

import pytest
from lxml import etree

import schematron
from relaxng_worker import handle_request, result_from_dict
from schematron_check import ISO_SCHEMA, check
from xml_roots import SchematronInfo, root_tag, schematron_info
from xslt_scenarios import saxon_available, stylesheet_info

needs_saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
HEAD = f'<?xml version="1.0"?>\n<sch:schema xmlns:sch="{SCH_NS}" queryBinding="xslt2">\n'
# Ligne 3 : le groupe ; 4 : la règle ; 5 : l'assertion.
RULES = (HEAD
         + '  <sch:pattern id="vers">\n'
         + '    <sch:rule context="lg">\n'
         + '      <sch:assert test="l" severity="warning">Groupe sans vers.</sch:assert>\n'
         + '    </sch:rule>\n'
         + '  </sch:pattern>\n'
         + '</sch:schema>\n')


@pytest.fixture(autouse=True)
def fresh_cache():
    schematron.clear_cache()
    yield
    schematron.clear_cache()


def _check(tmp_path, text, name="regles.sch"):
    return check(text, tmp_path / name)


def _rows(result):
    return [(issue.domain, issue.type_name if issue.domain == "SCHEMATRON_RULES" else "", issue.line)
            for issue in result.issues]


# --- Le schéma livré et la racine ------------------------------------------------

def test_the_bundled_schema_compiles_and_says_it_was_modified():
    etree.RelaxNG(etree.parse(str(ISO_SCHEMA)))
    text = ISO_SCHEMA.read_text(encoding="utf-8")
    assert "THIS SCHEMA HAS BEEN MODIFIED FROM THE SCHEMA DEFINED IN ISO/IEC 19757-3" in text
    assert text.count('<attribute name="severity">') == 2


@pytest.mark.parametrize("text, expected", [
    (RULES, SchematronInfo("sch", "xslt2")),
    (f'<!-- règles -->\n<?xml-stylesheet x?>\n<schema xmlns="{SCH_NS}"><pattern/></schema>', SchematronInfo("", "")),
    # Inachevé pendant la frappe : la balise ouvrante suffit.
    (f'<s:schema xmlns:s="{SCH_NS}" queryBinding="xpath2">\n<s:pat', SchematronInfo("s", "xpath2")),
    ('<schema xmlns="http://www.w3.org/2001/XMLSchema"/>', None),
    (f'<sch:pattern xmlns:sch="{SCH_NS}"/>', None),
    ('<TEI xmlns="http://www.tei-c.org/ns/1.0"/>', None),
    ("", None),
])
def test_a_schematron_root_is_recognised(text, expected):
    assert schematron_info(text) == expected


def test_the_root_tag_is_shared_with_the_stylesheets():
    assert root_tag('<?xml version="1.0"?>\n<a:b xmlns:a="u" c=\'d\'>') == ("a:b", {"xmlns:a": "u", "c": "d"})
    assert stylesheet_info('<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" version="3.0"/>')
    assert schematron_info('<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"/>') is None


# --- Bonne formation, structure, inclusions ------------------------------------------

def test_correct_rules_are_valid(tmp_path):
    result = _check(tmp_path, RULES)
    assert result.well_formed and result.valid and result.issues == ()


def test_malformed_rules_are_not_checked_further(tmp_path):
    result = _check(tmp_path, RULES.replace("</sch:rule>", "</sch:regle>"))
    assert not result.well_formed and not result.valid
    assert any(issue.domain == "PARSER" and issue.line == 6 for issue in result.issues)


def test_a_structure_error_is_given_at_its_line(tmp_path):
    result = _check(tmp_path, RULES.replace('<sch:rule context="lg">', "<sch:rule>"))
    assert not result.valid
    assert any(domain == "RELAXNGV" and line == 4 for domain, _code, line in _rows(result))


def test_an_unknown_reference_is_given_at_the_line_of_its_element(tmp_path):
    text = RULES.replace("  <sch:pattern", '  <sch:phase id="tout">\n    <sch:active pattern="absent"/>\n'
                         '  </sch:phase>\n  <sch:pattern', 1)
    result = _check(tmp_path, text)
    assert not result.valid
    [issue] = [issue for issue in result.issues if "absent" in issue.message and issue.domain == "RELAXNGV"]
    assert issue.line == 4


def test_a_reference_to_an_included_pattern_is_not_an_error(tmp_path):
    (tmp_path / "motifs.sch").write_text(
        f'<sch:pattern xmlns:sch="{SCH_NS}" id="inclus">\n'
        '  <sch:rule context="p"><sch:assert test="@n">Sans numéro.</sch:assert></sch:rule>\n'
        '</sch:pattern>\n', encoding="utf-8")
    text = RULES.replace("  <sch:pattern", '  <sch:phase id="tout"><sch:active pattern="inclus"/></sch:phase>\n'
                         '  <sch:include href="motifs.sch"/>\n  <sch:pattern', 1)
    result = _check(tmp_path, text)
    assert result.valid and result.issues == ()


def test_a_missing_included_file_is_given_at_the_line_of_the_inclusion(tmp_path):
    text = RULES.replace("  <sch:pattern", '  <sch:include href="absent.sch"/>\n  <sch:pattern', 1)
    result = _check(tmp_path, text)
    assert not result.valid
    [issue] = result.issues
    assert (issue.domain, issue.type_name, issue.line) == ("SCHEMATRON_RULES", "missing", 3)
    assert issue.file == str((tmp_path / "regles.sch").resolve()) and "absent.sch" in issue.message


# --- Compilation ----------------------------------------------------------------------

@needs_saxon
def test_an_incorrect_xpath_expression_of_the_unsaved_text_is_given_at_its_line(tmp_path):
    (tmp_path / "regles.sch").write_text(RULES, encoding="utf-8")       # le fichier enregistré est correct
    result = _check(tmp_path, RULES.replace('test="l"', 'test="l["'))
    assert not result.valid and result.well_formed
    [issue] = result.issues
    assert (issue.domain, issue.type_name, issue.line) == ("SCHEMATRON_RULES", "xpath", 5)
    assert issue.file == str((tmp_path / "regles.sch").resolve())


@needs_saxon
def test_every_phase_is_compiled(tmp_path):
    text = RULES.replace("  <sch:pattern", '  <sch:phase id="vide"/>\n  <sch:pattern', 1).replace(
        'queryBinding="xslt2"', 'queryBinding="xslt2" defaultPhase="vide"')
    assert _check(tmp_path, text).valid
    result = _check(tmp_path, text.replace('test="l"', 'test="l["'))
    assert [(code, line) for _domain, code, line in _rows(result)] == [("xpath", 6)]


@needs_saxon
def test_an_inconsistency_of_the_assembled_rules_is_given_at_its_line(tmp_path):
    (tmp_path / "motifs.sch").write_text(
        f'<sch:pattern xmlns:sch="{SCH_NS}" id="vers">\n'
        '  <sch:rule context="p"><sch:assert test="@n">Sans numéro.</sch:assert></sch:rule>\n'
        '</sch:pattern>\n', encoding="utf-8")
    text = RULES.replace("</sch:schema>", '  <sch:include href="motifs.sch"/>\n</sch:schema>')
    result = _check(tmp_path, text)
    assert not result.valid
    [issue] = result.issues
    assert (issue.domain, issue.type_name, issue.line) == ("SCHEMATRON_RULES", "assembly", 1)
    assert issue.file == str((tmp_path / "motifs.sch").resolve()) and "vers" in issue.message


@needs_saxon
def test_an_unknown_diagnostic_is_reported(tmp_path):
    text = RULES.replace('test="l"', 'test="l" diagnostics="d"')
    result = _check(tmp_path, text)
    assert ("SCHEMATRON_RULES", "assembly", 5) in _rows(result)


def test_without_saxon_the_structure_is_still_checked(tmp_path, monkeypatch):
    import xslt_engines
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    monkeypatch.setitem(sys.modules, "saxonche", None)
    result = _check(tmp_path, RULES.replace('test="l"', 'test="l["'))
    assert result.valid and result.schematron_error == "saxon_missing"
    result = _check(tmp_path, RULES.replace('<sch:rule context="lg">', "<sch:rule>"))
    assert not result.valid and result.schematron_error == "saxon_missing"


# --- Processus de validation ---------------------------------------------------------

def test_the_validation_process_checks_a_schematron_text(tmp_path):
    response = handle_request({"id": 4, "op": "check_schematron", "text": RULES.replace("<sch:rule context", "<sch:rule x"),
                               "path": str(tmp_path / "regles.sch")})
    assert response["id"] == 4
    result = result_from_dict(response["result"])
    assert not result.valid and result.issues


@pytest.mark.parametrize("request_", [
    {"op": "check_schematron", "path": "regles.sch"},
    {"op": "check_schematron", "text": RULES},
    {"op": "check_schematron", "text": RULES, "path": ""},
])
def test_an_incomplete_check_request_is_refused(request_):
    response = handle_request(dict(request_, id=5))
    assert response == {"id": 5, "error": "check_schematron needs 'text' and 'path'"}


def test_the_module_needs_neither_qt_nor_saxon_to_be_imported():
    import subprocess
    code = "import sys, schematron_check; print('PySide6' in sys.modules, 'saxonche' in sys.modules)"
    output = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True,
                            cwd=str(ISO_SCHEMA.parents[3])).stdout
    assert output.split() == ["False", "False"]
