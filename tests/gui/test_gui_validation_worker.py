# -*- coding: utf-8 -*-
"""Client du processus de validation RELAX NG (validation_worker) : requêtes
vers le processus séparé, attente sans figer la fenêtre, repli dans Varians."""
from __future__ import annotations

import importlib.util
import sys
import threading
import time
from pathlib import Path

import pytest
from PySide6.QtCore import QTimer, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

import validation_worker
from validation_worker import RelaxNGWorkerClient, default_worker_command

ROOT = Path(__file__).resolve().parents[2]
SLOW_WORKER = Path(__file__).with_name("slow_relaxng_worker.py")
SCHEMA = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><element name="root"><zeroOrMore><element name="p"><text/></element></zeroOrMore></element></start>
</grammar>
"""


@pytest.fixture
def schema(tmp_path):
    path = tmp_path / "essai.rng"
    path.write_text(SCHEMA, encoding="utf-8")
    return path


@pytest.fixture
def make_client():
    clients = []

    def _make(command=None):
        client = RelaxNGWorkerClient(command)
        clients.append(client)
        return client

    yield _make
    for client in clients:
        client.shutdown()


def _slow(delay):
    return [sys.executable, str(SLOW_WORKER), str(delay)]


def test_validation_goes_through_the_worker_process(make_client, schema, qtbot):
    client = make_client()
    assert client.validate("<root><p>a</p></root>", schema).valid
    result = client.validate("<root><x/></root>", schema)
    assert result.well_formed and not result.valid and result.issues
    assert client.uses_process and client.compilations == 1          # schéma compilé une fois
    process = client._process
    client.shutdown()
    assert process.poll() is not None


def test_asynchronous_validation_answers_in_the_main_thread(make_client, schema, qtbot):
    client = make_client()
    owner = QPushButton()
    answers, states = [], []
    client.busyChanged.connect(states.append)
    client.validate_async("<root/>", schema, None, owner,
                          lambda result: answers.append((result.valid, threading.current_thread())))
    assert client.busy
    qtbot.waitUntil(lambda: bool(answers), timeout=30000)
    assert answers == [(True, threading.main_thread())]
    assert states == [True, False] and not client.busy


def test_no_answer_for_a_destroyed_owner(make_client, schema, qtbot):
    client = make_client()
    owner = QPushButton()
    answers = []
    client.validate_async("<root/>", schema, None, owner, answers.append)
    owner.deleteLater()
    qtbot.wait(10)
    qtbot.waitUntil(lambda: not client.busy, timeout=30000)
    assert answers == []


def test_waiting_keeps_the_window_alive_and_ignores_clicks(make_client, schema, qtbot):
    # Validation de 2 s : une attente bloquante figerait la boucle au moins
    # autant ; le seuil de 1,5 s tolère les pauses d'une machine chargée.
    client = make_client(_slow(2.0))
    ticks = []
    timer = QTimer()
    timer.timeout.connect(lambda: ticks.append(time.perf_counter()))
    timer.start(20)
    button = QPushButton("essai")
    button.show()
    qtbot.waitExposed(button)
    clicks = []
    button.clicked.connect(lambda: clicks.append(1))
    QTimer.singleShot(300, lambda: QTest.mouseClick(button, Qt.MouseButton.LeftButton))
    started = time.perf_counter()
    assert client.validate("<root/>", schema).valid
    elapsed = time.perf_counter() - started
    timer.stop()
    assert elapsed >= 2.0
    assert len(ticks) >= 20                                          # la boucle d'événements a tourné
    assert max(b - a for a, b in zip(ticks, ticks[1:])) < 1.5
    assert clicks == []                                              # clic ignoré pendant l'attente
    qtbot.wait(50)
    assert clicks == []                                              # et non différé


def test_a_dead_worker_falls_back_to_validation_in_varians(make_client, schema, qtbot):
    client = make_client()
    assert client.validate("<root/>", schema).valid
    reasons = []
    client.fellBack.connect(reasons.append)
    client._process.kill()
    client._process.wait(10)
    assert client.validate("<root><p>b</p></root>", schema).valid
    assert not client.uses_process and client.fallback_reason
    assert client.validate("<root/>", schema).valid
    assert len(reasons) == 1                                         # signalé une seule fois


def test_a_worker_that_cannot_start_falls_back(make_client, schema, tmp_path, qtbot):
    client = make_client([str(tmp_path / "absent")])
    assert client.validate("<root/>", schema).valid
    assert not client.uses_process and client.fallback_reason


def test_pending_requests_survive_a_crash(make_client, schema, qtbot):
    client = make_client(_slow(30))
    owner = QPushButton()
    answers = []
    client.validate_async("<root/>", schema, None, owner, lambda result: answers.append(result.valid))
    qtbot.wait(300)
    client._process.kill()
    qtbot.waitUntil(lambda: bool(answers), timeout=10000)
    assert answers == [True] and not client.busy


def test_the_worker_command_works_from_sources_and_in_a_standalone_build(monkeypatch):
    assert default_worker_command() == [sys.executable, str(ROOT / "editeur_tei.py"), "--relaxng-worker"]
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert default_worker_command() == [sys.executable, "--relaxng-worker"]


def test_one_client_for_the_whole_application(monkeypatch):
    monkeypatch.setattr(validation_worker, "_client", None)
    first = validation_worker.worker_client()
    try:
        assert validation_worker.worker_client() is first
    finally:
        first.shutdown()


def test_closing_during_a_validation_stops_the_process_at_once(make_client, schema, qtbot):
    # Fermer Varians pendant la compilation d'un gros schéma ne doit pas
    # attendre la fin de celle-ci.
    client = make_client(_slow(30))
    client.validate_async("<root/>", schema, None, QPushButton(), lambda result: None)
    qtbot.wait(300)
    process = client._process
    started = time.perf_counter()
    client.shutdown()
    assert time.perf_counter() - started < 1.0
    assert process.poll() is not None


@pytest.mark.parametrize("command", [None, "absent"])
def test_an_assembled_edition_is_validated_with_its_parts(make_client, schema, tmp_path, qtbot, command):
    # Par le processus séparé, puis par le repli dans Varians : même fonction.
    client = make_client([str(tmp_path / "absent")] if command else None)
    part = tmp_path / "part.xml"
    part.write_text("<p>\n<x/></p>", encoding="utf-8")
    master = tmp_path / "edition.xml"
    text = '<root xmlns:xi="http://www.w3.org/2001/XInclude"><xi:include href="part.xml"/></root>'
    result = client.validate(text, schema, master, parts={})
    assert [(Path(i.file).name, i.line) for i in result.issues] == [("part.xml", 2)]
    answers = []
    client.validate_async(text, schema, master, QPushButton(), answers.append, parts={str(part): "<p>b</p>"})
    qtbot.waitUntil(lambda: bool(answers), timeout=30000)
    assert answers[0].valid
    assert client.uses_process is (command is None)


RULES = """<?xml version="1.0"?>
<schema xmlns="http://purl.oclc.org/dsdl/schematron">
  <pattern><rule context="p"><assert test="string-length(.) &gt; 1">Paragraphe trop court.</assert></rule></pattern>
