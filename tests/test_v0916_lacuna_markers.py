# -*- coding: utf-8 -*-
"""Repères de lacune dans le texte de lecture de l'export web (V0.9.1.6).

Chaque <lacunaStart/> et <lacunaEnd/> devient un segment invisible du texte
de lecture : {"kind": "lacuna", "start": …, "wit": […]}. Le témoin vient de
@wit, sinon de la leçon (<rdg>, <lem>) qui contient la balise, comme sur le
bureau (pivot_lines). Le viewer en tire les bandeaux de lacune.

Projet exemple (corpus_data.add_example_lacunae) : T2 en lacune de la ligne
20 du pivot T1 à la ligne 25 ; un passage absent de T1 avant la ligne 41."""
from __future__ import annotations

import json

import pytest

from corpus_data import PIVOT_GAP, T2_END, T2_START, add_example_lacunae, copy_example, insert_at
from pivot_lines import pivot_lb_pattern
from web_viewer.legacy_v11_core import extract_reading_document
from web_viewer.segment_views import doc_positions


def _keys(project):
    data = json.loads((project.parent / "alignments" / "T1.json").read_text(encoding="utf-8"))
    return [f"{page['id']}::{line.get('line')}" for page in data["pages"] for line in page["lines"]]


def _reading(project):
    edition = project.parent / "xml" / "edition.xml"
    return extract_reading_document(edition, "#T1", include_foreign_pagebreaks=True, base_line_keys=_keys(project))


def _flat(reading):
    return [(block, seg) for block in reading["blocks"] for seg in block["segments"]]


@pytest.fixture
def project(tmp_path):
    return copy_example(tmp_path / "exemple")


def test_a_project_without_lacunae_has_no_marker(project):
    assert not any(seg["kind"] == "lacuna" for _block, seg in _flat(_reading(project)))


def test_each_lacuna_tag_becomes_a_marker(project):
    add_example_lacunae(project)
    keys = _keys(project)
    flat = _flat(_reading(project))
    markers = [(i, seg) for i, (_block, seg) in enumerate(flat) if seg["kind"] == "lacuna"]
    assert [(seg["start"], seg["wit"]) for _i, seg in markers] == [
        (True, ["T2"]), (False, ["T2"]), (True, ["T1"]), (False, ["T1"])]

    def next_line(index):
        return next(seg["line_key"] for _block, seg in flat[index + 1:] if seg["kind"] == "text" and seg.get("line_key"))

    # Placés juste après le <lb/> de la ligne : avant le texte de cette ligne.
    assert next_line(markers[0][0]) == keys[T2_START]
    assert next_line(markers[1][0]) == keys[T2_END]
    assert next_line(markers[3][0]) == keys[PIVOT_GAP]
    assert all(block["type"] == "p" for block, seg in flat if seg["kind"] == "lacuna")


def test_the_witness_of_a_lacuna_in_a_reading_not_shown(project):
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    edition.write_text(insert_at(text, [
        (lbs[10][1], '<app><lem wit="#T1 #P"/><rdg wit="#T2"><lacunaStart/></rdg></app>'),
        (lbs[12][1], '<app><lem wit="#T1 #P"/><rdg wit="#T2"><lacunaEnd/></rdg></app>'),
    ]), encoding="utf-8")
    markers = [seg for _block, seg in _flat(_reading(project)) if seg["kind"] == "lacuna"]
    assert [(seg["start"], seg["wit"]) for seg in markers] == [(True, ["T2"]), (False, ["T2"])]


def test_a_lacuna_outside_a_paragraph_moves_to_the_next_one(project):
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start = text.index('<div xml:id="RLS_185">') + len('<div xml:id="RLS_185">')
    edition.write_text(insert_at(text, [(start, '<lacunaStart wit="#P"/>')]), encoding="utf-8")
    flat = _flat(_reading(project))
    block, marker = next((b, s) for b, s in flat if s["kind"] == "lacuna")
    assert block["type"] == "p" and marker["wit"] == ["P"]
    assert block["segments"][0] is marker


def test_the_positions_of_the_reading_document_count_every_segment_of_a_paragraph(project):
    add_example_lacunae(project)
    reading = _reading(project)
    positions = doc_positions(reading)
    paragraphs = [seg for block in reading["blocks"] if block["type"] == "p" for seg in block["segments"]]
    assert sorted(positions.values()) == list(range(len(paragraphs)))
    first = next(seg for seg in paragraphs if seg["kind"] == "lacuna")
    assert positions[id(first)] == paragraphs.index(first)
