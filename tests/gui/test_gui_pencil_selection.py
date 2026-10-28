# -*- coding: utf-8 -*-
"""Le crayon ✎ et F2 dans la vue XSLT / CSS (V0.9.2.8.2).

Le clic sur le crayon garde la sélection en cours de l'aperçu : si elle est
dans le paragraphe du crayon, elle est aussi sélectionnée dans l'éditeur de
fragment. F2, dans l'aperçu, ouvre le paragraphe de la sélection (ou du
curseur), la sélection reportée. Un fragment déjà ouvert et modifié n'est
pas rechargé.

Projet exemple : le paragraphe 2 contient trois fois « premium », le
paragraphe 3 « auaritia » (voir test_gui_selection_transfer.py)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QTextCursor
from PySide6.QtTest import QTest

from test_gui_selection_transfer import (
    _click, _fragment_occurrences, _preview_occurrences, _select, _selection, _show_preview,
)


def _pencil(view, paragraph):
    marker, _content, index = view.preview._paragraph_markers[paragraph]
    assert index == paragraph
    return marker


def _click_pencil(qtbot, view, paragraph):
    """Clic réel sur le crayon, sans toucher à la sélection de l'aperçu."""
    preview = view.preview
    selection = QTextCursor(preview.textCursor())
    _preview, point = _click(view, _pencil(view, paragraph), dx=4)
    preview.setTextCursor(selection)
    assert preview.anchorAt(point) == f"tei-edit://p/{paragraph}"
    qtbot.mouseClick(preview.viewport(), Qt.MouseButton.LeftButton, pos=point)


def test_the_pencil_keeps_the_selection_of_its_paragraph(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    occurrence = _preview_occurrences(view, "premium", 2)[2]
    _select(view.preview, *occurrence)
    _click_pencil(qtbot, view, 2)
    qtbot.waitUntil(lambda: view.current_paragraph == 2, timeout=3000)
    assert _selection(view.preview) == occurrence
    assert _selection(view.fragment_editor) == _fragment_occurrences(view, "premium")[2]
    assert view.focusWidget() is view.fragment_editor


def test_the_pencil_of_another_paragraph_keeps_the_selection_in_the_preview(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    occurrence = _preview_occurrences(view, "auaritia", 3)[0]
    _select(view.preview, *occurrence)
    _click_pencil(qtbot, view, 2)
    qtbot.waitUntil(lambda: view.current_paragraph == 2, timeout=3000)
    assert _selection(view.preview) == occurrence
    assert not view.fragment_editor.textCursor().hasSelection()


def test_f2_opens_the_paragraph_of_the_selection(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    action = view.edit_paragraph_action
    assert action.shortcut() == QKeySequence(Qt.Key.Key_F2)
    assert action in view.preview.actions()
    assert action.shortcutContext() == Qt.ShortcutContext.WidgetShortcut
    occurrence = _preview_occurrences(view, "premium", 2)[1]
    window.activateWindow()
    view.preview.setFocus()
    _select(view.preview, *occurrence)
    QTest.keyClick(view.preview, Qt.Key.Key_F2)
    assert view.current_paragraph == 2 and not view.frag_box.isHidden()
    assert _selection(view.preview) == occurrence
    assert _selection(view.fragment_editor) == _fragment_occurrences(view, "premium")[1]
    assert view.focusWidget() is view.fragment_editor


def test_f2_without_selection_opens_the_paragraph_of_the_cursor(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    start, _end = _preview_occurrences(view, "auaritia", 3)[0]
    cursor = QTextCursor(view.preview.document())
    cursor.setPosition(start)
    view.preview.setTextCursor(cursor)
    view.edit_paragraph_action.trigger()
    assert view.current_paragraph == 3 and not view.frag_box.isHidden()
    assert not view.fragment_editor.textCursor().hasSelection()
    assert view.focusWidget() is view.fragment_editor


def test_f2_outside_any_paragraph_does_nothing(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    cursor = QTextCursor(view.preview.document())
    cursor.setPosition(0)
    view.preview.setTextCursor(cursor)
    assert view.preview.paragraph_for_position(0) is None
    view.edit_paragraph_action.trigger()
    assert view.current_paragraph is None and view.frag_box.isHidden()


def test_a_modified_fragment_is_kept_when_its_paragraph_is_asked_again(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    assert view.load_fragment(2)
    cursor = view.fragment_editor.textCursor()
    cursor.setPosition(len("<p>"))
    cursor.insertText("uerbum nouum ")                    # pas encore appliqué
    modified = view.fragment_editor.toPlainText()
    _select(view.preview, *_preview_occurrences(view, "premium", 2)[2])
    view.edit_paragraph_action.trigger()
    assert view.fragment_editor.toPlainText() == modified
    assert _selection(view.fragment_editor) == _fragment_occurrences(view, "premium")[2]
    _click_pencil(qtbot, view, 2)
    qtbot.wait(100)
    assert view.fragment_editor.toPlainText() == modified
