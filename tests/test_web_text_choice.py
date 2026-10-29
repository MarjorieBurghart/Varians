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
