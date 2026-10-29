# -*- coding: utf-8 -*-
"""Sélections partagées entre la source, l'aperçu XSLT / CSS et l'éditeur de
fragment (V0.9.1.2).

Report entre les onglets Source et XSLT / CSS : une chaîne sélectionnée dans
une vue l'est dans l'autre, à la même occurrence du même paragraphe, y compris
à travers un ``<lb break="no"/>``. Pour une édition en parties, voir
test_gui_assembled_selection.py (V0.9.1.5).

Projet exemple : le paragraphe 1 (RLS_184) contient « me<lb break="no"/>cum »,
le paragraphe 2 trois fois « premium » (la première fois « premi<lb
break="no"/>um »)."""
from __future__ import annotations

import re

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QTextCursor

from fragment_units import unit_spans

WJ = "⁠"          # WORD JOINER technique de l'aperçu


def _show_preview(window, qtbot):
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: len(view.preview.toPlainText()) > 1000, timeout=15000)
    qtbot.wait(50)                  # repositionnement différé après un rendu
    return view


def _source_occurrences(window, word, paragraph):
    """Occurrences de ``word`` dans le XML du paragraphe, un ``<lb/>`` pouvant
    couper le mot."""
    pattern = r"(?:\s*<lb\b[^>]*/>\s*)?".join(re.escape(ch) for ch in word)
    text = window.editor.toPlainText()
    start, end = unit_spans(text)[paragraph]
    return [(start + m.start(), start + m.end()) for m in re.finditer(pattern, text[start:end])]


def _preview_occurrences(view, word, paragraph):
    preview = view.preview
    start, end = preview.paragraph_bounds(paragraph)
    plain = preview.toPlainText()
    pattern = (WJ + "*").join(re.escape(ch) for ch in word)
    return [(start + m.start(), start + m.end()) for m in re.finditer(pattern, plain[start:end])]


