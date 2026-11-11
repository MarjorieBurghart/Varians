# -*- coding: utf-8 -*-
"""Vues en XSLT 2.0 ou 3.0 dans la Vue XSLT / CSS (V0.9.4.4).

Le moteur suit la version de la feuille : 1.0, lxml dans Varians ; 2.0 ou
3.0, Saxon, dans le processus d'aperçu (saxon_preview), hors du fil de la
fenêtre, actualisation manuelle comprise. Les crayons y sont dans tous les
modes ; le fragment s'applique au document affiché comme avec une feuille
1.0. Une erreur, une feuille qui ne finit pas ou Saxon absent sont dits
sous l'aperçu, qui garde son contenu."""
from __future__ import annotations

import time
from dataclasses import replace

import pytest

import saxon_preview
from app_context import tr
from project_config import ViewConfig, load_project
from project_management import update_project_documents, update_project_edition_views
from test_gui_document_views import WJ, _personnes, _wait_preview
from test_gui_pencil_selection import _click_pencil
from xslt_scenarios import saxon_available

pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")

FICHES = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="#all">
  <xsl:output method="html"/>
  <xsl:template match="/">
    <html><body><h1>Fiches 3.0</h1><xsl:apply-templates select="//tei:person" mode="fiche"/></body></html>
  </xsl:template>
  <xsl:template match="tei:person" mode="fiche">
    <p class="fiche">{upper-case(tei:persName)}</p>
  </xsl:template>
</xsl:stylesheet>
"""


@pytest.fixture(autouse=True)
def saxon_process():
    """Le processus d'aperçu de chaque test est arrêté à la fin."""
    yield
    if saxon_preview._CLIENT is not None:
        saxon_preview._CLIENT.close()
        saxon_preview._CLIENT = None


@pytest.fixture
def saxon_project(project_with_documents):
    root = project_with_documents.parent
    (root / "xslt").mkdir(exist_ok=True)
    (root / "xslt" / "fiches.xsl").write_text(FICHES.replace("<p class=\"fiche\">{",
                                                             "<p class=\"fiche\" xsl:expand-text=\"yes\">{"),
                                              encoding="utf-8")
    project = load_project(project_with_documents)
    update_project_documents(project_with_documents, [
        replace(config, views=(ViewConfig("Fiches", "xslt/fiches.xsl", "", ("person",)),))
        if config.path.name == "personnes.xml" else config for config in project.documents])
    update_project_edition_views(project_with_documents,
                                 (ViewConfig("Apparat en notes", "${varians}/apparat-en-notes.xsl"),))
    return project_with_documents


