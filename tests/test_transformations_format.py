# -*- coding: utf-8 -*-
"""Scénarios de transformation XSLT (V0.9.2.0) : élément <transformations>
de project.xml.

Un projet sans <transformations> reste strictement identique : ni lecture
différente, ni élément ajouté à l'enregistrement. Les chemins d'un scénario
sont gardés tels qu'ils sont écrits ; xslt_scenarios les résout.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from project_config import TransformScenario, load_project
from project_management import ProjectDraft, WitnessDraft, update_project_transformations, write_project_xml

PERSONS = TransformScenario(
    "Index des personnes", "rendering/personnes.xsl", "publications/personnes.html",
    source="file", file="xml/personnes.xml", css="rendering/personnes.css",
    params=(("titre", "Index des personnes"), ("vide", "")))
PAGES = TransformScenario("Une page par sermon", "rendering/pages.xsl", "publications/sermons/index.html",
                          engine="saxon")


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
        '  <title>Essai</title>\n'
        '  <edition file="xml/edition.xml"/>\n'
        '  <witnesses base="A"><witness id="A" label="A"/></witnesses>\n'
        f'  {extra}\n'
        '</teiManuscriptProject>\n',
        encoding="utf-8",
    )
    return path


def test_a_project_without_transformations_reads_an_empty_tuple(tmp_path):
    assert load_project(_project_xml(tmp_path / "project.xml", "")).transformations == ()


def test_scenarios_are_read_in_order_with_their_defaults(tmp_path):
    path = _project_xml(tmp_path / "project.xml", """<transformations>
      <scenario name=" Index des personnes " source="file" file="xml/personnes.xml" engine="lxml"
                xslt="rendering/personnes.xsl" css="rendering/personnes.css"
                output="publications/personnes.html">
        <param name="titre" value="Index des personnes"/>
        <param name="vide"/>
      </scenario>
      <scenario name="Une page par sermon" engine="saxon" xslt="rendering/pages.xsl"
                output="publications/sermons/index.html"/>
    </transformations>""")
    assert load_project(path).transformations == (PERSONS, PAGES)
    assert PAGES.source == "edition" and PAGES.file == "" and PAGES.css == "" and PAGES.params == ()
    assert TransformScenario("x", "a.xsl", "b.html").engine == "lxml"


def test_nameless_or_repeated_scenarios_and_parameters_are_ignored(tmp_path):
    path = _project_xml(tmp_path / "project.xml", """<transformations>
      <scenario xslt="a.xsl" output="a.html"/>
      <scenario name="A" xslt="a.xsl" output="a.html">
        <param name="p" value="1"/><param name="p" value="2"/><param value="sans nom"/>
      </scenario>
      <scenario name="A" xslt="b.xsl" output="b.html"/>
    </transformations>""")
    assert load_project(path).transformations == (TransformScenario("A", "a.xsl", "a.html", params=(("p", "1"),)),)


def test_an_incomplete_or_unknown_scenario_is_kept_for_the_diagnostic(tmp_path):
    # Le projet s'ouvre ; la liste des scénarios montre le problème
    # (xslt_scenarios.scenario_problems) et l'enregistrement garde le scénario.
    path = _project_xml(tmp_path / "project.xml", """<transformations>
      <scenario name="Sans feuille" output="a.html"/>
      <scenario name="Moteur futur" engine="xsltproc" source="collection" xslt="a.xsl" output="b.html"/>
    </transformations>""")
    assert load_project(path).transformations == (
        TransformScenario("Sans feuille", "", "a.html"),
        TransformScenario("Moteur futur", "a.xsl", "b.html", source="collection", engine="xsltproc"),
    )


def test_scenarios_are_written_and_read_back(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path, transformations=[PERSONS, PAGES]))
    scenarios = ET.parse(path).getroot().find("transformations")
    first = scenarios[0]
    assert first.attrib == {"name": "Index des personnes", "source": "file", "file": "xml/personnes.xml",
                            "engine": "lxml", "xslt": "rendering/personnes.xsl", "css": "rendering/personnes.css",
                            "output": "publications/personnes.html"}
    assert [p.attrib for p in first.findall("param")] == [{"name": "titre", "value": "Index des personnes"},
                                                         {"name": "vide", "value": ""}]
    assert scenarios[1].attrib == {"name": "Une page par sermon", "source": "edition", "engine": "saxon",
                                   "xslt": "rendering/pages.xsl", "output": "publications/sermons/index.html"}
    assert load_project(path).transformations == (PERSONS, PAGES)


def test_a_project_without_scenarios_has_no_transformations_element(tmp_path):
    path = write_project_xml(tmp_path / "project.xml", _draft(tmp_path))
    assert ET.parse(path).getroot().find("transformations") is None


def test_updating_the_scenarios_keeps_the_rest_of_the_file(tmp_path):
    path = _project_xml(tmp_path / "project.xml", "<!-- note de l'éditeur -->\n  <parts/>")
    before = path.read_text(encoding="utf-8")
    update_project_transformations(path, [PAGES])
    text = path.read_text(encoding="utf-8")
    assert "<!-- note de l'éditeur -->" in text and "<parts" in text
    assert path.with_suffix(".xml.bak").read_text(encoding="utf-8") == before
    assert load_project(path).transformations == (PAGES,)
    update_project_transformations(path, [])
    assert ET.parse(path).getroot().find("transformations") is None
