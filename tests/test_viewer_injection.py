# -*- coding: utf-8 -*-
"""Red team (intégrité et sécurité, C1) : le texte d'une édition, d'un JSON
d'alignement ou d'un manifeste IIIF ne peut ni exécuter de script dans le
viewer web publié, ni le casser.

Les données sont insérées dans un bloc ``<script type="application/json">``.
Seul « </ » y était échappé, et les marques de la page (``__BODY_CLASS__``,
``__SEARCH_JS__``…) étaient remplacées après l'insertion des données : le
texte « <__BODY_CLASS__/script> » devenait une vraie balise fermante, et le
reste du texte du HTML exécuté par chaque visiteur. « <!--<script> » ou
« __SEARCH_JS__ » cassaient la page."""
from __future__ import annotations

import json
import os
import re

import pytest

from corpus_data import copy_example
from web_viewer.generator import generate, make_html

PAYLOADS = ("<__BODY_CLASS__/script><img src=x onerror=window.__pwned=1>", "<!--<script>", "__SEARCH_JS__",
            "</script><script>window.__pwned=2</script>", "__DATA_JSON__ __TITLE__   & <b>")


def _data_block(page):
    found = re.findall(r'<script id="data" type="application/json">(.*?)</script>', page, re.S)
    assert len(found) == 1
    return found[0]


def test_the_data_cannot_leave_their_block(tmp_path):
    clean = {"meta": {"title": "Titre", "has_images": True}, "i18n": {"default": "fr"}, "text": "x"}
    hostile = {**clean, "text": " ".join(PAYLOADS), PAYLOADS[1]: list(PAYLOADS)}
    page, reference = make_html(hostile), make_html(clean)
    assert page.count("</script") == reference.count("</script")
    assert page.count("<script") == reference.count("<script")
    assert "<!--" not in _data_block(page) and "<" not in _data_block(page)
    assert json.loads(_data_block(page)) == hostile                  # le texte reste intact
    # Les scripts de la page ne sont copiés qu'une fois, à leur place.
    assert page.count("function buildState") == reference.count("function buildState") == 1


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


def test_a_hostile_text_is_shown_as_text_in_the_viewer(browser, tmp_path):
    project = copy_example(tmp_path / "exemple")
    edition = project.parent / "xml" / "edition.xml"
    source = edition.read_text(encoding="utf-8")
    escaped = " ".join(p.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;") for p in PAYLOADS)
    assert source.count("Commune sanctorum") >= 1
    edition.write_text(source.replace("Commune sanctorum", f"Commune {escaped} sanctorum", 1), encoding="utf-8")
    output, _missing, data = generate(project)
    assert data["meta"]["has_images"]                                # le cas où __BODY_CLASS__ est vide
    page = browser.new_page()
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.route("http://**", lambda route: route.abort())
    page.route("https://**", lambda route: route.abort())
    page.goto(output.as_uri())
    page.wait_for_timeout(300)
    try:
        assert page.evaluate("()=>window.__pwned") is None
        assert not errors, errors
        text = page.evaluate("()=>document.getElementById('document').innerText")
        assert "<__BODY_CLASS__/script>" in text and "__SEARCH_JS__" in text and "<!--<script>" in text
    finally:
        page.close()
