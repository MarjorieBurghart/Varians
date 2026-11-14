# -*- coding: utf-8 -*-
"""Découpage du changement de sigle d'un témoin (V0.9.4.7).

witness_rename.py (1 525 lignes) est réparti en deux modules sans Qt, sans
changement du code déplacé :
- ``witness_rename_plan`` : le plan (``plan_witness_rename``, ``RenamePlan``
  et ses éléments, ``_Planner``), qui n'écrit rien, et la lecture du journal
  d'un changement interrompu (``journal_path``, ``read_journal``), qui lui
  permet de refuser un nouveau changement ;
- ``witness_rename`` : l'application du plan (``apply_witness_rename``),
  l'écriture du journal, la reprise après une interruption
  (``recover_interrupted_rename``, ``journal_state``) et le report des
  réglages d'affichage (``migrate_view_settings``).

Le plan ne dépend pas de l'application : ``witness_rename_plan`` n'importe
pas ``witness_rename``. Les deux modules sont protégés des anciennes
installations (``editeur_tei._LOCAL_MODULE_NAMES``) et décrits dans la carte
des modules (docs/DEVELOPPEMENT.md)."""
from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ["plan_witness_rename", "RenamePlan", "FileChange", "Move", "Mention", "_Planner", "journal_path",
        "read_journal"]
APPLICATION = ["apply_witness_rename", "recover_interrupted_rename", "journal_state", "migrate_view_settings",
               "RenameError", "RenameResult", "Recovery"]


def _tree(module):
    return ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))


def _defined(module):
    return {n.name for n in _tree(module).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def test_the_plan_lives_in_its_module():
    assert set(PLAN) <= _defined("witness_rename_plan")
    assert not set(PLAN) & _defined("witness_rename")


def test_the_application_stays_in_witness_rename():
    assert set(APPLICATION) <= _defined("witness_rename")
    assert not set(APPLICATION) & _defined("witness_rename_plan")


def test_the_plan_does_not_depend_on_the_application():
    for node in ast.walk(_tree("witness_rename_plan")):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "witness_rename"
        elif isinstance(node, ast.Import):
            assert all(alias.name != "witness_rename" for alias in node.names)


@pytest.mark.parametrize("module", ["witness_rename_plan", "witness_rename"])
def test_both_need_no_qt(module):
    code = f"import sys, {module}; print([m for m in sys.modules if m.startswith('PySide6')])"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_both_are_protected_like_the_other_local_modules():
    tree = _tree("editeur_tei")
    listed = next({elt.value for elt in node.value.elts} for node in ast.walk(tree)
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "_LOCAL_MODULE_NAMES" for t in node.targets))
    assert {"witness_rename", "witness_rename_plan"} <= listed


def test_the_module_map_names_both():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    for module in ("witness_rename", "witness_rename_plan"):
        assert f"| `{module}.py` |" in guide, module
