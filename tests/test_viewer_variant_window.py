# -*- coding: utf-8 -*-
"""Red team 2 (cohérence) : la fenêtre d'une variante du viewer web dit les
leçons comme l'apparat de l'Édition critique (décision de l'utilisatrice).

- C2 : un apparat imbriqué dans une leçon donne sa leçon affichée (il était
  lu en entier : « magna res rex ») ; un <lb/> suit la règle TEI, un <pb/>
  ne met pas d'espace (« s<pb/>et » : « set »).
- C3 : les notes d'une leçon sont dites entre parenthèses (celles de la
  leçon affichée ont leur propre repère dans le texte).
- C4 : « om. », « lacuna incipit », « lacuna desinit », « [lacune] »,
  [supplied], « sic » ; une leçon vide n'est plus « ∅ ».
- C5 : sigles (<idno type="siglum">) au lieu des identifiants ; le @wit
  d'un <rdgGrp> vaut pour ses leçons ; une leçon sans témoin est « éd. »."""
from __future__ import annotations

import os
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from web_viewer.legacy_v11_core import extract_reading_document

ROOT = Path(__file__).resolve().parents[1]
TEI_NS = "http://www.tei-c.org/ns/1.0"
FRENCH = {s.get("key"): s.text for s in ET.parse(ROOT / "i18n" / "fr.xml").getroot()}
SIGLA = ('<witness xml:id="A"><idno type="siglum">A1</idno>Codex A</witness>'
         '<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760</witness>'
         '<witness xml:id="C"><abbr>C</abbr>Codex C</witness>')


def _document(body, listwit="", **choice):
    header = f"<sourceDesc><listWit>{listwit}</listWit></sourceDesc>" if listwit else ""
    root = ET.fromstring(f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
                         f'{header}</fileDesc></teiHeader><text><body>{body}</body></text></TEI>')
    return extract_reading_document(None, "#A", root=root, **choice)


def _render(parts):
    """Ce que la fenêtre écrit (sans la mise en forme)."""
    out = []
    for part in parts:
        if "note" in part:
            out.append(f" ({_render(part['note'])})")
        elif "editor" in part:
            out.append(" ".join([part["editor"], *part.get("wit", [])]))
        elif "label" in part:
            out.append(FRENCH[part["label"]].replace("{extent}", part.get("extent", "")))
        elif "apparatus" in part:
            out.append(" [" + " ; ".join(f"{' '.join(r['wit']) or FRENCH['publication.editor_siglum']} : "
                                         f"{_render(r['parts'])}" for r in part["apparatus"]) + "]")
        else:
            out.append(part["text"])
    return "".join(out)


def _windows(body, listwit="", **choice):
    """Pour chaque variante, dans l'ordre : les lignes « sigles : leçon »."""
    document = _document(body, listwit, **choice)
    sigla = document.get("sigla", {})
    windows = []
    for ann in document["annotations"].values():
        if ann["kind"] != "variant":
            continue
        windows.append([f"{' '.join(sigla.get(w, w) for w in r['wit']) or FRENCH['publication.editor_siglum']}"
                        f" : {_render(r['parts'])}" for r in ann["readings"]])
    return windows


def _parts(body, **choice):
    return [r["parts"] for ann in _document(body, **choice)["annotations"].values() if ann["kind"] == "variant"
            for r in ann["readings"]]


def test_sigla_are_those_of_the_list_of_witnesses_and_a_reading_group_gives_its_witnesses():
    windows = _windows('<p>Lorem <app><lem wit="#A">ipsum</lem><rdg wit="#_1760">ipsam</rdg>'
                       '<rdgGrp wit="#C #D"><rdg>ipsus</rdg></rdgGrp><rdg>ipsis</rdg></app> dolor.</p>', SIGLA)
    assert windows == [["A1 : ipsum", "1760 : ipsam", "C D : ipsus", "éd. : ipsis"]]


def test_omissions_and_notes_are_said_as_in_the_apparatus():
    document = _document('<p>Lorem <app><lem wit="#A">ipsum<note>Nota lemmatis.</note></lem>'
                         '<rdg wit="#B">ipsam<note>Nota lectionis.</note></rdg>'
                         '<rdg wit="#C"><note>Omittit C.</note></rdg><rdg wit="#D"/></app> dolor.</p>')
    notes = [a["text"] for a in document["annotations"].values() if a["kind"] == "note"]
    assert notes == ["Nota lemmatis."]                  # la note de la leçon affichée a son repère
    assert _windows('<p>Lorem <app><lem wit="#A">ipsum<note>Nota lemmatis.</note></lem>'
                    '<rdg wit="#B">ipsam<note>Nota lectionis.</note></rdg>'
                    '<rdg wit="#C"><note>Omittit C.</note></rdg><rdg wit="#D"/></app> dolor.</p>') == [
        ["A : ipsum", "B : ipsam (Nota lectionis.)", "C : om. (Omittit C.)", "D : om."]]


