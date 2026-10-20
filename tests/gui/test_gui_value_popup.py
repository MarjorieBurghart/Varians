# -*- coding: utf-8 -*-
"""Liste automatique des pointeurs : taper « # » dans un attribut de référence
(@ref, @wit…) ouvre la liste des identifiants, sans Ctrl+Espace."""
from __future__ import annotations

from PySide6.QtCore import Qt


def _cursor_inside(window, markup, inside):
    text = window.editor.toPlainText()
    position = text.index("<body>") + len("<body>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)
    cursor = window.editor.textCursor()
    cursor.setPosition(position + markup.index(inside) + len(inside))
    window.editor.setTextCursor(cursor)
    window.editor.setFocus()


def _popup_values(window):
    model = window.editor._value_completer.completionModel()
    return [model.index(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(model.rowCount())]


def _popup_texts(window):
    model = window.editor._value_completer.completionModel()
    return [model.index(row, 0).data() for row in range(model.rowCount())]


def _popup_visible(window):
    return window.editor._value_completer.popup().isVisible()


def test_typing_a_hash_in_a_reference_opens_the_identifier_list(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    _cursor_inside(window, '<persName ref=""></persName>', 'ref="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_visible(window)
    assert _popup_values(window) == ["#bernard", "#petrus"]
    assert any("Bernardus" in text for text in _popup_texts(window))

    qtbot.keyClicks(window.editor, "be")
    assert _popup_values(window) == ["#bernard"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert not _popup_visible(window)
    assert '<persName ref="#bernard"></persName>' in window.editor.toPlainText()


def test_typing_a_hash_in_rdg_wit_lists_the_witnesses(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<app><rdg wit=""></rdg></app>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_values(window) == ["#T1", "#T2", "#P"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Tab)
    assert '<rdg wit="#T1">' in window.editor.toPlainText()

    qtbot.keyClicks(window.editor, " #")                     # second pointeur de la liste
    assert _popup_values(window) == ["#T2", "#P"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert '<rdg wit="#T1 #T2">' in window.editor.toPlainText()


def test_escape_closes_the_list(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<lem wit=""></lem>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_visible(window)
    qtbot.keyClick(window.editor, Qt.Key.Key_Escape)
    assert not _popup_visible(window)
    assert '<lem wit="#">' in window.editor.toPlainText()


def test_other_attributes_open_nothing(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, '<hi rend=""></hi>', 'rend="')
    qtbot.keyClicks(window.editor, "#i")
    assert not _popup_visible(window)


def test_attribute_name_popup_is_not_disturbed(open_window, example_project, qtbot):
    window = open_window(example_project)
    _cursor_inside(window, "<varianstest ></varianstest>", "<varianstest ")
    qtbot.keyClicks(window.editor, "k")
    assert window.editor._attribute_completer.popup().isVisible()
    assert not _popup_visible(window)


def test_an_ambiguous_identifier_is_listed_in_its_qualified_form(open_window, project_with_documents, qtbot):
    from project_config import DocumentConfig, load_project
    from project_management import update_project_documents

    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text('<listPlace><place xml:id="petrus"/></listPlace>', encoding="utf-8")
    documents = list(load_project(project_with_documents).documents) + [DocumentConfig(lieux, "Lieux")]
    update_project_documents(project_with_documents, documents)
    window = open_window(project_with_documents)
    _cursor_inside(window, '<persName ref=""></persName>', 'ref="')
    qtbot.keyClicks(window.editor, "#")
    assert _popup_values(window) == ["#bernard", "personnes.xml#petrus"]
    qtbot.keyClicks(window.editor, "pe")                     # « #pe » trouve la forme qualifiée
    assert _popup_values(window) == ["personnes.xml#petrus"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert '<persName ref="personnes.xml#petrus"></persName>' in window.editor.toPlainText()
