# -*- coding: utf-8 -*-
"""Version de l'application, cohérente partout où elle est annoncée."""
from __future__ import annotations

import ast
from pathlib import Path

from varians_source import CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")


def test_app_version():
    tree = ast.parse((ROOT / "app_context.py").read_text(encoding="utf-8"))
    values = [node.value.value for node in tree.body
              if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "APP_VERSION" for t in node.targets)]
    assert values == [CURRENT_VERSION]


def test_editeur_tei_header_announces_version():
    first_lines = (ROOT / "editeur_tei.py").read_text(encoding="utf-8").splitlines()[:3]
    assert any(f"V{CURRENT_VERSION}." in line for line in first_lines)


def test_readme_starts_with_current_version():
    head = (ROOT / "README.txt").read_text(encoding="utf-8")[:2000]
    assert f"VARIANS V{CURRENT_VERSION}" in head

