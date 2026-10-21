# -*- coding: utf-8 -*-
"""Indicateur d'attente de la barre d'état : une lueur parcourt un petit cercle
tant qu'une validation RELAX NG est en cours dans le processus séparé."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

import validation_worker
from app_context import tr
from busy_indicator import BusyIndicator
from validation_worker import RelaxNGWorkerClient

SLOW_WORKER = Path(__file__).with_name("slow_relaxng_worker.py")


@pytest.fixture
def slow_worker(monkeypatch):
    clients = []

    def _use(delay):
        client = RelaxNGWorkerClient([sys.executable, str(SLOW_WORKER), str(delay)])
        clients.append(client)
        monkeypatch.setattr(validation_worker, "_client", client)
        return client

    yield _use
    for client in clients:
        client.shutdown()


def test_the_indicator_turns_only_while_started(qtbot):
    indicator = BusyIndicator()
    qtbot.addWidget(indicator)
    assert indicator.isHidden() and not indicator.is_running()
    indicator.start()
    assert not indicator.isHidden() and indicator.is_running()
    first = indicator.angle
    qtbot.wait(200)
    assert indicator.angle != first                                   # la lueur avance
    image = indicator.grab().toImage()
    qtbot.wait(100)
    assert indicator.grab().toImage() != image                        # et se redessine
    indicator.stop()
    assert indicator.isHidden() and not indicator.is_running()


def test_the_indicator_shows_during_the_opening_validation(open_window, example_project, slow_worker, qtbot):
    client = slow_worker(1.0)
    window = open_window(example_project, wait_validation=False)
    assert client.busy
    assert window.rng_busy.is_running() and not window.rng_busy.isHidden()
    assert window.rng_status.text() == tr("rng.status.running")
    assert window.rng_busy.x() < window.rng_status.x()               # juste avant « RNG »
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    assert not window.rng_busy.is_running() and window.rng_busy.isHidden()
    assert window.rng_status.text() == tr("rng.status.valid")


def test_the_indicator_stops_after_an_invalid_result(open_window, example_project, slow_worker):
    slow_worker(0.3)
    window = open_window(example_project)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("\n<forbidden/>")
    window.validate_relaxng_manual()
    assert not window._last_rng_result.valid
    assert not window.rng_busy.is_running() and window.rng_busy.isHidden()


def test_no_indicator_when_validation_falls_back_to_varians(open_window, example_project, monkeypatch, tmp_path):
    client = RelaxNGWorkerClient([str(tmp_path / "absent")])
    monkeypatch.setattr(validation_worker, "_client", client)
    window = open_window(example_project)
    assert not client.uses_process
    assert window.rng_busy.isHidden()


def test_the_indicator_explains_itself_in_the_interface_language(open_window, example_project):
    window = open_window(example_project)
    assert window.rng_busy.toolTip() == tr("rng.status.running.tip")
    window._set_language_code("en")
    try:
        assert window.rng_busy.toolTip() == tr("rng.status.running.tip")
        assert "TEI_ALL" in window.rng_busy.toolTip()
    finally:
        window._set_language_code("fr")
