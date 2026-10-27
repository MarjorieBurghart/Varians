# -*- coding: utf-8 -*-
"""Règles Schematron (V0.9.2.3, schematron.py), sans Qt ; tests ignorés
sans Saxon, sauf ceux du dossier livré.

Les schémas sont fabriqués pour l'essai : des RNG avec des règles intégrées
(comme tei_all.rng, dont une règle est reprise telle quelle) et des fichiers
``.sch``. SchXslt2 (resources/schxslt2/transpile.xsl) les transforme en
feuilles XSLT 3.0 que Saxon applique au document.
"""
from __future__ import annotations

import hashlib
import os
import sys
import time
from pathlib import Path

import pytest
from lxml import etree

import schematron
from schematron import SCHXSLT_DIR, compiled, rules_text, validate
from xml_assembly import assemble
from xslt_scenarios import saxon_available

needs_saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
SCH = "http://purl.oclc.org/dsdl/schematron"
TEI = "http://www.tei-c.org/ns/1.0"

# Une règle de tei_all.rng (TEI P5 4.10.2), telle qu'elle y figure : la
# déclaration sch:ns est à la fin de la grammaire, comme dans tei_all.
TEI_RNG = f"""<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" xmlns:tei="{TEI}" ns="{TEI}">
  <start><ref name="any"/></start>
  <define name="any">
    <element><anyName/>
      <zeroOrMore><attribute><anyName/></attribute></zeroOrMore>
      <mixed><zeroOrMore><ref name="any"/></zeroOrMore></mixed>
    </element>
    <pattern xmlns="http://purl.oclc.org/dsdl/schematron"
             xmlns:rng="http://relaxng.org/ns/structure/1.0"
             id="tei_all-lg-atleast1oflggapl-constraint-rule-23">
      <sch:rule xmlns="{TEI}" xmlns:sch="http://purl.oclc.org/dsdl/schematron" context="tei:lg">
        <sch:assert test="count(descendant::tei:lg|descendant::tei:l|descendant::tei:gap) &gt; 0">An lg element must contain at least one child l, lg, or gap element.</sch:assert>
      </sch:rule>
    </pattern>
  </define>
  <include href="dates.rng"/>
  <sch:ns xmlns:sch="{SCH}" prefix="tei" uri="{TEI}"/>
</grammar>
"""
# Le RNG inclus : une règle sur un attribut, qui emploie XPath 2.0
# (matches), et une seconde déclaration du préfixe tei.
DATES_RNG = f"""<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" xmlns:sch="{SCH}">
  <sch:ns prefix="tei" uri="{TEI}"/>
  <sch:pattern id="dates">
    <sch:rule context="tei:date/@when" id="when-iso">
      <sch:assert test="matches(., '^\\d{{4}}(-\\d{{2}}){{0,2}}$')" id="when-format">La date « <sch:value-of select="."/> » n'est pas au format AAAA-MM-JJ.</sch:assert>
    </sch:rule>
  </sch:pattern>
</grammar>
"""
PLAIN_RNG = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><element><anyName/><text/></element></start>
</grammar>
"""
DOC = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}">
  <text><body>
    <lg/>
    <p>Le <date when="1290-03-01">1er mars</date>,
       le <date
           when="mars 1290">même mois</date>.</p>
  </body></text>
</TEI>
"""


