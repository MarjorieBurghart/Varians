# -*- coding: utf-8 -*-
"""Pivot propre à un texte d'une édition en parties (V0.9.1.1) : élément
<parts><part name="s02" base="B"/></parts> de project.xml.

Un projet sans <parts> reste strictement identique : ni lecture différente,
ni élément ajouté à l'enregistrement.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from project_config import PartConfig, load_project
from project_management import ProjectDraft, WitnessDraft, write_project_xml

PARTS = [PartConfig("s02", "B"), PartConfig("rls190", "T2")]


def _draft(root: Path, **extra) -> ProjectDraft:
    (root / "xml").mkdir(parents=True, exist_ok=True)
    edition = root / "xml" / "edition.xml"
    edition.write_text("<TEI/>", encoding="utf-8")
    return ProjectDraft(
        "Essai", edition, "fr", "en", root / "i18n",
        root / "rendering" / "tei-to-html.xsl", root / "rendering" / "tei.css",
        root / "rendering" / "custom-elements.xml", root / "web_output", "viewer.html",
        [WitnessDraft("A", "Témoin A"), WitnessDraft("B", "Témoin B")], "A",
        xslt_mode="builtin", schema_mode="none", **extra,
    )


def _project_xml(path: Path, extra: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<teiManuscriptProject version="1">\n'
        '  <title>Essai</title>\n'
        '  <edition file="xml/edition.xml"/>\n'
        '  <witnesses base="A"><witness id="A" label="A"/><witness id="B" label="B"/></witnesses>\n'
        f'  {extra}\n'
        '</teiManuscriptProject>\n',
        encoding="utf-8",
    )
    return path


def test_a_project_without_parts_reads_an_empty_tuple(tmp_path):
    assert load_project(_project_xml(tmp_path / "project.xml", "")).parts == ()


def test_parts_are_read_in_order(tmp_path):
    path = _project_xml(tmp_path / "project.xml",
                        '<parts><part name="s02" base="B"/><part name=" rls190 " base=" T2 "/></parts>')
    assert load_project(path).parts == tuple(PARTS)


def test_incomplete_or_repeated_parts_are_ignored(tmp_path):
    path = _project_xml(tmp_path / "project.xml",
                        '<parts><part name="s02" base="B"/><part name="s02" base="A"/>'
                        '<part name="s03"/><part base="B"/></parts>')
    assert load_project(path).parts == (PartConfig("s02", "B"),)


def test_a_part_naming_an_unknown_witness_is_kept_for_the_diagnostic(tmp_path):
    # Le projet s'ouvre ; le témoin inconnu est signalé par le diagnostic des
    # témoins (text_alignments), pas par une erreur à l'ouverture.
    path = _project_xml(tmp_path / "project.xml", '<parts><part name="s02" base="Z"/></parts>')
    assert load_project(path).parts == (PartConfig("s02", "Z"),)


def test_parts_are_written_and_read_back(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, parts=PARTS))
    root = ET.parse(path).getroot()
    assert [(p.get("name"), p.get("base")) for p in root.find("parts")] == [("s02", "B"), ("rls190", "T2")]
    assert load_project(path).parts == tuple(PARTS)


def test_a_project_without_parts_has_no_parts_element(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path))
    assert ET.parse(path).getroot().find("parts") is None
