# -*- coding: utf-8 -*-
"""L'édition assemblée lue par l'export web (V0.9.1.6), sans Qt.

L'export web relisait le fichier de l'édition seul : le texte des parties
(XInclude) en était absent. Il lit désormais l'édition assemblée, chaque
élément rattaché à son texte : l'édition (0), ou un texte synchronisé à
part (1, 2…, dans l'ordre de l'édition), qui a son pivot et ses lignes.

- Jeu « corpus » (tests/corpus_data.py) : s02 synchronisé à part avec le
  pivot B, s04 (et son exemplum) avec le pivot A ; s01 et s03 dans la
  numérotation continue de l'édition.
- Projet exemple dont RLS_185 est passé dans une partie, synchronisée à part
  (165 lignes du pivot T1, après la 116e ligne de l'édition)."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from corpus_data import copy_example, make_corpus, move_to_part, split_alignments
from project_config import load_project
from web_viewer.assembled_document import VX_SEG, load_assembled
from web_viewer.tei_line_anchors import build_pivot_lb_index, build_segment_lb_index
from xml_assembly import path_key

TEI = "{http://www.tei-c.org/ns/1.0}"


@pytest.fixture
def corpus(tmp_path):
    return load_project(make_corpus(tmp_path / "corpus"))


@pytest.fixture
def example_text(tmp_path):
    project = copy_example(tmp_path / "exemple")
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    return load_project(project)


def _by_id(root, xml_id):
    return next(e for e in root.iter() if e.get("{http://www.w3.org/XML/1998/namespace}id") == xml_id)


def _pivot_lbs(document, k):
    target = "#" + document.segments[k].pivot
    return [e for e in document.root.iter(f"{TEI}lb")
            if e.get("edRef") == target and document.segment(e) == k]


def test_a_single_file_edition_is_read_as_before(tmp_path):
    assert load_assembled(load_project(copy_example(tmp_path / "exemple"))) is None


def test_each_element_belongs_to_its_text(corpus):
    document = load_assembled(corpus)
    assert [(s.index, s.name, s.pivot, s.prefix) for s in document.segments] == [
        (0, None, "A", ""), (1, "s02", "B", "~1~"), (2, "s04", "A", "~2~")]
    root = document.root
    assert document.segment(_by_id(root, "s01")) == 0
    assert document.segment(_by_id(root, "s02")) == 1
    assert document.segment(_by_id(root, "s03")) == 0
    assert document.segment(_by_id(root, "s04")) == 2
    assert document.segment(_by_id(root, "s04_exemplum")) == 2         # inclus par s04
    assert document.target(_by_id(root, "s02")) == "#B"
    # La marque technique ne reste pas dans l'arbre.
    assert not any(VX_SEG in e.attrib for e in root.iter())


def test_each_text_counts_the_lines_of_its_own_pivot(corpus, example_text):
    for project in (corpus, example_text):
        document = load_assembled(project)
        for segment in document.segments:
            assert len(_pivot_lbs(document, segment.index)) == document.lines.segment_count(segment.key)
    document = load_assembled(example_text)
    text = document.segments[1]
    assert (text.name, text.pivot, text.anchor) == ("rls185", "T1", 116)
    assert len(_pivot_lbs(document, 1)) == 165
    assert path_key(text.path) == text.key


def test_the_text_of_the_parts_is_in_the_document(corpus):
    root = load_assembled(corpus).root
    words = " ".join("".join(e.itertext()) for e in root.iter(f"{TEI}body"))
    assert "Sermo in adventu Domini" in words and "exempl" in words.lower()
    # Pas de xi:include ni de commentaire : ce que lirait xml.etree d'un fichier unique.
    assert not any(str(e.tag).endswith("}include") for e in root.iter())
    assert all(isinstance(e.tag, str) for e in root.iter())


def test_an_internal_entity_survives_the_assembly(tmp_path):
    project = make_corpus(tmp_path / "corpus")
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    text = text.replace("<TEI ", '<!DOCTYPE TEI [<!ENTITY ed "editio">]>\n<TEI ', 1)
    text = text.replace("<body>", "<body><p>&ed; nova</p>", 1)
    edition.write_text(text, encoding="utf-8")
    root = load_assembled(load_project(project)).root
    assert "editio nova" in "".join(next(root.iter(f"{TEI}body")).itertext())


def test_the_lines_of_each_text_follow_its_json(corpus):
    document = load_assembled(corpus)
    keys = {0: [f"A-12r::{n}" for n in range(1, 20)],
            1: [f"~1~B-30r::{n}" for n in range(1, 9)],
            2: [f"~2~A-13r::{n}" for n in range(1, 9)]}
    lookup, reports, order = build_segment_lb_index(document.root, document.segment,
                                                    {s.index: s.pivot for s in document.segments}, keys)
    assert [lookup[id(lb)] for lb in _pivot_lbs(document, 1)] == keys[1]
    assert [lookup[id(lb)] for lb in _pivot_lbs(document, 2)] == keys[2]
    assert all(reports[k].as_dict()["count_match"] for k in keys)
    # L'ordre de lecture : s01 (édition), s02, s03 (édition), s04 et son exemplum.
    assert order.index("~1~B-30r::1") > order.index("A-12r::1")
    assert order.index("~2~A-13r::8") == len(order) - 1
    assert sorted(order) == sorted(k for found in keys.values() for k in found)


def test_one_text_is_the_index_of_the_pivot():
    root = ET.fromstring('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p><lb edRef="#A"/>a '
                         '<lb edRef="#B"/>b <lb edRef="#A"/>c <lb edRef="#A"/>d</p></body></text></TEI>')
    keys = ["p::1", "p::2"]
    lookup, reports, order = build_segment_lb_index(root, lambda node: 0, {0: "A"}, {0: keys})
    old_lookup, old_report = build_pivot_lb_index(root, "A", keys)
    assert lookup == old_lookup and reports[0].as_dict() == old_report.as_dict()
    assert order == keys
