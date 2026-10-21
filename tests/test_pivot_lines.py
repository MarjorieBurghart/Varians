# -*- coding: utf-8 -*-
"""Lignes du pivot dans une édition assemblée par XInclude (pivot_lines),
sans Qt : numérotation continue à travers les parties (V0.9.1.0) et pages des
témoins aux jonctions.

Jeu « sermons » (tests/data/sermons), pivot A : s01 a 10 lignes, s02 aucune
(son pivot est B), s03 9, s04 5 et son exemplum, inclus dans s04, 3 ; soit 27.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from document_session import LbIndex
from folio_navigation import Folio, folio_at_position, last_folio_mark
from pivot_lines import include_spans, pivot_lb_pattern, pivot_lines
from xml_assembly import assemble

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
SERMONS = DATA / "sermons"
S01, S02, S03, S04, EXEMPLUM = (SERMONS / f"{name}.xml" for name in ("s01", "s02", "s03", "s04", "s04_exemplum"))
PATTERN = pivot_lb_pattern("A")
TEI = "http://www.tei-c.org/ns/1.0"

# s04 avec du texte et une ligne après l'exemplum qu'il inclut.
S04_AFTER = S04.read_text(encoding="utf-8").replace(
    '<xi:include href="s04_exemplum.xml"/>\n',
    '<xi:include href="s04_exemplum.xml"/>\n  <p>Post exemplum\n    <lb edRef="#A"/>finis.</p>\n')


def _read(path):
    return path.read_text(encoding="utf-8")


def _lines(**texts):
    """``pivot_lines`` sur le jeu sermons ; ``texts`` : textes modifiés."""
    changed = {SERMONS / f"{name}.xml": text for name, text in texts.items()}
    return pivot_lines(_read(EDITION), EDITION, changed, "A")


def _text(path, **texts):
    return texts.get(path.stem, _read(path))


def _at(lines, path, needle, *, after=False, **texts):
    """Numéro de la ligne du pivot à ``needle`` (ou juste après) dans ``path``."""
    text = _text(path, **texts)
    position = text.index(needle) + (len(needle) if after else 0)
    return lines.ordinal_at(path, position, LbIndex.scan(text, PATTERN), include_spans(text))


# --- Numérotation --------------------------------------------------------------

def test_the_lines_are_numbered_in_the_assembled_order():
    lines = _lines()
    assert lines.count == 27
    assert lines.file(S01).ordinals == tuple(range(0, 10))
    assert lines.file(S02).ordinals == ()                  # pivot B
    assert lines.file(S03).ordinals == tuple(range(10, 19))
    assert lines.file(S04).ordinals == tuple(range(19, 24))
    assert lines.file(EXEMPLUM).ordinals == (24, 25, 26)
    assert lines.file(EDITION).ordinals == ()


def test_the_count_is_the_one_of_lxml_xinclude():
    tree = etree.parse(str(EDITION))
    tree.xinclude()
    assert len(tree.getroot().xpath("//tei:lb[@edRef='#A']", namespaces={"tei": TEI})) == _lines().count


def test_text_before_the_first_line_of_a_part_belongs_to_the_previous_line():
    lines = _lines()
    assert _at(lines, S01, "<head>") == 0                   # rien avant : première ligne
    assert _at(lines, S03, '<div xml:id="s03"') == 9        # dernière ligne de s01 (s02 n'en a pas)
    assert _at(lines, S04, "<head>") == 18


def test_a_position_in_a_part_has_the_number_of_its_line():
    lines = _lines()
    assert _at(lines, S01, "nostri. Triplex") == 2
    assert _at(lines, S03, "Tria sunt") == 13
    assert _at(lines, EXEMPLUM, "Narrat") == 24


def test_a_position_after_an_inclusion_takes_the_end_of_its_content():
    lines = _lines()
    assert _at(lines, EDITION, '<xi:include href="sermons/s03.xml"') == 9      # pas encore incluse
    assert _at(lines, EDITION, '<!-- Fragment qui inclut') == 18               # après s03
    assert _at(lines, EDITION, "</body>") == 26
    lines = _lines(s04=S04_AFTER)
    assert lines.count == 28
    assert _at(lines, S04, "Post exemplum", s04=S04_AFTER) == 26               # fin de l'exemplum
    assert _at(lines, S04, "finis", s04=S04_AFTER) == 27


def test_a_line_outside_the_included_element_or_in_a_comment_has_no_number():
    s03 = _read(S03).replace("      </div>\n", '      </div>\n      <div><p><lb edRef="#A"/>alia</p></div>\n', 1)
    s01 = _read(S01).replace("  <head>", '  <!-- <lb edRef="#A"/> -->\n  <head>', 1)
    lines = _lines(s01=s01, s03=s03)
    assert lines.count == 27
    assert lines.file(S01).ordinals == (None,) + tuple(range(0, 10))
    assert lines.file(S03).ordinals == tuple(range(10, 19)) + (None,)


def test_location_is_the_reverse_of_ordinal_at():
    lines = _lines()
    for ordinal in range(lines.count):
        path, index = lines.location(ordinal)
        text = _read(path)
        spans = LbIndex.scan(text, PATTERN)
        assert lines.ordinal_at(path, spans[index][0], spans, include_spans(text)) == ordinal
    assert lines.location(27) is None and lines.location(-1) is None


def test_a_malformed_part_brings_no_line():
    lines = _lines(s03="<div>")
    assert lines.count == 18
    assert lines.file(S04).ordinals == tuple(range(10, 15))
    assert [p.code for p in lines.problems] == ["malformed"]
    assert pivot_lines("<TEI>", EDITION, {}, "A") is None


def test_an_unknown_file_has_no_line():
    assert _lines().ordinal_at(DATA / "personnes.xml", 0, [], []) is None


def test_matches_compares_the_counts_of_a_file():
    lines = _lines()
    assert lines.matches(S01, 10, 0) and lines.matches(S04, 5, 1)
    assert not lines.matches(S01, 11, 0) and not lines.matches(S04, 5, 0)
    assert not lines.matches(DATA / "personnes.xml", 0, 0)


def test_include_spans_cover_the_whole_element():
    text = ('<r xmlns:x="http://www.w3.org/2001/XInclude">\n<x:include href="a.xml"/>\n'
            '<x:include href="b.xml"><x:fallback><x:include href="c.xml"/></x:fallback></x:include>\n</r>')
    spans = include_spans(text)
    assert [text[start:end] for start, end in spans] == [
        '<x:include href="a.xml"/>',
        '<x:include href="b.xml"><x:fallback><x:include href="c.xml"/></x:fallback></x:include>']


def test_the_assembly_tells_the_line_of_the_inclusion_of_each_copy():
    assembly = assemble(_read(EDITION), EDITION)
    sites = {assembly.origin(element).name: assembly.site(element)
             for element in assembly.root.iter() if assembly.site(element) is not None}
    assert sites == {"s01.xml": 34, "s02.xml": 36, "s03.xml": 38, "s04.xml": 40, "s04_exemplum.xml": 17}
    assert assembly.site(assembly.root) is None


# --- Pages ---------------------------------------------------------------------

FOLIOS_A = [Folio(f"A{n}", f"A{n}", n) for n in ("12v", "13r", "13v", "14r", "14v", "15r", "15v")]


def _page(lines, path, needle, witness="A", folios=FOLIOS_A, **texts):
    text = _text(path, **texts)
    folio = lines.page_at(path, text.index(needle), text, include_spans(text), witness, folios)
    return folio.label if folio else None


def test_the_page_follows_the_pb_of_the_part():
    lines = _lines()
    assert _page(lines, S01, "<head>") is None
    assert _page(lines, S01, "virgine") == "12v"
    assert _page(lines, S03, "Tria sunt") == "14v"


def test_the_page_at_the_start_of_a_part_is_the_last_one_before_it():
    lines = _lines()
    assert _page(lines, S03, "<head>") == "13r"            # fin de s01 dans A
    assert _page(lines, S04, "<head>") == "15v"            # fin de s03
    assert _page(lines, EXEMPLUM, "Narrat") == "13v"       # page de s04 avant l'exemplum


def test_the_page_after_an_inclusion_is_the_last_one_of_its_content():
    lines = _lines(s04=S04_AFTER)
    assert _page(lines, S04, "Post exemplum", s04=S04_AFTER) == "14r"


def test_the_page_of_another_witness_follows_the_edition_order():
    folios = [Folio(f"B{n}", f"B{n}", n) for n in ("30r", "30v", "31r", "31v", "32r")]
    lines = _lines()
    # Dans B, le sermon 2 précède le sermon 1 ; l'édition suit l'ordre inverse.
    assert _page(lines, S02, "<head>", witness="B", folios=folios) == "32r"


def test_last_folio_mark_gives_the_end_of_the_pb():
    text = _read(S01)
    position = text.index("virgine")
    folio, end = last_folio_mark(text, position, "A", FOLIOS_A)
    assert folio is folio_at_position(text, position, "A", FOLIOS_A)
    assert text[:end].endswith('<pb edRef="#A" n="12v"/>')
    assert last_folio_mark(text, 0, "A", FOLIOS_A) is None
