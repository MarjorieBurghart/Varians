# -*- coding: utf-8 -*-
"""Chercher et remplacer (V0.9.2.8, Ctrl+H) : une barre sous l'éditeur XML,
une ligne « Remplacer par » sous la recherche du fragment. Remplacer
change l'occurrence surlignée puis passe à la suivante ; Tout remplacer
s'annule d'un seul Ctrl+Z."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication

TEXT = '<rdg wit="#A">regem</rdg>\n<rdg wit="#B">reges</rdg>'


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _focus(qtbot, window, widget):
    window.activateWindow()
    widget.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is widget, timeout=3000)


def _open_replace(window, find, replace):
    window.action_replace.trigger()
    window.replace_find_box.setText(find)
    window.replace_box.setText(replace)


def test_ctrl_h_opens_the_replace_bar_under_the_xml(open_window, example_project, qtbot):
    window = open_window(example_project)
    assert window.action_replace.shortcut().toString() == "Ctrl+H"
    assert window.action_replace.text() == _tr("search.replace")
    entries = [action for action in window.search_menu.actions() if not action.isSeparator()]
    assert entries.index(window.action_replace) == entries.index(window.action_search_list) + 1
    assert not window.replace_bar.isVisible()
    window.editor.setPlainText(TEXT)
    cursor = window.editor.textCursor()
    cursor.setPosition(1)
    cursor.setPosition(4, QTextCursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    _focus(qtbot, window, window.editor)
    window.action_replace.trigger()
    assert window.replace_bar.isVisible() and window.left_tabs.currentIndex() == 0
    # La sélection devient la recherche, partagée avec le champ de la barre d'outils.
    assert window.replace_find_box.text() == "rdg" and window.find_box.text() == "rdg"
    window.find_box.setText("reg")
    assert window.replace_find_box.text() == "reg"
    qtbot.keyClick(window.replace_find_box, Qt.Key.Key_Escape)
    assert not window.replace_bar.isVisible()


def test_replace_goes_step_by_step(open_window, example_project):
    window = open_window(example_project)
    window.editor.setPlainText(TEXT)
    _open_replace(window, "<rdg ", "<lem ")
    window.replace_one_button.click()                    # trouve la première
    assert window.editor.toPlainText() == TEXT and window.replace_status.text() == "1/2"
    window.replace_one_button.click()                    # la remplace, trouve la suivante
    assert window.editor.toPlainText() == TEXT.replace("<rdg ", "<lem ", 1)
    assert window.replace_status.text() == "1/1"
    window.replace_one_button.click()
    # Les fermetures ne sont pas touchées : on remplace ce qu'on a trouvé.
    assert window.editor.toPlainText() == TEXT.replace("<rdg ", "<lem ")
    assert window.replace_status.text() == "0/0"


def test_replace_all_is_undone_in_one_step(open_window, example_project):
    window = open_window(example_project)
    window.editor.setPlainText(TEXT)
    _open_replace(window, "rdg", "lem")
    window.replace_all_button.click()
    assert window.editor.toPlainText() == TEXT.replace("rdg", "lem")
    assert window.statusBar().currentMessage() == _tr("replace.done", count=4)
    window.editor.undo()
    assert window.editor.toPlainText() == TEXT


def test_replace_all_with_groups_and_errors(open_window, example_project):
    window = open_window(example_project)
    window.editor.setPlainText(TEXT)
    window.action_search_regex.trigger()
    _open_replace(window, r'wit="#(\w+)"', r"\2")
    window.replace_all_button.click()
    assert window.statusBar().currentMessage().startswith(_tr("replace.error.template", detail=""))
    assert window.editor.toPlainText() == TEXT
    window.replace_box.setText(r'wit="#\1 #T3"')
    window.replace_all_button.click()
    assert window.editor.toPlainText() == TEXT.replace('#A"', '#A #T3"').replace('#B"', '#B #T3"')
    window.replace_find_box.setText("a(b")
    window.replace_all_button.click()
    assert window.statusBar().currentMessage().startswith(_tr("search.error.pattern", detail=""))
    assert "#A #T3" in window.editor.toPlainText()


def test_ctrl_h_in_the_fragment_replaces_in_the_fragment(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = window.formatted_view
    original = window.editor.toPlainText()
    # Un fragment ouvert depuis l'aperçu.
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: len(view.preview.toPlainText()) > 1000, timeout=15000)
    assert view.load_fragment(2)
    view.fragment_editor.setPlainText("<p>beta Beta</p>")
    _focus(qtbot, window, view.fragment_editor)
    window.action_replace.trigger()
    assert view.fragment_find_bar.isVisible() and view.fragment_replace_row.isVisible()
    assert not window.replace_bar.isVisible()
    view.fragment_find_box.setText("beta")
    view.fragment_replace_box.setText("gamma")
    view.fragment_replace_all_button.click()
    assert view.fragment_editor.toPlainText() == "<p>gamma gamma</p>"
    assert window.editor.toPlainText() == original
    view.fragment_editor.undo()
    assert view.fragment_editor.toPlainText() == "<p>beta Beta</p>"
    view.fragment_replace_one_button.click()
    view.fragment_replace_one_button.click()
    assert view.fragment_editor.toPlainText() == "<p>gamma Beta</p>"
    # Ctrl+F ouvre la recherche seule.
    view.show_fragment_find()
    assert view.fragment_find_bar.isVisible() and not view.fragment_replace_row.isVisible()
