# -*- coding: utf-8 -*-
"""Un témoin par pages mène l'édition (V0.9.1.4) ; les flèches d'un panneau
absent mènent au texte suivant ou précédent qui a ce témoin.

Projet exemple dont RLS_185 (xml/rls185.xml) est synchronisé à part (T1 et
T2 y ont un JSON ; P non), avec deux témoins par pages, à images locales :
- X (12r, 12v, 13r, 13v) : ses <pb> dans rls185, 12v après la ligne 4 du
  pivot (rang 3), 13r après la ligne 21 (rang 20) ; 13v n'a pas de <pb> ;
- Y (1r, 1v), sans <pb> : son <locus from="1v" target="#RLS_185">."""
from __future__ import annotations

import pytest

from app_context import tr
from corpus_data import add_page_witness
from pivot_lines import pivot_lb_pattern

PB_12V = '<pb edRef="#X" n="12v"/>'
PB_13R = '<pb edRef="#X" n="13r"/>'


def _insert(text, inserts):
    for position, value in sorted(inserts, reverse=True):
        text = text[:position] + value + text[position:]
    return text


@pytest.fixture
def text_with_pages(example_with_text):
    add_page_witness(example_with_text, "X", ("12r", "12v", "13r", "13v"))
    add_page_witness(example_with_text, "Y", ("1r", "1v"))
    part = example_with_text.parent / "xml" / "rls185.xml"
    text = part.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    part.write_text(_insert(text, [(lbs[3][1], PB_12V), (lbs[20][1], PB_13R)]), encoding="utf-8")
    edition = example_with_text.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace("</listWit>", '<witness xml:id="Y">Y <locus from="1v" target="#RLS_185"/>'
                                                  '</witness></listWit>', 1), encoding="utf-8")
    return example_with_text


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _open_text(open_window, project):
    window = open_window(project)
    window.show_document(_doc(window, "rls185.xml"))
    return window


def _at_line(window, ordinal):
    window._show_base_ordinal(ordinal)
    window.sync_panels_to_cursor(True)


def _surface(panel):
    return str(panel.current_item()["p"]["tei_surface_id"])


def _after(window, needle):
    return window.editor.toPlainText().index(needle) + len(needle)


def test_a_page_witness_leads_the_edition_to_its_pb(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    _at_line(window, 1)
    x = window.panels["X"]
    assert _surface(x) == "X-p0001"
    x.navigate(1)
    assert _surface(x) == "X-p0002"
    assert window.document is _doc(window, "rls185.xml")
    assert window.editor.textCursor().position() == _after(window, PB_12V)
    assert window._last_synced_ordinal == 3                   # les autres suivent le pivot
    x.navigate(1)
    assert _surface(x) == "X-p0003" and window.editor.textCursor().position() == _after(window, PB_13R)


def test_a_page_witness_leads_from_the_edition_into_the_text(open_window, text_with_pages):
    window = open_window(text_with_pages)
    x = window.panels["X"]
    assert window.document is window.edition_session and x.absent_key is None
    x.set_folio("X-p0001")
    x.navigate(1)
    assert window.document is _doc(window, "rls185.xml")
    assert window.editor.textCursor().position() == _after(window, PB_12V)
    assert _surface(x) == "X-p0002"


def test_choosing_a_folio_in_the_list_leads_the_edition(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    _at_line(window, 1)
    x = window.panels["X"]
    x.folio_combo.setCurrentIndex(next(i for i, f in enumerate(x.folios) if f.label == "13r"))
    assert window.editor.textCursor().position() == _after(window, PB_13R)
    assert _surface(x) == "X-p0003"


def test_a_page_without_pb_leaves_the_edition_with_a_message(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    _at_line(window, 30)
    x = window.panels["X"]
    position = window.editor.textCursor().position()
    x.set_folio("X-p0003")
    x.navigate(1)
    assert _surface(x) == "X-p0004"
    assert window.editor.textCursor().position() == position
    assert window.statusBar().currentMessage() == tr("status.page_unmarked", witness="X", folio="13v")


def test_the_locus_of_a_page_leads_to_the_start_of_the_text(open_window, text_with_pages):
    window = open_window(text_with_pages)
    y = window.panels["Y"]
    y.set_folio("Y-p0001")
    y.navigate(1)
    assert window.document is _doc(window, "rls185.xml")
    assert window._last_synced_ordinal == 0
    assert _surface(y) == "Y-p0002"


def test_the_arrows_of_an_absent_panel_go_to_the_next_text_that_has_the_witness(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    p = window.panels["P"]
    assert p.absent_key == "manuscript.text_absent"
    p.navigate(1)
    assert window.document is window.edition_session
    assert p.absent_key is None and window._last_synced_ordinal >= 116
    window.show_document(_doc(window, "rls185.xml"))
    p.navigate(-1)
    assert window.document is window.edition_session
    assert window._last_synced_ordinal <= 115
