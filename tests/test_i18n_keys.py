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
        # V0.9.2.9 : l'étiquette nomme l'élément ; le titre de chaque sermon
        # est aussi modifiable.
        label = catalog["fragment.label.file"].format(element="<p>", index=10, total=16, file="s03.xml")
        for text in ("✎", html.escape(label, quote=False), "<kbd>Ctrl+S</kbd>", "xi:include"):
            assert text in section, (language, text)
        # Les parties et le mode d'emploi renvoient à cette sous-section.
        assert parts.count('href="#xinclude-preview"') == 2, language
        version = page[page.index('<section id="v0915">'):]
        assert 'href="#xinclude-preview"' in version[:version.index("</section>")], language
        assert page.index('<section id="v0914">') < page.index('<section id="v0915">'), language


def test_each_help_explains_the_web_export_of_an_assembled_edition():
    """L'export web d'une édition assemblée (V0.9.1.6) : texte des parties,
    textes synchronisés à part, flèches, lacunes, enregistrement avant
    l'export ; plus de question « Exporter quand même »."""
    import html
    old_question = {"fr": "Exporter quand même", "en": "Export anyway", "de": "Trotzdem exportieren",
                    "it": "Esporta comunque", "cs": "Přesto exportovat", "ja": "それでも書き出す",
                    "ru": "Всё равно экспортировать"}
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        assert not [key for key in catalog if key.startswith("parts.webgen.")], language
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        assert old_question[language] not in page, language
        parts = page[page.index('<section id="xinclude">'):page.index('<section id="v0900">')]
        section = parts[parts.index('<h3 id="xinclude-web">'):]
        section = section[:section.index("<h3", 1)]
        for text in (html.escape(catalog["toolbar.generate_web"], quote=False),
                     html.escape(catalog["manuscript.text_absent"], quote=False),
                     "⤺", "<code>alignments/s02/</code>", 'href="#lacunae"',
                     '<code>parse="text"</code>', "<code>xi:fallback</code>"):
            assert text in section, (language, text)
        # Les limites et le mode d'emploi renvoient à cette sous-section, le
        # viewer web aussi ; rien n'est plus annoncé pour l'export web.
        assert parts.count('href="#xinclude-web"') == 2, language
        viewer = page[page.index('id="viewer"'):]
        viewer = viewer[:viewer.index("<h2", 10)]
        assert 'href="#xinclude-web"' in viewer and "⤺" in viewer, language
        version = page[page.index('<section id="v0916">'):]
        version = version[:version.index("</section>")]
        assert 'href="#xinclude-web"' in version and 'href="#viewer"' in version, language
        assert page.index('<section id="v0915">') < page.index('<section id="v0916">'), language


