# -*- coding: utf-8 -*-
"""Export web : parcours de chaque témoin dans son propre ordre, pages qui
mènent le texte (V0.9.1.6).

Les règles sont celles du bureau (``witness_route``, ``segment_model``) ; les
tests reprennent ceux de la fenêtre (test_gui_witness_route.py,
test_gui_witness_pages_route.py). Chaque arrêt du parcours exporté :
``{"s": texte, "k": clé de l'élément du panneau (ou folio d'un <pb>),
"t": ligne du pivot du texte à cet arrêt, "u": 1 si la ligne n'est pas
reliée, "p": position du <pb> dans le texte de lecture}``.

Projet exemple dont RLS_185 est synchronisé à part (après la 116e ligne de
l'édition ; T1 et T2 y ont un JSON, P non), avec les témoins par pages X
(<pb> de 12v et 13r dans rls185) et Y (<locus from="1v">)."""
from __future__ import annotations

import json
from itertools import groupby

import pytest

from corpus_data import add_text_pages, copy_example, make_corpus, move_to_part, split_alignments
from project_config import load_project
from web_viewer.generator import build_dataset
from web_viewer.segment_views import doc_positions


def _build(project, **options):
    data, _missing = build_dataset(load_project(project), **options)
    return data


def _witness(data, wid):
    return next(w for w in data["witnesses"] if w["id"] == wid)


def _runs(route):
    return [segment for segment, _stops in groupby(stop["s"] for stop in route)]


def _pivot_keys(data, k):
    t1 = _witness(data, "T1")
    pages = t1["pages"] if k == 0 else t1["views"][str(k)]["pages"]
    return [f"{page['id']}::{line['line']}" for page in pages for line in page["lines"]]


def _panel_keys(witness, k):
    view = witness if k == 0 else witness["views"][str(k)]
    return {f"{page['id']}::{line.get('alto_id') or line['line']}" for page in view["pages"] for line in page["lines"]}


def _make_text_apart(root):
    project = copy_example(root)
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    return project


@pytest.fixture
def text_apart(tmp_path):
    return _make_text_apart(tmp_path / "exemple")


def test_the_pivot_crosses_into_the_text_and_back(text_apart):
    data = _build(text_apart)
    route = _witness(data, "T1")["route"]
    # Le pivot des deux textes : toutes les lignes, dans l'ordre de lecture.
    assert [stop["t"] for stop in route] == data["meta"]["line_order"]
    assert all(stop["k"] == stop["t"] and "u" not in stop for stop in route)
    assert _runs(route) == [0, 1, 0]
    assert [stop["s"] for stop in route].index(1) == 116
    assert _witness(data, "T1")["route_uncertain"] == []


def test_a_secondary_witness_crosses_into_the_text_in_its_own_order(text_apart):
    data = _build(text_apart)
    t2 = _witness(data, "T2")
    route = t2["route"]
    assert _runs(route) == [0, 1, 0]
    for k in (0, 1):
        stops = [stop for stop in route if stop["s"] == k]
        assert {stop["k"] for stop in stops} <= _panel_keys(t2, k)
        assert {stop["t"] for stop in stops} <= set(_pivot_keys(data, k))
    assert all(stop["k"].startswith("~1~") and stop["t"].startswith("~1~") for stop in route if stop["s"] == 1)
    # Dans le texte, T2 entre par la ligne du pivot que désigne sa première ligne.
    first = next(stop for stop in route if stop["s"] == 1)
    assert _pivot_keys(data, 1).index(first["t"]) < 5


def test_a_witness_absent_from_a_text_has_no_stop_there(text_apart):
    route = _witness(_build(text_apart), "P")["route"]
    assert route and _runs(route) == [0]


