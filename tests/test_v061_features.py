from pathlib import Path

from rng_completion import (
    analyze_xml_context,
    adapt_pointer_list_value_context,
    format_pointer_list_insertion,
)
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_pointer_list_completion_after_complete_pointer_offers_remaining_values():
    text = '<rdg wit="#T2">toto</rdg>'
    position = text.index('#T2') + len('#T2')
    context = analyze_xml_context(text, position)
    adapted, values = adapt_pointer_list_value_context(
        context, text, position, ('#T1', '#T2', '#P')
    )
    assert adapted.kind == 'attribute_value'
    assert adapted.prefix == ''
    assert adapted.replace_start == position == adapted.replace_end
    assert values == ('#T1', '#P')
    replacement, final_pos = format_pointer_list_insertion(
        text, adapted.replace_start, adapted.replace_end, '#T1'
    )
    assert replacement == ' #T1'
    assert final_pos == position + len(' #T1')


def test_pointer_list_completion_replaces_only_partial_current_token():
    text = '<rdg wit="#T2 #T">toto</rdg>'
    second = text.index('#T', text.index('#T2') + len('#T2'))
    position = second + len('#T')
    context = analyze_xml_context(text, position)
    adapted, values = adapt_pointer_list_value_context(
        context, text, position, ('#T1', '#T2', '#P')
    )
    assert adapted.prefix == '#T'
    assert text[adapted.replace_start:adapted.replace_end] == '#T'
    assert values == ('#T1', '#P')


def test_pointer_list_completion_also_excludes_pointer_on_right():
    text = '<rdg wit="#T2 #P">toto</rdg>'
    position = text.index('#T2') + len('#T2')
    context = analyze_xml_context(text, position)
    adapted, values = adapt_pointer_list_value_context(
        context, text, position, ('#T1', '#T2', '#P')
    )
    assert adapted.prefix == ''
    assert values == ('#T1',)


def test_xpath_results_use_light_selection_and_hover_colours():
    source = application_source()
    assert 'QAbstractItemView::item:selected' in source
    assert 'background-color: #d9ecff' in source
    assert 'QAbstractItemView::item:hover' in source
    assert 'background-color: #eef7ff' in source


def _choose(text, position, value, values=('#T1', '#T2', '#T3', '#P')):
    """Texte obtenu en choisissant ``value`` dans la liste de Ctrl+Espace,
    comme le font la boîte de complétion et la liste de l'éditeur."""
    context = analyze_xml_context(text, position)
    adapted, remaining = adapt_pointer_list_value_context(context, text, position, values)
    assert value in remaining
    replacement, _ = format_pointer_list_insertion(text, adapted.replace_start, adapted.replace_end, value)
    return text[:adapted.replace_start] + replacement + text[adapted.replace_end:], remaining


def test_a_pointer_chosen_before_another_one_is_inserted_not_substituted():
    """Curseur juste devant un pointeur (« wit="|#T1 #T3" ») : la valeur
    choisie s'insère devant lui, elle ne le remplace pas."""
    text = '<rdg wit="#T1 #T3">toto</rdg>'
    result, remaining = _choose(text, text.index('#T1'), '#T2')
    assert result == '<rdg wit="#T2 #T1 #T3">toto</rdg>'
    assert remaining == ('#T2', '#P')                   # #T1 et #T3 déjà présents
    result, _ = _choose(text, text.index('#T3'), '#T2')
    assert result == '<rdg wit="#T1 #T2 #T3">toto</rdg>'


def test_a_pointer_being_typed_is_still_completed_in_place():
    """Le pointeur où l'on tape reste remplacé (« #T|1 », « #|T3 »)."""
    text = '<rdg wit="#T1 #T3">toto</rdg>'
    result, _ = _choose(text, text.index('#T1') + 2, '#T2')
    assert result == '<rdg wit="#T2 #T3">toto</rdg>'
    result, _ = _choose(text, text.index('#T3') + 1, '#P')
    assert result == '<rdg wit="#T1 #P">toto</rdg>'