def _sch(body, query_binding="xslt2", extra=""):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<schema xmlns="{SCH}" queryBinding="{query_binding}"{extra}>
  <ns prefix="tei" uri="{TEI}"/>
{body}
</schema>
"""


@pytest.fixture(autouse=True)
def fresh_cache():
    schematron.clear_cache()
    yield
    schematron.clear_cache()


@pytest.fixture
def tei_rng(tmp_path):
    (tmp_path / "dates.rng").write_text(DATES_RNG, encoding="utf-8")
    path = tmp_path / "tei-mini.rng"
    path.write_text(TEI_RNG, encoding="utf-8")
    return path


def _write(tmp_path, name, text):
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return path


def _tree(text, path=None):
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    return etree.fromstring(text.encode("utf-8"), parser,
                            base_url=str(path) if path else None).getroottree()


def _found(report):
    return [(issue.line, issue.level, issue.message) for issue in report.issues]


# --- Le dossier livré ---------------------------------------------------------

def test_schxslt2_is_bundled_with_its_licence_and_a_readme():
    transpiler = SCHXSLT_DIR / "transpile.xsl"
    head = transpiler.read_text(encoding="utf-8")[:1500]
    assert "Copyright (C) by David Maus" in head
    assert "Permission is hereby granted, free of charge" in head
    readme = (SCHXSLT_DIR / "LISEZMOI.md").read_text(encoding="utf-8")
    assert "1.11.2" in readme and "MIT" in readme
    # L'empreinte notée dans le LISEZMOI est celle du fichier livré.
    assert hashlib.sha256(transpiler.read_bytes()).hexdigest() in readme


# --- Les règles d'une source ----------------------------------------------------

def test_the_rules_of_a_rng_gather_namespaces_and_patterns_of_included_files(tei_rng):
    schema = etree.fromstring(rules_text(tei_rng).encode("utf-8"))
    assert etree.QName(schema).namespace == SCH and schema.get("queryBinding") == "xslt2"
    declared = [(ns.get("prefix"), ns.get("uri")) for ns in schema.findall(f"{{{SCH}}}ns")]
    assert declared == [("tei", TEI)]
    patterns = [pattern.get("id") for pattern in schema.findall(f"{{{SCH}}}pattern")]
    assert patterns == ["tei_all-lg-atleast1oflggapl-constraint-rule-23", "dates"]


def test_a_rng_without_rules_has_none(tmp_path):
    assert rules_text(_write(tmp_path, "plain.rng", PLAIN_RNG)) is None


def test_a_sch_file_is_taken_as_it_is(tmp_path):
    text = _sch('<pattern><rule context="tei:lg"><assert test="*">vide</assert></rule></pattern>')
    rules = rules_text(_write(tmp_path, "regles.sch", text))
    assert etree.tostring(etree.fromstring(rules.encode("utf-8"))) == etree.tostring(
        etree.fromstring(text.encode("utf-8")))


# --- Validation -----------------------------------------------------------------

@needs_saxon
def test_the_rules_of_a_rng_report_their_messages_at_their_lines(tmp_path, tei_rng):
    report = validate(_tree(DOC), [tei_rng])
    assert report.error == "" and report.errors == ()
    assert report.rules == (str(tei_rng),)
    assert _found(report) == [
        (4, "ERROR", "An lg element must contain at least one child l, lg, or gap element."),
        # La règle porte sur l'attribut : la ligne de son élément (celle où
        # finit sa balise ouvrante, comme pour une erreur RELAX NG).
        (7, "ERROR", "La date « mars 1290 » n'est pas au format AAAA-MM-JJ."),
    ]
    issue = report.issues[1]
    assert issue.domain == "SCHEMATRON" and issue.type_name == "when-format" and issue.file == ""
    assert report.issues[0].type_name == "tei_all-lg-atleast1oflggapl-constraint-rule-23"


@needs_saxon
def test_a_valid_document_has_no_message(tmp_path, tei_rng):
    text = DOC.replace("<lg/>", "<lg><l>vers</l></lg>").replace("mars 1290", "1290-03")
    report = validate(_tree(text), [tei_rng])
    assert report.issues == () and report.rules == (str(tei_rng),)


@needs_saxon
def test_a_rng_without_rules_is_not_counted(tmp_path):
    report = validate(_tree(DOC), [_write(tmp_path, "plain.rng", PLAIN_RNG)])
    assert report.issues == () and report.rules == () and report.errors == ()


@needs_saxon
@pytest.mark.parametrize("query_binding", ["xslt", "xslt2", "xslt3"])
def test_a_sch_file_is_applied_whatever_its_query_binding(tmp_path, query_binding):
    sch = _write(tmp_path, "regles.sch", _sch(
        '<pattern><rule context="tei:lg"><assert test="tei:l">Un groupe de vers sans vers.</assert></rule></pattern>',
        query_binding))
    report = validate(_tree(DOC), [sch])
    assert _found(report) == [(4, "ERROR", "Un groupe de vers sans vers.")]


@needs_saxon
def test_the_rules_of_several_sources_are_all_applied(tmp_path, tei_rng):
    sch = _write(tmp_path, "regles.sch", _sch(
        '<pattern><rule context="tei:p"><report test="tei:date">Un paragraphe daté.</report></rule></pattern>'))
    report = validate(_tree(DOC), [tei_rng, sch])
    assert report.rules == (str(tei_rng), str(sch))
    assert [line for line, _level, _message in _found(report)] == [4, 7, 5]


@needs_saxon
def test_only_the_default_phase_is_checked(tmp_path):
    body = """
  <phase id="vers"><active pattern="lg"/></phase>
  <phase id="tout"><active pattern="lg"/><active pattern="p"/></phase>
  <pattern id="lg"><rule context="tei:lg"><assert test="tei:l">Groupe sans vers.</assert></rule></pattern>
  <pattern id="p"><rule context="tei:p"><report test="true()">Paragraphe.</report></rule></pattern>"""
    sch = _write(tmp_path, "phases.sch", _sch(body, extra=' defaultPhase="vers"'))
    assert _found(validate(_tree(DOC), [sch])) == [(4, "ERROR", "Groupe sans vers.")]
    # Sans phase par défaut, toutes les règles.
    sch.write_text(_sch(body), encoding="utf-8")
    assert len(validate(_tree(DOC), [sch]).issues) == 2


@needs_saxon
def test_role_and_severity_give_the_level(tmp_path):
    asserts = "".join(f'<report test="true()" {attribute}>{attribute}</report>' for attribute in (
        'role="warning"', 'role="warn"', 'role="nonfatal"', 'role="info"', 'role="information"', 'role="error"',
        'role="fatal"', 'role="autre"', 'severity="warning"', 'severity="info"', 'severity="error"',
        'severity="fatal"', 'role="info" severity="error"', ''))
    sch = _write(tmp_path, "niveaux.sch", _sch(f'<pattern><rule context="tei:lg">{asserts}</rule></pattern>'))
    levels = [(message, level) for _line, level, message in _found(validate(_tree(DOC), [sch]))]
    assert levels == [
        ('role="warning"', "WARNING"), ('role="warn"', "WARNING"), ('role="nonfatal"', "WARNING"),
        ('role="info"', "INFO"), ('role="information"', "INFO"), ('role="error"', "ERROR"),
        ('role="fatal"', "ERROR"), ('role="autre"', "ERROR"), ('severity="warning"', "WARNING"),
        ('severity="info"', "INFO"), ('severity="error"', "ERROR"), ('severity="fatal"', "ERROR"),
        # @severity l'emporte sur @role.
        ('role="info" severity="error"', "ERROR"), ("", "ERROR"),
    ]


@needs_saxon
def test_the_message_is_the_text_with_normalized_spaces(tmp_path):
    sch = _write(tmp_path, "texte.sch", _sch("""
  <pattern><rule context="tei:date[@when = 'mars 1290']">
    <assert test="false()">La date
       <value-of select="@when"/>   (<name/>)
       est fautive.</assert>
  </rule></pattern>"""))
    assert _found(validate(_tree(DOC), [sch])) == [(7, "ERROR", "La date mars 1290 (date) est fautive.")]


@needs_saxon
def test_an_error_in_a_part_of_an_assembled_edition_is_reported_in_that_part(tmp_path):
    part = _write(tmp_path, "s01.xml", f"""<?xml version="1.0"?>
