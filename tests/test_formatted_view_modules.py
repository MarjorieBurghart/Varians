# -*- coding: utf-8 -*-
"""Découpage de la vue XSLT / CSS (V0.9.4.7).

formatted_view.py (2 489 lignes) est réparti en modules, un par
responsabilité, sans changement du code déplacé :
- ``preview_css`` (sans Qt) : règles CSS de l'aperçu et variables CSS ;
- ``preview_browser`` : le navigateur de l'aperçu (``ClickablePreview``) et
  la recherche dans un texte enrichi ;
- ``formatted_views`` : les vues nommées (``ViewsMixin``) ;
- ``fragment_editor`` : l'éditeur de fragment (``FragmentEditorMixin``).

Les méthodes de ``FormattedEditionWidget`` déplacées vivent dans des classes
« mixin » dont il hérite, comme celles de la fenêtre principale.

``formatted_view`` garde la transformation XSLT, la chaîne de l'aperçu et la
construction de la vue. Les modules sont protégés, comme les autres modules
locaux, contre les anciennes installations gardées par Spyder
(``editeur_tei._LOCAL_MODULE_NAMES``), et décrits dans la carte des modules
(docs/DEVELOPPEMENT.md)."""
from __future__ import annotations

import ast
import importlib
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PARTS = {
    "preview_css": ["PREVIEW_BASE_CSS", "has_own_style", "resolve_css_variables", "resolve_style_variables"],
    "preview_browser": ["ClickablePreview", "find_in_rich_editor"],
}
MIXINS = {
    "formatted_views": ("ViewsMixin", ["current_view", "xsl_path", "css_path", "context_changed", "new_view",
                                       "edit_view", "remove_view", "select_view", "view_unit_names"]),
    "fragment_editor": ("FragmentEditorMixin", ["edit_selected_paragraph", "load_fragment", "reload_fragment",
                                                "apply_fragment", "close_fragment_editor",
                                                "fragment_has_unapplied_changes"]),
}
MODULES = [*PARTS, *MIXINS]


def _local_module_names():
    tree = ast.parse((ROOT / "editeur_tei.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_LOCAL_MODULE_NAMES" for t in node.targets):
            return {elt.value for elt in node.value.elts}
    raise AssertionError("_LOCAL_MODULE_NAMES introuvable")


def _defined_in(path):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


@pytest.mark.parametrize("module, names", PARTS.items())
def test_each_part_lives_in_its_module(module, names):
    """Chaque partie est définie dans son module, et plus dans formatted_view."""
    assert set(names) <= _defined_in(ROOT / f"{module}.py")
    assert not set(names) & _defined_in(ROOT / "formatted_view.py")


@pytest.mark.parametrize("module, spec", MIXINS.items())
def test_the_widget_is_made_of_its_parts(module, spec):
    """Les méthodes déplacées sont celles du mixin, dont la vue hérite."""
    from formatted_view import FormattedEditionWidget
    mixin_name, methods = spec
    mixin = getattr(importlib.import_module(module), mixin_name)
    assert issubclass(FormattedEditionWidget, mixin)
    for name in methods:
        assert name in vars(mixin) and name not in vars(FormattedEditionWidget), name


def test_the_preview_css_needs_no_qt():
    code = "import sys, preview_css; print([m for m in sys.modules if m.startswith('PySide6')])"
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "[]"


def test_the_parts_are_protected_like_the_other_local_modules():
    assert set(MODULES) | {"formatted_view"} <= _local_module_names()


def test_the_module_map_names_the_parts():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    for module in MODULES:
        assert f"| `{module}.py` |" in guide, module


def test_the_parts_import_cleanly():
    for module in MODULES:
        importlib.import_module(module)
