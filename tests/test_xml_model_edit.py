# -*- coding: utf-8 -*-
"""Lecture et réécriture des déclarations Schematron ``<?xml-model?>``
(V0.9.2.5, ``xml_model_edit``), sans Qt : seule la déclaration visée
change, le reste du texte est gardé tel quel."""
from __future__ import annotations

import pytest

from schema_resolution import RELAXNG_NS, SCHEMATRON_NS, detect_xml_models
from xml_model_edit import add_declaration, remove_declaration, schematron_declarations, set_phase

RNG = f'<?xml-model href="tei_all.rng" type="application/xml" schematypens="{RELAXNG_NS}"?>'
SCH = f'<?xml-model href="regles.sch" type="application/xml" schematypens="{SCHEMATRON_NS}"?>'
TEXT = f'<?xml version="1.0" encoding="UTF-8"?>\n{RNG}\n{SCH}\n<TEI xmlns="http://www.tei-c.org/ns/1.0"/>\n'


def _phases(text):
    return [(d.href, d.phase) for d in detect_xml_models(text) if d.is_schematron]


def test_the_schematron_declarations_are_found_with_their_place():
    [declaration] = schematron_declarations(TEXT)
    assert (declaration.href, declaration.phase) == ("regles.sch", "")
    assert TEXT[declaration.start:declaration.end] == SCH


def test_a_phase_is_added_replaced_and_removed():
    text = set_phase(TEXT, 0, "lecons")
    assert _phases(text) == [("regles.sch", "lecons")]
    assert text == TEXT.replace(SCH, SCH[:-2] + ' phase="lecons"?>')
    text = set_phase(text, 0, "#ALL")
    assert _phases(text) == [("regles.sch", "#ALL")]
    assert set_phase(text, 0, "") == TEXT


def test_the_quotes_and_the_other_attributes_are_kept():
    declaration = (f"<?xml-model href='regles.sch' phase='a'  title=\"Règles\" "
                   f"schematypens='{SCHEMATRON_NS}' ?>")
    text = TEXT.replace(SCH, declaration)
    assert set_phase(text, 0, "b") == text.replace("phase='a'", "phase='b'")
    assert set_phase(text, 0, "") == text.replace(" phase='a'", "")


def test_only_the_chosen_declaration_changes():
    second = SCH.replace("regles.sch", "apparat.sch")
    text = TEXT.replace(SCH, SCH + "\n" + second)
    text = set_phase(text, 1, "temoins")
    assert _phases(text) == [("regles.sch", ""), ("apparat.sch", "temoins")]


def test_a_declaration_is_added_after_the_last_one():
    text = add_declaration(TEXT, "apparat.sch", "lecons")
    assert _phases(text) == [("regles.sch", ""), ("apparat.sch", "lecons")]
    assert text.index("apparat.sch") > text.index("regles.sch") and text.endswith("<TEI xmlns=\"http://www.tei-c.org/ns/1.0\"/>\n")
    # Sans autre déclaration : après la déclaration XML, sinon au début.
    bare = '<?xml version="1.0"?>\n<TEI/>\n'
    assert add_declaration(bare, "regles.sch").startswith('<?xml version="1.0"?>\n<?xml-model href="regles.sch"')
    assert add_declaration("<TEI/>", "regles.sch").endswith("?>\n<TEI/>")


def test_a_declaration_written_on_the_line_of_the_root_is_followed():
    text = f'<?xml version="1.0"?>\n{RNG}{SCH}<TEI/>\n'
    added = add_declaration(text, "apparat.sch")
    assert [d.href for d in detect_xml_models(added)] == ["tei_all.rng", "regles.sch", "apparat.sch"]
    assert added.endswith("?><TEI/>\n")


def test_special_characters_of_the_address_are_escaped():
    text = add_declaration(TEXT, 'r&d "1".sch')
    assert [d.href for d in detect_xml_models(text) if d.is_schematron][-1] == 'r&d "1".sch'


def test_a_declaration_is_removed_with_its_line():
    assert remove_declaration(TEXT, 0) == TEXT.replace(SCH + "\n", "")
    inline = f'<?xml version="1.0"?>\n{RNG}{SCH}<TEI/>\n'
    assert remove_declaration(inline, 0) == f'<?xml version="1.0"?>\n{RNG}<TEI/>\n'


def test_an_unknown_index_is_refused():
    with pytest.raises(IndexError):
        set_phase(TEXT, 1, "x")
    with pytest.raises(IndexError):
        remove_declaration(TEXT, 2)