<div xmlns="{TEI}">
  <p>Un sermon.</p>
  <lg/>
</div>
""")
    master_text = f"""<?xml version="1.0"?>
<TEI xmlns="{TEI}" xmlns:xi="http://www.w3.org/2001/XInclude">
  <text><body>
    <lg/>
    <xi:include href="s01.xml"/>
  </body></text>
</TEI>
"""
    master = _write(tmp_path, "edition.xml", master_text)
    assembly = assemble(master_text, master)
    sch = _write(tmp_path, "regles.sch", _sch(
        '<pattern><rule context="tei:lg"><assert test="tei:l">Groupe sans vers.</assert></rule></pattern>'))

    def file_of(element):
        origin = assembly.origin(element)
        return "" if origin == assembly.master else str(origin)

    report = validate(assembly.root.getroottree(), [sch], file_of)
    assert [(Path(issue.file).name if issue.file else "", issue.line) for issue in report.issues] == [
        ("", 4), ("s01.xml", 4)]


@needs_saxon
def test_the_address_of_the_document_is_the_one_given(tmp_path):
    # L'adresse que garde lxml peut être inutilisable (sous Windows :
    # « D:a/… ») : c'est celle que donne Varians qui compte.
    sch = _write(tmp_path, "adresse.sch", _sch(
        '<pattern><rule context="/*"><assert test="ends-with(base-uri(/), \'/donne/edition.xml\')">'
        '<value-of select="base-uri(/)"/></assert></rule></pattern>'))
    tree = _tree(DOC, "ailleurs/edition.xml")
    assert validate(tree, [sch], base=tmp_path / "donne" / "edition.xml").issues == ()
    # Sans adresse donnée, aucune.
    [issue] = validate(tree, [sch]).issues
    assert "ailleurs" not in issue.message


@needs_saxon
def test_an_incorrect_rule_is_an_error_of_the_rules_not_of_the_document(tmp_path, tei_rng):
    bad = _write(tmp_path, "fautive.sch", _sch(
        '<pattern><rule context="tei:lg"><assert test="tei:l[">vide</assert></rule></pattern>'))
    report = validate(_tree(DOC), [bad, tei_rng])
    # Les autres règles sont appliquées.
    assert len(report.issues) == 2 and report.rules == (str(tei_rng),)
    [(source, detail)] = report.errors
    # Le détail de Saxon (l'expression fautive) : sous Windows, il n'est que
    # sur la sortie d'erreur (voir test_relaxng_worker).
    assert source == str(bad) and detail and report.error == ""


def test_the_detail_of_an_incorrect_rule_gives_its_file_and_line(tmp_path):
    # Message de Saxon pour la feuille produite par SchXslt2 : l'assertion y
    # est entourée de not(…), son lieu est celui de cette feuille.
    _write(tmp_path, "motif.sch", f"""<pattern xmlns="{SCH}">
  <rule context="tei:lg">
    <assert test="tei:l[">vide</assert>
  </rule>
