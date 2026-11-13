# -*- coding: utf-8 -*-
"""Le journal des erreurs dans la fenêtre (V0.9.4.6) : ouvert au démarrage,
message de la barre d'état après une erreur inattendue, entrée « Journal des
erreurs » du menu Aide, qui ouvre son dossier (pour l'envoyer avec un
signalement)."""
from __future__ import annotations

import sys

import pytest
from PySide6 import QtCore

import error_log
import error_log_ui
from app_context import APP_VERSION, tr


@pytest.fixture
def journal_folder(tmp_path, monkeypatch):
    """Dossier du journal propre au test ; le journal est refermé à la fin,
    les crochets d'exceptions rendus."""
    folder = tmp_path / "journal"
    monkeypatch.setenv(error_log.ENVIRONMENT, str(folder))
    monkeypatch.setattr(sys, "excepthook", lambda *args: None)          # sans le crochet de pytest-qt
    error_log.uninstall()
    yield folder
    error_log.uninstall()


@pytest.fixture
def opened(monkeypatch):
    """Adresses que Varians demande au système d'ouvrir."""
    urls = []
    monkeypatch.setattr(error_log_ui.QDesktopServices, "openUrl", lambda url: urls.append(url) or True)
    return urls


def test_the_journal_opens_at_startup_with_the_versions(journal_folder):
    path = error_log_ui.install_for_application()
    assert path == journal_folder / error_log.FILE_NAME
    header = path.read_text(encoding="utf-8")
    assert f"Varians {APP_VERSION}" in header and f"Qt {QtCore.qVersion()}" in header


def test_main_opens_the_journal():
    from varians_source import application_source
    import editeur_tei
    assert "error_log_ui.install_for_application()" in application_source()
    assert {"error_log", "error_log_ui"} <= editeur_tei._LOCAL_MODULE_NAMES


def test_an_unexpected_error_is_said_in_the_status_bar(journal_folder, open_window, sermons_project):
    window = open_window(sermons_project)
    error_log_ui.install_for_application()
    sys.excepthook(ValueError, ValueError("inattendue"), None)
    assert window.statusBar().currentMessage() == tr("error_log.unexpected")
    assert "ValueError: inattendue" in (journal_folder / error_log.FILE_NAME).read_text(encoding="utf-8")


def test_the_help_menu_opens_the_folder_of_the_journal(journal_folder, opened, open_window, sermons_project):
    window = open_window(sermons_project)
    actions = window.help_menu.actions()
    assert actions.index(window.action_error_log) == actions.index(window.action_software_help) + 1
    assert window.action_error_log.text() == tr("help.error_log")
    assert window.action_error_log.toolTip() == tr("help.error_log.tip")
    window.action_error_log.trigger()
    assert [url.toLocalFile() for url in opened] == [str(journal_folder)]
    assert journal_folder.is_dir()                                         # créé s'il manquait


def test_the_welcome_window_has_the_entry_too(journal_folder, opened, editor_module, qtbot):
    window = editor_module.WelcomeWindow()
    qtbot.addWidget(window)
    actions = window.help_menu.actions()
    assert actions.index(window.action_error_log) == actions.index(window.action_software_help) + 1
    window.action_error_log.trigger()
    assert [url.toLocalFile() for url in opened] == [str(journal_folder)]


def test_a_folder_that_cannot_be_made_is_said(journal_folder, opened, open_window, sermons_project, dialogs,
                                              monkeypatch, tmp_path):
    blocked = tmp_path / "fichier"
    blocked.write_text("pas un dossier", encoding="utf-8")
    monkeypatch.setenv(error_log.ENVIRONMENT, str(blocked / "journal"))
    window = open_window(sermons_project)
    dialogs.expect("warning")
    window.action_error_log.trigger()
    kind, title, text = dialogs.seen[-1]
    assert (kind, title) == ("warning", tr("help.error_log"))
    assert text == tr("error_log.unavailable", folder=str(blocked / "journal"))
    assert opened == []


def test_the_entry_follows_the_language(journal_folder, open_window, sermons_project):
    from app_context import current_i18n
    window = open_window(sermons_project)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert window.action_error_log.text() == current_i18n().tr("help.error_log") == "Error Log"
    assert window.action_error_log.toolTip() == current_i18n().tr("help.error_log.tip")
