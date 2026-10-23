# -*- coding: utf-8 -*-
"""Menu Fichier ▸ Documents XML du projet : ajouter, créer, retirer ; feuilles
XSLT (V0.9.2.1)."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QInputDialog, QMessageBox

from app_context import tr
from project_config import load_project

Std = QMessageBox.StandardButton
Role = QMessageBox.ButtonRole


@pytest.fixture
def choose_file(monkeypatch):
    """Réponse programmée aux boîtes de choix de fichier."""
    def _set(path):
        answer = (str(path), "") if path else ("", "")
        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: answer))
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: answer))
    return _set


@pytest.fixture
def file_dialog_calls(monkeypatch):
    """Arguments reçus par les boîtes de choix de fichier, et leur réponse."""
    calls = []

    def _set(path):
        def answer(*args, **kwargs):
            calls.append(args)
            return (str(path), "") if path else ("", "")
        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(answer))
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(answer))
        return calls
    return _set


@pytest.fixture
def stylesheet_version(monkeypatch):
    """Réponse programmée au choix de la version d'une nouvelle feuille."""
    asked = []

    def _set(index, ok=True):
        def answer(parent, title, label, items, current=0, editable=True, *rest, **kwargs):
            asked.append(list(items))
            return (items[index], ok)
        monkeypatch.setattr(QInputDialog, "getItem", staticmethod(answer))
        return asked
    return _set


@pytest.fixture
def root_name(monkeypatch):
    def _set(name, ok=True):
        monkeypatch.setattr(QInputDialog, "getText", staticmethod(lambda *a, **k: (name, ok)))
    return _set


def _declared(project_path):
    return [d.path for d in load_project(project_path).documents]


def test_adding_an_outside_file_copies_it_into_the_project(open_window, example_project, choose_file, tmp_path):
    outside = tmp_path / "ailleurs" / "personnes.xml"
    outside.parent.mkdir()
    outside.write_text("<listPerson/>", encoding="utf-8")
    window = open_window(example_project)
    assert window.document_tab_bar.isHidden()

    choose_file(outside)
    assert window.add_document_dialog()
    copy = example_project.parent / "xml" / "personnes.xml"
    assert copy.read_text(encoding="utf-8") == "<listPerson/>"
    assert _declared(example_project) == [copy]
    assert window.document.path == copy and not window.document.modified
    assert not window.document_tab_bar.isHidden()
    assert window.document_tab_bar.count() == 2

    reopened = open_window(example_project)
    assert [s.path for s in reopened.documents[1:]] == [copy]


def test_adding_a_file_whose_name_is_taken_adds_a_suffix(open_window, project_with_documents, choose_file, tmp_path):
    outside = tmp_path / "personnes.xml"
    outside.write_text("<autre/>", encoding="utf-8")
    original = project_with_documents.parent / "xml" / "personnes.xml"
    before = original.read_text(encoding="utf-8")
    window = open_window(project_with_documents)

    choose_file(outside)
    assert window.add_document_dialog()
    copy = project_with_documents.parent / "xml" / "personnes_2.xml"
    assert copy.read_text(encoding="utf-8") == "<autre/>"
    assert original.read_text(encoding="utf-8") == before
    assert _declared(project_with_documents) == [original, copy]


def test_adding_a_file_inside_the_project_references_it(open_window, example_project, choose_file):
    notes = example_project.parent / "notes.xml"
    notes.write_text("<notes/>", encoding="utf-8")
    window = open_window(example_project)
    choose_file(notes)
    assert window.add_document_dialog()
    assert _declared(example_project) == [notes]
    assert not (example_project.parent / "xml" / "notes.xml").exists()


def test_adding_a_document_already_in_the_project_shows_it(open_window, project_with_documents, choose_file, dialogs):
    window = open_window(project_with_documents)
    before = project_with_documents.read_text(encoding="utf-8")
    choose_file(project_with_documents.parent / "xml" / "personnes.xml")
    dialogs.expect("information")
    assert window.add_document_dialog()
    assert window.document is window.documents[1]
    assert project_with_documents.read_text(encoding="utf-8") == before


