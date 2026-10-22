# -*- coding: utf-8 -*-
"""Sélections partagées (V0.9.1.2), sans Qt : retrouver dans un texte XML
(la source ou le fragment ouvert) l'occurrence d'un texte visible de
l'aperçu, et décrire une sélection XML pour l'aperçu.

Les fonctions sont extraites du code de l'application, comme dans
test_selection_onglets_sans_qt.py."""
from __future__ import annotations

import ast
import html as html_lib
import re

from selection_sync import choose_occurrence, occurrence_index_for_position
from tei_facsimile import position_inside_xml_markup
from varians_source import application_ast

NAMES = {"_selection_xml_to_visible_text", "_xml_selection_pattern",
         "xml_occurrences", "xml_selection_descriptor", "pick_xml_occurrence"}


def _functions():
    funcs = [n for n in application_ast().body if isinstance(n, ast.FunctionDef) and n.name in NAMES]
    ns = {"re": re, "html_lib": html_lib, "choose_occurrence": choose_occurrence,
          "occurrence_index_for_position": occurrence_index_for_position,
          "position_inside_xml_markup": position_inside_xml_markup}
    exec(compile(ast.Module(body=funcs, type_ignores=[]), "formatted_view.py", "exec"), ns)
    return ns


F = _functions()
xml_occurrences = F["xml_occurrences"]
xml_selection_descriptor = F["xml_selection_descriptor"]
pick_xml_occurrence = F["pick_xml_occurrence"]

FRAGMENT = ('<p><lb edRef="#T1"/>premium <hi rend="premium">uerbum</hi> et premi\n'
            '<lb edRef="#P" break="no"/>um, deinde <note>premium</note> premium</p>')


def _starts(spans):
    return [FRAGMENT[a:a + 5] for a, _b in spans]


def test_occurrences_skip_the_markup_and_follow_a_cut_word():
    spans = xml_occurrences(FRAGMENT, "premium")
    # Pas l'attribut rend="premium" ; le mot coupé par <lb break="no"/>.
    assert len(spans) == 4
    assert all(not position_inside_xml_markup(FRAGMENT, a) for a, _b in spans)
    cut = FRAGMENT[slice(*spans[1])]
    assert cut.startswith("premi") and cut.endswith("um") and 'break="no"' in cut


def test_occurrences_stay_in_the_given_range():
    start = FRAGMENT.index("deinde")
    spans = xml_occurrences(FRAGMENT, "premium", start, len(FRAGMENT))
    assert spans == xml_occurrences(FRAGMENT, "premium")[2:]
    assert xml_occurrences(FRAGMENT, "") == [] and xml_occurrences(FRAGMENT, "absens") == []


def test_a_selection_is_described_by_its_rank_and_its_visible_offset():
    spans = xml_occurrences(FRAGMENT, "premium")
    descriptor = xml_selection_descriptor(FRAGMENT, "premium", spans[2][0])
    assert descriptor["occurrence"] == 2
    # Texte visible qui précède, sans le blanc final (comme pour la source).
    assert descriptor["relative"] == len("premium uerbum et premium, deinde")


def test_the_rank_is_used_first_then_the_position():
    spans = xml_occurrences(FRAGMENT, "premium")
    assert pick_xml_occurrence(FRAGMENT, "premium", {"occurrence": 3, "relative": 0}) == spans[3]
    # Rang inconnu (l'aperçu compte autrement) : l'occurrence la plus proche
    # du décalage visible.
    assert pick_xml_occurrence(FRAGMENT, "premium", {"occurrence": 9, "relative": 20}) == spans[1]
    assert pick_xml_occurrence(FRAGMENT, "premium", {"occurrence": None, "relative": None}) == spans[0]
    assert pick_xml_occurrence(FRAGMENT, "absens", {"occurrence": 0, "relative": 0}) is None


def test_a_range_is_described_from_its_start():
    text = "<body>" + FRAGMENT + FRAGMENT + "</body>"
    second = text.index("<p>", 10)
    spans = xml_occurrences(text, "premium", second, len(text))
    descriptor = xml_selection_descriptor(text, "premium", spans[1][0], second, len(text))
    assert descriptor == {"occurrence": 1, "relative": len("premium uerbum et")}
    assert pick_xml_occurrence(text, "premium", descriptor, second, len(text)) == spans[1]
