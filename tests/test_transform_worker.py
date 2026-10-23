# -*- coding: utf-8 -*-
"""Processus d'une transformation XSLT (transform_worker), sans Qt : Varians
relancé avec ``--transform-worker`` lit une requête JSON et rend le compte
rendu de l'exécution en JSON."""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from project_config import TransformScenario, load_project
from xslt_engines import TransformResult
from xslt_scenarios import scenario_request

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(__file__).resolve().parent / "data" / "sermons"


def _worker(data: bytes):
    completed = subprocess.run([sys.executable, str(ROOT / "editeur_tei.py"), "--transform-worker"],
                               input=data, capture_output=True, timeout=120)
    assert completed.returncode == 0, completed.stderr
    return json.loads(completed.stdout.decode("utf-8"))


def test_the_worker_runs_a_request_without_loading_qt(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    project = load_project(root / "project.xml")
    request = scenario_request(TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                                 css="${varians}/tei.css"), project)
    answer = _worker(json.dumps(request).encode("utf-8"))
    assert answer["qt_loaded"] is False
    result = TransformResult.from_dict(answer)
    assert result.ok, result.error
    assert result.outputs == [str(root / "publications" / "edition.html"), str(root / "publications" / "tei.css")]
    assert "Sermones" in (root / "publications" / "edition.html").read_text(encoding="utf-8")


def test_a_bad_request_gets_an_answer():
    for data in (b"pas du JSON", b"[1, 2]"):
        result = TransformResult.from_dict(_worker(data))
        assert not result.ok and result.error_code == "internal"


def test_run_in_process_gives_the_answer_of_the_worker(tmp_path):
    from transform_worker import run_in_process, worker_command
    assert worker_command()[-1] == "--transform-worker"
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    request = scenario_request(TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html"),
                               load_project(root / "project.xml"))
    result = run_in_process(request)
    assert result.ok, result.error
    assert (root / "publications" / "edition.html").is_file()
    failed = run_in_process(request, command=[sys.executable, "-c", "import sys; sys.stderr.write('panne'); sys.exit(3)"])
    assert not failed.ok and failed.error_code == "worker_failed" and "panne" in failed.error