def test_adding_an_unreadable_file_declares_nothing(open_window, example_project, choose_file, dialogs, tmp_path):
    binary = tmp_path / "image.xml"
    binary.write_bytes(b"\xff\xfe\x00\x81")
    window = open_window(example_project)
    choose_file(binary)
    dialogs.expect("critical")
    assert not window.add_document_dialog()
    assert _declared(example_project) == []
    assert ET.parse(example_project).getroot().find("documents") is None


def test_cancelling_the_file_choice_does_nothing(open_window, example_project, choose_file):
    window = open_window(example_project)
    choose_file(None)
    assert not window.add_document_dialog()
    assert not window.new_document_dialog()
    assert window.documents == [window.edition_session]


@pytest.mark.parametrize("root, tag", [
    ("listPlace", "listPlace"),
    ("TEI", "{http://www.tei-c.org/ns/1.0}TEI"),
])
def test_new_document_is_created_declared_and_displayed(open_window, example_project, choose_file, root_name, root, tag):
    target = example_project.parent / "xml" / "lieux.xml"
    window = open_window(example_project)
    choose_file(target)
    root_name(root)
    assert window.new_document_dialog()
    assert ET.parse(target).getroot().tag == tag
    assert _declared(example_project) == [target]
    assert window.document.path == target and not window.document.modified


def test_new_document_never_overwrites_a_file(open_window, project_with_documents, choose_file, root_name, dialogs):
    existing = project_with_documents.parent / "xml" / "personnes.xml"
    before = existing.read_text(encoding="utf-8")
    window = open_window(project_with_documents)
    choose_file(existing)
    root_name("TEI")
    dialogs.expect("warning")
    assert not window.new_document_dialog()
    assert existing.read_text(encoding="utf-8") == before


def test_new_document_with_an_invalid_root_name_is_refused(open_window, example_project, choose_file, root_name, dialogs):
    target = example_project.parent / "xml" / "lieux.xml"
    window = open_window(example_project)
    choose_file(target)
    root_name("1 lieu")
    dialogs.expect("warning")
    assert not window.new_document_dialog()
    assert not target.exists()
    assert _declared(example_project) == []


