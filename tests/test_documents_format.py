# -*- coding: utf-8 -*-
"""Documents XML auxiliaires déclarés dans project.xml (élément <documents>).

Un projet qui ne déclare aucun document auxiliaire doit rester strictement
identique : ni lecture différente, ni élément <documents> ajouté à
l'enregistrement.
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from dataclasses import replace
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_config import DocumentConfig, load_project  # noqa: E402
from project_management import (  # noqa: E402
    ProjectDraft, WitnessDraft, update_project_documents, write_project_xml,
)


def _copy_example(tmp_path) -> Path:
    from corpus_data import copy_example
    return copy_example(tmp_path / "exemple")


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


def _project_xml(path: Path, documents: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<teiManuscriptProject version="1">\n'
        '  <title>Essai</title>\n'
        '  <edition file="xml/edition.xml"/>\n'
        '  <witnesses base="A"><witness id="A" label="A"/></witnesses>\n'
        f'  {documents}\n'
        '</teiManuscriptProject>\n',
        encoding="utf-8",
    )
    return path


def test_project_without_documents_reads_an_empty_tuple(tmp_path):
    project = load_project(_copy_example(tmp_path))
    assert project.documents == ()


def test_writing_a_project_without_documents_adds_no_element(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path))
    root = ET.parse(path).getroot()
    assert root.find("documents") is None
    assert "documents" not in path.read_text(encoding="utf-8")
    assert load_project(path).documents == ()


def test_documents_round_trip_through_write_and_load(tmp_path):
    documents = [
        DocumentConfig(tmp_path / "xml" / "personnes.xml", "Personnes"),
        DocumentConfig(tmp_path / "xml" / "lieux.xml", schema_mode="none"),
        DocumentConfig(tmp_path / "xml" / "notes.xml", "Notes", "file",
                       tmp_path / "schema" / "notes.rng"),
    ]
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, documents=documents))

    items = ET.parse(path).getroot().find("documents").findall("document")
    # Chemins portables, attributs par défaut omis.
    assert [item.attrib for item in items] == [
        {"file": "xml/personnes.xml", "label": "Personnes"},
        {"file": "xml/lieux.xml", "schema": "none"},
        {"file": "xml/notes.xml", "label": "Notes", "schema": "file",
         "schemaFile": "schema/notes.rng"},
    ]
    loaded = load_project(path).documents
    assert loaded == tuple(replace(d, path=d.path.resolve(),
                                   schema=d.schema.resolve() if d.schema else None)
                           for d in documents)


def test_document_label_defaults_to_the_file_name(tmp_path):
    path = _project_xml(tmp_path / "project.xml",
                        '<documents><document file="xml/personnes.xml"/></documents>')
    (doc,) = load_project(path).documents
    assert doc.label == ""
    assert doc.display_label == "personnes.xml"
    assert doc.schema_mode == "auto" and doc.schema is None


def test_duplicates_the_edition_and_empty_entries_are_ignored(tmp_path):
    path = _project_xml(tmp_path / "project.xml", (
        '<documents>'
        '<document file="xml/personnes.xml" label="Premier"/>'
        '<document file="xml/../xml/personnes.xml" label="Doublon"/>'
        '<document file="xml/edition.xml" label="Édition"/>'
        '<document file="  "/>'
        '<document label="Sans fichier"/>'
        '<document file="xml/lieux.xml"/>'
        '</documents>'))
    documents = load_project(path).documents
    assert [d.label for d in documents] == ["Premier", ""]
    assert [d.path.name for d in documents] == ["personnes.xml", "lieux.xml"]


def test_schema_aliases_are_accepted(tmp_path):
    path = _project_xml(tmp_path / "project.xml", (
        '<documents>'
        '<document file="a.xml" schema="xml-model"/>'
        '<document file="b.xml" schema="project" schemaFile="b.rng"/>'
        '<document file="c.xml" schema="off"/>'
        '</documents>'))
    assert [d.schema_mode for d in load_project(path).documents] == ["auto", "file", "none"]


@pytest.mark.parametrize("documents", [
    '<documents><document file="a.xml" schema="dtd"/></documents>',
    '<documents><document file="a.xml" schema="file"/></documents>',
])
def test_invalid_document_schema_is_reported(tmp_path, documents):
    path = _project_xml(tmp_path / "project.xml", documents)
    with pytest.raises(ValueError):
        load_project(path)


def test_writing_an_unknown_document_schema_mode_is_refused(tmp_path):
    draft = _draft(tmp_path, documents=[DocumentConfig(tmp_path / "a.xml", schema_mode="dtd")])
    with pytest.raises(ValueError):
        write_project_xml(tmp_path / "project.xml", draft)


def test_update_project_documents_changes_only_the_documents(tmp_path):
    path = _copy_example(tmp_path)
    before = load_project(path)
    original_text = path.read_text(encoding="utf-8")

    personnes = path.parent / "xml" / "personnes.xml"
    update_project_documents(path, [DocumentConfig(personnes, "Personnes")])

    after = load_project(path)
    assert after.documents == (DocumentConfig(personnes.resolve(), "Personnes"),)
    assert replace(after, documents=()) == before
    backup = path.with_suffix(".xml.bak")
    assert backup.read_text(encoding="utf-8") == original_text

    # Retirer le dernier document retire l'élément : le projet redevient simple.
    update_project_documents(path, [])
    assert load_project(path) == before
    assert ET.parse(path).getroot().find("documents") is None


def test_update_project_documents_keeps_comments(tmp_path):
    path = _project_xml(tmp_path / "project.xml", "<!-- à conserver -->")
    update_project_documents(path, [DocumentConfig(tmp_path / "a.xml")])
    assert "<!-- à conserver -->" in path.read_text(encoding="utf-8")
