# -*- coding: utf-8 -*-
"""L'aide du logiciel, remise à plat (V0.9.3.1) : un même plan dans les sept
langues, une présentation et un démarrage rapide en tête, aucun numéro de
version de Varians, des liens internes qui mènent tous à leur cible, des
sections qui ne s'emboîtent pas (les tests de l'aide découpent une section
jusqu'à son premier « </section> »)."""
from __future__ import annotations

import html as htmlmod
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from lxml import html

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
CHAPTERS = ("presentation", "quickstart", "concepts", "projects", "editing", "validation", "preview", "witnesses",
            "apparatus", "parts", "viewer", "publishing", "reference")


def _page(language):
    return (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {string.get("key"): htmlmod.escape(string.text or "", quote=False) for string in root.findall("string")}


def _ids(page):
    return [element.get("id") for element in html.fromstring(page).iter() if element.get("id")]


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_chapters_come_in_the_same_order_in_each_language(language):
    page = _page(language)
    assert re.findall(r'<h2 id="([\w-]+)">', page) == list(CHAPTERS), language
    # Le sommaire renvoie à chaque chapitre, dans l'ordre.
    toc = page[page.index('<div class="toc">'):page.index("</div>", page.index('<div class="toc">'))]
    assert re.findall(r'href="#([\w-]+)"', toc) == list(CHAPTERS), language


@pytest.mark.parametrize("language", LANGUAGES[1:])
def test_each_language_has_the_anchors_of_the_french_help(language):
    assert _ids(_page(language)) == _ids(_page("fr")), language


@pytest.mark.parametrize("language", LANGUAGES)
def test_no_version_of_varians_is_mentioned(language):
    page = _page(language)
    text = html.fromstring(page).text_content()
    assert not re.findall(r"\b0\.\d+\.\d+", text), language
    assert not [anchor for anchor in _ids(page) if re.fullmatch(r"v\d+", anchor)], language


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_internal_link_leads_to_its_target(language):
    page = _page(language)
    ids = set(_ids(page))
    targets = {link[1:] for link in re.findall(r'href="(#[^"]*)"', page)}
    assert not sorted(target for target in targets if target not in ids), language


@pytest.mark.parametrize("language", LANGUAGES)
def test_sections_are_not_nested_and_the_page_ends_once(language):
    page = _page(language)
    depth = 0
    for match in re.finditer(r"<(/?)section\b", page):
        depth += -1 if match.group(1) else 1
        assert depth in (0, 1), language
    assert depth == 0 and page.count("</body></html>") == 1, language


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_help_menu_lists_the_guide_to_tei_elements(language):
    """V0.9.3.1 : « Guide des éléments TEI », entre le dictionnaire latin et
    l'aide du logiciel ; les ressources en ligne disent ce qu'il ouvre."""
    catalog, page = _catalog(language), _page(language)
    start = page.index('<section id="menus">')
    menus = page[start:page.index("</section>", start)]
    positions = [menus.index(catalog[key]) for key in ("help.latin_dictionary", "help.tei_guide", "help.software")]
    assert positions == sorted(positions), language
    assert catalog["help.tei_guide"] in page[page.index("</section>", start):], language


PARENTHESES = {"fr": "parenthèses", "en": "parenthes", "de": "klammer", "ja": "括弧", "cs": "závork",
               "it": "parentes", "ru": "скобк"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_stage_directions_are_said_to_be_between_parentheses(language):
    """V0.9.3.1 : une didascalie entre parenthèses dans l'aperçu, le viewer
    et l'édition critique."""
    page = _page(language)
    for start, end in (('<h3 id="preview-rendering">', '<h2 id="witnesses">'),
                       ('<p id="viewer-text">', "</p>"), ('<section id="critical-edition">', "</section>")):
        part = page[page.index(start):]
        part = part[:part.index(end)]
        stage = part.index("<code>&lt;stage&gt;</code>")
        assert PARENTHESES[language] in part[stage:stage + 300].lower(), (language, start)
