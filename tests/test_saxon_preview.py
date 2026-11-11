# -*- coding: utf-8 -*-
"""Processus d'aperçu Saxon (V0.9.4.4), sans Qt.

L'aperçu d'une vue en XSLT 2.0 ou 3.0 est fait par Saxon, dans un processus
à part qui reste ouvert (Varians relancé avec ``--preview-worker``) : la
fenêtre ne se fige pas, une feuille qui boucle ou un plantage de Saxon
n'emportent pas Varians, et les feuilles compilées sont gardées tant que
leur fichier ne change pas. Comme l'aperçu en 1.0 : fichiers locaux
seulement, rien n'est jamais écrit, paramètres sans type."""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

import pytest

from fragment_units import chosen_units, mark_units, place_edit_markers
from saxon_preview import PreviewError, SaxonPreviewClient, worker_command
from xslt_scenarios import saxon_available

ROOT = Path(__file__).resolve().parents[1]
TEI_NS = "http://www.tei-c.org/ns/1.0"
PERSONS = (f'<listPerson xmlns="{TEI_NS}"><person><persName>Bernardus</persName></person>'
           '<person><persName>Petrus</persName></person></listPerson>')

pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


@pytest.fixture
def client():
    worker = SaxonPreviewClient([sys.executable, str(ROOT / "saxon_preview.py")])
    yield worker
    worker.close()


def _sheet(tmp_path, body, name="vue.xsl", params=""):
    path = tmp_path / name
    path.write_text('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
                    f'xmlns:tei="{TEI_NS}" exclude-result-prefixes="#all"><xsl:output method="html"/>'
                    f'{params}{body}</xsl:stylesheet>', encoding="utf-8")
    return path


FICHES = ('<xsl:template match="/"><html><body><h1><xsl:value-of select="$titre"/></h1>'
          '<xsl:apply-templates select="//tei:person" mode="fiche"/></body></html></xsl:template>'
          '<xsl:template match="tei:person" mode="fiche"><p><xsl:value-of select="tei:persName"/></p></xsl:template>')


def test_a_3_0_view_is_transformed_with_its_parameters_and_pencils(client, tmp_path):
    sheet = _sheet(tmp_path, FICHES, params='<xsl:param name="titre"/>')
    marked, _spans = mark_units(PERSONS, chosen_units(("person",)))
    result = client.transform(marked, sheet, {"titre": "Index"}, base=tmp_path / "personnes.xml")
    html, count = place_edit_markers(result.html, "✎")
    assert "<h1>Index</h1>" in html and count == 2
    assert result.engine.startswith("Saxon")


