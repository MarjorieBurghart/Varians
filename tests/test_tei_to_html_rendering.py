# -*- coding: utf-8 -*-
"""Rendu de la feuille de Varians (rendering/tei-to-html.xsl), V0.9.2.9 :
vers (chaque <l> sur sa ligne, chaque <lg> en bloc), <head> en titre,
<list> en liste, <figure> en bloc. Ces éléments sont désormais modifiables
avec le crayon ✎ de la Vue XSLT / CSS. V0.9.3.0 : <table> en tableau.
V0.9.3.1 : répliques (<sp>)."""
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
    """Une strophe est un seul bloc : ses vers y sont séparés par un <br/>.
    L'aperçu de Varians (Qt) ne regroupe pas des blocs imbriqués : des vers
    en <div> y seraient autant de paragraphes (V0.9.3.0)."""
    page = _page("<div><lg><head>Carmen</head><l>uersus unus</l><l>uersus duo</l><pb n=\"2r\"/><l>tres</l></lg>"
                 "<lg><l>quartus</l></lg><l>solus</l></div>")
    assert _texts(page, '//main//div[@class="lg"]/span[@class="l"]') == ["uersus unus", "uersus duo", "tres", "quartus"]
    assert _texts(page, '//div[@class="lg"]/h3[@class="head"]') == ["Carmen"]
    first, second = page.xpath('//div[@class="lg"]')
    assert [child.tag for child in first] == ["h3", "span", "br", "span", "br", "span", "span"]
    assert first.xpath("span")[-2].get("class") == "pb"
    assert not second.xpath("br")
    assert _texts(page, '//main//div[@class="l"]') == ["solus"]


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


def test_the_reference_of_a_quotation_is_shown_in_angle_brackets():
    """V0.9.3.0 : le <ref> d'une <cit> (autrefois omis) suit la citation,
    entre chevrons, grisé ; un <ref> hors d'une <cit> ne change pas."""
    page = _page('<div><p>Dixit <cit><quote>Uos estis</quote><ref>Lc. 22:28</ref></cit> et '
                 '<cit type="bible"><quote>In principio</quote> <ref>Io 1, 1</ref></cit> '
                 '<ref target="#x">alia</ref>.</p></div>')
    assert _texts(page, '//main//span[@class="ref"]') == ["<Lc. 22:28>", "<Io 1, 1>"]
    assert " ".join(page.xpath("//main//p")[0].text_content().split()) == \
        "Dixit Uos estis <Lc. 22:28> et In principio <Io 1, 1> alia."


def test_editorial_phenomena_as_in_the_critical_edition():
    """V0.9.3.0, comme « Édition critique » : une forme d'un <choice> (corr,
    reg, expan, sinon sic, orig, abbr), les autres en infobulle ; <sic>
    signalé ; <del> et <surplus> barrés, <add> marqué ; <supplied> entre
    crochets ; <gap> « [lacune] » ; <space> une espace."""
    page = _page('<div><p>Isti <choice><sic>erat</sic><corr>erant</corr></choice> '
                 '<choice><abbr>dns</abbr><expan>dominus</expan></choice> <sic>solum</sic> '
                 '<choice><orig>uita</orig><reg>vita</reg></choice> '
                 '<del>deleta</del> <add>addita</add> <surplus>et</surplus> Pe<supplied>trus</supplied>'
                 '<space/>fin<gap reason="illegible" extent="2 uerba"/>is <gap/>.</p></div>')
    paragraph = page.xpath("//main//p")[0]
    assert " ".join(paragraph.text_content().split()) == (
        "Isti erant dominus solum vita deleta addita et Pe[trus] fin[lacune : 2 uerba]is [lacune].")
    assert [e.get("title") for e in paragraph.xpath('.//span[@class="choice"]')] == [
        "Leçon transmise : erat", "Abréviation : dns", "Graphie originale : uita"]
    assert _texts(page, '//span[@class="rature"]') == ["deleta", "et"]
    assert _texts(page, '//span[@class="ajout"]') == ["addita"]
    assert _texts(page, '//span[@class="sic"]') == ["solum"]
    assert _texts(page, '//span[@class="restitution"]') == ["[trus]"]
    assert [e.get("title") for e in paragraph.xpath('.//span[@class="lacune"]')] == ["Lacune : illegible", "Lacune"]


