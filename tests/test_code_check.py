# -*- coding: utf-8 -*-
"""Vérification du code par ruff (V0.9.4.7).

Des règles minimales, qui ne visent que de vrais défauts : celles de
pyflakes (F : import ou variable inutilisés, nom non défini…), les erreurs
de syntaxe (E9), et deux pièges que relève bugbear, absents aujourd'hui
(B006 : argument par défaut modifiable ; B023 : fonction créée dans une
boucle qui voit la variable de la dernière itération). Le style (longueur
des lignes…) n'est pas vérifié. Dans les tests, une fixture importée d'un
autre fichier puis reçue en paramètre n'est pas une redéfinition (F811).

ruff est une dépendance de développement à version fixée ; le workflow Tests
le lance avant la suite des tests, et ce test aussi, en local."""
from __future__ import annotations

import importlib.util
import shutil
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _config():
    return tomllib.loads((ROOT / "ruff.toml").read_text(encoding="utf-8"))


def test_the_rules_aim_at_real_defects_only():
    lint = _config()["lint"]
    assert set(lint["select"]) == {"F", "E9", "B006", "B023"}
    assert lint["per-file-ignores"] == {"tests/**": ["F811"]}


def test_ruff_is_a_development_dependency_with_a_tested_version():
    requirements = (ROOT / "requirements-dev.txt").read_text(encoding="utf-8").split()
    assert "ruff" in requirements
    constraints = (ROOT / "constraints.txt").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("ruff==") for line in constraints)


def test_the_workflow_checks_the_code_before_the_tests():
    workflow = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")
    step = workflow.index("      - name: Vérification du code (ruff)\n")
    assert "run: python -m ruff check ." in workflow[step:workflow.index("\n\n", step)]
    assert step < workflow.index("      - name: Tests\n")


def test_the_development_guide_explains_the_check():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    assert "ruff" in guide and "python -m ruff check ." in guide


def _ruff():
    """La commande de ruff : le module installé par pip (comme dans le
    workflow), sinon le programme ruff s'il est sur le PATH."""
    if importlib.util.find_spec("ruff") is not None:
        return [sys.executable, "-m", "ruff"]
    program = shutil.which("ruff")
    return [program] if program else None


@pytest.mark.skipif(_ruff() is None, reason="ruff n'est pas installé")
def test_the_code_passes_the_check():
    result = subprocess.run(_ruff() + ["check", "--no-cache", "."], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
