# -*- coding: utf-8 -*-
"""Sélection retrouvée d'une vue à l'autre par son texte et son contexte
(V0.9.4.5).

Un document de notices sans ``<lb/>`` : rien ne repère les lignes. La vue
« Sans crayons » rend ses paragraphes par ``xsl:for-each`` (pas de crayon
✎) ; la vue « Avec crayons » par ``xsl:apply-templates``, et rend les notes
en fin de page, avec un appel « [1] ». Une sélection traverse une balise
(``<persName>``) ou une entité (``&amp;``) ; un mot répété est retrouvé à
sa place, même quand une note rendue ailleurs fausserait un décompte des
occurrences. Une sélection introuvable est signalée dans la barre d'état."""
from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtGui import QTextCursor

from app_context import tr
from project_config import DocumentConfig, ViewConfig, load_project
from project_management import update_project_documents

NOTICES = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Notices choisies</title></titleStmt>
      <publicationStmt><p>Essai</p></publicationStmt>
      <sourceDesc><p>Essai</p></sourceDesc>
    </fileDesc>
  </teiHeader>
  <text>
    <body>
      <!-- Primo dixit Petrus -->
      <p>Primo dixit <persName>Petrus</persName> ad populum.</p>
      <p>Deinde dixit <persName>Paulus</persName> ad fratres &amp; sorores.</p>
      <p>Tandem dixit Iohannes<note>dixit : sic B</note> et iterum dixit ad omnes.</p>
    </body>
  </text>
</TEI>
"""

SHEET = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">
  <xsl:output method="html"/>
  <xsl:template match="/">
    <html><body>
      {paragraphs}
      <div class="notes">
        <xsl:for-each select="//tei:note"><p>[<xsl:value-of select="position()"/>] <xsl:value-of select="."/></p></xsl:for-each>
      </div>
    </body></html>
  </xsl:template>
  <xsl:template match="tei:p"><p><xsl:apply-templates/></p></xsl:template>
  <xsl:template match="tei:note">[<xsl:number count="tei:note" level="any"/>]</xsl:template>
</xsl:stylesheet>
"""
WITHOUT_PENCILS = '<xsl:for-each select="//tei:body/tei:p"><p><xsl:apply-templates/></p></xsl:for-each>'
WITH_PENCILS = '<xsl:apply-templates select="//tei:body/tei:p"/>'


@pytest.fixture
def notices_project(example_project):
    root = example_project.parent
    (root / "xml" / "notices.xml").write_text(NOTICES, encoding="utf-8")
    (root / "xslt").mkdir(exist_ok=True)
    (root / "xslt" / "sans-crayons.xsl").write_text(SHEET.replace("{paragraphs}", WITHOUT_PENCILS), encoding="utf-8")
    (root / "xslt" / "avec-crayons.xsl").write_text(SHEET.replace("{paragraphs}", WITH_PENCILS), encoding="utf-8")
    views = (ViewConfig("Sans crayons", "xslt/sans-crayons.xsl"), ViewConfig("Avec crayons", "xslt/avec-crayons.xsl"))
    project = load_project(example_project)
    update_project_documents(example_project, list(project.documents) + [
        DocumentConfig(root / "xml" / "notices.xml", "Notices", views=views)])
    return example_project


def _show(open_window, project, qtbot, view_name):
    window = open_window(project)
    session = next(session for session in window.documents if session.path.name == "notices.xml")
    assert window.show_document(session)
    view = window.formatted_view
    assert view.select_view(view_name)
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: "iterum" in view.preview.toPlainText(), timeout=15000)
    qtbot.wait(50)
    return window, view


def _nth(text, needle, nth):
    start = -1
    for _ in range(nth + 1):
        start = text.index(needle, start + 1)
    return start, start + len(needle)


def _select(editor, start, end):
    cursor = QTextCursor(editor.document())
    cursor.setPosition(start)
    cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def _selection(editor):
    cursor = editor.textCursor()
    return cursor.selectionStart(), cursor.selectionEnd()


def _preview_to_source(window, view, qtbot, needle, nth=0):
    _select(view.preview, *_nth(view.preview.toPlainText(), needle, nth))
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.editor.textCursor().hasSelection(), timeout=5000)
    return window.editor.toPlainText()[slice(*_selection(window.editor))], _selection(window.editor)[0]


# --- Aperçu → source --------------------------------------------------------

@pytest.mark.parametrize("nth, context", [(1, "dixit <persName>Paulus"), (2, "dixit Iohannes")])
def test_without_line_breaks_or_pencils_a_repeated_word_comes_back_at_its_place(
        open_window, notices_project, qtbot, nth, context):
    window, view = _show(open_window, notices_project, qtbot, "Sans crayons")
    selected, start = _preview_to_source(window, view, qtbot, "dixit", nth)
    assert selected == "dixit" and start == window.editor.toPlainText().index(context)


