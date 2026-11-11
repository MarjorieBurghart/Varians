# -*- coding: utf-8 -*-
"""Vues nommées dans la Vue XSLT / CSS (V0.9.4.4).

Chaque document XML du projet a sa Vue XSLT / CSS : la vue du projet
(feuille et CSS de <rendering>) et ses vues nommées (project.xml, <view>),
choisies dans une liste. Les crayons ✎ et l'éditeur de fragment servent pour
le document affiché, quelle que soit la vue ; une vue peut nommer ses
éléments modifiables (units). La vue choisie est retenue pour chaque
document. Les boutons « XSLT… » et « CSS… » (choix pour la session) ont
disparu."""
from __future__ import annotations

from dataclasses import replace

import pytest

from app_context import tr
from project_config import DocumentConfig, ViewConfig, load_project
from project_management import update_project_documents, update_project_edition_views
from test_gui_pencil_selection import _click_pencil
from test_gui_selection_transfer import WJ

INDEX_XSL = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">
  <xsl:output method="html" encoding="UTF-8"/>
  <xsl:template match="/">
    <html><body><h1>Index des personnes</h1><xsl:apply-templates select="//tei:person"/></body></html>
  </xsl:template>
  <xsl:template match="tei:person"><p class="personne">Fiche : <xsl:value-of select="tei:persName"/></p></xsl:template>
</xsl:stylesheet>
"""
PLAIN_XSL = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0" exclude-result-prefixes="tei">
  <xsl:output method="html" encoding="UTF-8"/>
  <xsl:template match="/"><html><body><h1>Vue brute</h1><xsl:apply-templates select="//tei:body//tei:p"/></body></html></xsl:template>
  <xsl:template match="tei:p"><p><xsl:value-of select="."/></p></xsl:template>
</xsl:stylesheet>
"""


def _add_views(project_with_documents):
    root = project_with_documents.parent
    (root / "xslt").mkdir(exist_ok=True)
    (root / "xslt" / "index.xsl").write_text(INDEX_XSL, encoding="utf-8")
    (root / "xslt" / "brute.xsl").write_text(PLAIN_XSL, encoding="utf-8")
    (root / "rendering" / "index.css").write_text("p.personne { color: #333; }\n", encoding="utf-8")
    project = load_project(project_with_documents)
    update_project_documents(project_with_documents, [
        replace(config, views=(ViewConfig("Index", "xslt/index.xsl", "rendering/index.css", ("person",)),))
        if config.path.name == "personnes.xml" else config for config in project.documents])
    update_project_edition_views(project_with_documents, (ViewConfig("Brute", "xslt/brute.xsl"),))
    return project_with_documents


@pytest.fixture
def views_project(project_with_documents):
    """Projet exemple avec xml/personnes.xml (deux personnes), sa vue
    « Index » (une fiche par <person>, éléments modifiables : person) et la
    vue « Brute » de l'édition."""
    return _add_views(project_with_documents)


@pytest.fixture
def views_with_part(project_with_documents):
    """Le même, l'édition ayant une partie (xml/rls185.xml)."""
    from corpus_data import move_to_part
    move_to_part(project_with_documents)
    return _add_views(project_with_documents)


def _personnes(window):
    return next(session for session in window.documents if session.path.name == "personnes.xml")


def _wait_preview(qtbot, view, needle):
    window = view.main
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: needle in view.preview.toPlainText().replace(WJ, ""), timeout=15000)
    qtbot.wait(50)


def _content(view, index):
    start, end = view.preview.paragraph_bounds(index)
    return view.preview.toPlainText()[start:end].replace(WJ, "").strip()


def _names(view):
    return [view.view_combo.itemText(index) for index in range(view.view_combo.count())]


def test_a_document_view_uses_its_stylesheet_and_its_pencils(open_window, views_project, qtbot):
    window = open_window(views_project)
    edition_text = window.edition_session.text_document.toPlainText()
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert window.left_tabs.isTabEnabled(window.left_tabs.indexOf(view))
    assert _names(view) == [tr("preview.view.project"), "Index"]
    assert view.select_view("Index")
    assert view.view_combo.toolTip().endswith(tr("preview.view.units.tip", units="person"))
    _wait_preview(qtbot, view, "Index des personnes")
    assert [index for _marker, _pos, index in view.preview._paragraph_markers] == [0, 1]
    assert _content(view, 0).startswith("Fiche : Bernardus")
    assert _content(view, 1).startswith("Fiche : Petrus")
    _click_pencil(qtbot, view, 1)
    qtbot.waitUntil(lambda: view.current_paragraph == 1, timeout=3000)
    assert view.fragment_editor.toPlainText() == '<person xml:id="petrus"><persName>Petrus</persName></person>'
    view.fragment_editor.setPlainText(view.fragment_editor.toPlainText().replace("Petrus<", "Petrus Lombardus<"))
    assert view.apply_fragment()
    assert "<persName>Petrus Lombardus</persName>" in window.editor.toPlainText()
    assert window.document is _personnes(window)
    assert window.edition_session.text_document.toPlainText() == edition_text