def test_a_3_0_view_is_shown_by_saxon_with_its_pencils(open_window, saxon_project, qtbot):
    window = open_window(saxon_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Fiches")
    _wait_preview(qtbot, view, "BERNARDUS")
    assert "Fiches 3.0" in view.preview.toPlainText()
    assert [index for _marker, _pos, index in view.preview._paragraph_markers] == [0, 1]
    assert "Saxon" in view.info.text()
    _click_pencil(qtbot, view, 1)
    qtbot.waitUntil(lambda: view.current_paragraph == 1, timeout=3000)
    view.fragment_editor.setPlainText(view.fragment_editor.toPlainText().replace("Petrus<", "Petrus Lombardus<"))
    assert view.apply_fragment()
    assert "<persName>Petrus Lombardus</persName>" in window.editor.toPlainText()
    qtbot.waitUntil(lambda: "PETRUS LOMBARDUS" in view.preview.toPlainText().replace(WJ, ""), timeout=15000)


def test_a_manual_refresh_with_saxon_does_not_block_the_window(open_window, saxon_project, qtbot):
    window = open_window(saxon_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Fiches")
    _wait_preview(qtbot, view, "BERNARDUS")
    window.editor.setPlainText(window.editor.toPlainText().replace("Bernardus", "Bernardus abbas"))
    started = time.perf_counter()
    view.refresh_preview(force=True)
    assert time.perf_counter() - started < 0.5                     # rendu tout de suite à la fenêtre
    assert view.info.text() == tr("preview.refreshing")
    qtbot.waitUntil(lambda: "BERNARDUS ABBAS" in view.preview.toPlainText(), timeout=15000)


def test_an_edition_view_in_3_0_has_a_pencil_per_element(open_window, saxon_project, qtbot):
    from fragment_units import unit_spans
    window = open_window(saxon_project)
    view = window.formatted_view
    assert view.select_view("Apparat en notes")
    window.left_tabs.setCurrentWidget(view)
    total = len(unit_spans(window.editor.toPlainText(), window.fragment_unit_names()))
    qtbot.waitUntil(lambda: len(view.preview._paragraph_markers) == total, timeout=30000)
    assert "Saxon" in view.info.text()
    assert sorted(index for _marker, _pos, index in view.preview._paragraph_markers) == list(range(total))


def test_an_error_of_a_3_0_stylesheet_is_shown_under_the_preview(open_window, saxon_project, qtbot):
    sheet = saxon_project.parent / "xslt" / "fiches.xsl"
    sheet.write_text(FICHES.replace('<xsl:apply-templates select="//tei:person" mode="fiche"/>',
                                    '<xsl:value-of select="1 +"/>'), encoding="utf-8")
    window = open_window(saxon_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Fiches")
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: "fiches.xsl" in view.info.text(), timeout=15000)
    assert view.info.text().startswith(tr("preview.transform_error", error="").strip())


def test_a_3_0_stylesheet_that_never_ends_is_stopped(open_window, saxon_project, qtbot, monkeypatch):
    monkeypatch.setattr(saxon_preview, "PREVIEW_TIMEOUT_SEC", 2)
    sheet = saxon_project.parent / "xslt" / "fiches.xsl"
    sheet.write_text(FICHES.replace('<xsl:template match="/">',
                                    '<xsl:template match="/"><xsl:iterate select="1 to 2000000000">'
                                    '<xsl:next-iteration/></xsl:iterate>'), encoding="utf-8")
    window = open_window(saxon_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Fiches")
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: view.info.text() == tr("preview.saxon.timeout", seconds=2), timeout=20000)


def test_without_saxon_a_3_0_view_says_so(open_window, saxon_project, qtbot, monkeypatch):
    class Missing:
        def transform(self, *args, **kwargs):
            raise saxon_preview.PreviewError("saxon_missing", "no saxonche")
    monkeypatch.setattr(saxon_preview, "client", lambda: Missing())
    window = open_window(saxon_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Fiches")
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: view.info.text() == tr("preview.saxon.missing"), timeout=10000)


def test_a_1_0_view_still_uses_lxml_in_the_window(open_window, saxon_project, qtbot):
    window = open_window(saxon_project)
    view = window.formatted_view
    assert view.select_view(None)
    window.left_tabs.setCurrentWidget(view)
    view.refresh_preview(force=True)                                # synchrone, comme avant
    assert "lxml" in view.info.text() and "Commune sanctorum" in view.preview.toPlainText()
    assert saxon_preview._CLIENT is None                            # aucun processus Saxon lancé


def test_the_source_selection_reaches_a_3_0_preview_when_it_is_ready(open_window, saxon_project, qtbot):
    """L'aperçu Saxon arrive après le changement d'onglet : la sélection de
    la source y est reportée quand il est prêt, et non sur l'ancien
    contenu."""
    from test_gui_selection_transfer import _select
    window = open_window(saxon_project)
    view = window.formatted_view
    assert view.select_view("Apparat en notes")
    text = window.editor.toPlainText()
    start = text.index("Commune sanctorum") + len("Commune ")
    _select(window.editor, start, start + len("sanctorum"))
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: view.preview.textCursor().selectedText() == "sanctorum", timeout=20000)
