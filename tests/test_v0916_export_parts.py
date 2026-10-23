# -*- coding: utf-8 -*-
"""Export web d'une édition en parties (XInclude), numérotation continue
(V0.9.1.6).

L'export lit l'édition assemblée : le texte des parties est dans le viewer,
et les lignes du pivot sont comptées d'une partie à l'autre, comme sur le
bureau. Passer un sermon dans une partie ne change donc rien à l'export."""
from __future__ import annotations

import json
import shutil

import pytest

from corpus_data import SERMONS, copy_example, insert_at, move_to_part
from pivot_lines import pivot_lb_pattern
from project_config import load_project
from web_viewer.generator import build_dataset


def _export(project):
    data, _missing = build_dataset(load_project(project))
    data.pop("i18n", None)
    return data


def _text(data):
    return " ".join(seg.get("text", "") for block in data["document"]["blocks"] for seg in block["segments"])


def test_moving_a_sermon_into_a_part_changes_nothing(tmp_path):
    single = _export(copy_example(tmp_path / "un"))
    project = copy_example(tmp_path / "parties")
    move_to_part(project)
    assembled = _export(project)
    assert assembled["meta"].pop("assembled") is True
    assert assembled["meta"].pop("assembly_problems") == []
    assert json.dumps(assembled["document"], sort_keys=True) == json.dumps(single["document"], sort_keys=True)
    assert assembled["witnesses"] == single["witnesses"]
    assert assembled["meta"] == single["meta"]


@pytest.fixture
def sermons(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(SERMONS, root)
    return root / "project.xml"


def test_the_text_of_every_part_is_exported(sermons):
    data = _export(sermons)
    text = _text(data)
    for words in ("Sermo in adventu Domini", "Puer natus est nobis", "Surrexit Dominus vere", "exemplum"):
        assert words.lower() in text.lower(), words
    sermon_ids = [b["attrs"]["xml_id"] for b in data["document"]["blocks"] if b["type"] == "sermon"]
    assert [i for i in sermon_ids if i in ("s01", "s02", "s03", "s04")] == ["s01", "s02", "s03", "s04"]
    assert data["meta"]["assembled"] is True and data["meta"]["assembly_problems"] == []


def test_a_missing_part_is_reported(sermons):
    (sermons.parent / "xml" / "sermons" / "s03.xml").unlink()
    data = _export(sermons)
    problems = data["meta"]["assembly_problems"]
    assert [(p["file"], p["code"]) for p in problems] == [("xml/edition.xml", "missing")]
    assert problems[0]["line"] > 0
    assert "Sermo in adventu Domini" in _text(data)


def test_a_lacuna_crosses_the_parts(tmp_path):
    project = copy_example(tmp_path / "exemple")
    part = move_to_part(project)
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [m.span() for m in pivot_lb_pattern("T1").finditer(text)]
    edition.write_text(insert_at(text, [(lbs[110][1], '<lacunaStart wit="#T2"/>')]), encoding="utf-8")
    text = part.read_text(encoding="utf-8")
    lbs = [m.span() for m in pivot_lb_pattern("T1").finditer(text)]
    part.write_text(insert_at(text, [(lbs[10][1], '<lacunaEnd wit="#T2"/>')]), encoding="utf-8")
    segments = [s for b in _export(project)["document"]["blocks"] for s in b["segments"]]
    markers = [(s["start"], s["wit"]) for s in segments if s["kind"] == "lacuna"]
    assert markers == [(True, ["T2"]), (False, ["T2"])]
