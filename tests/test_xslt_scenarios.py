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
    scenario = predefined_scenarios()[0]
    assert scenario == TransformScenario("varians-html", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                         css="${varians}/tei.css", params=(("tocTitle", "Contents"),))
    # Le nom et le titre du sommaire, dans la langue de l'interface.
    named = predefined_scenarios(lambda key: {"varians-html": "Édition", "toc": "Sommaire"}.get(key, key))[0]
    assert (named.name, named.params) == ("Édition", (("tocTitle", "Sommaire"),))
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

def test_the_pivot_witness_is_substituted_in_the_parameters(project):
    """V0.9.2.7 : ``${pivot}``, dans la valeur d'un paramètre, est le témoin
    pivot du projet au moment de l'exécution."""
    scenario = replace(BASE, params=(("temoin-de-base", "${pivot}"), ("titre", "Pivot ${pivot} !"), ("autre", "x")))
    params = scenario_request(scenario, project)["params"]
    pivot = project.base_witness
    assert pivot and params == [["temoin-de-base", pivot], ["titre", f"Pivot {pivot} !"], ["autre", "x"]]


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
    assert {"output_is_source", "tei_missing"} <= set(PROBLEM_CODES) and len(PROBLEM_CODES) == 14
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        root = ET.parse(Path(__file__).resolve().parents[1] / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key") for string in root.findall("string")}
        assert {f"transform.problem.{code}" for code in PROBLEM_CODES} <= catalog, language
        assert {f"transform.predefined.{scenario.name}" for scenario in predefined_scenarios()} <= catalog, language


# --- TEI Stylesheets (V0.9.2.2) ---------------------------------------------------------------
# La bibliothèque des tests est installée depuis l'archive livrée, dans un
# dossier temporaire commun à la session (tests/conftest.py).

TEI_OUTPUTS = {"tei-html": ("html", "html"), "tei-txt": ("txt", "txt"), "tei-markdown": ("markdown", "md"),
               "tei-latex": ("latex", "tex")}


@pytest.fixture
def no_tei(tmp_path, monkeypatch):
    """Aucune version installée, et aucune archive livrée à installer."""
    import tei_stylesheets
    monkeypatch.setenv("VARIANS_TEI_STYLESHEETS", str(tmp_path / "bibliotheque-vide"))
    monkeypatch.setattr(tei_stylesheets, "BUNDLED_DIR", tmp_path / "sans-archive")
    return tei_stylesheets.library_dir()


def test_tei_paths_designate_the_active_version(project, tmp_path):
    from tei_stylesheets import library_dir
    from xslt_scenarios import TEI_PREFIX, scenario_path, tei_library
    library = tei_library()                               # installée au premier usage
    assert TEI_PREFIX == "${tei}/" and library is not None and library.source == "bundled"
    folder = library.folder.resolve()
    assert resolve_path(project, "${tei}/profiles/default/html/to.xsl") == folder / "profiles" / "default" / "html" / "to.xsl"
    assert scenario_path(project, folder / "tei.css") == "${tei}/tei.css"
    # Un fichier d'une autre version installée désigne celui de la version active.
    assert scenario_path(project, library_dir() / "7.0.0" / "tei.css") == "${tei}/tei.css"
    assert scenario_path(project, library_dir() / "notes.xsl") == (library_dir() / "notes.xsl").resolve().as_posix()


def test_the_tei_scenarios_are_predefined(project):
    scenarios = predefined_scenarios()
    assert [scenario.name for scenario in scenarios] == ["varians-html", *TEI_OUTPUTS]
    for scenario in scenarios[1:]:
        folder, extension = TEI_OUTPUTS[scenario.name]
        assert scenario.xslt == f"${{tei}}/profiles/default/{folder}/to.xsl"
        # Dans un dossier à part : leur CSS (tei.css) ne remplace pas celle de Varians.
        assert scenario.output == f"publications/tei/edition.{extension}"
        assert (scenario.source, scenario.engine) == ("edition", "saxon")
        assert stylesheet_path(scenario, project).is_file()
        assert scenario_problems(scenario, project) == []
    html = scenarios[1]
    # La CSS des TEI Stylesheets, copiée à côté du résultat : aucun lien vers tei-c.org.
    assert html.css == "${tei}/tei.css"
    assert html.params == (("cssFile", "tei.css"), ("cssPrintFile", ""), ("homeURL", ""))
    assert scenarios[2].css == "" and scenarios[2].params == ()
    # Les deux éditions HTML ne copient pas leur CSS au même endroit.
    copies = [resolve_path(project, s.output).parent / resolve_path(project, s.css).name for s in scenarios if s.css]
    assert len(copies) == len(set(copies)) == 2


def test_the_tei_scenarios_speak_the_language_of_the_interface():
    html = predefined_scenarios(language="fr")[1]
    assert html.params[-2:] == (("lang", "fr"), ("documentationLanguage", "fr"))
    assert predefined_scenarios(language="ja")[4].params == (("lang", "ja"), ("documentationLanguage", "ja"))
    names = [scenario.name for scenario in predefined_scenarios(lambda key: f"«{key}»", "fr")]
    assert names == ["«varians-html»", "«tei-html»", "«tei-txt»", "«tei-markdown»", "«tei-latex»"]


def test_without_tei_stylesheets_the_tei_scenarios_report_it(project, no_tei):
    from xslt_scenarios import ScenarioProblem, tei_library
    assert tei_library() is None
    varians, html, text = predefined_scenarios()[:3]
    assert scenario_problems(html, project) == [ScenarioProblem("tei_missing", str(no_tei))]
    assert scenario_problems(text, project) == [ScenarioProblem("tei_missing", str(no_tei))]
    assert scenario_problems(varians, project) == []


def _customization(project, imported="profiles/default/html/to.xsl"):
    path = project.root_dir / "xslt" / "perso.xsl"
    path.parent.mkdir(exist_ok=True)
    path.write_text('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
                    f'  <xsl:import href="http://www.tei-c.org/release/xml/tei/stylesheet/{imported}"/>\n'
                    '</xsl:stylesheet>\n', encoding="utf-8")
    return path


def test_a_saxon_request_carries_the_catalog_of_the_tei_stylesheets(project):
    from xslt_scenarios import tei_library
    library = tei_library()
    label = f"TEI Stylesheets {library.version}"
    request = scenario_request(predefined_scenarios()[1], project)
    assert request["catalogs"] == [str(library.catalog)] and request["library"] == label
    assert request["xslt"] == str((library.folder / "profiles" / "default" / "html" / "to.xsl").resolve())
    assert request["css"] == str((library.folder / "tei.css").resolve())
    # Une feuille de personnalisation, qui importe l'adresse officielle.
    _customization(project)
    custom = scenario_request(replace(BASE, xslt="xslt/perso.xsl", engine="saxon"), project)
    assert custom["catalogs"] == [str(library.catalog)] and custom["library"] == label
    # Toute feuille XSLT 3.0 reçoit le catalogue ; le journal ne nomme la
    # bibliothèque que si la feuille l'emploie.
    other = scenario_request(replace(BASE, engine="saxon"), project)
    assert other["catalogs"] == [str(library.catalog)] and "library" not in other
    assert "catalogs" not in scenario_request(BASE, project)                     # lxml


def test_without_tei_stylesheets_a_request_has_no_catalog(project, no_tei):
    request = scenario_request(replace(BASE, engine="saxon"), project)
    assert "catalogs" not in request and "library" not in request


def test_a_check_request_carries_the_catalog_for_saxon(project):
    from xslt_scenarios import check_request, tei_library
    path = _customization(project)
    assert check_request("saxon", path, "<x/>") == {"op": "check", "engine": "saxon", "xslt": str(path),
                                                    "text": "<x/>", "catalogs": [str(tei_library().catalog)]}
    assert check_request("lxml", path, None) == {"op": "check", "engine": "lxml", "xslt": str(path), "text": None}


# --- Feuille de personnalisation (V0.9.2.2) ---------------------------------------------------

@pytest.mark.parametrize("raw, name", [
    ("${tei}/profiles/default/html/to.xsl", "tei-html.xsl"),
    ("${tei}/profiles/default/latex/to.xsl", "tei-latex.xsl"),
    ("${tei}/profiles/enrich/docx/to.xsl", "tei-enrich-docx.xsl"),
    ("${tei}/html/html.xsl", "tei-html.xsl"),
])
def test_a_customization_is_named_after_the_profile(raw, name):
    from xslt_scenarios import customization_name
    assert customization_name(raw) == name


def test_a_customization_imports_the_official_address_of_the_stylesheet():
    from lxml import etree
    from tei_stylesheets import OFFICIAL_URI
    from xslt_scenarios import XSL_NAMESPACE, StylesheetInfo, customization_text, stylesheet_info
    text = customization_text("${tei}/profiles/default/html/to.xsl", "Ma feuille -- à moi.\n\nSecond paragraphe.",
                              "Exemples :")
    root = etree.fromstring(text.encode("utf-8"))
    assert stylesheet_info(text) == StylesheetInfo("xsl", "3.0", "xsl:stylesheet")
    assert [i.get("href") for i in root.iter(f"{{{XSL_NAMESPACE}}}import")] == [
        OFFICIAL_URI + "profiles/default/html/to.xsl"]
    # Une sortie HTML : les éléments ajoutés sont du XHTML, comme ceux des TEI Stylesheets.
    assert root.nsmap[None] == "http://www.w3.org/1999/xhtml"
    assert len(root) == 1                                              # rien d'autre que l'import
    comment = root.getprevious()
    assert isinstance(comment, etree._Comment) and "--" not in comment.text
    assert "Ma feuille" in comment.text and "Second paragraphe." in comment.text and "Exemples :" in comment.text
    assert '<xsl:param name="numberHeadings">false</xsl:param>' in comment.text
    assert "<b><xsl:apply-templates/></b>" in comment.text
    latex = etree.fromstring(customization_text("${tei}/profiles/default/latex/to.xsl").encode("utf-8"))
    assert None not in latex.nsmap and "<b>" not in latex.getprevious().text


def test_the_comment_of_a_customization_is_wrapped_by_display_width():
    import unicodedata
    from xslt_scenarios import customization_text
    japanese = "TEI Consortium のスタイルシート profiles/default/latex/to.xsl をインポートします。" * 4
    text = customization_text("${tei}/profiles/default/latex/to.xsl", japanese, "例：")
    lines = text.split("<!--", 1)[1].split("-->", 1)[0].splitlines()

    def width(line):
        return sum(2 if unicodedata.east_asian_width(c) in "WF" else 1 for c in line)

    assert lines[1].startswith("  TEI Consortium のスタイルシート")
    assert all(width(line) <= 78 for line in lines if "xsl:" not in line)
    assert not [line for line in lines if line.strip().startswith(("。", "、"))]
    assert "".join(line.strip() for line in lines[1:-4]).replace(" ", "") == japanese.replace(" ", "")
