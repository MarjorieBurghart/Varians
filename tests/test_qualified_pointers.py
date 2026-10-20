# -*- coding: utf-8 -*-
"""Pointeurs « fichier.xml#id » parmi les valeurs proposées : un identifiant
d'un autre document est proposé sous cette forme, qui doit se comporter comme
« #id » (liste de pointeurs, insertion, source « ids »)."""
from __future__ import annotations

from custom_completion import load_custom_completion
from rng_completion import (
    adapt_pointer_list_value_context, analyze_xml_context, format_pointer_list_insertion,
)

VALUES = ("#bernard", "personnes.xml#molesme")


def _adapt(text, position):
    return adapt_pointer_list_value_context(analyze_xml_context(text, position), text, position, VALUES)


def test_a_qualified_pointer_keeps_the_pointer_list_behaviour():
    text = '<persName ref="#bernard #mo">x</persName>'
    position = text.index("#mo") + len("#mo")
    adapted, values = _adapt(text, position)
    assert adapted.prefix == "#mo"
    assert text[adapted.replace_start:adapted.replace_end] == "#mo"     # #bernard conservé
    assert values == ("personnes.xml#molesme",)


def test_a_qualified_pointer_is_added_with_a_separator():
    text = '<persName ref="#bernard">x</persName>'
    position = text.index("#bernard") + len("#bernard")
    adapted, values = _adapt(text, position)
    assert values == ("personnes.xml#molesme",)
    replacement, _ = format_pointer_list_insertion(
        text, adapted.replace_start, adapted.replace_end, "personnes.xml#molesme")
    assert replacement == " personnes.xml#molesme"


def test_ids_source_keeps_the_file_form_of_an_identifier_of_another_document(tmp_path):
    path = tmp_path / "custom-elements.xml"
    path.write_text('''<customElements>
      <element name="name"><attribute name="ref" valuesMode="replace">
        <values source="ids" prefix="#"/></attribute></element>
      <element name="term"><attribute name="key">
        <values source="ids"/></attribute></element>
    </customElements>''', encoding="utf-8")
    config = load_custom_completion(path)
    ids_for = lambda elements: ("bernard", "personnes.xml#molesme")
    assert config.attribute_values("name", "ref", (), ids_for)[0] == VALUES
    # Sans préfixe « # », la valeur attendue n'est pas un pointeur : l'identifiant seul.
    assert config.attribute_values("term", "key", (), ids_for)[0] == ("bernard", "molesme")
