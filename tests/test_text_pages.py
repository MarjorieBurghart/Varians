# -*- coding: utf-8 -*-
"""Témoins par pages dans un texte synchronisé à part (V0.9.1.3), sans Qt.

Un témoin sans JSON pour un texte synchronisé à part, mais qui a ce texte (un
``<pb edRef>`` dans le texte, ou un ``<locus target>`` dans son ``<witness>``),
y suit ses pages. Sa page de départ, avant son premier ``<pb>`` dans le
texte : le ``@from`` de son ``<locus>``, sinon la page qui précède celle de ce
premier ``<pb>``, dans l'ordre des pages du témoin.

Jeu « sermons » (tests/data/sermons) : dans le <listWit> de l'édition, A et C
ont un <locus from to target="#s04">. Jeu « corpus » (tests/corpus_data.py) :
s02 et s04 sont synchronisés à part.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from corpus_data import add_page_witness, make_corpus
from folio_navigation import Folio, Locus, page_folios, text_start_folio, witness_loci
from pivot_lines import pivot_lines
from project_config import load_project
from text_alignments import text_project, text_syncs
from witness_resource_refresh import assemble_resources
from xml_assembly import assemble, path_key

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
S02 = DATA / "sermons" / "s02.xml"

FOLIOS_A = [Folio(f"A{n}", f"A{n}", n) for n in ("12v", "13r", "13v", "14r", "14v")]
FOLIOS_D = [Folio(f"D{n}", f"D{n}", n) for n in ("100v", "101r", "101v", "102r", "102v")]


def _read(path):
    return path.read_text(encoding="utf-8")


# --- <locus> des témoins -----------------------------------------------------------

def test_the_loci_of_the_witnesses_are_read_in_the_list_wit():
    loci = witness_loci(_read(EDITION))
    assert loci["A"] == (Locus("A", "13r", "14r", frozenset({"s04"})),)
    assert loci["C"] == (Locus("C", "3r", "3v", frozenset({"s04"})),)
    assert "B" not in loci and "D" not in loci
    assert witness_loci("<TEI><mal formé") == {}


def test_page_folios_are_the_zones_or_the_whole_surfaces():
    folios = [Folio("S1", "S1", "1r"), Folio("S2", "S2", "2"),
              Folio("Z2a", "S2", "2r", (0, 0, .5, 1)), Folio("Z2b", "S2", "2v", (.5, 0, .5, 1))]
    assert [folio.ref for folio in page_folios(folios)] == ["S1", "Z2a", "Z2b"]


# --- Première page d'un témoin dans un texte, page de départ ------------------------

def test_the_first_page_of_a_witness_in_a_text_synchronized_apart():
    lines = pivot_lines(_read(EDITION), EDITION, {}, "A", text_bases={S02: "B"})
    assert lines.first_page(path_key(S02), "D", FOLIOS_D).label == "101r"
    assert lines.first_page(path_key(S02), "A", FOLIOS_A) is None      # A n'a pas s02


def test_the_start_page_is_the_page_before_the_first_pb():
    first = FOLIOS_D[1]                                                # 101r
    assert text_start_folio("D", FOLIOS_D, first=first).label == "100v"
    assert text_start_folio("D", FOLIOS_D, first=FOLIOS_D[0]).label == "100v"   # déjà la première
    assert text_start_folio("D", FOLIOS_D) is None


def test_the_start_page_is_first_the_from_of_a_locus_of_the_text():
    loci = witness_loci(_read(EDITION))["A"]
    start = text_start_folio("A", FOLIOS_A, loci, text_ids={"s04", "s04_p1"}, first=FOLIOS_A[2])
    assert start.label == "13r"                                        # @from, et non 13r « avant 13v »
    # Un locus d'un autre texte ne compte pas ; un @from inconnu non plus.
    assert text_start_folio("A", FOLIOS_A, loci, text_ids={"s03"}, first=FOLIOS_A[4]).label == "14r"
    unknown = (Locus("A", "99r", None, frozenset({"s04"})),)
    assert text_start_folio("A", FOLIOS_A, unknown, text_ids={"s04"}, first=FOLIOS_A[2]).label == "13r"


def test_the_start_page_uses_the_page_folios_of_a_divided_surface():
    folios = [Folio("S1", "S1", "1"), Folio("Z1r", "S1", "1r", (0, 0, .5, 1)),
              Folio("Z1v", "S1", "1v", (.5, 0, .5, 1)), Folio("S2", "S2", "2r")]
    assert text_start_folio("W", folios, first=folios[3]).ref == "Z1v"


# --- Projet réduit à un texte, avec ses témoins par pages ----------------------------

@pytest.fixture
def corpus(tmp_path):
    project_xml = make_corpus(tmp_path / "corpus")
    add_page_witness(project_xml, "X", ("1r", "1v"))
    return project_xml


def _s02(project):
    edition = project.edition
    parts = list(assemble(edition.read_text(encoding="utf-8"), edition).parts)
    return next(sync for sync in text_syncs(project, parts)[0] if sync.name == "s02")


def test_the_project_of_a_text_keeps_its_page_witnesses(corpus):
    project = load_project(corpus)
    s02 = _s02(project)
    reduced = text_project(project, s02, page_witnesses={"X", "B"})     # B a un JSON : par lignes
    assert [w.id for w in reduced.witnesses] == ["B", "D", "X"]
    assert reduced.witness_by_id["X"].alignment is None
    assert reduced.witness_by_id["X"].role == "secondary"
    assert reduced.page_witnesses == frozenset({"X"})
    state = assemble_resources(reduced)
    assert [item["l"].get("_page_mode") for item in state.display_items["X"]] == [True, True]
    assert state.base_active and state.secondary_links["D"] == 8
    assert text_project(project, s02).page_witnesses == frozenset()
