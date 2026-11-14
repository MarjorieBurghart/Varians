# -*- coding: utf-8 -*-
"""Découpage des boîtes du projet (V0.9.4.7).

project_dialogs.py (1 558 lignes) réunissait cinq boîtes indépendantes ;
chacune a désormais son module, sans changement du code déplacé :
- ``project_widgets`` : ``PathRow``, la ligne « chemin + Parcourir… » ;
- ``iiif_canvas_picker`` : ``IIIFCanvasPicker``, le choix des pages d'un
  Manifest IIIF ;
- ``witness_edit_dialog`` : ``WitnessEditDialog``, la fiche d'un témoin ;
- ``witness_table`` : ``WitnessTable``, la table des témoins.

``project_dialogs`` garde « Nouveau projet », « Paramètres du projet » et la
préparation du pivot. Les dépendances vont dans un seul sens (project_dialogs
→ witness_table → witness_edit_dialog → iiif_canvas_picker ; tous →
project_widgets). Les modules sont protégés des anciennes installations
(``editeur_tei._LOCAL_MODULE_NAMES``) et décrits dans la carte des modules."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARTS = {
    "project_widgets": ["PathRow"],
    "iiif_canvas_picker": ["IIIFCanvasPicker"],
    "witness_edit_dialog": ["WitnessEditDialog"],
    "witness_table": ["WitnessTable"],
}
KEPT = ["NewProjectDialog", "ProjectSettingsDialog", "run_pivot_scaffold_dialog"]
ORDER = ["project_dialogs", "witness_table", "witness_edit_dialog", "iiif_canvas_picker", "project_widgets"]


def _tree(module):
    return ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))


def _defined(module):
    return {n.name for n in _tree(module).body if isinstance(n, (ast.FunctionDef, ast.ClassDef))}


def _local_imports(module):
    found = set()
    for node in ast.walk(_tree(module)):
        if isinstance(node, ast.ImportFrom) and node.module and (ROOT / f"{node.module}.py").is_file():
            found.add(node.module)
        elif isinstance(node, ast.Import):
            found.update(a.name for a in node.names if (ROOT / f"{a.name}.py").is_file())
    return found


@pytest.mark.parametrize("module, names", PARTS.items())
def test_each_dialog_lives_in_its_module(module, names):
    assert set(names) <= _defined(module)
    assert not set(names) & _defined("project_dialogs")


def test_project_dialogs_keeps_the_project_boxes():
    assert set(KEPT) <= _defined("project_dialogs")


def test_the_dependencies_go_one_way():
    """Un module n'importe que ceux qui le suivent dans ORDER : pas d'import
    circulaire."""
    for i, module in enumerate(ORDER):
        assert not _local_imports(module) & set(ORDER[:i + 1]), module


def test_the_parts_are_protected_like_the_other_local_modules():
    tree = _tree("editeur_tei")
    listed = next({elt.value for elt in node.value.elts} for node in ast.walk(tree)
                  if isinstance(node, ast.Assign)
                  and any(isinstance(t, ast.Name) and t.id == "_LOCAL_MODULE_NAMES" for t in node.targets))
    assert set(PARTS) | {"project_dialogs"} <= listed


def test_the_module_map_names_the_parts():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    for module in PARTS:
        assert f"| `{module}.py` |" in guide, module


def test_the_parts_import_cleanly():
    for module in [*PARTS, "project_dialogs"]:
        importlib.import_module(module)
