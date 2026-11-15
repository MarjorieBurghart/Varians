# -*- coding: utf-8 -*-
"""Contrôle de bonne formation encore en cours quand la fenêtre est détruite
(V0.9.4.7).

Le contrôle tourne hors du fil de la fenêtre (``xml_health.XmlHealthWorker``)
et rend son résultat par un signal. Si la fenêtre est fermée puis détruite
pendant qu'il tourne, le résultat ne doit jamais lui parvenir : son éditeur
n'existe plus. C'est le cas tant que le slot qui le reçoit,
``_async_xml_health_finished``, est défini dans ``MainWindow`` même : PySide
lie alors la connexion à la fenêtre et l'oublie à sa destruction. Défini dans
un mixin, il ne le fait pas (vu sous Windows en CI lors du découpage de la
fenêtre)."""
from __future__ import annotations

import time
from pathlib import Path

import xml_health


def test_a_check_still_running_never_reaches_a_destroyed_window(qtbot, editor_module, example_project,
                                                                 dialogs, monkeypatch):
    original = xml_health.XmlHealthWorker.run

    def slow(self):
        time.sleep(1.0)
        return original(self)

    monkeypatch.setattr(xml_health.XmlHealthWorker, "run", slow)
    window = editor_module.MainWindow(Path(example_project))
    window.show()
    qtbot.waitExposed(window)
    window.editor.insertPlainText("<!-- brouillon -->")
    window._force_close = True
    window.close()
    # La minuterie de frappe (650 ms) lance le contrôle, fenêtre fermée.
    qtbot.waitUntil(lambda: window._xml_health_running, timeout=5000)
    destroyed = []
    window.destroyed.connect(lambda *_: destroyed.append(True))
    window.deleteLater()
    qtbot.waitUntil(lambda: bool(destroyed), timeout=10000)
    # Le contrôle se termine après la destruction ; son résultat ne doit
    # rien appeler sur la fenêtre (pytest-qt ferait échouer le test).
    qtbot.wait(1500)
