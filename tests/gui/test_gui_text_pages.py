# -*- coding: utf-8 -*-
"""Témoins par pages dans un texte synchronisé à part (V0.9.1.3).

Projet exemple dont RLS_185, passé dans une partie (xml/rls185.xml), est
synchronisé à part (T1 et T2 y ont un JSON, P non : il garde le message
d'absence). On ajoute deux témoins par pages, à images locales :
- X (folios 12r, 12v, 13r, 13v), qui a ses <pb> dans le texte : 12v après la
  ligne 3 du pivot, 13r après la ligne 20 ;
- Y (folios 1r, 1v), sans <pb> dans le texte."""
from __future__ import annotations

import pytest

from app_context import tr
from corpus_data import add_text_pages
from corpus_data import insert_at as _insert
from pivot_lines import pivot_lb_pattern

TEXT_ABSENT = "manuscript.text_absent"


@pytest.fixture
def text_with_pages(example_with_text):
    add_text_pages(example_with_text)
    return example_with_text


def _with_loci(project, loci):
    """Ajoute des <witness> à <locus> dans le <listWit> de l'édition."""
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    witnesses = "".join(f'<witness xml:id="{wid}">{wid} <locus from="{start}" target="#RLS_185"/></witness>'
                        for wid, start in loci)
    edition.write_text(text.replace("</listWit>", witnesses + "</listWit>", 1), encoding="utf-8")


def _open_text(open_window, project):
    window = open_window(project)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    return window


def _at_line(window, ordinal, offset=0):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.lb_spans()[ordinal][1] + offset)
    window.editor.setTextCursor(cursor)
    window.sync_panels_to_cursor()


def _surface(panel):
    return str(panel.current_item()["p"]["tei_surface_id"])


def test_a_page_witness_follows_its_pages_in_the_text(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    x, y = window.panels["X"], window.panels["Y"]
    assert x.absent_key is None and not x.sync_enabled and len(x.items) == 4
    assert y.absent_key == TEXT_ABSENT and window.panels["P"].absent_key == TEXT_ABSENT
    _at_line(window, 1)
    assert _surface(x) == "X-p0001"            # avant son premier <pb> (12v) : la page qui précède
    _at_line(window, 3, offset=len('<pb edRef="#X" n="12v"/>'))
    assert _surface(x) == "X-p0002"
    _at_line(window, 21)
    assert _surface(x) == "X-p0003"
    # Retour à l'édition : X y reste un témoin par pages, Y aussi.
    window.show_document(window.edition_session)
    assert x.absent_key is None and y.absent_key is None and len(y.items) == 2


def test_the_start_page_comes_from_the_locus_of_the_witness(open_window, text_with_pages):
    _with_loci(text_with_pages, (("X", "12v"), ("Y", "1v")))
    window = _open_text(open_window, text_with_pages)
    x, y = window.panels["X"], window.panels["Y"]
    assert y.absent_key is None and len(y.items) == 2       # Y a le texte par son <locus>
    _at_line(window, 1)
    assert _surface(x) == "X-p0002"                          # @from, et non la page qui précède
    assert _surface(y) == "Y-p0002"


def test_a_page_witness_in_lacuna_in_the_text(open_window, text_with_pages):
    part = text_with_pages.parent / "xml" / "rls185.xml"
    text = part.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    part.write_text(_insert(text, [(lbs[10][1], '<lacunaStart wit="#X"/>')]), encoding="utf-8")
    window = _open_text(open_window, text_with_pages)
    _at_line(window, 12)
    assert window.panels["X"].lacuna_key == "manuscript.lacuna"
    assert _surface(window.panels["X"]) == "X-p0002"


def test_marking_a_page_of_a_page_witness_in_the_text(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    part = window.document
    _at_line(window, 30)
    window._edition_write(window._mark_page_in_tei)("X", "X-p0004", "13v")
    assert '<pb n="13v" edRef="#X" facs="#X-p0004"/>' in window.editor.toPlainText()
    assert 'xml:id="X-p0004"' in window.edition_session.text_document.toPlainText()
    assert part.modified
    window.sync_panels_to_cursor(True)
    assert _surface(window.panels["X"]) == "X-p0004"


def test_the_diagnostics_name_the_page_witnesses_of_a_text(open_window, text_with_pages, dialogs):
    window = _open_text(open_window, text_with_pages)
    found = []
    dialogs.expect("dialog", lambda dialog: found.append(dialog.notes.text()) or 0)
    window.show_witness_diagnostics()
    expected = tr("diagnostics.text_item.pages", name="rls185", base="T1", witnesses="T1, T2", pages="X")
    assert expected != "diagnostics.text_item.pages" and expected in found[0]


def test_a_new_pb_in_the_text_is_found_on_the_next_visit(open_window, text_with_pages):
    window = _open_text(open_window, text_with_pages)
    assert window.panels["Y"].absent_key == TEXT_ABSENT
    _at_line(window, 5)
    window.editor.textCursor().insertText('<pb edRef="#Y" n="1v"/>')
    window.show_document(window.edition_session)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    assert window.panels["Y"].absent_key is None