def test_each_help_announces_the_tabs_of_version_0917():
    """Onglet du document affiché bien distinct (V0.9.1.7)."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0917">'):]
        version = version[:version.index("</section>")]
        assert 'href="#auxiliary-documents"' in version, language
        assert page.index('<section id="v0916">') < page.index('<section id="v0917">'), language


def test_each_help_explains_the_transformation_scenarios_with_the_command_labels():
    """Scénarios de transformation XSLT (V0.9.2.0)."""
    labels = ("menu.file", "menu.transform_scenarios", "toolbar.transform", "toolbar.generate_web",
              "transform.group.project", "transform.group.predefined", "transform.add", "transform.edit",
              "transform.duplicate", "transform.remove", "transform.run", "transform.preview",
              "transform.predefined.varians-html", "transform.engine.lxml", "transform.engine.saxon",
              "transform.source.edition", "transform.source.current", "transform.cancel", "common.open",
              "common.open_folder")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="transformations">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("&lt;transformations&gt;", "${varians}/", "installer_dependances.bat", "xsl:result-document",
                     "<code>css</code>", "Ctrl+Shift+T", "publications/edition.html", 'href="#auxiliary-documents"'):
            assert text in section, (language, text)
        assert "<td>Ctrl+Shift+T</td>" in page, language


def test_each_help_announces_the_scenarios_of_version_0920():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0920">'):]
        version = version[:version.index("</section>")]
        assert 'href="#transformations"' in version and "installer_dependances.bat" in version, language
        assert page.index('<section id="v0917">') < page.index('<section id="v0920">'), language
        assert page.index('<section id="xinclude-guide">') < page.index('<section id="transformations">') \
            < page.index('<section id="v0900">'), language


def test_each_help_explains_how_to_edit_stylesheets():
    """Feuilles XSLT éditées dans Varians (V0.9.2.1)."""
    labels = ("documents.menu", "documents.add.menu", "documents.new_stylesheet.menu", "transform.open_stylesheet",
              "xslt_check.action", "transform.engine.lxml", "transform.engine.saxon", "transform.duplicate")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="xslt-editing">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("<code>xslt/</code>", "<code>xml/</code>", "${varians}/", "<kbd>F8</kbd>", "<code>version=\"1.0\"</code>",
                     "xsl:import", "xsl:include", "custom-elements.xml", 'href="#transformations"',
                     'href="#auxiliary-documents"'):
            assert text in section, (language, text)
        assert page.index('<section id="transformations">') < page.index('<section id="xslt-editing">') \
            < page.index('<section id="v0900">'), language


def test_each_help_announces_stylesheet_editing_in_version_0921():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0921">'):]
        version = version[:version.index("</section>")]
        assert 'href="#xslt-editing"' in version and "<code>xslt/</code>" in version, language
        assert page.index('<section id="v0920">') < page.index('<section id="v0921">'), language


def test_each_help_explains_the_tei_stylesheets():
    """Scénarios TEI, personnalisation, mises à jour et licence (V0.9.2.2)."""
    labels = ("tei_stylesheets.menu", "tei_stylesheets.check", "tei_stylesheets.install", "tei_stylesheets.later",
              "tei_stylesheets.show_licence", "transform.predefined.tei-html", "transform.predefined.tei-txt",
              "transform.predefined.tei-markdown", "transform.predefined.tei-latex", "transform.open_stylesheet",
              "transform.open_stylesheet.create", "transform.duplicate", "menu.transform_scenarios")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="tei-stylesheets">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("github.com/TEIC/Stylesheets", "${tei}/", "<code>publications/tei/</code>", "<code>xslt/</code>",
                     "<code>xslt/tei-html.xsl</code>", "http://www.tei-c.org/release/xml/tei/stylesheet/",
                     "xsl:import", 'xmlns="http://www.w3.org/1999/xhtml"', "numberHeadings", "documentationLanguage",
                     "BSD", "CC BY-SA 3.0", "<code>LICENCE</code>", "<kbd>F8</kbd>", "Oxygen", "xelatex",
                     'href="#transformations"', 'href="#xslt-editing"'):
            assert text in section, (language, text)
        assert page.index('<section id="xslt-editing">') < page.index('<section id="tei-stylesheets">') \
            < page.index('<section id="v0900">'), language


def test_each_help_announces_the_tei_stylesheets_in_version_0922():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0922">'):]
        version = version[:version.index("</section>")]
        assert 'href="#tei-stylesheets"' in version and "<code>publications/tei/</code>" in version, language
        assert page.index('<section id="v0921">') < page.index('<section id="v0922">'), language


def test_each_help_explains_the_schematron_rules():
    """Règles appliquées, messages, barre d'état, règles incorrectes, Saxon
    (V0.9.2.3)."""
    labels = ("rng.column.origin", "rng.level.info", "schematron.status.valid", "schematron.status.rules_error",
              "schematron.status.saxon_missing", "schematron.status.disabled", "file.save_rng_invalid.title",
              "rng.panel.title")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="schematron">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("SchXslt2", "http://purl.oclc.org/dsdl/schematron", "<code>tei_all.rng</code>",
                     "<code>.sch</code>", "<code>@role</code>", "<code>@severity</code>", "<code>nonfatal</code>",
                     "<kbd>F8</kbd>", "MIT", "saxonche", "XPath", "<code>sch:phase</code>",
                     'href="#rng-background"'):
            assert text in section, (language, text)
        assert page.index('<section id="rng-background">') < page.index('<section id="schematron">') \
            < page.index('<section id="v0892">'), language


def test_each_help_announces_the_schematron_rules_in_version_0923():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0923">'):]
        version = version[:version.index("</section>")]
        assert 'href="#schematron"' in version and "Schematron" in version, language
        assert page.index('<section id="v0922">') < page.index('<section id="v0923">'), language


def test_each_help_explains_schematron_phases_and_files():
    """Phase d'une déclaration, règles incorrectes dans le panneau, fichiers
    .sch dans Varians : ajout, création, vérification, complétion
    (V0.9.2.4)."""
    labels = ("rng.origin.schematron_rules", "schematron_check.action", "documents.new_schematron.menu",
              "documents.add.menu", "schematron.status.rules_error", "rng.column.document")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="schematron">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ('phase="lecons"', "<code>#ALL</code>", "<code>#DEFAULT</code>", "<code>defaultPhase</code>",
                     "<code>xml/regles.sch</code>", "<code>xml/</code>", "<code>severity</code>",
                     "<code>queryBinding</code>", "<code>sch:group</code>", "apparat.sch"):
            assert text in section, (language, text)


def test_each_help_announces_schematron_phases_and_files_in_version_0924():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0924">'):]
        version = version[:version.index("</section>")]
        assert 'href="#schematron"' in version and "<code>phase</code>" in version, language
        assert catalog["documents.new_schematron.menu"] in version, language
        assert page.index('<section id="v0923">') < page.index('<section id="v0924">'), language


def test_each_help_explains_the_rules_dialog_unsaved_rules_2020_and_xsd():
    """Boîte des déclarations, règles non enregistrées, norme 2020/2025,
    règles d'un XSD (V0.9.2.5)."""
    labels = ("schematron.dialog.title", "schematron.panel.rules_button")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="schematron">'):]
        section = section[:section.index("</section>")]
        for key in labels:
            assert catalog[key] in section, (language, key)
        for text in ("<code>&lt;?xml-model?&gt;</code>", "<kbd>Ctrl+Z</kbd>", "regles.sch", "<code>sch:library</code>",
                     "<code>@visit-each</code>", "<code>xs:appinfo</code>", "<code>xs:include</code>",
                     "<code>xs:import</code>", "<code>sch:include</code>"):
            assert text in section, (language, text)


