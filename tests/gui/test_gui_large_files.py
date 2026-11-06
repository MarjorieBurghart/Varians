# -*- coding: utf-8 -*-
"""Fichiers trop volumineux : Varians demande avant d'ouvrir un projet dont
l'édition dépasse le seuil, ou d'afficher un document qui le dépasse
(« Annuler » : rien ne change)."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

import large_files
from app_context import tr


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def test_opening_a_large_project_from_varians_asks_first(open_window, example_project, editor_module, dialogs,
                                                         monkeypatch, qtbot, tmp_path):
    from corpus_data import copy_example
    window = open_window(example_project)
    other = copy_example(tmp_path / "autre")
    monkeypatch.setattr(large_files, "LARGE_FILE_BYTES", 1000)
    # Modification non enregistrée : la question de taille vient d'abord ;
    # « Annuler » ne propose pas d'enregistrer et ne change rien.
    window.editor.insertPlainText(" ")
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert window._replace_with_project(other) is False
    kind, title, text = dialogs.seen[-1]
    assert title == tr("large_file.title")
    assert str(other.parent / "xml" / "edition.xml") in text
    assert window.project.path == example_project
    assert window.isVisible()

    welcome = editor_module.WelcomeWindow()                  # « Ouvrir un projet… » de l'accueil
    qtbot.addWidget(welcome)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert welcome._open_project_path(other) is False
    assert welcome._replacement_window is None


def test_showing_a_large_document_asks_first(open_window, project_with_documents, dialogs, monkeypatch):
    window = open_window(project_with_documents)
    aux = _aux(window)
    monkeypatch.setattr(large_files, "LARGE_FILE_BYTES", 10)

    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert window.show_document(aux) is False
    assert window.document is window.edition_session
    assert aux.text_document is None                      # pas lu
    kind, title, text = dialogs.seen[-1]
    assert title == tr("large_file.title") and str(aux.path) in text

    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    assert window.show_document(aux) is True
    assert window.document is aux

    # Déjà chargé : on y revient sans question.
    assert window.show_document(window.edition_session)
    assert window.show_document(aux) is True
