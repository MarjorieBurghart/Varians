# -*- coding: utf-8 -*-
"""Leçons hors <lem> surlignées dans le viewer web (V0.9.3.1), dans Chromium
(ignoré sans Playwright ni Chromium, comme sur GitHub).

Dans le texte établi, une case de l'en-tête, à côté de « Variantes » et
« Notes », surligne en jaune (bande de surligneur au pied des lettres) les
leçons qui ne viennent pas d'un <lem>. Son état de départ est celui choisi
à l'export ; le lecteur la coche ou la décoche. Dans le texte d'un témoin,
elle n'apparaît pas."""
from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from corpus_data import copy_example
from project_management import update_project_web_text
from test_v0916_viewer_texts import Viewer

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
KEYS = ("viewer.show_nonlem", "viewer.show_nonlem.tip")

STATE = """()=>{const box=document.getElementById('showNonLem'),option=document.getElementById('showNonLemOption'),
    mark=document.querySelector('#document .non-lem');
    return {hidden:option.hidden,checked:box.checked,body:document.body.classList.contains('show-nonlem'),
            marks:document.querySelectorAll('#document .non-lem').length,
            image:mark?getComputedStyle(mark).backgroundImage:'',label:option.textContent,tip:option.title}}"""


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


def _viewer(browser, tmp_path, mode="established", witness="", highlight=None):
    project = copy_example(tmp_path / f"exemple-{mode}-{witness}-{highlight}")
    update_project_web_text(project, mode, witness, highlight_nonlem=highlight)
    return Viewer(browser, project)


def test_the_reader_highlights_the_readings_outside_a_lem(browser, tmp_path):
    viewer = _viewer(browser, tmp_path)
    try:
        state = viewer(STATE)
        # Non surlignées au départ, par défaut ; la case est offerte.
        assert not state["hidden"] and not state["checked"] and not state["body"]
        flagged = sum(1 for block in viewer.data["document"]["blocks"] for seg in block["segments"]
                      if seg.get("nonlem") and seg["kind"] == "text")
        assert state["marks"] == flagged > 0
        assert state["image"] == "none"
        assert state["label"] == viewer.text("viewer.show_nonlem") and state["tip"] == viewer.text("viewer.show_nonlem.tip")
        viewer.page.click("#showNonLem")
        state = viewer(STATE)
        assert state["checked"] and state["body"] and "linear-gradient" in state["image"]
        # Distinct de la ligne choisie (jaune pâle) : la bande reste sur elle.
        selected = viewer("""()=>{const m=document.querySelector('#document .non-lem[data-line]');selectLine(m.dataset.line,false);
            const s=getComputedStyle(m);return [m.classList.contains('selected-line'),s.backgroundImage,s.backgroundColor]}""")
        assert selected[0] and "linear-gradient" in selected[1] and selected[2] != "rgba(0, 0, 0, 0)"
        viewer.page.click("#showNonLem")
        assert viewer(STATE)["image"] == "none"
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_export_can_start_with_the_highlight(browser, tmp_path):
    viewer = _viewer(browser, tmp_path, highlight=True)
    try:
        state = viewer(STATE)
        assert state["checked"] and state["body"] and "linear-gradient" in state["image"]
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_text_of_a_witness_offers_no_highlight(browser, tmp_path):
    viewer = _viewer(browser, tmp_path, "witness", "T2", highlight=True)
    try:
        state = viewer(STATE)
        assert state["hidden"] and state["marks"] == 0 and not state["body"]
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_highlight_labels_exist_in_the_seven_catalogs():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        for key in KEYS:
            assert catalog.get(key), (language, key)
