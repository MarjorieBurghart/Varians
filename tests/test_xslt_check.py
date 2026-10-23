# -*- coding: utf-8 -*-
"""Vérification d'une feuille XSLT (V0.9.2.1), sans Qt : compilation par
lxml ou Saxon, sans exécution, du texte de l'éditeur même non enregistré ;
toutes les erreurs avec leur ligne ; choix du moteur.

Saxon passe par le processus de transformation (``run_in_process``), comme
dans Varians : sa sortie d'erreur y est un fichier, où il écrit le lieu de
ses erreurs sous Windows.
"""
from __future__ import annotations

import json
import shutil
from dataclasses import replace
from pathlib import Path

import pytest

from project_config import TransformScenario, load_project
from transform_worker import run_in_process
from xslt_engines import TransformResult, check
from xslt_scenarios import check_engines, saxon_available, stylesheet_info

DATA = Path(__file__).resolve().parent / "data" / "sermons"
saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


def _head(version):
    return (f'<xsl:stylesheet version="{version}" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
            ' xmlns:tei="http://www.tei-c.org/ns/1.0">\n')


def _stylesheet(folder, body, name="essai.xsl", version="1.0"):
    path = Path(folder) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_head(version) + body + "</xsl:stylesheet>\n", encoding="utf-8")
    return path


def _check(engine, path, text=None):
    request = {"op": "check", "engine": engine, "xslt": str(path)}
    if text is not None:
        request["text"] = text
    return run_in_process(request) if engine == "saxon" else check(request)


ENGINES = ["lxml", pytest.param("saxon", marks=saxon)]


# --- Ce qu'est une feuille --------------------------------------------------------------------

@pytest.mark.parametrize("text, prefix, version", [
    ('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"/>', "xsl", "1.0"),
    ("<?xml version='1.0'?>\n<!-- c -->\n<x:transform xmlns:x='http://www.w3.org/1999/XSL/Transform'\n"
     "  version='3.0'>", "x", "3.0"),
    ('<stylesheet xmlns="http://www.w3.org/1999/XSL/Transform" version="2.0">', "", "2.0"),
    ('<xsl:package name="p" package-version="1" version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">',
     "xsl", "3.0"),
    ('<html xsl:version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"><body/></html>', "xsl", "1.0"),
    ('<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform">', "xsl", ""),
])
def test_a_stylesheet_is_known_by_its_root(text, prefix, version):
    info = stylesheet_info(text)
    assert info is not None and (info.prefix, info.version) == (prefix, version)


@pytest.mark.parametrize("text", [
    '<TEI xmlns="http://www.tei-c.org/ns/1.0"/>',
    '<xsl:stylesheet xmlns:xsl="http://example.org/autre" version="1.0"/>',
    '<html xmlns:xsl="http://www.w3.org/1999/XSL/Transform"><body/></html>',      # sans xsl:version
    "",
    "<",
])
def test_other_documents_are_not_stylesheets(text):
    assert stylesheet_info(text) is None


# --- Moteur de la vérification ----------------------------------------------------------------

@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return load_project(root / "project.xml")


def test_the_engines_are_those_of_the_scenarios_that_use_the_stylesheet(project):
    path = _stylesheet(project.root_dir / "xslt", "", version="3.0")
    other = _stylesheet(project.root_dir / "xslt", "", name="autre.xsl")
    project = replace(project, transformations=(
        TransformScenario("A", "xslt/essai.xsl", "publications/a.html", engine="saxon"),
        TransformScenario("B", "xslt/autre.xsl", "publications/b.html", engine="saxon"),
        TransformScenario("C", str(path), "publications/c.html", engine="lxml"),
        TransformScenario("D", "xslt/essai.xsl", "publications/d.html", engine="saxon"),
    ))
    assert check_engines(path, project, path.read_text(encoding="utf-8")) == ("saxon", "lxml")
    assert check_engines(other, project, other.read_text(encoding="utf-8")) == ("saxon",)


@pytest.mark.parametrize("version, engines", [("1.0", ("lxml",)), ("2.0", ("saxon",)), ("3.0", ("saxon",)),
                                              ("", ("saxon",))])
def test_without_scenario_the_engine_follows_the_version(project, version, engines):
    path = project.root_dir / "xslt" / "seule.xsl"
    text = _head(version).replace(' version=""', "") + "</xsl:stylesheet>"
    assert check_engines(path, project, text) == engines


def test_an_unknown_engine_of_a_scenario_is_ignored(project):
    path = _stylesheet(project.root_dir / "xslt", "")
    project = replace(project, transformations=(
        TransformScenario("A", "xslt/essai.xsl", "publications/a.html", engine="xsltproc"),))
    assert check_engines(path, project, path.read_text(encoding="utf-8")) == ("lxml",)


# --- Compilation ------------------------------------------------------------------------------

@pytest.mark.parametrize("engine", ENGINES)
def test_a_correct_stylesheet_has_no_issue(tmp_path, engine):
    path = _stylesheet(tmp_path, '<xsl:template match="/"><r><xsl:value-of select="count(//tei:p)"/></r>'
                                 '</xsl:template>\n', version="1.0" if engine == "lxml" else "3.0")
    result = _check(engine, path)
    assert result.ok, result.issues
    assert result.issues == [] and result.engine == engine and result.version


