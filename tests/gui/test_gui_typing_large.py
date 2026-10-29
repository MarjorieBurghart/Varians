# -*- coding: utf-8 -*-
"""Red team 2 (robustesse) : la frappe dans un grand document.

- A2 : la gouttière recalculait le repliage de tout le document à chaque
  frappe (130 ms par Mo) : une frappe qui ne touche ni balise ni ligne garde
  ses repères ; une autre les décale, puis ils sont recalculés une fois,
  après une courte pause.
- A5 : chaque frappe relisait le texte entier une dizaine de fois, et, avec
  un caractère hors BMP (𝔄), reconstruisait autant de tables de positions
  UTF-16 : une seule lecture et une seule table par modification.
- A7 : une très longue ligne n'est colorée que sur ses 10 000 premiers
  caractères."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor, QTextDocument

import code_editor
from xml_folding import foldable_xml_regions

BODY = "".join(f"<div n=\"{i}\">\n  <p>Lorem ipsum et dolor {i}</p>\n  <p>Sed et uita</p>\n</div>\n"
               for i in range(400))
TEXT = f"<TEI>\n<text>\n<body>\n{BODY}</body>\n</text>\n</TEI>\n"


def _editor(qtbot, text=TEXT):
    editor = code_editor.CodeEditor()
    qtbot.addWidget(editor)
    document = QTextDocument(editor)
    editor.set_text_document(document)
    editor.setPlainText(text)
    editor.resize(600, 400)
    editor.show()
    qtbot.waitExposed(editor)
    return editor


def _place(editor, needle, offset=0):
    cursor = editor.textCursor()
    cursor.setPosition(editor.toPlainText().index(needle) + offset)
    editor.setTextCursor(cursor)


def _headers(editor):
    return {r.opening_line for r in foldable_xml_regions(editor.toPlainText())}


def _count(monkeypatch, module, name):
    calls = []
    original = getattr(module, name)

    def counted(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, counted)
    return calls


def test_typing_text_does_not_rescan_the_folds(qtbot, monkeypatch):
    editor = _editor(qtbot)
    editor.lineNumberArea.repaint()
    scans = _count(monkeypatch, code_editor, "foldable_xml_regions")
    _place(editor, "dolor 200", 5)
    for key in "abc":
        qtbot.keyClick(editor, key)
        editor.lineNumberArea.repaint()
    assert scans == []
    assert editor.fold_header_lines() == _headers(editor)


def test_after_a_structural_edit_the_folds_are_shifted_then_rescanned_once(qtbot, monkeypatch):
    editor = _editor(qtbot)
    before = editor.fold_header_lines()
    scans = _count(monkeypatch, code_editor, "foldable_xml_regions")
    _place(editor, '<div n="100">')
    line = editor.textCursor().blockNumber()
    qtbot.keyClick(editor, Qt.Key.Key_Return)
    editor.lineNumberArea.repaint()
    assert scans == []
    # Décalés d'une ligne en attendant : rien ne saute dans la gouttière.
    assert editor.fold_header_lines() == {n if n < line else n + 1 for n in before}
    qtbot.waitUntil(lambda: len(scans) == 1, timeout=3000)
    assert editor.fold_header_lines() == _headers(editor)
    # Une balise tapée : recalcul après la pause.
    _place(editor, "Sed et uita", 0)
    for key in "<b>":
        qtbot.keyClick(editor, key)
    qtbot.waitUntil(lambda: len(scans) == 2, timeout=3000)
    assert editor.fold_header_lines() == _headers(editor)


def test_folding_still_works_after_typing(qtbot):
    editor = _editor(qtbot)
    _place(editor, "dolor 3", 2)
    qtbot.keyClick(editor, "x")
    line = editor.toPlainText()[:editor.toPlainText().index('<div n="5">')].count("\n")
    assert editor.toggle_xml_fold(line)
    assert not editor.document().findBlockByNumber(line + 1).isVisible()
    editor.unfold_all_xml()


def test_the_text_is_read_once_per_change(qtbot, monkeypatch):
    editor = _editor(qtbot, TEXT.replace("Lorem", "𝔄 Lorem"))
    _place(editor, "dolor 200", 5)
    qtbot.wait(50)
    reads = _count(monkeypatch, code_editor, "raw_text")
    tables = _count(monkeypatch, code_editor, "Utf16Positions")
    for key in "abc":
        qtbot.keyClick(editor, key)
    qtbot.wait(50)
    assert len(reads) <= 3, len(reads)
    assert len(tables) <= 3, len(tables)
    assert editor.toPlainText() == editor.document().toRawText().replace(" ", "\n")


def test_the_snapshot_follows_every_change(qtbot):
    editor = _editor(qtbot, "<a>un</a>")
    assert editor.toPlainText() == "<a>un</a>"
    editor.setPlainText("<b>deux</b>")
    assert editor.toPlainText() == "<b>deux</b>"
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("!")
    assert editor.toPlainText() == "<b>deux</b>!"
    editor.document().undo()
    assert editor.toPlainText() == "<b>deux</b>"
    other = QTextDocument(editor)
    other.setPlainText("<c/>")
    editor.set_text_document(other)
    assert editor.toPlainText() == "<c/>"


def test_a_very_long_line_is_colored_on_its_first_ten_thousand_characters(qtbot):
    line = "<p>" + "<hi rend=\"b\">x</hi> " * 3000 + "</p>"
    editor = _editor(qtbot, line)
    highlighter = code_editor.XMLHighlighter(editor.document())
    highlighter.rehighlight()
    formats = editor.document().firstBlock().layout().formats()
    assert formats and max(f.start + f.length for f in formats) <= 10000
