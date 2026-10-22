# -*- coding: utf-8 -*-
"""Validation RELAX NG sans figer la fenêtre : la validation automatique part
vers le processus séparé, la validation demandée (F8, enregistrement) attend
sa réponse en laissant la fenêtre se redessiner."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

import validation_worker
from app_context import tr
from validation_worker import RelaxNGWorkerClient

SLOW_WORKER = Path(__file__).with_name("slow_relaxng_worker.py")


@pytest.fixture
def slow_worker(monkeypatch):
    """Processus de validation qui met ``delay`` secondes à chaque réponse."""
    clients = []

    def _use(delay):
        client = RelaxNGWorkerClient([sys.executable, str(SLOW_WORKER), str(delay)])
        clients.append(client)
        monkeypatch.setattr(validation_worker, "_client", client)
        return client

    yield _use
    for client in clients:
        client.shutdown()


def _insert_after(window, needle, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index(needle) + len(needle))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_the_window_keeps_working_during_the_opening_validation(open_window, example_project, slow_worker, qtbot):
    # La validation dure 2,5 s : une fenêtre bloquée pendant l'attente
    # s'arrêterait au moins autant. Une machine chargée (tests GitHub) peut
    # marquer de courtes pauses, d'où le seuil de 1,5 s.
    client = slow_worker(2.5)
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start(20)
    window = open_window(example_project, wait_validation=False)
    assert client.busy                                              # validation partie
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    timer.stop()
    assert max(b - a for a, b in zip(ticks, ticks[1:])) < 1.5      # jamais figée
    assert window.rng_status.text() == tr("rng.status.valid")
    assert window._last_rng_result is not None and window._last_rng_result.valid


def test_an_edit_during_validation_discards_the_old_result(open_window, example_project, slow_worker, qtbot):
    client = slow_worker(1.0)
    window = open_window(example_project, wait_validation=False)
    assert client.busy
    _insert_after(window, "<body>", " ")
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    assert window._last_rng_result is None                          # résultat d'une ancienne révision
    assert window.rng_status.text() == tr("rng.status.modified")


def test_a_result_for_a_document_no_longer_displayed_is_not_shown(open_window, project_with_documents,
                                                                  slow_worker, qtbot):
    client = slow_worker(1.0)
    window = open_window(project_with_documents, wait_validation=False)
    edition = window.edition_session
    assert client.busy
    assert window.show_document(window.documents[1])
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    assert window.document is window.documents[1]
    assert window.rng_status.text() == tr("rng.status.no_xml_model")  # personnes.xml, sans schéma
    assert window.show_document(edition)
    qtbot.wait(300)
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    assert window.rng_status.text() == tr("rng.status.valid")       # validée à nouveau au retour


def test_saving_during_validation_waits_then_warns(open_window, example_project, slow_worker, dialogs, qtbot):
    client = slow_worker(1.0)
    window = open_window(example_project, wait_validation=False)
    _insert_after(window, "<body>", "\n<forbidden/>")
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)        # « Annuler » : document invalide
    started = time.perf_counter()
    assert not window.save()
    assert time.perf_counter() - started >= 0.9                     # a attendu la validation
    assert dialogs.seen[-1][1] == tr("file.save_rng_invalid.title")
    assert not client.busy


def test_manual_validation_returns_its_result(open_window, example_project, slow_worker):
    slow_worker(0.5)
    window = open_window(example_project, wait_validation=False)
    _insert_after(window, "<body>", "\n<forbidden/>")
    window.validate_relaxng_manual()
    assert window._last_rng_result is not None and not window._last_rng_result.valid
    assert window.validation_table.rowCount() >= 1


def test_an_unavailable_worker_is_reported_once_and_validation_still_works(open_window, example_project,
                                                                          monkeypatch, tmp_path):
    client = RelaxNGWorkerClient([str(tmp_path / "absent")])
    monkeypatch.setattr(validation_worker, "_client", client)
    window = open_window(example_project)
    assert window.rng_status.text() == tr("rng.status.valid")
    assert window.statusBar().currentMessage() == tr("rng.worker.fallback", reason=client.fallback_reason)
