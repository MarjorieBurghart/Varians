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
    labels = ("rng.column.document", "references.action", "apparatus.menu",
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


def test_each_help_explains_the_synchronization_across_parts():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="xinclude">'):]
        section = section[:section.index("</section>")]
        for key in ("manuscript.mark_page", "folio.split.button", "documents.tab.hide"):
            assert catalog[key] in section, (language, key)
        for text in ('&lt;lb edRef="#A"/&gt;', "&lt;pb", "&lt;facsimile&gt;"):
            assert text in section, (language, text)
        version = page[page.index('<section id="v0910">'):]
        assert 'href="#xinclude"' in version[:version.index("</section>")], language


def test_each_help_has_a_guide_for_editions_in_parts():
    """Mode d'emploi d'un projet avec XInclude (V0.9.1.1, demandé à la
    préparation de cette version), et textes synchronisés à part."""
    labels = ("menu.project_settings", "diagnostics.menu", "diagnostics.refresh", "documents.tab.hide")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        guide = page[page.index('<section id="xinclude-guide">'):]
        guide = guide[:guide.index("</section>")]
        for key in labels:
            assert catalog[key] in guide, (language, key)
        ok = catalog["status.structure.ok"].format(base="B", count=8)
        for text in ('xmlns:xi="http://www.w3.org/2001/XInclude"', 'xpointer="s02"', "alignments/s02/B.json",
                     "&lt;parts&gt;", '&lt;part name="s02" base="B"/&gt;', "xmllint --xinclude",
                     "<kbd>Ctrl+S</kbd>", 'href="#xinclude"', ok):
            assert text in guide, (language, text)
        section = page[page.index('<section id="xinclude">'):]
        section = section[:section.index("</section>")]
        assert 'href="#xinclude-guide"' in section, language
        for text in (catalog["manuscript.text_absent"], "alignments/s02/", '&lt;part name="s02" base="B"/&gt;'):
            assert text in section, (language, text)
        version = page[page.index('<section id="v0911">'):]
        assert 'href="#xinclude-guide"' in version[:version.index("</section>")], language


def test_each_help_explains_the_selections_shared_with_the_fragment_editor():
    """Sélections partagées entre l'aperçu XSLT / CSS et l'éditeur de
    fragment, crayon ✎ sans synchronisation des témoins (V0.9.1.2)."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        heading = re.search(r'<h2 id="(edition|editing)">', page)
        section = page[heading.start():page.index("<h2", heading.end())]
        for text in ("✎", '&lt;lb break="no"/&gt;', catalog["fragment.apply_xml"]):
            assert text in section, (language, text)
        version = page[page.index('<section id="v0912">'):]
        version = version[:version.index("</section>")]
        assert f'href="#{heading.group(1)}"' in version and "0.9.1.3" in version, language
        # Les limites de l'édition en parties annoncent la version suivante :
        # voir le test de la V0.9.1.3.


def test_each_help_explains_the_lacunae_and_the_page_witnesses_of_a_text():
    """Lacunes des témoins et témoins par pages dans un texte synchronisé à
    part (V0.9.1.3)."""
    import html
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="lacunae">'):]
        section = section[:section.index("</section>")]
        for key in ("manuscript.lacuna", "manuscript.lacuna.pivot", "apparatus.check.incomplete"):
            assert html.escape(catalog[key], quote=False) in section, (language, key)
        # Encodage TEI : dans une leçon (model.rdgPart n'est admis que dans
        # <rdg> et <lem>), le témoin de la leçon ou celui du @wit de la balise.
        for text in ("&lt;rdg wit=\"#T2\"&gt;&lt;lacunaStart/&gt;", "&lt;lacunaEnd/&gt;",
                     "&lt;rdg wit=\"#T2 #P\"&gt;… &lt;lacunaStart wit=\"#P\"/&gt;&lt;/rdg&gt;"):
            assert text in section, (language, text)
        parts = page[page.index('<section id="xinclude">'):]
        parts = parts[:parts.index("</section>")]
        for text in ('&lt;locus from="13r" to="14r" target="#s04"&gt;', "&lt;pb edRef=\"#C\"/&gt;",
                     html.escape(catalog["manuscript.mark_page"], quote=False)):
            assert text in parts, (language, text)
        version = page[page.index('<section id="v0913">'):]
        assert 'href="#lacunae"' in version[:version.index("</section>")], language


def test_each_help_explains_how_to_follow_a_manuscript_in_its_own_order():
    """Suivre un manuscrit dans son propre ordre (V0.9.1.4)."""
    import html
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="witness-route">'):]
        section = section[:section.index("</section>")]
        for text in ("⤺", '&lt;pb edRef="#M" n="45v"/&gt;', '&lt;locus from="80r" target="#s04"&gt;',
                     html.escape(catalog["manuscript.text_absent"], quote=False),
                     html.escape(catalog["project.settings.title"], quote=False)):
            assert text in section, (language, text)
        assert page.index('<section id="witness-route">') < page.index('<section id="xinclude">'), language
        # Plus rien d'annoncé pour la 0.9.1.4 dans les éditions assemblées ;
        # leurs limites et le mode d'emploi renvoient au parcours.
        parts = page[page.index('<section id="xinclude">'):page.index('<section id="v0900">')]
        assert "0.9.1.4" not in parts, language
        assert parts.count('href="#witness-route"') == 2, language
        version = page[page.index('<section id="v0914">'):]
        assert 'href="#witness-route"' in version[:version.index("</section>")], language
        assert page.index('<section id="v0913">') < page.index('<section id="v0914">'), language


def test_each_help_explains_the_preview_of_an_assembled_edition():
    """La Vue XSLT / CSS d'une édition assemblée (V0.9.1.5) : ✎ dans le
    fichier du paragraphe, clic, reports ; plus de lecture seule."""
    import html
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        assert "preview.assembled.read_only" not in catalog, language
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        parts = page[page.index('<section id="xinclude">'):page.index('<section id="v0900">')]
        section = parts[parts.index('<h3 id="xinclude-preview">'):]
        section = section[:section.index("<h3", 1)]
        label = catalog["fragment.label.file"].format(index=7, total=12, file="s03.xml")
        for text in ("✎", html.escape(label, quote=False), "<kbd>Ctrl+S</kbd>", "xi:include"):
            assert text in section, (language, text)
        # Les parties et le mode d'emploi renvoient à cette sous-section.
        assert parts.count('href="#xinclude-preview"') == 2, language
        version = page[page.index('<section id="v0915">'):]
        assert 'href="#xinclude-preview"' in version[:version.index("</section>")], language
        assert page.index('<section id="v0914">') < page.index('<section id="v0915">'), language

