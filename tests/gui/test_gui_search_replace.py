# -*- coding: utf-8 -*-
"""Recherche et remplacement dans l'éditeur XML (V0.9.2.8) :
code_editor.find_in_plain_editor avec ses options (casse, expressions
régulières), replace_in_plain_editor et replace_all_in_plain_editor.
Un remplacement s'annule d'un seul Ctrl+Z et ne déclenche pas les
automatismes des paires de balises."""
from __future__ import annotations

import pytest

from text_search import SearchError, SearchOptions

LITERAL = SearchOptions()
CASE = SearchOptions(case_sensitive=True)
REGEX = SearchOptions(regex=True)


@pytest.fixture
def make_editor(qtbot, editor_module):
    def _make(text):
        editor = editor_module.CodeEditor()
        qtbot.addWidget(editor)
        editor.setPlainText(text)
        return editor
    return _make


def _highlighted(editor):
    start, end = editor._search_match
    cursor = editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
    return cursor.selectedText()


def test_the_search_follows_its_options(make_editor):
    from code_editor import find_in_plain_editor
    editor = make_editor("alpha BETA beta <rdg wit=\"#A\">x</rdg>")
    assert find_in_plain_editor(editor, "beta")[2] == 2                # comme avant
    assert find_in_plain_editor(editor, "beta", options=CASE) == (True, 1, 1)
    assert _highlighted(editor) == "beta"
    # Le surlignage couvre l'occurrence, non la longueur de l'expression.
    assert find_in_plain_editor(editor, r"<rdg[^>]*>", options=REGEX) == (True, 1, 1)
    assert _highlighted(editor) == '<rdg wit="#A">'
    assert not editor.textCursor().hasSelection()
    with pytest.raises(SearchError):
        find_in_plain_editor(editor, "a(b", options=REGEX)


def test_the_positions_are_right_after_a_character_beyond_u_ffff(make_editor):
    from code_editor import find_in_plain_editor, replace_all_in_plain_editor
    editor = make_editor("\U0001d51e beta \U0001d51e beta")
    assert find_in_plain_editor(editor, "beta") == (True, 1, 2)
    assert _highlighted(editor) == "beta"
    assert replace_all_in_plain_editor(editor, "beta", "lem") == 2
    assert editor.toPlainText() == "\U0001d51e lem \U0001d51e lem"


def test_replace_changes_the_highlighted_occurrence_then_goes_to_the_next(make_editor):
    from code_editor import replace_in_plain_editor
    editor = make_editor("<rdg>a</rdg> <rdg>b</rdg>")
    # Rien n'est surligné : le premier appel trouve sans remplacer.
    assert replace_in_plain_editor(editor, "<rdg>", "<lem>") == (False, (True, 1, 2))
    assert editor.toPlainText() == "<rdg>a</rdg> <rdg>b</rdg>"
    assert replace_in_plain_editor(editor, "<rdg>", "<lem>") == (True, (True, 1, 1))
    # La fermeture n'est pas renommée avec l'ouverture : on remplace ce
    # qu'on a trouvé, rien de plus.
    assert editor.toPlainText() == "<lem>a</rdg> <rdg>b</rdg>"
    assert _highlighted(editor) == "<rdg>" and editor._search_match[0] == 13
    editor.undo()
    assert editor.toPlainText() == "<rdg>a</rdg> <rdg>b</rdg>"


def test_a_changed_occurrence_is_not_replaced(make_editor):
    from code_editor import find_in_plain_editor, replace_in_plain_editor
    editor = make_editor("beta gamma beta")
    find_in_plain_editor(editor, "beta")
    cursor = editor.textCursor()
    cursor.setPosition(0)
    cursor.insertText("x")                       # « xbeta » : l'occurrence surlignée a bougé
    replaced, found = replace_in_plain_editor(editor, "beta", "B")
    assert not replaced and found[0] and editor.toPlainText() == "xbeta gamma beta"


def test_replace_all_is_undone_in_one_step_and_keeps_the_closing_tags(make_editor):
    from code_editor import replace_all_in_plain_editor
    editor = make_editor("<rdg>a</rdg> <rdg>b</rdg>")
    assert replace_all_in_plain_editor(editor, "rdg", "lem") == 4
    assert editor.toPlainText() == "<lem>a</lem> <lem>b</lem>"
    editor.undo()
    assert editor.toPlainText() == "<rdg>a</rdg> <rdg>b</rdg>"
    # Une ouverture remplacée par rien : sa fermeture reste.
    assert replace_all_in_plain_editor(editor, "<rdg>", "", options=CASE) == 2
    assert editor.toPlainText() == "a</rdg> b</rdg>"


def test_replace_all_with_a_regular_expression_uses_its_groups(make_editor):
    from code_editor import replace_all_in_plain_editor
    text = '<rdg wit="#A">x</rdg>\n<rdg wit="#B">y</rdg>'
    editor = make_editor(text)
    assert replace_all_in_plain_editor(editor, r'wit="#(\w+)"', r'wit="#\1 #T3"', options=REGEX) == 2
    assert editor.toPlainText() == '<rdg wit="#A #T3">x</rdg>\n<rdg wit="#B #T3">y</rdg>'
    with pytest.raises(SearchError):
        replace_all_in_plain_editor(editor, "(x)", r"\2", options=REGEX)
    assert replace_all_in_plain_editor(editor, "absent", "y") == 0
    assert editor.toPlainText().startswith('<rdg wit="#A #T3">')
