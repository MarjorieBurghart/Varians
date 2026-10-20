# -*- coding: utf-8 -*-
"""Menu Fichier ▸ Documents XML du projet : ajouter, créer, retirer."""
from __future__ import annotations

import xml.etree.ElementTree as ET

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