def test_each_help_announces_version_0925():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0925">'):]
        version = version[:version.index("</section>")]
        assert 'href="#schematron"' in version and catalog["schematron.dialog.title"] in version, language
        assert page.index('<section id="v0924">') < page.index('<section id="v0925">'), language


def test_each_help_explains_the_unsaved_included_files():
    """Fichiers inclus non enregistrés (V0.9.2.6) : l'info-bulle citée en
    exemple ; les limites ne disent plus qu'un fichier inclus est lu tel
    qu'il est enregistré."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="schematron">'):]
        section = section[:section.index("</section>")]
        tip = catalog["schematron.tip.unsaved_included"].format(name="regles.sch", files="motifs.sch")
        assert tip in section and "<code>sch:extends</code>" in section, language
        limits = section[section.rindex("<p><strong>"):]
        assert "<code>sch:include</code>" not in limits, language


def test_each_help_announces_version_0926():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0926">'):]
        version = version[:version.index("</section>")]
        assert 'href="#schematron"' in version and "<code>sch:include</code>" in version, language
        assert page.index('<section id="v0925">') < page.index('<section id="v0926">'), language


def _label(catalog, key):
    """Un intitulé de champ sans ses deux-points (« Format du résultat »)."""
    return catalog[key].rstrip(" :：")


def test_each_help_explains_the_scenarios_of_version_0927():
    """Sous-groupe TEI Stylesheets, format du résultat, pré-passage, paramètres
    sans type, ${pivot} (V0.9.2.7)."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="transformations">'):]
        section = section[:section.index("</section>")]
        for key in ("transform.group.tei", "transform.predefined.edition-critique"):
            assert catalog[key] in section, (language, key)
        for key in ("transform.scenario.package", "transform.scenario.prepare"):
            assert _label(catalog, key) in section, (language, key)
        for text in ("${pivot}", "${tei}/", "xs:boolean", 'href="#critical-edition"', 'href="#tei-stylesheets"'):
            assert text in section, (language, text)


def test_each_help_explains_the_new_tei_formats():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="tei-stylesheets">'):]
        section = section[:section.index("</section>")]
        for key in ("transform.group.tei", "transform.predefined.tei-pages", "transform.predefined.tei-docx",
                    "transform.predefined.tei-odt", "transform.predefined.tei-epub"):
            assert catalog[key] in section, (language, key)
        for text in ("<code>splitLevel</code>", "<code>publications/tei/pages/index.html</code>",
                     "<code>edition.docx</code>", "<code>edition.odt</code>", "<code>edition.epub</code>",
                     "<code>apparat-en-notes.xsl</code>", "lacuna incipit", 'type="apparatus"', 'place="end"',
                     'href="#critical-edition"'):
            assert text in section, (language, text)


