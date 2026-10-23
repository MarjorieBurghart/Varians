# -*- coding: utf-8 -*-
"""Règles des textes synchronisés à part et du parcours des témoins
(V0.9.1.6), sans Qt : communes à la fenêtre et à l'export web.

Projet exemple dont RLS_185 (xml/rls185.xml) est synchronisé à part (T1 et T2
y ont un JSON ; P non), avec deux témoins par pages :
- X (12r, 12v, 13r, 13v), qui a ses <pb> dans rls185 : 12v après la ligne 4
  du pivot, 13r après la ligne 21 ;
- Y (1r, 1v), sans <pb>, dont le <locus from="1v" target="#RLS_185"> est
  dans le <listWit> de l'édition."""
from __future__ import annotations

import pytest

import segment_model as sm
from corpus_data import add_text_pages, copy_example, make_corpus, move_to_part, split_alignments
from folio_navigation import Folio, witness_loci
from pivot_lines import pivot_lines
from witness_route import Stop, WitnessRoute
from xml_assembly import path_key


def _folios(witness, labels):
    return [Folio(f"{witness}-p{i:04d}", f"{witness}-p{i:04d}", label) for i, label in enumerate(labels, 1)]


X_FOLIOS = _folios("X", ("12r", "12v", "13r", "13v"))
Y_FOLIOS = _folios("Y", ("1r", "1v"))


@pytest.fixture
def text_apart(tmp_path):
    project = copy_example(tmp_path / "exemple")
    part = move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    edition = project.parent / "xml" / "edition.xml"
    edition_text = edition.read_text(encoding="utf-8")
    part_text = part.read_text(encoding="utf-8")
    lines = pivot_lines(edition_text, edition, {}, "T1", text_bases={part: "T1"})
    segment = path_key(part)
    ids = sm.segment_ids([part_text])
    loci = sm.segment_loci(witness_loci(edition_text), part_text)
    return lines, segment, ids, loci


def test_the_ids_of_a_text_include_its_nested_parts(tmp_path):
    root = make_corpus(tmp_path / "corpus").parent / "xml" / "sermons"
    ids = sm.segment_ids([(root / "s04.xml").read_text(encoding="utf-8"),
                          (root / "s04_exemplum.xml").read_text(encoding="utf-8")])
    assert {"s04", "s04_p1", "s04_exemplum"} <= ids


def test_the_loci_of_a_text(text_apart):
    _lines, _segment, ids, loci = text_apart
    assert "RLS_185" in ids
    assert [locus.start for locus in loci["Y"]] == ["1v"]
    assert sm.locus_start(loci, "Y", ids) == "1v"
    assert sm.locus_start(loci, "X", ids) is None
    assert sm.locus_start(loci, "Y", {"autre"}) is None


def test_the_page_witnesses_of_a_text(text_apart):
    lines, segment, ids, loci = text_apart
    # Tout témoin qui a un <pb> dans le texte, ou un locus vers lui ; ceux qui
    # y ont un JSON (ici T1) sont écartés ensuite (text_project).
    declared = {"T1", "T2", "P", "X", "Y"}
    assert sm.text_page_witnesses(lines, segment, ids, loci, declared) == {"T1", "X", "Y"}
    assert sm.text_page_witnesses(lines, segment, ids, loci, {"P", "X"}) == {"X"}


def test_the_start_page_of_a_page_witness(text_apart):
    lines, segment, ids, loci = text_apart
    # X : la page qui précède son premier <pb> dans le texte ; Y : son locus.
    assert sm.start_folio(lines, segment, "X", X_FOLIOS, loci, ids).label == "12r"
    assert sm.start_folio(lines, segment, "Y", Y_FOLIOS, loci, ids).label == "1v"
    assert sm.start_folio(lines, segment, "P", [], loci, ids) is None


def test_declared_page_ranks():
    caches = [{"pages": [{"id": "a", "tei_surface_id": "X-p0003"}, {"id": "b", "tei_surface_id": "libre"}]},
              {"pages": [{"id": "c", "tei_surface_id": "X-p0001"}]}]
    ranks = sm.declared_page_ranks(caches, X_FOLIOS)
    assert ranks["id:a"] == 3 and ranks["id:c"] == 1 and "id:b" not in ranks
    assert ranks["folio:X-p0003"] == 3 and ranks["folio:X-p0001"] == 1 and "folio:X-p0002" not in ranks


def _route(*stops, uncertain=()):
    return WitnessRoute("X", tuple(stops), (), tuple(uncertain))


def test_the_stop_of_a_page():
    line = Stop(None, "k1", "id:p1", 4)
    mark = Stop("s1", "X-p0002", "folio:X-p0002", 3, location=("rls185.xml", 120))
    route = _route(line, mark)
    assert sm.page_stop(route, "id:p1", X_FOLIOS[0], X_FOLIOS) is line
    # Page sans ligne du témoin : son folio, ou un <pb> de la même image.
    assert sm.page_stop(route, None, X_FOLIOS[1], X_FOLIOS) is mark
    zone = Folio("X-p0002-a", "X-p0002", "12v a", (0, 0, .5, 1))
    assert sm.page_stop(route, None, zone, X_FOLIOS + [zone]) is mark
    assert sm.page_stop(route, None, X_FOLIOS[3], X_FOLIOS) is None


def test_the_text_of_a_locus():
    tei = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><listWit><witness xml:id="Y">'
           '<locus from="1V" target="#T"/></witness></listWit></TEI>')
    texts = [("s1", witness_loci(tei), {"T"})]
    assert sm.locus_segment("Y", Y_FOLIOS[1], texts) == "s1"
    assert sm.locus_segment("Y", Y_FOLIOS[0], texts) is None
    assert sm.locus_segment("X", Y_FOLIOS[1], texts) is None


def test_the_present_stop_before_and_after():
    early, late = Stop(None, "a", "p", 10), Stop(None, "b", "p", 200)
    first, last = Stop("s1", "c", "p", 0), Stop("s1", "d", "p", 30)
    route = _route(early, first, last, late)
    anchors = {"s1": 116}
    # Dans l'édition, ligne 100 : le texte suivant est s1 (placé après la
    # ligne 116), où le témoin reprend à son premier arrêt.
    assert sm.present_stop(route, anchors.get, ["s1"], None, 100, 1) is first
    assert sm.present_stop(route, anchors.get, ["s1"], None, 100, -1) is early
    # Dans s1 : après lui, la ligne 200 de l'édition ; avant lui, la ligne 10.
    assert sm.present_stop(route, anchors.get, ["s1"], "s1", None, 1) is late
    assert sm.present_stop(route, anchors.get, ["s1"], None, 300, 1) is None
    # En reculant vers un texte, le témoin y reprend à son dernier arrêt.
    assert sm.present_stop(route, anchors.get, ["s1"], None, 250, -1) is late
    assert sm.present_stop(route, anchors.get, ["s1"], None, 150, -1) is last
