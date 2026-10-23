# -*- coding: utf-8 -*-
"""Viewer web : bandeaux de lacune (V0.9.1.6), comme sur le bureau
(test_gui_lacunae.py), pilotés dans Chromium (ignorés sans Playwright ni
Chromium).

- Un témoin par lignes en lacune montre la ligne où son texte s'interrompt,
  avec « Lacune de ce témoin : son texte s'interrompt ici. ».
- Pendant une lacune du pivot, les autres témoins par lignes restent sur sa
  dernière ligne, avec « Lacune du témoin pivot… » ; les pages continuent.
- Un témoin par pages en lacune garde sa page, avec le bandeau.
- La lacune continue d'une partie à l'autre, et un texte synchronisé à part
  repart sans lacune.

Projet exemple (corpus_data.add_example_lacunae) : T2 en lacune de la ligne
20 du pivot T1 à la ligne 25 ; « PASSAGE <pb 1v de X> ABSENS », absent de
T1, avant la ligne 41."""
from __future__ import annotations

import pytest

from corpus_data import PIVOT_GAP, T2_END, T2_START, add_example_lacunae, copy_example
from test_v0916_viewer_texts import Viewer, browser  # noqa: F401  (fixture)


@pytest.fixture
def lacunae(browser, tmp_path):  # noqa: F811
    project = copy_example(tmp_path / "exemple")
    add_example_lacunae(project)
    viewer = Viewer(browser, project)
    yield viewer
    assert not viewer.errors, viewer.errors
    viewer.page.close()


def _banner(viewer, wid):
    banner = viewer.card(wid).locator("[data-role=lacuna]")
    return banner.inner_text() if banner.count() and banner.is_visible() else None


def _base_keys(viewer, wid):
    return viewer("id=>{const s=states.get(id);return s.center==null?[]:(s.physical[s.center].l.base_keys||[])}", wid)


def _click_text(viewer, words):
    viewer.page.locator(".line-frag", has_text=words).first.click()


def test_a_witness_in_lacuna_shows_where_its_text_stops(lacunae):
    order = lacunae("()=>lineOrder")
    linked = lacunae("()=>[...states.get('T2').byBase.keys()]")
    anchor = next(order[o] for o in range(T2_START, -1, -1) if order[o] in linked)
    lacunae.select(order[T2_START + 2])
    assert _banner(lacunae, "T2") == lacunae.text("manuscript.lacuna")
    assert anchor in _base_keys(lacunae, "T2")
    assert _banner(lacunae, "P") is None and order[T2_START + 2] in _base_keys(lacunae, "P")
    lacunae.select(order[T2_END])
    assert _banner(lacunae, "T2") is None and order[T2_END] in _base_keys(lacunae, "T2")


def test_a_lacuna_of_the_pivot_stops_the_lines_not_the_pages(lacunae):
    order = lacunae("()=>lineOrder")
    lacunae.select(order[PIVOT_GAP - 1])
    assert lacunae.folio("X") == "X-p0001"
    _click_text(lacunae, "ABSENS")
    assert lacunae("()=>selectedKey") == order[PIVOT_GAP - 1]           # dernière ligne de T1
    assert _banner(lacunae, "T1") == lacunae.text("manuscript.lacuna")
    for wid in ("T2", "P"):
        assert _banner(lacunae, wid) == lacunae.text("manuscript.lacuna.pivot"), wid
    assert lacunae.page.locator("#syncNotice").inner_text() == lacunae.text("status.base_lacuna").replace("{base}", "T1")
    assert lacunae.folio("X") == "X-p0002" and _banner(lacunae, "X") is None   # les pages continuent
    lacunae.select(order[PIVOT_GAP])
    assert _banner(lacunae, "T1") is None and _banner(lacunae, "T2") is None
    assert lacunae.page.locator("#syncNotice").inner_text() == ""


def test_a_page_witness_in_lacuna_keeps_its_page(browser, tmp_path):  # noqa: F811
    project = copy_example(tmp_path / "exemple")
    add_example_lacunae(project)
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace('<lacunaStart wit="#T1"/>PASSAGE', '<lacunaStart wit="#T1 #X"/>PASSAGE', 1)
                       .replace('ABSENS<lacunaEnd wit="#T1"/>', 'ABSENS<lacunaEnd wit="#T1"/><lacunaEnd wit="#X"/>', 1)
                       .replace('<pb edRef="#X" n="1v"/>', "", 1), encoding="utf-8")
    viewer = Viewer(browser, project)
    try:
        _click_text(viewer, "ABSENS")
        assert _banner(viewer, "X") == viewer.text("manuscript.lacuna")
        assert viewer.folio("X") == "X-p0001"
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_banner_follows_the_interface_language(lacunae):
    order = lacunae("()=>lineOrder")
    lacunae.select(order[T2_START + 2])
    lacunae.page.select_option("#languageSelect", "en")
    assert _banner(lacunae, "T2") == lacunae.data["i18n"]["catalogs"]["en"]["manuscript.lacuna"]


def test_a_lacuna_crosses_the_parts_and_a_text_apart_starts_without_it(browser, tmp_path):  # noqa: F811
    from test_v0916_sync_model import _lacuna_project
    viewer = Viewer(browser, _lacuna_project(tmp_path / "exemple"))
    try:
        order = viewer.data["meta"]["line_order"]
        viewer.select(order[110])
        assert _banner(viewer, "T2") == viewer.text("manuscript.lacuna")
        viewer.select(order[116 + 50])
        assert viewer("()=>activeSeg") == 1 and _banner(viewer, "T2") is None
        viewer.select(order[116 + 165 + 5])
        assert _banner(viewer, "T2") == viewer.text("manuscript.lacuna")
        viewer.select(order[116 + 165 + 14])
        assert _banner(viewer, "T2") is None
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_an_empty_paragraph_is_not_shown():
    from web_viewer.generator import HTML_TEMPLATE
    assert ".tei-p:empty{display:none}" in HTML_TEMPLATE
