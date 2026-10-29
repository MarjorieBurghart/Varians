# -*- coding: utf-8 -*-
"""Choix du texte du viewer web (V0.9.3.0), sans Qt.

Au moment de « Générer viewer web », le texte est soit le texte établi (le
<lem>, à défaut la leçon d'un témoin choisi), soit le texte d'un témoin (sa
leçon, même quand elle n'est pas le <lem>). Le choix est gardé dans
project.xml : ``<webViewer text="established|witness" textWitness="T2"/>``
(``textWitness`` absent : le pivot de chaque texte ; ``text`` absent : le
texte établi)."""
from __future__ import annotations

import pytest

from corpus_data import copy_example
from project_config import load_project
from project_management import update_project_web_text


def _web_viewer(project_xml, attributes):
    text = project_xml.read_text(encoding="utf-8")
    old = '<webViewer outputDir="web_output" filename="viewer.html" />'
    assert old in text
    project_xml.write_text(text.replace(old, f'<webViewer outputDir="web_output" filename="viewer.html" {attributes}/>'),
                           encoding="utf-8")


def test_without_setting_the_text_is_the_established_text_of_the_pivot(tmp_path):
    project = load_project(copy_example(tmp_path / "exemple"))
    assert (project.web_text_mode, project.web_text_witness) == ("established", "")


@pytest.mark.parametrize("attributes, expected", [
    ('text="witness" textWitness="T2"', ("witness", "T2")),
    ('text="established" textWitness="P"', ("established", "P")),
    ('text="witness"', ("witness", "")),
    ('text="autre" textWitness=" T2 "', ("established", "T2")),
])
def test_the_setting_is_read_from_the_web_viewer_element(tmp_path, attributes, expected):
    project_xml = copy_example(tmp_path / "exemple")
    _web_viewer(project_xml, attributes)
    project = load_project(project_xml)
    assert (project.web_text_mode, project.web_text_witness) == expected


