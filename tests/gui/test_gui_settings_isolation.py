# -*- coding: utf-8 -*-
"""Les tests ne modifient jamais les réglages réels de l'utilisateur."""
from __future__ import annotations

from PySide6.QtCore import QSettings


def _real_settings_snapshot():
    import app_context

    real = QSettings(app_context.SETTINGS_ORGANIZATION, app_context.SETTINGS_APPLICATION)
    return {key: real.value(key) for key in real.allKeys()}


def test_window_and_language_change_leave_real_settings_untouched(open_window, example_project):
    import app_context

    before = _real_settings_snapshot()
    window = open_window(example_project)
    window.language_actions["en"].trigger()
    window.update_recent_projects_menu()
    assert app_context._settings().value("startupLanguage") == "en"   # écrit… mais ailleurs
    assert _real_settings_snapshot() == before