def test_an_unlinked_line_leads_to_the_previous_linked_line(text_apart):
    path = text_apart.parent / "alignments" / "T2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = sorted((line for page in data["pages"] for line in page["lines"]), key=lambda line: int(line["order"]))
    lines[41]["base_keys"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    route = _witness(_build(text_apart), "T2")["route"]
    index = next(i for i, stop in enumerate(route) if stop.get("u"))
    assert route[index]["t"] == route[index - 1]["t"] and route[index]["s"] == 0
    assert sum(1 for stop in route if stop.get("u")) == 1


def test_an_uncertain_place_is_exported(text_apart):
    path = text_apart.parent / "alignments" / "rls185" / "T2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for index, page in enumerate(data["pages"]):
        page["id"] = f"autre-{index}"
        for field in ("iiif", "image", "image_name", "label"):
            page.pop(field, None)
    path.write_text(json.dumps(data), encoding="utf-8")
    t2 = _witness(_build(text_apart), "T2")
    assert t2["route_uncertain"] == [1]
    # Le texte garde sa place dans l'ordre de l'édition.
    assert _runs(t2["route"]) == [0, 1, 0]


def test_the_pb_of_a_page_witness_are_stops_at_their_place_in_the_text(text_apart):
    data = _build(text_apart)
    route = _witness(data, "X")["route"]
    assert [(stop["s"], stop["k"]) for stop in route] == [(1, "X-p0002"), (1, "X-p0003")]
    reading = data["document"]
    positions = doc_positions(reading)
    chips = {seg["label"]: positions[id(seg)] for block in reading["blocks"] for seg in block["segments"]
             if seg["kind"] == "pb" and seg.get("edref") == "#X"}
    assert [stop["p"] for stop in route] == [chips["12v"], chips["13r"]]
    # La ligne du pivot du texte à cet endroit : 12v après la 4e ligne, 13r après la 21e.
    keys = _pivot_keys(data, 1)
    assert [stop["t"] for stop in route] == [keys[3], keys[20]]


def test_the_pages_that_lead_the_text(text_apart):
    data = _build(text_apart)
    x, y = _witness(data, "X"), _witness(data, "Y")
    # 12v et 13r mènent à leur <pb> ; 12r et 13v n'en ont pas.
    assert x["lead"] == {"X-p0002": 0, "X-p0003": 1}
    assert x["views"]["1"].get("same_pages") and x["views"]["1"]["lead"] == x["lead"]
    # Y n'a pas de <pb> : son locus 1v mène au début de RLS_185.
    assert y["route"] == [] and "lead" not in y
    assert y["lead_locus"] == {"Y-p0002": 1}
    assert "lead_locus" not in x
    # Un témoin par lignes ne mène pas par ses pages.
    assert "lead" not in _witness(data, "T2")


def test_a_page_witness_with_a_json_of_its_lines_leads_by_its_first_line(text_apart):
    # P : sans lien vers le pivot, ses pages ; ses lignes n'y mènent pas, ses <pb> non plus.
    path = text_apart.parent / "alignments" / "P.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for page in data["pages"]:
        for line in page["lines"]:
            line["base_keys"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    p = _witness(_build(text_apart), "P")
    assert p["line_sync"] is False and p["route"] == [] and "lead" not in p


def test_the_routes_of_the_corpus(tmp_path):
    data = _build(make_corpus(tmp_path / "corpus"))
    assert _runs(_witness(data, "B")["route"]) == [1]           # B : seulement s02
    assert _runs(_witness(data, "D")["route"]) == [1]
    assert _runs(_witness(data, "A")["route"]) == [0, 2]        # A : l'édition, puis s04
    assert _runs(_witness(data, "C")["route"]) == [0, 2]
    stops = [stop for stop in _witness(data, "A")["route"] if stop["s"] == 2]
    assert [stop["k"] for stop in stops] == [f"~2~A-13r::{n}" for n in range(1, 9)]


def test_a_hidden_witness_has_no_route(tmp_path):
    data = _build(make_corpus(tmp_path / "corpus"), display_witness_ids=["A", "C", "D"])
    assert "route" not in _witness(data, "B") and "route" in _witness(data, "D")


def test_the_lacuna_markers_count_in_the_positions_of_the_pb(tmp_path):
    from corpus_data import add_example_lacunae
    # X (1r, 1v) : son <pb> de 1r au début de l'édition, celui de 1v dans le passage absent de T1.
    project = copy_example(tmp_path / "lacunes")
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_example_lacunae(project)
    data = _build(project)
    assert [stop["t"] for stop in _witness(data, "T1")["route"]] == data["meta"]["line_order"]
    positions = doc_positions(data["document"])
    segments = [seg for block in data["document"]["blocks"] for seg in block["segments"]]
    assert sum(1 for seg in segments if seg["kind"] == "lacuna") == 4
    chips = [positions[id(seg)] for seg in segments if seg["kind"] == "pb" and seg.get("edref") == "#X"]
    route = _witness(data, "X")["route"]
    assert [(stop["s"], stop["p"]) for stop in route] == [(0, chip) for chip in chips] and len(chips) == 2
