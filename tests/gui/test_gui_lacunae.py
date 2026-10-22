# -*- coding: utf-8 -*-
"""Lacunes des témoins dans la fenêtre (V0.9.1.3).

Un témoin en lacune garde la ligne (ou la page) où son texte s'interrompt,
avec le bandeau « Lacune » ; pendant une lacune du pivot, les témoins
synchronisés par lignes restent sur la dernière ligne du pivot, avec un
message, et les témoins par pages continuent de suivre leurs <pb>.

Copie du projet exemple (pivot T1 ; T2 et P synchronisés par lignes) :
- T2 est en lacune de la ligne 20 du pivot (après son <lb/>) à la ligne 25 ;
- un passage absent de T1 est inséré avant la ligne 41 ;
- X, témoin par pages (folios 1r, 1v), a son <pb n="1r"/> au début du
  <body> et son <pb n="1v"/> dans le passage absent de T1."""
from __future__ import annotations

import pytest

from app_context import tr
from corpus_data import add_page_witness
from pivot_lines import pivot_lb_pattern

T2_START, T2_END, PIVOT_GAP = 20, 25, 41
GAP = '<lacunaStart wit="#T1"/>PASSAGE <pb edRef="#X" n="1v"/>ABSENS<lacunaEnd wit="#T1"/>'


def _insert(text, inserts):
    for position, value in sorted(inserts, reverse=True):
        text = text[:position] + value + text[position:]
    return text


@pytest.fixture
def example_with_lacunae(example_project):
    add_page_witness(example_project, "X", ("1r", "1v"))
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    body = text.index("<body>") + len("<body>")
    edition.write_text(_insert(text, [
        (body, '<pb edRef="#X" n="1r"/>'),
        (lbs[T2_START][1], '<lacunaStart wit="#T2"/>'),
        (lbs[T2_END][1], '<lacunaEnd wit="#T2"/>'),
        (lbs[PIVOT_GAP][0], GAP),
    ]), encoding="utf-8")
    return example_project


def _cursor(window, position):
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)


def _at(window, needle, offset=0):
    _cursor(window, window.editor.toPlainText().index(needle) + offset)
    window.sync_panels_to_cursor()


def _at_line(window, ordinal, offset=1):
    _cursor(window, window.lb_spans()[ordinal][1] + offset)
    window.sync_panels_to_cursor()


def _linked_before(window, wid, ordinal):
    """Ligne du pivot la plus proche de ``ordinal``, en remontant, à laquelle
    le témoin a une ligne reliée."""
    panel = window.panels[wid]
    return next(o for o in range(ordinal, -1, -1) if panel.map_base.get(window.base_items[o]["key"]))


def test_a_witness_in_lacuna_shows_where_its_text_stops(open_window, example_with_lacunae):
    window = open_window(example_with_lacunae)
    t2, p = window.panels["T2"], window.panels["P"]
    _at_line(window, T2_START + 2)
    assert window._last_synced_ordinal == T2_START + 2
    assert t2.lacuna_key == "manuscript.lacuna" and t2.lacuna_label.text() == tr("manuscript.lacuna")
    assert not t2.lacuna_label.isHidden()
    anchor = _linked_before(window, "T2", T2_START)
    assert t2.primary_key == window.base_items[anchor]["key"] and t2.match_indices
    assert p.lacuna_key is None and p.primary_key == window.base_items[T2_START + 2]["key"]
    # Après <lacunaEnd/>, T2 suit de nouveau le pivot.
    _at_line(window, T2_END, offset=len('<lacunaEnd wit="#T2"/>') + 1)
    assert t2.lacuna_key is None and t2.lacuna_label.isHidden()
    assert t2.primary_key == window.base_items[T2_END]["key"]


def test_entering_a_lacuna_inside_a_line_shows_the_banner(open_window, example_with_lacunae):
    window = open_window(example_with_lacunae)
    tag = window.editor.toPlainText().index('<lacunaStart wit="#T2"/>')
    _cursor(window, tag)
    window.sync_panels_to_cursor()
    assert window.panels["T2"].lacuna_key is None
    _cursor(window, tag + len('<lacunaStart wit="#T2"/>') + 1)            # même ligne du pivot
    window.sync_panels_to_cursor()
    assert window.panels["T2"].lacuna_key == "manuscript.lacuna"


def test_a_lacuna_of_the_pivot_stops_the_lines_not_the_pages(open_window, example_with_lacunae):
    window = open_window(example_with_lacunae)
    x = window.panels["X"]
    assert not x.sync_enabled
    _at_line(window, PIVOT_GAP - 1)
    assert str(x.current_item()["p"]["tei_surface_id"]) == "X-p0001"
    _at(window, "ABSENS")
    assert window._last_synced_ordinal == PIVOT_GAP - 1                   # dernière ligne de T1
    assert window.base_panel.lacuna_key == "manuscript.lacuna"
    for wid in ("T2", "P"):
        panel = window.panels[wid]
        assert panel.lacuna_key == "manuscript.lacuna.pivot", wid
        assert panel.primary_key == window.base_items[PIVOT_GAP - 1]["key"], wid
    assert window.statusBar().currentMessage() == tr("status.base_lacuna", base="T1")
    assert str(x.current_item()["p"]["tei_surface_id"]) == "X-p0002"     # les pages continuent
    assert x.lacuna_key is None
    _at_line(window, PIVOT_GAP)
    assert window.base_panel.lacuna_key is None and window.panels["T2"].lacuna_key is None


def test_a_page_witness_in_lacuna_keeps_its_page(open_window, example_with_lacunae):
    edition = example_with_lacunae.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace('<lacunaStart wit="#T1"/>PASSAGE', '<lacunaStart wit="#T1 #X"/>PASSAGE', 1)
                       .replace('ABSENS<lacunaEnd wit="#T1"/>', 'ABSENS<lacunaEnd wit="#T1"/><lacunaEnd wit="#X"/>', 1)
                       .replace('<pb edRef="#X" n="1v"/>', "", 1), encoding="utf-8")
    window = open_window(example_with_lacunae)
    x = window.panels["X"]
    _at(window, "ABSENS")
    assert x.lacuna_key == "manuscript.lacuna"
    assert str(x.current_item()["p"]["tei_surface_id"]) == "X-p0001"     # la page où il s'interrompt


def test_the_banner_follows_the_interface_language(open_window, example_with_lacunae):
    window = open_window(example_with_lacunae)
    _at_line(window, T2_START + 2)
    window._set_language_code("en")
    try:
        assert window.panels["T2"].lacuna_label.text() == tr("manuscript.lacuna")
    finally:
        window._set_language_code("fr")


def test_a_lacuna_crosses_the_parts_of_the_edition(open_window, example_with_part):
    edition = example_with_part.parent / "xml" / "edition.xml"
    part = edition.parent / "rls185.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    edition.write_text(_insert(text, [(lbs[110][1], '<lacunaStart wit="#T2"/>')]), encoding="utf-8")
    part_text = part.read_text(encoding="utf-8")
    part_lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(part_text)]
    part.write_text(_insert(part_text, [(part_lbs[10][1], '<lacunaEnd wit="#T2"/>')]), encoding="utf-8")
    window = open_window(example_with_part)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    t2 = window.panels["T2"]
    _at_line(window, 5)
    assert t2.lacuna_key == "manuscript.lacuna"
    assert t2.primary_key == window.base_items[_linked_before(window, "T2", 110)]["key"]
    _at_line(window, 10, offset=len('<lacunaEnd wit="#T2"/>') + 1)
    assert t2.lacuna_key is None
