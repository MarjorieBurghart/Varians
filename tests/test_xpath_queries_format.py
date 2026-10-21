# -*- coding: utf-8 -*-
"""Requêtes XPath nommées enregistrées dans project.xml (élément <xpathQueries>).

Un projet sans requête doit rester strictement identique : ni lecture
différente, ni élément <xpathQueries> ajouté à l'enregistrement.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from project_config import DocumentConfig, XPathQuery, load_project
from project_management import (
    ProjectDraft, WitnessDraft, update_project_documents, update_project_xpath_queries, write_project_xml,
)

QUERIES = [
    XPathQuery("rdg sans @wit", "//tei:rdg[not(@wit)]"),
    XPathQuery("Leçons courtes & vides", "//tei:rdg[string-length(.) < 2 and @type=\"om\"]"),
]


def _draft(root: Path, **extra) -> ProjectDraft:
    (root / "xml").mkdir(parents=True, exist_ok=True)
    edition = root / "xml" / "edition.xml"
    edition.write_text("<TEI/>", encoding="utf-8")
    return ProjectDraft(
        "Essai", edition, "fr", "en", root / "i18n",
        root / "rendering" / "tei-to-html.xsl", root / "rendering" / "tei.css",
        root / "rendering" / "custom-elements.xml", root / "web_output", "viewer.html",
        [WitnessDraft("A", "Témoin A")], "A",
        xslt_mode="builtin", schema_mode="none", **extra,
    )


def _project_xml(path: Path, extra: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<teiManuscriptProject version="1">\n'
        '  <!-- commentaire conservé -->\n'
        '  <title>Essai</title>\n'
        '  <edition file="xml/edition.xml"/>\n'
        '  <witnesses base="A"><witness id="A" label="A"/></witnesses>\n'
        f'  {extra}\n'
        '</teiManuscriptProject>\n',
        encoding="utf-8",
    )
    return path


def test_project_without_queries_reads_an_empty_tuple(tmp_path):
    assert load_project(_project_xml(tmp_path / "project.xml", "")).xpath_queries == ()


def test_writing_a_project_without_queries_adds_no_element(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path))
    assert "xpathQueries" not in path.read_text(encoding="utf-8")
    assert load_project(path).xpath_queries == ()


def test_queries_round_trip_through_write_and_load(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, xpath_queries=QUERIES))
    items = ET.parse(path).getroot().find("xpathQueries").findall("query")
    assert [(item.get("name"), item.text) for item in items] == [(q.name, q.expression) for q in QUERIES]
    assert load_project(path).xpath_queries == tuple(QUERIES)


def test_unnamed_empty_and_duplicate_queries_are_ignored(tmp_path):
    path = _project_xml(tmp_path / "project.xml", (
        '<xpathQueries>'
        '<query name="  Premier  ">  //tei:app  </query>'
        '<query name="Premier">//tei:rdg</query>'
        '<query name="Vide">   </query>'
        '<query>//tei:lem</query>'
        '<query name="Second">//tei:note</query>'
        '</xpathQueries>'))
    assert load_project(path).xpath_queries == (
        XPathQuery("Premier", "//tei:app"), XPathQuery("Second", "//tei:note"))


def test_updating_queries_rewrites_only_that_element(tmp_path):
    path = _project_xml(tmp_path / "project.xml",
                        '<documents><document file="xml/personnes.xml" label="Personnes"/></documents>')
    before = path.read_text(encoding="utf-8")
    update_project_xpath_queries(path, QUERIES)
    text = path.read_text(encoding="utf-8")
    assert "commentaire conservé" in text
    assert path.with_name("project.xml.bak").read_text(encoding="utf-8") == before
    project = load_project(path)
    assert project.xpath_queries == tuple(QUERIES)
    assert [d.label for d in project.documents] == ["Personnes"]

    update_project_xpath_queries(path, QUERIES[:1])
    assert load_project(path).xpath_queries == tuple(QUERIES[:1])
    update_project_xpath_queries(path, [])
    assert "xpathQueries" not in path.read_text(encoding="utf-8")


def test_updating_documents_keeps_the_queries(tmp_path):
    path = _project_xml(tmp_path / "project.xml", "")
    update_project_xpath_queries(path, QUERIES)
    update_project_documents(path, [DocumentConfig(tmp_path / "xml" / "lieux.xml")])
    project = load_project(path)
    assert project.xpath_queries == tuple(QUERIES)
    assert [d.path.name for d in project.documents] == ["lieux.xml"]