</schema>
"""


@pytest.mark.skipif(importlib.util.find_spec("saxonche") is None, reason="Saxon (saxonche) n'est pas installé")
@pytest.mark.parametrize("command", [None, "absent"])
def test_schematron_sources_go_with_the_request(make_client, schema, tmp_path, qtbot, command):
    # V0.9.2.3 : par le processus séparé, puis par le repli dans Varians.
    client = make_client([str(tmp_path / "absent")] if command else None)
    rules = tmp_path / "regles.sch"
    rules.write_text(RULES, encoding="utf-8")
    result = client.validate("<root>\n<p>a</p>\n</root>", schema, schematron=[rules])
    assert not result.valid and [(i.domain, i.line) for i in result.issues] == [("SCHEMATRON", 2)]
    answers = []
    client.validate_async("<root><p>a</p></root>", None, None, QPushButton(), answers.append, schematron=[rules])
    qtbot.waitUntil(lambda: bool(answers), timeout=30000)
    assert answers[0].schematron_rules == (str(rules),) and not answers[0].valid
    assert client.uses_process is (command is None)


def test_the_worker_writes_its_errors_to_a_log_removed_at_the_end(make_client, schema, qtbot):
    client = make_client()
    assert client.validate("<root/>", schema).valid
    log = Path(client.stderr_log)
    assert log.is_file()
    client.shutdown()
    assert not log.exists()
