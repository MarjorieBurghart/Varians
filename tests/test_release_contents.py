# -*- coding: utf-8 -*-
"""Contenu des publications (V0.9.2.8.2) : le projet de test vit avec les
tests (tests/data/exemple), pas à la racine de Varians, et le dossier tests/
est exclu des archives des publications GitHub (.gitattributes,
export-ignore). Le générateur du viewer web demande donc un projet."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
EXAMPLE = REPO / "tests" / "data" / "exemple"


def test_the_example_project_lives_with_the_tests():
    assert (EXAMPLE / "project.xml").is_file()
    assert (EXAMPLE / "xml" / "edition.xml").is_file()
    for witness in ("T1", "T2", "P"):
        assert (EXAMPLE / "alignments" / f"{witness}.json").is_file()
    for name in ("project.xml", "xml", "alignments", "web_output"):
        assert not (REPO / name).exists(), name


def test_the_tests_are_left_out_of_release_archives():
    git = shutil.which("git")
    if git is None or not (REPO / ".git").exists():
        pytest.skip("dépôt Git indisponible")
    paths = ["tests/data/exemple/project.xml", "tests/test_version.py",
             "editeur_tei.py", "rendering/tei.css", "i18n/fr.xml", "help/fr.html"]
    output = subprocess.run([git, "check-attr", "export-ignore", "--", *paths], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout
    values = dict(line.rsplit(": export-ignore: ", 1) for line in output.splitlines())
    assert values == {
        "tests/data/exemple/project.xml": "set", "tests/test_version.py": "set",
        "editeur_tei.py": "unspecified", "rendering/tei.css": "unspecified",
        "i18n/fr.xml": "unspecified", "help/fr.html": "unspecified"}


def test_the_viewer_generator_asks_for_a_project(capsys):
    from web_viewer.generator import main
    assert main([]) == 2
    assert "project.xml" in capsys.readouterr().err
