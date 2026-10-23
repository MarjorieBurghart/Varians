# -*- coding: utf-8 -*-
"""Fichiers des documents auxiliaires : copie dans le projet, nouveau document,
nouvelle feuille XSLT (V0.9.2.1)."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from document_dialogs import (STYLESHEET_VERSIONS, copy_document_into_project, document_target_path,
                              new_document_text, new_stylesheet_text)

XSL = "{http://www.w3.org/1999/XSL/Transform}"


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


# --- Feuilles XSLT (V0.9.2.1) ------------------------------------------------------------------

@pytest.mark.parametrize("name", ["index.xsl", "index.xslt"])
def test_outside_stylesheet_is_copied_into_xslt(tmp_path, name):
    project = tmp_path / "projet"
    (project / "xslt").mkdir(parents=True)
    stem, suffix = name.split(".")
    (project / "xslt" / name).write_text("<existant/>", encoding="utf-8")
    outside = tmp_path / "ailleurs" / name
    outside.parent.mkdir()
    outside.write_text("<nouvelle/>", encoding="utf-8")

    target = copy_document_into_project(outside, project)
    assert target == (project / "xslt" / f"{stem}_2.{suffix}").resolve()
    assert target.read_text(encoding="utf-8") == "<nouvelle/>"
    assert (project / "xslt" / name).read_text(encoding="utf-8") == "<existant/>"
    assert not (project / "xml").exists()


def test_copy_creates_the_xslt_folder(tmp_path):
    project = tmp_path / "projet"
    project.mkdir()
    outside = tmp_path / "Index.XSL"
    outside.write_text("<a/>", encoding="utf-8")
    assert copy_document_into_project(outside, project) == (project / "xslt" / "Index.XSL").resolve()


def test_stylesheet_inside_the_project_stays_in_place(tmp_path):
    inside = tmp_path / "rendering" / "tei-to-html.xsl"
    inside.parent.mkdir()
    inside.write_text("<a/>", encoding="utf-8")
    assert document_target_path(inside, tmp_path) == (inside.resolve(), False)


@pytest.mark.parametrize("version", ["1.0", "3.0"])
def test_new_stylesheet_text(version):
    text = new_stylesheet_text(version)
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n')
    root = ET.fromstring(text)
    assert root.tag == XSL + "stylesheet" and root.get("version") == version
    assert 'xmlns:tei="http://www.tei-c.org/ns/1.0"' in text
    assert root.find(XSL + "output") is not None
    assert [t.get("match") for t in root.findall(XSL + "template")] == ["/"]


def test_the_stylesheet_versions_are_those_of_the_two_engines():
    assert STYLESHEET_VERSIONS == (("1.0", "lxml"), ("3.0", "saxon"))
    with pytest.raises(ValueError):
        new_stylesheet_text("2.0")


DATA = Path(__file__).resolve().parent / "data" / "sermons"


@pytest.mark.parametrize("version, engine", [("1.0", "lxml"), ("3.0", "saxon")])
def test_a_new_stylesheet_runs_on_the_edition(tmp_path, version, engine):
    from project_config import TransformScenario, load_project
    from transform_worker import run_in_process
    from xslt_scenarios import saxon_available, scenario_request
    if engine == "saxon" and not saxon_available():
        pytest.skip("Saxon (saxonche) n'est pas installé")
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    (root / "xslt").mkdir()
    (root / "xslt" / "nouvelle.xsl").write_text(new_stylesheet_text(version), encoding="utf-8")
    project = load_project(root / "project.xml")
    scenario = TransformScenario("Essai", "xslt/nouvelle.xsl", "publications/essai.html", engine=engine)
    result = run_in_process(scenario_request(scenario, project))
    assert result.ok, result.error
    html = (root / "publications" / "essai.html").read_text(encoding="utf-8")
    assert "<title>" in html and "Sermones" in html and "saint Bernard" in html
