# -*- coding: utf-8 -*-
"""Aide × 7 (red team) : les questions que pose désormais Varians y sont
décrites avec les libellés de leurs boutons, dans la section concernée :
fichier modifié hors de Varians et encodage, à l'enregistrement ; schéma
d'un autre site que celui de la TEI, avec la validation RELAX NG ; règles
Schematron hors du projet, avec les règles Schematron."""
from __future__ import annotations

import html as htmlmod
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
SECTIONS = {
    "saving": ("file.changed.overwrite", "file.changed.reload", "common.cancel", "file.encoding.fix"),
    "rng-background": ("schemas.site.allow", "schemas.site.refuse", "rng.status.site_refused",
                       "toolbar.validate_rng"),
    "schematron": ("schematron.outside.apply", "schematron.outside.skip", "schematron.status.refused",
                   "toolbar.validate_rng"),
}


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {string.get("key"): htmlmod.escape(string.text or "", quote=False) for string in root.findall("string")}


def _section(page, anchor):
    """Le texte de la section *anchor* : jusqu'à sa fin (</section>), ou
    jusqu'au titre suivant pour un simple titre."""
    start = page.index(f'id="{anchor}"')
    if page.rfind("<section", 0, start) == page.rfind("<", 0, start):
        return page[start:page.index("</section>", start)]
    ends = [index for index in (page.find("<h2", start), page.find("<h3", start + 1)) if index != -1]
    return page[start:min(ends)]


@pytest.mark.parametrize("language", LANGUAGES)
@pytest.mark.parametrize("anchor", SECTIONS)
def test_the_new_questions_are_described_with_their_buttons(language, anchor):
    catalog = _catalog(language)
    section = _section((ROOT / "help" / f"{language}.html").read_text(encoding="utf-8"), anchor)
    missing = [key for key in SECTIONS[anchor] if catalog[key] not in section]
    assert not missing, (language, anchor, [catalog[key] for key in missing])


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_tei_site_is_named(language):
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    assert "tei-c.org" in _section(page, "rng-background"), language


# Red team 2 (robustesse et cohérence), dans la section concernée.
NUMBERS = {"fr": ("10 000", "2 000 000"), "en": ("10,000", "2,000,000"), "de": ("10.000", "2.000.000"),
           "it": ("10.000", "2.000.000"), "cs": ("10 000", "2 000 000"), "ru": ("10 000", "2 000 000"),
           "ja": ("10,000", "2,000,000")}


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_second_red_team_is_described(language):
    catalog = _catalog(language)
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    long_line, inclusions = NUMBERS[language]
    start = page.index('id="editing"')
    editing = page[start:page.index("<h2", start + 5)]          # tout le chapitre
    assert "U+2029" in editing and "&amp;#x2029;" in editing and long_line in editing
    assert catalog["file.paragraph_separator.title"] in editing
    assert catalog["alignment.damaged.title"] in _section(page, "witness-sync")
    assert catalog["diagnostics.refresh"] in _section(page, "witness-sync")
    assert inclusions in _section(page, "xinclude")
    viewer = page[page.index('id="viewer-text"'):page.index('id="viewer-text-choice"')]
    assert 'break="no"' in viewer and "<i>om.</i>" in viewer and "lacuna incipit" in viewer
