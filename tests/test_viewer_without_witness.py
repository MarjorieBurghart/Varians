# -*- coding: utf-8 -*-
"""Viewer web d'un projet sans témoin : le texte seul, sans fac-similé ni
choix de témoin (le navigateur : ignoré sans Playwright ni Chromium)."""
from __future__ import annotations

import os
import re

import pytest

from corpus_data import copy_example
from project_config import load_project
from web_viewer.generator import build_dataset


def _without_witness(tmp_path):
    project = copy_example(tmp_path / "exemple")
    text = project.read_text(encoding="utf-8")
    text = re.sub(r"<witnesses\b.*?</witnesses>", "<witnesses/>", text, flags=re.S)
    project.write_text(text, encoding="utf-8")
    return project


def test_the_dataset_of_a_project_without_witness_is_the_text_alone(tmp_path):
    project = load_project(_without_witness(tmp_path))
    data, unaligned = build_dataset(project)
    assert data["witnesses"] == [] and unaligned == 0
    meta = data["meta"]
    assert meta["base_witness"] == "" and meta["display_witnesses"] == []
    assert meta["has_images"] is False and meta["line_sync"] is False
    text = " ".join(seg.get("text", "") for block in data["document"]["blocks"]
                    for seg in block.get("segments", []) if seg.get("kind") == "text")
    assert len(text.split()) > 100
    # Le texte établi : <lem>, sinon la première leçon ; sans témoin, aucun
    # passage n'est « sans leçon du témoin pivot ».
    assert meta["text"]["mode"] == "established" and meta["text"]["missing"] == 0
    assert not any(seg.get("no_reading") for block in data["document"]["blocks"]
                   for seg in block.get("segments", []))


def test_without_witness_the_text_is_always_the_established_text(tmp_path):
    project = load_project(_without_witness(tmp_path))
    data, _ = build_dataset(project, text_mode="witness", text_witness="")
    assert data["meta"]["text"]["mode"] == "established" and data["meta"]["text"]["missing"] == 0


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


def test_the_viewer_shows_the_text_without_witness_panel(browser, tmp_path):
    from test_v0916_viewer_texts import Viewer
    viewer = Viewer(browser, _without_witness(tmp_path))
    try:
        assert len(viewer("()=>document.getElementById('document').textContent").split()) > 100
        # L'en-tête : texte seul, sans « témoin pivot ».
        stats = viewer("()=>document.getElementById('stats').textContent")
        variants = viewer.data["meta"]["variants"]
        from i18n import format_message
        assert stats == (format_message(viewer.text("viewer.stats.text_only"), "fr", variants=variants)
                         + " · " + viewer.text("viewer.text.established_only"))
        assert viewer("()=>document.querySelectorAll('#document .no-reading').length") == 0
        # « ← ligne / ligne → » parcourent les lignes du pivot : masqués.
        assert viewer("()=>[$('prevBase').hidden,$('nextBase').hidden]") == [True, True]
        # Pas de panneau de témoin ni de fac-similé.
        assert viewer("()=>document.querySelectorAll('[data-w]').length") == 0
        # Un clic dans le texte ne mène nulle part, sans erreur.
        viewer("()=>{const s=document.querySelector('#document [data-line-key], #document span');"
               "if(s)s.click();return true}")
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()
