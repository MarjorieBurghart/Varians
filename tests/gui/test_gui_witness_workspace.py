# -*- coding: utf-8 -*-
"""Disposition des panneaux de témoins dans la vraie fenêtre."""
from __future__ import annotations

from PySide6.QtCore import Qt


def test_hide_a_witness_through_visibility_dialog(open_window, example_project, dialogs):
    window = open_window(example_project)
    assert set(window._visible_witness_ids) == {"T1", "T2", "P"}

    def uncheck_p(dialog):
        for i in range(dialog.list.count()):
            item = dialog.list.item(i)
            if item.data(Qt.ItemDataRole.UserRole) == "P":
                item.setCheckState(Qt.CheckState.Unchecked)
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", uncheck_p)
    window.choose_visible_witnesses()
    assert "P" not in window._visible_witness_ids
    assert not window.panels["P"].isVisible()
    assert window.panels["T1"].isVisible()


def test_detach_and_dock_witness_keeps_the_same_panel(open_window, example_project, qtbot):
    window = open_window(example_project)
    panel = window.panels["T2"]
    assert window._detach_witness("T2") is True
    detached = window._detached_windows["T2"]
    assert panel.window() is detached
    assert window._dock_witness("T2") is True
    assert "T2" not in window._detached_windows
    assert panel.window() is window
    assert panel.isVisible()


def test_workspace_mode_switch_and_back(open_window, example_project):
    window = open_window(example_project)
    start = window._workspace_mode
    other = "grid" if start != "grid" else "vertical"
    window._set_workspace_mode(other, persist=False)
    assert window._workspace_mode == other
    assert all(window.panels[w].isVisible() for w in window._visible_witness_ids)
    window._set_workspace_mode(start, persist=False)
    assert window._workspace_mode == start


def test_maximize_one_witness_then_restore(open_window, example_project):
    window = open_window(example_project)
    window._toggle_witness_panel_maximize("T1")
    assert window._witness_maximized_id == "T1"
    window._toggle_witness_panel_maximize("T1")
    assert window._witness_maximized_id is None
