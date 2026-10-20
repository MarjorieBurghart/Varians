# -*- coding: utf-8 -*-
"""Onglets de documents affichés : masqués, réordonnés, mémorisés localement
pour le projet ; un document masqué atteint par une référence réapparaît."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from app_context import _settings, tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents

LIEUX = ('<listPlace xmlns="http://www.tei-c.org/ns/1.0">\n'
         '<place xml:id="clairvaux" corresp="#nulle"><placeName>Clara Vallis</placeName></place>\n'
         '</listPlace>\n')


@pytest.fixture
def three_documents(project_with_documents):
    """Édition, personnes.xml (« Personnes ») et lieux.xml (sans label)."""
    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text(LIEUX, encoding="utf-8")
    documents = list(load_project(project_with_documents).documents) + [DocumentConfig(lieux)]
    update_project_documents(project_with_documents, documents)
    return project_with_documents


def _tabs(window):
    bar = window.document_tab_bar
    return [bar.tabText(i) for i in range(bar.count())]


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _edition_tab():
    return tr("documents.edition_tab")


def test_every_tab_is_shown_at_first_opening(open_window, three_documents):
    window = open_window(three_documents)
    assert _tabs(window) == [_edition_tab(), "Personnes", "lieux.xml"]
    assert window._visible_document_sessions() == window.documents
    assert window._document_key(window.edition_session) == "edition"
    assert window._document_key(_doc(window, "personnes.xml")) == "xml/personnes.xml"


def test_a_hidden_tab_stays_in_the_project_and_stays_hidden_after_reopening(open_window, three_documents):
    window = open_window(three_documents)
    assert window.hide_document_tab(_doc(window, "lieux.xml"))
    assert _tabs(window) == [_edition_tab(), "Personnes"]
    assert len(window.documents) == 3                                  # toujours dans le projet
    assert len(load_project(three_documents).documents) == 2           # project.xml inchangé
    reopened = open_window(three_documents)
    assert _tabs(reopened) == [_edition_tab(), "Personnes"]


def test_tab_order_is_kept_after_reopening(open_window, three_documents):
    window = open_window(three_documents)
    window.set_document_tabs(["xml/lieux.xml", "edition", "xml/personnes.xml"], [])
    assert _tabs(window) == ["lieux.xml", _edition_tab(), "Personnes"]
    assert window.document_tab_bar.currentIndex() == 1                 # l'édition reste affichée
    reopened = open_window(three_documents)
    assert _tabs(reopened) == ["lieux.xml", _edition_tab(), "Personnes"]
    assert [s.path.name for s in reopened.documents] == ["edition.xml", "personnes.xml", "lieux.xml"]


def test_tab_index_designates_the_visible_documents(open_window, three_documents):
    window = open_window(three_documents)
    window.hide_document_tab(_doc(window, "personnes.xml"))
    window.document_tab_bar.setCurrentIndex(1)
    assert window.document is _doc(window, "lieux.xml")
    assert window.document_tab_bar.currentIndex() == 1


def test_hiding_the_displayed_document_shows_the_neighbouring_tab(open_window, three_documents):
    window = open_window(three_documents)
    window.show_document(_doc(window, "personnes.xml"))
    assert window.hide_document_tab(_doc(window, "personnes.xml"))
    assert window.document is _doc(window, "lieux.xml")                # le suivant
    assert window.hide_document_tab(_doc(window, "lieux.xml"))
    assert window.document is window.edition_session                    # sinon le précédent


def test_the_last_visible_tab_cannot_be_hidden(open_window, three_documents):
    window = open_window(three_documents)
    window.hide_document_tab(_doc(window, "personnes.xml"))
    window.hide_document_tab(_doc(window, "lieux.xml"))
    assert not window.hide_document_tab(window.edition_session)
    assert _tabs(window) == [_edition_tab()]
    assert not window.document_tab_bar.isHidden()                       # clic droit toujours possible


def test_f12_towards_a_hidden_document_brings_its_tab_back_for_good(open_window, three_documents):
    window = open_window(three_documents)
    window.hide_document_tab(_doc(window, "personnes.xml"))
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText('<persName ref="personnes.xml#bernard">B</persName>')
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("personnes.xml#ber") + len("personnes.xml#ber"))
    window.editor.setTextCursor(cursor)
    assert window.go_to_reference()
    assert window.document is _doc(window, "personnes.xml")
    assert _tabs(window) == [_edition_tab() + " *", "Personnes", "lieux.xml"]
    window.show_document(window.edition_session)
    assert "Personnes" in _tabs(window)                                 # durablement
    assert "Personnes" in _tabs(open_window(three_documents))


def test_double_click_in_references_brings_a_hidden_tab_back(open_window, three_documents):
    window = open_window(three_documents)
    window.hide_document_tab(_doc(window, "lieux.xml"))
    window.check_references()
    row = next(r for r in range(window.references_table.rowCount())
               if window.references_table.item(r, 0).text() == "lieux.xml")
    assert window.goto_reference_problem(row)
    assert window.document is _doc(window, "lieux.xml")
    assert "lieux.xml" in _tabs(window)


def test_saving_a_hidden_document_does_not_bring_its_tab_back(open_window, three_documents):
    window = open_window(three_documents)
    personnes = _doc(window, "personnes.xml")
    window.show_document(personnes)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("</listPerson>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText('<person xml:id="nouveau"/>\n')
    assert window.hide_document_tab(personnes)
    assert personnes in window._unsaved_sessions()                      # proposé à l'enregistrement
    assert window._save_session(personnes)
    assert 'xml:id="nouveau"' in personnes.path.read_text(encoding="utf-8")
    assert "Personnes" not in _tabs(window)
    assert window.document is not personnes


def test_a_refused_save_leaves_the_hidden_document_displayed_with_its_tab(open_window, three_documents, dialogs):
    window = open_window(three_documents)
    personnes = _doc(window, "personnes.xml")
    window.show_document(personnes)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("</listPerson>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("<person>\n")                        # mal formé
    assert window.hide_document_tab(personnes)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # Annuler
    assert not window._save_session(personnes)
    assert window.document is personnes                                 # montré pour l'avertissement
    assert "Personnes *" in _tabs(window)
    assert window.document_tab_bar.currentIndex() == _tabs(window).index("Personnes *")


def test_the_edition_is_displayed_with_its_tab_at_opening(open_window, three_documents):
    window = open_window(three_documents)
    assert window.hide_document_tab(window.edition_session)
    assert window.document is _doc(window, "personnes.xml")
    assert window.hide_document_tab(_doc(window, "lieux.xml"))
    reopened = open_window(three_documents)
    assert reopened.document is reopened.edition_session
    assert _tabs(reopened) == [_edition_tab(), "Personnes"]
    assert reopened.document_tab_bar.currentIndex() == 0


def test_a_document_added_later_is_visible(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window.hide_document_tab(_doc(window, "personnes.xml"))
    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text(LIEUX, encoding="utf-8")
    assert window._register_document(DocumentConfig(lieux))
    assert _tabs(window) == [_edition_tab(), "lieux.xml"]
    assert window.document is _doc(window, "lieux.xml")


@pytest.mark.parametrize("stored", [
    "pas du json",
    '{"order": ["edition"], "hidden": ["edition", "xml/personnes.xml", "xml/lieux.xml"]}',
    '{"order": 3, "hidden": "x"}',
])
def test_an_unusable_setting_still_shows_the_edition(open_window, three_documents, stored):
    window = open_window(three_documents)
    key = window._view_settings_key("documentTabs")
    _settings().setValue(key, stored)
    reopened = open_window(three_documents)
    assert _edition_tab() in _tabs(reopened)
    assert reopened.document is reopened.edition_session