</pattern>
""")
    sch = _write(tmp_path, "regles.sch", _sch('<include href="motif.sch"/>'))
    exc = Exception(" Error in {not(tei:l[)} at char 12 in if/@test on line 1 column 1705 of file:///x/:\n"
                    "  XPST0003  Unexpected token ) before ...\n")
    assert schematron._saxon_text(exc, sch.resolve()) == "motif.sch:3: XPST0003 Unexpected token ) before ..."
    # Expression introuvable dans la source : elle suit le message.
    other = Exception(" Error in {count()} at char 5 in if/@test on line 1 column 9 of file:///x/:\n"
                      "  XPST0017  Cannot find a 0-argument function named\n  Q{fn}count()\n")
    assert schematron._saxon_text(other, sch.resolve()) == (
        "XPST0017 Cannot find a 0-argument function named Q{fn}count() : count()")


def test_a_truncated_expression_still_gives_the_line_of_its_rule(tmp_path):
    # Saxon abrège une longue expression (« … g... ») ; une autre règle
    # (contexte tei:rdg) figure en entier dans ce qui reste.
    sch = _write(tmp_path, "apparat.sch", _sch("""
  <pattern>
    <rule context="tei:app">
      <assert test="count(tei:lem | tei:rdg)
                    ge">Une seule leçon.</assert>
    </rule>
    <rule context="tei:rdg"><assert test="@wit">Sans témoin.</assert></rule>
  </pattern>"""))
    exc = Exception(" Error in {not(count(tei:lem | tei:rdg) g...} at char 33 in if/@test on line 1 column 2329"
                    " of file:///x/:\n  XPST0003  Unexpected token ) before ...\n")
    # La ligne est celle où finit la balise ouvrante (convention de lxml).
    assert schematron._saxon_text(exc, sch.resolve()) == "apparat.sch:8: XPST0003 Unexpected token ) before ..."


@needs_saxon
def test_a_rule_reads_a_document_relative_to_its_source(tmp_path):
    folder = tmp_path / "regles"
    folder.mkdir()
    _write(folder, "dates.xml", "<dates><d>1290-03-01</d></dates>")
    sch = _write(folder, "liste.sch", _sch(
        '<pattern><rule context="tei:date"><assert test="@when = doc(\'dates.xml\')//d">'
        'Date hors de la liste.</assert></rule></pattern>'))
    assert _found(validate(_tree(DOC), [sch])) == [(7, "ERROR", "Date hors de la liste.")]


@needs_saxon
def test_a_missing_or_malformed_source_is_an_error_of_the_rules(tmp_path):
    missing = tmp_path / "absente.sch"
    malformed = _write(tmp_path, "malformee.sch", "<schema xmlns='http://purl.oclc.org/dsdl/schematron'>")
    report = validate(_tree(DOC), [missing, malformed])
    assert report.issues == () and report.rules == ()
    assert [source for source, _detail in report.errors] == [str(missing), str(malformed)]
    assert all(detail for _source, detail in report.errors)


@needs_saxon
def test_a_dynamic_error_of_a_rule_is_an_error_of_the_rules(tmp_path):
    sch = _write(tmp_path, "dynamique.sch", _sch(
        '<ns prefix="xs" uri="http://www.w3.org/2001/XMLSchema"/>'
        '<pattern><rule context="tei:date"><assert test="xs:integer(@when) gt 0">nombre</assert></rule></pattern>'))
    report = validate(_tree(DOC), [sch])
    assert report.issues == ()
    [(source, detail)] = report.errors
    assert source == str(sch) and "1290-03-01" in detail


@needs_saxon
def test_a_sch_file_can_include_another_one(tmp_path):
    _write(tmp_path, "motif.sch", f"""<pattern xmlns="{SCH}" id="inclus">
  <rule context="tei:lg"><assert test="tei:l">Inclus : groupe sans vers.</assert></rule>