def test_a_selection_across_an_inline_element_comes_back(open_window, notices_project, qtbot):
    window, view = _show(open_window, notices_project, qtbot, "Sans crayons")
    selected, _start = _preview_to_source(window, view, qtbot, "dixit Paulus")
    assert selected == "dixit <persName>Paulus"


def test_an_entity_comes_back(open_window, notices_project, qtbot):
    window, view = _show(open_window, notices_project, qtbot, "Avec crayons")
    selected, _start = _preview_to_source(window, view, qtbot, "fratres & sorores")
    assert selected == "fratres &amp; sorores"


def test_a_note_rendered_elsewhere_does_not_shift_the_occurrence(open_window, notices_project, qtbot):
    """Dans l'élément, l'aperçu montre « Tandem dixit », « iterum dixit »,
    puis la note ; la source « Tandem dixit », la note, « iterum dixit »."""
    window, view = _show(open_window, notices_project, qtbot, "Avec crayons")
    assert len(view.preview._paragraph_markers) == 3
    selected, start = _preview_to_source(window, view, qtbot, "dixit", 3)       # « iterum dixit »
    assert selected == "dixit" and start == window.editor.toPlainText().index("dixit ad omnes")


def test_a_text_written_by_the_stylesheet_is_reported(open_window, notices_project, qtbot):
    window, view = _show(open_window, notices_project, qtbot, "Avec crayons")
    _select(view.preview, *_nth(view.preview.toPlainText(), "[1]", 0))
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == tr("selection.not_found.source"), timeout=5000)
    assert not window.editor.textCursor().hasSelection()


# --- Source → aperçu --------------------------------------------------------

@pytest.mark.parametrize("view_name", ["Sans crayons", "Avec crayons"])
def test_a_source_selection_is_found_in_the_preview_by_its_context(open_window, notices_project, qtbot, view_name):
    window, view = _show(open_window, notices_project, qtbot, view_name)
    window.left_tabs.setCurrentIndex(0)
    source = window.editor.toPlainText()
    start = source.index("dixit ad omnes")
    _select(window.editor, start, start + len("dixit"))
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    start = view.preview.toPlainText().index("dixit ad omnes")
    assert _selection(view.preview) == (start, start + len("dixit"))


def test_a_source_selection_absent_from_the_preview_is_reported(open_window, notices_project, qtbot):
    window, view = _show(open_window, notices_project, qtbot, "Sans crayons")
    window.left_tabs.setCurrentIndex(0)
    source = window.editor.toPlainText()
    _select(window.editor, *_nth(source, "Notices choisies", 0))
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: window.statusBar().currentMessage() == tr("selection.not_found.preview"), timeout=5000)
    assert not view.preview.textCursor().hasSelection()


# --- Aperçu ↔ éditeur de fragment -------------------------------------------

def _open_fragment(open_window, project, qtbot, paragraph):
    window, view = _show(open_window, project, qtbot, "Avec crayons")
    assert view.load_fragment(paragraph)
    return window, view


def test_a_preview_selection_across_an_entity_is_selected_in_the_fragment(open_window, notices_project, qtbot):
    _window, view = _open_fragment(open_window, notices_project, qtbot, 1)
    _select(view.preview, *_nth(view.preview.toPlainText(), "fratres & sorores", 0))
    view.preview.textSelected.emit()
    assert view.fragment_editor.textCursor().selectedText() == "fratres &amp; sorores"


def test_a_note_does_not_shift_the_occurrence_in_the_fragment(open_window, notices_project, qtbot):
    _window, view = _open_fragment(open_window, notices_project, qtbot, 2)
    _select(view.preview, *_nth(view.preview.toPlainText(), "dixit", 3))          # « iterum dixit »
    view.preview.textSelected.emit()
    fragment = view.fragment_editor.toPlainText()
    start = fragment.index("dixit ad omnes")
    assert _selection(view.fragment_editor) == (start, start + len("dixit"))


def test_a_fragment_selection_finds_its_place_in_the_preview(open_window, notices_project, qtbot):
    _window, view = _open_fragment(open_window, notices_project, qtbot, 2)
    view.fragment_editor.setFocus()
    qtbot.waitUntil(view.fragment_editor.hasFocus, timeout=3000)
    start = view.fragment_editor.toPlainText().index("dixit ad omnes")
    _select(view.fragment_editor, start, start + len("dixit"))
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=3000)
    target = view.preview.toPlainText().index("dixit ad omnes")
    assert _selection(view.preview) == (target, target + len("dixit"))