def test_lacunae_are_said_with_the_words_of_the_apparatus():
    assert _windows('<p>Lorem <app><lem wit="#A #B"/><rdg wit="#C"><lacunaStart/></rdg></app>ipsum dolor '
                    '<app><lem wit="#A #B"/><rdg wit="#C"><lacunaEnd/></rdg></app>sit amet.</p>') == [
        ["A B : om.", "C : lacuna incipit"], ["A B : om.", "C : lacuna desinit"]]
    assert _windows('<p>Lorem <app><lem wit="#A">ipsum</lem><rdg wit="#B #C">ipsam <lacunaStart wit="#C"/></rdg>'
                    '</app> dolor.</p>') == [["A : ipsum", "B C : ipsam lacuna incipit C"]]
    parts = _parts('<p><app><lem wit="#A">x</lem><rdg wit="#C"><lacunaStart/></rdg><rdg wit="#D"/></app></p>')
    assert parts[1] == [{"editor": "lacuna incipit"}] and parts[2] == [{"editor": "om."}]


def test_gaps_and_transcription_phenomena_as_in_the_apparatus():
    body = ('<p>Lorem <app><lem wit="#A">est</lem><rdg wit="#B"><gap reason="illegible"/></rdg>'
            '<rdg wit="#C"><unclear>ips</unclear><gap extent="2 letters"/></rdg>'
            '<rdg wit="#D"><del>non</del> est</rdg><rdg wit="#E"><supplied>es</supplied>t <add>enim</add></rdg>'
            '<rdg wit="#F"><sic>quot</sic></rdg>'
            '<rdg wit="#G"><choice><abbr>qd</abbr><expan>quod</expan></choice> <hi rend="sup">2</hi></rdg>'
            '<rdg wit="#H"><hi rend="italic">uerbum</hi> <emph>illud</emph> <hi rend="bold">hoc</hi></rdg></app> dolor.</p>')
    assert _windows(body) == [["A : est", "B : [lacune]", "C : ips[lacune : 2 letters]", "D : non est",
                               "E : [es]t enim", "F : quot sic", "G : quod 2", "H : uerbum illud hoc"]]
    parts = _parts(body)
    assert parts[3][0] == {"text": "non", "styles": ["del"]}
    assert parts[5] == [{"text": "quot "}, {"editor": "sic"}]
    assert {"text": "2", "styles": ["sup"]} in parts[6]
    # En romain, comme dans l'apparat ; le gras reste.
    assert parts[7] == [{"text": "uerbum illud "}, {"text": "hoc", "styles": ["bold"]}]


def test_a_nested_apparatus_gives_its_reading_shown():
    body = ('<p>Lorem <app><lem wit="#A #B">magna <app><lem wit="#A">res</lem><rdg wit="#B">rex</rdg></app></lem>'
            '<rdg wit="#C">parua res</rdg></app> dolor.</p>')
    assert _windows(body)[0] == ["A B : magna res", "C : parua res"]
    assert _windows(body, text_mode="witness", text_witness="B")[0] == ["A B : magna rex", "C : parua res"]


def test_line_and_page_breaks_in_a_reading_follow_the_tei_rule():
    assert _windows('<p>Lorem <app><lem wit="#B">ipsum dolor</lem>'
                    '<rdg wit="#A">ip<lb edRef="#A" break="no"/>sum <lb edRef="#A"/>dolor</rdg>'
                    '<rdg wit="#C">ip\n<lb edRef="#C" break="no"/>\nsum<lb edRef="#C"/>dolor</rdg>'
                    '<rdg wit="#D">ip<lb edRef="#A" break="no"/><lb edRef="#D"/>sum dolor</rdg></app> sit.</p>') == [
        ["B : ipsum dolor", "A : ipsum dolor", "C : ipsum dolor", "D : ipsum dolor"]]
    assert _windows('<p>dolor <app><lem wit="#A">sit</lem><rdg wit="#B">s<pb edRef="#B" n="13r"/>et</rdg></app>'
                    ' amet.</p>') == [["A : sit", "B : set"]]


