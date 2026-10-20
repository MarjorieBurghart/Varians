# -*- coding: utf-8 -*-
"""Appels différés visant une fenêtre détruite entre-temps."""
from __future__ import annotations

from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, QThreadPool


def test_call_later_runs_callback_while_owner_exists(qtbot):
    from app_context import call_later

    owner = QObject()
    calls = []
    call_later(10, owner, lambda: calls.append("appelé"))
    qtbot.wait(60)
    assert calls == ["appelé"]


def test_call_later_skips_callback_once_owner_is_destroyed(qtbot):
    from app_context import call_later

    owner = QObject()
    calls = []
    call_later(10, owner, lambda: calls.append("appelé"))
    shiboken6.delete(owner)
    qtbot.wait(60)
    assert calls == []


def test_window_destroyed_right_after_opening_a_document(qtbot, editor_module, example_project, dialogs):
    """open_path programme une synchronisation (50 ms) et une validation
    (120 ms). En V0.8.5.26.2, elles s'exécutaient sur la fenêtre détruite et
    levaient « Internal C++ object … already deleted » (pytest-qt fait alors
    échouer le test)."""
    window = editor_module.MainWindow(Path(example_project))
    window.show()
    qtbot.wait(10)                                   # minuteries immédiates du démarrage
    window.open_path(window.current_path)            # reprogramme les appels à 50 et 120 ms
    window._force_close = True
    window.close()
    QThreadPool.globalInstance().waitForDone(5000)
    shiboken6.delete(window)
    qtbot.wait(300)
