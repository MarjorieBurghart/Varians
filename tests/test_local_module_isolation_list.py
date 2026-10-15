# -*- coding: utf-8 -*-
"""Chaque module local importé par editeur_tei.py est protégé contre les
anciennes installations conservées par Spyder (_LOCAL_MODULE_NAMES)."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_every_local_import_is_listed():
    tree = ast.parse((ROOT / "editeur_tei.py").read_text(encoding="utf-8"))
    listed = None
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "_LOCAL_MODULE_NAMES" for t in node.targets):
            listed = {elt.value for elt in node.value.elts}
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            top = node.module.split(".")[0]
            if (ROOT / f"{top}.py").is_file():
                imported.add(top)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if (ROOT / f"{top}.py").is_file():
                    imported.add(top)
    assert listed is not None
    assert imported - listed == set()