def _select(editor, start, end):
    cursor = QTextCursor(editor.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def _selection(editor):
    cursor = editor.textCursor()
    return cursor.selectionStart(), cursor.selectionEnd()


def _visible(text):
    return re.sub(r"<[^>]+>|\s", "", text.replace(WJ, ""))


# --- Source <-> XSLT / CSS (comportement existant, à garder) -----------------

def test_a_source_selection_selects_the_same_occurrence_in_the_preview(open_window, example_project, qtbot):
    window = open_window(example_project)
    _show_preview(window, qtbot)                          # aperçu déjà calculé
    window.left_tabs.setCurrentIndex(0)
    _select(window.editor, *_source_occurrences(window, "premium", 2)[1])
    view = _show_preview(window, qtbot)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    assert _selection(view.preview) == _preview_occurrences(view, "premium", 2)[1]


def test_a_preview_selection_selects_the_same_occurrence_in_the_source(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    expected = _source_occurrences(window, "premium", 2)[2]
    _select(view.preview, *_preview_occurrences(view, "premium", 2)[2])
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.editor.textCursor().hasSelection(), timeout=5000)
    assert _selection(window.editor) == expected


def test_a_word_cut_by_a_line_break_is_selected_in_both_views(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    window.left_tabs.setCurrentIndex(0)
    source = _source_occurrences(window, "mecum", 1)
    assert len(source) == 1 and "<lb" in window.editor.toPlainText()[slice(*source[0])]
    _select(window.editor, *source[0])
    _show_preview(window, qtbot)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    assert _selection(view.preview) == _preview_occurrences(view, "mecum", 1)[0]
    # Retour : la sélection de l'aperçu redevient la sélection XML continue.
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.editor.textCursor().hasSelection(), timeout=5000)
    assert _selection(window.editor) == source[0]
    assert _visible(window.editor.textCursor().selectedText()) == "mecum"


# --- Le crayon ✎ ouvre le paragraphe sans entraîner les témoins --------------

def _click(view, position, dx=0):
    """Clic de souris réel dans l'aperçu, sur le caractère ``position``."""
    preview = view.preview
    cursor = QTextCursor(preview.document())
    cursor.setPosition(position)
    preview.setTextCursor(cursor)
    preview.ensureCursorVisible()
    rect = preview.cursorRect(cursor)
    return preview, QPoint(rect.left() + dx, rect.center().y())


def _witness_state(window):
    return (window._last_synced_ordinal, window.editor.textCursor().position(),
            {wid: (panel.center_index, panel.primary_key) for wid, panel in window.panels.items()})


def test_the_pencil_opens_the_paragraph_without_moving_the_witnesses(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    qtbot.wait(150)
    before = _witness_state(window)
    marker, _content, paragraph = view.preview._paragraph_markers[5]
    preview, point = _click(view, marker, dx=4)
    assert preview.anchorAt(point) == f"tei-edit://p/{paragraph}"
    qtbot.mouseClick(preview.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.waitUntil(lambda: view.current_paragraph == paragraph, timeout=3000)
    assert not view.frag_box.isHidden()
    qtbot.wait(300)                                       # minuterie de synchronisation
    assert _witness_state(window) == before


def test_a_click_on_the_text_still_moves_the_witnesses(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _show_preview(window, qtbot)
    qtbot.wait(150)
    start, _end = _preview_occurrences(view, "premium", 2)[2]
    line = view.preview.line_for_position(start)
    assert line and line != window._last_synced_ordinal
    preview, point = _click(view, start, dx=2)
    qtbot.mouseClick(preview.viewport(), Qt.MouseButton.LeftButton, pos=point)
    qtbot.waitUntil(lambda: window._last_synced_ordinal == line, timeout=3000)
    assert window.base_panel.center_index == line


# --- Aperçu -> éditeur de fragment -------------------------------------------

def _open_fragment(window, qtbot, paragraph):
    view = _show_preview(window, qtbot)
    assert view.load_fragment(paragraph)
    return view


def _double_click(qtbot, view, position, dx=3):
    """Double-clic réel : QTest.mouseDClick n'envoie que l'événement du
    double-clic, sans le relâchement qui le suit."""
    preview, point = _click(view, position, dx=dx)
    left = Qt.MouseButton.LeftButton
    qtbot.mousePress(preview.viewport(), left, pos=point)
    qtbot.mouseRelease(preview.viewport(), left, pos=point)
    qtbot.mouseDClick(preview.viewport(), left, pos=point)
    qtbot.mouseRelease(preview.viewport(), left, pos=point)


def _fragment_occurrences(view, word):
    pattern = r"(?:\s*<lb\b[^>]*/>\s*)?".join(re.escape(ch) for ch in word)
    return [m.span() for m in re.finditer(pattern, view.fragment_editor.toPlainText())]


def test_a_preview_selection_is_selected_in_the_open_fragment(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _double_click(qtbot, view, _preview_occurrences(view, "premium", 2)[2][0])
    assert view.preview.textCursor().selectedText().replace(WJ, "") == "premium"
    qtbot.waitUntil(lambda: view.fragment_editor.textCursor().hasSelection(), timeout=3000)
    assert _selection(view.fragment_editor) == _fragment_occurrences(view, "premium")[2]
    assert view.fragment_editor.hasFocus()


def test_a_word_cut_by_a_line_break_is_selected_in_the_fragment(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _select(view.preview, *_preview_occurrences(view, "premium", 2)[0])
    view.preview.textSelected.emit()
    first = _fragment_occurrences(view, "premium")[0]
    assert _selection(view.fragment_editor) == first
    assert 'break="no"' in view.fragment_editor.textCursor().selectedText()


def test_a_selection_in_another_paragraph_leaves_the_fragment(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _double_click(qtbot, view, _preview_occurrences(view, "auaritia", 3)[0][0])
    assert view.preview.textCursor().hasSelection()
    qtbot.wait(100)
    assert not view.fragment_editor.textCursor().hasSelection()
    assert view.current_paragraph == 2 and not view.fragment_editor.hasFocus()


def test_the_pencil_is_not_a_selection(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    marker, _content, paragraph = view.preview._paragraph_markers[2]
    _double_click(qtbot, view, marker, dx=4)
    qtbot.wait(100)
    assert view.current_paragraph == paragraph == 2
    assert not view.fragment_editor.textCursor().hasSelection()


def test_a_modified_fragment_is_searched_in_its_current_text(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    cursor = view.fragment_editor.textCursor()
    cursor.setPosition(len("<p>"))
    cursor.insertText("uerbum nouum ")                    # pas encore appliqué
    _select(view.preview, *_preview_occurrences(view, "premium", 2)[2])
    view.preview.textSelected.emit()
    # Même rang, à sa nouvelle place dans le texte du fragment.
    expected = _fragment_occurrences(view, "premium")[2]
    assert expected[0] > _source_occurrences(window, "premium", 2)[2][0] - unit_spans(
        window.editor.toPlainText())[2][0]
    assert _selection(view.fragment_editor) == expected


# --- Éditeur de fragment -> aperçu -------------------------------------------

def _focus_fragment(qtbot, view):
    view.fragment_editor.setFocus()
    qtbot.waitUntil(view.fragment_editor.hasFocus, timeout=3000)


def test_a_fragment_selection_is_selected_in_the_preview(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _focus_fragment(qtbot, view)
    _select(view.fragment_editor, *_fragment_occurrences(view, "premium")[2])
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=3000)
    assert _selection(view.preview) == _preview_occurrences(view, "premium", 2)[2]
    assert view.fragment_editor.hasFocus()                # on continue à taper


def test_a_cut_word_of_the_fragment_is_selected_in_the_preview(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _focus_fragment(qtbot, view)
    first = _fragment_occurrences(view, "premium")[0]
    assert 'break="no"' in view.fragment_editor.toPlainText()[slice(*first)]
    _select(view.fragment_editor, *first)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=3000)
    assert _selection(view.preview) == _preview_occurrences(view, "premium", 2)[0]


def test_a_selection_from_the_preview_does_not_come_back(open_window, example_project, qtbot, monkeypatch):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    calls = []
    original = view.preview.select_visible_text_in_paragraph
    monkeypatch.setattr(view.preview, "select_visible_text_in_paragraph",
                        lambda *args, **kwargs: calls.append(args) or original(*args, **kwargs))
    _double_click(qtbot, view, _preview_occurrences(view, "premium", 2)[1][0])
    qtbot.waitUntil(lambda: view.fragment_editor.textCursor().hasSelection(), timeout=3000)
    qtbot.wait(400)
    assert calls == []
    assert _selection(view.preview) == _preview_occurrences(view, "premium", 2)[1]


def test_markup_or_a_simple_cursor_move_changes_nothing(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = _open_fragment(window, qtbot, 2)
    _focus_fragment(qtbot, view)
    text = view.fragment_editor.toPlainText()
    start = text.index("<app>")
    _select(view.fragment_editor, start, start + len("<app>"))       # balise seule
    qtbot.wait(400)
    assert not view.preview.textCursor().hasSelection()
    cursor = view.fragment_editor.textCursor()
    cursor.setPosition(_fragment_occurrences(view, "premium")[2][0])
    view.fragment_editor.setTextCursor(cursor)                        # sans sélection
    qtbot.wait(400)
    assert not view.preview.textCursor().hasSelection()
