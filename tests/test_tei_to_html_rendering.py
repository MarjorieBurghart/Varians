# -*- coding: utf-8 -*-
"""Rendu de la feuille de Varians (rendering/tei-to-html.xsl), V0.9.2.9 :
vers (chaque <l> sur sa ligne, chaque <lg> en bloc), <head> en titre,
<list> en liste, <figure> en bloc. Ces éléments sont désormais modifiables
avec le crayon ✎ de la Vue XSLT / CSS. V0.9.3.0 : <table> en tableau."""
from __future__ import annotations

from pathlib import Path

from lxml import etree, html

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ROOT / "rendering" / "tei-to-html.xsl"
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _page(body, header="", text=""):
    tei = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>{header}</fileDesc>'
           f'</teiHeader><text{text}><body>{body}</body></text></TEI>')
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


def test_a_division_is_titled_by_its_head_or_its_n_never_by_its_identifier():
    """Comme « Édition critique » : le premier <head> d'une division, sinon
    son @n ; un @xml:id n'est pas un titre. Chaque division est une section."""
    page = _page('<div xml:id="RLS_184"><p>a</p></div><div xml:id="d2" n="Sermo 2"><p>b</p></div>'
                 '<div xml:id="d3" n="tertius"><head>Titulus</head><p>c</p></div>')
    assert _texts(page, '//main//h2[@class="section-title"]') == ["Sermo 2", "Titulus"]
    assert not page.xpath('//main//h3[@class="head"]')
    assert "RLS_184" not in page.text_content() and "tertius" not in page.text_content()
    assert len(page.xpath('//main//div[@class="section"]')) == 3
    assert _texts(page, '//div[@class="section"]/p') == ["a", "b", "c"]


def test_the_table_of_contents_lists_the_titled_divisions_by_level():
    page = _page('<div n="I"><head>Liber primus</head>'
                 '<div><head>Caput <app><lem>unum</lem><rdg>primum</rdg></app><note>n</note></head><p>a</p></div>'
                 '<div xml:id="c2"><p>b</p></div></div><div xml:id="x"><p>c</p></div><div n="II"><p>d</p></div>')
    toc = page.xpath('//nav[@class="toc"]/ul[@class="toc-list"]')[0]
    entries = [(" ".join(li.find("a").text_content().split()), [" ".join(a.text_content().split())
                                                                 for a in li.xpath("./ul/li/a")])
               for li in toc.xpath("./li")]
    assert entries == [("Liber primus", ["Caput unum"]), ("II", [])]
    for link in toc.xpath(".//a"):
        anchor = link.get("href").removeprefix("tei-toc:/")
        assert link.get("href").startswith("tei-toc:/") and page.xpath(f'//main//a[@name="{anchor}"]')
    assert not _page('<div xml:id="a"><p>x</p></div>').xpath('//nav')


def test_the_header_shows_the_title_and_the_page_takes_the_language_of_the_text():
    header = ('<sourceDesc><msDesc><msIdentifier/><msContents><textLang>Latin</textLang>'
              '<origDate>XIIIe s.</origDate></msContents></msDesc></sourceDesc>')
    page = _page("<div><p>a</p></div>", header=header, text=' xml:lang="la"')
    assert _texts(page, "//header/*") == ["T"]
    assert page.get("lang") == "la"
    assert _page("<div><p>a</p></div>").get("lang") is None


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


TABLE = ('<div><table rows="4" cols="2"><head>Tabula</head>'
         '<row role="label"><cell>Nomen</cell><cell>Folium</cell></row>'
         '<row><cell role="label">Petrus</cell><cell>12r</cell></row>'
         '<row><cell cols="2">totum</cell></row>'
         '<row role="label"><cell rows="2">a</cell><cell role="data">b</cell></row></table></div>')


def _cells(table):
    return [[(cell.tag, " ".join(cell.text_content().split()), cell.get("colspan"), cell.get("rowspan"))
             for cell in row] for row in table.xpath(".//tr")]


def test_a_table_is_a_table():
    """V0.9.3.0 : son <head> en légende ; une cellule @role="label", ou
    d'une ligne @role="label", en en-tête ; @cols et @rows fusionnent."""
    page = _page(TABLE)
    table = page.xpath("//main//table")[0]
    assert _texts(page, "//main//table/caption") == ["Tabula"]
    assert _cells(table) == [[("th", "Nomen", None, None), ("th", "Folium", None, None)],
                             [("th", "Petrus", None, None), ("td", "12r", None, None)],
                             [("td", "totum", "2", None)],
                             [("th", "a", None, "2"), ("td", "b", None, None)]]
    assert not page.xpath('//main//h3[@class="head"]')


def test_paragraphs_are_unchanged():
    page = _page("<div><p>Commune <hi rend=\"italic\">sanctorum</hi></p></div>")
    assert _texts(page, "//main//p") == ["Commune sanctorum"]


def test_the_stylesheet_of_new_projects_styles_them():
    css = (ROOT / "rendering" / "tei.css").read_text(encoding="utf-8")
    for selector in (".lg", ".l", ".head", ".figure", ".figdesc", ".table"):
        assert f"\n{selector} " in css or f"\n{selector}," in css, selector
