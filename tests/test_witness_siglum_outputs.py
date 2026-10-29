# -*- coding: utf-8 -*-
"""Le sigle d'un témoin dans les sorties (V0.9.2.8.2).

Dans la TEI, un témoin dont le sigle n'est pas un identifiant XML le porte
dans ``<idno type="siglum">`` (``<witness xml:id="_1760"><idno
type="siglum">1760</idno>…``). Les feuilles livrées (Édition critique,
apparat en notes, aperçu XSLT / CSS) et le viewer web montrent ce sigle à
la place de l'identifiant ; sans ``<idno>``, l'identifiant. Le JSON
d'alignement peut nommer le témoin par son sigle ou son identifiant."""
from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from lxml import etree

from corpus_data import copy_example

REPO = Path(__file__).resolve().parents[1]
TEI = "http://www.tei-c.org/ns/1.0"


def _siglum(project_xml, wid, siglum):
    text = project_xml.read_text(encoding="utf-8")
    old = f'<witness id="{wid}" '
    assert old in text
    project_xml.write_text(text.replace(old, f'{old}siglum="{siglum}" '), encoding="utf-8")


# --- Feuille « Édition critique » (Saxon) ------------------------------------------------------

saxon = pytest.importorskip("xslt_scenarios")


@pytest.fixture
def critique(tmp_path):
    if not saxon.saxon_available():
        pytest.skip("Saxon (saxonche) n'est pas installé")
    from test_edition_critique_saxon import TESTS
    import shutil
    from project_config import load_project
    root = tmp_path / "sermons"
    shutil.copytree(TESTS / "sermons", root)
    text = (TESTS / "edition_critique" / "edition.xml").read_text(encoding="utf-8")
    text = text.replace('<witness xml:id="B">', '<witness xml:id="_1760"><idno type="siglum">1760</idno>')
    text = text.replace('"#B"', '"#_1760"')
    assert "#B" not in text
    (root / "xml" / "kit_1760.xml").write_text(text, encoding="utf-8")
    return load_project(root / "project.xml")


def test_the_critical_edition_shows_the_idno_siglum(critique):
    from test_edition_critique_saxon import _edition, _entries, _text
    result, tree = _edition(critique, "kit_1760.xml")
    assert result.ok, result.error
    witnesses = [(_text(div.find("dt")), _text(div.find("dd"))) for div in tree.xpath("//section[@class='temoins']//div")]
    assert witnesses == [("A", "Témoin fictif A (premier de la liste)."), ("1760", "Témoin fictif B.")]
    assert ("1", "ipsum ] ipsam 1760") in _entries(tree) and ("2", "breve add. 1760") in _entries(tree)
    assert "_1760" not in tree.text_content()
    result, tree = _edition(critique, "kit_1760.xml", "_1760")
    assert result.ok, result.error
    assert _text(tree.find_class("chapeau")[0]).count("1760") == 1
    assert "_1760" not in tree.text_content()


def test_an_element_holding_only_the_siglum_is_not_repeated_in_the_label(critique):
    # <abbr type="siglum">, <label>… : le sigle n'est pas répété dans le
    # libellé, collé à lui (« AAvranches ») (V0.9.3.0). Le texte du libellé
    # qui commence par le sigle reste entier.
    from test_edition_critique_saxon import _edition, _text
    path = critique.root_dir / "xml" / "kit_1760.xml"
    text = path.read_text(encoding="utf-8")
    text = text.replace('<witness xml:id="A">', '<witness xml:id="A"><abbr type="siglum">A</abbr>')
    text = text.replace('<idno type="siglum">1760</idno>', '<idno type="siglum">1760</idno><label>1760</label>')
    path.write_text(text, encoding="utf-8")
    result, tree = _edition(critique, "kit_1760.xml")
    assert result.ok, result.error
    witnesses = [(_text(div.find("dt")), _text(div.find("dd"))) for div in tree.xpath("//section[@class='temoins']//div")]
    assert witnesses == [("A", "Témoin fictif A (premier de la liste)."), ("1760", "Témoin fictif B.")]


# --- Aperçu XSLT / CSS (tei-to-html.xsl, XSLT 1.0) ---------------------------------------------

def test_the_preview_shows_the_idno_siglum():
    source = etree.fromstring(
        f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt>'
        '<publicationStmt><p/></publicationStmt><sourceDesc><listWit>'
        '<witness xml:id="A">Témoin A</witness>'
        '<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>'
        '</listWit></sourceDesc></fileDesc></teiHeader><text><body><p>Lorem '
        '<app><lem wit="#A #_1760">ipsum</lem><rdg wit="#_1760">ipsam</rdg><rdg wit="#Z">ipsus</rdg></app>'
        '</p></body></text></TEI>'.encode("utf-8"))
    transform = etree.XSLT(etree.parse(str(REPO / "rendering" / "tei-to-html.xsl")))
    html = str(transform(source, baseWitness="'A'"))
    assert "(A 1760)" in html and "(1760)" in html and "(Z)" in html
    assert "_1760" not in html


