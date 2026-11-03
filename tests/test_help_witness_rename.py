# -*- coding: utf-8 -*-
"""Aide × 7 (V0.9.4.0) : « Changer le sigle d'un témoin », sous « Sigle et
identifiant d'un témoin », avec les libellés du menu et des boutons, ce qui
change, les copies .bak, l'échange de deux sigles et les citations du sigle
à vérifier."""
from __future__ import annotations

import html as htmlmod
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
LABELS = ("menu.project_settings", "witness_rename.button", "witness_rename.preview", "witness_rename.apply",
          "project.witness.edit")


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {string.get("key"): htmlmod.escape(string.text or "", quote=False) for string in root.findall("string")}


def _section(language):
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    start = page.index('id="witness-rename"')
    return page[start:page.index('<h3 id="pivot-scaffold">', start)]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_help_explains_how_to_change_a_siglum(language):
    catalog = _catalog(language)
    section = _section(language)
    missing = [catalog[key] for key in LABELS if catalog[key] not in section]
    assert not missing, (language, missing)
    for text in ("P2", ".bak", "P-p0001", "alignments/P.json", "@wit", "@edRef", "P1 → X", "P2 → P1", "X → P2"):
        assert text in section, (language, text)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_help_on_sigla_comes_first(language):
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    assert page.index('id="witness-siglum"') < page.index('id="witness-rename"') < page.index('id="pivot-scaffold"')
