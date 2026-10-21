# -*- coding: utf-8 -*-
"""Édition assemblée par XInclude, dans la fenêtre : F12 d'une partie à
l'autre, commande « Références », identifiants proposés, schéma de la
complétion et « Débugger l'apparat » dans une partie. Projet « sermons »."""
from __future__ import annotations

from app_context import tr


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _choose(setup):
    def answer(dialog):
        setup(dialog)
        dialog.accept()
        return dialog.result()
    return answer


def test_f12_goes_from_one_part_to_another(open_window, sermons_project, qtbot):
    window = open_window(sermons_project)
    window.show_document(_doc(window, "s01.xml"))
    text = window.editor.toPlainText()
    assert window.go_to_reference(text.index("#s03_p1") + 1)
    qtbot.wait(20)
    assert window.document is _doc(window, "s03.xml")
    assert window.editor.textCursor().selectedText().startswith('<p xml:id="s03_p1"')
    line = window.editor.toPlainText()[:window.editor.textCursor().selectionStart()].count("\n") + 1
    # « #s03_p1 » est correct dans l'édition assemblée : pas d'invitation à
    # écrire « s03.xml#s03_p1 ».
    assert window.statusBar().currentMessage() == tr("references.jumped", file="s03.xml", line=line)
    assert window.go_back()
    assert window.document is _doc(window, "s01.xml")


def test_only_the_missing_sermon_is_reported(open_window, sermons_project):
    window = open_window(sermons_project)
    window.check_references()
    table = window.references_table
    rows = [(table.item(row, 0).text(), table.item(row, 3).text()) for row in range(table.rowCount())]
    assert rows == [("s04.xml", "#s05")]


def test_ids_of_the_other_parts_are_proposed_as_short_pointers(open_window, sermons_project):
    window = open_window(sermons_project)
    window.show_document(_doc(window, "s01.xml"))
    values = [value for value, _description, _element in window._reference_id_entries()]
    assert "#s02_p1" in values and "#s01_p1" in values
    assert "s02.xml#s02_p1" not in values
    # Témoins : ceux de l'édition (#A) ; E n'est déclaré que dans l'en-tête
    # de s03, hors de l'édition assemblée : forme explicite.
    witnesses = [value for value, _d, _e in window._reference_id_entries(frozenset({"witness"}))]
    assert "#A" in witnesses and "s03.xml#E" in witnesses and "#E" not in witnesses
    assert len(values) == len(set(values))


def test_a_part_uses_the_schema_of_the_edition_for_completion(open_window, collection_project):
    window = open_window(collection_project)
    window.show_document(_doc(window, "s01.xml"))
    assert window._resolve_completion_schema().schema_path.name == "collection.rng"


def test_debugging_the_apparatus_of_a_part_uses_its_witnesses(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)
    window.show_document(_doc(window, "s01.xml"))
    labels = []

    def incomplete(dialog):
        labels.append(dialog.witnesses_label.text())
        dialog.incomplete_radio.setChecked(True)

    dialogs.expect("dialog", _choose(incomplete))
    assert window.debug_apparatus()
    assert labels == [tr("apparatus.witnesses.wit", ids="A, B, C")]
    assert window.xpath_table.rowCount() == 1                           # « vigilantes »


def test_a_part_with_its_own_list_wit(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)
    window.show_document(_doc(window, "s03.xml"))
    labels = []
    dialogs.expect("dialog", lambda dialog: labels.append(dialog.witnesses_label.text()) or 0)
    window.debug_apparatus()
    assert labels == [tr("apparatus.witnesses.part", ids="A, C, D, E")]
