# -*- coding: utf-8 -*-
"""Sélections partagées entre la source, l'aperçu XSLT / CSS et l'éditeur de
fragment (V0.9.1.2).

Report entre les onglets Source et XSLT / CSS : une chaîne sélectionnée dans
une vue l'est dans l'autre, à la même occurrence du même paragraphe, y compris
à travers un ``<lb break="no"/>``. Pour une édition en parties, l'aperçu
montre l'édition assemblée en lecture seule : rien n'est reporté (étape 5).

Projet exemple : le paragraphe 1 (RLS_184) contient « me<lb break="no"/>cum »,
le paragraphe 2 trois fois « premium » (la première fois « premi<lb
break="no"/>um »)."""
from __future__ import annotations

import re

from PySide6.QtGui import QTextCursor

from formatted_view import paragraph_spans

WJ = "⁠"          # WORD JOINER technique de l'aperçu


def _show_preview(window, qtbot):
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: len(view.preview.toPlainText()) > 1000, timeout=15000)
    return view


def _source_occurrences(window, word, paragraph):
    """Occurrences de ``word`` dans le XML du paragraphe, un ``<lb/>`` pouvant
    couper le mot."""
    pattern = r"(?:\s*<lb\b[^>]*/>\s*)?".join(re.escape(ch) for ch in word)
    text = window.editor.toPlainText()
    start, end = paragraph_spans(text)[paragraph]
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


def test_an_edition_in_parts_does_not_carry_the_selection(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    _select(window.editor, *_source_occurrences(window, "premium", 2)[1])
    view = _show_preview(window, qtbot)
    qtbot.wait(150)
    assert not view.preview.textCursor().hasSelection()
    word = _preview_occurrences(view, "premium", 2) if view.preview.paragraph_bounds(2) else []
    assert word == []                                     # pas de repères de paragraphe
    plain = view.preview.toPlainText()
    start = plain.index("premium")
    _select(view.preview, start, start + len("premium"))
    window.left_tabs.setCurrentIndex(0)
    qtbot.wait(150)
    assert _selection(window.editor) == _source_occurrences(window, "premium", 2)[1]
