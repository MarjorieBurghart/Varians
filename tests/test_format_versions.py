# -*- coding: utf-8 -*-
"""Numéros de format de project.xml et des synchronisations (V0.9.4.7).

``project_management.write_project_xml`` écrit ``<teiManuscriptProject
version="1">`` ; les fichiers de synchronisation portent
``meta.format = "tei-manuscript-alignment"`` et ``meta.format_version = 1``.
Ces numéros ne changent que si le format change vraiment : Varians-Synchro
fonde sur eux sa compatibilité avec Varians (et non sur un numéro de
version de Varians), et sa CI vérifie chaque semaine que Varians écrit
toujours le même format de project.xml. Le dossier développeur (chapitres 4
et 6) et ALIGNMENT_FORMAT.md donnent la règle ; le numéro documenté est celui
qu'écrit le code."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = "ne change que si le format change"


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def _chapter(title, following):
    handoff = _read("DEVELOPER_HANDOFF.md")
    return handoff[handoff.index(title):handoff.index(following)]


def _written_project_version():
    tree = ast.parse(_read("project_management.py"))
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and node.args and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "teiManuscriptProject" and len(node.args) > 1
                and isinstance(node.args[1], ast.Dict)):
            for key, value in zip(node.args[1].keys, node.args[1].values):
                if isinstance(key, ast.Constant) and key.value == "version":
                    return value.value
    raise AssertionError("version de project.xml introuvable dans write_project_xml")


def test_the_project_chapter_states_the_written_format_and_the_rule():
    chapter = _chapter("## 4. Contrat de `project.xml`", "## 5. Modèle TEI utilisé par Varians")
    assert f'<teiManuscriptProject version="{_written_project_version()}">' in chapter
    assert RULE in chapter
    assert "Varians-Synchro" in chapter


def test_the_alignment_chapter_states_the_format_version_and_the_rule():
    chapter = _chapter("## 6. Contrat JSON de synchronisation", "## 7. Cartographie des modules Python")
    assert '"format": "tei-manuscript-alignment"' in chapter and '"format_version": 1' in chapter
    assert RULE in chapter


def test_the_alignment_format_document_gives_the_rule():
    document = _read("ALIGNMENT_FORMAT.md")
    assert document.startswith("# Format d'alignement — version 1\n")
    assert RULE in document
