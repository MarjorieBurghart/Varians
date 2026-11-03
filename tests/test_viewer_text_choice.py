# -*- coding: utf-8 -*-
"""Choix du texte du viewer web (V0.9.3.0), dans Chromium (ignoré sans
Playwright ni Chromium, comme sur GitHub).

L'en-tête dit quel texte est affiché et combien de passages n'ont pas de
leçon du témoin choisi ; ces passages sont encadrés, avec une infobulle, et
la fenêtre de leur variante le dit. Une ligne du pivot que le témoin
affiché omet garde sa place : un clic sur elle y mène."""
from __future__ import annotations

import os

import pytest

from corpus_data import copy_example
from i18n import format_message
from project_management import update_project_web_text
from test_v0916_viewer_texts import Viewer


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


def _viewer(browser, tmp_path, mode, witness):
    project = copy_example(tmp_path / f"exemple-{mode}-{witness}")
    update_project_web_text(project, mode, witness)
    return Viewer(browser, project)


def test_the_header_names_the_text_and_the_passages_without_reading_are_marked(browser, tmp_path):
    viewer = _viewer(browser, tmp_path, "witness", "P")
    try:
        stats = viewer("()=>document.getElementById('stats').textContent")
        missing = viewer.data["meta"]["text"]["missing"]
        assert missing > 0
        assert viewer.text("viewer.text.witness").replace("{witness}", "P") in stats
        assert format_message(viewer.text("viewer.text.missing"), "fr", count=missing, witness="P") in stats
        marked = viewer("()=>[...document.querySelectorAll('#document .no-reading')].map(x=>x.title)")
        assert marked and all("P" in title for title in marked)
        expected = viewer.text("viewer.missing").split("{")[0]
        assert all(title.startswith(expected) for title in marked)
        # Encadré : le cadre reste quand les repères de variantes sont masqués.
        assert viewer("()=>getComputedStyle(document.querySelector('#document .no-reading')).outlineStyle") == "dashed"
        # La fenêtre de la variante le dit.
        note = viewer("""()=>{const m=[...document.querySelectorAll('#document .ann-marker.v')]
            .find(b=>DATA.document.annotations[b.dataset.ann].missing);showAnnotation(m.dataset.ann,{clientX:10,clientY:10});
            return document.querySelector('#popover .no-reading-note')?.textContent||''}""")
        assert note.startswith(expected)
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_a_line_of_the_pivot_omitted_by_the_witness_shown_keeps_its_place(browser, tmp_path):
    viewer = _viewer(browser, tmp_path, "witness", "T2")
    try:
        anchors = viewer("()=>[...document.querySelectorAll('#document .line-anchor')].map(x=>x.dataset.line)")
        assert len(anchors) == 5
        viewer.select(anchors[0])
        assert viewer("k=>[...document.querySelectorAll('.selected-line')].some(x=>x.dataset.line===k)", anchors[0])
        stats = viewer("()=>document.getElementById('stats').textContent")
        assert viewer.text("viewer.text.witness").replace("{witness}", "T2") in stats
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_established_text_is_the_default(browser, tmp_path):
    project = copy_example(tmp_path / "exemple")
    viewer = Viewer(browser, project)
    try:
        stats = viewer("()=>document.getElementById('stats').textContent")
        pivot = viewer.text("viewer.text.pivot")
        assert viewer.text("viewer.text.established").replace("{witness}", pivot) in stats
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()
