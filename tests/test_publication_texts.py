# -*- coding: utf-8 -*-
"""Textes des feuilles livrées avec Varians (V0.9.3.1) : édition critique,
apparat en notes, Vue XSLT / CSS. Ils viennent des catalogues i18n, dans la
langue de l'interface (paramètres ``langue`` et ``catalogues``) ; chaque clé
lue par une feuille existe dans les sept catalogues, et le français inscrit
dans la feuille, pour un usage hors de Varians, est celui du catalogue
français."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
SHEETS = ("edition-critique.xsl", "apparat-commun.xsl", "apparat-en-notes.xsl", "tei-to-html.xsl")
XSL = "{http://www.w3.org/1999/XSL/Transform}"


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {string.get("key"): "".join(string.itertext()) for string in root.findall("string")}


def _keys_used():
    keys = {}
    for name in SHEETS:
        text = (ROOT / "rendering" / name).read_text(encoding="utf-8")
        for key in re.findall(r"'((?:publication|viewer)\.[\w.]+)'", text):
            keys.setdefault(key, name)
    return keys


def _french_in_the_stylesheets():
    """Le français de repli : ``<string key>`` de ``f:textes-fr``
    (apparat-commun.xsl) et ``<xsl:when test="$cle = '…'">`` du modèle
    ``texte-fr`` (tei-to-html.xsl)."""
    common = ET.parse(ROOT / "rendering" / "apparat-commun.xsl").getroot()
    variable = next(v for v in common.iter(f"{XSL}variable") if v.get("name") == "f:textes-fr")
    french = {s.get("key"): "".join(s.itertext()) for s in variable.iter("string")}
    preview = ET.parse(ROOT / "rendering" / "tei-to-html.xsl").getroot()
    template = next(t for t in preview.iter(f"{XSL}template") if t.get("name") == "texte-fr")
    for when in template.iter(f"{XSL}when"):
        key = re.fullmatch(r"\$cle = '([\w.]+)'", when.get("test")).group(1)
        french[key] = "".join(when.itertext())
    return french


def test_every_text_of_the_stylesheets_is_in_the_seven_catalogs():
    keys = _keys_used()
    assert {"publication.critique.title", "publication.not_available", "viewer.form.sic", "publication.page"} <= set(keys)
    for language in LANGUAGES:
        catalog = _catalog(language)
        missing = sorted(f"{key} ({sheet})" for key, sheet in keys.items() if not catalog.get(key))
        assert not missing, (language, missing)


def test_the_french_written_in_the_stylesheets_is_the_french_catalog():
    french, catalog, keys = _french_in_the_stylesheets(), _catalog("fr"), _keys_used()
    assert set(french) == set(keys)
    assert {key: text for key, text in french.items() if catalog[key] != text} == {}


def test_the_conventions_of_the_apparatus_stay_latin():
    common = (ROOT / "rendering" / "apparat-commun.xsl").read_text(encoding="utf-8")
    for latin in ("'om.'", "'add.'", "'lacuna incipit'", "'lacuna desinit'"):
        assert latin in common, latin
