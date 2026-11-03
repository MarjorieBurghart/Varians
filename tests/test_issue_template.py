# -*- coding: utf-8 -*-
"""Formulaire de signalement GitHub (« Nouveau signalement ») pour les
personnes qui testent Varians : ce qui s'est passé, comment le reproduire,
version (Aide → À propos…), système et mode d'installation, langue de
l'interface, rapport de « --self-test » (mêmes commandes que le LISEZMOI
de l'archive), fichiers joints."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FORM = ROOT / ".github" / "ISSUE_TEMPLATE" / "signalement.yml"
LANGUAGES = ("Français", "English", "Deutsch", "日本語", "Čeština", "Italiano", "Русский")
SYSTEMS = ("Windows", "macOS (Apple Silicon : M1, M2…)", "macOS (Intel)", "Linux")


def _catalog(language):
    return {node.get("key"): node.text for node in ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()}


def test_the_form_asks_what_a_report_needs():
    text = FORM.read_text(encoding="utf-8")
    # Commandes de vérification : celles du LISEZMOI de l'archive, et celle
    # du mode source.
    readme = (ROOT / "packaging" / "readme" / "LISEZMOI.txt").read_text(encoding="utf-8")
    for command in ("start /wait Varians.exe --self-test", "/Applications/Varians.app/Contents/MacOS/Varians --self-test",
                    "./Varians --self-test"):
        assert command in text and command in readme, command
    assert "python editeur_tei.py --self-test" in text
    # Où lire la version, avec les libellés de l'interface.
    for language in ("fr", "en"):
        catalog = _catalog(language)
        assert f"{catalog['menu.help']} → {catalog['help.about']}" in text, language
    for name in LANGUAGES + SYSTEMS:
        assert name in text, name


def test_the_form_is_a_valid_github_issue_form():
    yaml = pytest.importorskip("yaml")
    form = yaml.safe_load(FORM.read_text(encoding="utf-8"))
    assert form["name"] and form["description"] and isinstance(form["body"], list)
    fields = {item["id"]: item for item in form["body"] if "id" in item}
    assert len(fields) == len([item for item in form["body"] if item["type"] != "markdown"])
    for item in form["body"]:
        assert item["type"] in {"markdown", "textarea", "input", "dropdown", "checkboxes"}
        if item["type"] != "markdown":
            assert item["attributes"]["label"], item
    for required in ("what", "steps", "version", "system", "installation"):
        assert fields[required]["validations"]["required"] is True, required
    assert tuple(fields["system"]["attributes"]["options"][:4]) == SYSTEMS
    assert tuple(fields["language"]["attributes"]["options"]) == LANGUAGES
    assert fields["self_test"]["attributes"]["render"] == "json"
