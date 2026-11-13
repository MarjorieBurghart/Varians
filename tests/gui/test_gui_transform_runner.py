# -*- coding: utf-8 -*-
"""Client du processus de transformation (transform_runner) : lancer, recevoir
le compte rendu, annuler ; un processus qui échoue ne bloque jamais."""
from __future__ import annotations

import shutil
import signal
import sys
import time
from pathlib import Path

import pytest

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



@pytest.mark.skipif(not hasattr(signal, "SIGCHLD"), reason="SIGCHLD : systèmes POSIX seulement")
def test_the_end_of_a_process_still_arrives_after_sigchld_is_reset(qtbot):
    """Sous macOS, Qt apprend la fin d'un QProcess par le signal SIGCHLD.
    Saxon, programme Java chargé dans Varians quand Varians valide lui-même
    des règles Schematron (processus de validation indisponible), remet ce
    signal à son état par défaut : la fin des transformations n'arrivait
    plus, et F8 sur une feuille XSLT ou Transformer restaient bloqués
    jusqu'à la fermeture de Varians (V0.9.4.6). SIGCHLD remis à son état par
    défaut après un premier processus, la fin des suivants arrive encore, et
    l'annulation aussi."""
    _finish(qtbot, TransformRunner([sys.executable, "-c", "print('{}')"]), {}, timeout=20_000)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    result = _finish(qtbot, TransformRunner([sys.executable, "-c", "import sys; sys.exit(3)"]), {}, timeout=20_000)
    assert result.error_code == "worker_failed"
    runner = TransformRunner([sys.executable, "-c", "import time; time.sleep(60)"])
    with qtbot.waitSignal(runner.finished, timeout=20_000) as blocker:
        runner.start({})
        runner.cancel()
    assert blocker.args[0].error_code == "cancelled" and not runner.running()
