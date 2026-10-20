# -*- coding: utf-8 -*-
"""Erreurs de project.xml traduisibles : l'erreur porte une clé des
catalogues et ses paramètres ; l'interface affiche le message dans sa langue,
l'export en ligne de commande garde le texte français."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from project_config import ProjectConfigError, load_project

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")


def _project_with_pivot(tmp_path, pivot):
    path = tmp_path / "project.xml"
    shutil.copy2(ROOT / "project.xml", path)
    path.write_text(path.read_text(encoding="utf-8").replace('<witnesses base="T1">', f'<witnesses base="{pivot}">'),
                    encoding="utf-8")
    return path


def test_unknown_pivot_witness_is_a_translatable_error(tmp_path):
    with pytest.raises(ProjectConfigError) as caught:
        load_project(_project_with_pivot(tmp_path, "Z"))
    error = caught.value
    assert isinstance(error, ValueError)                     # appels existants inchangés
    assert error.key == "project.error.unknown_pivot"
    assert error.values == {"witness": "Z", "witnesses": "T1, T2, P"}
    assert str(error).startswith("Témoin pivot inconnu")
    assert "de base" not in str(error)


def test_unknown_pivot_message_exists_in_the_seven_catalogs():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        text = next(s.text for s in root.findall("string") if s.get("key") == "project.error.unknown_pivot")
        assert "{witness}" in text and "{witnesses}" in text, language
