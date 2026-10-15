# -*- coding: utf-8 -*-
"""Saisie dans un long document, dans la vraie fenêtre.

En V0.8.5.26.2, chaque frappe dans une balise ouvrante non fermée au début du
projet exemple (≈ 530 000 caractères) prenait plusieurs dizaines de secondes
(recherche de la balise fermante de coût quadratique, xml_tag_pairs).
"""
from __future__ import annotations

import time


def _place_cursor(window, position):
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)


def test_typing_an_unclosed_opening_tag_stays_responsive(open_window, example_project):
    window = open_window(example_project)
    _place_cursor(window, window.editor.toPlainText().index("<body>") + len("<body>"))
    durations = []
    for key in ["<", "v", "a", " "]:
        start = time.perf_counter()
        window.editor.insertPlainText(key)          # une frappe, avec ses signaux
        durations.append(time.perf_counter() - start)
    assert "<body><va " in window.editor.toPlainText()
    assert max(durations) < 2.0, durations          # 23 à 39 s par frappe en V0.8.5.26.2


def test_renaming_an_opening_tag_still_renames_its_closing_tag(open_window, example_project):
    window = open_window(example_project)
    text = window.editor.toPlainText()
    opening = text.index("<p>", text.index("<body>"))
    _place_cursor(window, opening + len("<p"))       # juste après le nom « p »
    window.editor.insertPlainText("p")
    text = window.editor.toPlainText()
    assert text[opening:opening + 4] == "<pp>"
    # La fermeture correspondante est la première </…> qui équilibre la pile.
    from xml_tag_pairs import matching_closing_tag, opening_tag_at

    closing = matching_closing_tag(text, opening_tag_at(text, opening))
    assert closing is not None and closing.name == "pp"
