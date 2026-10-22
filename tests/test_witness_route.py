# -*- coding: utf-8 -*-
"""Parcours d'un témoin dans son propre ordre (V0.9.1.4), sans Qt.

Un témoin a des lignes dans le JSON global (édition en numérotation
continue, segment None) et dans les JSON des textes synchronisés à part. Son
parcours range toutes ces lignes dans l'ordre du manuscrit : l'ordre de ses
pages (images déclarées, sinon fusion des listes de pages de ses JSON, sinon
<locus from> ou foliotation, sinon ordre de l'édition), puis l'ordre des
lignes sur la page.
"""
from __future__ import annotations

from witness_route import PageMark, Source, folio_number, page_identity, witness_route


def page(pid, lines, *, label=None, canvas=None):
    """Page d'un JSON : ``lines`` est une suite de (numéro, base_keys) ; une
    ligne du pivot a base_keys None."""
    data = {"id": pid, "lines": []}
    for number, keys in lines:
        line = {"line": number}
        if keys is not None:
            line.update(order=number, base_keys=list(keys))
        data["lines"].append(line)
    if label or canvas:
        data["iiif"] = {k: v for k, v in (("id", canvas), ("label", label)) if v}
    return data


def cache(*pages):
    return {"meta": {}, "pages": list(pages)}


def pivot_keys(page_id, count, start=0):
    """Table clé → rang des ``count`` lignes d'une page du pivot."""
    return {f"{page_id}::{n}": start + n - 1 for n in range(1, count + 1)}


def keys(route):
    return [(stop.segment, stop.key) for stop in route.stops]


# --- Identité et foliotation ------------------------------------------------------

def test_the_identity_of_a_page_is_its_canvas_then_its_image_then_its_id():
    assert page_identity({"id": "f1", "image_name": "f1.jpg", "iiif": {"id": "https://x/c1"}}) == "canvas:https://x/c1"
    assert page_identity({"id": "f1", "image_name": "f1.jpg"}) == "image:f1.jpg"
    assert page_identity({"id": "f1"}) == "id:f1"


def test_a_folio_number_needs_a_recto_or_verso():
    assert folio_number("f. 12v") == (12, 1)
    assert folio_number("240r") == (240, 0)
    assert folio_number("f. 266v - 267") == (266, 1)
    assert folio_number("vue 217") is None and folio_number("") is None


# --- Un seul JSON ---------------------------------------------------------------------

def test_the_pivot_of_a_single_json_keeps_the_order_of_its_lines():
    route = witness_route("A", [Source(None, cache(page("A-1", [(1, None), (2, None)]),
                                                     page("A-2", [(1, None)])), is_base=True)])
    assert keys(route) == [(None, "A-1::1"), (None, "A-1::2"), (None, "A-2::1")]
    assert [stop.ordinal for stop in route.stops] == [0, 1, 2]
    assert route.texts == (None,) and route.uncertain == ()


def test_a_secondary_line_leads_to_the_pivot_line_it_designates():
    base = pivot_keys("A-1", 4)
    route = witness_route("C", [Source(None, cache(page("C-1", [(1, ["A-1::1"]), (2, ["A-1::3", "A-1::2"]),
                                                               (3, []), (4, ["A-1::4"])])), base_by_key=base)])
    # Une ligne reliée à plusieurs lignes du pivot mène à la première ; une
    # ligne non reliée, à la ligne reliée qui la précède.
    assert [stop.ordinal for stop in route.stops] == [0, 1, 1, 3]
    assert [stop.linked for stop in route.stops] == [True, True, False, True]


# --- Plusieurs textes ----------------------------------------------------------------

def _corpus(locus=None, shared=True):
    """C a s01 et s03 dans le JSON global (pages C-2, C-3), et s02 à part :
    dans le manuscrit, s02 vient AVANT s01 (pages C-1 et le haut de C-2)."""
    edition = Source(None, cache(page("C-2", [(5, ["A-1::1"]), (6, ["A-1::2"])]),
                                 page("C-3", [(1, ["A-1::3"])])),
                     base_by_key=pivot_keys("A-1", 3))
    s02_pages = [page("C-1", [(1, ["B-1::1"]), (2, ["B-1::2"])], label="1r")]
    if shared:
        s02_pages.append(page("C-2", [(1, ["B-1::3"])]))
    s02 = Source("s02", cache(*s02_pages), base_by_key=pivot_keys("B-1", 3), anchor=2, locus=locus)
    return edition, s02


