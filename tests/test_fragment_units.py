# -*- coding: utf-8 -*-
"""Éléments modifiables comme fragment (V0.9.2.9), sans Qt.

Le crayon ✎ de la Vue XSLT / CSS ouvre dans l'éditeur de fragment chaque
élément de ``model.divPart`` ou de ``model.inter``, et chaque ``<head>``,
``<figure>`` ou ``<note>``, du ``<body>``, sauf s'il est dans un autre
élément de cet ensemble : ce sont les blocs posés dans une division. Les
classes sont lues dans le schéma RELAX NG du projet, sinon dans la liste de
TEI P5 4.10.2."""
from __future__ import annotations

import os

import pytest
from lxml import etree

from fragment_units import (
    EDIT_NS, TEI_UNIT_NAMES, mark_units, unit_elements, unit_names_from_schema, unit_spans,
)

TEI_NS = "http://www.tei-c.org/ns/1.0"
HEADER = "<teiHeader><fileDesc><publicationStmt><p>Diffusion libre</p></publicationStmt></fileDesc></teiHeader>"


def _tei(body, front=""):
    return f'<TEI xmlns="{TEI_NS}">{HEADER}<text>{front}<body>{body}</body></text></TEI>'


def _units(text, names=TEI_UNIT_NAMES):
    return [text[start:end] for start, end in unit_spans(text, names)]


def _content(fragment, prefixes=""):
    root = etree.fromstring(f'<w xmlns="{TEI_NS}"{prefixes}>{fragment}</w>')
    return " ".join("".join(root.itertext()).split())


RULE_CASES = {
    "vers": ("<div><lg><l>vers un</l><l>vers deux</l></lg></div>",
             ["<lg><l>vers un</l><l>vers deux</l></lg>"]),
    "citation et note dans un paragraphe": ("<div><p>Il dit <quote>ceci</quote> <note>voir</note>.</p></div>",
                                             ["<p>Il dit <quote>ceci</quote> <note>voir</note>.</p>"]),
    "figure": ("<div><figure><head>Plan</head><p>Légende</p></figure></div>",
               ["<figure><head>Plan</head><p>Légende</p></figure>"]),
    "titre de division": ("<div><head>Titre</head><p>un</p><p>deux</p></div>",
                          ["<head>Titre</head>", "<p>un</p>", "<p>deux</p>"]),
    "cit": ("<div><cit><quote>q</quote><bibl>Aug.</bibl></cit></div>",
            ["<cit><quote>q</quote><bibl>Aug.</bibl></cit>"]),
    "liste dans une liste": ("<div><list><item>a<list><item>b</item></list></item></list></div>",
                             ["<list><item>a<list><item>b</item></list></item></list>"]),
    "réplique": ("<div><sp><speaker>A</speaker><p>x</p><l>y</l></sp></div>",
                 ["<sp><speaker>A</speaker><p>x</p><l>y</l></sp>"]),
    "ab dans ab": ("<div><ab>x<ab>y</ab></ab></div>", ["<ab>x<ab>y</ab></ab>"]),
    "texte flottant": ("<div><floatingText><body><p>a</p></body></floatingText></div>",
                       ["<floatingText><body><p>a</p></body></floatingText>"]),
    "note entre deux paragraphes": ("<div><p>a</p><note><p>n</p></note><p>b</p></div>",
                                    ["<p>a</p>", "<note><p>n</p></note>", "<p>b</p>"]),
    "élément vide": ('<div><p/><p rend="x"/></div>', ["<p/>", '<p rend="x"/>']),
    "chevron dans un attribut": ('<div><p rend="a>b">x</p></div>', ['<p rend="a>b">x</p>']),
    "divisions imbriquées": ("<div><div><head>I</head><p>a</p></div><div><p>b</p></div></div>",
                             ["<head>I</head>", "<p>a</p>", "<p>b</p>"]),
    "autres éléments ignorés": ('<div><pb n="1"/><p>a<lb/>b</p><milestone unit="x"/></div>', ["<p>a<lb/>b</p>"]),
}


