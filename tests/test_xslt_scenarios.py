# -*- coding: utf-8 -*-
"""Scénarios de transformation XSLT (V0.9.2.0), sans Qt : chemins, sources,
garde-fous du résultat, requête d'exécution, scénarios prédéfinis.

Jeu d'essai : « sermons » (tests/data/sermons), une édition en parties et un
document auxiliaire (xml/personnes.xml).
"""
from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from project_config import DEFAULT_APPLICATION_XSLT, TransformScenario, load_project
from xslt_scenarios import (VARIANS_STYLESHEETS, predefined_scenarios, resolve_path, saxon_available,
                            scenario_problems, scenario_request, stylesheet_path)

DATA = Path(__file__).resolve().parent / "data" / "sermons"
BASE = TransformScenario("Personnes", "rendering/personnes.xsl", "publications/personnes.html",
                         source="file", file="xml/personnes.xml")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    (root / "rendering" / "personnes.xsl").write_text("<xsl:stylesheet/>", encoding="utf-8")
    (root / "alignments" / "s02").mkdir(parents=True)
    (root / "alignments" / "s02" / "B.json").write_text("{}", encoding="utf-8")
    return load_project(root / "project.xml")


def _codes(problems):
    return [problem.code for problem in problems]


# --- Chemins ------------------------------------------------------------------------------

def test_paths_are_relative_to_the_project_or_to_the_stylesheets_of_varians(project):
    assert VARIANS_STYLESHEETS == DEFAULT_APPLICATION_XSLT.parent
    assert resolve_path(project, "rendering/a.xsl") == project.root_dir / "rendering" / "a.xsl"
    assert resolve_path(project, "${varians}/tei-to-html.xsl") == DEFAULT_APPLICATION_XSLT
    assert resolve_path(project, "") is None
    assert stylesheet_path(BASE, project) == project.root_dir / "rendering" / "personnes.xsl"


def test_the_predefined_scenario_publishes_the_edition_with_the_stylesheet_of_varians(project):
    (scenario,) = predefined_scenarios()
    assert scenario == TransformScenario("varians-html", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                         css="${varians}/tei.css")
    assert predefined_scenarios(lambda key: key.upper())[0].name == "VARIANS-HTML"
    assert stylesheet_path(scenario, project).is_file()
    assert scenario_problems(scenario, project) == []


# --- Problèmes ------------------------------------------------------------------------------

def test_a_complete_scenario_has_no_problem(project):
    assert scenario_problems(BASE, project) == []


@pytest.mark.parametrize("change, code", [
    ({"xslt": ""}, "no_xslt"),
    ({"xslt": "rendering/absente.xsl"}, "xslt_missing"),
    ({"output": ""}, "no_output"),
    ({"source": "collection"}, "unknown_source"),
    ({"file": ""}, "no_file"),
    ({"file": "xml/absent.xml"}, "file_missing"),
    ({"engine": "xsltproc"}, "unknown_engine"),
    ({"css": "rendering/absente.css"}, "css_missing"),
])
def test_each_problem_of_a_scenario_is_named(project, change, code):
    assert _codes(scenario_problems(replace(BASE, **change), project)) == [code]


def test_saxon_missing_is_a_problem_only_for_a_saxon_scenario(project, monkeypatch):
    import xslt_scenarios
    monkeypatch.setattr(xslt_scenarios, "saxon_available", lambda: False)
    assert _codes(scenario_problems(replace(BASE, engine="saxon"), project)) == ["saxon_missing"]
    assert scenario_problems(BASE, project) == []


def test_saxon_is_detected_without_being_loaded():
    import sys
    loaded = "saxonche" in sys.modules
    assert saxon_available() in (True, False)
    assert ("saxonche" in sys.modules) == loaded


@pytest.mark.parametrize("output", [
    "project.xml", "xml/edition.xml", "xml/sermons/s01.xml", "xml/sermons/s04_exemplum.xml",
    "xml/personnes.xml", "rendering/personnes.xsl", "rendering/tei.css", "rendering/custom-elements.xml",
    "alignments/s02/B.json",
])
def test_the_result_never_overwrites_a_source_of_the_project(project, output):
    problems = scenario_problems(replace(BASE, output=output), project)
    assert _codes(problems) == ["output_is_source"]
    assert problems[0].detail == output


