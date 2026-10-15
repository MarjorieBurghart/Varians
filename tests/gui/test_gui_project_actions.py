# -*- coding: utf-8 -*-
"""Actions de projet dans la vraie fenêtre."""
from __future__ import annotations


def test_validating_project_settings_reloads_project_in_new_window(open_window, example_project, dialogs, qtbot):
    window = open_window(example_project)

    def accept(dialog):
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", accept)                 # Réglages du projet : OK
    dialogs.expect("information")                    # « Réglages enregistrés »
    window.project_settings_dialog()

    new_window = window._replacement_window
    try:
        assert type(new_window) is type(window)
        assert new_window.project.path == window.project.path
        assert new_window.current_path == window.current_path
        assert not window.isVisible()
    finally:
        if new_window is not None:
            new_window._force_close = True
            new_window.close()
