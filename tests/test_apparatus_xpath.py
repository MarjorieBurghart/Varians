# -*- coding: utf-8 -*-
"""Requêtes XPath de contrôle de l'apparat critique (parallel segmentation),
sans Qt : témoins du <listWit>, témoin cité plusieurs fois, <app> incomplets,
témoin donné."""
from __future__ import annotations

import re

import pytest
from lxml import etree

from apparatus_xpath import incomplete_app_xpath, repeated_witness_xpath, witness_ids, witness_xpath
from xpath_search import search_xpath

# Un <app> par ligne, nommé par @n : les résultats sont identifiés par leur ligne.
TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
<teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt>
<publicationStmt><p>Essai</p></publicationStmt>
<sourceDesc><listWit>
  <witness xml:id="A">Manuscrit A</witness>
  <witness xml:id="B">Manuscrit B</witness>
  <witness xml:id="C">Manuscrit C</witness>
</listWit></sourceDesc></fileDesc></teiHeader>
<text><body><p>
<app n="complet"><lem wit="#A">a</lem><rdg wit="#B #C">b</rdg></app>
<app n="doublon"><lem wit="#A #B">a</lem><rdg wit="#B #C">b</rdg></app>
<app n="doublon-meme-wit"><lem wit="#A #A">a</lem><rdg wit="#B #C">b</rdg></app>
<app n="doublon-groupe"><lem wit="#A">a</lem><rdgGrp><rdg wit="#B">b</rdg><rdg wit="#B #C">c</rdg></rdgGrp></app>
<app n="incomplet"><lem wit="#A">a</lem><rdg wit="#B">b</rdg></app>
<app n="lem-sans-wit"><lem>a</lem><rdg wit="#B">b</rdg></app>
<app n="prefixe"><lem wit="#AB">a</lem><rdg wit="#B #C">b</rdg></app>
<app n="multiligne"><lem wit="  #A
   #C ">a</lem><rdg wit="#B">b</rdg></app>
