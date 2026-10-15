# -*- coding: utf-8 -*-
"""L'état du document ouvert est porté par MainWindow.document."""
from __future__ import annotations

from pathlib import Path

from document_session import DocumentSession


def test_window_state_lives_in_document_session(open_window, example_project):
    window = open_window(example_project)
    session = window.document
    assert isinstance(session, DocumentSession)
    assert session.text_document is window.editor.document()
    assert session.path == Path(example_project).parent / "xml" / "edition.xml"
    assert session.modified is False

    # Les anciens noms d'attributs lisent et écrivent dans la session.
    assert window.current_path is session.path
    assert window.lb_spans() is session.lb.spans
    assert not session.lb.dirty

    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(" ")
    assert session.modified is True
    assert session.last_rng_result is None and session.last_rng_revision == -1


def _type_at(window, position, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_plain_typing_shifts_lb_index_without_rescan(open_window, example_project):
    from document_session import LbIndex

    window = open_window(example_project)
    lb = window.document.lb
    spans_before = list(window.lb_spans())
    target = spans_before[10][0]
    _type_at(window, target, "abc")
    assert not lb.dirty                                   # pas de nouveau balayage
    assert lb.spans == LbIndex.scan(window.editor.toPlainText(), window.lb_base_re)
    assert lb.spans[10][0] == target + 3


def test_typing_markup_invalidates_lb_index(open_window, example_project):
    window = open_window(example_project)
    window.lb_spans()
    _type_at(window, window.lb_spans()[5][0], "<hi>")
    assert window.document.lb.dirty