def test_a_non_breaking_space_and_a_biblical_reference_in_a_reading():
    assert _windows('<p><app><lem wit="#A">M. Petrus</lem><rdg wit="#B"><cit type="bible"><quote>In principio'
                    '</quote><ref>Gn 1, 1</ref></cit></rdg></app></p>') == [
        ["A : M. Petrus", "B : In principio <Gn 1, 1>"]]


def test_the_plain_text_of_a_reading_is_kept():
    document = _document('<p><app><lem wit="#A">ip<lb break="no"/>sum <note>N.</note></lem>'
                         '<rdg wit="#B"><sic>quot</sic></rdg><rdg wit="#C"/></app></p>')
    ann = next(a for a in document["annotations"].values() if a["kind"] == "variant")
    assert [r["text"] for r in ann["readings"]] == ["ipsum", "quot", ""]


def test_an_apparatus_in_a_note_gives_its_reading_then_its_entry_in_brackets():
    """C2 : un apparat dans une note était lu en entier (« Vide alibiibi
    infra. ») ; comme dans le DOCX, sa leçon puis son entrée entre
    crochets. Un <lb break="no"/> soude, l'italique d'une note reste."""
    document = _document('<p>Lorem<note><hi rend="italic">Vide</hi> <app><lem wit="#A">alibi</lem>'
                         '<rdg wit="#B">ibi</rdg></app> in<lb break="no"/>fra.</note> ipsum.</p>')
    note = next(a for a in document["annotations"].values() if a["kind"] == "note")
    assert note["text"] == "Vide alibi infra."
    assert note["parts"][0] == {"text": "Vide", "styles": ["italic"]}
    entry = next(part["apparatus"] for part in note["parts"] if "apparatus" in part)
    assert [(r["wit"], _render(r["parts"])) for r in entry] == [(["A"], "alibi"), (["B"], "ibi")]
    assert _render(note["parts"]) == "Vide alibi [A : alibi ; B : ibi] infra."
    assert not [a for a in document["annotations"].values() if a["kind"] == "variant"]


# --- Dans le viewer -----------------------------------------------------------------------------

@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as playwright:
        try:
            launched = playwright.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM") or None,
                                                  args=["--no-sandbox"])
        except Exception as exc:          # Chromium absent
            pytest.skip(f"Chromium indisponible : {exc}")
        yield launched
        launched.close()


def _project(tmp_path, body):
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
        '<witness id="C" label="C"><images type="none"/></witness></witnesses></teiManuscriptProject>',
        encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(
        f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>E</title></titleStmt><publicationStmt><p/>'
        f'</publicationStmt><sourceDesc><listWit>{SIGLA}</listWit></sourceDesc></fileDesc></teiHeader>'
        f'<text><body>{body}</body></text></TEI>', encoding="utf-8")
    return root / "project.xml"


def test_the_variant_window_in_the_viewer(browser, tmp_path):
    from test_v0916_viewer_texts import Viewer
    project = _project(tmp_path, '<p>Lorem <app><lem wit="#A">ipsum</lem><rdg wit="#_1760"><gap/></rdg>'
                                  '<rdg wit="#C"><note>Omittit C.</note></rdg><rdg>ipsus</rdg></app> dolor'
                                  '<note>Vide <app><lem wit="#A">alibi</lem><rdg wit="#C">ibi</rdg></app> infra.</note>.</p>')
    viewer = Viewer(browser, project)
    try:
        show = """()=>{const m=document.querySelector('#document .ann-marker.v');showAnnotation(m.dataset.ann,{clientX:10,clientY:10});
            const p=document.getElementById('popover');
            return {lines:[...p.querySelectorAll('.reading')].map(x=>x.textContent),
                    editor:[...p.querySelectorAll('.reading .editor-word')].map(x=>[x.textContent,getComputedStyle(x).fontStyle])}}"""
        shown = viewer(show)
        assert shown["lines"] == ["A1 : ipsum", "1760 : [lacune]", "C : om. (Omittit C.)", "éd. : ipsus"]
        assert shown["editor"] == [["om.", "italic"]]
        viewer("()=>setLanguage('en')")
        english = viewer(show)["lines"]
        catalog = viewer.data["i18n"]["catalogs"]["en"]
        assert english[1] == f"1760 : {catalog['publication.gap']}"
        assert english[3] == f"{catalog['publication.editor_siglum']} : ipsus"
        note = viewer("""()=>{const m=document.querySelector('#document .ann-marker.n');showAnnotation(m.dataset.ann,{clientX:10,clientY:10});
            return document.querySelector('#popover div').textContent}""")
        assert note == "Vide alibi [A1 : alibi ; C : ibi] infra."
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()
