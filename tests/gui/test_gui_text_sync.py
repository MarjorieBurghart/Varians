# -*- coding: utf-8 -*-
"""Textes synchronisés à part (V0.9.1.1) : quand le document affiché passe
d'un segment à l'autre (l'édition, ou un texte qui a son dossier
alignments/<texte>/), les panneaux des témoins reçoivent les données de ce
segment, avec son pivot.

- Projet exemple, RLS_185 dans xml/rls185.xml et synchronisé à part
  (alignments/rls185/T1.json et T2.json ; P n'a pas ce texte) : l'édition
  garde 3625 lignes de T1, le texte en a 165.
- Jeu « corpus » (tests/corpus_data.py) : s02 a B pour pivot."""
from __future__ import annotations

from app_context import tr

LB = '<lb edRef="#T1"/>'


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _cursor_at(window, needle, start=0):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index(needle, start))
    window.editor.setTextCursor(cursor)


def test_each_segment_has_its_own_lines(open_window, example_with_text):
    window = open_window(example_with_text)
    assert window._active_segment is None
    assert window.structure_status.text() == tr("status.structure.ok", base="T1", count=3625)
    window.show_document(_doc(window, "rls185.xml"))
    assert window._active_segment is not None
    assert window.structure_status.text() == tr("status.structure.ok", base="T1", count=165)
    assert window.structure_status.toolTip() == tr("status.structure.text.tip", base="T1", name="rls185")
    assert len(window.base_items) == 165 and window.expected_base_lines == 165
    # Retour sur l'édition, déjà affichée : son état de structure revient.
    window.show_document(window.edition_session)
    assert window.structure_status.text() == tr("status.structure.ok", base="T1", count=3625)
    assert window.structure_status.toolTip() == tr("status.structure.assembled.tip")


def test_the_cursor_of_a_text_uses_its_own_alignments(open_window, example_with_text):
    window = open_window(example_with_text)
    window.show_document(_doc(window, "rls185.xml"))
    _cursor_at(window, LB)
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal == 0
    assert window.base_panel.center_index == 0
    assert window.panels["T2"].primary_key == window.base_items[0]["key"]
    # P n'a pas de JSON pour ce texte : son panneau reste, avec un message.
    absent = window.panels["P"]
    assert absent.absent_key == "manuscript.text_absent" and absent.items == []
    assert absent.message.text() == tr("manuscript.text_absent")
    # Un clic dans le pivot reste dans le texte.
    window._primary_panel_navigate(500)
    assert window.document is _doc(window, "rls185.xml")
    assert window.editor.textCursor().position() == window.lb_spans()[164][1]


def test_coming_back_to_the_edition_restores_its_alignments(open_window, example_with_text):
    window = open_window(example_with_text)
    global_key = window.base_items[116]["key"]
    window.show_document(_doc(window, "rls185.xml"))
    window.show_document(window.edition_session)
    assert window._active_segment is None and len(window.base_items) == 3625
    assert window.panels["P"].absent_key is None and window.panels["P"].items
    # Dans l'édition, RLS_186 suit directement RLS_184 : ligne 116.
    _cursor_at(window, LB, window.editor.toPlainText().index('<div xml:id="RLS_186">'))
    window.sync_panels_to_cursor(True)
    assert window._last_synced_ordinal == 116
    assert window.base_items[116]["key"] == global_key


def test_the_layout_and_detached_windows_stay_in_place(open_window, example_with_text):
    window = open_window(example_with_text)
    assert window._detach_witness("T2")
    detached = window._detached_windows["T2"]
    visible = list(window._visible_witness_ids)
    window.show_document(_doc(window, "rls185.xml"))
    assert detached.isVisible() and window._detached_windows["T2"] is detached
    assert window._visible_witness_ids == visible
    assert not window.panels["P"].isHidden()


def test_a_text_with_its_own_pivot(open_window, corpus_project):
    window = open_window(corpus_project)
    assert window.base_id == "A" and window.base_panel is window.panels["A"]
    window.show_document(_doc(window, "s02.xml"))
    assert window.base_id == "B" and window.base_panel is window.panels["B"]
    assert window.panels["B"].is_base and not window.panels["A"].is_base
    assert len(window.lb_spans()) == 8                     # <lb edRef="#B"/>
    assert window.panels["A"].absent_key == "manuscript.text_absent"
    assert window.panels["D"].absent_key is None
    window._rebuild_lb_cache()
    assert window.structure_status.text() == tr("status.structure.ok", base="B", count=8)
    window.show_document(window.edition_session)
    assert window.base_id == "A" and window.panels["A"].is_base and not window.panels["B"].is_base
    assert window.panels["A"].absent_key is None
    assert len(window.lb_spans()) == 0                      # l'édition n'a pas de ligne de A


def test_a_nested_part_belongs_to_the_segment_of_its_text(open_window, corpus_project):
    window = open_window(corpus_project)
    window.show_document(_doc(window, "s04.xml"))
    segment = window._active_segment
    window.show_document(_doc(window, "s04_exemplum.xml"))
    assert window._active_segment == segment
    assert window._base_line_count() == 8                  # 5 dans s04, 3 dans l'exemplum
