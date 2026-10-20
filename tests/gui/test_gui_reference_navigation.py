# -*- coding: utf-8 -*-
"""Aller de la référence à sa cible (F12, Ctrl+clic, menu) et revenir (Alt+←)."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QContextMenuEvent
from PySide6.QtWidgets import QApplication, QMenu

from app_context import tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents


def _insert_in_body(window, markup, inside):
    text = window.editor.toPlainText()
    position = text.index("<body>") + len("<body>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)
    target = position + markup.index(inside) + len(inside)
    cursor = window.editor.textCursor()
    cursor.setPosition(target)
    window.editor.setTextCursor(cursor)
    return target


def _aux(window):
    return window.documents[1]


def test_f12_shows_the_target_in_the_authority_file_and_alt_left_comes_back(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    start = _insert_in_body(window, '<persName ref="personnes.xml#bernard">B</persName>', 'ref="personnes.xml#ber')
    assert window.action_go_to_reference.shortcut().toString() == "F12"
    assert window.action_reference_back.shortcut().toString() == "Alt+Left"

    window.action_go_to_reference.trigger()
    assert window.document is _aux(window)
    assert window.editor.textCursor().selectedText() == '<person xml:id="bernard">'
    qtbot.wait(20)                                           # défilement différé
    assert window.editor.textCursor().selectedText() == '<person xml:id="bernard">'

    window.action_reference_back.trigger()
    assert window.document is window.edition_session
    assert window.editor.textCursor().position() == start


def test_ctrl_click_on_a_reference_goes_to_its_target(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    target = _insert_in_body(window, '<persName ref="personnes.xml#petrus">P</persName>', 'ref="personnes.xml#pe')
    cursor = window.editor.textCursor()
    cursor.setPosition(target)
    point = window.editor.cursorRect(cursor).center()
    qtbot.mouseClick(window.editor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.ControlModifier, point)
    assert window.document is _aux(window)
    assert window.editor.textCursor().selectedText() == '<person xml:id="petrus">'


def test_plain_click_does_not_navigate(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    target = _insert_in_body(window, '<persName ref="#petrus">P</persName>', 'ref="#pe')
    cursor = window.editor.textCursor()
    cursor.setPosition(target)
    qtbot.mouseClick(window.editor.viewport(), Qt.MouseButton.LeftButton,
                     Qt.KeyboardModifier.NoModifier, window.editor.cursorRect(cursor).center())
    assert window.document is window.edition_session


def test_missing_target_leaves_the_document_and_says_so(open_window, project_with_documents):
    window = open_window(project_with_documents)
    _insert_in_body(window, '<persName ref="#absent">A</persName>', 'ref="#ab')
    assert not window.go_to_reference()
    assert window.document is window.edition_session
    assert window.statusBar().currentMessage() == tr("references.missing", token="#absent")


def test_nothing_happens_outside_a_reference(open_window, project_with_documents):
    window = open_window(project_with_documents)
    _insert_in_body(window, '<persName ref="#bernard">Bernardus</persName>', 'Bern')
    assert not window.go_to_reference()
    assert window.statusBar().currentMessage() == tr("references.none_here")


def test_short_form_pointing_elsewhere_still_leads_to_the_target_and_gives_the_tei_form(
        open_window, project_with_documents):
    # « #bernard » ne désigne que l'édition : Varians mène tout de même à la
    # cible trouvée dans personnes.xml et indique la forme à écrire.
    window = open_window(project_with_documents)
    _insert_in_body(window, '<persName ref="#bernard">B</persName>', 'ref="#ber')
    assert window.go_to_reference()
    assert window.document is _aux(window)
    assert window.editor.textCursor().selectedText() == '<person xml:id="bernard">'
    assert window.statusBar().currentMessage() == tr(
        "references.other_document", token="#bernard", suggestion="personnes.xml#bernard")


def test_short_form_found_in_two_other_documents_asks_which_target(open_window, project_with_documents, dialogs):
    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text('<listPlace><place xml:id="petrus"/></listPlace>', encoding="utf-8")
    documents = list(load_project(project_with_documents).documents) + [DocumentConfig(lieux, "Lieux")]
    update_project_documents(project_with_documents, documents)
    window = open_window(project_with_documents)
    _insert_in_body(window, '<persName ref="#petrus">P</persName>', 'ref="#pe')
    choices = []

    def choose_second(dialog):
        choices.extend(dialog.list_widget.item(i).text() for i in range(dialog.list_widget.count()))
        dialog.list_widget.setCurrentRow(1)
        dialog._accept_current()
        return dialog.result()

    dialogs.expect("dialog", choose_second)
    assert window.go_to_reference()
    assert len(choices) == 2 and "lieux.xml" in choices[1]
    assert window.document is window.documents[2]
    assert window.editor.textCursor().selectedText() == '<place xml:id="petrus"/>'
    assert window.statusBar().currentMessage() == tr(
        "references.other_document", token="#petrus", suggestion="lieux.xml#petrus")


def test_pointer_to_the_document_itself(open_window, example_project):
    window = open_window(example_project)
    text = window.editor.toPlainText()
    position = text.index('edRef="#T1"') + len('edRef="#T')
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    assert window.go_to_reference()
    assert window.document is window.edition_session
    assert window.editor.textCursor().selectedText().startswith('<witness xml:id="T1"')


def test_context_menu_offers_go_to_target_on_a_reference(open_window, project_with_documents):
    window = open_window(project_with_documents)
    on_reference = _insert_in_body(window, '<persName ref="#bernard">B</persName>', 'ref="#ber')
    menu = QMenu(window)
    window._reference_context_menu(menu, on_reference)
    actions = [action for action in menu.actions() if not action.isSeparator()]
    assert actions and actions[0].text() == tr("references.goto")
    assert actions[0].isEnabled()

    elsewhere = QMenu(window)
    window._reference_context_menu(elsewhere, 0)
    assert not [a for a in elsewhere.actions() if a.text() == tr("references.goto") and a.isEnabled()]


def test_right_click_uses_the_clicked_position(open_window, project_with_documents):
    window = open_window(project_with_documents)
    start = _insert_in_body(window, '<persName ref="personnes.xml#bernard">B</persName>', '<persName')
    cursor = window.editor.textCursor()
    cursor.setPosition(start + len(' ref="personnes.xml#be'))                  # le curseur reste hors de la valeur
    point = window.editor.cursorRect(cursor).center()
    event = QContextMenuEvent(QContextMenuEvent.Reason.Mouse, point,
                              window.editor.viewport().mapToGlobal(point))
    QApplication.sendEvent(window.editor.viewport(), event)
    menu = QApplication.activePopupWidget()
    try:
        goto = menu.actions()[0]
        assert goto.text() == tr("references.goto") and goto.isEnabled()
        goto.trigger()
    finally:
        menu.close()
    assert window.document is _aux(window)
    assert window.editor.textCursor().selectedText() == '<person xml:id="bernard">'
