# -*- coding: utf-8 -*-
"""Chaque clé de traduction écrite en clair dans le code existe dans les sept
catalogues i18n (sinon l'interface afficherait la clé elle-même)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
# _t("clé", …), tr("clé", …) ou self.tr("clé", …)
KEY_CALL = re.compile(r"""\b(?:_t|tr|self\.tr)\(\s*(['"])([A-Za-z0-9_.\-]+)\1""")


def _used_keys():
    used = {}
    for path in sorted(ROOT.glob("*.py")) + sorted((ROOT / "web_viewer").glob("*.py")):
        for match in KEY_CALL.finditer(path.read_text(encoding="utf-8")):
            key = match.group(2)
            if key.endswith("."):          # préfixe d'une clé complétée à l'exécution
                continue
            used.setdefault(key, path.name)
    return used


def test_every_literal_translation_key_exists_in_the_seven_catalogs():
    used = _used_keys()
    assert len(used) > 500
    assert "documents.unsaved.text" in used
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key") for string in root.findall("string")}
        missing = sorted(f"{key} ({used[key]})" for key in used if key not in catalog)
        assert not missing, (language, missing)


def test_each_help_explains_auxiliary_documents_with_the_menu_labels():
    labels = ("documents.menu", "documents.add.menu", "documents.new.menu",
              "documents.remove.menu", "documents.edition_tab",
              # Onglets affichés (V0.8.9.0)
              "menu.display", "documents.view.choose", "documents.tab.hide", "documents.tab.rename",
              "references.action")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="auxiliary-documents">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        assert "&lt;documents&gt;" in section
        assert "<code>label</code>" in section, language


def test_each_help_explains_references_with_the_command_labels():
    labels = ("references.action", "references.goto", "references.back", "references.recheck",
              "references.column.problem")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="references">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("F12", "Alt+←", "#bernard", "personnes.xml#bernard", 'source="ids"',
                     'href="#auxiliary-documents"'):
            assert text in section, (language, text)
        # Raccourcis principaux
        assert "<td>F12</td>" in page and "<td>Alt+←</td>" in page, language


def test_each_help_explains_the_apparatus_debugging_with_the_command_labels():
    labels = ("menu.help", "apparatus.menu", "apparatus.search", "apparatus.query.add",
              "apparatus.query.edit", "apparatus.query.remove", "references.action")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="apparatus-debug">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("&lt;listWit&gt;", "&lt;rdgGrp&gt;", "&lt;xpathQueries&gt;", "tei:", "#A"):
            assert text in section, (language, text)
        # Renvoi depuis le chapitre « Recherche XPath ».
        chapter = page[page.index('<h2 id="xpath">'):]
        chapter = chapter[:chapter.index("<h2", 4)]
        assert 'href="#apparatus-debug"' in chapter, language


def test_each_help_explains_background_validation():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="rng-background">'):]
        section = section[:section.index("</section>")]
        for text in (catalog["rng.status.running"], catalog["toolbar.validate_rng"], "<kbd>F8</kbd>", "TEI_ALL"):
            assert text in section, (language, text)


def test_each_help_explains_assembled_editions():
    labels = ("rng.column.document", "references.action", "apparatus.menu", "parts.webgen.continue",
              "documents.tab.rename", "documents.remove.menu")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="xinclude">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("xi:include", 'xpointer="s02"', "element(/1/2/1/1)", "&lt;locus", "@wit",
                     "&lt;teiHeader&gt;", "<kbd>F12</kbd>", "<kbd>Ctrl+S</kbd>", "xi:fallback"):
            assert text in section, (language, text)
        version = page[page.index('<section id="v0900">'):]
        assert 'href="#xinclude"' in version[:version.index("</section>")], language
