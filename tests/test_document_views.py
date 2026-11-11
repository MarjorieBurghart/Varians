# -*- coding: utf-8 -*-
"""Vues nommées des documents (project.xml, sans Qt).

Une vue est une feuille XSLT et une CSS, avec en option les éléments
modifiables comme fragment : ``<view name="…" xslt="…" css="…" units="…"/>``,
sous ``<edition>`` (vues de l'édition, en plus de celle du projet) ou sous un
``<document>`` (document auxiliaire). Les chemins s'écrivent comme ceux des
scénarios de transformation : relatifs au projet, ou ``${varians}/…`` pour
une feuille fournie avec Varians.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

from project_config import DocumentConfig, ViewConfig, load_project
from project_management import update_project_documents, update_project_edition_views

PROJECT = """<?xml version="1.0" encoding="UTF-8"?>
<teiManuscriptProject version="1">
  <title>Gloses</title>
  <!-- l'édition -->
  <edition file="xml/edition.xml">{edition_views}</edition>
  <rendering xsltMode="builtin" css="rendering/tei.css"/>
  <witnesses/>
  {documents}
</teiManuscriptProject>
"""


def _project(tmp_path, edition_views="", documents=""):
    path = tmp_path / "project.xml"
    path.write_text(PROJECT.format(edition_views=edition_views, documents=documents), encoding="utf-8")
    return path


def test_a_project_without_views_has_none(tmp_path):
    project = load_project(_project(tmp_path, documents='<documents><document file="xml/a.xml"/></documents>'))
    assert project.edition_views == ()
    assert project.documents[0].views == ()


def test_views_of_the_edition_and_of_a_document_are_read(tmp_path):
    project = load_project(_project(
        tmp_path,
        edition_views='<view name="Apparat en notes" xslt="${varians}/apparat-en-notes.xsl" css="rendering/tei.css"/>',
        documents=('<documents><document file="xml/personnes.xml" label="Personnes">'
                   '<view name="Index" xslt="xslt/index.xsl" css="rendering/index.css" units="person  place"/>'
                   '<view name="Brut" xslt="xslt/brut.xsl"/>'
                   '</document></documents>')))
    assert project.edition_views == (ViewConfig("Apparat en notes", "${varians}/apparat-en-notes.xsl",
                                                 "rendering/tei.css"),)
    document = project.documents[0]
    assert document.label == "Personnes"
    assert document.views == (ViewConfig("Index", "xslt/index.xsl", "rendering/index.css", ("person", "place")),
                              ViewConfig("Brut", "xslt/brut.xsl"))
    assert document.views[1].css == "" and document.views[1].units == ()


def test_incomplete_or_repeated_views_are_ignored(tmp_path):
    project = load_project(_project(tmp_path, documents=(
        '<documents><document file="xml/a.xml">'
        '<view xslt="xslt/sans-nom.xsl"/>'
        '<view name="Sans feuille"/>'
        '<view name=" Index " xslt="xslt/un.xsl" units="person 1x a:b &lt;p&gt; place"/>'
        '<view name="Index" xslt="xslt/deux.xsl"/>'
        '</document></documents>')))
    assert project.documents[0].views == (ViewConfig("Index", "xslt/un.xsl", "", ("person", "place")),)


def test_document_views_are_kept_when_the_documents_change(tmp_path):
    path = _project(tmp_path, documents=(
        '<documents><document file="xml/a.xml"><view name="Index" xslt="xslt/i.xsl" units="person"/>'
        '</document></documents>'))
    project = load_project(path)
    added = DocumentConfig((tmp_path / "xml" / "b.xml").resolve(), "B",
                           views=(ViewConfig("Fiches", "xslt/f.xsl", "rendering/f.css"),))
    update_project_documents(path, list(project.documents) + [added])
    again = load_project(path)
    assert again.documents[0].views == project.documents[0].views
    assert again.documents[1].views == added.views
    view = ET.parse(path).getroot().find("documents/document/view")
    assert view.attrib == {"name": "Index", "xslt": "xslt/i.xsl", "units": "person"}


def test_edition_views_are_written_without_touching_the_rest(tmp_path):
    path = _project(tmp_path)
    before = path.read_text(encoding="utf-8")
    views = (ViewConfig("Apparat en notes", "${varians}/apparat-en-notes.xsl", "rendering/tei.css"),
             ViewConfig("Texte seul", "xslt/texte.xsl", units=("p", "lg")))
    update_project_edition_views(path, views)
    project = load_project(path)
    assert project.edition_views == views
    assert project.edition == (tmp_path / "xml" / "edition.xml").resolve()
    text = path.read_text(encoding="utf-8")
    assert "<!-- l'édition -->" in text and '<rendering xsltMode="builtin" css="rendering/tei.css"' in text
    update_project_edition_views(path, ())
    assert load_project(path).edition_views == ()
    assert ET.parse(path).getroot().find("edition").attrib == {"file": "xml/edition.xml"}
    assert (path.with_suffix(".xml.bak")).is_file() and before
