# -*- coding: utf-8 -*-
"""Menus « Éditer » et « Rechercher » (V0.9.2.8), juste après « Fichier ».
Les commandes d'édition agissent sur le champ qui a le focus (XML,
fragment, un champ de texte), sinon sur le XML ; la barre d'outils garde
ses boutons (Indenter, XPath, recherche)."""
from __future__ import annotations

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _entries(menu):
    return [(action.text(), action.shortcut().toString()) for action in menu.actions() if not action.isSeparator()]


def _choose(window, action):
    """Comme un clic dans le menu : le menu s'ouvre (et met à jour ses
    commandes), puis la commande est choisie."""
    window.edit_menu.aboutToShow.emit()
    assert action.isEnabled(), action.text()
    action.trigger()


def _focus(qtbot, window, widget):
    window.activateWindow()
    widget.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is widget, timeout=3000)


def test_the_edit_and_search_menus_follow_the_file_menu(open_window, example_project):
    window = open_window(example_project)
    toolbar = window.main_toolbar
    buttons = [toolbar.widgetForAction(action) for action in toolbar.actions()[:5]]
    assert [button.text() for button in buttons] == [_tr("menu.file"), _tr("menu.edit"), _tr("menu.search"),
                                                     _tr("menu.display"), _tr("menu.help")]
    assert buttons[1].menu() is window.edit_menu and buttons[2].menu() is window.search_menu
    assert _entries(window.edit_menu) == [
        (_tr("edit.undo"), "Ctrl+Z"), (_tr("edit.redo"), "Ctrl+Y"),
        (_tr("edit.cut"), "Ctrl+X"), (_tr("edit.copy"), "Ctrl+C"), (_tr("edit.paste"), "Ctrl+V"),
        (_tr("edit.select_all"), "Ctrl+A"), (_tr("edit.format_xml"), ""),
    ]
    assert window.action_format_xml in window.edit_menu.actions()
    assert _entries(window.search_menu) == [
        (_tr("search.find"), "Ctrl+F"), (_tr("search.previous"), "Shift+F3"), (_tr("search.next"), "F3"),
        (_tr("search.case"), ""), (_tr("search.regex"), ""), (_tr("search.xpath"), "Ctrl+Shift+F"),
    ]
    # La barre d'outils garde ses boutons et leurs libellés courts.
    for action, key in ((window.action_format_xml, "toolbar.format_xml"), (window.action_xpath_search, "xpath.action"),
                        (window.action_search, "toolbar.search"), (window.action_find_next, "toolbar.next")):
        assert toolbar.widgetForAction(action).text() == _tr(key)


def test_the_edit_commands_act_on_the_focused_field(open_window, example_project, qtbot):
    window = open_window(example_project)
    editor = window.editor
    original = editor.toPlainText()
    cursor = editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("<!-- essai -->")
    _focus(qtbot, window, editor)
    _choose(window, window.action_undo)
    assert editor.toPlainText() == original
    _choose(window, window.action_redo)
    assert editor.toPlainText().endswith("<!-- essai -->")
    # Le focus hors d'un champ de texte : les commandes vont au XML.
    _focus(qtbot, window, window.left_tabs.tabBar())
    _choose(window, window.action_undo)
    assert editor.toPlainText() == original

    # Dans un champ de texte : Sélectionner tout, Copier, Couper, Coller.
    box = window.find_box
    box.setText("magnates")
    box.deselect()
    _focus(qtbot, window, box)
    window.edit_menu.aboutToShow.emit()
    assert not window.action_copy.isEnabled() and not window.action_cut.isEnabled()
    _choose(window, window.action_select_all)
    assert box.selectedText() == "magnates"
    _choose(window, window.action_copy)
    assert QApplication.clipboard().text() == "magnates"
    _choose(window, window.action_cut)
    assert box.text() == ""
    _choose(window, window.action_paste)
    assert box.text() == "magnates"
    assert editor.toPlainText() == original

    # Dans le fragment.
    window.left_tabs.setCurrentIndex(1)
    fragment = window.formatted_view.fragment_editor
    fragment.setPlainText("<p>abc</p>")
    _focus(qtbot, window, fragment)
    _choose(window, window.action_select_all)
    _choose(window, window.action_copy)
    assert QApplication.clipboard().text() == "<p>abc</p>"


def test_the_new_menus_are_translated(open_window, example_project):
    from app_context import current_i18n
    window = open_window(example_project)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert (window.edit_menu_button.text(), window.search_menu_button.text()) == ("Edit", "Search")
    assert window.edit_menu.title() == "Edit" and window.action_undo.text() == "Undo"
    assert window.action_format_xml.text() == current_i18n().tr("edit.format_xml")
    assert window.main_toolbar.widgetForAction(window.action_format_xml).text() == "Indent"
