# -*- coding: utf-8 -*-
"""Onglets des documents (V0.9.2.8) : quand ils ne tiennent plus dans leur
rangée, une flèche ▾ s'affiche à sa droite ; elle déroule le menu de tous
les onglets (le document affiché coché), puis « Choisir les documents
affichés… »."""
from __future__ import annotations

import pytest


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


@pytest.fixture
def project_with_many_documents(example_project):
    """Projet exemple déclarant douze documents auxiliaires."""
    from project_config import DocumentConfig
    from project_management import update_project_documents

    folder = example_project.parent / "xml"
    documents = []
    for number in range(1, 13):
        path = folder / f"notes{number:02}.xml"
        path.write_text(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>Notes {number}</p>'
                        f'</body></text></TEI>', encoding="utf-8")
        documents.append(DocumentConfig(path, f"Notes de travail {number:02}"))
    update_project_documents(example_project, documents)
    return example_project


def _entries(window):
    menu = window.document_tabs_button.menu()
    menu.aboutToShow.emit()
    return [action for action in menu.actions() if not action.isSeparator()]


def test_no_arrow_while_the_tabs_fit(open_window, example_project, project_with_documents):
    window = open_window(project_with_documents)
    assert not window.document_tab_bar.isHidden()
    assert not window.document_tabs_button.isVisible()


def test_the_arrow_lists_every_tab(open_window, project_with_many_documents, qtbot):
    window = open_window(project_with_many_documents)
    bar = window.document_tab_bar
    button = window.document_tabs_button
    qtbot.waitUntil(button.isVisible, timeout=3000)
    assert button.toolTip() == _tr("documents.tabs.menu")
    # À droite de la rangée d'onglets.
    assert button.mapTo(window, button.rect().topLeft()).x() >= bar.mapTo(window, bar.rect().topRight()).x()
    entries = _entries(window)
    assert [action.text() for action in entries] == (
        [bar.tabText(index) for index in range(bar.count())] + [window.action_choose_documents.text()])
    assert bar.count() == 13
    assert [action.isChecked() for action in entries[:13]] == [index == bar.currentIndex() for index in range(13)]
    # Choisir un onglet affiche son document.
    entries[12].trigger()
    assert window.document.path.name == "notes12.xml"
    assert bar.currentIndex() == 12
    assert [action.isChecked() for action in _entries(window)[:13]] == [index == 12 for index in range(13)]


def test_the_arrow_follows_the_tabs(open_window, project_with_many_documents, qtbot):
    window = open_window(project_with_many_documents)
    button = window.document_tabs_button
    qtbot.waitUntil(button.isVisible, timeout=3000)
    # Les onglets masqués : la flèche disparaît quand les autres tiennent.
    hidden = window._visible_document_sessions()[2:]
    for session in hidden:
        assert window.hide_document_tab(session)
    qtbot.waitUntil(lambda: not button.isVisible(), timeout=3000)
    assert [action.text() for action in _entries(window)] == [
        window.document_tab_bar.tabText(index) for index in range(2)] + [window.action_choose_documents.text()]
    # Les onglets rendus : la flèche revient.
    for session in hidden:
        window.show_document_tab(session)
    qtbot.waitUntil(button.isVisible, timeout=3000)
    assert len(_entries(window)) == 14


def test_the_tooltip_is_translated(open_window, project_with_documents):
    from app_context import current_i18n
    window = open_window(project_with_documents)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert window.document_tabs_button.toolTip() == current_i18n().tr("documents.tabs.menu") == "All tabs"