def test_each_help_explains_the_critical_edition():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="critical-edition">'):]
        section = section[:section.index("</section>")]
        assert catalog["transform.predefined.edition-critique"] in section, language
        for text in ("<code>temoin-de-base</code>", "${pivot}", "<code>aucun</code>", "<code>montrer-folios</code>",
                     "<code>montrer-numeros-de-vers</code>", "<code>sauts-lb</code>", "lacuna incipit",
                     "lacuna desinit", "<code>&lt;rdgGrp&gt;</code>", "<code>publications/edition-critique.html</code>",
                     "<code>@n</code>", "om.", "add.", 'href="#tei-stylesheets"', 'href="#transformations"'):
            assert text in section, (language, text)
        assert page.index('<section id="tei-stylesheets">') < page.index('<section id="critical-edition">') \
            < page.index('<section id="v0900">'), language


def test_the_apparatus_is_called_by_numbers_and_the_notes_by_letters():
    """Édition critique : l'apparat, nombreux, appelé par des chiffres ; les
    notes par des lettres (a, b… z, aa…)."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="critical-edition">'):]
        section = section[:section.index("</section>")]
        letters = section.index("aa…")
        # En japonais, le complément précède le nom : « 文字（…）で呼び出される … Notes ».
        anchor = "Apparat critique</strong>" if language == "ja" else "<strong>Notes</strong>"
        assert letters > section.index(anchor), language


def test_each_help_shows_the_list_of_witnesses_of_the_critical_edition():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = page[page.index('<section id="critical-edition">'):]
        section = section[:section.index("</section>")]
        assert catalog["transform.param.pivot"].format(witness="T1") in section, language
        assert catalog["transform.param.no_witness"] in section, language


def test_each_help_announces_version_0927():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = page[page.index('<section id="v0927">'):]
        version = version[:version.index("</section>")]
        for link in ('href="#critical-edition"', 'href="#tei-stylesheets"', 'href="#transformations"'):
            assert link in version, (language, link)
        assert page.index('<section id="v0926">') < page.index('<section id="v0927">'), language


def test_the_documents_menu_names_xml_and_xslt():
    root = ET.parse(ROOT / "i18n" / "fr.xml").getroot()
    catalog = {string.get("key"): string.text for string in root.findall("string")}
    assert catalog["documents.menu"] == "Documents XML / XSLT du projet…"
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        label = next(string.text for string in root.findall("string") if string.get("key") == "documents.menu")
        assert "XSLT" in label, language


def _help_section(page, section_id):
    section = page[page.index(f'<section id="{section_id}">'):]
    return section[:section.index("</section>")]


def test_each_help_explains_search_and_replace():
    """V0.9.2.8 : menus Éditer et Rechercher, casse, expressions régulières,
    chercher et remplacer."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "search-replace")
        for key in ("menu.edit", "menu.search", "edit.format_xml", "search.find", "search.case", "search.regex",
                    "replace.one", "replace.all"):
            assert catalog[key] in section, (language, key)
        assert catalog["search.replace"].rstrip("…") in section, language
        assert catalog["replace.with.label"].rstrip(" :：") in section, language
        for text in ("Ctrl+H", "Ctrl+F", "F3", "Ctrl+Z", "<strong>Aa</strong>", "<strong>.*</strong>",
                     "<code>\\1</code>", "<code>\\g&lt;", "<code>re</code>", 'href="#xpath"',
                     '<code>wit="#(\\w+)"</code>'):
            assert text in section, (language, text)
        assert page.index('<section id="critical-edition">') < page.index('<section id="search-replace">') \
            < page.index('<section id="v0900">'), language


def test_each_help_lists_ctrl_h_among_the_shortcuts():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        ctrl_f = page.index("<tr><td>Ctrl+F</td>")
        assert page.index("<tr>", ctrl_f + 1) == page.index("<tr><td>Ctrl+H</td>"), language


def test_each_help_announces_version_0928():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = _help_section(page, "v0928")
        assert 'href="#search-replace"' in version, language
        assert page.index('<section id="v0927">') < page.index('<section id="v0928">'), language


