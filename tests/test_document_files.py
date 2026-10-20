# -*- coding: utf-8 -*-
"""Fichiers des documents auxiliaires : copie dans le projet, nouveau document."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from document_dialogs import copy_document_into_project, document_target_path, new_document_text


def test_file_inside_the_project_is_used_in_place(tmp_path):
    inside = tmp_path / "autorites" / "personnes.xml"
    inside.parent.mkdir()
    inside.write_text("<a/>", encoding="utf-8")
    assert document_target_path(inside, tmp_path) == (inside.resolve(), False)
    assert copy_document_into_project(inside, tmp_path) == inside.resolve()
    assert not (tmp_path / "xml").exists()


def test_outside_file_is_copied_into_xml_without_overwriting(tmp_path):
    project = tmp_path / "projet"
    (project / "xml").mkdir(parents=True)
    existing = project / "xml" / "personnes.xml"
    existing.write_text("<existant/>", encoding="utf-8")
    (project / "xml" / "personnes_2.xml").write_text("<existant2/>", encoding="utf-8")
    outside = tmp_path / "ailleurs" / "personnes.xml"
    outside.parent.mkdir()
    outside.write_text("<nouveau/>", encoding="utf-8")

    target = copy_document_into_project(outside, project)
    assert target == (project / "xml" / "personnes_3.xml").resolve()
    assert target.read_text(encoding="utf-8") == "<nouveau/>"
    assert existing.read_text(encoding="utf-8") == "<existant/>"
    assert outside.read_text(encoding="utf-8") == "<nouveau/>"


def test_copy_creates_the_xml_folder(tmp_path):
    project = tmp_path / "projet"
    project.mkdir()
    outside = tmp_path / "lieux.xml"
    outside.write_text("<a/>", encoding="utf-8")
    assert copy_document_into_project(outside, project) == (project / "xml" / "lieux.xml").resolve()


@pytest.mark.parametrize("root, namespace", [
    ("TEI", "{http://www.tei-c.org/ns/1.0}TEI"),
    ("listPerson", "listPerson"),
])
def test_new_document_text(root, namespace):
    text = new_document_text(root)
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n')
    assert ET.fromstring(text).tag == namespace


@pytest.mark.parametrize("name", ["", "1abc", "a b", "<x>", "tei:TEI"])
def test_invalid_root_names_are_refused(name):
    with pytest.raises(ValueError):
        new_document_text(name)
