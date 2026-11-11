# -*- coding: utf-8 -*-
"""Fichiers d'une nouvelle vue (V0.9.4.4), sans Qt.

« Nouvelle vue… » peut écrire une feuille XSLT 1.0 et une CSS de départ,
nommées d'après la vue, dans ``xslt/`` et ``rendering/`` du projet, sans
jamais remplacer un fichier. La feuille montre tout document : un élément
qui contient du texte est un paragraphe, un autre un bloc ; les crayons ✎
sont ceux de Varians. Pour un document auxiliaire, les éléments modifiables
proposés sont les entrées de sa première liste (``<person>`` d'un
``<listPerson>``)."""
from __future__ import annotations

import re

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
    assert paragraphs == ["Bernardus", "1090", "Petrus"]
    assert re.search(r'<div class="person">\s*<p class="persName"><a href="tei-edit://p/0"', html)


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
