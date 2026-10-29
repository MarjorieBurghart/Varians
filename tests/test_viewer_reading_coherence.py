# -*- coding: utf-8 -*-
"""Red team 2 (cohérence) : le texte de lecture du viewer web suit les règles
de l'Édition critique (référence choisie par l'utilisatrice).

- C1, D9 : un <lb/> d'un autre témoin que le pivot suit la règle TEI, comme
  partout ailleurs : sans break="no", il marque une fin de mot ; avec
  break="no", le mot est soudé (le viewer laissait « ip sum », ou collait
  « XXII »). Des <lb/> contigus soudent le mot si l'un porte break="no".
- C6 : une espace insécable (U+00A0) reste insécable.
- C14 : <emph> en italique, <quote> en romain, et une espace avant la
  référence d'une citation biblique, comme dans l'Édition critique.
- D2 : la recherche trouve un mot coupé par un <lb break="no"/> du pivot.
- D4, D10 : « Lacune du pivot » nomme son sigle ; un libellé de page est
  montré tel quel, comme sur le bureau.
- En-tête : le nombre de variantes est celui de l'apparat, même sans
  alignement par lignes."""
from __future__ import annotations

import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from web_viewer.generator import HTML_TEMPLATE
from web_viewer.legacy_v11_core import extract_reading_document

ROOT = Path(__file__).resolve().parents[1]
TEI_NS = "http://www.tei-c.org/ns/1.0"
SEARCH = ROOT / "web_viewer" / "fulltext_search.js"


def _reading(body):
    root = ET.fromstring(f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
                         f'</fileDesc></teiHeader><text><body>{body}</body></text></TEI>')
    return extract_reading_document(None, "#A", root=root)


def _text(reading):
    """Texte visible, sans les marques de coupure du pivot (U+2060)."""
    return "".join(seg.get("text", "") for block in reading["blocks"] for seg in block["segments"]
                   if seg["kind"] in ("text", "editorial-ref")).replace("⁠", "")


@pytest.mark.parametrize("body, expected", [
    ('<p>Lorem ip\n<lb edRef="#B" break="no"/>\nsum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip<lb edRef="#B"/>sum dolor.</p>', "Lorem ip sum dolor."),
    ('<p>Lorem ip<lb edRef="#B" break="no"/><lb edRef="#A"/>sum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip<lb edRef="#A"/><lb edRef="#B" break="no"/>sum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip\n<lb edRef="#B"/>\nsum dolor.</p>', "Lorem ip sum dolor."),
    ('<p>Lorem ip\n<lb edRef="#A" break="no"/>\nsum dolor.</p>', "Lorem ipsum dolor."),
])
def test_an_lb_of_any_witness_follows_the_tei_rule(body, expected):
    assert _text(_reading(body)) == expected


def test_a_non_breaking_space_stays_non_breaking():
    reading = _reading('<p>M. Petrus finis ! <note>Nota bene.</note></p>')
    assert "M. Petrus finis !" in _text(reading)
    notes = [a["text"] for a in reading["annotations"].values() if a["kind"] == "note"]
    assert notes == ["Nota bene."]


def test_emph_is_italic_and_quote_roman_as_in_the_critical_edition():
    reading = _reading('<p>Vide <emph>hoc</emph> et <quote>illud</quote>.</p>')
    styles = {seg["text"]: seg.get("styles") for block in reading["blocks"] for seg in block["segments"]
              if seg["kind"] == "text"}
    assert styles["hoc"] == ["italic"] and styles["illud"] == ["quote"]
    style_classes = HTML_TEMPLATE.split("const STYLE_CLASSES=", 1)[1].split(";", 1)[0]
    assert "quote:'tei-quote'" in style_classes and "quote:'tei-italic'" not in style_classes


def test_a_biblical_reference_is_spaced_from_its_quotation():
    reading = _reading('<p>Dixit: <cit type="bible"><quote>In principio</quote><ref>Gn 1, 1</ref></cit> et.</p>')
    segments = [seg for block in reading["blocks"] for seg in block["segments"]]
    ref = next(i for i, seg in enumerate(segments) if seg["kind"] == "editorial-ref")
    assert segments[ref - 1]["text"].endswith(" ") and segments[ref]["text"] == "Gn 1, 1"