def test_the_result_may_not_be_a_folder(project):
    assert _codes(scenario_problems(replace(BASE, output="xml/sermons"), project)) == ["output_is_folder"]


def test_the_copy_of_the_css_never_overwrites_a_source_of_the_project(project):
    (project.root_dir / "rendering" / "personnes.css").write_text("p {}", encoding="utf-8")
    scenario = replace(BASE, css="rendering/personnes.css", output="rendering/personnes.html")
    assert scenario_problems(scenario, project) == []                      # la CSS est déjà là
    # La CSS de Varians copiée dans rendering/ remplacerait celle du projet.
    scenario = replace(BASE, css="${varians}/tei.css", output="rendering/personnes.html")
    problems = scenario_problems(scenario, project)
    assert _codes(problems) == ["css_overwrites_source"]
    assert problems[0].detail == "rendering/tei.css"


# --- Sources --------------------------------------------------------------------------------

def test_the_edition_is_assembled(project):
    request = scenario_request(replace(BASE, source="edition"), project)
    assert request["source"] == str(project.edition)
    assert request["assemble"] is True


def test_a_file_is_read_as_it_is(project):
    request = scenario_request(BASE, project)
    assert request["source"] == str(project.root_dir / "xml" / "personnes.xml")
    assert request["assemble"] is False


def test_the_displayed_document_is_the_current_file_or_the_assembled_edition(project):
    scenario = replace(BASE, source="current", file="")
    assert _codes(scenario_problems(scenario, project)) == ["no_current"]
    part = project.root_dir / "xml" / "sermons" / "s02.xml"
    assert scenario_problems(scenario, project, current=part) == []
    request = scenario_request(scenario, project, current=part)
    assert (request["source"], request["assemble"]) == (str(part), False)
    request = scenario_request(scenario, project, current=project.edition)
    assert (request["source"], request["assemble"]) == (str(project.edition), True)


# --- Requête ------------------------------------------------------------------------------

def test_the_request_holds_absolute_paths_and_the_parameters(project):
    scenario = replace(BASE, css="rendering/tei.css", params=(("titre", "Index"),))
    request = scenario_request(scenario, project)
    root = project.root_dir
    assert request["engine"] == "lxml"
    assert request["xslt"] == str(root / "rendering" / "personnes.xsl")
    assert request["css"] == str(root / "rendering" / "tei.css")
    assert request["output"] == str(root / "publications" / "personnes.html")
    # Le nom de la CSS est passé à la feuille, sauf si le scénario le fixe.
    assert request["params"] == [["titre", "Index"], ["css", "tei.css"]]
    scenario = replace(scenario, params=(("css", "autre.css"),))
    assert scenario_request(scenario, project)["params"] == [["css", "autre.css"]]
    assert str(root / "xml" / "edition.xml") in request["protected"]
    assert str(root / "rendering" / "personnes.xsl") in request["protected"]


def test_the_preview_writes_in_another_folder(project, tmp_path):
    request = scenario_request(BASE, project, output_dir=tmp_path / "apercu")
    assert request["output"] == str(tmp_path / "apercu" / "personnes.html")


# --- Chemins écrits par la boîte d'un scénario ------------------------------------------------

def test_a_chosen_path_is_written_relative_to_the_project_or_to_the_stylesheets_of_varians(project, tmp_path):
    from xslt_scenarios import scenario_path
    assert scenario_path(project, project.root_dir / "rendering" / "a.xsl") == "rendering/a.xsl"
    assert scenario_path(project, DEFAULT_APPLICATION_XSLT) == "${varians}/tei-to-html.xsl"
    assert scenario_path(project, tmp_path / "ailleurs.xsl") == (tmp_path / "ailleurs.xsl").as_posix()


def test_each_problem_has_a_message_in_the_seven_catalogs():
    import xml.etree.ElementTree as ET
    from xslt_scenarios import PROBLEM_CODES
    assert "output_is_source" in PROBLEM_CODES and len(PROBLEM_CODES) == 13
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        root = ET.parse(Path(__file__).resolve().parents[1] / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key") for string in root.findall("string")}
        assert {f"transform.problem.{code}" for code in PROBLEM_CODES} <= catalog, language