def test_removing_a_document_keeps_its_file(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    aux = window.documents[1]
    assert not window.action_remove_document.isEnabled()          # édition affichée
    window.show_document(aux)
    assert window.action_remove_document.isEnabled()

    dialogs.expect("question", Std.Yes)
    assert window.remove_document_from_project()
    assert aux.path.is_file()
    assert window.documents == [window.edition_session]
    assert window.document is window.edition_session
    assert window.document_tab_bar.isHidden()
    # Le projet redevient simple : plus d'élément <documents>.
    assert ET.parse(project_with_documents).getroot().find("documents") is None


def test_removing_a_modified_document_asks_about_its_changes(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    aux = window.documents[1]
    before = aux.path.read_text(encoding="utf-8")
    window.show_document(aux)
    window.editor.insertPlainText(" ")

    dialogs.expect("question", Std.Yes)                            # Retirer ?
    dialogs.expect("box", Role.DestructiveRole)                    # Ignorer les modifications
    assert window.remove_document_from_project()
    assert aux.path.read_text(encoding="utf-8") == before
    assert _declared(project_with_documents) == []


def test_declining_the_removal_keeps_the_document(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    window.show_document(window.documents[1])
    dialogs.expect("question", Std.No)
    assert not window.remove_document_from_project()
    assert len(window.documents) == 2
    assert len(_declared(project_with_documents)) == 1



# --- Feuilles XSLT (V0.9.2.1) ------------------------------------------------------------------

XSL = "{http://www.w3.org/1999/XSL/Transform}"


def test_the_add_dialog_offers_stylesheets(open_window, example_project, file_dialog_calls):
    window = open_window(example_project)
    calls = file_dialog_calls(None)
    assert window.action_add_document.text() == tr("documents.add.menu")
    assert not window.add_document_dialog()
    (parent, title, folder, filters), = calls
    assert filters.split(";;")[0] == "XML, XSLT (*.xml *.xsl *.xslt)"
    assert "XSLT (*.xsl *.xslt)" in filters.split(";;")


def test_adding_an_outside_stylesheet_copies_it_into_xslt(open_window, example_project, choose_file, tmp_path):
    outside = tmp_path / "ailleurs" / "index.xsl"
    outside.parent.mkdir()
    outside.write_text('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"/>',
                       encoding="utf-8")
    window = open_window(example_project)
    choose_file(outside)
    assert window.add_document_dialog()
    copy = example_project.parent / "xslt" / "index.xsl"
    assert copy.read_text(encoding="utf-8") == outside.read_text(encoding="utf-8")
    assert _declared(example_project) == [copy]
    assert window.document.path == copy
    assert window.statusBar().currentMessage() == tr("documents.add.copied", path=copy)


def test_new_stylesheet_is_created_in_xslt_declared_and_displayed(open_window, example_project,
                                                                  file_dialog_calls, stylesheet_version):
    window = open_window(example_project)
    assert window.action_new_stylesheet.text() == tr("documents.new_stylesheet.menu")
    assert window.action_new_stylesheet in window.documents_menu.actions()
    target = example_project.parent / "xslt" / "personnes.xsl"
    calls = file_dialog_calls(target)
    asked = stylesheet_version(1)
    assert window.new_stylesheet_dialog()
    (parent, title, proposed, filters), = calls
    assert title == tr("documents.new_stylesheet.title")
    assert Path(proposed) == example_project.parent / "xslt" / "nouvelle.xsl"
    assert filters == "XSLT (*.xsl *.xslt)"
    assert asked == [[tr("transform.engine.lxml"), tr("transform.engine.saxon")]]
    root = ET.parse(target).getroot()
    assert root.tag == XSL + "stylesheet" and root.get("version") == "3.0"
    assert _declared(example_project) == [target]
    assert window.document.path == target and not window.document.modified


def test_new_stylesheet_receives_the_xsl_suffix(open_window, example_project, choose_file, stylesheet_version):
    window = open_window(example_project)
    choose_file(example_project.parent / "xslt" / "index")
    stylesheet_version(0)
    assert window.new_stylesheet_dialog()
    target = example_project.parent / "xslt" / "index.xsl"
    assert ET.parse(target).getroot().get("version") == "1.0"
    assert _declared(example_project) == [target]


def test_new_stylesheet_never_overwrites_a_file(open_window, example_project, choose_file, stylesheet_version,
                                                dialogs):
    existing = example_project.parent / "xslt" / "index.xsl"
    existing.parent.mkdir()
    existing.write_text("<existant/>", encoding="utf-8")
    window = open_window(example_project)
    choose_file(existing)
    stylesheet_version(0)
    dialogs.expect("warning")
    assert not window.new_stylesheet_dialog()
    assert existing.read_text(encoding="utf-8") == "<existant/>"
    assert _declared(example_project) == []


def test_cancelling_the_new_stylesheet_creates_nothing(open_window, example_project, choose_file,
                                                       stylesheet_version):
    window = open_window(example_project)
    choose_file(None)
    assert not window.new_stylesheet_dialog()
    target = example_project.parent / "xslt" / "index.xsl"
    choose_file(target)
    stylesheet_version(0, ok=False)
    assert not window.new_stylesheet_dialog()
    assert not target.exists()
    assert _declared(example_project) == []


def test_the_documents_menu_follows_the_project_settings(open_window, example_project):
    # V0.9.2.1 : « Documents XML / XSLT du projet… », sous « Paramètres du projet… ».
    window = open_window(example_project)
    actions = window.file_menu.actions()
    position = actions.index(window.action_project_settings)
    assert actions[position + 1] is window.documents_menu.menuAction()
    assert window.documents_menu.title() == tr("documents.menu")
