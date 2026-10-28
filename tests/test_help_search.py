# -*- coding: utf-8 -*-
"""Recherche dans l'aide de Varians (V0.9.2.8), sans Qt : help_search.py.
Sans tenir compte des accents ni de la casse ; plusieurs mots : les
sections qui les contiennent tous ; entre guillemets, l'expression exacte."""
from __future__ import annotations

from help_search import Section, fold, query_terms, search

TEXT = ("Édition critique\n"
        "Le scénario « Édition critique (HTML) » publie l’édition en une page.\n"
        "Rechercher et remplacer\n"
        "Les expressions régulières sont celles de Python : cochez Expressions régulières.\n")
FIRST = TEXT.index("Rechercher")
SECTIONS = [Section("Édition critique", 0, FIRST), Section("Rechercher et remplacer", FIRST, len(TEXT))]


def test_the_text_is_folded_without_accents_case_or_typographic_signs():
    folded, origin = fold("Édition l’œuvre « x »")
    assert folded == "edition l'œuvre \" x \""
    assert len(origin) == len(folded) and origin[:3] == [0, 1, 2]
    assert fold("Straße")[0] == "strasse"                   # ß : ss
    assert fold("Straße")[1] == [0, 1, 2, 3, 4, 4, 5]       # les deux « s » viennent du ß


def test_the_query_gives_words_and_quoted_phrases():
    assert query_terms("expressions REGULIERES") == ["expressions", "regulieres"]
    assert query_terms('"edition critique" html') == ["edition critique", "html"]
    assert query_terms("« Édition critique »") == ["edition critique"]
    assert query_terms("   ") == []


def test_a_section_must_contain_every_word():
    hits = search(TEXT, SECTIONS, "edition CRITIQUE")
    assert [hit.section.title for hit in hits] == ["Édition critique"]
    found = {TEXT[a:b] for a, b in hits[0].spans}
    assert found == {"Édition", "édition", "critique"}
    assert search(TEXT, SECTIONS, "scenario python") == []        # deux sections différentes
    assert search(TEXT, SECTIONS, "") == []


def test_accents_case_and_apostrophes_do_not_matter():
    hits = search(TEXT, SECTIONS, "expressions regulieres")
    assert [hit.section.title for hit in hits] == ["Rechercher et remplacer"]
    assert [TEXT[a:b] for a, b in hits[0].spans] == ["expressions", "régulières", "Expressions", "régulières"]
    hits = search(TEXT, SECTIONS, "l'edition")
    assert [TEXT[a:b] for a, b in hits[0].spans] == ["l’édition"]


def test_a_quoted_phrase_is_found_as_a_whole():
    hits = search(TEXT, SECTIONS, '"edition critique"')
    assert [TEXT[a:b] for a, b in hits[0].spans] == ["Édition critique", "Édition critique"]
    assert search(TEXT, SECTIONS, '"critique edition"') == []


def test_each_hit_has_a_one_line_excerpt_around_its_first_occurrence():
    hits = search(TEXT, SECTIONS, "python", context=12)
    excerpt = hits[0].excerpt
    assert "Python" in excerpt and "\n" not in excerpt
    assert excerpt.startswith("…") and excerpt.endswith("…")
