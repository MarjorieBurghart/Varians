# -*- coding: utf-8 -*-
"""Découpage de la fenêtre principale, suite (V0.9.4.7).

``MainWindow`` (editeur_tei.py) est déjà faite de mixins depuis la V0.8.6.0 ;
elle garde ici encore 1 241 lignes. Les groupes de méthodes les plus souvent
modifiés passent dans des mixins, un module par responsabilité, sans
changement du code déplacé :
- ``source_selection`` (``SourceSelectionMixin``) : passage de l'onglet
  « XML source » à l'aperçu et retour, la sélection retrouvée par son texte
  et son contexte ;
- ``pivot_line_index`` (``PivotLineIndexMixin``) : repères de ligne du pivot
  dans le texte de l'éditeur, rang d'un repère, état de structure de la barre
  d'état.

Les modules n'importent pas ``editeur_tei`` (il peut être lancé comme
script), sont protégés des anciennes installations gardées par Spyder
(``_LOCAL_MODULE_NAMES``), lus par les tests qui inspectent le code
(``tests/varians_source.APPLICATION_MODULES``) et décrits dans la carte des
modules (docs/DEVELOPPEMENT.md)."""
from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

from varians_source import APPLICATION_MODULES

ROOT = Path(__file__).resolve().parents[1]
MIXINS = {
    "source_selection": ("SourceSelectionMixin", [
        "_source_compact", "_source_unit_spans", "_source_unit_at", "_source_unit_span",
        "_source_selection_context", "_source_selection_structure", "_select_source_quote",
        "_select_source_span", "_left_tab_changed"]),
    "pivot_line_index": ("PivotLineIndexMixin", [
        "_source_contents_changed", "_set_lb_spans", "_rebuild_lb_cache", "lb_spans",
        "ordinal_at_position", "ordinal_at_cursor"]),
}


def _editor_tree():
    return ast.parse((ROOT / "editeur_tei.py").read_text(encoding="utf-8"))


def _main_window():
    return next(node for node in _editor_tree().body
                if isinstance(node, ast.ClassDef) and node.name == "MainWindow")


def _local_module_names():
    for node in ast.walk(_editor_tree()):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_LOCAL_MODULE_NAMES" for t in node.targets):
            return {elt.value for elt in node.value.elts}
    raise AssertionError("_LOCAL_MODULE_NAMES introuvable")


@pytest.mark.parametrize("module, spec", MIXINS.items())
def test_the_methods_live_in_their_mixin(module, spec):
    """Les méthodes sont celles du mixin, et plus celles de MainWindow."""
    mixin_name, methods = spec
    mixin = getattr(importlib.import_module(module), mixin_name)
    own = {item.name for item in _main_window().body if isinstance(item, ast.FunctionDef)}
    for name in methods:
        assert name in vars(mixin) and name not in own, name


@pytest.mark.parametrize("module, spec", MIXINS.items())
def test_the_window_inherits_each_mixin(module, spec):
    """MainWindow hérite du mixin, importé de son module."""
    mixin_name, _methods = spec
    assert mixin_name in {base.id for base in _main_window().bases if isinstance(base, ast.Name)}
    imported = {(node.module, alias.name) for node in _editor_tree().body
                if isinstance(node, ast.ImportFrom) for alias in node.names}
    assert (module, mixin_name) in imported


@pytest.mark.parametrize("module", MIXINS)
def test_no_other_mixin_defines_the_same_methods(module):
    """Aucun autre module de l'interface ne définit ces méthodes : l'ordre des
    bases de MainWindow ne change rien."""
    mixin_name, methods = MIXINS[module]
    for path in sorted(ROOT.glob("*.py")):
        if path.stem == module:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Mixin"):
                defined = {item.name for item in node.body if isinstance(item, ast.FunctionDef)}
                assert not defined & set(methods), (path.name, node.name, defined & set(methods))


@pytest.mark.parametrize("module", MIXINS)
def test_the_modules_do_not_import_the_launcher(module):
    tree = ast.parse((ROOT / f"{module}.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module != "editeur_tei"
        elif isinstance(node, ast.Import):
            assert all(alias.name != "editeur_tei" for alias in node.names)


def test_the_modules_are_protected_like_the_other_local_modules():
    assert set(MIXINS) <= _local_module_names()


def test_the_source_inspecting_tests_read_the_modules():
    assert {f"{module}.py" for module in MIXINS} <= set(APPLICATION_MODULES)


def test_the_module_map_names_the_modules():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    for module in MIXINS:
        assert f"| `{module}.py` |" in guide, module