# --- Viewer web ---------------------------------------------------------------------------------

def test_the_viewer_labels_leave_the_idno_out():
    from web_viewer.legacy_v11_core import extract_witness_labels
    root = ET.fromstring(
        f'<listWit xmlns="{TEI}"><witness xml:id="A">Témoin A</witness>'
        '<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>'
        '<witness xml:id="_1761"><idno type="siglum">1761</idno></witness>'
        '<witness xml:id="B"/></listWit>')
    assert extract_witness_labels(root) == {"A": "Témoin A", "_1760": "Troyes 1760", "_1761": "1761", "B": "B"}


def test_the_viewer_labels_leave_an_element_holding_only_the_siglum_out():
    from web_viewer.legacy_v11_core import extract_witness_labels
    root = ET.fromstring(
        f'<listWit xmlns="{TEI}"><witness xml:id="P"><abbr type="siglum">P</abbr>Paris, BnF</witness>'
        '<witness xml:id="T1"><label>T1</label>Troyes 816</witness>'
        '<witness xml:id="_1760"><idno type="siglum">1760</idno><abbr>1760</abbr>Troyes 1760</witness>'
        '<witness xml:id="A">A la marge</witness></listWit>')
    assert extract_witness_labels(root) == {"P": "Paris, BnF", "T1": "Troyes 816", "_1760": "Troyes 1760",
                                            "A": "A la marge"}


def test_the_viewer_data_carries_the_sigla(tmp_path):
    from project_config import load_project
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    _siglum(project_xml, "P", "P 15940")
    data = build_dataset(load_project(project_xml))[0]
    # Seulement quand il diffère de l'identifiant : l'export d'un projet sans
    # sigle à part ne change pas.
    assert {w["id"]: w.get("siglum") for w in data["witnesses"]} == {"T1": None, "T2": None, "P": "P 15940"}


# --- JSON d'alignement : sigle ou identifiant ---------------------------------------------------

def _issues(project_xml):
    from project_config import load_project
    from witness_resource_refresh import assemble_resources, diagnostic_rows
    project = load_project(project_xml)
    return {row.id: row.issue_codes for row in diagnostic_rows(project, assemble_resources(project))}


def _meta(project_xml, wid, **values):
    path = project_xml.parent / "alignments" / f"{wid}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["meta"].update(values)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_the_alignment_may_name_witnesses_by_their_siglum(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    _siglum(project_xml, "T1", "T 1")
    _siglum(project_xml, "P", "P 15940")
    _meta(project_xml, "P", witness="P 15940", base_witness="T 1")
    _meta(project_xml, "T2", witness="T2", base_witness="T1")
    issues = _issues(project_xml)
    assert "witness_mismatch" not in issues["P"] and "pivot_mismatch" not in issues["P"]
    assert "witness_mismatch" not in issues["T2"] and "pivot_mismatch" not in issues["T2"]
    _meta(project_xml, "P", witness="Q", base_witness="T2")
    issues = _issues(project_xml)
    assert "witness_mismatch" in issues["P"] and "pivot_mismatch" in issues["P"]


# --- Viewer web dans Chromium : messages ----------------------------------------------------------

def test_the_viewer_messages_name_witnesses_by_their_siglum(tmp_path):
    sync_api = pytest.importorskip("playwright.sync_api")
    import os
    from test_v0916_viewer_texts import Viewer
    project_xml = copy_example(tmp_path / "exemple")
    _siglum(project_xml, "P", "P 15940")
    with sync_api.sync_playwright() as playwright:
        try:
            browser = playwright.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM") or None,
                                                 args=["--no-sandbox"])
        except Exception as exc:          # Chromium absent
            pytest.skip(f"Chromium indisponible : {exc}")
        try:
            viewer = Viewer(browser, project_xml)
            viewer("()=>witnessEnd('P',1)")
            notice = viewer("()=>document.getElementById('syncNotice').textContent")
            assert notice == viewer.text("status.witness_end").replace("{witness}", "P 15940")
            assert not viewer.errors, viewer.errors
        finally:
            browser.close()


def test_the_viewer_cards_are_titled_by_siglum_and_label(tmp_path):
    """En-tête du panneau et titre de « Détails » : « sigle · nom affiché »,
    sauf si le nom affiché commence déjà par le sigle (projet exemple)."""
    from project_config import load_project
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    _siglum(project_xml, "P", "P 15940")
    text = project_xml.read_text(encoding="utf-8").replace('label="P · Paris, BnF, Latin 15940"',
                                                            'label="Paris, BnF, Latin 15940"')
    project_xml.write_text(text, encoding="utf-8")
    data = build_dataset(load_project(project_xml))[0]
    labels = {w["id"]: w["label"] for w in data["witnesses"]}
    assert labels == {"T1": "T1 · Troyes 816", "T2": "T2 · Troyes 1760", "P": "P 15940 · Paris, BnF, Latin 15940"}
