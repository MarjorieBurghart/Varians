# -*- coding: utf-8 -*-
"""Export web : textes synchronisés à part (V0.9.1.6).

Un texte synchronisé à part a ses JSON (alignments/<texte>/) et son pivot.
Dans l'export, il forme un texte (1, 2…) dont les clés sont préfixées
(~1~…), car ses JSON peuvent reprendre les pages et les numéros du JSON
global du même témoin. Chaque témoin y a une vue (lignes ou pages, avec sa
page de départ), ou n'en a pas (absent : « Pas d'alignement de ce témoin
pour ce texte. »).

- Projet exemple dont RLS_185 est synchronisé à part (165 lignes de T1,
  après la 116e ligne de l'édition ; T1 et T2 y ont un JSON, P non), avec
  les témoins par pages X (ses <pb> dans le texte) et Y (son <locus from>).
- Jeu « corpus » : s02 au pivot B (D y est relié), s04 au pivot A."""
from __future__ import annotations

import json

import pytest

from corpus_data import add_text_pages, copy_example, make_corpus, move_to_part, split_alignments
from project_config import load_project
from web_viewer.generator import build_dataset, generate


@pytest.fixture
def text_apart(tmp_path):
    project = copy_example(tmp_path / "exemple")
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    return project


def _export(project, **options):
    data, _missing = build_dataset(load_project(project), **options)
    return data


def _witness(data, wid):
    return next(w for w in data["witnesses"] if w["id"] == wid)


def test_the_texts_of_the_edition(text_apart):
    meta = _export(text_apart)["meta"]
    segments = meta["segments"]
    assert [(s["index"], s["name"], s["pivot"], s["prefix"], s["anchor"]) for s in segments] == [
        (0, None, "T1", "", 0), (1, "rls185", "T1", "~1~", 116)]
    assert segments[1]["file"] == "xml/rls185.xml" and segments[1]["lines"] == 165
    assert all(s["line_sync"] for s in segments)
    assert meta["lines"] == sum(s["lines"] for s in segments)


def test_the_reading_order_of_the_lines(text_apart):
    meta = _export(text_apart)["meta"]
    order = meta["line_order"]
    assert len(order) == meta["lines"] == len(set(order))
    prefixed = [i for i, key in enumerate(order) if key.startswith("~1~")]
    # RLS_185 à part s'insère entre la 116e et la 117e ligne de l'édition.
    assert prefixed == list(range(116, 116 + 165))


def test_each_witness_has_a_view_of_the_text_or_is_absent(text_apart):
    data = _export(text_apart)
    t1, t2, p, x, y = (_witness(data, wid) for wid in ("T1", "T2", "P", "X", "Y"))
    assert t1["views"]["1"]["mode"] == "line" and t1["views"]["1"]["role"] == "base"
    assert all(page["id"].startswith("~1~") for page in t1["views"]["1"]["pages"])
    assert sum(len(page["lines"]) for page in t1["views"]["1"]["pages"]) == 165
    view = t2["views"]["1"]
    assert view["mode"] == "line" and view["role"] == "secondary" and view["line_sync"]
    keys = [key for page in view["pages"] for line in page["lines"] for key in line.get("base_keys") or []]
    assert keys and all(key.startswith("~1~") for key in keys)
    assert "1" not in p.get("views", {})                       # P n'a pas ce texte
    assert x["views"]["1"]["mode"] == "page" and x["views"]["1"]["start"] == "X-p0001"   # avant 12v : 12r
    assert y["views"]["1"]["mode"] == "page" and y["views"]["1"]["start"] == "Y-p0002"   # son locus : 1v
    # La vue de l'édition reste celle d'avant : les champs du témoin.
    assert not any(page["id"].startswith("~") for page in t1["pages"])


def test_the_pivot_lines_of_a_text_carry_their_reading(text_apart):
    data = _export(text_apart)
    lines = [line for page in _witness(data, "T1")["views"]["1"]["pages"] for line in page["lines"]]
    assert all(line.get("corrected") for line in lines[:5])
    keys = {seg["line_key"] for block in data["document"]["blocks"] for seg in block["segments"]
            if seg.get("seg") == 1 and seg.get("line_key")}
    assert len(keys) == 165 and all(key.startswith("~1~") for key in keys)


def test_a_hidden_pivot_of_a_text_is_exported_without_images(tmp_path):
    data = _export(make_corpus(tmp_path / "corpus"), display_witness_ids=["A", "C", "D"])
    assert data["meta"]["display_witnesses"] == ["A", "C", "D"]
    b = _witness(data, "B")
    assert b["views"]["1"]["role"] == "base" and b["views"]["1"]["mode"] == "line"
    assert all((page.get("image") or {}).get("type") == "none" for page in b["views"]["1"]["pages"])
    d = _witness(data, "D")
    assert d["views"]["1"]["mode"] == "line" and "2" not in d.get("views", {})
    a = _witness(data, "A")
    assert "1" not in a.get("views", {}) and a["views"]["2"]["role"] == "base"


def test_the_images_of_a_text_are_copied_once(text_apart):
    output, _missing, data = generate(text_apart)
    images = sorted(p.relative_to(output.parent).as_posix() for p in (output.parent / "images").rglob("*.png"))
    assert images == sorted(set(images))
    assert [path for path in images if "/X/" in f"/{path}"] and len([path for path in images if "X" in path]) == 4
    x = _witness(data, "X")
    paths = {(page.get("image") or {}).get("path") for page in x["pages"]}
    assert paths and all(path and not path.startswith("/") for path in paths)
    assert str(text_apart.parent) not in json.dumps(data, ensure_ascii=False)
