# -*- coding: utf-8 -*-
"""Complétion Ctrl+Espace guidée par le schéma RELAX NG, dans la vraie fenêtre."""
from __future__ import annotations


def _place_cursor_after(window, marker, typed=""):
    text = window.editor.toPlainText()
    pos = text.index(marker) + len(marker)
    cursor = window.editor.textCursor()
    cursor.setPosition(pos)
    window.editor.setTextCursor(cursor)
    if typed:
        window.editor.insertPlainText(typed)


def test_element_completion_proposes_schema_element_and_inserts_it(open_window, example_project, dialogs):
    window = open_window(example_project)
    # Enfants de la racine TEI, déclarée explicitement par le schéma de test.
    root_tag = window.editor.toPlainText().index("<TEI")
    _place_cursor_after(window, window.editor.toPlainText()[root_tag:].split(">", 1)[0] + ">")
    proposed = []

    def choose_varianstest(dialog):
        items = [dialog.list_widget.item(i) for i in range(dialog.list_widget.count())]
        proposed.extend(item.data(0x0100) for item in items)
        dialog.list_widget.setCurrentRow(proposed.index("varianstest"))
        dialog._accept_current()                    # comme la touche Entrée
        return dialog.result()

    dialogs.expect("dialog", choose_varianstest)
    window.show_rng_completion(window.editor)

    assert "varianstest" in proposed
    text = window.editor.toPlainText()
    start = text.index(">", text.index("<TEI")) + 1
    assert text[start:start + len("<varianstest")] == "<varianstest"


def test_attribute_completion_lists_required_attribute(open_window, example_project, dialogs):
    window = open_window(example_project)
    _place_cursor_after(window, "<body>", "<varianstest ")
    proposed = []

    def cancel(dialog):
        proposed.extend(dialog.list_widget.item(i).data(0x0100)
                        for i in range(dialog.list_widget.count()))
        return 0                                     # Échap : rien n'est inséré

    dialogs.expect("dialog", cancel)
    before = window.editor.toPlainText()
    window.show_rng_completion(window.editor)
    assert "kind" in proposed
    assert window.editor.toPlainText() == before
