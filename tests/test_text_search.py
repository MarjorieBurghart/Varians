# -*- coding: utf-8 -*-
"""Moteur de recherche et de remplacement du XML et du fragment (V0.9.2.8),
sans Qt : text_search.py. Recherche littérale ou par expression régulière,
casse respectée ou non ; positions Python et positions Qt (UTF-16)."""
from __future__ import annotations

import pytest

from text_search import SearchError, SearchOptions, Utf16Positions, find_spans, match_at, replacements

LITERAL = SearchOptions()
CASE = SearchOptions(case_sensitive=True)
REGEX = SearchOptions(regex=True)
REGEX_CASE = SearchOptions(case_sensitive=True, regex=True)


def test_the_literal_search_ignores_the_case_and_keeps_overlapping_occurrences():
    assert find_spans("alpha BETA beta beta", "beta", LITERAL) == [(6, 10), (11, 15), (16, 20)]
    # Les occurrences qui se chevauchent comptent, comme avant la 0.9.2.8.
    assert find_spans("aaa", "aa", LITERAL) == [(0, 2), (1, 3)]
    # Un caractère spécial d'expression régulière reste un caractère.
    assert find_spans("a.b axb", "a.b", LITERAL) == [(0, 3)]
    assert find_spans("texte", "", LITERAL) == []


def test_the_case_can_be_respected():
    assert find_spans("alpha BETA beta", "beta", CASE) == [(11, 15)]
    assert find_spans("alpha BETA beta", "BETA", CASE) == [(6, 10)]
    assert find_spans("Beta beta", r"\bB\w+", REGEX_CASE) == [(0, 4)]
    assert find_spans("Beta beta", r"\bB\w+", REGEX) == [(0, 4), (5, 9)]


def test_a_regular_expression_finds_each_line_and_no_empty_match():
    text = '<rdg wit="#A">regem</rdg>\n<rdg wit="#B">reges</rdg>'
    assert [text[a:b] for a, b in find_spans(text, r'wit="#\w+"', REGEX)] == ['wit="#A"', 'wit="#B"']
    # ^ et $ : début et fin de chaque ligne.
    assert find_spans(text, r"^<rdg", REGEX) == [(0, 4), (26, 30)]
    assert find_spans(text, r"</rdg>$", REGEX) == [(19, 25), (45, 51)]
    # Une correspondance vide n'est pas une occurrence.
    assert find_spans("abc", "x*", REGEX) == []
    assert find_spans("axxb", "x*", REGEX) == [(1, 3)]


def test_an_incorrect_expression_is_reported():
    with pytest.raises(SearchError) as error:
        find_spans("abc", "a(b", REGEX)
    assert error.value.code == "pattern_invalid" and "missing )" in error.value.detail
    # Le même texte, en recherche littérale, se cherche tel quel.
    assert find_spans("a(b", "a(b", LITERAL) == [(0, 3)]


def test_an_occurrence_is_checked_where_it_is():
    text = "alpha BETA beta"
    assert match_at(text, 6, 10, "beta", LITERAL) is not None
    assert match_at(text, 6, 10, "beta", CASE) is None
    assert match_at(text, 6, 9, "beta", LITERAL) is None              # pas toute l'occurrence
    assert match_at(text, 11, 15, r"b\w+", REGEX).group(0) == "beta"
    assert match_at(text, 30, 34, "beta", LITERAL) is None


def test_the_literal_replacements_do_not_overlap_and_keep_the_text_as_is():
    assert replacements("rdg <rdg>", "rdg", "lem", LITERAL) == [(0, 3, "lem"), (5, 8, "lem")]
    assert replacements("aaaa", "aa", "b", LITERAL) == [(0, 2, "b"), (2, 4, "b")]
    # \1 n'a pas de sens hors des expressions régulières : il est écrit tel quel.
    assert replacements("ab", "a", r"\1", LITERAL) == [(0, 1, r"\1")]
    assert replacements("Rdg rdg", "rdg", "lem", CASE) == [(4, 7, "lem")]


def test_a_regular_expression_replacement_uses_its_groups():
    text = '<rdg wit="#A">x</rdg> <rdg wit="#B">y</rdg>'
    found = replacements(text, r'wit="#(\w+)"', r'wit="#\1 #T3"', REGEX)
    assert [value for _a, _b, value in found] == ['wit="#A #T3"', 'wit="#B #T3"']
    named = replacements("Magnates", r"(?P<debut>Mag)nates", r"\g<debut>na", REGEX)
    assert named == [(0, 8, "Magna")]
    assert replacements("a b", " ", r"\n", REGEX) == [(1, 2, "\n")]
    with pytest.raises(SearchError) as error:
        replacements("ab", "(a)", r"\2", REGEX)
    assert error.value.code == "template_invalid"


def test_python_and_qt_positions_differ_after_a_character_beyond_u_ffff():
    text = "a\U0001d51eb\U0001d51ec"                       # a 𝔞 b 𝔞 c
    positions = Utf16Positions(text)
    assert find_spans(text, "c", LITERAL) == [(4, 5)]
    assert [positions.qt(i) for i in range(6)] == [0, 1, 3, 4, 6, 7]
    assert [positions.python(q) for q in (0, 1, 3, 4, 6, 7)] == [0, 1, 2, 3, 4, 5]
    plain = Utf16Positions("abc")
    assert (plain.qt(2), plain.python(2)) == (2, 2)


def test_each_occurrence_has_its_line_and_its_context_on_one_line():
    from text_search import kwic
    text = "alpha\n  beta gamma\ndelta beta"
    rows = kwic(text, find_spans(text, "beta", LITERAL), width=8)
    assert [(row.line, row.before, row.match, row.after) for row in rows] == [
        (2, "alpha ", "beta", " gamma d"),
        (3, "a delta ", "beta", ""),
    ]
    assert (rows[0].start, rows[0].end) == (8, 12)
    # Une occurrence sur deux lignes tient sur une seule.
    row = kwic("xa\n   b y", find_spans("xa\n   b y", r"a\s+b", REGEX))[0]
    assert (row.line, row.before, row.match, row.after) == (1, "x", "a b", " y")
    assert kwic("abc", []) == []
