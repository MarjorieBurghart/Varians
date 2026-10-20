# -*- coding: utf-8 -*-
"""Le témoin pivot ne sert qu'à la synchronisation : l'interface et l'aide
parlent de « témoin pivot » et du rôle « Pivot », jamais de « manuscrit
pivot » ni de « témoin de base », qui ont un sens précis en ecdotique."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

OLD_TERMS = {
    "fr": ["manuscrit pivot", "Manuscrit pivot", "témoin de base", "Pages de base"],
    "en": ["pivot manuscript", "Pivot manuscript", "pivot-manuscript", "base witness"],
    "de": ["Pivot-Handschrift"],
    "ja": ["ピボット写本"],
    "cs": ["pivotní rukopis", "Pivotní rukopis", "pivotního rukopisu"],
    "it": ["manoscritto pivot", "Manoscritto pivot", "testimone base"],
    "ru": ["опорная рукопись", "Опорная рукопись", "опорной рукописи", "опорную рукопись", "опорного списка"],
}
PIVOT_ROLE = {"fr": "Pivot", "en": "Pivot", "de": "Pivot", "ja": "ピボット",
              "cs": "Pivotní", "it": "Pivot", "ru": "Опорный"}
PIVOT_WITNESS = {"fr": "témoin pivot", "en": "pivot witness", "de": "Pivot-Textzeugen",
                 "ja": "ピボット伝本", "cs": "pivotního svědka", "it": "testimone pivot",
                 "ru": "опорным свидетелем"}


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {string.get("key"): "".join(string.itertext()) for string in root.findall("string")}


@pytest.mark.parametrize("language", sorted(OLD_TERMS))
def test_no_old_pivot_wording_in_catalog_or_help(language):
    catalog = "\n".join(_catalog(language).values())
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    for term in OLD_TERMS[language]:
        assert term not in catalog, (language, "catalogue", term)
        assert term not in page, (language, "aide", term)


@pytest.mark.parametrize("language", sorted(OLD_TERMS))
def test_role_is_pivot_and_button_names_the_pivot_witness(language):
    catalog = _catalog(language)
    assert catalog["project.witness.base"] == PIVOT_ROLE[language]
    assert PIVOT_WITNESS[language] in catalog["project.witness.set_base"]


def test_the_tip_still_distinguishes_the_pivot_from_the_base_manuscript():
    tip = _catalog("fr")["project.witness.pivot_tip"]
    assert tip.startswith("Le témoin pivot sert uniquement")
    assert "manuscrit de base de l’édition critique" in tip