def test_the_project_view_serves_every_document(open_window, views_project, qtbot):
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.current_view is None                                   # vue du projet au départ
    assert view.xsl_path == window.project.xslt and view.css_path == window.project.css
    _wait_preview(qtbot, view, "Bernardus")
    # Sans <body> ni éléments choisis : la règle de l'édition, tout le document compte.
    assert len(view.preview._paragraph_markers) == 1


def test_the_chosen_view_is_remembered_for_each_document(open_window, views_project, qtbot):
    window = open_window(views_project)
    view = window.formatted_view
    assert _names(view) == [tr("preview.view.project"), "Brute"]      # l'édition
    assert window.show_document(_personnes(window))
    assert view.select_view("Index")
    assert window.show_document(window.edition_session)
    assert view.current_view is None and view.view_combo.currentIndex() == 0
    assert window.show_document(_personnes(window))
    assert view.current_view.name == "Index" and view.view_combo.currentText() == "Index"
    again = open_window(views_project)
    assert again.show_document(_personnes(again))
    assert again.formatted_view.current_view.name == "Index"


def test_the_edition_has_its_named_views(open_window, views_project, qtbot):
    window = open_window(views_project)
    view = window.formatted_view
    assert view.select_view("Brute")
    assert view.xsl_path == (views_project.parent / "xslt" / "brute.xsl").resolve()
    assert view.css_path == window.project.css                         # CSS du projet
    assert view.view_combo.toolTip() == tr("preview.view.files.tip", xslt=view.xsl_path, css=view.css_path)
    _wait_preview(qtbot, view, "Vue brute")
    assert len(view.preview._paragraph_markers) > 1                    # crayons de l'édition
    assert view.select_view(None)
    _wait_preview(qtbot, view, "Commune sanctorum")
    assert "Vue brute" not in view.preview.toPlainText()


def test_a_missing_view_stylesheet_is_reported(open_window, views_project, qtbot):
    (views_project.parent / "xslt" / "index.xsl").unlink()
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: view.info.text() == tr("preview.files_missing"), timeout=5000)


def test_stylesheets_have_no_view(open_window, views_project, qtbot):
    stylesheet = views_project.parent / "xslt" / "index.xsl"
    project = load_project(views_project)
    update_project_documents(views_project, list(project.documents) + [DocumentConfig(stylesheet)])
    window = open_window(views_project)
    session = next(s for s in window.documents if s.path == stylesheet.resolve())
    assert window.show_document(session)
    assert not window.left_tabs.isTabEnabled(window.left_tabs.indexOf(window.formatted_view))
    assert window.show_document(_personnes(window))
    assert window.left_tabs.isTabEnabled(window.left_tabs.indexOf(window.formatted_view))


def test_changing_document_closes_the_fragment(open_window, views_project, qtbot):
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")
    _wait_preview(qtbot, view, "Index des personnes")
    _click_pencil(qtbot, view, 0)
    qtbot.waitUntil(lambda: view.current_paragraph == 0, timeout=3000)
    assert window.show_document(window.edition_session)
    assert view.frag_box.isHidden() and window.left_tabs.currentIndex() == 0


def test_the_session_only_buttons_are_gone(open_window, views_project):
    view = open_window(views_project).formatted_view
    assert not hasattr(view, "xsl_btn") and not hasattr(view, "css_btn")
    assert not hasattr(view, "choose_xslt") and not hasattr(view, "choose_css")


def test_a_document_of_an_edition_in_parts_shows_itself(open_window, views_with_part, qtbot):
    """Édition en parties : l'aperçu de l'édition et de ses parties est
    l'édition assemblée ; celui d'un document auxiliaire, ce document, et
    son fragment modifie ce document."""
    window = open_window(views_with_part)
    part = next(s for s in window.documents if s.is_part)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")
    _wait_preview(qtbot, view, "Index des personnes")
    assert "Commune sanctorum" not in view.preview.toPlainText()
    assert [index for _marker, _pos, index in view.preview._paragraph_markers] == [0, 1]
    _click_pencil(qtbot, view, 0)
    qtbot.waitUntil(lambda: view.current_paragraph == 0, timeout=3000)
    assert view.fragment_session is _personnes(window)
    assert view.frag_label.text() == tr("fragment.label", element="<person>", index=1, total=2)
    view.fragment_editor.setPlainText(view.fragment_editor.toPlainText().replace("Bernardus", "Bernardus abbas"))
    assert view.apply_fragment()
    assert "<persName>Bernardus abbas</persName>" in window.editor.toPlainText()
    assert window.show_document(part)
    assert view.current_view is None
    _wait_preview(qtbot, view, "Commune sanctorum")
    assert "Index des personnes" not in view.preview.toPlainText()
