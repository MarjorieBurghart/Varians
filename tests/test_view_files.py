# -*- coding: utf-8 -*-
"""Fichiers d'une nouvelle vue (V0.9.4.4), sans Qt.

« Nouvelle vue… » peut écrire une feuille XSLT 1.0 et une CSS de départ,
nommées d'après la vue, dans ``xslt/`` et ``rendering/`` du projet, sans
jamais remplacer un fichier. La feuille montre tout document : une entrée de
liste est un paragraphe, son contenu en ligne ; ailleurs, un élément qui
contient du texte est un paragraphe, un autre un bloc ; les crayons ✎ sont
ceux de Varians. Pour un document auxiliaire, les éléments modifiables
proposés sont les entrées de sa première liste (``<person>`` d'un
``<listPerson>``)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from lxml import etree

from fragment_units import chosen_units, edit_stylesheet, edit_stylesheet_url, mark_units, place_edit_markers
from view_files import (
    check_view, parse_units, starter_css, starter_paths, starter_stylesheet, suggested_units, view_slug,
    write_starter,
)

TEI_NS = "http://www.tei-c.org/ns/1.0"
PERSONS = (f'<listPerson xmlns="{TEI_NS}">'
           '<person xml:id="b"><persName>Bernardus</persName> <birth>1090</birth></person>'
           '<person xml:id="p"><persName>Petrus</persName></person></listPerson>')


@pytest.mark.parametrize("name, slug", [
    ("Index des personnes", "index-des-personnes"),
    ("Gloses · marge (B)", "gloses-marge-b"),
    ("Été", "ete"),
    ("索引", "vue"),
    ("  ", "vue"),
])
def test_file_names_come_from_the_view_name(name, slug):
    assert view_slug(name) == slug


def test_starter_files_never_replace_a_file(tmp_path):
    (tmp_path / "xslt").mkdir()
    (tmp_path / "xslt" / "index.xsl").write_text("garder", encoding="utf-8")
    xslt, css = starter_paths(tmp_path, "Index")
    assert xslt == tmp_path / "xslt" / "index_2.xsl"
    assert css == tmp_path / "rendering" / "index.css"
    written = write_starter(tmp_path, "Index")
    assert written == ("xslt/index_2.xsl", "rendering/index.css")
    assert (tmp_path / "xslt" / "index.xsl").read_text(encoding="utf-8") == "garder"
    assert "Index" in (tmp_path / "xslt" / "index_2.xsl").read_text(encoding="utf-8")
    assert write_starter(tmp_path, "Index") == ("xslt/index_3.xsl", "rendering/index_2.css")


def _render(stylesheet_path, xml_text, names):
    marked, _spans = mark_units(xml_text, names)
    xslt = etree.XSLT(etree.fromstring(edit_stylesheet(stylesheet_path).encode("utf-8"),
                                       base_url=edit_stylesheet_url(stylesheet_path)))
    return place_edit_markers(str(xslt(etree.fromstring(marked.encode("utf-8")))), "✎")


def test_the_starter_stylesheet_shows_any_document_with_its_pencils(tmp_path):
    path = tmp_path / "vue.xsl"
    path.write_text(starter_stylesheet("Fiches & <notes>"), encoding="utf-8")
    assert etree.parse(str(path)).getroot().get("version") == "1.0"
    html, count = _render(path, PERSONS, chosen_units(("person",)))
    assert count == 2
    assert "<h1>Fiches &amp; &lt;notes&gt;</h1>" in html
    paragraphs = [re.sub(r"<[^>]+>", "", p).replace("✎", "").strip()
                  for p in re.findall(r"<p\b[^>]*>(.*?)</p>", html, re.S)]
    assert paragraphs == ["Bernardus 1090", "Petrus"]                 # une entrée, un paragraphe
    assert re.search(r'<p class="person"><a href="tei-edit://p/0"[^>]*>✎</a> <span class="persName">Bernardus', html)


def test_the_starter_stylesheet_keeps_elements_inline_in_a_paragraph(tmp_path):
    path = tmp_path / "vue.xsl"
    path.write_text(starter_stylesheet("Vue"), encoding="utf-8")
    xml_text = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>'
                '</teiHeader><text><body><p>Vidit <persName>Petrus</persName> ibi.</p></body></text></TEI>')
    html, count = _render(path, xml_text, frozenset({"p"}))
    assert count == 1
    assert '<span class="persName">Petrus</span>' in html
    assert ">T<" not in html                                   # en-tête masqué


def test_the_starter_css_is_plain(tmp_path):
    css = starter_css("Vue */ { color: red }")
    assert "@media" not in css and "*/ {" not in css.split("*/", 1)[1]
    assert css.count("/*") == css.count("*/")


@pytest.mark.parametrize("xml_text, units", [
    (PERSONS, ("person",)),
    (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><sourceDesc><listWit><witness/></listWit></sourceDesc>'
     '</fileDesc></teiHeader><standOff><listPlace><place/><place/></listPlace></standOff></TEI>', ("place",)),
    (f'<listPerson xmlns="{TEI_NS}"><person/><personGrp/><person/></listPerson>', ("person", "personGrp")),
    (f'<TEI xmlns="{TEI_NS}"><text><body><listPerson><person/></listPerson></body></text></TEI>', ()),
    (f'<div xmlns="{TEI_NS}"><p/></div>', ()),
    ("<listPerson><person>", ()),
])
def test_editable_elements_suggested_for_a_document(xml_text, units):
    assert suggested_units(xml_text) == units


def test_editable_element_names_are_checked():
    assert parse_units(" person  place ") == ("person", "place")
    assert parse_units("") == ()
    assert parse_units("person <p>") is None
    assert parse_units("tei:person") is None


def test_a_view_is_checked_before_it_is_written(tmp_path):
    xslt = tmp_path / "vue.xsl"
    xslt.write_text("<x/>", encoding="utf-8")
    css = tmp_path / "vue.css"
    css.write_text("", encoding="utf-8")
    taken = ("Index",)
    assert check_view("Fiches", xslt, None, "person", taken) is None
    assert check_view("Fiches", xslt, css, "", taken) is None
    assert check_view("  ", xslt, None, "", taken) == "views.error.name"
    assert check_view(" index ", xslt, None, "", taken) == "views.error.taken"
    assert check_view("Fiches", None, None, "", taken) == "views.error.xslt"
    assert check_view("Fiches", tmp_path / "absente.xsl", None, "", taken) == "views.error.xslt"
    assert check_view("Fiches", xslt, tmp_path / "absente.css", "", taken) == "views.error.css"
    assert check_view("Fiches", xslt, None, "a:b", taken) == "views.error.units"


def test_a_view_with_starter_files_needs_only_a_name_and_element_names():
    assert check_view("Fiches", None, None, "person", ("Index",), starter=True) is None
    assert check_view("Index", None, None, "", ("Index",), starter=True) == "views.error.taken"
    assert check_view("Fiches", None, None, "<p>", ("Index",), starter=True) == "views.error.units"


def test_the_starter_stylesheet_says_how_to_keep_the_pencils():
    text = starter_stylesheet("Vue")
    comment = text[text.index("<!--"):text.index("-->")]
    assert "xsl:apply-templates" in comment and "xsl:for-each" in comment and "mode" in comment


# -- Feuille de départ 3.0 et repères de ligne (V0.9.4.4) -------------------------

EDITION = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>'
           '</teiHeader><facsimile><surface><graphic url="a.jpg"/></surface><surface><graphic url="b.jpg"/>'
           '</surface></facsimile><text><body><p><lb edRef="#A"/>Prima <lb edRef="#B"/>linea '
           '<app><lem>uera</lem><rdg>falsa<lb edRef="#A"/></rdg></app></p><p><lb edRef="#A"/>secunda</p>'
           '</body></text></TEI>')


def _lxml(path, xml_text, **params):
    xslt = etree.XSLT(etree.parse(str(path)))
    return str(xslt(etree.fromstring(xml_text.encode("utf-8")),
                    **{k: etree.XSLT.strparam(v) for k, v in params.items()}))


def _saxon(path, xml_text, **params):
    from saxonche import PySaxonProcessor
    processor = PySaxonProcessor(license=False)
    executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(path))
    for name, value in params.items():
        executable.set_parameter(name, processor.make_atomic_value("untypedAtomic", value))
    return executable.transform_to_string(xdm_node=processor.parse_xml(xml_text=xml_text))


@pytest.mark.parametrize("version", ["1.0", "3.0"])
def test_the_starter_writes_one_line_marker_per_pivot_line(tmp_path, version):
    from xslt_scenarios import saxon_available
    if version == "3.0" and not saxon_available():
        pytest.skip("Saxon (saxonche) n'est pas installé")
    path = tmp_path / "vue.xsl"
    path.write_text(starter_stylesheet("Vue", version), encoding="utf-8")
    assert etree.parse(str(path)).getroot().get("version") == version
    html = (_lxml if version == "1.0" else _saxon)(path, EDITION, baseWitness="A")
    assert re.findall(r'class="tei-line-marker" href="tei-line://base/INDEX"', html).__len__() == 3
    assert "a.jpg" not in html and html.count('class="graphic"') == 0         # pas le fac-similé
    assert "Prima" in html and "secunda" in html


def test_the_3_0_starter_says_modes_are_fine():
    text = starter_stylesheet("Vue", "3.0")
    comment = text[text.index("<!--"):text.index("-->")]
    assert "3.0" in comment and "mode" in comment and "xsl:for-each" in comment and "baseWitness" in text


def test_a_3_0_starter_is_written(tmp_path):
    xslt, css = write_starter(tmp_path, "Gloses", "3.0")
    assert xslt == "xslt/gloses.xsl" and css == "rendering/gloses.css"
    assert 'version="3.0"' in (tmp_path / xslt).read_text(encoding="utf-8")
    assert 'version="1.0"' in (tmp_path / write_starter(tmp_path, "Gloses")[0]).read_text(encoding="utf-8")


def test_the_view_dialog_texts_speak_of_both_versions():
    """La boîte « Nouvelle vue » (×7) : la feuille de départ en 1.0 ou 3.0,
    avec les repères de ligne ; 2.0 et 3.0 par Saxon, crayons par
    xsl:apply-templates."""
    import xml.etree.ElementTree as ET
    root = Path(__file__).resolve().parents[1]
    for language in ("fr", "en", "de", "cs", "it", "ru", "ja"):
        catalog = {s.get("key"): s.text or "" for s in ET.parse(root / "i18n" / f"{language}.xml").getroot()}
        assert "1.0" in catalog["views.create_starter.tip"] and "3.0" in catalog["views.create_starter.tip"], language
        note = catalog["views.note"]
        assert "Saxon" in note and "3.0" in note and "xsl:apply-templates" in note, language
