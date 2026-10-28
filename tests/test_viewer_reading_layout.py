# -*- coding: utf-8 -*-
"""Mise en forme du texte de lecture dans le viewer web (V0.9.3.0), pilotée
dans Chromium (ignorée sans Playwright ni Chromium, comme sur GitHub).

Projet exemple enrichi : des préliminaires (<front>), un titre au sermon
RLS_184, puis, après son premier paragraphe, une strophe numérotée, une
liste à sous-liste, une liste numérotée, une note entre deux blocs et un
tableau (ligne d'en-tête, cellule fusionnée, choix, rature, ajout,
lacune). Ces blocs portent la ligne du pivot ouverte à leur place."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from corpus_data import copy_example
from web_viewer.generator import generate, make_html

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
KEYS = ("viewer.part.front", "viewer.part.back", "viewer.form.sic", "viewer.form.corr", "viewer.form.orig",
        "viewer.form.reg", "viewer.form.abbr", "viewer.form.expan", "viewer.form.gap", "viewer.form.detail")

STRUCTURES = ('<lg><l n="1">Uersus primus</l><l n="2">uersus secundus</l></lg>'
              '<list><head>Index</head><item>primum<list><item>sub primo</item></list>suite</item>'
              '<item>secundum</item></list><list rend="numbered"><item>unum</item></list>'
              '<note>Nota inter paragraphos</note>'
              '<table><head>Tabula</head><row role="label"><cell>Nomen</cell><cell>Folium</cell></row>'
              '<row><cell cols="2">Petrus <choice><sic>erat</sic><corr>erant</corr></choice> <del>deleta</del> '
              '<add>addita</add> <gap reason="illegible" extent="2 verba"/></cell></row></table>')


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


def _structured(root):
    project = copy_example(root)
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    for old, new in (("<text>", '<text xml:lang="la"><front><div><p>Praefatio operis</p></div></front>'),
                     ('<div xml:id="RLS_184">', '<div xml:id="RLS_184"><head>Sermo de apostolis</head>'),
                     ("</p>\n<p>In q", "</p>\n" + STRUCTURES + "<p>In q")):
        assert text.count(old) == 1, old
        text = text.replace(old, new)
    edition.write_text(text, encoding="utf-8")
    return project


@pytest.fixture(scope="module")
def viewer(browser, tmp_path_factory):
    output, _missing, data = generate(_structured(tmp_path_factory.mktemp("mise-en-forme") / "exemple"))
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("http://**", lambda route: route.abort())
    page.route("https://**", lambda route: route.abort())
    page.goto(output.as_uri())
    page.data = data
    yield page
    assert not errors, errors
    page.close()


def _texts(page, selector):
    return page.eval_on_selector_all(selector, "els=>els.map(e=>e.innerText.replace(/\\s+/g,' ').trim())")


def test_divisions_have_their_titles_and_the_table_of_contents_their_levels(viewer):
    assert _texts(viewer, "#document .div-title") == ["Préliminaires", "pr", "Sermo de apostolis"]
    divisions = [block for block in viewer.data["document"]["blocks"] if block["type"] == "div"]
    assert viewer.locator("#document .div-start").count() == len(divisions) > 3
    assert viewer.locator("#RLS_184").count() == 1 and viewer.locator("#RLS_185 .div-title").count() == 0
    entries = viewer.eval_on_selector_all("#toc .toc-list a", "els=>els.map(e=>[e.textContent,e.className,"
                                                               "!!document.getElementById(e.hash.slice(1))])")
    assert entries == [["Préliminaires", "toc-d0", True], ["pr", "toc-d0", True],
                       ["Sermo de apostolis", "toc-d1", True]]
    assert "RLS" not in viewer.inner_text("#toc")


def test_a_stanza_shows_each_line_with_its_number(viewer):
    assert _texts(viewer, ".tei-lg .tei-l .line-frag") == ["Uersus primus", "uersus secundus"]
    assert _texts(viewer, ".tei-lg .verse-n") == ["1", "2"]
    assert viewer.locator(".tei-lg").count() == 1


def test_nested_lists(viewer):
    assert _texts(viewer, "#document h3.tei-head") == ["Index"]
    assert _texts(viewer, "#document > ul.tei-list > li") == ["primum sub primo suite", "secundum"]
    assert _texts(viewer, "#document > ul.tei-list > li > ul.tei-list > li") == ["sub primo"]
    assert _texts(viewer, "#document > ol.tei-list > li") == ["unum"]


def test_a_table_has_its_caption_its_header_and_its_merged_cell(viewer):
    assert _texts(viewer, "table.tei-table caption") == ["Tabula"]
    assert _texts(viewer, "table.tei-table th") == ["Nomen", "Folium"]
    assert viewer.eval_on_selector_all("table.tei-table td", "els=>els.map(e=>e.colSpan)") == [2]
    assert viewer.locator("table.tei-table tr").count() == 2
    assert viewer.eval_on_selector(".tei-table-wrap", "e=>getComputedStyle(e).overflowX") == "auto"


def test_a_choice_shows_one_form_with_the_other_in_a_tooltip(viewer):
    cell = viewer.inner_text("table.tei-table td")
    assert "erant" in cell and "erat " not in cell and "[…]" in cell
    titles = viewer.eval_on_selector_all("table.tei-table td [title]", "els=>els.map(e=>[e.textContent,e.title])")
    assert ["erant", "Leçon transmise : erat"] in titles
    assert ["[…]", "Lacune : illegible · 2 verba"] in titles
    styles = viewer.eval_on_selector_all("table.tei-table td .tei-del, table.tei-table td .tei-add",
                                         "els=>els.map(e=>[e.textContent,getComputedStyle(e).textDecorationLine])")
    assert styles == [["deleta", "line-through"], ["addita", "underline"]]


def test_a_note_between_two_blocks_is_a_marker_hidden_with_the_notes(viewer):
    block = viewer.locator(".tei-note-block .ann-marker.n")
    assert block.count() == 1 and block.is_visible()
    assert "Nota inter" not in viewer.inner_text("#document")
    viewer.uncheck("#showNotes")
    assert not block.is_visible()
    viewer.check("#showNotes")


def test_a_click_on_a_verse_or_a_cell_selects_its_line(viewer):
    for selector in (".tei-l .line-frag", "table.tei-table td .line-frag"):
        fragment = viewer.locator(selector).first
        key = fragment.get_attribute("data-line")
        assert key
        viewer.evaluate("()=>document.querySelectorAll('.selected-line').forEach(e=>e.classList.remove('selected-line'))")
        fragment.click()
        assert "selected-line" in fragment.get_attribute("class")


def test_the_search_finds_a_title(viewer):
    viewer.fill("#search", "apostolis")
    viewer.press("#search", "Enter")
    viewer.wait_for_selector("#document .div-title mark.search-hit")
    assert _texts(viewer, "#document .div-title mark.search-hit") == ["apostolis"]
    viewer.fill("#search", "")
    viewer.press("#search", "Enter")


def test_the_reading_text_has_its_language_and_its_positions_are_in_order(viewer):
    assert viewer.get_attribute("#document", "lang") == "la"
    positions = viewer.eval_on_selector_all("#document [data-doc-pos]", "els=>els.map(e=>Number(e.dataset.docPos))")
    assert positions == list(range(len(positions)))
    assert positions and len(positions) == viewer.evaluate("()=>syncIndex.items.length")


def test_the_labels_exist_in_the_seven_catalogs():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        for key in KEYS:
            assert catalog.get(key), (language, key)
        assert "{label}" in catalog["viewer.form.detail"] and "{value}" in catalog["viewer.form.detail"]


def test_old_sermon_blocks_are_gone():
    html = make_html({"meta": {"title": "T", "has_images": False, "base_witness": "A"}, "witnesses": [],
                      "document": {"blocks": []},
                      "i18n": {"default": "fr", "fallback": "en", "catalogs": {"fr": {}}, "languages": []}})
    assert "sermon" not in html