@pytest.mark.parametrize("case", sorted(RULE_CASES))
def test_the_blocks_of_a_division_are_editable(case):
    body, expected = RULE_CASES[case]
    assert _units(_tei(body)) == expected


@pytest.mark.parametrize("case", sorted(RULE_CASES))
def test_the_tree_rule_finds_the_same_elements(case):
    text = _tei(RULE_CASES[case][0])
    elements = unit_elements(etree.fromstring(text.encode("utf-8")), TEI_UNIT_NAMES)
    found = [(etree.QName(e).localname, " ".join("".join(e.itertext()).split())) for e in elements]
    assert found == [(etree.QName(etree.fromstring(f'<w xmlns="{TEI_NS}">{u}</w>')[0]).localname, _content(u))
                     for u in _units(text)]


def test_only_the_body_counts():
    text = _tei("<div><p>corps</p></div>", front="<front><p>préface</p></front>") \
        .replace("</body>", "</body><back><p>annexe</p></back>")
    assert _units(text) == ["<p>corps</p>"]
    assert [e.text for e in unit_elements(etree.fromstring(text.encode()), TEI_UNIT_NAMES)] == ["corps"]


def test_every_body_of_a_group_counts():
    text = (f'<TEI xmlns="{TEI_NS}">{HEADER}<text><group><text><body><p>a</p></body></text>'
            '<text><body><lg><l>b</l></lg></body></text></group></text></TEI>')
    assert _units(text) == ["<p>a</p>", "<lg><l>b</l></lg>"]


def test_a_document_without_body_counts_whole():
    part = f'<div xmlns="{TEI_NS}" xml:id="s01"><head>Sermon</head><p>a</p><lg><l>b</l></lg></div>'
    assert _units(part) == ["<head>Sermon</head>", "<p>a</p>", "<lg><l>b</l></lg>"]
    root = etree.fromstring(part.encode())
    assert [etree.QName(e).localname for e in unit_elements(root, TEI_UNIT_NAMES)] == ["head", "p", "lg"]
    alone = f'<lg xmlns="{TEI_NS}"><l>b</l></lg>'
    assert _units(alone) == [alone]
    assert unit_elements(etree.fromstring(alone.encode()), TEI_UNIT_NAMES)[0].tag == f"{{{TEI_NS}}}lg"


def test_comments_cdata_and_instructions_are_not_read():
    body = "<div><!-- <p>caché</p> --><p>a</p><?pi <p>?><p><![CDATA[<p>]]>b</p></div>"
    assert _units(_tei(body)) == ["<p>a</p>", "<p><![CDATA[<p>]]>b</p>"]
    doctype = '<!DOCTYPE TEI [<!ENTITY x "<p>faux</p>">]>'
    assert _units(doctype + _tei("<div><p>a</p></div>")) == ["<p>a</p>"]


def test_prefixed_tei_elements():
    text = (f'<tei:TEI xmlns:tei="{TEI_NS}"><tei:text><tei:body><tei:div><tei:p>a</tei:p>'
            '<tei:lg><tei:l>b</tei:l></tei:lg></tei:div></tei:body></tei:text></tei:TEI>')
    assert _units(text) == ["<tei:p>a</tei:p>", "<tei:lg><tei:l>b</tei:l></tei:lg>"]


def test_mark_units_numbers_the_editable_elements():
    text = _tei('<div><head>T</head><p rend="x">a<note>n</note></p><p/><lg><l>v</l></lg></div>')
    marked, spans = mark_units(text, TEI_UNIT_NAMES)
    assert spans == unit_spans(text, TEI_UNIT_NAMES)
    root = etree.fromstring(marked.encode("utf-8"))
    edit = f"{{{EDIT_NS}}}edit"
    numbered = [(etree.QName(e).localname, e.get(edit)) for e in root.iter() if e.get(edit) is not None]
    assert numbered == [("head", "0"), ("p", "1"), ("p", "2"), ("lg", "3")]
    assert root.find(f".//{{{TEI_NS}}}body//{{{TEI_NS}}}p").get("rend") == "x"
    # Sans les attributs ajoutés, le texte est inchangé.
    for element in root.iter():
        element.attrib.pop(edit, None)
    etree.cleanup_namespaces(root)
    assert etree.tostring(root, encoding="unicode") == etree.tostring(etree.fromstring(text.encode()), encoding="unicode")


