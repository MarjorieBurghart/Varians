# -*- coding: utf-8 -*-
"""Respecter la casse et expressions régulières (V0.9.2.8) : deux options
cochables du menu Rechercher, reprises par les boutons « Aa » et « .* » de
la barre d'outils et de la barre de recherche du fragment ; communes au
XML et au fragment, retenues d'une session à l'autre."""
from __future__ import annotations

from PySide6.QtWidgets import QToolButton


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _search_source(window, query):
    window.find_box.setText(query)
    window.find_source_next()
    return window.statusBar().currentMessage()


def test_the_options_are_in_the_menu_the_toolbar_and_the_fragment_bar(open_window, example_project):
    window = open_window(example_project)
    case, regex = window.action_search_case, window.action_search_regex
    entries = [action for action in window.search_menu.actions() if not action.isSeparator()]
    assert entries == [window.action_search, window.action_find_prev, window.action_find_next,
                       window.action_replace, case, regex, window.action_xpath_search]
    assert (case.text(), regex.text()) == (_tr("search.case"), _tr("search.regex"))
    assert case.isCheckable() and regex.isCheckable()
    assert not case.isChecked() and not regex.isChecked()
    toolbar = window.main_toolbar
    assert [toolbar.widgetForAction(action).text() for action in (case, regex)] == ["Aa", ".*"]
    assert toolbar.widgetForAction(case).toolTip() == _tr("search.case")
    buttons = window.formatted_view.fragment_find_bar.findChildren(QToolButton)
    assert {button.defaultAction() for button in buttons} >= {case, regex}


def test_the_simple_search_follows_the_options(open_window, example_project):
    window = open_window(example_project)
    window.editor.setPlainText("alpha BETA beta\n<rdg>betas</rdg>")
    found = lambda total: _tr("status.search.xml.found", n=1, total=total, query="beta")  # noqa: E731
    assert _search_source(window, "beta") == found(3)
    window.action_search_case.trigger()
    window.editor.moveCursor(window.editor.textCursor().MoveOperation.Start)
    assert _search_source(window, "beta") == found(2)
    window.action_search_case.trigger()
    window.action_search_regex.trigger()
    window.editor.moveCursor(window.editor.textCursor().MoveOperation.Start)
    message = _search_source(window, r"\bbeta\b")
    assert message == _tr("status.search.xml.found", n=1, total=2, query=r"\bbeta\b")
    # Une expression incorrecte est signalée, sans arrêter Varians.
    message = _search_source(window, "a(b")
    assert message.startswith(_tr("search.error.pattern", detail="")) and "missing )" in message


def test_the_fragment_search_follows_the_options(open_window, example_project):
    window = open_window(example_project)
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(1)
    view.fragment_editor.setPlainText("<p>Beta beta</p>")
    view.fragment_find_box.setText("beta")
    view.find_fragment_next()
    assert view.fragment_find_status.text() == "1/2"
    window.action_search_case.trigger()
    view.find_fragment_next()
    assert view.fragment_find_status.text() == "1/1"
    window.action_search_regex.trigger()
    view.fragment_find_box.setText("(b")
    view.find_fragment_next()
    assert view.fragment_find_status.text() == "!"
    assert window.statusBar().currentMessage().startswith(_tr("search.error.pattern", detail=""))


def test_the_options_are_remembered(open_window, example_project):
    window = open_window(example_project)
    window.action_search_regex.trigger()
    other = open_window(example_project)
    assert other.action_search_regex.isChecked() and not other.action_search_case.isChecked()
