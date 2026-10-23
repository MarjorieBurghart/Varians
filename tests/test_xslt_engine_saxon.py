# -*- coding: utf-8 -*-
"""Moteur XSLT 3.0 des scénarios (xslt_engines, Saxon), sans Qt.

Jeu d'essai : « sermons » (tests/data/sermons). Saxon garde le verrou de
Python pendant une transformation : le serveur http des lectures réseau
tourne donc dans un autre processus. Tests ignorés sans Saxon, sauf celui du
message « Saxon n'est pas installé ».
"""
from __future__ import annotations

import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

from project_config import TransformScenario, load_project
from xslt_engines import run
from xslt_scenarios import saxon_available, scenario_request

DATA = Path(__file__).resolve().parent / "data" / "sermons"
XSL_HEAD = ('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
            ' xmlns:tei="http://www.tei-c.org/ns/1.0" xmlns:xs="http://www.w3.org/2001/XMLSchema"'
            ' exclude-result-prefixes="#all">\n')
saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return load_project(root / "project.xml")


def _stylesheet(project, body, name="essai.xsl"):
    path = project.root_dir / "rendering" / name
    path.write_text(XSL_HEAD + body + "\n</xsl:stylesheet>\n", encoding="utf-8")
    return "rendering/" + name


def _run(project, body, output="publications/essai.html", **changes):
    scenario = TransformScenario("Essai", _stylesheet(project, body), output, engine="saxon", **changes)
    return run(scenario_request(scenario, project)), project.root_dir / output


def test_without_saxon_a_saxon_scenario_is_refused(project, monkeypatch):
    import xslt_engines
    monkeypatch.setitem(sys.modules, "saxonche", None)              # import saxonche → ImportError
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    result, output = _run(project, '<xsl:template match="/"><r/></xsl:template>')
    assert not result.ok and result.error_code == "saxon_missing"
    assert not output.exists()


# --- Sources ------------------------------------------------------------------------------

@saxon
def test_a_file_is_read_with_its_base_uri(project):
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="upper-case(local-name(document(\'edition.xml\', /)/*))"/>'
                                   '</xsl:template>', source="file", file="xml/personnes.xml")
    assert result.ok, result.error
    assert result.outputs == [str(output)]
    assert output.read_text(encoding="utf-8") == "TEI"
    assert result.engine == "saxon" and result.version.startswith("SaxonC")


@saxon
def test_the_assembled_edition_keeps_the_base_uri_of_each_part(project):
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="//tei:persName[@ref]!count(document(substring-before'
                                   '(@ref, \'#\'), .)/*)" separator=""/></xsl:template>')
    assert result.ok, result.error
    counts = output.read_text(encoding="utf-8")
    assert len(counts) >= 3 and set(counts) == {"1"}


@saxon
def test_external_entities_of_the_source_are_not_resolved(project):
    (project.root_dir / "secret.txt").write_text("SECRET", encoding="utf-8")
    (project.root_dir / "xml" / "entite.xml").write_text(
        '<!DOCTYPE a [<!ENTITY x SYSTEM "../secret.txt">]><a>&x;</a>', encoding="utf-8")
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="."/></xsl:template>', source="file", file="xml/entite.xml")
    assert result.ok, result.error
    assert "SECRET" not in output.read_text(encoding="utf-8")


@saxon
def test_a_malformed_source_is_reported_with_its_line(project):
    (project.root_dir / "xml" / "casse.xml").write_text("<a>\n<b>\n</a>", encoding="utf-8")
    result, output = _run(project, '<xsl:template match="/"><r/></xsl:template>', source="file", file="xml/casse.xml")
    assert not result.ok and result.error_code == "source_malformed"
    assert "casse.xml:3" in result.error
    assert not output.exists()


# --- Feuille, paramètres, journal -----------------------------------------------------------

@saxon
def test_parameters_are_passed_as_strings(project):
    result, output = _run(project, '<xsl:param name="titre"/><xsl:param name="calcul"/>'
                                   '<xsl:template match="/"><r t="{$titre}" c="{$calcul}"/></xsl:template>',
                          params=(("titre", "L'index « A »"), ("calcul", "1 + 1")))
    assert result.ok, result.error
    text = output.read_text(encoding="utf-8")
    assert "L'index « A »" in text and 'c="1 + 1"' in text


@saxon
def test_messages_are_kept_in_the_journal_even_before_a_failure(project):
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>bonjour</xsl:message><r/></xsl:template>')
    assert result.ok, result.error
    assert ["message", "bonjour"] in result.journal
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>avant</xsl:message>\n'
                                    '<xsl:message terminate="yes">arrêt</xsl:message></xsl:template>')
    assert not result.ok and result.error_code == "transform_failed"
    assert result.error.startswith("essai.xsl:3:")
    assert ["message", "avant"] in result.journal


@saxon
def test_an_error_of_the_stylesheet_is_reported_with_its_line(project):
    result, output = _run(project, '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>')
    assert not result.ok and result.error_code == "xslt_invalid"
    assert result.error.startswith("essai.xsl:3: XPST0003")
    assert not output.exists()