def test_compiled_stylesheets_are_kept_until_their_file_changes(client, tmp_path):
    sheet = _sheet(tmp_path, FICHES, params='<xsl:param name="titre"/>')
    first = client.transform(PERSONS, sheet, {"titre": "Un"})
    second = client.transform(PERSONS, sheet, {"titre": "Deux"})
    assert first.compiled and not second.compiled
    assert "<h1>Deux</h1>" in second.html                                    # paramètres de chaque aperçu
    sheet.write_text(sheet.read_text(encoding="utf-8").replace("<h1>", "<h2>").replace("</h1>", "</h2>"),
                     encoding="utf-8")
    os.utime(sheet, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    third = client.transform(PERSONS, sheet, {"titre": "Trois"})
    assert third.compiled and "<h2>Trois</h2>" in third.html


def test_parameters_are_untyped(client, tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="/"><p><xsl:value-of select="$n + 1"/><xsl:text> </xsl:text>'
                             '<xsl:value-of select="if ($b) then \'oui\' else \'non\'"/></p></xsl:template>',
                   params='<xsl:param name="n" as="xs:integer"/><xsl:param name="b" as="xs:boolean"/>')
    sheet.write_text(sheet.read_text(encoding="utf-8").replace(
        'xmlns:tei=', 'xmlns:xs="http://www.w3.org/2001/XMLSchema" xmlns:tei='), encoding="utf-8")
    assert "<p>4 non</p>" in client.transform(PERSONS, sheet, {"n": "3", "b": "false"}).html


def test_the_document_keeps_its_place_for_relative_files(client, tmp_path):
    (tmp_path / "autorites.xml").write_text("<a>Clairvaux</a>", encoding="utf-8")
    sheet = _sheet(tmp_path, '<xsl:template match="/"><p><xsl:value-of select="doc(resolve-uri(\'autorites.xml\', '
                             'base-uri(/)))"/></p></xsl:template>')
    html = client.transform(PERSONS, sheet, {}, base=tmp_path / "personnes.xml").html
    assert "<p>Clairvaux</p>" in html


def test_nothing_is_written_and_the_network_is_not_read(client, tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="/"><xsl:result-document href="ailleurs.html"><p>non</p>'
                             '</xsl:result-document><p>aperçu</p></xsl:template>')
    html = client.transform(PERSONS, sheet, {}, base=tmp_path / "personnes.xml").html
    assert "<p>aperçu</p>" in html
    assert not (tmp_path / "ailleurs.html").exists()
    web = _sheet(tmp_path, '<xsl:template match="/"><p><xsl:value-of select="doc(\'http://example.invalid/a.xml\')"/>'
                           '</p></xsl:template>', name="web.xsl")
    with pytest.raises(PreviewError) as error:
        client.transform(PERSONS, web, {})
    assert error.value.code in ("network_failed", "transform_failed")
    assert "<p>aperçu</p>" in client.transform(PERSONS, sheet, {}).html            # le processus continue


def test_errors_say_where_they_are(client, tmp_path):
    broken = tmp_path / "cassee.xsl"
    broken.write_text('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
                      '<xsl:template match="/"><xsl:value-of select="1 +"/></xsl:template>\n'
                      '</xsl:stylesheet>', encoding="utf-8")
    with pytest.raises(PreviewError) as error:
        client.transform(PERSONS, broken, {})
    assert error.value.code == "xslt_invalid" and "cassee.xsl" in error.value.detail
    with pytest.raises(PreviewError) as error:
        client.transform("<listPerson>", _sheet(tmp_path, FICHES, params='<xsl:param name="titre"/>'), {})
    assert error.value.code == "source_malformed"
    missing = tmp_path / "absente.xsl"
    with pytest.raises(PreviewError) as error:
        client.transform(PERSONS, missing, {})
    assert error.value.code == "xslt_missing"


def test_a_stylesheet_that_never_ends_is_stopped(client, tmp_path):
    endless = _sheet(tmp_path, '<xsl:template match="/"><xsl:call-template name="boucle"/></xsl:template>'
                               '<xsl:template name="boucle"><xsl:param name="n" select="0"/>'
                               '<xsl:if test="$n &gt;= 0"><xsl:call-template name="boucle">'
                               '<xsl:with-param name="n" select="$n + 1"/></xsl:call-template></xsl:if></xsl:template>',
                     name="boucle.xsl")
    started = time.monotonic()
    with pytest.raises(PreviewError) as error:
        client.transform(PERSONS, endless, {}, timeout=3)
    assert error.value.code in ("timeout", "transform_failed")              # arrêté, ou débordement de pile
    assert time.monotonic() - started < 30
    sheet = _sheet(tmp_path, FICHES, params='<xsl:param name="titre"/>')
    assert "Bernardus" in client.transform(PERSONS, sheet, {"titre": "x"}).html   # relancé au besoin


def test_a_dead_process_is_started_again(client, tmp_path):
    sheet = _sheet(tmp_path, FICHES, params='<xsl:param name="titre"/>')
    assert "Petrus" in client.transform(PERSONS, sheet, {"titre": "x"}).html
    client._process.kill()
    client._process.wait()
    assert "Petrus" in client.transform(PERSONS, sheet, {"titre": "x"}).html


def test_the_process_is_varians_without_qt():
    worker = SaxonPreviewClient(worker_command())
    try:
        answer = worker.ping()
    finally:
        worker.close()
    assert answer["ok"] and not answer["qt_loaded"] and not answer["gui_loaded"]
    assert worker_command()[-1] == "--preview-worker"


def test_a_process_that_does_not_answer_is_stopped_after_the_delay(tmp_path):
    silent = SaxonPreviewClient([sys.executable, "-c", "import time; time.sleep(120)"])
    try:
        started = time.monotonic()
        with pytest.raises(PreviewError) as error:
            silent.transform(PERSONS, tmp_path / "vue.xsl", {}, timeout=1)
        assert error.value.code == "timeout" and time.monotonic() - started < 10
        assert silent._process is None                                     # arrêté, relancé à la demande suivante
    finally:
        silent.close()
