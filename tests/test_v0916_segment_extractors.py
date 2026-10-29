# -*- coding: utf-8 -*-
"""Extracteurs de l'export web selon le texte (V0.9.1.6), sans Qt.

Dans une édition assemblée, un texte synchronisé à part a son propre pivot :
ses lignes sont celles de ce pivot, ses leçons celles de ce pivot, ses
sauts de page ceux de ce pivot (les autres sont des repères invisibles).

Jeu « corpus » : s02 a pour pivot B (8 lignes, alignments/s02/B.json, clés
préfixées ~1~) ; s04 a pour pivot A (8 lignes, ~2~) ; s01 et s03 suivent la
numérotation de l'édition (A, 19 lignes). Dans s02, l'<app> de « dixit »
est réécrit pour que la leçon de B soit un <rdg> : <lem wit="#D">cecinit
</lem><rdg wit="#B">dixit</rdg>."""
from __future__ import annotations

import pytest

from corpus_data import make_corpus
from project_config import load_project
from web_viewer.assembled_document import load_assembled
from web_viewer.legacy_v11_core import extract_corrected_pages, extract_reading_document
from web_viewer.tei_line_anchors import build_segment_lb_index

KEYS = {0: [f"A-12r::{n}" for n in range(1, 20)],
        1: [f"~1~B-30r::{n}" for n in range(1, 9)],
        2: [f"~2~A-13r::{n}" for n in range(1, 9)]}


@pytest.fixture
def corpus(tmp_path):
    project = make_corpus(tmp_path / "corpus")
    s02 = project.parent / "xml" / "sermons" / "s02.xml"
    text = s02.read_text(encoding="utf-8")
    old = '<app><lem wit="#B">dixit</lem><rdg wit="#D">cecinit</rdg></app>'
    assert old in text
    s02.write_text(text.replace(old, '<app><lem wit="#D">cecinit</lem><rdg wit="#B">dixit</rdg></app>'),
                   encoding="utf-8")
    document = load_assembled(load_project(project))
    lookup, _reports, _order = build_segment_lb_index(
        document.root, document.segment, {s.index: s.pivot for s in document.segments}, KEYS)
    return document, lookup


def _options(document, lookup):
    return dict(root=document.root, line_anchors=lookup, segment_of=document.segment,
                target_of=document.target)


def _segments(reading):
    return [seg for block in reading["blocks"] for seg in block["segments"]]


def test_the_reading_document_follows_the_pivot_of_each_text(corpus):
    document, lookup = corpus
    reading = extract_reading_document(None, "#A", include_foreign_pagebreaks=True, **_options(document, lookup))
    segments = _segments(reading)
    texts = [s for s in segments if s["kind"] == "text"]
    # s02 : les lignes de B, préfixées ; le texte porte son texte (seg 1).
    s02 = [s for s in texts if s.get("seg") == 1]
    assert s02 and {s["line_key"] for s in s02 if s["line_key"]} == set(KEYS[1])
    assert {s["line_key"] for s in texts if s.get("seg") == 2 and s["line_key"]} == set(KEYS[2])
    assert {s["line_key"] for s in texts if "seg" not in s and s["line_key"]} == set(KEYS[0])
    # La leçon de B, pivot de s02.
    words = "".join(s["text"] for s in s02)
    assert "dixit" in words and "cecinit" not in words
    # Avant sa première ligne, le texte de s02 n'est pas rattaché à une ligne de l'édition.
    first = next(i for i, s in enumerate(texts) if s.get("seg") == 1)
    assert texts[first]["line_key"] is None or texts[first]["line_key"].startswith("~1~")
    # Après s02, l'édition reprend avec ses propres lignes.
    after = next(s for s in texts[first:] if "seg" not in s)
    assert after["line_key"] is None or after["line_key"] in KEYS[0]


def test_the_established_text_takes_the_lem_and_the_pivot_of_each_text_otherwise(corpus):
    # Choix du texte (V0.9.3.0) : le <lem> de D dans s02 ; « pivot » est
    # celui de chaque texte (B pour s02). Les lignes de B gardent leurs clés.
    document, lookup = corpus
    for choice, shown, hidden in ((dict(text_mode="established"), "cecinit", "dixit"),
                                  (dict(text_mode="witness"), "dixit", "cecinit")):
        reading = extract_reading_document(None, "#A", include_foreign_pagebreaks=True, **choice,
                                           **_options(document, lookup))
        s02 = [s for s in _segments(reading) if s["kind"] == "text" and s.get("seg") == 1]
        words = "".join(s["text"] for s in s02)
        assert shown in words and hidden not in words, choice
        assert {s["line_key"] for s in s02 if s["line_key"]} == set(KEYS[1])
        assert reading["missing_readings"] == 0


def test_the_page_breaks_of_the_pivot_of_a_text_are_visible(corpus):
    document, lookup = corpus
    reading = extract_reading_document(None, "#A", include_foreign_pagebreaks=True, **_options(document, lookup))
    pbs = [s for s in _segments(reading) if s["kind"] == "pb" and s.get("seg") == 1]
    assert {(s["edref"], s["foreign"]) for s in pbs} == {("#B", False), ("#D", True)}


def test_the_lines_of_a_text_carry_the_reading_of_its_pivot(corpus):
    document, lookup = corpus
    pages, _labels = extract_corrected_pages(None, "#A", **_options(document, lookup))
    lines = {line["line_key"]: line for found in pages.values() for line in found}
    assert set(KEYS[1]) <= set(lines) and set(KEYS[0]) <= set(lines)
    assert "dixit" in lines["~1~B-30r::2"]["text"] and "cecinit" not in lines["~1~B-30r::2"]["text"]
    variant = next(a for a in lines["~1~B-30r::2"]["annotations"] if a["kind"] == "variant")
    assert variant["target"] == "B"


def test_without_options_a_single_file_is_read_as_before(tmp_path):
    from corpus_data import copy_example
    edition = copy_example(tmp_path / "exemple").parent / "xml" / "edition.xml"
    old = extract_reading_document(edition, "#T1", include_foreign_pagebreaks=True)
    assert all("seg" not in s for s in _segments(old))
