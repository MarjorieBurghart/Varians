# -*- coding: utf-8 -*-
"""Documents XML auxiliaires affichés dans la fenêtre, à côté de l'édition."""
from __future__ import annotations

from app_context import tr


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def _type_at(window, position, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def _after_declaration(window):
    return window.editor.toPlainText().index("?>") + 2


def test_simple_project_has_only_the_edition(open_window, example_project):
    window = open_window(example_project)
    assert window.documents == [window.edition_session]
    assert window.document is window.edition_session
    assert window.edition_session.is_edition


def test_declared_documents_are_listed_and_loaded_on_demand(open_window, project_with_documents):
    window = open_window(project_with_documents)
    aux = _aux(window)
    assert aux.role == "auxiliary" and aux.label == "Personnes"
    assert aux.path == project_with_documents.parent / "xml" / "personnes.xml"
    assert aux.text_document is None                     # pas encore lu
    assert window.document is window.edition_session


def test_showing_an_auxiliary_document_and_coming_back(open_window, project_with_documents):
    window = open_window(project_with_documents)
    edition = window.edition_session
    edition_text = window.editor.toPlainText()
    aux = _aux(window)

    assert window.show_document(aux)
    assert window.document is aux
    assert window.editor.document() is aux.text_document
    assert window.editor.toPlainText() == aux.path.read_text(encoding="utf-8")
    assert window.current_path == aux.path
    assert "personnes.xml" in window.windowTitle()
    assert aux.modified is False
    assert aux.highlighter is not None and aux.highlighter.document() is aux.text_document

    assert window.show_document(edition)
    assert window.document is edition
    assert window.editor.toPlainText() == edition_text
    assert "edition.xml" in window.windowTitle()


def test_each_document_has_its_own_undo_history_and_modified_state(open_window, project_with_documents):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    body = window.editor.toPlainText().index("<body>") + len("<body>")
    _type_at(window, body, "X")
    assert edition.modified

    window.show_document(aux)
    assert aux.modified is False
    assert not window.editor.document().isUndoAvailable()
    _type_at(window, _after_declaration(window), "<!-- Y -->")
    assert aux.modified and "*" in window.windowTitle()

    window.show_document(edition)
    text = window.editor.toPlainText()
    assert text[body] == "X" and "<!-- Y -->" not in text
    window.editor.undo()
    assert window.editor.toPlainText()[body] != "X"
    assert "?><!-- Y -->" in aux.text_document.toPlainText()


def test_edition_state_survives_a_visit_to_another_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    edition = window.edition_session
    spans = list(window.lb_spans())
    rng_status = window.rng_status.text()
    cursor = window.editor.textCursor()
    cursor.setPosition(spans[20][1])
    window.editor.setTextCursor(cursor)

    window.show_document(_aux(window))
    cursor = window.editor.textCursor()
    cursor.setPosition(10)
    window.editor.setTextCursor(cursor)
    window.show_document(edition)

    assert not edition.lb.dirty and edition.lb.spans == spans
    assert window.editor.textCursor().position() == spans[20][1]
    assert window.rng_status.text() == rng_status
    window.show_document(_aux(window))
    assert window.editor.textCursor().position() == 10


def test_auxiliary_document_is_validated_with_its_own_schema(open_window, project_with_documents, qtbot):
    # Pas de <?xml-model?> dans personnes.xml : aucun schéma, alors que
    # l'édition est validée par test.rng.
    window = open_window(project_with_documents)
    window.show_document(_aux(window))
    qtbot.wait(300)
    assert window.rng_status.text() == tr("rng.status.no_xml_model")
    assert window.xml_status.text() == tr("xml.valid")
    assert window.validation_table.rowCount() == 0


def test_save_writes_only_the_displayed_document(open_window, project_with_documents):
    # Aucune boîte de dialogue attendue : le contrôle du nombre de <lb/> du
    # témoin pivot ne concerne que l'édition.
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    edition_on_disk = edition.path.read_text(encoding="utf-8")
    _type_at(window, window.editor.toPlainText().index("<body>") + len("<body>"), "X")

    window.show_document(aux)
    _type_at(window, _after_declaration(window), "<!-- Y -->")
    assert window.save()

    assert "?><!-- Y -->" in aux.path.read_text(encoding="utf-8")
    assert aux.modified is False and edition.modified is True
    assert edition.path.read_text(encoding="utf-8") == edition_on_disk


def test_panel_writes_into_the_edition_are_refused_elsewhere(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    edition, aux = window.edition_session, _aux(window)
    edition_text = window.editor.toPlainText()
    window.show_document(aux)
    aux_text = window.editor.toPlainText()

    dialogs.expect("information")
    window.base_panel.markPageRequested.emit(window.base_id, "T1-p0001", "1r")
    dialogs.expect("information")
    window.base_panel.splitFolioRequested.emit(window.base_id, "T1-p0001")

    assert [title for _kind, title, _text in dialogs.seen] == [tr("documents.edition_required.title")] * 2
    assert window.editor.toPlainText() == aux_text and not aux.modified
    assert edition.text_document.toPlainText() == edition_text and not edition.modified


def test_witness_navigation_leaves_the_auxiliary_document_alone(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window.show_document(_aux(window))
    cursor = window.editor.textCursor()
    cursor.setPosition(5)
    window.editor.setTextCursor(cursor)
    assert not window.sync_timer.isActive()           # pas de synchronisation des témoins

    window.base_panel.primaryNavigate.emit(3)
    window.navigate_to_base_ordinal(3)
    assert window.document is _aux(window)
    assert window.editor.textCursor().position() == 5


def test_late_xml_check_of_another_document_is_ignored(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window._xml_health_session = window.edition_session    # contrôle lancé sur l'édition…
    window._xml_health_running = True
    aux = _aux(window)
    window.show_document(aux)                              # … qui n'est plus affichée
    window._async_xml_health_finished(aux.text_document.revision(), False, 1, 0, "erreur", None)
    assert aux.health == "normal"
    assert window.xml_status.text() == tr("xml.valid")
    assert not window._xml_health_running


def test_missing_document_file_is_reported(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    aux = _aux(window)
    aux.path.unlink()
    dialogs.expect("critical")
    assert not window.show_document(aux)
    assert window.document is window.edition_session
