# -*- coding: utf-8 -*-
"""Interface réservée à l'édition : aperçu, témoins et commandes associées
sont indisponibles quand un document auxiliaire est affiché, puis rétablis à
l'identique au retour sur l'édition."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app_context import tr


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def _witness_actions(window):
    return [window.action_reload_images, window.action_choose_witnesses,
            window.workspace_layout_menu.menuAction(), window.action_diagnose_witnesses,
            window.action_refresh_synchronizations]


def test_preview_is_reserved_to_the_edition(open_window, project_with_documents):
    window = open_window(project_with_documents)
    preview = window.left_tabs.indexOf(window.formatted_view)
    window.show_document(_aux(window))
    assert not window.left_tabs.isTabEnabled(preview)
    assert not window.action_preview.isEnabled()
    window.action_preview.trigger()
    assert window.left_tabs.currentIndex() == 0

    window.show_document(window.edition_session)
    assert window.left_tabs.isTabEnabled(preview)
    assert window.action_preview.isEnabled()


def test_leaving_the_preview_for_another_document_shows_the_source(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    window.left_tabs.setCurrentWidget(window.formatted_view)
    qtbot.wait(50)
    assert window.show_document(_aux(window))
    assert window.left_tabs.currentIndex() == 0


def test_witnesses_are_hidden_then_restored(open_window, project_with_documents):
    window = open_window(project_with_documents)
    assert not window.witness_scroll.isHidden()             # projet exemple : images locales
    sizes = window.main_splitter.sizes()
    enabled = [action.isEnabled() for action in _witness_actions(window)]
    assert any(enabled)

    window.show_document(_aux(window))
    assert window.witness_scroll.isHidden()
    assert window.structure_status.isHidden()
    assert not any(action.isEnabled() for action in _witness_actions(window))
    assert not window.action_save_as.isEnabled()
    assert window.action_save.text() == tr("menu.save_document")

    window.show_document(window.edition_session)
    assert not window.witness_scroll.isHidden()
    assert not window.structure_status.isHidden()
    assert window.main_splitter.sizes() == sizes
    assert [action.isEnabled() for action in _witness_actions(window)] == enabled
    assert window.action_save_as.isEnabled()
    assert window.action_save.text() == tr("menu.save_edition")


def test_detached_witness_window_is_hidden_then_shown_again(open_window, project_with_documents):
    window = open_window(project_with_documents)
    witness = window._visible_witness_ids[0]
    assert window._detach_witness(witness)
    detached = window._detached_windows[witness]
    assert detached.isVisible()

    window.show_document(_aux(window))
    assert not detached.isVisible()
    assert window._detached_windows.get(witness) is detached      # toujours détaché

    window.show_document(window.edition_session)
    assert detached.isVisible()


def test_structure_status_keeps_the_edition_count(open_window, project_with_documents):
    window = open_window(project_with_documents)
    status = window.structure_status.text()
    window.show_document(_aux(window))
    window.show_document(window.edition_session)
    assert window.structure_status.text() == status


def _open_modified_fragment(window, qtbot):
    window.left_tabs.setCurrentWidget(window.formatted_view)
    qtbot.wait(50)
    view = window.formatted_view
    assert view.load_fragment(0)
    view.fragment_editor.setPlainText(view.fragment_editor.toPlainText() + "FRAGMENT")
    assert view.fragment_has_unapplied_changes()
    return view


def test_cancelling_the_unapplied_fragment_keeps_the_edition_displayed(open_window, project_with_documents, dialogs, qtbot):
    window = open_window(project_with_documents)
    view = _open_modified_fragment(window, qtbot)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # Annuler
    assert not window.show_document(_aux(window))
    assert window.document is window.edition_session
    assert view.fragment_has_unapplied_changes()


def test_discarding_the_unapplied_fragment_leaves_the_edition_untouched(open_window, project_with_documents, dialogs, qtbot):
    window = open_window(project_with_documents)
    text = window.editor.toPlainText()
    view = _open_modified_fragment(window, qtbot)
    dialogs.expect("box", QMessageBox.ButtonRole.DestructiveRole)       # Ignorer
    assert window.show_document(_aux(window))
    assert view.frag_box.isHidden()
    assert window.edition_session.text_document.toPlainText() == text
    assert not window.edition_session.modified


def test_applying_the_unapplied_fragment_writes_it_into_the_edition(open_window, project_with_documents, dialogs, qtbot):
    window = open_window(project_with_documents)
    _open_modified_fragment(window, qtbot)
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)            # Appliquer
    assert window.show_document(_aux(window))
    assert "FRAGMENT" in window.edition_session.text_document.toPlainText()
    assert window.edition_session.modified


def test_language_change_while_another_document_is_displayed(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    assert window.rng_status.text() == tr("rng.status.valid")
    window.show_document(_aux(window))
    window._set_language_code("en")
    assert window.action_save.text() == tr("menu.save_document") == "Save document"

    window.show_document(window.edition_session)
    # Langue changée : l'état est recalculé, la validation repart en
    # arrière-plan (V0.8.9.2) ; attendre sa réponse, non un délai fixe.
    import validation_worker
    qtbot.wait(300)
    qtbot.waitUntil(lambda: not validation_worker.worker_client().busy, timeout=60000)
    qtbot.wait(50)
    assert window.action_save.text() == tr("menu.save_edition") == "Save edition"
    assert window.rng_status.text() == tr("rng.status.valid")
    assert window.xml_status.text() == tr("xml.valid")
