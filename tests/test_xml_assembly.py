# -*- coding: utf-8 -*-
"""Assemblage d'une édition par XInclude (xml_assembly), sans Qt.

Le jeu « sermons » (tests/data/sermons, copie du projet d'essai « Essai
sermons Varians ») couvre les formes d'inclusion : fragment, ``xpointer`` par
identifiant, ``element()`` et inclusion imbriquée. Les autres cas sont écrits
dans des fichiers minimaux.
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from lxml import etree

from xml_assembly import assemble, find_includes

DATA = Path(__file__).resolve().parent / "data" / "sermons"
TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
MASTER_HEAD = ('<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">'
               '<text><body>\n')


@pytest.fixture
def sermons(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return root / "xml"


def _master(tmp_path, body, name="edition.xml"):
    path = tmp_path / name
    path.write_text(MASTER_HEAD + body + "\n</body></text></TEI>\n", encoding="utf-8")
    return path


def _assemble(path, texts=None):
    return assemble(path.read_text(encoding="utf-8"), path, texts)


def _by_id(assembly, ident):
    found = assembly.root.xpath("//*[@xml:id=$i]", i=ident)
    return found[0] if found else None


def _codes(assembly):
    return [(p.file.name, p.line, p.code) for p in assembly.problems]


def test_find_includes_lists_each_inclusion_with_its_line(sermons):
    includes = find_includes((sermons / "edition.xml").read_text(encoding="utf-8"))
    assert [(i.href, i.xpointer, i.line) for i in includes] == [
        ("sermons/s01.xml", "", 34),
        ("sermons/s02.xml", "s02", 36),
        ("sermons/s03.xml", "element(/1/2/1/1)", 38),
        ("sermons/s04.xml", "", 40),
    ]
    assert all(i.parse == "xml" and not i.has_fallback for i in includes)


def test_find_includes_of_a_malformed_text_is_empty():
    assert find_includes("<TEI><xi:include href='a.xml'/>") == []


def test_the_sermons_are_assembled_like_lxml_does(sermons):
    master = sermons / "edition.xml"
    assembly = _assemble(master)
    assert assembly.problems == ()
    reference = etree.parse(str(master))
    reference.xinclude()
    ours = etree.canonicalize(etree.tostring(assembly.root, encoding="unicode"))
    theirs = etree.canonicalize(etree.tostring(reference.getroot(), encoding="unicode"))
    assert ours == theirs


def test_parts_are_listed_in_inclusion_order(sermons):
    assembly = _assemble(sermons / "edition.xml")
    assert [p.relative_to(sermons).as_posix() for p in assembly.parts] == [
        "sermons/s01.xml", "sermons/s02.xml", "sermons/s03.xml", "sermons/s04.xml",
        "sermons/s04_exemplum.xml"]


def test_each_element_keeps_its_file_and_line(sermons):
    assembly = _assemble(sermons / "edition.xml")
    quote = assembly.root.xpath("//tei:quote[@typ]", namespaces={"tei": TEI})[0]
    assert (assembly.origin(quote).name, quote.sourceline) == ("s02.xml", 27)
    gregorius = assembly.root.xpath("//tei:persName[contains(@ref, 'gregorius')]", namespaces={"tei": TEI})[0]
    assert (assembly.origin(gregorius).name, gregorius.sourceline) == ("s04_exemplum.xml", 4)
    head = _by_id(assembly, "s04")[0]
    assert (assembly.origin(head).name, head.sourceline) == ("s04.xml", 3)
    preface = assembly.root.xpath("//tei:front/tei:div", namespaces={"tei": TEI})[0]
    assert (assembly.origin(preface).name, preface.sourceline) == ("edition.xml", 27)


def test_the_text_of_an_open_part_replaces_the_file(sermons):
    part = sermons / "sermons" / "s01.xml"
    edited = part.read_text(encoding="utf-8").replace("Sermo in adventu Domini", "Titre non enregistré")
    assembly = _assemble(sermons / "edition.xml", {part: edited})
    assert _by_id(assembly, "s01")[0].text == "Titre non enregistré"
    assert "Titre non enregistré" not in part.read_text(encoding="utf-8")


@pytest.mark.parametrize("xpointer, expected", [
    ("s02", "s02"),
    ("element(s02)", "s02"),
    ("element(/1/2/1/1)", "s02"),
    ("element(s02/1)", "s02_head"),
    ("xmlns(t=http://www.tei-c.org/ns/1.0) element(s02)", "s02"),
])
def test_xpointer_forms(tmp_path, xpointer, expected):
    (tmp_path / "part.xml").write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
        '<div xml:id="s02"><head xml:id="s02_head">t</head><p>a</p></div></body></text></TEI>',
        encoding="utf-8")
    assembly = _assemble(_master(tmp_path, f'<xi:include href="part.xml" xpointer="{xpointer}"/>'))
    assert assembly.problems == ()
    body = assembly.root.find(f"{{{TEI}}}text/{{{TEI}}}body")
    assert [child.get(XML_ID) for child in body] == [expected]
    assert body[0].tail == "\n"


def test_the_same_file_included_twice_is_one_part(tmp_path):
    (tmp_path / "two.xml").write_text(
        '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div xml:id="a"/><div xml:id="b"/></body></text></TEI>',
        encoding="utf-8")
    assembly = _assemble(_master(tmp_path, '<xi:include href="two.xml" xpointer="a"/>'
                                           '<xi:include href="two.xml" xpointer="b"/>'))
    assert [p.name for p in assembly.parts] == ["two.xml"]
    assert _by_id(assembly, "a") is not None and _by_id(assembly, "b") is not None


def test_a_missing_part_is_reported_at_its_inclusion(tmp_path):
    (tmp_path / "present.xml").write_text('<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="ok"/>', encoding="utf-8")
    assembly = _assemble(_master(tmp_path, '<xi:include href="absent.xml"/>\n<xi:include href="present.xml"/>'))
    assert _codes(assembly) == [("edition.xml", 2, "missing")]
    assert _by_id(assembly, "ok") is not None
    assert not assembly.root.xpath("//xi:include", namespaces={"xi": "http://www.w3.org/2001/XInclude"})
    # Une partie absente n'a pas d'onglet à ouvrir ; une partie mal formée, si.
    assert [p.name for p in assembly.parts] == ["present.xml"]


def test_a_malformed_part_is_reported_in_its_own_file(tmp_path):
    (tmp_path / "bad.xml").write_text('<div xmlns="http://www.tei-c.org/ns/1.0">\n<p>\n</div>', encoding="utf-8")
    assembly = _assemble(_master(tmp_path, '<xi:include href="bad.xml"/>'))
    [problem] = assembly.problems
    assert (problem.file.name, problem.line, problem.code) == ("bad.xml", 3, "malformed")
    assert problem.detail
    assert [p.name for p in assembly.parts] == ["bad.xml"]


def test_a_circular_inclusion_is_reported_and_stopped(tmp_path):
    (tmp_path / "a.xml").write_text(
        '<div xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude" xml:id="a">\n'
        '<xi:include href="b.xml"/></div>', encoding="utf-8")
    (tmp_path / "b.xml").write_text(
        '<div xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude" xml:id="b">\n\n'
        '<xi:include href="a.xml"/></div>', encoding="utf-8")
    assembly = _assemble(_master(tmp_path, '<xi:include href="a.xml"/>'))
    assert _codes(assembly) == [("b.xml", 3, "circular")]
    assert _by_id(assembly, "a") is not None and _by_id(assembly, "b") is not None


@pytest.mark.parametrize("include, code", [
    ('<xi:include href="notes.txt" parse="text"/>', "parse_text"),
    ('<xi:include href="absent.xml"><xi:fallback><p/></xi:fallback></xi:include>', "fallback"),
    ('<xi:include href="part.xml" xpointer="xpointer(//div)"/>', "xpointer_unsupported"),
    ('<xi:include href="part.xml" xpointer="nope"/>', "xpointer_not_found"),
    ('<xi:include href="http://example.org/part.xml"/>', "href_unsupported"),
    ('<xi:include xpointer="s01"/>', "href_unsupported"),
])
def test_unsupported_inclusions_are_reported(tmp_path, include, code):
    (tmp_path / "notes.txt").write_text("texte", encoding="utf-8")
    (tmp_path / "part.xml").write_text('<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="p"/>', encoding="utf-8")
    assembly = _assemble(_master(tmp_path, include))
    assert _codes(assembly) == [("edition.xml", 2, code)]


def test_a_part_with_a_fallback_is_included_normally_when_it_exists(tmp_path):
    (tmp_path / "part.xml").write_text('<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="p"/>', encoding="utf-8")
    assembly = _assemble(_master(tmp_path, '<xi:include href="part.xml"><xi:fallback/></xi:include>'))
    assert assembly.problems == () and _by_id(assembly, "p") is not None


def test_a_malformed_master_has_no_assembly(tmp_path):
    master = tmp_path / "edition.xml"
    master.write_text("<TEI>\n<text>", encoding="utf-8")
    assembly = _assemble(master)
    assert assembly.root is None and assembly.parts == ()
    assert [(p.file.name, p.code) for p in assembly.problems] == [("edition.xml", "malformed")]


def test_a_document_without_inclusion_is_unchanged(tmp_path):
    master = _master(tmp_path, "<p>seul</p>")
    assembly = _assemble(master)
    assert assembly.parts == () and assembly.problems == ()
    assert etree.tostring(assembly.root) == etree.tostring(etree.parse(str(master)).getroot())
