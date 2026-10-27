# -*- coding: utf-8 -*-
"""Scénarios prédéfinis sur les TEI Stylesheets (V0.9.2.2), exécutés par
Saxon sur le jeu d'essai « sermons » ; tests ignorés sans Saxon.

La bibliothèque est celle des tests (tests/conftest.py), installée depuis
l'archive livrée. Les exécutions qui doivent prouver que le catalogue est
transmis passent par un processus de transformation neuf
(``run_in_process``) : le processeur Saxon d'un processus garde le dernier
catalogue reçu.
"""
from __future__ import annotations

import re
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from project_config import TransformScenario, load_project
from transform_worker import run_in_process
from xslt_engines import run
from xslt_scenarios import check_request, predefined_scenarios, saxon_available, scenario_request, tei_library

DATA = Path(__file__).resolve().parent / "data" / "sermons"
pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return load_project(root / "project.xml")


def _scenario(name, language="fr"):
    return next(scenario for scenario in predefined_scenarios(language=language) if scenario.name == name)


def test_the_html_scenario_publishes_the_edition_without_link_to_the_tei_c(project):
    result = run(scenario_request(_scenario("tei-html"), project))
    assert result.ok, result.error
    output = project.root_dir / "publications" / "tei" / "edition.html"
    html = output.read_text(encoding="utf-8")
    assert "Sermo in adventu Domini" in html and "Table des matières" in html        # lang : fr
    assert '<link href="tei.css" rel="stylesheet" type="text/css"/>' in html
    assert not [url for url in re.findall(r'(?:href|src)="([^"]*)"', html) if "tei-c.org" in url or url == "/"]
    assert (output.parent / "tei.css").read_bytes() == (tei_library().folder / "tei.css").read_bytes()
    assert ["library", f"TEI Stylesheets {tei_library().version}"] in result.journal


@pytest.mark.parametrize("name, extension, expected", [
    ("tei-txt", "txt", "Sermo in adventu Domini"),
    ("tei-markdown", "md", "# Sermo in adventu Domini"),
    ("tei-latex", "tex", "\\documentclass"),
])
def test_the_other_tei_scenarios(project, name, extension, expected):
    result = run(scenario_request(_scenario(name), project))
    assert result.ok, result.error
    output = project.root_dir / "publications" / "tei" / f"edition.{extension}"
    assert result.outputs == [str(output)]
    assert expected in output.read_text(encoding="utf-8")


# Les TEI Stylesheets écrivent du XHTML : les éléments ajoutés aussi (xmlns).
CUSTOMIZATION = '''<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns="http://www.w3.org/1999/xhtml" exclude-result-prefixes="#all">
  <xsl:import href="http://www.tei-c.org/release/xml/tei/stylesheet/profiles/default/html/to.xsl"/>
  <xsl:template match="tei:persName"><b class="perso"><xsl:apply-templates/></b></xsl:template>
</xsl:stylesheet>
'''


def test_a_customization_imports_the_official_stylesheets_from_the_library(project):
    path = project.root_dir / "xslt" / "perso.xsl"
    path.parent.mkdir()
    path.write_text(CUSTOMIZATION, encoding="utf-8")
    html_scenario = _scenario("tei-html")
    scenario = replace(html_scenario, name="Perso", xslt="xslt/perso.xsl", output="publications/perso.html")
    result = run_in_process(scenario_request(scenario, project), timeout=120)
    assert result.ok, result.error
    html = (project.root_dir / "publications" / "perso.html").read_text(encoding="utf-8")
    assert '<b class="perso">saint Bernard</b>' in html and "Table des matières" in html
    assert ["library", f"TEI Stylesheets {tei_library().version}"] in result.journal


def test_a_customization_is_checked_with_the_library(project):
    path = project.root_dir / "xslt" / "perso.xsl"
    path.parent.mkdir()
    path.write_text(CUSTOMIZATION, encoding="utf-8")
    result = run_in_process(check_request("saxon", path, CUSTOMIZATION), timeout=120)
    assert result.ok, result.error
    assert [issue for issue in result.issues if issue[2] == "error"] == []


def test_a_tei_scenario_reads_the_assembled_edition(project):
    # Les sermons sont des parties incluses (XInclude) : tous sont publiés.
    result = run(scenario_request(_scenario("tei-txt"), project))
    assert result.ok, result.error
    text = (project.root_dir / "publications" / "tei" / "edition.txt").read_text(encoding="utf-8")
    for title in ("Sermo in adventu Domini", "Sermo in nativitate Domini", "Sermo in die Paschae",
                  "Sermo in die Pentecostes"):
        assert title in text


def test_the_scenario_runs_with_a_project_scenario_too(project):
    # Un scénario du projet (dupliqué) qui emploie ${tei}/ directement.
    scenario = TransformScenario("Copie", "${tei}/profiles/default/markdown/to.xsl", "publications/copie.md",
                                 engine="saxon")
    result = run(scenario_request(scenario, project))
    assert result.ok, result.error
    assert (project.root_dir / "publications" / "copie.md").is_file()


@pytest.mark.parametrize("name", ["tei-html", "tei-txt", "tei-markdown", "tei-latex"])
def test_the_customization_stylesheet_of_each_tei_scenario_compiles_and_runs(project, name):
    from xslt_scenarios import customization_name, customization_text
    scenario = _scenario(name)
    path = project.root_dir / "xslt" / customization_name(scenario.xslt)
    path.parent.mkdir()
    text = customization_text(scenario.xslt, "Commentaire.", "Exemples :")
    path.write_text(text, encoding="utf-8")
    assert run_in_process(check_request("saxon", path, text), timeout=120).ok
    # Sans rien d'autre que l'import, elle donne le même résultat que la feuille du TEI-C.
    result = run(scenario_request(replace(scenario, xslt=f"xslt/{path.name}", output=scenario.output + ".perso"),
                                  project))
    assert result.ok, result.error
    output = project.root_dir / scenario.output
    run(scenario_request(scenario, project))
    # Date, heure et identifiants générés (generate-id) changent d'une exécution à l'autre.
    stamp = re.compile(r"\d{4}-\d\d-\d\dT[\d:.]+Z?|Generated from [^\n]*|\d{4}-\d\d-\d\d|d\d+e\d+")
    assert stamp.sub("", Path(str(output) + ".perso").read_text(encoding="utf-8")) == \
        stamp.sub("", output.read_text(encoding="utf-8"))
