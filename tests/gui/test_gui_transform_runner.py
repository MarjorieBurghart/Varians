# -*- coding: utf-8 -*-
"""Client du processus de transformation (transform_runner) : lancer, recevoir
le compte rendu, annuler ; un processus qui échoue ne bloque jamais."""
from __future__ import annotations

import shutil
import sys
import time
from pathlib import Path

from project_config import TransformScenario, load_project
from transform_runner import TransformRunner
from xslt_scenarios import scenario_request

DATA = Path(__file__).resolve().parents[1] / "data" / "sermons"


def _finish(qtbot, runner, request, timeout=60_000):
    with qtbot.waitSignal(runner.finished, timeout=timeout) as blocker:
        runner.start(request)
    return blocker.args[0]


def test_a_scenario_runs_in_its_own_process(qtbot, tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    request = scenario_request(TransformScenario("Édition", "${varians}/tei-to-html.xsl",
                                                 "publications/edition.html"), load_project(root / "project.xml"))
    runner = TransformRunner()
    result = _finish(qtbot, runner, request)
    assert result.ok, result.error
    assert (root / "publications" / "edition.html").is_file()
    assert not runner.running()


def test_cancelling_stops_the_process_at_once(qtbot):
    runner = TransformRunner([sys.executable, "-c", "import time; time.sleep(60)"])
    start = time.monotonic()
    with qtbot.waitSignal(runner.finished, timeout=10_000) as blocker:
        runner.start({})
        assert runner.running()
        runner.cancel()
    assert blocker.args[0].error_code == "cancelled"
    assert time.monotonic() - start < 10
    assert not runner.running()


def test_a_process_that_fails_gives_a_failed_result(qtbot):
    for command in ([sys.executable, "-c", "import sys; sys.exit(3)"],
                    [sys.executable, "-c", "print('pas du JSON')"],
                    [str(Path(sys.executable).parent / "programme-absent")]):
        result = _finish(qtbot, TransformRunner(command), {})
        assert not result.ok and result.error_code == "worker_failed", command
