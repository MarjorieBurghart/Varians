# -*- coding: utf-8 -*-
"""Sigle et identifiant d'un témoin (V0.9.2.8.2).

Le sigle saisi peut ne pas être un identifiant XML valide (« 1760 »,
« T 2 »). Varians en tire alors un identifiant valide, employé comme
``xml:id`` du témoin et dans ``@wit`` / ``@edRef`` ; le sigle saisi est
gardé dans project.xml (``siglum``) et dans la TEI créée avec le projet
(``<idno type="siglum">``), seulement quand il diffère de l'identifiant."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from project_config import load_project
from project_management import ProjectDraft, WitnessDraft, minimal_tei_text, write_project_xml
from witness_ids import is_xml_id, witness_id_for_siglum

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


@pytest.mark.parametrize("siglum, expected", [
    ("T1", "T1"), ("P", "P"), ("Σ", "Σ"), ("σ1", "σ1"), ("a.b-c_d", "a.b-c_d"), ("é", "é"),
    ("1760", "_1760"), ("T 2", "T_2"), ("A/2", "A_2"), ("a:b", "a_b"), ("#A", "_A"),
    ("-x", "_-x"), (".a", "_.a"), ("Troyes 816", "Troyes_816"), ("  T2 ", "T2"),
    ("T2*", "T2_"), ("(A)", "_A_"),
])
def test_the_identifier_drawn_from_a_siglum(siglum, expected):
    assert witness_id_for_siglum(siglum) == expected
    assert is_xml_id(expected)


def test_an_empty_siglum_gives_no_identifier():
    assert witness_id_for_siglum("   ") == ""
    assert not is_xml_id("")


@pytest.mark.parametrize("value", ["1760", "T 2", "a:b", "-x", "#A", "A/2"])
def test_invalid_identifiers(value):
    assert not is_xml_id(value)


def _draft(root, witnesses):
    return ProjectDraft(
        "Essai", root / "xml" / "edition.xml", "fr", "en", root / "i18n",
        root / "rendering" / "tei-to-html.xsl", root / "rendering" / "tei.css",
        root / "rendering" / "custom-elements.xml", root / "web_output", "viewer.html",
        witnesses, "T1", xslt_mode="builtin", schema_mode="none")


WITNESSES = [
    WitnessDraft("T1", "T1 · Troyes 816"),
    WitnessDraft("_1760", "Troyes 1760", siglum="1760"),
    WitnessDraft("P", "", siglum="P"),
]


def test_project_xml_keeps_the_siglum_only_when_it_differs(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, WITNESSES))
    elements = {el.get("id"): el for el in ET.parse(path).getroot().iter("witness")}
    assert elements["_1760"].get("siglum") == "1760"
    assert elements["T1"].get("siglum") is None and elements["P"].get("siglum") is None
    assert elements["P"].get("label") == "P"


def test_the_siglum_is_read_back_and_shown(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, WITNESSES))
    witnesses = {w.id: w for w in load_project(path).witnesses}
    assert witnesses["_1760"].siglum == "1760"
    assert witnesses["_1760"].display_siglum == "1760"
    assert witnesses["T1"].siglum == "" and witnesses["T1"].display_siglum == "T1"
    assert witnesses["T1"].is_base


def test_the_label_defaults_to_the_siglum(tmp_path):
    (tmp_path / "project.xml").write_text(
        '<teiManuscriptProject version="1"><edition file="xml/edition.xml"/>'
        '<witnesses base="T1"><witness id="T1"/><witness id="_1760" siglum="1760"/></witnesses>'
        '</teiManuscriptProject>', encoding="utf-8")
    witnesses = {w.id: w for w in load_project(tmp_path / "project.xml").witnesses}
    assert witnesses["_1760"].label == "1760"
    assert witnesses["T1"].label == "T1"


def test_the_new_edition_declares_the_siglum_in_an_idno():
    text = minimal_tei_text("Essai", WITNESSES, "T1", schema_mode="none")
    root = ET.fromstring(text.split("?>", 1)[1])
    witnesses = {el.get(XML_ID): el for el in root.iter(f"{TEI}witness")}
    assert list(witnesses) == ["T1", "_1760", "P"]
    idno = witnesses["_1760"].find(f"{TEI}idno")
    assert idno is not None and idno.get("type") == "siglum" and idno.text == "1760"
    assert "".join(witnesses["_1760"].itertext()) == "1760Troyes 1760"
    assert witnesses["_1760"].find(f"{TEI}idno").tail == "Troyes 1760"
    assert witnesses["T1"].find(f"{TEI}idno") is None and witnesses["T1"].text == "T1 · Troyes 816"
    assert witnesses["P"].find(f"{TEI}idno") is None and witnesses["P"].text == "P"