def test_each_help_names_indent_as_a_command_of_the_edit_menu():
    """V0.9.2.8 : « Indenter le XML » n'est plus un bouton de la barre
    d'outils, mais une commande du menu Éditer."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        command = f"<strong>{catalog['menu.edit']} → {catalog['edit.format_xml']}</strong>"
        heading = page.index('<h2 id="formatage">' if language == "fr" else '<h2 id="formatting">')
        assert command in page[heading:page.index("<h2", heading + 1)], language
        assert f"<strong>{catalog['toolbar.format_xml']}</strong>" not in page, language


def test_each_help_has_a_quick_reference_of_regular_expressions():
    """V0.9.2.8 : la syntaxe des expressions régulières, dans un tableau de
    la section « Rechercher et remplacer »."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "search-replace")
        assert '<h3 id="regex-syntax">' in section and "<table>" in section, language
        table = section[section.index('<h3 id="regex-syntax">'):]
        for text in ("<code>.</code>", "<code>\\d</code>", "<code>\\w</code>", "<code>\\s</code>",
                     "<code>[^&lt;]</code>", "<code>*</code>", "<code>+</code>", "<code>?</code>",
                     "<code>{2,4}</code>", "<code>*?</code>", "<code>a|b</code>", "<code>(…)</code>",
                     "<code>^</code>", "<code>$</code>", "<code>\\b</code>", "<code>\\.</code>",
                     "<code>mic?hi</code>", "<code>[uv]ox</code>",
                     'href="https://docs.python.org/3/library/re.html"'):
            assert text in table, (language, text)


def test_each_help_names_references_as_a_command_of_the_edit_menu():
    """V0.9.2.8 : « Références » est la dernière commande du menu Éditer,
    plus un bouton de la barre d'outils."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        command = f"<strong>{catalog['menu.edit']} → {catalog['references.action']}</strong>"
        references = _help_section(page, "references")
        assert command in references, language
        assert page.count(command) == 2, language
        edit = _help_section(page, "search-replace").split("</li>")[0]
        separator = "、" if language == "ja" else ", "
        assert f"{catalog['edit.format_xml']}{separator}{catalog['references.action']}" in edit, language


def test_each_help_explains_how_to_search_the_help():
    """V0.9.2.8 : la recherche dans l'aide, et la version qui l'annonce avec
    les commandes passées dans le menu Éditer."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "search-replace")
        item = section[section.index('<li id="help-search">'):]
        item = item[:item.index("</li>")]
        for text in ("<kbd>Ctrl+F</kbd>", "<kbd>F3</kbd>", '<code>"'):
            assert text in item, (language, text)
        assert item.index('<li id="help-search">') == 0 and section.index(item) < section.index("</ul>"), language
        version = _help_section(page, "v0928")
        assert 'href="#help-search"' in version, language
        for key in ("edit.format_xml", "references.action"):
            assert catalog[key] in version, (language, key)


def test_each_help_explains_the_list_of_all_occurrences():
    """V0.9.2.8 : « Tout lister » (Ctrl+Maj+L), le panneau des occurrences
    en contexte, dans la section « Rechercher et remplacer », le tableau des
    raccourcis et la version."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "search-replace")
        item = section[section.index('<li id="search-results">'):]
        item = item[:item.index("</li>")]
        for key in ("search.list", "search.list.menu", "results.all_project"):
            assert catalog[key] in item, (language, key)
        assert ("<kbd>Ctrl+Maj+L</kbd>" if language == "fr" else "<kbd>Ctrl+Shift+L</kbd>") in item, language
        assert section.index("<kbd>Ctrl+F</kbd>") < section.index(item) < section.index("<kbd>Ctrl+H</kbd>"), language
        ctrl_h = page.index("<tr><td>Ctrl+H</td>")
        assert page.index("<tr>", ctrl_h + 1) == page.index("<tr><td>Ctrl+Shift+L</td>"), language
        version = _help_section(page, "v0928")
        assert 'href="#search-results"' in version and catalog["search.list"] in version, language


def test_each_help_explains_the_menu_of_all_tabs():
    """V0.9.2.8 : la flèche ▾ à droite des onglets trop nombreux."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        documents = _help_section(page, "auxiliary-documents")
        assert "<strong>▾</strong>" in documents and catalog["documents.tabs.menu"] in documents, language
        version = _help_section(page, "v0928")
        assert "<strong>▾</strong>" in version and 'href="#auxiliary-documents"' in version, language


