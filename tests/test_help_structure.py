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


@pytest.mark.parametrize("language", LANGUAGES)
def test_down_arrow_is_explained_for_ctrl_e_and_ctrl_space(language):
    """V0.9.3.1 : ↓ dans le champ de filtre passe à la liste, avec Ctrl+E comme
    avec Ctrl+Espace ; chacun l'explique dans son paragraphe."""
    paragraphs = [p for p in html.fromstring(_page(language)).iter("p")
                  if "↓" in [kbd.text_content() for kbd in p.iter("kbd")]]
    assert len(paragraphs) == 2, language
    keys = [{kbd.text_content() for kbd in p.iter("kbd")} for p in paragraphs]
    assert any("Ctrl+E" in found for found in keys), language
    assert any(any(key.startswith("Ctrl+") and key != "Ctrl+E" for key in found) for found in keys), language


@pytest.mark.parametrize("language", LANGUAGES)
def test_large_files_and_the_startup_guard_are_explained(language):
    """Un fichier de plus de 20 Mo n'est ouvert qu'avec l'accord de
    l'utilisatrice ; un dernier projet qui n'a pas fini de se rouvrir ne
    l'est pas au lancement suivant. Les libellés cités sont ceux de
    l'interface."""
    page = _page(language)
    catalog = _catalog(language)
    paragraph = page[page.index('<p id="large-files">'):]
    paragraph = paragraph[:paragraph.index("</p>")]
    assert "20" in paragraph
    assert catalog["common.cancel"] in paragraph
    assert catalog["menu.recent_projects"] in paragraph


@pytest.mark.parametrize("language", LANGUAGES)
def test_a_project_without_witness_is_explained(language):
    """Un projet peut se créer sans témoin : le <bibl> à compléter, la
    <listWit> créée au premier témoin, le viewer web du texte seul."""
    page = _page(language)
    catalog = _catalog(language)
    paragraph = page[page.index('<p id="no-witness">'):]
    paragraph = paragraph[:paragraph.index("</p>")]
    for words in ("&lt;sourceDesc&gt;", "&lt;bibl&gt;", "&lt;listWit&gt;", "&lt;p&gt;",
                  catalog["menu.project_settings"], catalog["menu.generate_web"]):
        assert words in paragraph, words
    # L'ajout refusé tant que le <sourceDesc> a des paragraphes ; les témoins
    # non déclarés proposés à chaque enregistrement.
    assert paragraph.count("&lt;listWit&gt;") >= 3
    # Varians crée désormais la <listWit> ; l'aide ne dit plus le contraire.
    assert 'href="#no-witness"' in page
    for never in ("Varians n’en crée pas", "Varians does not create it", "Varians legt keine an",
                  "Varians ji nevytváří", "Varians non la crea", "Varians её не создаёт", "新たに作ることはありません"):
        assert never not in page, never


CURSOR_PLACE = {"fr": "curseur", "en": "cursor", "de": "Cursor", "cs": "kurzor", "it": "cursore",
                "ru": "курсор", "ja": "カーソル"}


@pytest.mark.parametrize("language", LANGUAGES)
def test_reopening_a_project_brings_back_the_cursor(language):
    """Un projet rouvert retrouve le document affiché et le curseur."""
    page = _page(language)
    start = page.index('<p id="large-files">')
    reopening = page[page.rindex("<p>", 0, start):start]
    assert CURSOR_PLACE[language] in reopening


VIEW_LABELS = ("preview.formatting", "preview.view.project", "views.menu", "views.new", "views.create_starter",
               "views.units", "views.edit", "views.remove", "views.open_xslt")


@pytest.mark.parametrize("language", LANGUAGES)
def test_named_views_are_explained(language):
    """V0.9.4.4 : la Vue XSLT / CSS de tout document XML du projet, ses vues
    nommées et leur gestion ; les libellés cités sont ceux de l'interface,
    dans l'ordre du menu."""
    page, catalog = _page(language), _catalog(language)
    paragraph = page[page.index('<p id="preview-views">'):]
    paragraph = paragraph[:paragraph.index("</p>")]
    positions = [paragraph.index(f"<strong>{catalog[key]}</strong>") for key in VIEW_LABELS]
    assert positions == sorted(positions), language
    assert "<code>&lt;view&gt;</code>" in paragraph and "<code>units</code>" in paragraph, language
    assert "XSLT 1.0" in paragraph, language
    assert 'href="#fragment-units"' in paragraph, language