def test_the_texts_follow_the_order_of_the_manuscript():
    route = witness_route("C", list(_corpus()))
    assert keys(route) == [("s02", "C-1::1"), ("s02", "C-1::2"), ("s02", "C-2::1"),
                           (None, "C-2::5"), (None, "C-2::6"), (None, "C-3::1")]
    assert route.texts == ("s02", None) and route.uncertain == ()


def test_a_page_shared_by_two_texts_keeps_the_order_of_its_lines():
    route = witness_route("C", list(_corpus()))
    on_c2 = [stop for stop in route.stops if stop.page == "id:C-2"]
    assert [(stop.segment, stop.key) for stop in on_c2] == [("s02", "C-2::1"), (None, "C-2::5"), (None, "C-2::6")]
    assert route.on_page("id:C-2") is on_c2[0]


def test_declared_images_give_the_order_of_the_pages():
    edition, s02 = _corpus(shared=False)
    declared = {"id:C-1": 9, "id:C-2": 1, "id:C-3": 2}            # s02 est à la fin du manuscrit
    route = witness_route("C", [edition, s02], declared=declared)
    assert route.texts == (None, "s02") and route.uncertain == ()


def test_a_text_without_a_shared_page_is_placed_by_its_locus_or_its_foliation():
    edition = Source(None, cache(page("C-2", [(1, ["A-1::1"])], label="2r"),
                                 page("C-4", [(1, ["A-1::2"])], label="4r")),
                     base_by_key=pivot_keys("A-1", 2))
    s02 = Source("s02", cache(page("X-1", [(1, ["B-1::1"])])), base_by_key=pivot_keys("B-1", 1),
                 anchor=0, locus="3r")
    route = witness_route("C", [edition, s02])
    assert keys(route) == [(None, "C-2::1"), ("s02", "X-1::1"), (None, "C-4::1")]
    # Sans <locus>, la foliotation de sa première page.
    s02 = Source("s02", cache(page("X-1", [(1, ["B-1::1"])], label="f. 5r")), base_by_key=pivot_keys("B-1", 1))
    assert witness_route("C", [edition, s02]).texts == (None, "s02")


def test_a_text_that_cannot_be_placed_keeps_the_order_of_the_edition():
    edition = Source(None, cache(page("C-2", [(1, ["A-1::1"]), (2, ["A-1::2"])]),
                                 page("C-3", [(1, ["A-1::3"])])),
                     base_by_key=pivot_keys("A-1", 3))
    # s02 vient après la ligne 2 du pivot de l'édition (anchor 2).
    s02 = Source("s02", cache(page("X-1", [(1, ["B-1::1"])])), base_by_key=pivot_keys("B-1", 1), anchor=2)
    route = witness_route("C", [edition, s02])
    assert keys(route) == [(None, "C-2::1"), (None, "C-2::2"), ("s02", "X-1::1"), (None, "C-3::1")]
    assert route.uncertain == ("s02",)


# --- Pas à pas ----------------------------------------------------------------------

def test_stepping_crosses_from_one_text_to_the_next_and_stops_at_the_ends():
    route = witness_route("C", list(_corpus()))
    assert route.step("s02", "C-2::1", 1).key == "C-2::5"
    assert route.step(None, "C-2::5", -1).segment == "s02"
    assert route.step("s02", "C-1::1", -1) is None
    assert route.step(None, "C-3::1", 1) is None
    assert route.step(None, "inconnue", 1) is None
    assert route.first("s02").key == "C-1::1" and route.last(None).key == "C-3::1"
    assert route.first("s09") is None


# --- Témoin par pages dans un texte -------------------------------------------------

def test_the_pb_of_a_page_witness_are_stops_of_its_route():
    edition = Source(None, cache(page("M-1", [(1, ["A-1::1"])], label="45r"),
                                 page("M-3", [(1, ["A-1::2"])], label="46r")),
                     base_by_key=pivot_keys("A-1", 2))
    marks = (PageMark("M-p0002", "45v", ("rls186.xml", 120), 3),)
    s186 = Source("rls186", marks=marks, anchor=1)
    route = witness_route("M", [edition, s186])
    assert keys(route) == [(None, "M-1::1"), ("rls186", "M-p0002"), (None, "M-3::1")]
    stop = route.stops[1]
    assert stop.location == ("rls186.xml", 120) and stop.ordinal == 3 and stop.linked
