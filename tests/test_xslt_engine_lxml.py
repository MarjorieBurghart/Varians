# -*- coding: utf-8 -*-
"""Moteur XSLT 1.0 des scénarios (xslt_engines, lxml), sans Qt.

Jeu d'essai : « sermons » (tests/data/sermons). Les lectures réseau passent
par un petit serveur http local.
"""
from __future__ import annotations

import functools
import http.server
import json
import shutil
import threading
from dataclasses import replace
from pathlib import Path

import pytest

from project_config import TransformScenario, load_project
from xslt_engines import TransformResult, run
from xslt_scenarios import scenario_request

DATA = Path(__file__).resolve().parent / "data" / "sermons"
XSL_HEAD = ('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
            ' xmlns:tei="http://www.tei-c.org/ns/1.0">\n')


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    return load_project(root / "project.xml")


def _stylesheet(project, body, name="essai.xsl", head=XSL_HEAD):
    path = project.root_dir / "rendering" / name
    path.write_text(head + body + "\n</xsl:stylesheet>\n", encoding="utf-8")
    return "rendering/" + name


def _run(project, body, **changes):
    scenario = TransformScenario("Essai", _stylesheet(project, body), "publications/essai.html", **changes)
    return run(scenario_request(scenario, project)), project.root_dir / "publications" / "essai.html"


# --- Sources ------------------------------------------------------------------------------

def test_a_file_is_read_with_its_base_uri(project):
    # document() relatif à un nœud de la source : depuis xml/personnes.xml.
    result, output = _run(project, '<xsl:template match="/"><r n="{count(document(\'edition.xml\', /)/*)}"/>'
                                   '</xsl:template>', source="file", file="xml/personnes.xml")
    assert result.ok, result.error
    assert result.outputs == [str(output)]
    assert 'n="1"' in output.read_text(encoding="utf-8")


def test_the_assembled_edition_keeps_the_base_uri_of_each_part(project):
    # Les @ref de l'édition (personnes.xml#…) et des parties (../personnes.xml#…)
    # sont relatifs chacun à son fichier.
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:for-each select="//tei:persName[@ref]">'
                                   '<xsl:value-of select="count(document(substring-before(@ref, \'#\'), .)/*)"/>'
                                   '</xsl:for-each></xsl:template>')
    assert result.ok, result.error
    counts = output.read_text(encoding="utf-8")
    assert len(counts) >= 3 and set(counts) == {"1"}


def test_external_entities_of_the_source_are_not_resolved(project):
    secret = project.root_dir / "secret.txt"
    secret.write_text("SECRET", encoding="utf-8")
    source = project.root_dir / "xml" / "entite.xml"
    source.write_text('<!DOCTYPE a [<!ENTITY x SYSTEM "../secret.txt">]><a>&x;</a>', encoding="utf-8")
    result, output = _run(project, '<xsl:output method="text"/><xsl:template match="/">'
                                   '<xsl:value-of select="."/></xsl:template>', source="file", file="xml/entite.xml")
    assert result.ok, result.error
    assert "SECRET" not in output.read_text(encoding="utf-8")


def test_a_malformed_source_is_reported_with_its_line(project):
    (project.root_dir / "xml" / "casse.xml").write_text("<a>\n<b>\n</a>", encoding="utf-8")
    result, output = _run(project, '<xsl:template match="/"><r/></xsl:template>', source="file", file="xml/casse.xml")
    assert not result.ok and result.error_code == "source_malformed"
    assert "casse.xml:3" in result.error
    assert not output.exists()


# --- Feuille, paramètres, journal -----------------------------------------------------------

def test_parameters_are_passed_as_strings(project):
    result, output = _run(project, '<xsl:param name="titre"/><xsl:param name="calcul"/>'
                                   '<xsl:template match="/"><r t="{$titre}" c="{$calcul}"/></xsl:template>',
                          params=(("titre", "L'index « A »"), ("calcul", "1 + 1")))
    assert result.ok, result.error
    from lxml import etree
    written = etree.fromstring(output.read_bytes())
    assert (written.get("t"), written.get("c")) == ("L'index « A »", "1 + 1")          # une chaîne, pas une expression


def test_messages_are_kept_in_the_journal(project):
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>bonjour</xsl:message><r/></xsl:template>')
    assert result.ok, result.error
    assert ["message", "bonjour"] in result.journal
    assert result.engine == "lxml" and "libxslt" in result.version and result.seconds >= 0


def test_the_messages_before_a_failure_stay_in_the_journal(project):
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>avant</xsl:message>'
                                    '<xsl:message terminate="yes">arrêt</xsl:message></xsl:template>')
    assert not result.ok and result.error == "essai.xsl: arrêt"
    assert result.journal == [["message", "avant"]]


def test_an_error_of_the_stylesheet_is_reported_with_its_line(project):
    result, output = _run(project, '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>')
    assert not result.ok and result.error_code == "xslt_invalid"
    assert "essai.xsl:3" in result.error
    assert not output.exists()


def test_a_failed_run_keeps_the_previous_result(project):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:template match="/"><xsl:message terminate="yes">arrêt</xsl:message>'
                                    '</xsl:template>')
    assert not result.ok and result.error_code == "transform_failed"
    assert "arrêt" in result.error
    assert output.read_text(encoding="utf-8") == "ancien"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]       # aucun fichier temporaire


