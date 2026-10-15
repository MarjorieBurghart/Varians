# -*- coding: utf-8 -*-
"""Menus, aide, « À propos », langue et projets récents dans la vraie fenêtre."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QLabel, QTextBrowser


def _texts(widget, kind):
    return [w.text() if kind is QLabel else w.toPlainText() for w in widget.findChildren(kind)]


def test_about_dialog_shows_version(open_window, example_project, dialogs):
    from app_context import APP_VERSION

    window = open_window(example_project)
    seen = []
    dialogs.expect("dialog", lambda dialog: seen.extend(_texts(dialog, QLabel)) or 0)
    window.action_about.trigger()
    assert any(APP_VERSION in text for text in seen)


def test_software_help_opens_localized_help(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = []
    dialogs.expect("dialog", lambda dialog: seen.extend(_texts(dialog, QTextBrowser)) or 0)
    window.action_software_help.trigger()
    assert seen and len(seen[0]) > 1000                 # help/fr.html chargé


def test_switching_language_retranslates_menus(open_window, example_project):
    from app_context import current_i18n

    window = open_window(example_project)
    assert current_i18n().language == "fr"
    french = window.file_menu_button.text()
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    english = window.file_menu_button.text()
    assert english != french
    assert english == current_i18n().tr("menu.file")


def test_recent_projects_menu_lists_open_project(open_window, example_project):
    window = open_window(example_project)
    window.update_recent_projects_menu()
    tips = [action.toolTip() for action in window.recent_menu.actions()]
    assert str(Path(example_project).resolve()) in tips
