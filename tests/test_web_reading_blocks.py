# -*- coding: utf-8 -*-
"""Texte de lecture de l'export web (V0.9.3.0), sans Qt.

``extract_reading_document`` fait du TEI une suite de blocs. Une division
est un bloc ``div`` (identifiant, niveau, titre) ; ses titres, paragraphes,
vers, entrées de liste, cellules de tableau, légendes et notes posées entre
deux blocs sont des blocs rendus (``RENDERED_BLOCKS``). Une division est
titrée par son premier ``<head>``, sinon par son ``@n``, jamais par son
``@xml:id``. Tous les textes sont lus : ``<front>``, ``<body>`` et
``<back>``, et chaque texte d'un ``<group>``.

Le texte suit « Édition critique » : une forme d'un ``<choice>`` (les autres
en infobulle), ratures barrées, ajouts marqués, restitutions entre
crochets, lacunes « […] ». Les leçons d'un ``<rdgGrp>`` sont lues ; la
langue du texte est donnée au viewer."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from web_viewer.legacy_v11_core import RENDERED_BLOCKS, extract_corrected_pages, extract_reading_document

TEI_NS = "http://www.tei-c.org/ns/1.0"


def _root(body, front="", back="", text=""):
    return ET.fromstring(f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
                         f'</fileDesc></teiHeader><text{text}>{front}<body>{body}</body>{back}</text></TEI>')


def _reading(body, keys=None, **parts):
    return extract_reading_document(None, "#A", root=_root(body, **parts), base_line_keys=keys)


def _text(block):
    return " ".join("".join(seg.get("text", "") for seg in block["segments"] if seg["kind"] == "text").split())


def _blocks(reading, *attrs):
    """``(type, texte, attributs demandés présents)`` de chaque bloc."""
    return [(block["type"], _text(block), {name: block["attrs"][name] for name in attrs if name in block["attrs"]})
            for block in reading["blocks"]]


def test_a_division_is_titled_by_its_head_or_its_n_never_by_its_identifier():
    reading = _reading('<div xml:id="RLS_184"><p>a</p></div><div n="Sermo 2"><p>b</p></div>'
                       '<div n="tertius" xml:id="d3"><head>Titulus</head><p>c</p></div>')
    assert _blocks(reading, "title", "label", "div_title") == [
        ("div", "", {}), ("p", "a", {}),
        ("div", "", {"title": "Sermo 2", "label": "Sermo 2"}), ("p", "b", {}),
        ("div", "", {"label": "Titulus"}), ("head", "Titulus", {"div_title": True}), ("p", "c", {})]
    ids = [block["attrs"]["id"] for block in reading["blocks"] if block["type"] == "div"]
    assert ids[0] == "RLS_184" and ids[2] == "d3"
    assert len(set(ids)) == 3 and ids[1] not in ("RLS_184", "d3")
    assert not any(block["type"] == "sermon" for block in reading["blocks"])


def test_a_generated_identifier_is_not_one_of_the_document():
    reading = _reading('<div><p xml:id="div-1">a</p></div><div><p xml:id="div-2">b</p></div>')
    ids = [block["attrs"]["id"] for block in reading["blocks"] if block["type"] == "div"]
    assert len(set(ids)) == 2 and not set(ids) & {"div-1", "div-2"}


def test_divisions_have_their_level():
    reading = _reading('<div><head>I</head><div><head>I.1</head><p>a</p></div><div><p>b</p></div></div>'
                       '<div1><head>II</head><div2><head>II.1</head><p>c</p></div2></div1>')
    assert [(block["attrs"]["level"], block["attrs"].get("label")) for block in reading["blocks"]
            if block["type"] == "div"] == [(1, "I"), (2, "I.1"), (2, None), (1, "II"), (2, "II.1")]
    assert [block["attrs"].get("div_title", False) for block in reading["blocks"] if block["type"] == "head"] \
        == [True] * 4


def test_the_title_of_a_division_is_its_reading_without_notes():
    reading = _reading('<div><head>Caput <app><lem wit="#A">unum</lem><rdg wit="#B">primum</rdg></app>'
                       '<note>nota</note></head><p>a</p></div>')
    assert reading["blocks"][0]["attrs"]["label"] == "Caput unum"
    head = reading["blocks"][1]
    assert [seg["kind"] for seg in head["segments"]] == ["text", "text", "variant-marker", "note"]


def test_a_verse_group_is_a_stanza_of_numbered_lines():
    reading = _reading('<div><lg><head>Carmen</head><l n="1">uersus unus</l><l n="2">uersus duo</l></lg>'
                       '<lg><l>tertius</l></lg><l>quartus</l><l>quintus</l></div>')
    blocks = [block for block in reading["blocks"] if block["type"] != "div"]
    assert [(block["type"], _text(block), block["attrs"].get("n")) for block in blocks] == [
        ("head", "Carmen", None), ("l", "uersus unus", "1"), ("l", "uersus duo", "2"),
        ("l", "tertius", None), ("l", "quartus", None), ("l", "quintus", None)]
    groups = [block["attrs"]["group"] for block in blocks[1:]]
    assert groups[0] == groups[1] and groups[2] not in (groups[0], groups[3])
    assert groups[3] == groups[4]
    assert not blocks[0]["attrs"].get("div_title")


def test_a_page_break_between_two_lines_stays_in_the_stanza():
    reading = _reading('<div><lg><l>a</l><pb n="2r"/><l>b</l></lg></div>')
    assert [block["type"] for block in reading["blocks"]] == ["div", "l", "l"]
    assert [seg["kind"] for seg in reading["blocks"][1]["segments"]] == ["text", "pb"]


def test_lists_numbered_or_not_and_nested():
    reading = _reading('<div><list><head>Index</head><item>a<list><item>a1</item><item>a2</item></list>'
                       'suite de a</item><item>b</item></list>'
                       '<list rend="numbered"><item>primum</item></list><list type="ordered"><item>secundum</item>'
                       '</list><list rend="unnumbered"><item>tres</item></list></div>')
    blocks = [block for block in reading["blocks"] if block["type"] != "div"]
    assert [(block["type"], _text(block)) for block in blocks] == [
        ("head", "Index"), ("item", "a"), ("item", "a1"), ("item", "a2"), ("item", "suite de a"), ("item", "b"),
        ("item", "primum"), ("item", "secundum"), ("item", "tres")]
    items = [block["attrs"] for block in blocks[1:]]
    assert [attrs["depth"] for attrs in items] == [1, 2, 2, 1, 1, 1, 1, 1]
    assert [attrs.get("cont", False) for attrs in items] == [False, False, False, True, False, False, False, False]
    lists = [attrs["list"] for attrs in items]
    assert lists[0] == lists[3] == lists[4] and lists[1] == lists[2] != lists[0]
    assert len(set(lists[5:]) | {lists[0], lists[1]}) == 5
    assert [attrs["numbered"] for attrs in items] == [False] * 5 + [True, True, False]


def test_a_list_in_a_paragraph_is_not_merged_into_it():
    reading = _reading("<div><p>ante <list><item>i</item></list> post</p></div>")
    assert _blocks(reading, "cont")[1:] == [("p", "ante", {}), ("item", "i", {}), ("p", "post", {"cont": True})]


def test_a_table_is_made_of_cells():
    reading = _reading('<div><table rows="3" cols="2"><head>Tabula</head>'
                       '<row role="label"><cell>Nomen</cell><cell>Folium</cell></row>'
                       '<row><cell role="label">Petrus</cell><cell>12r</cell></row>'
                       '<row><cell cols="2" rows="1">to<lb edRef="#A"/>tum '
                       '<app><lem wit="#A">x</lem><rdg wit="#B">y</rdg></app><note>nota</note></cell></row>'
                       '<row><cell/><cell>z</cell></row></table>'
                       '<table><row><cell>alia</cell></row></table></div>', keys=["P::1"])
    blocks = [block for block in reading["blocks"] if block["type"] != "div"]
    head, cells = blocks[0], blocks[1:]
    assert head["type"] == "head" and _text(head) == "Tabula" and "table" in head["attrs"]
    assert not head["attrs"].get("div_title")
    assert [(block["type"], _text(block), block["attrs"]["row"], block["attrs"].get("label", False))
            for block in cells] == [
        ("cell", "Nomen", 1, True), ("cell", "Folium", 1, True), ("cell", "Petrus", 2, True),
        ("cell", "12r", 2, False), ("cell", "to tum x", 3, False), ("cell", "", 4, False), ("cell", "z", 4, False),
        ("cell", "alia", 1, False)]
    tables = [block["attrs"]["table"] for block in cells]
    assert set(tables[:7]) == {head["attrs"]["table"]} and tables[7] != tables[0]
    assert cells[4]["attrs"]["cols"] == 2 and "rows" not in cells[4]["attrs"]
    assert [seg["kind"] for seg in cells[4]["segments"]] == ["text", "text", "text", "variant-marker", "note"]
    assert cells[4]["segments"][1]["line_key"] == "P::1"
    assert "y" not in _text(cells[4])


def test_a_figure_has_its_title_and_its_caption():
    reading = _reading('<div><figure><head>Imago</head><figDesc>Descriptio</figDesc>'
                       '<graphic url="x.png"/></figure></div>')
    assert _blocks(reading)[1:] == [("head", "Imago", {}), ("caption", "Descriptio", {})]


def test_a_note_between_two_paragraphs_is_a_note_marker():
    reading = _reading("<div><p>a</p><note>Nota inter paragraphos</note><p>b</p></div>")
    assert [block["type"] for block in reading["blocks"]] == ["div", "p", "note", "p"]
    marker = reading["blocks"][2]["segments"]
    assert [seg["kind"] for seg in marker] == ["note"]
    assert reading["annotations"][marker[0]["ann_id"]]["text"] == "Nota inter paragraphos"
    assert "Nota" not in "".join(_text(block) for block in reading["blocks"])


def test_front_and_back_are_divisions():
    reading = _reading("<div><p>corpus</p></div>",
                       front="<front><div><head>Praefatio</head><p>f</p></div></front>",
                       back='<back><div n="Index"><p>z</p></div></back>')
    assert [(block["type"], _text(block), block["attrs"].get("part"), block["attrs"].get("level"),
             block["attrs"].get("label")) for block in reading["blocks"]] == [
        ("div", "", "front", 1, None), ("div", "", None, 2, "Praefatio"), ("head", "Praefatio", None, None, None),
        ("p", "f", None, None, None),
        ("div", "", None, 1, None), ("p", "corpus", None, None, None),
        ("div", "", "back", 1, None), ("div", "", None, 2, "Index"), ("p", "z", None, None, None)]


def test_every_text_of_a_group_is_read():
    root = ET.fromstring(f'<TEI xmlns="{TEI_NS}"><teiHeader/><text><group>'
                         '<text n="Textus A"><body><div><head>I</head><p>a</p></div></body></text>'
                         '<text><body><p>b</p></body></text></group></text></TEI>')
    reading = extract_reading_document(None, "#A", root=root)
    assert [(block["type"], _text(block), block["attrs"].get("level"), block["attrs"].get("title"))
            for block in reading["blocks"]] == [
        ("div", "", 1, "Textus A"), ("div", "", 2, None), ("head", "I", None, None), ("p", "a", None, None),
        ("div", "", 1, None), ("p", "b", None, None)]


def test_titles_and_lines_keep_their_line_keys():
    keys = ["P::1", "P::2", "P::3", "P::4"]
    reading = _reading('<div><head><lb edRef="#A"/>Titulus</head><lg><l><lb edRef="#A"/>uersus</l></lg>'
                       '<p><lb edRef="#A"/>prosa</p><lb edRef="#A"/><p>post lineam</p></div>', keys=keys)
    texts = [(seg["text"].strip(), seg["line_key"]) for block in reading["blocks"] for seg in block["segments"]
             if seg["kind"] == "text"]
    assert texts == [("Titulus", "P::1"), ("uersus", "P::2"), ("prosa", "P::3"), ("post lineam", "P::4")]


def test_lacunae_stay_in_place_in_rendered_blocks():
    reading = _reading('<div><lacunaStart wit="#B"/><head>T</head><lg><l>a</l><lacunaEnd wit="#B"/>'
                       '<l>b</l></lg><p>c</p></div>')
    flat = [(block["type"], seg) for block in reading["blocks"] for seg in block["segments"]]
    order = [seg["kind"] if seg["kind"] != "text" else seg["text"] for _type, seg in flat]
    assert order == ["lacuna", "T", "a", "lacuna", "b", "c"]
    assert all(kind in RENDERED_BLOCKS for kind, seg in flat if seg["kind"] == "lacuna")


def test_an_anonymous_block_is_a_paragraph_and_a_variant_keeps_one_reading():
    reading = _reading('<div><ab>x <app><lem wit="#A">ille</lem><rdg wit="#B">iste</rdg></app></ab>'
                       '<quote><p>q1</p><p>q2</p></quote>'
                       '<cit type="bible"><quote>Verbum</quote><ref>Io 1, 1</ref></cit></div>')
    assert _blocks(reading)[1:] == [("p", "x ille", {}), ("p", "q1", {}), ("p", "q2", {}), ("p", "Verbum", {})]
    cit = reading["blocks"][-1]["segments"]
    assert [seg["kind"] for seg in cit] == ["text", "editorial-ref"]
    assert "quote" in cit[0]["styles"]


def test_a_title_page_keeps_its_parts_apart():
    reading = _reading("<div><p>a</p></div>", front="<front><titlePage><docTitle><titlePart>Liber</titlePart>"
                                                    "</docTitle><byline>auctore Petro</byline></titlePage></front>")
    assert _blocks(reading)[:3] == [("div", "", {}), ("p", "Liber", {}), ("p", "auctore Petro", {})]


def test_every_block_is_a_division_or_rendered():
    assert RENDERED_BLOCKS == {"p", "head", "l", "item", "cell", "caption", "note"}
    reading = _reading('<div><head>T</head><lg><l>a</l></lg><list><item>b</item></list>'
                       '<table><row><cell>c</cell></row></table><figure><figDesc>d</figDesc></figure>'
                       '<note>e</note><p>f</p></div>')
    assert {block["type"] for block in reading["blocks"]} == RENDERED_BLOCKS | {"div"}


def test_the_lines_of_front_and_back_are_extracted_for_the_facsimile():
    root = _root('<div><p><lb edRef="#A"/>corpus</p></div>',
                 front='<front><div><p><lb edRef="#A"/>praefatio</p></div></front>',
                 back='<back><div><p><lb edRef="#A"/>appendix</p></div></back>')
    pages, _labels = extract_corrected_pages(None, "#A", root=root, base_line_keys=["P::1", "P::2", "P::3"])
    assert [(line["line_key"], line["text"]) for line in pages["P"]] == [
        ("P::1", "praefatio"), ("P::2", "corpus"), ("P::3", "appendix")]


# W.2 : phénomènes éditoriaux comme « Édition critique », <rdgGrp>, langue, <hi>.

def _segments(reading):
    return [seg for block in reading["blocks"] for seg in block["segments"]]


def test_a_choice_shows_one_form_and_gives_the_other_in_a_tooltip():
    reading = _reading('<div><p>Isti <choice><sic>erat</sic><corr>erant</corr></choice> '
                       '<choice><abbr>dns</abbr><expan>dominus</expan></choice> '
                       '<choice><orig>uita</orig><reg>vita</reg></choice> '
                       '<choice><sic>solum</sic></choice> <choice><seg>unum</seg><seg>alterum</seg></choice></p></div>')
    paragraph = reading["blocks"][1]
    assert _text(paragraph) == "Isti erant dominus vita solum unum"
    assert [seg["alt"] for seg in paragraph["segments"] if seg.get("alt")] == [
        [["sic", "erat"]], [["abbr", "dns"]], [["orig", "uita"]], [["seg", "alterum"]]]
    solum = next(seg for seg in paragraph["segments"] if seg.get("text") == "solum")
    assert "sic" in solum["styles"] and "alt" not in solum


def test_a_choice_in_a_reading_keeps_its_variant():
    reading = _reading('<div><p><app><lem wit="#A"><choice><sic>erat</sic><corr>erant</corr></choice></lem>'
                       '<rdg wit="#B">fuit</rdg></app></p></div>')
    erant = next(seg for seg in _segments(reading) if seg.get("text") == "erant")
    assert erant.get("variant_id") and erant["alt"] == [["sic", "erat"]]
    ann = reading["annotations"][erant["variant_id"]]
    assert ann["selected"] == "erant" and [r["text"] for r in ann["readings"]] == ["erant", "fuit"]


def test_deletions_additions_supplied_text_gaps_and_spaces():
    reading = _reading('<div><p><del>deleta</del> <add>addita</add> <surplus>et</surplus> '
                       'Pe<supplied>trus</supplied><space quantity="3"/>fin<gap reason="illegible" extent="3 litterae"/>is '
                       '<gap/></p></div>')
    paragraph = reading["blocks"][1]
    assert _text(paragraph) == "deleta addita et Pe[trus] fin[…]is […]"
    styles = {seg["text"].strip(): seg["styles"] for seg in paragraph["segments"] if seg["kind"] == "text"}
    assert styles["deleta"] == ["del"] and styles["et"] == ["del"] and styles["addita"] == ["add"]
    assert styles["[trus]"] == ["supplied"]
    gaps = [seg for seg in paragraph["segments"] if seg.get("text", "").strip() == "[…]"]
    assert [(seg["styles"], seg["alt"]) for seg in gaps] == [
        (["gap"], [["gap", "illegible · 3 litterae"]]), (["gap"], [["gap", ""]])]


def test_renditions_of_hi():
    reading = _reading('<div><p>x <hi rend="sup">a</hi> <hi rend="superscript">b</hi> <hi rend="sub">c</hi> '
                       '<hi rend="subscript">d</hi> <hi rend="underline">e</hi> <hi rend="italic bold">f</hi> '
                       '<hi rend="smallcaps">g</hi></p></div>')
    styles = {seg["text"].strip(): seg["styles"] for seg in _segments(reading) if seg["kind"] == "text"}
    assert [styles[x] for x in "abcdefg"] == [["sup"], ["sup"], ["sub"], ["sub"], ["underline"], ["italic", "bold"],
                                              ["smallcaps"]]


def test_the_readings_of_a_reading_group_are_read():
    reading = _reading('<div><p>a <app><lem wit="#B">ille</lem><rdgGrp type="orth"><rdg wit="#A">iste</rdg>'
                       '<rdg wit="#C">yste</rdg></rdgGrp></app> b</p>'
                       '<p><app><rdgGrp><rdg wit="#B">primus</rdg></rdgGrp><rdgGrp><rdg wit="#C">secundus</rdg>'
                       '</rdgGrp></app></p></div>')
    first, second = reading["blocks"][1], reading["blocks"][2]
    assert _text(first) == "a iste b" and _text(second) == "primus"
    marker = next(seg for seg in first["segments"] if seg["kind"] == "variant-marker")
    ann = reading["annotations"][marker["ann_id"]]
    assert [(r["role"], r["wit"], r["text"]) for r in ann["readings"]] == [
        ("lem", ["B"], "ille"), ("rdg", ["A"], "iste"), ("rdg", ["C"], "yste")]
    assert ann["selected"] == "iste"


def test_a_lacuna_in_a_reading_group_not_shown():
    reading = _reading('<div><p>a<app><lem wit="#A"/><rdgGrp><rdg wit="#B"><lacunaStart/></rdg></rdgGrp></app>'
                       '</p></div>')
    assert [(seg["start"], seg["wit"]) for seg in _segments(reading) if seg["kind"] == "lacuna"] == [(True, ["B"])]


def test_the_document_has_the_language_of_its_text():
    assert _reading("<div><p>a</p></div>", text=' xml:lang="la"')["lang"] == "la"
    root = ET.fromstring(f'<TEI xmlns="{TEI_NS}" xml:lang="fr"><teiHeader/><text><body><p>a</p></body></text></TEI>')
    assert extract_reading_document(None, "#A", root=root)["lang"] == "fr"
    assert "lang" not in _reading("<div><p>a</p></div>")


def test_the_lines_for_the_facsimile_show_one_form_of_a_choice_and_a_reading_group():
    root = _root('<div><p><lb edRef="#A"/>Isti <choice><sic>erat</sic><corr>erant</corr></choice> '
                 '<app><lem wit="#B">ille</lem><rdgGrp><rdg wit="#A">iste</rdg></rdgGrp></app></p></div>')
    pages, _labels = extract_corrected_pages(None, "#A", root=root, base_line_keys=["P::1"])
    assert pages["P"][0]["text"] == "Isti erant iste"


def test_the_reference_of_a_biblical_quotation_stays_in_angle_brackets_the_others_are_notes():
    """V0.9.3.0 : comme « Édition critique », le <ref> d'une <cit
    type="bible"> reste une référence entre chevrons ; celui d'une autre
    <cit> est un repère de note ; un <ref> hors d'une <cit> ne change pas."""
    reading = _reading('<div><p>Dixit <cit type="bible"><quote>Uos estis</quote><ref>Lc. 22:28</ref></cit> et '
                       '<cit><quote>Ait Augustinus</quote><ref>Aug. Conf. 1</ref></cit> '
                       '<ref target="#x">alia</ref>.</p></div>')
    segments = reading["blocks"][1]["segments"]
    assert [(seg["kind"], seg.get("text", "").strip()) for seg in segments if seg["kind"] != "text"] == [
        ("editorial-ref", "Lc. 22:28"), ("note", ""), ("editorial-ref", "alia")]
    note = next(seg for seg in segments if seg["kind"] == "note")
    annotation = reading["annotations"][note["ann_id"]]
    assert (annotation["kind"], annotation["text"], annotation["type"]) == ("note", "Aug. Conf. 1", "ref")
    assert "Aug." not in _text(reading["blocks"][1])
