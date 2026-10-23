# -*- coding: utf-8 -*-
"""Synchronisation des témoins à travers les parties (V0.9.1.0, numérotation
continue). Projet exemple dont le sermon RLS_185 est passé dans une partie,
xml/rls185.xml : l'édition garde 3625 lignes du pivot T1, la partie en a 165 ;
le total, 3790, est celui de T1.json. RLS_185 occupe les lignes 116 à 280,
comme dans l'édition en un seul fichier."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

import document_tabs
from app_context import tr

LB = '<lb edRef="#T1"/>'


def _part(window):
    return next(s for s in window.documents if s.is_part)


def _cursor_at(window, needle, start=0):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index(needle, start))
    window.editor.setTextCursor(cursor)
    return cursor.position()


def _lb_after(window, needle):
    """Place le curseur sur le premier <lb/> du pivot qui suit ``needle``."""
    text = window.editor.toPlainText()
    return _cursor_at(window, LB, text.index(needle))


def test_the_lines_of_the_pivot_are_counted_in_the_assembled_edition(open_window, example_with_part):
    window = open_window(example_with_part)
    assert window.expected_base_lines == 3790
    ok = tr("status.structure.ok", base="T1", count=3790)
    assert window.structure_status.text() == ok
    assert window.structure_status.toolTip() == tr("status.structure.assembled.tip")
    window.show_document(_part(window))
    window._rebuild_lb_cache()
    assert window.structure_status.text() == ok


def test_the_cursor_of_a_part_moves_the_witnesses(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    window.show_document(_part(window))
    _cursor_at(window, LB)
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal == 116
    assert window.base_panel.center_index == 116
    assert window.panels["T2"].primary_key == window.base_items[116]["key"]
    # Le curseur, déplacé dans la partie, fait suivre les témoins.
    _lb_after(window, "proprie")
    qtbot.waitUntil(lambda: window._last_synced_ordinal == 279, timeout=2000)


def test_the_edition_after_the_part_is_shifted(open_window, example_with_part):
    window = open_window(example_with_part)
    _cursor_at(window, '<div xml:id="RLS_186">')
    assert window._base_ordinal_at_cursor() == 280          # dernière ligne de la partie
    _lb_after(window, '<div xml:id="RLS_186">')
    assert window._base_ordinal_at_cursor() == 281
    _lb_after(window, '<div xml:id="RLS_205">')
    assert window._base_ordinal_at_cursor() == 3604
    _lb_after(window, '<div xml:id="RLS_184">')
    assert window._base_ordinal_at_cursor() == 1            # avant la partie : inchangé


def test_a_click_in_the_pivot_opens_the_part_of_the_line(open_window, example_with_part):
    window = open_window(example_with_part)
    part = _part(window)
    window.hide_document_tab(part)
    window._primary_panel_navigate(200)
    assert window.document is part
    assert part not in window._hidden_documents               # onglet réaffiché
    assert window.editor.textCursor().position() == window.lb_spans()[84][1]
    assert window._last_synced_ordinal == 200
    assert window.panels["T2"].primary_key == window.base_items[200]["key"]
    window._primary_panel_navigate(300)
    assert window.document is window.edition_session
    assert window.editor.textCursor().position() == window.lb_spans()[135][1]
    window.navigate_to_base_ordinal(116)
    assert window.document is part
    assert window.editor.textCursor().position() == window.lb_spans()[0][1]


def test_typing_in_a_part_keeps_the_numbering_until_a_line_is_added(open_window, example_with_part,
                                                                    dialogs, monkeypatch):
    window = open_window(example_with_part)
    assert window._pivot_lines().count == 3790
    calls = []
    real = document_tabs.pivot_lines
    monkeypatch.setattr(document_tabs, "pivot_lines", lambda *args, **kw: calls.append(1) or real(*args, **kw))
    window.show_document(_part(window))
    _lb_after(window, "proprie")
    window.editor.textCursor().insertText("abc ")
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal == 279 and calls == []
    window.editor.textCursor().insertText(LB)
    window._rebuild_lb_cache()
    assert len(calls) == 1 and window._pivot_lines().count == 3791
    assert window.structure_status.text() == tr("status.structure.changed", base="T1", count=3791, expected=3790)
    dialogs.expect("warning", QMessageBox.StandardButton.Cancel)
    assert not window.save()
    assert dialogs.seen[-1][2] == tr("file.structure.text", count=3791, base="T1", expected=3790)


def _witness_actions(window):
    return [window.action_reload_images, window.action_choose_witnesses,
            window.workspace_layout_menu.menuAction(), window.action_diagnose_witnesses,
            window.action_refresh_synchronizations]


def test_the_witnesses_stay_on_a_part_and_leave_on_an_auxiliary_document(open_window, example_with_part,
                                                                         project_with_documents):
    window = open_window(example_with_part)
    preview = window.left_tabs.indexOf(window.formatted_view)
    witness = window._visible_witness_ids[0]
    assert window._detach_witness(witness)
    detached = window._detached_windows[witness]
    sizes = window.main_splitter.sizes()
    enabled = [action.isEnabled() for action in _witness_actions(window)]
    assert any(enabled)

    def witnesses_shown():
        return (not window.witness_scroll.isHidden() and not window.structure_status.isHidden()
                and detached.isVisible() and [a.isEnabled() for a in _witness_actions(window)] == enabled)

    window.show_document(_part(window))
    assert witnesses_shown()
    # L'aperçu de l'édition assemblée reste disponible (V0.9.1.5).
    assert window.left_tabs.isTabEnabled(preview) and window.action_preview.isEnabled()
    assert not window.action_save_as.isEnabled()
    aux = next(s for s in window.documents if s.is_auxiliary)
    window.show_document(aux)
    assert not window.left_tabs.isTabEnabled(preview) and not window.action_preview.isEnabled()
    assert window.witness_scroll.isHidden() and window.structure_status.isHidden()
    assert not detached.isVisible()
    assert not any(action.isEnabled() for action in _witness_actions(window))
    window.show_document(_part(window))
    assert witnesses_shown() and window.main_splitter.sizes() == sizes
    window.show_document(window.edition_session)
    assert witnesses_shown()
    assert window.left_tabs.isTabEnabled(preview)
    assert window.action_preview.isEnabled() and window.action_save_as.isEnabled()


def test_an_edition_without_parts_keeps_its_synchronization(open_window, example_project):
    window = open_window(example_project)
    assert window._pivot_lines() is None
    assert window.structure_status.text() == tr("status.structure.ok", base="T1", count=3790)
    assert window.structure_status.toolTip() == ""
    # Même ligne que dans l'édition découpée.
    _cursor_at(window, '<div xml:id="RLS_186">')
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal == 280
    window._primary_panel_navigate(200)
    assert window.editor.textCursor().position() == window.lb_spans()[200][1]
