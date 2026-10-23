# -*- coding: utf-8 -*-
"""Viewer web d'une édition assemblée : textes et vues (V0.9.1.6), piloté
dans Chromium (ignoré sans Playwright ni Chromium, comme sur GitHub).

Quand la ligne choisie passe dans un texte synchronisé à part, chaque panneau
montre la vue de son témoin dans ce texte : ses lignes, ses pages (depuis sa
page de départ, selon les <pb> de ce texte seulement), ou « Pas d'alignement
de ce témoin pour ce texte. ». Le zoom et les cadres restent. Les boutons
← → de l'en-tête parcourent toutes les lignes dans l'ordre de lecture.

Projet exemple dont RLS_185 est synchronisé à part (après la 116e ligne de
l'édition ; T1 et T2 y ont un JSON, P non) ; X (12r…13v) a ses <pb> de 12v
et 13r dans le texte, Y (1r, 1v) son <locus from="1v">. Jeu « corpus » :
s02 au pivot B (D y est relié ; A et C n'y sont pas)."""
from __future__ import annotations

import os

import pytest

from corpus_data import add_text_pages, copy_example, make_corpus, move_to_part, split_alignments
from web_viewer.generator import generate


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


class Viewer:
    def __init__(self, browser, project):
        self.output, _missing, self.data = generate(project)
        self.page = browser.new_page()
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.route("http://**", lambda route: route.abort())
        self.page.route("https://**", lambda route: route.abort())
        self.page.goto(self.output.as_uri())

    def __call__(self, expression, arg=None):
        return self.page.evaluate(expression, arg)

    def select(self, key):
        assert self("k=>selectLine(k,false)", key) is True
        return self

    def text(self, key):
        return self.data["i18n"]["catalogs"]["fr"][key]

    def card(self, wid):
        return self.page.locator(f'[data-w="{wid}"]')

    def center_key(self, wid):
        return self("id=>{const w=witnessMap.get(id),s=states.get(id);return s.center==null?null:itemKey(w,s.physical[s.center])}",
                    wid)

    def folio(self, wid):
        return self("id=>states.get(id).folioRef", wid)


@pytest.fixture
def example(browser, tmp_path):
    project = copy_example(tmp_path / "exemple")
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    viewer = Viewer(browser, project)
    yield viewer
    assert not viewer.errors, viewer.errors
    viewer.page.close()


def _keys(viewer, prefix):
    return [key for key in viewer.data["meta"]["line_order"] if key.startswith(prefix)]


def test_a_line_of_a_text_apart_shows_the_views_of_the_text(example):
    text = _keys(example, "~1~")
    example.select(text[10])
    assert example("()=>activeSeg") == 1
    assert example.center_key("T1") == text[10]
    assert example.center_key("T2").startswith("~1~")
    assert example.text("manuscript.text_absent") in example.card("P").inner_text()
    edition = _keys(example, "f")
    example.select(edition[200])
    assert example("()=>activeSeg") == 0
    assert example.center_key("T1") == edition[200]
    assert example.text("manuscript.text_absent") not in example.card("P").inner_text()
    assert example.center_key("P") is not None and not example.center_key("T2").startswith("~")


def test_the_page_witnesses_of_a_text_follow_its_pb_from_their_start_page(example):
    text = _keys(example, "~1~")
    example.select(text[2])
    assert example.folio("X") == "X-p0001"       # avant le <pb> de 12v : 12r
    assert example.folio("Y") == "Y-p0002"       # son locus : 1v
    example.select(text[3])
    assert example.folio("X") == "X-p0002"
    example.select(text[25])
    assert example.folio("X") == "X-p0003"
    example.select(text[2])
    assert example.folio("X") == "X-p0001"


def test_the_zoom_and_the_frames_are_kept_from_a_text_to_another(example):
    example.card("T2").locator("[data-act=plus]").click()
    example.card("T2").locator("[data-act=frames]").click()
    example.select(_keys(example, "~1~")[5])
    assert example("()=>[states.get('T2').zoom,states.get('T2').frames]") == [1.25, True]
    assert example.card("T2").locator("[data-role=zoom]").inner_text() == "125 %"


def test_the_header_arrows_go_through_every_line_in_reading_order(example):
    order = example.data["meta"]["line_order"]
    example.select(order[115])
    example.page.locator("#nextBase").click()
    assert example("()=>selectedKey") == order[116] and example("()=>activeSeg") == 1
    example.select(order[116 + 164])
    example.page.locator("#nextBase").click()
    assert example("()=>selectedKey") == order[116 + 165] and example("()=>activeSeg") == 0
    example.page.locator("#prevBase").click()
    assert example("()=>selectedKey") == order[116 + 164]


def test_clicking_the_text_of_a_text_apart_activates_it(example):
    key = _keys(example, "~1~")[40]
    example.page.locator(f'.line-frag[data-line="{key}"]').first.click()
    assert example("()=>activeSeg") == 1 and example.center_key("T1") == key


def test_the_pivot_of_a_text_leads_its_panel(browser, tmp_path):
    viewer = Viewer(browser, make_corpus(tmp_path / "corpus"))
    try:
        viewer.select("~1~B-30r::3")
        assert viewer.center_key("B") == "~1~B-30r::3"
        assert viewer.center_key("D").startswith("~1~D-101r::")
        for wid in ("A", "C"):
            assert viewer.text("manuscript.text_absent") in viewer.card(wid).inner_text()
        viewer.select("~2~A-13r::2")
        assert viewer.center_key("A") == "~2~A-13r::2"
        assert viewer.text("manuscript.text_absent") in viewer.card("B").inner_text()
        viewer.select("A-12r::4")
        assert viewer.center_key("A") == "A-12r::4" and viewer.center_key("C").startswith("C-2r::")
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_a_single_file_edition_is_shown_as_before(browser, tmp_path):
    viewer = Viewer(browser, copy_example(tmp_path / "exemple"))
    try:
        order = [key for key in viewer("()=>lineOrder")]
        assert len(order) == viewer.data["meta"]["lines"]
        viewer.select(order[30])
        assert viewer.center_key("T1") == order[30] and viewer("()=>activeSeg") == 0
        viewer.page.locator("#nextBase").click()
        assert viewer("()=>selectedKey") == order[31]
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_a_pb_without_facs_leads_its_page_witness(browser, tmp_path):
    """<pb edRef="#X" n="1v"/> : le folio est trouvé par son nom, comme sur le
    bureau (pb_folio), même si l'image et le folio portent le même nom."""
    from corpus_data import PIVOT_GAP, add_example_lacunae
    project = copy_example(tmp_path / "exemple")
    add_example_lacunae(project)       # X (1r, 1v) : <pb> de 1r au début, de 1v avant la 41e ligne
    viewer = Viewer(browser, project)
    try:
        order = viewer("()=>lineOrder")
        viewer.select(order[10])
        assert viewer.folio("X") == "X-p0001"
        viewer.select(order[PIVOT_GAP + 1])
        assert viewer.folio("X") == "X-p0002"
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()
