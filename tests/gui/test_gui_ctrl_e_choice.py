# -*- coding: utf-8 -*-
"""Choix de l'élément de Ctrl+E (V0.9.2.8.1) : une entrée de la liste n'est
surlignée que si elle est réellement sélectionnée ; Entrée insère l'entrée
sélectionnée, sinon le texte saisi. Tab ou ↓ depuis le champ sélectionne
la première entrée ; retaper dans le champ efface la sélection.
Ctrl+Espace (sans texte libre) garde la première entrée présélectionnée."""
from __future__ import annotations

import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

ITEMS = [("persName", "rng"), ("person", "rng"), ("placeName", "custom")]


@pytest.fixture
def ctrl_e(qtbot, editor_module):
    from completion_ui import CompletionDialog          # catalogue installé par editor_module

    def make(items=ITEMS, allow_custom=True):
        dialog = CompletionDialog("Ctrl+E", "Élément", items, "", allow_custom=allow_custom)
        qtbot.addWidget(dialog)
        dialog.show()
        qtbot.waitExposed(dialog)
        dialog.activateWindow()
        dialog.filter_box.setFocus()
        return dialog

    return make


def _selected(dialog):
    return [item.data(Qt.ItemDataRole.UserRole) for item in dialog.list_widget.selectedItems()]


def test_nothing_is_highlighted_until_an_entry_is_chosen(ctrl_e):
    dialog = ctrl_e()
    assert dialog.list_widget.count() == 3 and _selected(dialog) == []
    QTest.keyClicks(dialog.filter_box, "pers")
    assert dialog.list_widget.count() == 2 and _selected(dialog) == []
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Return)
    assert dialog.result() == dialog.DialogCode.Accepted and dialog.selected_value == "pers"


def test_tab_selects_the_first_entry_and_enter_inserts_it(ctrl_e):
    dialog = ctrl_e()
    QTest.keyClicks(dialog.filter_box, "pers")
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Tab)
    assert dialog.focusWidget() is dialog.list_widget and _selected(dialog) == ["persName"]
    QTest.keyClick(dialog.list_widget, Qt.Key.Key_Return)
    assert dialog.result() == dialog.DialogCode.Accepted and dialog.selected_value == "persName"


def test_down_selects_the_first_entry_then_the_next(ctrl_e):
    dialog = ctrl_e()
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Down)
    assert dialog.focusWidget() is dialog.list_widget and _selected(dialog) == ["persName"]
    QTest.keyClick(dialog.list_widget, Qt.Key.Key_Down)
    assert _selected(dialog) == ["person"]
    QTest.keyClick(dialog.list_widget, Qt.Key.Key_Return)
    assert dialog.selected_value == "person"


def test_typing_again_clears_the_selection(ctrl_e):
    dialog = ctrl_e()
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Down)
    assert _selected(dialog) == ["persName"]
    dialog.filter_box.setFocus()
    QTest.keyClicks(dialog.filter_box, "p")
    assert _selected(dialog) == []
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Return)
    assert dialog.selected_value == "p"


def test_a_clicked_entry_is_inserted_even_from_the_field(ctrl_e):
    dialog = ctrl_e()
    QTest.keyClicks(dialog.filter_box, "p")
    rect = dialog.list_widget.visualItemRect(dialog.list_widget.item(2))
    QTest.mouseClick(dialog.list_widget.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    assert _selected(dialog) == ["placeName"]
    # Le focus revient au champ sans rien taper : l'entrée surlignée reste choisie.
    dialog.filter_box.setFocus()
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Return)
    assert dialog.selected_value == "placeName"


def test_ctrl_space_keeps_the_first_entry_preselected(ctrl_e):
    dialog = ctrl_e(allow_custom=False)
    assert _selected(dialog) == ["persName"]
    QTest.keyClicks(dialog.filter_box, "pla")
    QTest.keyClick(dialog.filter_box, Qt.Key.Key_Return)
    assert dialog.selected_value == "placeName"


def test_ctrl_e_in_the_xml_wraps_with_the_chosen_entry_or_the_typed_text(open_window, example_project, dialogs):
    """Dans la fenêtre : texte saisi sans entrée choisie, puis première
    entrée de la liste choisie par ↓."""
    window = open_window(example_project)
    editor = window.editor

    def select(word):
        text = editor.toPlainText()
        start = text.index(word, text.index("<body>"))
        cursor = editor.textCursor()
        cursor.setPosition(start)
        cursor.setPosition(start + len(word), cursor.MoveMode.KeepAnchor)
        editor.setTextCursor(cursor)

    def typed_only(dialog):
        dialog.show()
        QTest.keyClicks(dialog.filter_box, "hi")
        QTest.keyClick(dialog.filter_box, Qt.Key.Key_Return)
        return dialog.result()

    def chosen(dialog):
        dialog.show()
        assert dialog.list_widget.selectedItems() == []
        QTest.keyClick(dialog.filter_box, Qt.Key.Key_Down)
        first = dialog.list_widget.selectedItems()[0].data(Qt.ItemDataRole.UserRole)
        seen.append(first)
        QTest.keyClick(dialog.list_widget, Qt.Key.Key_Return)
        return dialog.result()

    seen = []
    word = "Troyes"
    select(word)
    dialogs.expect("dialog", typed_only)
    window.source_wrap_element_action.trigger()
    assert f"<hi>{word}</hi>" in editor.toPlainText()
    editor.undo()
    select(word)
    dialogs.expect("dialog", chosen)
    window.source_wrap_element_action.trigger()
    assert seen
    # Avec les attributs que custom-elements.xml lui donne.
    assert re.search(rf"<{seen[0]}\b[^>]*>{word}</{seen[0]}>", editor.toPlainText())
