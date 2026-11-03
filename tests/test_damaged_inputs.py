# -*- coding: utf-8 -*-
"""Red team 2 (robustesse), sans Qt.

- B5 : un fichier d'alignement abîmé est décrit par une clé de message et
  l'endroit fautif (ligne et colonne du JSON, page, ligne, champ), que
  l'interface traduit.
- B2 : U+2029, séparateur de paragraphe Unicode, coupe un bloc de Qt :
  enregistré, il devenait un saut de ligne. À l'ouverture, il est écrit
  « &#x2029; », le même caractère pour XML.
- B8 : des inclusions XInclude en éventail (une partie incluse dix fois,
  qui en inclut dix…) croissaient sans borne : l'assemblage s'arrête au-delà
  d'un nombre d'éléments, avec un problème « too_large »."""
from __future__ import annotations

import json
import time
import xml.etree.ElementTree as ET

import pytest

import xml_assembly
from document_session import protect_paragraph_separators
from witness_resource_refresh import AlignmentError, read_alignment_json


@pytest.mark.parametrize("content, key, values", [
    ('{"pages": [}', "alignment.error.json", {"line": 1, "column": 12}),
    ('[1, 2]', "alignment.error.root", {}),
    ('{"pages": [{"id": "1r", "lines": 3}]}', "alignment.error.page", {"page": 1}),
    ('{"pages": [{"id": "1r", "lines": [{"line": 1}, 7]}]}', "alignment.error.line", {"page": 1, "line": 2}),
    ('{"pages": [{"id": "1r", "lines": [{"line": 1, "base_keys": ["a", 2]}]}]}', "alignment.error.keys",
     {"page": 1, "line": 1, "field": "base_keys"}),
])
def test_a_damaged_alignment_is_described_by_a_key_and_a_place(tmp_path, content, key, values):
    path = tmp_path / "T2.json"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(AlignmentError) as error:
        read_alignment_json(path)
    assert error.value.key == key
    assert {name: error.value.values[name] for name in values} == values


def test_an_unreadable_alignment_is_described_too(tmp_path):
    path = tmp_path / "T2.json"
    path.write_bytes(b'{"pages": ["\xff"]}')
    with pytest.raises(AlignmentError) as error:
        read_alignment_json(path)
    assert error.value.key == "alignment.error.read"
    with pytest.raises(AlignmentError) as error:
        read_alignment_json(tmp_path / "absent.json")
    assert error.value.key == "alignment.error.read"


def test_a_sound_alignment_is_read_as_before(tmp_path):
    data = {"pages": [{"id": "1r", "lines": [{"line": 1, "base_keys": ["1r::1"]}]}]}
    path = tmp_path / "T2.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    assert read_alignment_json(path) == data


def test_paragraph_separators_become_character_references():
    text = '<p n="a b">un deux</p>'
    protected, count = protect_paragraph_separators(text)
    assert count == 2 and " " not in protected
    assert protected == '<p n="a&#x2029;b">un&#x2029;deux</p>'
    element = ET.fromstring(protected)
    assert element.text == "un deux" and element.get("n") == "a b"
    assert protect_paragraph_separators("<p/>") == ("<p/>", 0)


def test_a_fan_of_inclusions_is_stopped(tmp_path, monkeypatch):
    monkeypatch.setattr(xml_assembly, "MAX_ASSEMBLED_ELEMENTS", 20000)
    tei = 'xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude"'
    for level in range(6):
        inner = "".join(f'<xi:include href="p{level + 1}.xml"/>' for _ in range(10)) if level < 5 else "<p>x</p>"
        (tmp_path / f"p{level}.xml").write_text(f'<div {tei}>{inner}</div>', encoding="utf-8")
    master = tmp_path / "edition.xml"
    text = f'<TEI {tei}><text><body><xi:include href="p0.xml"/></body></text></TEI>'
    master.write_text(text, encoding="utf-8")
    started = time.perf_counter()
    assembly = xml_assembly.assemble(text, master)
    assert time.perf_counter() - started < 10
    assert [p.code for p in assembly.problems] == ["too_large"]
    assert assembly.root is not None


def test_an_ordinary_assembly_is_unchanged(tmp_path):
    tei = 'xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude"'
    (tmp_path / "p1.xml").write_text(f'<div {tei}><p>un</p></div>', encoding="utf-8")
    master = tmp_path / "edition.xml"
    text = f'<TEI {tei}><text><body><xi:include href="p1.xml"/><xi:include href="p1.xml"/></body></text></TEI>'
    assembly = xml_assembly.assemble(text, master)
    assert not assembly.problems
    assert len(assembly.root.findall(".//{http://www.tei-c.org/ns/1.0}p")) == 2
