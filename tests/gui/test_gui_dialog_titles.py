# -*- coding: utf-8 -*-
"""Les boîtes « Nouveau projet… » et « Paramètres du projet… » portent la
version courante de Varians dans leur titre (elles affichaient encore
« Varians 0.8.5.10 »)."""
from __future__ import annotations

from pathlib import Path

import app_context
from app_context import APP_VERSION
from i18n import I18nManager
from project_config import load_project

ROOT = Path(__file__).resolve().parents[2]


def test_project_dialogs_show_the_current_version(qapp, example_project):
    from project_dialogs import NewProjectDialog, ProjectSettingsDialog
    previous = app_context.current_i18n()
    manager = I18nManager(ROOT / "i18n", "fr", "en")
    app_context.set_i18n(manager)
    try:
        tr = manager.tr
        languages = [("fr", "Français")]
        dialogs = [NewProjectDialog(tr, languages),
                   ProjectSettingsDialog(tr, load_project(example_project), languages)]
        titles = [dialog.windowTitle() for dialog in dialogs]
        for dialog in dialogs:
            dialog.deleteLater()
    finally:
        app_context.set_i18n(previous)
    assert titles == [f'{tr("project.new.title")} — Varians {APP_VERSION}',
                      f'{tr("project.settings.title")} — Varians {APP_VERSION}']