<app n="englobant"><lem wit="#A #B">x
<app n="imbrique-complet"><lem wit="#A">y</lem><rdg wit="#B">z</rdg></app>
</lem><rdg wit="#C">w</rdg></app>
<app n="englobant-2"><lem wit="#A #B">x
<app n="imbrique-incomplet"><lem wit="#A">y</lem></app>
</lem><rdg wit="#C">w</rdg></app>
<app n="englobant-sans-wit"><lem>x
<app n="imbrique-inconnu"><lem wit="#A">y</lem></app>
</lem><rdg wit="#C">w</rdg></app>
</p></body></text>
</TEI>
"""

LINE_NAMES = {number: match.group(1)
              for number, line in enumerate(TEI.splitlines(), 1)
              for match in [re.search(r'<app n="([^"]+)"', line)] if match}


def _found(expression):
    result = search_xpath(TEI, expression)
    assert not result.namespace_fallback_used                 # préfixe tei: explicite
    return [LINE_NAMES[match.line] for match in result.matches]


def test_witnesses_come_from_the_list_wit():
    assert witness_ids(TEI) == ["A", "B", "C"]


def test_witness_list_ignores_witnesses_outside_list_wit():
    text = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader><listWit>'
            '<witness xml:id="A"/><listWit xml:id="groupe"><witness xml:id="B"/></listWit>'
            '<witness/></listWit></teiHeader>'
            '<text><body><witness xml:id="Z"/></body></text></TEI>')
    assert witness_ids(text) == ["A", "B"]


@pytest.mark.parametrize("text", ["", "<TEI", "<TEI xmlns='http://www.tei-c.org/ns/1.0'/>"])
def test_no_witness_without_a_usable_list_wit(text):
    assert witness_ids(text) == []


def test_a_witness_cited_several_times_in_an_app():
    assert _found(repeated_witness_xpath(["A", "B", "C"])) == ["doublon", "doublon-meme-wit", "doublon-groupe"]


def test_incomplete_apps():
    # « lem-sans-wit » : le <lem> couvre les témoins absents des <rdg> ;
    # « imbrique-inconnu » : ses témoins attendus ne sont pas connus.
    assert _found(incomplete_app_xpath(["A", "B", "C"])) == ["incomplet", "prefixe", "imbrique-incomplet"]


def test_a_given_witness_cited_in_lem_or_rdg():
    found = _found(witness_xpath("A", present=True, rdg_only=False))
    assert "lem-sans-wit" in found                              # A absent des <rdg> : dans le <lem>
    assert "prefixe" not in found and "multiligne" in found
    # « englobant-sans-wit » : A absent du <rdg>, donc couvert par le <lem> sans @wit.
    assert _found(witness_xpath("A", present=False, rdg_only=False)) == ["prefixe"]


def test_a_given_witness_cited_in_rdg_only():
    assert _found(witness_xpath("C", present=True, rdg_only=True)) == [
        "complet", "doublon", "doublon-meme-wit", "doublon-groupe", "prefixe",
        "englobant", "englobant-2", "englobant-sans-wit"]
    absent = _found(witness_xpath("C", present=False, rdg_only=True))
    assert "multiligne" in absent and "incomplet" in absent and "complet" not in absent


def test_generated_expressions_are_plain_xpath_1():
    namespaces = {"tei": "http://www.tei-c.org/ns/1.0"}
    for expression in (repeated_witness_xpath(["A", "B"]), incomplete_app_xpath(["A", "B"]),
                       witness_xpath("A", present=False, rdg_only=True)):
        assert expression.startswith("//tei:app[")
        etree.XPath(expression, namespaces=namespaces)          # compile en XPath 1.0


def test_unusual_identifiers_are_quoted_safely():
    expression = witness_xpath("A.1-b", present=True, rdg_only=False)
    assert "' #A.1-b '" in expression
    with pytest.raises(ValueError):
        witness_xpath("A'B", present=True, rdg_only=False)


# --- Lacunes (V0.9.1.3) ----------------------------------------------------------
# Un témoin en lacune n'a pas de leçon dans le passage : ses <app> ne sont pas
# incomplets pour lui. Les deux encodages de att.rdgPart.

LACUNA_TEI = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
<teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt>
<publicationStmt><p>Essai</p></publicationStmt>
<sourceDesc><listWit>
  <witness xml:id="A">Manuscrit A</witness>
  <witness xml:id="B">Manuscrit B</witness>
  <witness xml:id="C">Manuscrit C</witness>
</listWit></sourceDesc></fileDesc></teiHeader>
<text><body><p>
<app n="avant"><lem wit="#A">a</lem><rdg wit="#B">b</rdg></app>
<lacunaStart wit="#C"/>
<app n="lacune-c"><lem wit="#A">a</lem><rdg wit="#B">b</rdg></app>
<app n="lacune-c-sans-b"><lem wit="#A">a</lem></app>
<lacunaEnd wit="#C"/>
<app n="apres"><lem wit="#A">a</lem><rdg wit="#B">b</rdg></app>
<app n="debut-b"><lem wit="#A #C">a</lem><rdg wit="#B"><lacunaStart/></rdg></app>
<app n="lacune-b"><lem wit="#A #C">a</lem></app>
<app n="fin-b"><lem wit="#A #C">a</lem><rdg wit="#B"><lacunaEnd/></rdg></app>
<app n="apres-b"><lem wit="#A #C">a</lem></app>
</p></body></text>
</TEI>
"""

LACUNA_LINES = {number: match.group(1)
                for number, line in enumerate(LACUNA_TEI.splitlines(), 1)
                for match in [re.search(r'<app n="([^"]+)"', line)] if match}


def _found_in(text, lines, expression):
    return [lines[match.line] for match in search_xpath(text, expression).matches]


def test_an_app_in_a_lacuna_of_a_witness_is_not_incomplete_for_it():
    expression = incomplete_app_xpath(["A", "B", "C"], lacunose=["B", "C"])
    assert _found_in(LACUNA_TEI, LACUNA_LINES, expression) == ["avant", "lacune-c-sans-b", "apres", "apres-b"]
    # Sans le relevé des lacunes, tous les <app> du passage sont signalés.
    assert "lacune-c" in _found_in(LACUNA_TEI, LACUNA_LINES, incomplete_app_xpath(["A", "B", "C"]))


def test_the_lacuna_condition_is_only_added_for_lacunose_witnesses():
    assert incomplete_app_xpath(["A", "B"]) == incomplete_app_xpath(["A", "B"], lacunose=())
    assert "lacunaStart" not in incomplete_app_xpath(["A", "B"])
    with_c = incomplete_app_xpath(["A", "B", "C"], lacunose=["C"])
    assert with_c.count("lacunaStart") == 1 and "#C" in with_c
    etree.XPath(with_c, namespaces={"tei": "http://www.tei-c.org/ns/1.0"})   # XPath 1.0 valide