def test_the_setting_is_written_without_touching_the_rest(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    text = project_xml.read_text(encoding="utf-8")
    project_xml.write_text(text.replace("<webViewer", "<!-- viewer -->\n  <webViewer", 1), encoding="utf-8")
    update_project_web_text(project_xml, "witness", "T2")
    project = load_project(project_xml)
    assert (project.web_text_mode, project.web_text_witness) == ("witness", "T2")
    assert (project.web_output_dir.name, project.web_filename) == ("web_output", "viewer.html")
    assert "<!-- viewer -->" in project_xml.read_text(encoding="utf-8")
    assert project_xml.with_suffix(".xml.bak").read_text(encoding="utf-8") == text.replace(
        "<webViewer", "<!-- viewer -->\n  <webViewer", 1)
    update_project_web_text(project_xml, "established", "")
    assert 'textWitness' not in project_xml.read_text(encoding="utf-8")
    assert load_project(project_xml).web_text_mode == "established"
    with pytest.raises(ValueError):
        update_project_web_text(project_xml, "autre", "")


def test_a_project_without_web_viewer_element_receives_one(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    text = project_xml.read_text(encoding="utf-8")
    project_xml.write_text(text.replace('<webViewer outputDir="web_output" filename="viewer.html" />', ""),
                           encoding="utf-8")
    update_project_web_text(project_xml, "witness", "P")
    project = load_project(project_xml)
    assert (project.web_text_mode, project.web_text_witness) == ("witness", "P")
    assert project.web_filename == "viewer.html"


# --- Générateur (E.3) -------------------------------------------------------------------------

def _lem_differs(project_xml):
    """Un <app> du projet exemple dont le <lem> n'est pas la leçon du pivot
    (T1), et un autre où T2 n'a pas de leçon."""
    edition = project_xml.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    old = "Uos estis"
    assert old in text
    edition.write_text(text.replace(old, '<app><lem wit="#T2">Vosestis</lem><rdg wit="#T1">Uosestis</rdg></app>'
                                         '<app><lem wit="#T1">qui</lem><rdg wit="#P">que</rdg></app>', 1),
                       encoding="utf-8")


def _words(data):
    return " ".join(seg.get("text", "") for block in data["document"]["blocks"] for seg in block["segments"]
                    if seg["kind"] == "text")


def test_the_export_follows_the_choice_of_project_xml_or_the_one_given(tmp_path):
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    _lem_differs(project_xml)
    data = build_dataset(load_project(project_xml))[0]
    assert "Vosestis" in _words(data) and "Uosestis" not in _words(data)        # texte établi, par défaut
    text = data["meta"]["text"]                       # ``nonlem`` : voir plus bas (V0.9.3.1)
    assert text == {"mode": "established", "witness": "", "missing": 0, "nonlem": text["nonlem"], "highlight": False}
    data = build_dataset(load_project(project_xml), text_mode="witness", text_witness="T2")[0]
    assert "Vosestis" in _words(data)
    assert data["meta"]["text"]["mode"] == "witness" and data["meta"]["text"]["witness"] == "T2"
    assert data["meta"]["text"]["missing"] >= 1                                 # « qui » : pas de T2
    update_project_web_text(project_xml, "witness", "T1")
    data = build_dataset(load_project(project_xml))[0]
    assert "Uosestis" in _words(data) and "Vosestis" not in _words(data)


def test_an_unknown_witness_falls_back_to_the_pivot(tmp_path):
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    _web_viewer(project_xml, 'text="witness" textWitness="Z"')
    data = build_dataset(load_project(project_xml))[0]
    assert data["meta"]["text"] == {"mode": "witness", "witness": "", "missing": 0, "unknown": "Z",
                                    "nonlem": 0, "highlight": False}


def test_every_line_of_the_pivot_keeps_its_place_whatever_the_choice(tmp_path):
    # Chaque ligne du pivot garde du texte, ou, quand le témoin choisi omet
    # le passage, un repère invisible à sa place (T2 omet deux passages, où
    # s'ouvrent cinq lignes de T1).
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    keys = None
    for choice in ({}, dict(text_mode="established"), dict(text_mode="witness", text_witness="T2"),
                   dict(text_mode="witness", text_witness="P")):
        data = build_dataset(load_project(project_xml), **choice)[0]
        segments = [seg for block in data["document"]["blocks"] for seg in block["segments"]]
        found = {seg["line_key"] for seg in segments if seg["kind"] in ("text", "line-anchor") and seg.get("line_key")}
        keys = found if keys is None else keys
        assert found == keys, choice
        anchors = [seg for seg in segments if seg["kind"] == "line-anchor"]
        assert len(anchors) == (5 if choice.get("text_witness") == "T2" else 0), choice


# --- Leçons hors <lem> surlignées (V0.9.3.1) -----------------------------------------------------
# Texte établi : la boîte « Générer viewer web » fixe l'état de départ du
# surlignage (``<webViewer highlightNonLem="true"/>``) ; le lecteur le change
# dans l'en-tête du viewer.

@pytest.mark.parametrize("attributes, expected", [('', False), ('highlightNonLem="true"', True),
                                                  ('highlightNonLem="false"', False)])
def test_the_highlight_of_readings_outside_a_lem_is_read_from_project_xml(tmp_path, attributes, expected):
    project_xml = copy_example(tmp_path / "exemple")
    if attributes:
        _web_viewer(project_xml, attributes)
    assert load_project(project_xml).web_highlight_nonlem is expected


def test_the_highlight_is_written_with_the_text_choice(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    update_project_web_text(project_xml, "established", "", highlight_nonlem=True)
    assert 'highlightNonLem="true"' in project_xml.read_text(encoding="utf-8")
    assert load_project(project_xml).web_highlight_nonlem is True
    update_project_web_text(project_xml, "witness", "T2")                 # sans avis : inchangé
    assert load_project(project_xml).web_highlight_nonlem is True
    update_project_web_text(project_xml, "established", "", highlight_nonlem=False)
    assert "highlightNonLem" not in project_xml.read_text(encoding="utf-8")


def test_the_export_counts_the_readings_outside_a_lem_and_gives_the_starting_state(tmp_path):
    from web_viewer.generator import build_dataset
    project_xml = copy_example(tmp_path / "exemple")
    text = build_dataset(load_project(project_xml))[0]["meta"]["text"]
    assert text["nonlem"] > 0 and text["highlight"] is False
    text = build_dataset(load_project(project_xml), highlight_nonlem=True)[0]["meta"]["text"]
    assert text["highlight"] is True
    update_project_web_text(project_xml, "established", "", highlight_nonlem=True)
    assert build_dataset(load_project(project_xml))[0]["meta"]["text"]["highlight"] is True
    text = build_dataset(load_project(project_xml), text_mode="witness", text_witness="T2")[0]["meta"]["text"]
    assert text["nonlem"] == 0 and text["highlight"] is False
