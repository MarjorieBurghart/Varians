# -*- coding: utf-8 -*-
"""CSS d'une vue nommée (V0.9.4.4).

Une vue qui a son propre fichier CSS l'emploie. Sans fichier : la CSS du
projet s'ajoute automatiquement, sauf si la feuille XSLT produit son propre
``<style>`` ; ``projectCss`` (always, never) impose un autre choix. Les
variables CSS d'un ``<style>`` produit par la feuille sont remplacées par
leur valeur, que Qt ne comprendrait pas. Les règles de Varians (crayons,
repères de ligne) restent toujours."""
from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QTextCursor

from app_context import tr
from project_config import ViewConfig, load_project
from project_management import update_project_documents
from test_gui_document_views import _personnes, _wait_preview

GREEN = "#00aa00"
RED = "#cc0000"

SHEET = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">
  <xsl:output method="html"/>
  <xsl:template match="/">
    <html><head>{style}</head><body>
      <p class="marque">Marque du projet</p>
      <xsl:apply-templates select="//tei:person"/>
    </body></html>
  </xsl:template>
  <xsl:template match="tei:person"><p class="fiche"><xsl:value-of select="tei:persName"/></p></xsl:template>
</xsl:stylesheet>
"""
STYLE = "<style>:root {{ --rouge: {red}; }} p.fiche {{ color: var(--rouge); }}</style>".format(red=RED)


@pytest.fixture
def css_project(project_with_documents):
    root = project_with_documents.parent
    # En tête : Qt ignore les règles qui suivent un @media.
    (root / "rendering" / "tei.css").write_text(
        f"p.marque {{ color: {GREEN}; }}\n" + (root / "rendering" / "tei.css").read_text(encoding="utf-8"),
        encoding="utf-8")
    (root / "xslt").mkdir(exist_ok=True)
    (root / "xslt" / "avec-style.xsl").write_text(SHEET.replace("{style}", STYLE), encoding="utf-8")
    (root / "xslt" / "sans-style.xsl").write_text(SHEET.replace("{style}", ""), encoding="utf-8")
    person = ("person",)
    views = (ViewConfig("Avec style", "xslt/avec-style.xsl", units=person),
             ViewConfig("Sans style", "xslt/sans-style.xsl", units=person),
             ViewConfig("Avec style, CSS du projet", "xslt/avec-style.xsl", units=person, project_css="always"),
             ViewConfig("Sans style, sans CSS", "xslt/sans-style.xsl", units=person, project_css="never"))
    project = load_project(project_with_documents)
    update_project_documents(project_with_documents, [
        replace(config, views=views) if config.path.name == "personnes.xml" else config
        for config in project.documents])
    return project_with_documents


def _color(view, word):
    text = view.preview.toPlainText()
    cursor = QTextCursor(view.preview.document())
    cursor.setPosition(text.index(word) + 1)
    return cursor.charFormat().foreground().color().name()


def _show(open_window, project, qtbot, name):
    window = open_window(project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view(name)
    _wait_preview(qtbot, view, "Bernardus")
    return view


def test_a_stylesheet_with_its_own_style_leaves_out_the_project_css(open_window, css_project, qtbot):
    view = _show(open_window, css_project, qtbot, "Avec style")
    assert _color(view, "Marque") != GREEN                      # la CSS du projet n'est pas ajoutée
    assert _color(view, "Bernardus") == RED                     # variable du <style> remplacée
    assert len(view.preview._paragraph_markers) == 2            # les règles de Varians restent


def test_a_stylesheet_without_style_gets_the_project_css(open_window, css_project, qtbot):
    view = _show(open_window, css_project, qtbot, "Sans style")
    assert _color(view, "Marque") == GREEN


def test_the_project_css_can_be_kept_or_left_out_explicitly(open_window, css_project, qtbot):
    view = _show(open_window, css_project, qtbot, "Avec style, CSS du projet")
    assert _color(view, "Marque") == GREEN and _color(view, "Bernardus") == RED
    view = _show(open_window, css_project, qtbot, "Sans style, sans CSS")
    assert _color(view, "Marque") != GREEN


def test_the_tooltip_says_which_css_is_used(open_window, css_project, qtbot):
    view = _show(open_window, css_project, qtbot, "Avec style")
    project_css = view.main.project.css
    assert view.view_combo.toolTip().startswith(tr("preview.view.files.tip", xslt=view.xsl_path,
                                                      css=tr("preview.view.css.auto", css=project_css)) + "\n")
    assert view.select_view("Sans style, sans CSS")
    assert view.view_combo.toolTip().startswith(tr("preview.view.files.tip", xslt=view.xsl_path,
                                                      css=tr("preview.view.css.none")) + "\n")
    assert view.select_view("Avec style, CSS du projet")
    assert view.view_combo.toolTip().startswith(tr("preview.view.files.tip", xslt=view.xsl_path, css=project_css) + "\n")


def test_a_view_without_project_css_does_not_need_it(open_window, css_project, qtbot):
    (css_project.parent / "rendering" / "tei.css").unlink()
    view = _show(open_window, css_project, qtbot, "Sans style, sans CSS")
    assert view.info.text() != tr("preview.files_missing")
