# -*- coding: utf-8 -*-
"""Enregistrement et fermeture quand plusieurs documents sont ouverts."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app_context import tr

Std = QMessageBox.StandardButton
Role = QMessageBox.ButtonRole


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def _modify_edition(window):
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("<!-- édition -->")


def _modify_aux(window):
    window.show_document(_aux(window))
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("?>") + 2)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("<!-- personnes -->")


def _on_disk(session):
    return session.path.read_text(encoding="utf-8")


def test_only_the_edition_modified_keeps_the_usual_question(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    _modify_edition(window)
    window.show_document(aux)

    dialogs.expect("question", Std.Save)
    assert window.maybe_save() is True
    assert dialogs.seen[-1][2] == tr("file.unsaved.continue")
    assert "<!-- édition -->" in _on_disk(edition) and not edition.modified
    assert window.document is aux                        # affichage rétabli


def test_several_modified_documents_are_listed_and_can_be_kept(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    before = (_on_disk(edition), _on_disk(aux))
    _modify_edition(window)
    _modify_aux(window)

    dialogs.expect("box", Role.RejectRole)                           # Annuler
    assert window.maybe_save() is False
    _kind, _title, text = dialogs.seen[-1]
    assert "edition.xml" in text and "personnes.xml" in text
    assert (_on_disk(edition), _on_disk(aux)) == before
    assert edition.modified and aux.modified


def test_save_all_writes_every_modified_document(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    _modify_edition(window)
    _modify_aux(window)

    dialogs.expect("box", Role.AcceptRole)                           # Tout enregistrer
    assert window.maybe_save() is True
    assert "<!-- édition -->" in _on_disk(edition)
    assert "<!-- personnes -->" in _on_disk(aux)
    assert not edition.modified and not aux.modified


def test_discarding_writes_nothing(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    before = (_on_disk(edition), _on_disk(aux))
    _modify_edition(window)
    _modify_aux(window)

    dialogs.expect("box", Role.DestructiveRole)                      # Ignorer
    assert window.maybe_save() is True
    assert (_on_disk(edition), _on_disk(aux)) == before


def test_failed_save_stops_on_the_document_concerned(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    aux = _aux(window)
    _modify_edition(window)
    _modify_aux(window)
    window.editor.insertPlainText("<")                               # personnes.xml mal formé

    dialogs.expect("box", Role.AcceptRole)                           # Tout enregistrer
    dialogs.expect("box", Role.RejectRole)                           # XML mal formé : annuler
    assert window.maybe_save() is False
    assert window.document is aux and aux.modified


def test_quitting_with_only_an_auxiliary_document_modified(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    aux = _aux(window)
    _modify_aux(window)
    window.show_document(window.edition_session)

    dialogs.expect("box", Role.AcceptRole)                           # Tout enregistrer
    assert window.confirm_close_application() is True
    assert "personnes.xml" in dialogs.seen[-1][2]
    assert "<!-- personnes -->" in _on_disk(aux)


def test_quitting_with_only_the_edition_modified_keeps_the_usual_box(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition = window.edition_session
    _modify_edition(window)
    window.show_document(_aux(window))

    dialogs.expect("box", Role.AcceptRole)                           # Enregistrer et quitter
    assert window.confirm_close_application() is True
    assert dialogs.seen[-1][2] == tr("file.unsaved.quit.text")
    assert "<!-- édition -->" in _on_disk(edition)


def test_web_export_saves_the_edition_even_when_not_displayed(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    _modify_edition(window)
    _modify_aux(window)

    dialogs.expect("box", Role.RejectRole)                           # export terminé : fermer
    window.generate_web_viewer()
    assert dialogs.seen[-1][1] == tr("webgen.done.title")
    assert "<!-- édition -->" in _on_disk(edition) and not edition.modified
    assert aux.modified                                              # non concerné
    assert window.document is aux
