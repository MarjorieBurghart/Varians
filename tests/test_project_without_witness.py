# -*- coding: utf-8 -*-
"""Projet sans témoin : on peut créer un projet (édition, validation,
aperçu, transformations) et n'ajouter ses témoins que plus tard, par
« Paramètres du projet »."""
from __future__ import annotations

from project_config import load_project

PROJECT = ('<teiManuscriptProject version="1"><title>Essai</title>'
           '<edition file="xml/edition.xml"/><rendering xsltMode="builtin"/>'
           '{witnesses}</teiManuscriptProject>')


def _project(tmp_path, witnesses):
    path = tmp_path / "project.xml"
    path.write_text(PROJECT.format(witnesses=witnesses), encoding="utf-8")
    return path


def test_a_project_without_witness_is_read(tmp_path):
    for witnesses in ("<witnesses/>", '<witnesses base=""/>', "<witnesses></witnesses>"):
        project = load_project(_project(tmp_path, witnesses))
        assert list(project.witnesses) == []
        assert project.base_witness == ""
        assert project.witness_by_id == {}
