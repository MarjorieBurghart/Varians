# -*- coding: utf-8 -*-
"""Recherche dans l'aide (V0.9.2.8) : un champ en haut de la fenêtre
d'aide (Ctrl+F), la liste des sections qui contiennent les mots, les
occurrences surlignées et parcourues par ◀ ▶."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


@pytest.fixture
def help_dialog(open_window, example_project, qtbot):
    window = open_window(example_project)
    from help_dialogs import SoftwareHelpDialog
    dialog = SoftwareHelpDialog(window)
    qtbot.addWidget(dialog)
    dialog.show()
    qtbot.waitExposed(dialog)
    return dialog


def _search(dialog, query):
    dialog.search_box.setText(query)
    dialog.run_search()
    return [dialog.results.item(row).data(Qt.ItemDataRole.UserRole) for row in range(dialog.results.count())]


def test_the_help_is_searched_without_accents_or_case(help_dialog):
    dialog = help_dialog
    assert not dialog.results.isVisible()
    titles = _search(dialog, "EXPRESSIONS regulieres")
    assert "Rechercher et remplacer" in titles and "Aide-mémoire des expressions régulières" in titles
    assert dialog.results.isVisible()
    # Le sommaire, fait de liens, n'est pas un résultat.
    assert "Sommaire" not in titles
    count = len(dialog.occurrences)
    assert count >= len(titles) >= 2
    assert dialog.search_status.text() == _tr("help.search.summary", sections=len(titles), count=count)
    assert len(dialog.browser.extraSelections()) == count
    text = dialog.browser.toPlainText()
    start, end = dialog.occurrences[0]
    assert text[start:end].lower() in ("expressions", "régulières")


def test_previous_and_next_go_through_the_occurrences(help_dialog):
    dialog = help_dialog
    _search(dialog, "Ctrl+H")
    assert dialog.current == 0
    first = dialog.browser.textCursor().position()
    dialog.search_next.click()
    assert dialog.current == 1 and dialog.browser.textCursor().position() > first
    dialog.search_prev.click()
    dialog.search_prev.click()
    assert dialog.current == len(dialog.occurrences) - 1          # en boucle


def test_a_section_of_the_list_shows_its_first_occurrence(help_dialog):
    dialog = help_dialog
    titles = _search(dialog, "expressions regulieres")
    row = titles.index("Aide-mémoire des expressions régulières")
    dialog.results.setCurrentRow(row)
    start, _end = dialog.occurrences[dialog.current]
    heading = dialog.browser.toPlainText().index("Aide-mémoire des expressions régulières")
    assert start >= heading
    assert dialog.browser.textCursor().position() == start


def test_no_result_and_ctrl_f(help_dialog, qtbot):
    dialog = help_dialog
    assert _search(dialog, "zzzqqq") == []
    assert dialog.search_status.text() == _tr("help.search.none")
    assert dialog.browser.extraSelections() == []
    _search(dialog, "")
    assert not dialog.results.isVisible() and dialog.search_status.text() == ""
    dialog.activateWindow()
    dialog.browser.setFocus()
    qtbot.waitUntil(lambda: QApplication.focusWidget() is dialog.browser, timeout=3000)
    qtbot.keyClick(dialog.browser, Qt.Key.Key_F, Qt.KeyboardModifier.ControlModifier)
    assert QApplication.focusWidget() is dialog.search_box
    assert dialog.search_box.placeholderText() == _tr("help.search.placeholder")


def test_the_search_starts_while_typing(help_dialog, qtbot):
    dialog = help_dialog
    dialog.search_box.setText("Tout remplacer")
    qtbot.waitUntil(lambda: dialog.results.count() > 0, timeout=3000)
