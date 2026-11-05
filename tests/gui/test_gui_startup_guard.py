# -*- coding: utf-8 -*-
"""Démarrage de Varians : réouverture du dernier projet, garde-fou après un
démarrage interrompu, question avant un fichier trop volumineux.

Un projet dont l'édition faisait 700 Mo, dernier projet ouvert, bloquait le
démarrage : Varians le rouvrait avant d'afficher sa fenêtre, et la fenêtre
n'apparaissait jamais.
"""
from __future__ import annotations

import gc
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QThreadPool
from PySide6.QtWidgets import QApplication, QMessageBox

import app_context
import large_files
from app_context import tr


@pytest.fixture
def started(qtbot, editor_module):
    """``startup_window`` comme au lancement de Varians ; les fenêtres sont
    fermées proprement à la fin."""
    windows = []

    def _start(argv=("varians",)):
        window = editor_module.startup_window(list(argv))
        windows.append(window)
        return window

    yield _start

    import validation_worker
    qtbot.waitUntil(lambda: not validation_worker.worker_client().busy, timeout=60000)
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    for window in windows:
        window._force_close = True
        window.close()
        window.deleteLater()
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    gc.collect()


def _resolved(path):
    return Path(path).resolve()


def test_the_last_open_project_is_reopened_and_the_start_completes(started, example_project, editor_module,
                                                                   dialogs, qtbot):
    app_context.remember_open_project(example_project)
    window = started()
    assert isinstance(window, editor_module.MainWindow)
    # Tant que la fenêtre n'est pas affichée, le démarrage est en cours.
    assert app_context.startup_pending_project() == _resolved(example_project)
    editor_module.show_startup_window(window)
    qtbot.waitUntil(lambda: app_context.startup_pending_project() is None)
    assert app_context.last_open_project_path() == _resolved(example_project)


def test_a_project_whose_last_start_did_not_complete_is_not_reopened(started, example_project, editor_module,
                                                                    dialogs, qtbot):
    app_context.remember_recent_project(example_project)
    app_context.remember_open_project(example_project)
    # Démarrage précédent interrompu : fenêtre jamais affichée, Varians fermé.
    app_context.mark_startup_pending(example_project)

    dialogs.expect("warning")
    window = started()
    assert isinstance(window, editor_module.WelcomeWindow)
    editor_module.show_startup_window(window)
    qtbot.waitUntil(lambda: bool(dialogs.seen))
    kind, title, text = dialogs.seen[-1]
    assert (kind, title) == ("warning", tr("startup.interrupted.title"))
    assert text == tr("startup.interrupted", path=_resolved(example_project))
    # Il n'est plus rouvert, mais reste dans les projets récents.
    assert app_context.last_open_project_path() is None
    assert app_context.startup_pending_project() is None
    assert str(_resolved(example_project)) in app_context.recent_project_paths()

    # Démarrage suivant : l'accueil, sans message.
    assert isinstance(started(), editor_module.WelcomeWindow)


def test_a_start_interrupted_on_another_project_does_not_block_the_last_one(started, example_project,
                                                                            editor_module, dialogs, tmp_path):
    app_context.remember_open_project(example_project)
    app_context.mark_startup_pending(tmp_path / "autre" / "project.xml")
    window = started()
    assert isinstance(window, editor_module.MainWindow)
    assert app_context.startup_pending_project() == _resolved(example_project)


def test_a_large_last_project_is_reopened_only_on_request(started, example_project, editor_module, dialogs,
                                                          monkeypatch):
    monkeypatch.setattr(large_files, "LARGE_FILE_BYTES", 1000)
    edition = example_project.parent / "xml" / "edition.xml"
    app_context.remember_open_project(example_project)

    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    window = started()
    assert isinstance(window, editor_module.WelcomeWindow)
    kind, title, text = dialogs.seen[-1]
    assert title == tr("large_file.title")
    assert str(edition) in text
    assert app_context.last_open_project_path() is None
    assert app_context.startup_pending_project() is None

    app_context.remember_open_project(example_project)
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    assert isinstance(started(), editor_module.MainWindow)


def test_a_large_project_given_on_the_command_line_is_opened_only_on_request(started, example_project,
                                                                             editor_module, dialogs,
                                                                             monkeypatch):
    monkeypatch.setattr(large_files, "LARGE_FILE_BYTES", 1000)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert isinstance(started(["varians", str(example_project)]), editor_module.WelcomeWindow)

    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    assert isinstance(started(["varians", str(example_project)]), editor_module.MainWindow)


def test_the_large_file_question_defaults_to_cancel(qapp, monkeypatch, tmp_path):
    seen = {}

    def answer(box):
        seen["default"] = box.defaultButton().text()
        seen["escape"] = box.escapeButton().text()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", answer)
    files = [(tmp_path / "edition.xml", 700 * 1024 * 1024)]
    assert large_files.confirm_large_files(None, files) is False
    assert seen == {"default": tr("common.cancel"), "escape": tr("common.cancel")}