def test_the_search_finds_a_word_broken_by_a_pivot_line(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    blocks = [{"type": "p", "segments": [{"kind": "text", "text": "hereditatem et heredi"},
                                         {"kind": "text", "text": "⁠tatem"}]}]
    data = tmp_path / "blocks.json"
    data.write_text(json.dumps(blocks), encoding="utf-8")
    js = (f"const F=require({json.dumps(str(SEARCH))});"
          f"const B=JSON.parse(require('fs').readFileSync({json.dumps(str(data))},'utf8'));"
          "const hits=F.find(F.makeIndex(B),'hereditatem');"
          "process.stdout.write(JSON.stringify(hits.map(h=>h.pieces)));")
    run = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    pieces = json.loads(run.stdout)
    assert len(pieces) == 2
    assert pieces[1] == [{"docPos": 0, "start": 15, "end": 21}, {"docPos": 1, "start": 0, "end": 6}]


def test_the_pivot_lacuna_notice_names_its_siglum_and_page_labels_are_shown_as_they_are():
    assert "t('status.base_lacuna',{base:siglumOf(activePivot())})" in HTML_TEMPLATE
    assert "t('status.base_lacuna',{base:activePivot()})" not in HTML_TEMPLATE
    label = HTML_TEMPLATE.split("function pageLabel(x){", 1)[1].split("}", 1)[0]
    assert "replaceAll" not in label


def test_the_header_counts_the_variants_of_the_apparatus_without_line_alignment(tmp_path):
    from project_config import load_project
    from web_viewer.generator import build_dataset
    root = tmp_path / "projet"
    (root / "xml").mkdir(parents=True)
    (root / "web_output").mkdir()
    shutil.copytree(ROOT / "rendering", root / "rendering")
    (root / "project.xml").write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n<teiManuscriptProject version=\"1\"><title>Essai</title>"
        '<edition file="xml/edition.xml"/><interface language="fr"/>'
        '<rendering xsltMode="builtin" css="rendering/tei.css" customElements="rendering/custom-elements.xml"/>'
        '<webViewer outputDir="web_output" filename="viewer.html"/><witnesses base="A">'
        '<witness id="A" label="A" role="base"><images type="none"/></witness>'
        '<witness id="B" label="B"><images type="none"/></witness></witnesses></teiManuscriptProject>',
        encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>E</title></titleStmt><publicationStmt><p/>'
        '</publicationStmt><sourceDesc><listWit><witness xml:id="A">A</witness><witness xml:id="B">B</witness>'
        '</listWit></sourceDesc></fileDesc></teiHeader><text><body><p>Lorem <app><lem wit="#A">ipsum</lem>'
        '<rdg wit="#B">ipsam</rdg></app> dolor <app><lem wit="#A">sit</lem><rdg wit="#B">sat</rdg></app>.</p>'
        '</body></text></TEI>', encoding="utf-8")
    data, _missing = build_dataset(load_project(root / "project.xml"))
    assert data["meta"]["variants"] == 2


def test_the_pivot_is_named_with_its_own_phrases():
    """« sans leçon de le témoin pivot » : le pivot a ses propres tournures,
    dans chaque langue (red team 2, C15)."""
    import xml.etree.ElementTree as XET
    choice = HTML_TEMPLATE.split("function textChoice(){", 1)[1].split("return s}", 1)[0]
    assert "t('viewer.text.missing_pivot'" in choice and "t('viewer.text.witness_pivot')" in choice
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        keys = {s.get("key"): s.text for s in XET.parse(ROOT / "i18n" / f"{language}.xml").getroot()}
        assert "{count}" in keys["viewer.text.missing_pivot"] and keys["viewer.text.witness_pivot"]
    french = {s.get("key"): s.text for s in XET.parse(ROOT / "i18n" / "fr.xml").getroot()}
    assert french["viewer.text.missing_pivot"].startswith("{count} passage(s) sans leçon du témoin pivot")
