from pathlib import Path

from rng_completion import (
    analyze_xml_context,
    adapt_pointer_list_value_context,
    format_pointer_list_insertion,
)

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
    source = (ROOT / 'editeur_tei.py').read_text(encoding='utf-8')
    assert 'QAbstractItemView::item:selected' in source
    assert 'background-color: #d9ecff' in source
    assert 'QAbstractItemView::item:hover' in source
    assert 'background-color: #eef7ff' in source