</pattern>
""")
    sch = _write(tmp_path, "principal.sch", _sch('<include href="motif.sch"/>'))
    assert _found(validate(_tree(DOC), [sch])) == [(4, "ERROR", "Inclus : groupe sans vers.")]


# --- Cache ------------------------------------------------------------------------

@needs_saxon
def test_the_rules_are_compiled_once_then_again_when_a_file_changes(tmp_path, tei_rng):
    validate(_tree(DOC), [tei_rng])
    validate(_tree(DOC), [tei_rng])
    assert schematron.cache_info()["compilations"] == 1
    assert compiled(tei_rng) is compiled(tei_rng)
    # Une modification du RNG inclus suffit.
    dates = tei_rng.parent / "dates.rng"
    dates.write_text(DATES_RNG.replace("n'est pas au format", "est mal écrite, format"), encoding="utf-8")
    stamp = time.time() + 5
    os.utime(dates, (stamp, stamp))
    report = validate(_tree(DOC), [tei_rng])
    assert schematron.cache_info()["compilations"] == 2
    assert "est mal écrite" in report.issues[1].message


@needs_saxon
def test_a_rng_without_rules_is_not_compiled(tmp_path):
    plain = _write(tmp_path, "plain.rng", PLAIN_RNG)
    validate(_tree(DOC), [plain])
    validate(_tree(DOC), [plain])
    assert schematron.cache_info()["compilations"] == 0


# --- Sans Saxon ---------------------------------------------------------------

def test_without_saxon_the_rules_are_not_applied(tmp_path, tei_rng, monkeypatch):
    import xslt_engines
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    monkeypatch.setitem(sys.modules, "saxonche", None)
    report = validate(_tree(DOC), [tei_rng])
    assert report.error == "saxon_missing" and report.issues == () and report.errors == ()
    # Sans source, Saxon n'est même pas demandé.
    assert validate(_tree(DOC), []).error == ""
