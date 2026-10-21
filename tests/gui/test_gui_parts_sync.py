# -*- coding: utf-8 -*-
"""Synchronisation des témoins suspendue pour une édition qui a des parties
(V0.9.0.0) : les témoins restent consultables en navigation libre, l'état de
structure le dit, et l'enregistrement ne vérifie pas le nombre de <lb/>.
Un projet sans xi:include garde sa synchronisation."""
from __future__ import annotations

import re

import pytest
from PySide6.QtGui import QTextCursor

from app_context import tr

XI = "http://www.w3.org/2001/XInclude"


@pytest.fixture
def example_with_part(example_project):
    """Projet exemple dont le sermon RLS_185 est passé dans une partie,
    xml/rls185.xml, incluse par l'édition."""
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start = text.index('<div xml:id="RLS_185">')
    end = text.index('<div xml:id="RLS_186">')
    part = text[start:end].rstrip()
    assert part.endswith("</div>")
    part = part.replace('<div xml:id="RLS_185">', '<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="RLS_185">', 1)
    (edition.parent / "rls185.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + part + "\n",
                                               encoding="utf-8")
    text = text[:start] + '<xi:include href="rls185.xml"/>\n' + text[end:]
    text = re.sub(r"<TEI\b", f'<TEI xmlns:xi="{XI}"', text, count=1)
    edition.write_text(text, encoding="utf-8")
    return example_project


def _cursor_at(window, needle):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index(needle))
    window.editor.setTextCursor(cursor)
    return cursor.position()


def test_the_witnesses_are_not_synchronized_for_an_edition_with_parts(open_window, example_with_part, qtbot):
    window = open_window(example_with_part)
    assert [s.path.name for s in window.documents if s.is_part] == ["rls185.xml"]
    assert window._witness_sync_suspended()
    assert window.structure_status.text() == tr("status.structure.suspended", base=window.base_id)
    assert window.structure_status.toolTip() == tr("status.structure.suspended.tip")
    # Le curseur ne déplace pas les témoins…
    _cursor_at(window, '<div xml:id="RLS_186">')
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal is None
    # … et un témoin ne déplace pas le curseur.
    position = window.editor.textCursor().position()
    window._primary_panel_navigate(40)
    window.navigate_to_base_ordinal(40)
    window.goto_xml_from_base()
    assert window.editor.textCursor().position() == position


def test_saving_an_edition_with_parts_does_not_check_the_lb_count(open_window, example_with_part):
    window = open_window(example_with_part)
    # Les <lb/> du sermon passé dans la partie manquent à l'édition : sans
    # suspension, l'enregistrement demanderait confirmation.
    assert window.expected_base_lines is not None and len(window.lb_spans()) != window.expected_base_lines
    cursor = window.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("<!-- essai -->")
    assert window.save()                                      # aucune boîte attendue


def test_the_witness_diagnostics_mention_the_suspension(open_window, example_with_part, dialogs):
    window = open_window(example_with_part)
    notes = []
    dialogs.expect("dialog", lambda dialog: notes.append(dialog.note.text()) or 0)
    window.show_witness_diagnostics()
    assert notes == [tr("diagnostics.sync_suspended")]


def test_an_edition_without_parts_keeps_its_synchronization(open_window, example_project, dialogs):
    window = open_window(example_project)
    assert not window._witness_sync_suspended()
    assert window.structure_status.text() == tr("status.structure.ok", base=window.base_id,
                                                count=window.expected_base_lines)
    _cursor_at(window, '<div xml:id="RLS_186">')
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal is not None
    notes = []
    dialogs.expect("dialog", lambda dialog: notes.append(dialog.note.isHidden()) or 0)
    window.show_witness_diagnostics()
    assert notes == [True]