def test_each_help_explains_the_choice_in_the_ctrl_e_list():
    """V0.9.2.8.1 : l'entrée surlignée est insérée, sinon le texte saisi."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        start = page.index("<kbd>Ctrl+E</kbd>")
        paragraph = page[start:page.index("</p>", start)]
        assert "<kbd>Tab</kbd>" in paragraph and "<kbd>↓</kbd>" in paragraph, language


def test_each_help_explains_the_apps_without_lem():
    """V0.9.2.8.1 : troisième recherche de « Débugger l'apparat »."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "apparatus-debug")
        assert section.split("<li")[3].startswith(' id="app-without-lem">'), language
        item = section[section.index('<li id="app-without-lem">'):]
        item = item[:item.index("</li>")]
        for text in ("<code>&lt;app&gt;</code>", "<code>&lt;lem&gt;</code>", "&lt;rdgGrp&gt;", "&lt;listWit&gt;"):
            assert text in item, (language, text)


def test_each_help_explains_the_lead_button():
    """V0.9.2.8.1 : le bouton au livre des panneaux de témoins ; enfoncé,
    les flèches mènent l'édition (par défaut, celles du pivot)."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        section = _help_section(page, "witness-route")
        paragraph = section[section.index('<p id="lead-witness">'):]
        paragraph = paragraph[:paragraph.index("</p>")]
        assert "⤺" in paragraph and "<code>project.xml</code>" in paragraph, language
        assert "browse-witness" not in page, language


def test_each_help_announces_version_09281():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = _help_section(page, "v09281")
        for text in ('href="#lead-witness"', 'href="#app-without-lem"', "<kbd>Ctrl+E</kbd>"):
            assert text in version, (language, text)
        assert page.index('<section id="v0928">') < page.index('<section id="v09281">'), language


def test_each_help_explains_the_witness_siglum():
    """V0.9.2.8.2 : un sigle qui n'est pas un identifiant XML, et son <idno>."""
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        projects = '<h2 id="projets">' if language == "fr" else '<h2 id="projects">'
        start = page.index('<p id="witness-siglum">')
        assert page.index(projects) < start < page.index("<h2", page.index(projects) + 1), language
        block = page[start:page.index("<h2", start)]
        for text in ("<code>_1760</code>", "<code>T_2</code>", "<code>siglum</code>", "&lt;idno type=\"siglum\"&gt;",
                     "#_1760", catalog["menu.project_settings"], "<code>&lt;listWit&gt;</code>"):
            assert text in block, (language, text)


