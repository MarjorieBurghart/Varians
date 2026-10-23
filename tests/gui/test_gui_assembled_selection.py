# -*- coding: utf-8 -*-
"""Report des sélections et de la position entre la Vue XSLT / CSS d'une
édition assemblée et la source (V0.9.1.5) : la sélection de l'aperçu va dans
le fichier qui contient le texte (une partie, ou l'édition), à la même
occurrence du même paragraphe ; dans l'autre sens, la sélection d'une partie
est retrouvée dans l'aperçu de toute l'édition.

Projet exemple dont le sermon RLS_185 est dans une partie, xml/rls185.xml :
les paragraphes 0 à 11 de l'aperçu sont dans l'édition (le paragraphe 2
contient trois fois « premium »), les paragraphes 12 à 22 dans la partie (le
paragraphe 14 contient plusieurs fois « meritum »)."""
from __future__ import annotations

import re
from pathlib import Path

from PySide6.QtGui import QTextCursor

from formatted_view import paragraph_spans

WJ = "⁠"          # WORD JOINER technique de l'aperçu
PART_PARAGRAPH = 14


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _show_preview(window, qtbot):
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: len(view.preview.toPlainText()) > 1000, timeout=15000)
    qtbot.wait(50)                  # repositionnement différé après un rendu
    return view


def _word(word):
    return r"(?:\s*<lb\b[^>]*/>\s*)?".join(re.escape(ch) for ch in word)


def _occurrences_in(text, word, start, end):
    return [(start + m.start(), start + m.end()) for m in re.finditer(_word(word), text[start:end])]


def _part_occurrences(window, word, paragraph):
    """Occurrences de ``word`` dans le XML du paragraphe ``paragraph`` de
    l'aperçu, dans son fichier."""
    span = window._assembled_preview_sources().paragraphs[paragraph]
    session = _doc(window, Path(span.path).name)
    text = session.text_document.toPlainText() if session.text_document else Path(span.path).read_text(encoding="utf-8")
    return session, _occurrences_in(text, word, span.start, span.end)


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


def _to_source(window, qtbot):
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.editor.textCursor().hasSelection(), timeout=5000)


# --- Aperçu -> source ----------------------------------------------------------

def test_a_preview_selection_goes_into_the_part_that_contains_it(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    view = _show_preview(window, qtbot)
    part, expected = _part_occurrences(window, "meritum", PART_PARAGRAPH)
    preview = _preview_occurrences(view, "meritum", PART_PARAGRAPH)
    assert part.path.name == "rls185.xml" and len(expected) == len(preview) >= 2
    _select(view.preview, *preview[1])
    _to_source(window, qtbot)
    assert window.document is part
    assert _selection(window.editor) == expected[1]


def test_a_preview_selection_in_the_edition_stays_in_the_edition(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    window.show_document(_doc(window, "rls185.xml"))
    view = _show_preview(window, qtbot)
    edition, expected = _part_occurrences(window, "premium", 2)
    assert edition is window.edition_session
    _select(view.preview, *_preview_occurrences(view, "premium", 2)[2])
    _to_source(window, qtbot)
    assert window.document is window.edition_session
    assert _selection(window.editor) == expected[2]


def test_a_preview_position_leads_the_cursor_into_its_file(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    view = _show_preview(window, qtbot)
    index = next(i for i, (path, _end) in enumerate(view.sources.lines) if Path(path).name == "rls185.xml") + 12
    view.preview.scroll_to_line(index, center=True)
    line = view.current_preview_line()
    assert Path(view.sources.lines[line][0]).name == "rls185.xml"
    window.left_tabs.setCurrentIndex(0)
    qtbot.wait(50)
    assert window.document is _doc(window, "rls185.xml")
    assert window.editor.textCursor().position() == view.sources.lines[line][1]


# --- Source -> aperçu ----------------------------------------------------------

def test_a_part_selection_is_found_in_the_preview_of_the_edition(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    view = _show_preview(window, qtbot)                   # aperçu déjà calculé
    part, occurrences = _part_occurrences(window, "meritum", PART_PARAGRAPH)
    window.left_tabs.setCurrentIndex(0)
    window.show_document(part)
    _select(window.editor, *occurrences[1])
    _show_preview(window, qtbot)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    assert _selection(view.preview) == _preview_occurrences(view, "meritum", PART_PARAGRAPH)[1]


def test_an_edition_selection_is_found_in_the_preview(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    text = window.editor.toPlainText()
    start, end = paragraph_spans(text)[2]
    _select(window.editor, *_occurrences_in(text, "premium", start, end)[1])
    view = _show_preview(window, qtbot)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    assert _selection(view.preview) == _preview_occurrences(view, "premium", 2)[1]


def test_a_part_position_scrolls_the_preview_to_its_line(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    view = _show_preview(window, qtbot)
    part = _doc(window, "rls185.xml")
    index = next(i for i, (path, _end) in enumerate(view.sources.lines) if Path(path).name == "rls185.xml") + 20
    window.left_tabs.setCurrentIndex(0)
    window.show_document(part)
    cursor = window.editor.textCursor()
    cursor.setPosition(view.sources.lines[index][1] + 2)
    window.editor.setTextCursor(cursor)
    _show_preview(window, qtbot)
    qtbot.wait(100)
    assert abs(view.current_preview_line() - index) <= 1


# --- Aperçu <-> éditeur de fragment ---------------------------------------------

def _fragment_occurrences(view, word):
    return [m.span() for m in re.finditer(_word(word), view.fragment_editor.toPlainText())]


def test_the_fragment_of_a_part_and_the_preview_share_their_selection(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    view = _show_preview(window, qtbot)
    assert view.load_fragment(PART_PARAGRAPH)
    _select(view.preview, *_preview_occurrences(view, "meritum", PART_PARAGRAPH)[1])
    view.preview.textSelected.emit()
    assert _selection(view.fragment_editor) == _fragment_occurrences(view, "meritum")[1]
    view.fragment_editor.setFocus()
    qtbot.waitUntil(view.fragment_editor.hasFocus, timeout=3000)
    view.preview.setTextCursor(QTextCursor(view.preview.document()))
    _select(view.fragment_editor, *_fragment_occurrences(view, "meritum")[0])
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=3000)
    assert _selection(view.preview) == _preview_occurrences(view, "meritum", PART_PARAGRAPH)[0]