def test_the_result_replaces_the_previous_one(project):
    output = project.root_dir / "publications" / "essai.html"
    output.parent.mkdir()
    output.write_text("ancien", encoding="utf-8")
    result, _output = _run(project, '<xsl:output method="text"/><xsl:template match="/">nouveau</xsl:template>')
    assert result.ok, result.error
    assert output.read_text(encoding="utf-8") == "nouveau"
    assert sorted(p.name for p in output.parent.iterdir()) == ["essai.html"]


def test_a_stylesheet_may_not_write_other_files(project):
    head = XSL_HEAD.replace(">\n", ' xmlns:exsl="http://exslt.org/common" extension-element-prefixes="exsl">\n', 1)
    scenario = TransformScenario("Essai", _stylesheet(project, '<xsl:template match="/"><exsl:document href="autre.html">'
                                                                '<x/></exsl:document><r/></xsl:template>', head=head),
                                 "publications/essai.html")
    result = run(scenario_request(scenario, project))
    assert not result.ok and result.error_code == "write_refused"
    assert "autre.html" in result.error
    assert not (project.root_dir / "publications").exists()
    assert not (project.root_dir / "rendering" / "autre.html").exists()


# --- Réseau -----------------------------------------------------------------------------------

@pytest.fixture
def server(tmp_path):
    folder = tmp_path / "www"
    folder.mkdir()
    (folder / "distant.xml").write_text("<distant>du serveur</distant>", encoding="utf-8")
    (folder / "commun.xsl").write_text(XSL_HEAD + '<xsl:template name="commun"><importe/></xsl:template>'
                                       '\n</xsl:stylesheet>', encoding="utf-8")
    handler = functools.partial(_QuietHandler, directory=str(folder))
    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{httpd.server_port}/"
    httpd.shutdown()
    httpd.server_close()


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def test_a_stylesheet_may_read_from_the_network(project, server):
    result, output = _run(project, f'<xsl:import href="{server}commun.xsl"/><xsl:template match="/"><r>'
                                   f'<xsl:call-template name="commun"/><xsl:copy-of select="document(\'{server}distant.xml\')"/>'
                                   '</r></xsl:template>')
    assert result.ok, result.error
    text = output.read_text(encoding="utf-8")
    assert "<importe" in text and "du serveur" in text
    assert ["network_read", server + "commun.xsl"] in result.journal
    assert ["network_read", server + "distant.xml"] in result.journal


def test_a_failed_network_read_stops_the_run(project, server):
    result, output = _run(project, f'<xsl:template match="/"><r n="{{count(document(\'{server}absent.xml\'))}}"/>'
                                   '</xsl:template>')
    assert not result.ok and result.error_code == "network_failed"
    assert server + "absent.xml" in result.error
    assert not output.exists()


# --- CSS ----------------------------------------------------------------------------------------

def test_the_css_is_copied_next_to_the_result_and_named_to_the_stylesheet_of_varians(project):
    css = project.root_dir / "rendering" / "perso.css"
    css.write_text("p { color: red }", encoding="utf-8")
    scenario = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                 css="rendering/perso.css")
    result = run(scenario_request(scenario, project))
    assert result.ok, result.error
    folder = project.root_dir / "publications"
    assert result.outputs == [str(folder / "edition.html"), str(folder / "perso.css")]
    assert (folder / "perso.css").read_text(encoding="utf-8") == "p { color: red }"
    assert 'href="perso.css"' in (folder / "edition.html").read_text(encoding="utf-8")
    assert ["css_copied", str(folder / "perso.css")] in result.journal


def test_the_stylesheet_of_varians_links_tei_css_by_default(project):
    scenario = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html")
    result = run(scenario_request(scenario, project))
    assert result.ok, result.error
    assert 'href="tei.css"' in (project.root_dir / "publications" / "edition.html").read_text(encoding="utf-8")


def test_the_css_never_overwrites_a_protected_file(project):
    # scenario_problems l'empêche déjà ; le moteur le vérifie encore.
    scenario = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "rendering/edition.html",
                                 css="${varians}/tei.css")
    before = (project.root_dir / "rendering" / "tei.css").read_bytes()
    result = run(scenario_request(scenario, project))
    assert result.ok, result.error
    assert (project.root_dir / "rendering" / "tei.css").read_bytes() == before
    assert ["write_refused", str(project.root_dir / "rendering" / "tei.css")] in result.journal
    assert result.outputs == [str(project.root_dir / "rendering" / "edition.html")]


# --- Résultat --------------------------------------------------------------------------------

def test_the_result_goes_through_json(project):
    result, _output = _run(project, '<xsl:template match="/"><xsl:message>m</xsl:message><r/></xsl:template>')
    assert TransformResult.from_dict(json.loads(json.dumps(result.to_dict()))) == result


def test_an_unknown_engine_is_refused(project):
    request = scenario_request(TransformScenario("Essai", _stylesheet(project, ""), "publications/essai.html"), project)
    result = run(dict(request, engine="xsltproc"))
    assert not result.ok and result.error_code == "unknown_engine"


def test_each_failure_and_journal_entry_has_a_message_in_the_seven_catalogs():
    import xml.etree.ElementTree as ET
    from xslt_engines import ERROR_CODES, JOURNAL_CODES
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        root = ET.parse(Path(__file__).resolve().parents[1] / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key") for string in root.findall("string")}
        assert {f"transform.error.{code}" for code in ERROR_CODES} <= catalog, language
        assert {f"transform.journal.{code}" for code in JOURNAL_CODES} <= catalog, language