def test_each_help_explains_the_pencil_and_f2():
    """V0.9.2.8.2 : le crayon garde la sélection ; F2 ouvre le paragraphe de la sélection."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        start = page.index('<p id="fragment-selection">')
        paragraph = page[start:page.index("</p>", start)]
        assert "✎" in paragraph and "<kbd>F2</kbd>" in paragraph, language
        f8 = page.index("<tr><td>F8</td>")
        assert page.rindex("<tr>", 0, f8) == page.index("<tr><td>F2</td>"), language


def test_each_help_announces_version_09282():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = _help_section(page, "v09282")
        for text in ('href="#witness-siglum"', 'href="#fragment-selection"', "<kbd>F2</kbd>", "<code>siglum</code>",
                     "<code>&lt;listWit&gt;</code>", "Σ"):
            assert text in version, (language, text)
        assert page.index('<section id="v09281">') < page.index('<section id="v09282">'), language


def test_the_fragment_messages_speak_of_elements():
    """V0.9.2.9 : le crayon ✎ ouvre tout élément modifiable, plus seulement
    un paragraphe ; l'étiquette du fragment nomme l'élément ouvert."""
    paragraph = {"fr": ("paragraphe",), "en": ("paragraph",), "de": ("absatz", "absätz"), "ja": ("段落",),
                 "cs": ("odstav",), "it": ("paragraf",), "ru": ("абзац",)}
    keys = ("preview.edit_paragraph", "preview.info.default", "preview.updated.timed.lines",
            "preview.updated.timed.no_lines", "fragment.label", "fragment.label.file", "fragment.placeholder",
            "fragment.unapplied.question", "fragment.moved.text", "fragment.source_changed.text")
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        for key in ("fragment.label", "fragment.label.file"):
            assert "{element} {index}/{total}" in catalog[key], (language, key)
        for key in keys:
            text = re.sub(r"\{\w+\}", "", catalog[key]).lower()          # hors noms de paramètres
            assert not any(word in text for word in paragraph[language]), (language, key)


PARAGRAPH_WORDS = {"fr": ("paragraphe",), "en": ("paragraph",), "de": ("absatz", "absätz"), "ja": ("段落",),
                   "cs": ("odstav",), "it": ("paragraf",), "ru": ("абзац",)}


def test_each_help_explains_the_editable_elements():
    """V0.9.2.9 : le crayon ✎ ouvre chaque bloc d'une division (model.divPart,
    model.inter, <head>, <figure>, <note>), sauf s'il est dans un autre ;
    classes du schéma du projet, sinon TEI P5 ; toute feuille XSLT."""
    import html
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        selection = page.index('<p id="fragment-selection">')
        start = page.index('<p id="fragment-units">')
        assert selection < start < page.index("<h2", selection), language
        block = page[start:page.index("</p>", start)]
        label = html.escape(catalog["fragment.label"].format(element="<lg>", index=3, total=40), quote=False)
        for text in ("✎", "<code>model.divPart</code>", "<code>model.inter</code>", "<code>&lt;head&gt;</code>",
                     "<code>&lt;figure&gt;</code>", "<code>&lt;note&gt;</code>", "<code>&lt;lg&gt;</code>",
                     "<code>&lt;l&gt;</code>", "<code>&lt;body&gt;</code>", "RELAX NG", "ODD", "TEI P5 4.10.2", label):
            assert text in block, (language, text)
        paragraph = page[selection:page.index("</p>", selection)]
        assert 'href="#fragment-units"' in paragraph, language
        f2 = page.index("<tr><td>F2</td>")
        row = page[f2:page.index("</tr>", f2)].lower()
        assert not any(word in row for word in PARAGRAPH_WORDS[language]), language
        parts = page[page.index('<h3 id="xinclude-preview">'):]
        fragment = parts[parts.index("✎"):]
        fragment = fragment[:fragment.index("</li>")]
        assert not any(word in fragment.split("«")[0].split("“")[0].split("„")[0].split("「")[0].lower()
                       for word in PARAGRAPH_WORDS[language]), language


def test_each_help_announces_version_0929():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = _help_section(page, "v0929")
        for text in ('href="#fragment-units"', "<code>model.divPart</code>", "<code>model.inter</code>", "✎",
                     "<code>project.xml</code>", '<code>@rend="numbered"</code>', '<code>@type="ordered"</code>',
                     "<code>@n</code>", "<code>@xml:id</code>"):
            assert text in version, (language, text)
        assert page.index('<section id="v09282">') < page.index('<section id="v0929">'), language


def test_each_help_explains_the_reading_text_of_the_web_viewer():
    """V0.9.3.0 : le texte de lecture du viewer web (titres, sommaire,
    préliminaires et annexes, textes d'un groupe, vers, listes, tableaux,
    notes, choix, ratures, lacunes, groupes de leçons, langue)."""
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        viewer = page[page.index('<h2 id="viewer">'):]
        viewer = viewer[:viewer.index("<h2 ", 1)]
        paragraph = viewer[viewer.index('<p id="viewer-text">'):]
        paragraph = paragraph[:paragraph.index("</p>")]
        for name in ("head", "front", "back", "group", "lg", "l", "table", "note", "choice", "del", "add",
                     "supplied", "gap", "rdgGrp", "cit", "ref"):
            assert f"<code>&lt;{name}&gt;</code>" in paragraph, (language, name)
        for attribute in ("@n", "@xml:id", "@xml:lang", '@role="label"', "@cols", "@rows"):
            assert f"<code>{attribute}</code>" in paragraph, (language, attribute)
        assert "[…]" in paragraph, language


def test_each_help_announces_version_0930():
    for language in LANGUAGES:
        page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
        version = _help_section(page, "v0930")
        for text in ('href="#viewer-text"', "<code>&lt;table&gt;</code>", "<code>&lt;rdgGrp&gt;</code>",
                     "<code>@xml:id</code>", "<code>project.xml</code>", "<code>&lt;cit&gt;</code>",
                     "<code>&lt;ref&gt;</code>", '<code>type="bible"</code>', "✎", "XPath",
                     "<code>&lt;choice&gt;</code>", "<code>&lt;hi&gt;</code>"):
            assert text in version, (language, text)
        assert page.index('<section id="v0929">') < page.index('<section id="v0930">'), language
