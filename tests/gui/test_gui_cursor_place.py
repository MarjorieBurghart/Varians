# -*- coding: utf-8 -*-
"""Un projet rouvert retrouve son curseur : même document affiché, même
ligne, même colonne (ou la fin de la ligne si elle est devenue plus courte,
la dernière ligne si le fichier a raccourci)."""
from __future__ import annotations

from PySide6.QtGui import QTextCursor


def _place(window):
    cursor = window.editor.textCursor()
    return cursor.blockNumber(), cursor.positionInBlock()


def _move(window, line, column):
    document = window.editor.document()
    block = document.findBlockByNumber(line)
    cursor = QTextCursor(document)
    cursor.setPosition(block.position() + column)
    window.editor.setTextCursor(cursor)


def _close(window):
    window._force_close = True
    window.close()


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def test_the_cursor_comes_back_to_its_line_and_column(open_window, example_project):
    window = open_window(example_project)
    _move(window, 120, 7)
    _close(window)
    window = open_window(example_project)
    assert _place(window) == (120, 7)
    # Le curseur est visible : la ligne est dans la zone affichée.
    first = window.editor.firstVisibleBlock().blockNumber()
    assert first <= 120 < first + 80


def test_a_shorter_line_or_a_shorter_file_still_finds_its_place(open_window, example_project):
    edition = example_project.parent / "xml" / "edition.xml"
    window = open_window(example_project)
    _move(window, 120, 7)
    _close(window)
    lines = edition.read_text(encoding="utf-8").split("\n")
    lines[120] = "  x"
    edition.write_text("\n".join(lines), encoding="utf-8")
    window = open_window(example_project)
    assert _place(window) == (120, 3)                     # fin de la ligne
    _close(window)
    edition.write_text("\n".join(lines[:50]), encoding="utf-8")
    window = open_window(example_project)
    assert _place(window)[0] == 49                        # dernière ligne


def test_the_shown_document_and_each_cursor_come_back(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    _move(window, 30, 2)
    assert window.show_document(_aux(window))
    _move(window, 2, 4)
    _close(window)
    window = open_window(project_with_documents)
    qtbot.waitUntil(lambda: window.document is _aux(window))
    assert _place(window) == (2, 4)
    assert window.show_document(window.edition_session)
    assert _place(window) == (30, 2)


def test_reloading_the_same_project_keeps_the_current_place(open_window, example_project, dialogs):
    window = open_window(example_project)
    _move(window, 10, 0)
    _close(window)
    window = open_window(example_project)
    _move(window, 60, 3)
    # Paramètres du projet, ou le même projet rouvert : la position du
    # moment, non celle de la dernière fermeture.
    assert window._replace_with_project(example_project)
    replacement = window._replacement_window
    try:
        assert _place(replacement) == (60, 3)
    finally:
        _close(replacement)


def test_a_new_project_opens_at_the_start(open_window, example_project):
    window = open_window(example_project)
    assert _place(window) == (0, 0)