@pytest.mark.parametrize("language", LANGUAGES)
def test_writing_the_stylesheet_of_a_view_is_explained(language):
    """V0.9.4.4 : la seule condition pour que Varians place les crayons
    (chaque élément modifiable traité par xsl:apply-templates, sans mode),
    avec un exemple, et ce qui en prive (xsl:for-each, mode) ; l'attribut
    vx:edit, l'enregistrement de la feuille, XSLT 1.0, le CSS de Qt.
    « Éléments modifiables » y renvoie au lieu de dire que la feuille n'a
    rien à prévoir."""
    page, catalog = _page(language), _catalog(language)
    start = page.index('<p id="view-stylesheet">')
    part = page[start:page.index("</p>", page.index("</pre>", start))]
    for needle in ("<code>xsl:apply-templates</code>", "<code>xsl:for-each</code>", "<code>mode</code>",
                   "<code>vx:edit</code>", "<kbd>Ctrl+S</kbd>", "XSLT 1.0", "<code>@media</code>",
                   "&lt;xsl:apply-templates select=\"//tei:person\"/&gt;", catalog["views.open_xslt"]):
        assert needle in part, (language, needle)
    units = page[page.index('<p id="fragment-units">'):]
    units = units[:units.index("</p>")]
    assert 'href="#view-stylesheet"' in units, language


@pytest.mark.parametrize("language", LANGUAGES)
def test_views_in_xslt_3_and_line_markers_are_explained(language):
    """V0.9.4.4 : une vue en XSLT 2.0 ou 3.0 passe par Saxon (crayons dans
    tous les modes) ; une feuille personnalisée suit les témoins si elle
    écrit les repères de ligne du pivot, avec la règle donnée en exemple ;
    l'avertissement de décalage ; « Édition critique » comme vue."""
    page = _page(language)
    start = page.index('<p id="view-stylesheet">')
    stylesheet = page[start:page.index("</p>", start)]
    assert "Saxon" in stylesheet and "3.0" in stylesheet and "<code>mode</code>" in stylesheet, language
    start = page.index('<p id="view-line-markers">')
    part = page[start:page.index("</p>", page.index("</pre>", start))]
    for needle in ("<code>baseWitness</code>", "tei-line://base/INDEX", "tei-line-marker", "<code>INDEX</code>",
                   "<code>reperes-lignes</code>", "edition-critique.xsl", "410", "412"):
        assert needle in part, (language, needle)
    assert 'href="#view-line-markers"' in page[page.index('<p id="view-stylesheet">'):start], language


CSS_LABELS = ("views.css", "views.css.mode.auto", "views.css.mode.always", "views.css.mode.never",
              "views.css.mode.file", "views.css.file")


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_css_of_a_view_is_explained(language):
    """V0.9.4.4 : la CSS d'une vue — automatique (celle de la feuille si
    elle a son propre <style>), celle du projet, aucune, un fichier ;
    variables CSS remplacées ; projectCss dans project.xml. Les libellés
    cités sont ceux de la boîte, dans son ordre ; « Vues nommées » y
    renvoie."""
    page, catalog = _page(language), _catalog(language)
    start = page.index('<p id="view-css">')
    paragraph = page[start:page.index("</p>", start)]
    positions = [paragraph.index(f"<strong>{catalog[key]}</strong>") for key in CSS_LABELS]
    assert positions == sorted(positions), language
    for needle in ("<code>&lt;style&gt;</code>", "<code>var(--", 'projectCss="always"', 'projectCss="never"',
                   "<code>background-color</code>"):
        assert needle in paragraph, (language, needle)
    views = page[page.index('<p id="preview-views">'):]
    assert 'href="#view-css"' in views[:views.index("</p>")], language


@pytest.mark.parametrize("language", LANGUAGES)
def test_an_external_css_of_a_view_is_explained(language):
    """V0.9.4.4 : une CSS appelée par <link rel="stylesheet"> n'est pas lue
    par l'aperçu (Qt ne la charge pas) ; elle se déclare dans la vue (« Un
    fichier CSS »), le <link> servant au navigateur ; <link> et <style> :
    seul le <style> compte en automatique ; règles après un @media
    ignorées."""
    page, catalog = _page(language), _catalog(language)
    start = page.index('<p id="view-css">')
    paragraph = page[start:page.index("</p>", start)]
    link = paragraph.index('<code>&lt;link rel="stylesheet"&gt;</code>')
    for needle in (f"<strong>{catalog['views.css.mode.file']}</strong>", f"<strong>{catalog['views.css.file']}</strong>",
                   '<code>css="xslt/catalogue.css"</code>', f"<strong>{catalog['toolbar.transform']}</strong>",
                   "<code>@media</code>"):
        assert needle in paragraph[link:], (language, needle)


@pytest.mark.parametrize("language", LANGUAGES)
def test_javascript_in_a_view_is_explained(language):
    """V0.9.4.4 : l'aperçu n'exécute pas le JavaScript d'une feuille
    (<script> ignoré, onclick sans effet) ; pour une page qui en a besoin,
    un scénario de Transformer et un navigateur."""
    page, catalog = _page(language), _catalog(language)
    start = page.index("</pre>", page.index('<p id="view-stylesheet">'))
    rest = page[start:page.index("</p>", start)]
    for needle in ("<code>&lt;script&gt;</code>", "<code>onclick</code>", f"<strong>{catalog['toolbar.transform']}</strong>"):
        assert needle in rest, (language, needle)