def test_renditions_of_hi_and_italic_elements():
    page = _page('<div><p><hi rend="bold">a</hi> <hi rend="underline">b</hi> <hi rend="sup">c</hi> '
                 '<hi rend="subscript">d</hi> <hi rend="smallcaps">e</hi> <hi rend="italic bold">f</hi> '
                 '<hi rend="italic">g</hi> <emph>h</emph> <title>Summa</title> <foreign>logos</foreign></p></div>')
    paragraph = page.xpath("//main//p")[0]
    assert [e.text_content() for e in paragraph.xpath(".//b")] == ["a", "f"]
    assert [e.text_content() for e in paragraph.xpath(".//u")] == ["b"]
    assert [e.text_content() for e in paragraph.xpath(".//sup")] == ["c"]
    assert [e.text_content() for e in paragraph.xpath(".//sub")] == ["d"]
    assert _texts(page, '//span[@class="petites-capitales"]') == ["e"]
    assert [e.text_content() for e in paragraph.xpath(".//i")] == ["f", "h", "Summa", "logos"]
    assert paragraph.xpath(".//i/b")[0].text_content() == "f"
    assert _texts(page, '//p/span[@class="quote"]') == ["g"]


SCENE = ('<div><head>Scena prima</head><stage>Intrat Hamletus.</stage>'
         '<sp who="#h"><speaker>HAMLETUS</speaker><lg><l>Esse aut non esse,</l><stage>ridet</stage>'
         '<l>haec quaestio.</l></lg></sp>'
         '<sp who="#o"><speaker>OPHELIA</speaker><p>Domine <stage>susurrat</stage> quomodo uales?</p>'
         '<stage>Exit.</stage></sp></div>')


def test_a_speech_has_its_speaker_its_lines_and_its_stage_directions():
    """V0.9.3.1, comme le viewer web : chaque réplique est un bloc, son
    locuteur en tête ; une didascalie, entre parenthèses comme dans
    « Édition critique », est un bloc entre deux blocs, une ligne dans une
    strophe, en italique dans une phrase."""
    page = _page(SCENE)
    speeches = page.xpath('//main//div[@class="sp"]')
    assert [_texts(sp, 'div[@class="speaker"]') for sp in speeches] == [["HAMLETUS"], ["OPHELIA"]]
    assert _texts(speeches[0], 'div[@class="lg"]/span[@class="l"]') == ["Esse aut non esse,", "haec quaestio."]
    assert [child.tag for child in speeches[0].xpath('div[@class="lg"]')[0]] == ["span", "br", "span", "br", "span"]
    assert _texts(speeches[0], 'div[@class="lg"]/span[@class="stage"]') == ["(ridet)"]
    assert _texts(speeches[1], 'p/span[@class="stage"]') == ["(susurrat)"]
    assert _texts(page, '//main//div[@class="stage"]') == ["(Intrat Hamletus.)", "(Exit.)"]
    assert _texts(speeches[1], 'div[@class="stage"]') == ["(Exit.)"]


def test_the_parentheses_of_a_stage_direction_hug_its_text():
    page = _page('<div><sp><speaker>A</speaker><p>Ita <stage>\n  ridet <hi rend="italic">multum</hi>\n</stage> est.</p>'
                 '<stage>\n    Exeunt\n  </stage></sp></div>')
    assert [element.text_content() for element in page.xpath('//main//*[@class="stage"]')] == [
        "(ridet multum)", "(Exeunt)"]


def test_the_preview_styles_the_speeches_even_with_the_stylesheet_of_an_older_project():
    from formatted_view import PREVIEW_BASE_CSS
    for rule in (".speaker {", ".stage {", "div.stage {"):
        assert rule in PREVIEW_BASE_CSS, rule
    assert "small-caps" in PREVIEW_BASE_CSS.split(".speaker {")[1].split("}")[0]
    assert "italic" in PREVIEW_BASE_CSS.split(".stage {")[1].split("}")[0]


def test_paragraphs_are_unchanged():
    page = _page("<div><p>Commune <hi rend=\"italic\">sanctorum</hi></p></div>")
    assert _texts(page, "//main//p") == ["Commune sanctorum"]


def test_the_stylesheet_of_new_projects_styles_them():
    css = (ROOT / "rendering" / "tei.css").read_text(encoding="utf-8")
    for selector in (".lg", ".lg br", ".l", ".head", ".figure", ".figdesc", ".table", ".ref",
                     ".rature", ".ajout", ".sic", ".lacune", ".petites-capitales", ".sp", ".speaker", ".stage"):
        assert f"\n{selector} " in css or f"\n{selector}," in css, selector
    # Qt ignore toute règle placée après un @media : il reste à la fin.
    assert css.rindex("@media") > css.rindex(".lg br")
