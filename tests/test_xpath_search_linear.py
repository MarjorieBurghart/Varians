# -*- coding: utf-8 -*-
"""Red team 2 (robustesse, A3) : la recherche XPath croissait comme le
carré du nombre d'éléments frères : le chemin de chaque élément du document
(``getpath``), puis celui de chaque résultat, comptaient leurs frères. Une
transcription « plate » de 20 000 <lb/> dans un seul <ab> demandait 104 s
pour //lb, 4,5 s pour un seul résultat."""
from __future__ import annotations

import time

from xpath_search import search_xpath


def _flat(n):
    lines = "".join(f'<lb edRef="#T1" n="{i}"/>linea {i} uerba\n' for i in range(n))
    return ('<?xml version="1.0" encoding="UTF-8"?>\n<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><ab>\n'
            + lines + '</ab></body></text></TEI>\n')


def test_many_results_among_many_siblings_take_linear_time():
    text = _flat(10000)
    started = time.perf_counter()
    result = search_xpath(text, "//lb")
    elapsed = time.perf_counter() - started
    assert len(result.matches) == 10000
    assert elapsed < 4.0, elapsed
    match = result.matches[1234]
    tag = '<lb edRef="#T1" n="1234"/>'
    assert match.position == text.index(tag) and match.end_position == match.position + len(tag)
    assert match.path == "/TEI/text/body/ab/lb[1235]"


def test_one_result_does_not_walk_every_path():
    text = _flat(20000)
    started = time.perf_counter()
    result = search_xpath(text, "//lb[@n='19999']")
    elapsed = time.perf_counter() - started
    assert len(result.matches) == 1
    assert result.matches[0].position == text.index('<lb edRef="#T1" n="19999"/>')
    assert result.matches[0].path == "/TEI/text/body/ab/lb[20000]"
    assert elapsed < 2.0, elapsed


def test_paths_and_positions_are_unchanged_on_a_mixed_document():
    text = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div><p>a</p><p>b<note>n</note></p></div>'
            '<div><p>c</p><!-- <p>x</p> --><p>d</p></div></body></text></TEI>')
    result = search_xpath(text, "//p")
    assert [m.path for m in result.matches] == ["/TEI/text/body/div[1]/p[1]", "/TEI/text/body/div[1]/p[2]",
                                                "/TEI/text/body/div[2]/p[1]", "/TEI/text/body/div[2]/p[2]"]
    assert [text[m.position:m.end_position] for m in result.matches] == [
        "<p>a</p>", "<p>b<note>n</note></p>", "<p>c</p>", "<p>d</p>"]
    note = search_xpath(text, "//note").matches[0]
    assert note.path == "/TEI/text/body/div[1]/p[2]/note" and text[note.position:note.end_position] == "<note>n</note>"
