# -*- coding: utf-8 -*-
"""Rangée d'onglets des documents, au-dessus de la source et de l'aperçu."""
from __future__ import annotations

from PySide6.QtGui import QColor

from app_context import tr


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def _type_at_end(window, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(len(window.editor.toPlainText()))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_simple_project_shows_no_document_tabs(open_window, example_project):
    window = open_window(example_project)
    assert window.document_tab_bar.isHidden()
    assert window.document_tab_bar.count() == 1


def test_tabs_list_the_edition_then_the_auxiliary_documents(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    assert not bar.isHidden()
    assert bar.parentWidget() is window.left_tabs.parentWidget()     # au-dessus des vues
    assert [bar.tabText(i) for i in range(bar.count())] == [tr("documents.edition_tab"), "Personnes"]
    assert str(window.edition_session.path) in bar.tabToolTip(0)
    assert str(_aux(window).path) in bar.tabToolTip(1)
    assert bar.currentIndex() == 0


def test_choosing_a_tab_shows_its_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    bar.setCurrentIndex(1)
    assert window.document is _aux(window)
    bar.setCurrentIndex(0)
    assert window.document is window.edition_session


def test_current_tab_follows_the_displayed_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window.show_document(_aux(window))
    assert window.document_tab_bar.currentIndex() == 1


def test_refused_switch_keeps_the_current_tab(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    _aux(window).path.unlink()
    dialogs.expect("critical")
    window.document_tab_bar.setCurrentIndex(1)
    assert window.document_tab_bar.currentIndex() == 0
    assert window.document is window.edition_session


def test_modified_documents_are_marked(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    _type_at_end(window, " ")
    assert bar.tabText(0) == tr("documents.edition_tab") + " *"

    window.show_document(_aux(window))
    _type_at_end(window, " ")
    assert bar.tabText(1) == "Personnes *"
    assert bar.tabText(0) == tr("documents.edition_tab") + " *"
    assert window.save()
    assert bar.tabText(1) == "Personnes"


def test_tab_colour_follows_the_health_of_each_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    normal = bar.tabTextColor(0)
    window.show_document(_aux(window))
    _type_at_end(window, "<")
    window.validate_text(False)
    assert bar.tabTextColor(1) == QColor("#a13d32")
    assert tr("xml.health.malformed.tooltip") in bar.tabToolTip(1)

    window.show_document(window.edition_session)
    assert bar.tabTextColor(1) == QColor("#a13d32")              # propre au document
    assert bar.tabTextColor(0) == normal
