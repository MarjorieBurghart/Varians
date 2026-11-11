# -*- coding: utf-8 -*-
"""Repères de ligne du témoin pivot dans l'aperçu (V0.9.4.4).

La synchronisation avec les témoins associe le n-ième repère de la page
(``tei-line://base/INDEX``) à la n-ième ligne du pivot de la source. Une
feuille qui en omet ou en répète décale tout ce qui suit : l'aperçu le dit,
avec les deux nombres, au lieu de se taire."""
from __future__ import annotations

import re

import pytest

from app_context import tr
from project_config import ViewConfig
from project_management import update_project_edition_views

SKIPPING = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">
  <xsl:output method="html"/>
  <xsl:param name="baseWitness"/>
  <xsl:template match="/"><html><body>
    <xsl:apply-templates select="(//tei:body//tei:p)[position() &gt; {skip}]"/>
  </body></html></xsl:template>
  <xsl:template match="tei:p"><p><xsl:apply-templates/></p></xsl:template>
  <xsl:template match="tei:note | tei:rdg"/>
  <xsl:template match="tei:lb">
    <xsl:if test="@edRef = concat('#', $baseWitness)">
      <a class="tei-line-marker" href="tei-line://base/INDEX"><xsl:text>&#8288;</xsl:text></a>
    </xsl:if>
  </xsl:template>
</xsl:stylesheet>
"""


def _project(project_path, skip):
    root = project_path.parent
    (root / "xslt").mkdir(exist_ok=True)
    (root / "xslt" / "lignes.xsl").write_text(SKIPPING.replace("{skip}", str(skip)), encoding="utf-8")
    update_project_edition_views(project_path, (ViewConfig("Lignes", "xslt/lignes.xsl"),))
    return project_path


def _markers(view):
    return len(set(re.findall(r"tei-line://base/(\d+)", view.preview.toHtml())))


def test_missing_line_markers_are_reported(open_window, example_project, qtbot):
    window = open_window(_project(example_project, skip=3))
    view = window.formatted_view
    assert view.select_view("Lignes")
    window.left_tabs.setCurrentWidget(view)
    view.refresh_preview(force=True)
    expected = len(window.lb_spans())
    produced = _markers(view)
    assert 0 < produced < expected
    assert view.info.text().endswith(tr("preview.lines_mismatch", lines=produced, expected=expected))


def test_a_stylesheet_with_every_line_marker_says_nothing_more(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    view.refresh_preview(force=True)
    assert _markers(view) == len(window.lb_spans())
    mismatch = tr("preview.lines_mismatch", lines=1, expected=2)
    assert mismatch.split("1")[0] not in view.info.text()


def test_the_assembled_edition_is_checked_too(open_window, example_with_part, qtbot):
    window = open_window(_project(example_with_part, skip=3))
    view = window.formatted_view
    assert view.select_view("Lignes")
    window.left_tabs.setCurrentWidget(view)
    view.refresh_preview(force=True)
    expected = len(view.sources.lines)
    produced = _markers(view)
    assert 0 < produced < expected
    assert view.info.text().endswith(tr("preview.lines_mismatch", lines=produced, expected=expected))