def test_the_tei_p5_list():
    for name in ("p", "ab", "l", "lg", "sp", "spGrp", "u", "annotationBlock", "list", "table", "quote", "cit",
                 "said", "bibl", "listBibl", "label", "stage", "castList", "floatingText", "listWit",
                 "head", "figure", "note"):
        assert name in TEI_UNIT_NAMES
    for name in ("div", "body", "hi", "lb", "pb", "item", "app", "rdg", "seg", "w"):
        assert name not in TEI_UNIT_NAMES
    assert len(TEI_UNIT_NAMES) == 57


RNG_NS = "http://relaxng.org/ns/structure/1.0"


def _rng(path, body):
    path.write_text(f'<grammar xmlns="{RNG_NS}" ns="{TEI_NS}">{body}</grammar>', encoding="utf-8")
    return path


def _element(name, define=None):
    return f'<define name="{define or name}"><element name="{name}"><text/></element></define>'


def test_classes_are_read_from_the_project_schema(tmp_path):
    """Les classes et leurs sous-classes, sur plusieurs fichiers ; un élément
    ajouté à model.divPart par une personnalisation (combine="choice")
    devient modifiable."""
    _rng(tmp_path / "inter.rng",
         '<define name="model.inter"><choice><ref name="model.listLike"/><ref name="quote"/></choice></define>'
         '<define name="model.listLike"><ref name="list"/></define>' + _element("list") + _element("quote"))
    schema = _rng(tmp_path / "projet.rng",
                  '<start><ref name="TEI"/></start>' + _element("TEI") + '<include href="inter.rng"/>'
                  '<define name="model.divPart"><choice><ref name="model.pLike"/><ref name="lg"/></choice></define>'
                  '<define name="model.pLike"><choice><ref name="p"/><ref name="ab"/></choice></define>'
                  '<define name="model.divPart" combine="choice"><ref name="strophe"/></define>'
                  + "".join(_element(n) for n in ("p", "ab", "lg", "strophe", "item", "hi")))
    names = unit_names_from_schema(schema)
    assert names == frozenset({"p", "ab", "lg", "strophe", "list", "quote", "head", "figure", "note"})


def test_prefixed_definitions_give_the_element_names(tmp_path):
    schema = _rng(tmp_path / "prefixe.rng",
                  '<define name="model.divPart"><choice><ref name="tei_p"/><ref name="tei_lg"/></choice></define>'
                  '<define name="model.inter"><notAllowed/></define>'
                  + _element("p", "tei_p") + _element("lg", "tei_lg"))
    assert unit_names_from_schema(schema) == frozenset({"p", "lg", "head", "figure", "note"})


def test_a_schema_without_the_classes_gives_none(tmp_path):
    schema = _rng(tmp_path / "autre.rng", '<start><ref name="doc"/></start>' + _element("doc"))
    assert unit_names_from_schema(schema) is None
    assert unit_names_from_schema(tmp_path / "absent.rng") is None
    bad = tmp_path / "casse.rng"
    bad.write_text("<grammar", encoding="utf-8")
    assert unit_names_from_schema(bad) is None


def test_the_schema_is_read_again_when_it_changes(tmp_path):
    schema = _rng(tmp_path / "projet.rng",
                  '<define name="model.divPart"><ref name="p"/></define>' + _element("p"))
    first = unit_names_from_schema(schema)
    assert unit_names_from_schema(schema) is first
    _rng(schema, '<define name="model.divPart"><choice><ref name="p"/><ref name="lg"/></choice></define>'
                 + _element("p") + _element("lg"))
    stat = schema.stat()
    os.utime(schema, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1_000_000))
    assert "lg" in unit_names_from_schema(schema)
