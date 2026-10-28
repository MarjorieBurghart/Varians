# -*- coding: utf-8 -*-
"""Appariement des balises : exactitude et coût linéaire sur un long document.

Jusqu'à V0.8.5.26.2, ``matching_closing_tag`` vérifiait, pour chaque balise
rencontrée, qu'elle n'était pas dans un commentaire en recherchant en arrière
jusqu'au début du texte : coût quadratique, plusieurs secondes par frappe lors
de la saisie d'une balise ouvrante non fermée dans un long document.
"""
from __future__ import annotations

import time
from pathlib import Path

import xml_tag_pairs as X

ROOT = Path(__file__).resolve().parents[1]
EDITION = (ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml").read_text(encoding="utf-8")


def _reference_find_markup_end(text: str, start: int) -> int:
    """Implémentation caractère par caractère de V0.8.5.26.2 (référence)."""
    n = len(text)
    if text.startswith("<!--", start):
        stop = text.find("-->", start + 4)
        return n if stop < 0 else stop + 3
    if text.startswith("<![CDATA[", start):
        stop = text.find("]]>", start + 9)
        return n if stop < 0 else stop + 3
    if text.startswith("<?", start):
        stop = text.find("?>", start + 2)
        return n if stop < 0 else stop + 2
    quote = None
    bracket_depth = 0
    i = start + 1
    declaration = text.startswith("<!", start)
    while i < n:
        ch = text[i]
        if quote:
            if ch == quote:
                quote = None
        elif ch in ("'", '"'):
            quote = ch
        elif declaration and ch == "[":
            bracket_depth += 1
        elif declaration and ch == "]" and bracket_depth:
            bracket_depth -= 1
        elif ch == ">" and bracket_depth == 0:
            return i + 1
        i += 1
    return n


EDGE_CASES = [
    '<a b="x>y">', "<a b='x\">y'>", '<a b="non fermé>', "<a", '<a b="x"/>', "<a\n  c='1'\n>",
    "<!DOCTYPE r [<!ENTITY e 'v'>]><r/>", "<!-- <b> -->", "<![CDATA[ <x> ]]>", "<?pi <x>?>",
    "<!-- non fermé", "<a b=\"\">", "<a b=''>", "<>", "< a>",
]


def test_find_markup_end_matches_reference_everywhere():
    for text in [EDITION, *EDGE_CASES]:
        for i, ch in enumerate(text):
            if ch == "<":
                assert X._find_markup_end(text, i) == _reference_find_markup_end(text, i), (text[i:i + 40], i)


def test_matching_closing_tag_agrees_with_full_stack_pairing():
    """Oracle indépendant : tag_pairs() apparie tout le document par pile."""
    expected = {pair.opening: pair.closing for pair in X.tag_pairs(EDITION)}
    assert len(expected) > 3000                  # 3 314 paires dans le projet exemple
    for opening, closing in expected.items():
        assert X.matching_closing_tag(EDITION, opening) == closing


def test_special_markup_between_opening_and_closing_is_skipped():
    text = '<r><a><!-- <b> </a> --><![CDATA[</a>]]><?pi <x>?><c attr="x>y"/></a></r>'
    opening = X.opening_tag_at(text, text.index("<a>"))
    closing = X.matching_closing_tag(text, opening)
    assert closing is not None and closing.start == text.rindex("</a>")


def test_unclosed_opening_in_long_document_is_fast():
    pos = EDITION.index("<body>") + len("<body>")
    text = EDITION[:pos] + "<varianstest " + EDITION[pos:]
    opening = X.opening_tag_at(text, pos)
    assert opening is not None and opening.name == "varianstest"
    start = time.perf_counter()
    assert X.matching_closing_tag(text, opening) is None
    assert time.perf_counter() - start < 1.0          # ≈ 8 s en V0.8.5.26.2