@pytest.mark.parametrize("language", LANGUAGES)
def test_what_the_preview_can_display_is_explained(language):
    """L'aperçu n'est pas un navigateur : Qt y affiche un HTML 4 et une CSS 2
    simplifiés. Ce qui est compris (tableaux, largeurs par attribut), ce qui
    ne l'est pas (flex, padding d'un <div>, em, pseudo-classes…), rien ne se
    masque, balises HTML 5 et formulaires, images à adresse complète ;
    « Écrire la feuille d'une vue » et « La CSS d'une vue » y renvoient."""
    page, catalog = _page(language), _catalog(language)
    start = page.index('<p id="view-html">')
    part = page[start:page.index("</ul>", start)]
    for needle in ("HTML 4", "CSS 2", f"<strong>{catalog['toolbar.transform']}</strong>",
                   "<code>&lt;table&gt;</code>", '<code>&lt;td width="30%"&gt;</code>', "<code>padding</code>",
                   "<code>display: flex</code>", "<code>border-radius</code>", "<code>em</code>",
                   "<code>!important</code>", "<code>:hover</code>", "<code>::before</code>", "<code>@media</code>",
                   "<code>display: none</code>", "<code>hidden</code>", "<code>xsl:if</code>",
                   "<code>&lt;section&gt;</code>", "<code>&lt;details&gt;</code>", "<code>&lt;input&gt;</code>",
                   "<code>file:///", "static-base-uri()", "base-uri(/)"):
        assert needle in part, (language, needle)
    rest = page[page.index("</pre>", page.index('<p id="view-stylesheet">')):]
    assert 'href="#view-html"' in rest[:rest.index("</p>")], language
    css = page[page.index('<p id="view-css">'):]
    assert 'href="#view-html"' in css[:css.index("</p>")], language


@pytest.mark.parametrize("language", LANGUAGES)
def test_moving_a_selection_between_views_is_explained(language):
    """V0.9.4.5 : une sélection passe de l'aperçu à la source, et à
    l'éditeur de fragment, par son texte et son contexte : à travers des
    balises et des entités, sans <lb/> ni crayon ; une sélection
    introuvable est signalée dans la barre d'état."""
    page = _page(language)
    start = page.index('<p id="view-selection">')
    paragraph = page[start:page.index("</p>", start)]
    for needle in ('<code>&lt;lb break="no"/&gt;</code>', "<code>&lt;persName&gt;</code>", "<code>&lt;hi&gt;</code>",
                   "<code>&amp;amp;</code>", "<code>&lt;lb/&gt;</code>", "✎", "XPath"):
        assert needle in paragraph, (language, needle)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_error_log_is_explained(language):
    """V0.9.4.6 : Aide → Journal des erreurs, entre l'aide du logiciel et
    « À propos » ; ce que le journal contient (jamais le texte des
    documents), où il est sous chaque système, sa taille limitée, et comment
    l'envoyer."""
    catalog, page = _catalog(language), _page(language)
    start = page.index('<section id="menus">')
    menus = page[start:page.index("</section>", start)]
    positions = [menus.index(catalog[key]) for key in ("help.software", "help.error_log", "help.about")]
    assert positions == sorted(positions), language
    start = page.index('<p id="error-log">')
    paragraph = page[start:page.index("</p>", start)]
    for needle in (catalog["help.error_log"], "<code>varians.log</code>", r"<code>%LOCALAPPDATA%\Varians\logs</code>",
                   "<code>~/Library/Logs/Varians</code>", "<code>~/.local/state/varians/logs</code>", {"fr": "1 Mo", "ru": "1 МБ"}.get(language, "1 MB")):
        assert needle in paragraph, (language, needle)


@pytest.mark.parametrize("language", LANGUAGES)
def test_the_check_of_downloads_is_explained(language):
    """V0.9.4.6 : l'empreinte SHA-256 des TEI Stylesheets téléchargées est
    comparée à celle que publie GitHub ; sans empreinte, le journal des
    erreurs le note ; les modèles TEI, lus par morceaux, ont leur CRC-32."""
    page = _page(language)
    section = page[page.index('<section id="tei-stylesheets">'):]
    section = section[:section.index("</section>")]
    start = section.index('<p id="tei-stylesheets-digest">')
    paragraph = section[start:section.index("</p>", start)]
    for needle in ("SHA-256", "GitHub", "CRC-32", 'href="#error-log"'):
        assert needle in paragraph, (language, needle)
