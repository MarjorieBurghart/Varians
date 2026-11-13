# -*- coding: utf-8 -*-
"""Ce que Varians note dans son journal des erreurs (V0.9.4.6), en plus des
exceptions non rattrapées : les erreurs montrées à l'utilisateur, avec leur
pile d'appels ; les processus séparés en échec (validation, transformation,
aperçu), avec la fin de leur sortie d'erreur ; les échecs qui ne
s'affichent pas, mais laisseraient un fichier ou un état en trop."""
from __future__ import annotations

import logging
import os
import sys
from pathlib import Path

import pytest
from PySide6.QtWidgets import QPushButton

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><element name="root"><text/></element></start>
</grammar>
"""


@pytest.fixture
def journal(caplog):
    """Les écritures du journal (logger « varians » et ses enfants)."""
    caplog.set_level(logging.INFO, logger="varians")

    def records(part):
        return [record for record in caplog.records if record.name == f"varians.{part}"]
    return records


def test_an_error_shown_to_the_user_is_written_with_its_trace(journal):
    from app_context import error_message
    try:
        raise OSError("disque plein")
    except OSError as exc:
        assert error_message(exc) == "disque plein"
    [record] = journal("interface")
    assert record.levelno == logging.WARNING and "disque plein" in record.getMessage()
    assert record.exc_info and record.exc_info[0] is OSError


def test_an_error_built_without_raising_is_written_without_trace(journal):
    from app_context import error_message
    assert error_message(ValueError("valeur")) == "valeur"
    [record] = journal("interface")
    assert "valeur" in record.getMessage() and not record.exc_info


def test_a_validation_process_that_cannot_start_is_written(journal, tmp_path, qtbot):
    from validation_worker import RelaxNGWorkerClient
    schema = tmp_path / "essai.rng"
    schema.write_text(SCHEMA, encoding="utf-8")
    client = RelaxNGWorkerClient([str(tmp_path / "absent")])
    try:
        assert client.validate("<root/>", schema).valid
    finally:
        client.shutdown()
    [record] = journal("validation")
    assert record.levelno == logging.WARNING and client.fallback_reason in record.getMessage()


def test_a_validation_process_that_dies_is_written_with_its_errors(journal, tmp_path, qtbot):
    from validation_worker import RelaxNGWorkerClient
    schema = tmp_path / "essai.rng"
    schema.write_text(SCHEMA, encoding="utf-8")
    dying = tmp_path / "mourant.py"
    dying.write_text("import sys\nsys.stderr.write('Saxon : panne grave\\n')\nsys.exit(7)\n", encoding="utf-8")
    client = RelaxNGWorkerClient([sys.executable, str(dying)])
    try:
        assert client.validate("<root/>", schema).valid                  # validé dans Varians
    finally:
        client.shutdown()
    [record] = journal("validation")
    assert "Saxon : panne grave" in record.getMessage()


def test_a_transformation_process_that_fails_is_written(journal, qtbot):
    from transform_runner import TransformRunner
    runner = TransformRunner([sys.executable, "-c", "import sys; sys.stderr.write('Saxon : erreur fatale'); sys.exit(3)"])
    with qtbot.waitSignal(runner.finished, timeout=20_000) as blocker:
        runner.start({})
    assert blocker.args[0].error_code == "worker_failed"
    [record] = journal("transformation")
    assert record.levelno == logging.WARNING and "Saxon : erreur fatale" in record.getMessage()


def test_a_cancelled_or_successful_transformation_writes_nothing(journal, qtbot):
    from transform_runner import TransformRunner
    runner = TransformRunner([sys.executable, "-c", "import time; time.sleep(60)"])
    with qtbot.waitSignal(runner.finished, timeout=20_000):
        runner.start({})
        runner.cancel()
    assert journal("transformation") == []


def test_a_preview_process_that_fails_is_written(journal, tmp_path):
    from saxon_preview import PreviewError, SaxonPreviewClient
    dying = SaxonPreviewClient([sys.executable, "-c", "import sys; sys.stderr.write('aperçu en panne'); sys.exit(1)"])
    try:
        with pytest.raises(PreviewError):
            dying.ping(timeout=20)
    finally:
        dying.close()
    silent = SaxonPreviewClient([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        with pytest.raises(PreviewError):
            silent.ping(timeout=1)
    finally:
        silent.close()
    messages = [record.getMessage() for record in journal("preview")]
    assert len(messages) == 2 and "aperçu en panne" in messages[0] and "timeout" in messages[1]


def test_a_temporary_file_left_by_a_failed_save_is_written(journal, tmp_path, monkeypatch):
    import save_io
    target = tmp_path / "edition.xml"
    target.write_text("<TEI/>", encoding="utf-8")

    def refuse(*args, **kwargs):
        raise PermissionError("verrouillé")

    monkeypatch.setattr(save_io.os, "replace", refuse)
    monkeypatch.setattr(Path, "unlink", refuse)
    with pytest.raises(PermissionError):
        save_io.atomic_write_text_with_backup(target, "<TEI>nouveau</TEI>")
    [record] = journal("files")
    assert record.levelno == logging.WARNING and ".edition.xml." in record.getMessage()


def test_cursor_places_that_cannot_be_kept_are_written(journal, open_window, sermons_project, monkeypatch):
    window = open_window(sermons_project)

    def broken():
        raise KeyError("place")

    monkeypatch.setattr(window, "remember_cursor_places", broken)
    window._remember_cursor_places_safely()
    [record] = journal("window")
    assert record.levelno == logging.WARNING and record.exc_info[0] is KeyError


def test_an_abandoned_compilation_is_written_with_its_schema(journal, tmp_path, qtbot, monkeypatch):
    import validation_worker
    from validation_worker import RelaxNGWorkerClient
    monkeypatch.setattr(validation_worker, "COMPILE_LIMIT_SEC", 1)
    stuck = tmp_path / "bloque.rng"
    stuck.write_text(SCHEMA, encoding="utf-8")
    client = RelaxNGWorkerClient([sys.executable, str(Path(__file__).with_name("stuck_relaxng_worker.py"))])
    answers = []
    owner = QPushButton()
    try:
        client.validate_async("<root/>", stuck, None, owner, answers.append)
        qtbot.waitUntil(lambda: bool(answers), timeout=20_000)
    finally:
        client.shutdown()
    assert answers[0].abandoned
    [record] = journal("validation")
    assert record.levelno == logging.WARNING and "bloque.rng" in record.getMessage()
