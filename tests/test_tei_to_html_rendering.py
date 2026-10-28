# -*- coding: utf-8 -*-
"""Rendu de la feuille de Varians (rendering/tei-to-html.xsl), V0.9.2.9 :
vers (chaque <l> sur sa ligne, chaque <lg> en bloc), <head> en titre,
<list> en liste, <figure> en bloc. Ces éléments sont désormais modifiables
avec le crayon ✎ de la Vue XSLT / CSS."""
from __future__ import annotations

from pathlib import Path

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ROOT / "rendering" / "tei-to-html.xsl"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _page(body):
    tei = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>'
           f'</teiHeader><text><body>{body}</body></text></TEI>')
    result = etree.XSLT(etree.parse(str(BUILTIN)))(etree.fromstring(tei.encode("utf-8")))
    return html.fromstring(str(result))


def _texts(page, xpath):
    return [" ".join(element.text_content().split()) for element in page.xpath(xpath)]


def test_a_verse_group_is_a_block_of_lines():
    page = _page("<div><lg><head>Carmen</head><l>uersus unus</l><l>uersus duo</l></lg>"
                 "<lg><l>tertius</l></lg></div>")
    assert _texts(page, '//main//div[@class="lg"]/div[@class="l"]') == ["uersus unus", "uersus duo", "tertius"]
    assert _texts(page, '//div[@class="lg"]/h3[@class="head"]') == ["Carmen"]
    assert len(page.xpath('//div[@class="lg"]')) == 2


def test_a_head_is_a_heading():
    page = _page('<div xml:id="d1"><head>Titulus</head><p>textus</p></div>')
    assert _texts(page, '//div[@class="section"]/h3[@class="head"]') == ["Titulus"]
    assert _texts(page, '//div[@class="section"]/p') == ["textus"]


def test_a_list_is_a_list():
    page = _page('<div><list><head>Index</head><item>unum</item><item>duo</item></list>'
                 '<list rend="numbered"><item>primum</item></list><list type="ordered"><item>secundum</item></list>'
                 '<list rend="unnumbered"><item>tres</item></list></div>')
    assert _texts(page, "//main//ul/li") == ["unum", "duo", "tres"]
    assert _texts(page, "//main//ol/li") == ["primum", "secundum"]
    heading = page.xpath('//main//h3[@class="head"]')[0]
    assert heading.text_content() == "Index" and heading.getnext().tag == "ul"


def test_a_figure_is_a_block():
    page = _page("<div><figure><head>Tabula</head><figDesc>Descriptio tabulae</figDesc></figure></div>")
    assert _texts(page, '//div[@class="figure"]/h3[@class="head"]') == ["Tabula"]
    assert _texts(page, '//div[@class="figure"]/div[@class="figdesc"]') == ["Descriptio tabulae"]


def test_paragraphs_are_unchanged():
    page = _page("<div><p>Commune <hi rend=\"italic\">sanctorum</hi></p></div>")
    assert _texts(page, "//main//p") == ["Commune sanctorum"]


def test_the_stylesheet_of_new_projects_styles_them():
    css = (ROOT / "rendering" / "tei.css").read_text(encoding="utf-8")
    for selector in (".lg", ".l", ".head", ".figure", ".figdesc"):
        assert f"\n{selector} " in css or f"\n{selector}," in css, selector
