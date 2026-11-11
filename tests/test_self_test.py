# -*- coding: utf-8 -*-
"""Vérification d'une installation (V0.9.4.0) : « Varians --self-test
RAPPORT.json ».

La version prête à l'emploi (sans Python, construite par PyInstaller) est
vérifiée sur chaque système, à sa construction, par cette option : sans
écran, Varians contrôle ses traductions, son aide et ses ressources, lance
ses processus de validation et de transformation (lxml et Saxon) comme il
le fait d'ordinaire, crée un petit projet et l'ouvre dans sa fenêtre.
Le rapport JSON dit ce qui a été vérifié ; le code de sortie est 0 si tout
va bien. Ici, le même contrôle en mode source."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHECKS = ["translations", "help", "resources", "project", "relaxng_worker", "transform_lxml",
          "transform_saxon", "preview_saxon", "window"]


def _environment(tmp_path):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    for name in ("HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "XDG_CONFIG_HOME"):
        env[name] = str(tmp_path / "home")
    (tmp_path / "home").mkdir(exist_ok=True)
    return env


def test_varians_checks_its_own_installation(tmp_path):
    report = tmp_path / "rapport.json"
    completed = subprocess.run([sys.executable, str(ROOT / "editeur_tei.py"), "--self-test", str(report)],
                               env=_environment(tmp_path), capture_output=True, timeout=300)
    data = json.loads(report.read_text(encoding="utf-8"))
    assert completed.returncode == 0, (completed.stderr.decode("utf-8", "replace")[-3000:],
                                       [c for c in data["checks"] if not c["ok"]])
    assert data["ok"] is True and data["frozen"] is False
    assert [check["name"] for check in data["checks"]] == CHECKS
    assert all(check["ok"] for check in data["checks"])
    from app_context import APP_VERSION
    assert data["version"] == APP_VERSION


def test_a_missing_part_of_the_installation_is_reported(tmp_path):
    """Une aide absente (fichier oublié par la recette de construction) :
    la vérification le dit et rend 1."""
    import self_test
    installation = tmp_path / "installation"
    for name in ("i18n", "rendering", "resources", "web_viewer"):
        shutil.copytree(ROOT / name, installation / name)
    report = tmp_path / "rapport.json"
    code = self_test.run(report, root=installation, only=("translations", "help", "resources"))
    data = json.loads(report.read_text(encoding="utf-8"))
    assert code == 1 and data["ok"] is False
    failed = [check for check in data["checks"] if not check["ok"]]
    assert [check["name"] for check in failed] == ["help"]
    assert "fr.html" in failed[0]["detail"]


def test_the_worker_processes_never_load_the_interface():
    """Les processus de validation et de transformation n'ouvrent pas
    l'interface. En mode source, ils ne chargent pas du tout PySide6 ; dans
    la version construite, PyInstaller charge QtCore dans tout processus
    (crochet d'exécution de PySide6) : toléré, mais jamais QtGui ni
    QtWidgets."""
    import self_test
    light = {"qt_loaded": False, "gui_loaded": False}
    assert self_test.worker_problem(light, frozen=False) is None
    assert self_test.worker_problem(light, frozen=True) is None
    core = {"qt_loaded": True, "gui_loaded": False}
    assert self_test.worker_problem(core, frozen=False)
    assert self_test.worker_problem(core, frozen=True) is None
    assert self_test.worker_problem({"qt_loaded": True, "gui_loaded": True}, frozen=True)
    assert self_test.worker_problem({"qt_loaded": False}, frozen=True)