@pytest.mark.parametrize("engine", ENGINES)
def test_every_error_is_reported_with_its_line(tmp_path, engine):
    version = "1.0" if engine == "lxml" else "3.0"
    path = _stylesheet(tmp_path, '<xsl:template match="/">\n'           # ligne 2
                                 '<xsl:value-of select="(("/>\n'         # ligne 3
                                 '<r/>\n'
                                 '<xsl:apply-templates select="]"/>\n'   # ligne 5
                                 '</xsl:template>\n', version=version)
    result = _check(engine, path)
    assert not result.ok and result.error_code == "xslt_invalid"
    errors = [issue for issue in result.issues if issue[2] == "error"]
    assert [(Path(file), line) for file, line, _level, _message in errors] == [(path, 3), (path, 5)]
    assert all(message for _file, _line, _level, message in errors)
    assert "((" in errors[0][3] or "XPST0003" in errors[0][3]
    assert result.error.startswith("essai.xsl:3: ")


@pytest.mark.parametrize("engine", ENGINES)
def test_the_text_of_the_editor_is_checked_rather_than_the_file(tmp_path, engine):
    version = "1.0" if engine == "lxml" else "3.0"
    path = _stylesheet(tmp_path, '<xsl:template match="/"><r/></xsl:template>\n', version=version)
    text = _head(version) + '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>\n' \
                            "</xsl:stylesheet>\n"
    result = _check(engine, path, text)
    assert not result.ok
    assert [(Path(f), line) for f, line, level, _m in result.issues if level == "error"] == [(path, 3)]
    assert _check(engine, path).ok


@pytest.mark.parametrize("engine", ENGINES)
def test_relative_imports_are_read_from_the_folder_of_the_stylesheet(tmp_path, engine):
    version = "1.0" if engine == "lxml" else "3.0"
    _stylesheet(tmp_path / "lib", '<xsl:template name="commun"><c/></xsl:template>\n', name="commun.xsl",
                version=version)
    path = tmp_path / "essai.xsl"
    text = _head(version) + '<xsl:import href="lib/commun.xsl"/>\n' \
                            '<xsl:template match="/"><xsl:call-template name="commun"/></xsl:template>\n' \
                            "</xsl:stylesheet>\n"
    result = _check(engine, path, text)                    # le fichier n'existe pas encore
    assert result.ok, result.issues


@pytest.mark.parametrize("engine", ENGINES)
def test_an_error_in_an_imported_stylesheet_names_its_file(tmp_path, engine):
    version = "1.0" if engine == "lxml" else "3.0"
    imported = _stylesheet(tmp_path, '<xsl:template name="commun">\n<xsl:value-of select="(("/>\n'
                                     '</xsl:template>\n', name="commun.xsl", version=version)
    path = _stylesheet(tmp_path, '<xsl:import href="commun.xsl"/>\n<xsl:template match="/"><r/></xsl:template>\n',
                       version=version)
    result = _check(engine, path)
    assert not result.ok
    assert [(Path(f), line) for f, line, level, _m in result.issues if level == "error"] == [(imported, 3)]


@pytest.mark.parametrize("engine", ENGINES)
def test_a_missing_import_is_an_error(tmp_path, engine):
    version = "1.0" if engine == "lxml" else "3.0"
    path = _stylesheet(tmp_path, '<xsl:import href="absente.xsl"/>\n<xsl:template match="/"><r/></xsl:template>\n',
                       version=version)
    result = _check(engine, path)
    assert not result.ok and result.error_code == "xslt_invalid"
    assert "absente.xsl" in " ".join(message for _f, _l, _level, message in result.issues)


@pytest.mark.parametrize("engine", ENGINES)
def test_a_malformed_stylesheet_is_reported_with_its_line(tmp_path, engine):
    path = tmp_path / "essai.xsl"
    text = _head("1.0") + '<xsl:template match="/">\n<r>\n</xsl:template>\n</xsl:stylesheet>\n'
    result = _check(engine, path, text)
    assert not result.ok and result.error_code == "xslt_malformed"
    ((file, line, level, _message),) = result.issues
    assert (Path(file), level) == (path, "error") and line in (4, 5)


@saxon
def test_saxon_reports_what_lxml_lets_through(tmp_path):
    # Un attribut inconnu sur un élément XSLT : lxml le laisse passer (une
    # feuille 3.0 n'a pour lui que des avertissements).
    path = _stylesheet(tmp_path, '<xsl:template match="/" mode2="x"><r/></xsl:template>\n', version="3.0")
    lxml = _check("lxml", path)
    assert lxml.ok and {level for _f, _l, level, _m in lxml.issues} <= {"warning"}
    result = _check("saxon", path)
    assert not result.ok
    ((file, line, level, message),) = result.issues
    assert (Path(file), line, level) == (path, 2, "error") and "XTSE0090" in message


def test_without_saxon_the_check_says_so(tmp_path, monkeypatch):
    import sys
    import xslt_engines
    monkeypatch.setitem(sys.modules, "saxonche", None)
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    path = _stylesheet(tmp_path, "", version="3.0")
    result = check({"op": "check", "engine": "saxon", "xslt": str(path)})
    assert not result.ok and result.error_code == "saxon_missing" and result.issues == []


def test_an_unknown_engine_is_refused(tmp_path):
    result = check({"op": "check", "engine": "xsltproc", "xslt": str(_stylesheet(tmp_path, ""))})
    assert not result.ok and result.error_code == "unknown_engine"


# --- Processus ----------------------------------------------------------------------------------

def test_the_worker_checks_without_running(tmp_path):
    path = _stylesheet(tmp_path, '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>\n')
    result = run_in_process({"op": "check", "engine": "lxml", "xslt": str(path)})
    assert not result.ok and [(Path(f), line) for f, line, _l, _m in result.issues] == [(path, 3)]
    assert result.outputs == []


def test_the_issues_go_through_json(tmp_path):
    path = _stylesheet(tmp_path, '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>\n')
    result = check({"op": "check", "engine": "lxml", "xslt": str(path)})
    assert result.issues
    assert TransformResult.from_dict(json.loads(json.dumps(result.to_dict()))) == result