@saxon
def test_a_runtime_error_is_reported_with_its_line(project):
    result, output = _run(project, '<xsl:template match="/">\n<r><xsl:value-of select="xs:integer(\'abc\')"/></r>\n'
                                   '</xsl:template>')
    assert not result.ok and result.error_code == "transform_failed"
    assert result.error.startswith("essai.xsl:3: FORG0001")
    assert not output.exists()


@saxon
def test_a_failed_run_keeps_the_previous_result(project):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:template match="/"><xsl:message terminate="yes">arrêt</xsl:message>'
                                    '</xsl:template>')
    assert not result.ok
    assert output.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]


# --- Plusieurs fichiers ------------------------------------------------------------------------

PAGES = ('<xsl:template match="/">'
         '<xsl:result-document href="pages/p1.html" method="html" html-version="5">'
         '<html><head><title>p1</title></head><body>été<br/></body></html></xsl:result-document>'
         '<xsl:result-document href="liste.txt" method="text">ligne</xsl:result-document>'
         '<html><body>sommaire</body></html></xsl:template>')


@saxon
def test_other_files_are_written_in_the_folder_of_the_result_as_the_stylesheet_says(project):
    result, output = _run(project, PAGES)
    assert result.ok, result.error
    folder = output.parent
    assert result.outputs == [str(output), str(folder / "liste.txt"), str(folder / "pages" / "p1.html")]
    page = (folder / "pages" / "p1.html").read_text(encoding="utf-8")
    assert page.startswith("<!DOCTYPE HTML>") and "<br>" in page and "été" in page      # méthode html
    assert (folder / "liste.txt").read_text(encoding="utf-8") == "ligne"
    assert sorted(p.name for p in folder.iterdir()) == ["essai.html", "liste.txt", "pages"]


@saxon
@pytest.mark.parametrize("href", ["../ailleurs.html", "{resolve-uri('/tmp/varians-ailleurs.html')}"])
def test_a_file_outside_the_folder_of_the_result_is_refused_and_nothing_is_written(project, href):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:template match="/">'
                                    f'<xsl:result-document href="{href}"><x/></xsl:result-document>'
                                    '<xsl:result-document href="dedans.html"><x/></xsl:result-document>'
                                    '<r/></xsl:template>')
    assert not result.ok and result.error_code == "write_refused"
    assert "ailleurs.html" in result.error
    assert output.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]
    assert not (project.root_dir / "ailleurs.html").exists()
    assert not Path("/tmp/varians-ailleurs.html").exists()


@saxon
def test_another_file_never_overwrites_a_source_of_the_project(project):
    before = (project.root_dir / "rendering" / "tei.css").read_bytes()
    result, output = _run(project, '<xsl:template match="/"><xsl:result-document href="tei.css" method="text">'
                                   'écrasé</xsl:result-document><r/></xsl:template>', output="rendering/essai.html")
    assert result.ok, result.error
    assert (project.root_dir / "rendering" / "tei.css").read_bytes() == before
    assert ["write_refused", str(project.root_dir / "rendering" / "tei.css")] in result.journal
    assert result.outputs == [str(output)]


# --- Réseau -----------------------------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    folder = tmp_path / "www"
    folder.mkdir()
    (folder / "distant.xml").write_text("<distant>du serveur</distant>", encoding="utf-8")
    (folder / "commun.xsl").write_text(XSL_HEAD + '<xsl:template name="commun"><importe/></xsl:template>'
                                       '\n</xsl:stylesheet>', encoding="utf-8")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = probe.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "http.server", str(port), "--bind", "127.0.0.1",
                                "--directory", str(folder)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        with socket.socket() as attempt:
            if attempt.connect_ex(("127.0.0.1", port)) == 0:
                break
        time.sleep(0.05)
    yield f"http://127.0.0.1:{port}/"
    process.terminate()
    process.wait(timeout=10)


@saxon
def test_a_stylesheet_may_read_from_the_network(project, server):
    result, output = _run(project, f'<xsl:import href="{server}commun.xsl"/><xsl:template match="/"><r>'
                                   f'<xsl:call-template name="commun"/><xsl:copy-of select="doc(\'{server}distant.xml\')"/>'
                                   '</r></xsl:template>')
    assert result.ok, result.error
    text = output.read_text(encoding="utf-8")
    assert "<importe" in text and "du serveur" in text


@saxon
def test_a_failed_network_read_stops_the_run(project, server):
    result, output = _run(project, f'<xsl:template match="/"><r n="{{count(doc(\'{server}absent.xml\'))}}"/>'
                                   '</xsl:template>')
    assert not result.ok and result.error_code == "network_failed"
    assert server + "absent.xml" in result.error
    assert not output.exists()


# --- CSS -----------------------------------------------------------------------------------------

@saxon
def test_the_css_is_copied_and_named_to_the_stylesheet_of_varians(project):
    css = project.root_dir / "rendering" / "perso.css"
    css.write_text("p { color: red }", encoding="utf-8")
    scenario = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                 engine="saxon", css="rendering/perso.css")
    result = run(scenario_request(scenario, project))
    assert result.ok, result.error
    folder = project.root_dir / "publications"
    assert result.outputs == [str(folder / "edition.html"), str(folder / "perso.css")]
    assert 'href="perso.css"' in (folder / "edition.html").read_text(encoding="utf-8")
