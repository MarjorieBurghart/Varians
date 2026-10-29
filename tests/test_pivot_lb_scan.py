# -*- coding: utf-8 -*-
"""Red team 2 (robustesse, B3, B6 ; D1) : les lignes du pivot, les <pb> et
les lacunes sont lus dans le texte comme le fait un analyseur XML.

Un <lb edRef="#T1"/> dans un commentaire (un passage retiré, par exemple),
une CDATA ou une instruction comptait comme une ligne du pivot : toute la
suite de la synchronisation était décalée d'une ligne, alors que le viewer
web et les feuilles XSLT l'ignorent. La casse était ignorée (<LB>,
edRef="#t1") ; un « > » dans un attribut placé avant edRef cachait le <lb/>.
Un commentaire contenant « <? » masquait tous les <pb> et toutes les
lacunes qui suivent."""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree

from document_session import LbIndex
from folio_navigation import _pb_tags
from lacunae import lacuna_events
from pivot_lines import pivot_lb_pattern, pivot_lines

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
S01 = DATA / "sermons" / "s01.xml"
LB = '<lb edRef="#T1"/>'


def _spans(text, base="T1"):
    return [match.span() for match in pivot_lb_pattern(base).finditer(text)]


def _xml_count(text, base="T1"):
    root = etree.fromstring(text.encode("utf-8"), etree.XMLParser(resolve_entities=False))
    return sum(1 for element in root.iter() if isinstance(element.tag, str)
               and etree.QName(element).localname == "lb" and element.get("edRef") == f"#{base}")


def test_lb_in_comments_cdata_instructions_and_doctype_are_not_lines():
    text = ('<!DOCTYPE TEI [<!ENTITY x "&#60;lb edRef=\'#T1\'/&#62;"> <!-- <lb edRef="#T1"/> -->]>'
            f'<TEI><p>a{LB}b<!-- {LB} --><![CDATA[{LB}]]><?pi {LB}?>c{LB}d</p></TEI>')
    found = _spans(text)
    assert len(found) == 2 == _xml_count(text)
    assert [text[start:end] for start, end in found] == [LB, LB]


@pytest.mark.parametrize("tag, counted", [
    ('<LB edRef="#T1"/>', False),
    ('<lb edref="#T1"/>', False),
    ('<lb edRef="#t1"/>', False),
    ('<lb rend="->" edRef="#T1"/>', True),
    ("<lb n='a>b' edRef='#T1'/>", True),
    ('<lb edRef="&#35;T1"/>', True),
    ('<tei:lb xmlns:tei="http://www.tei-c.org/ns/1.0" edRef="#T1"/>', True),
    ('<lb edRef="#T1 #T2"/>', False),
    ('<lbx edRef="#T1"/>', False),
])
def test_a_pivot_lb_is_read_as_xml_reads_it(tag, counted):
    text = f"<TEI><p>a{tag}b</p></TEI>"
    found = _spans(text)
    assert len(found) == int(counted) == _xml_count(text)
    if counted:
        assert text[found[0][0]:found[0][1]] == tag


def test_an_unclosed_comment_hides_the_rest():
    text = f"<p>a{LB}b<!-- c{LB}d"
    assert len(_spans(text)) == 1


def test_a_commented_lb_on_the_line_of_a_real_one_does_not_shift_the_numbering():
    text = S01.read_text(encoding="utf-8")
    first = text.index('<lb edRef="#A"/>')
    changed = text[:first] + '<!-- <lb edRef="#A"/> -->' + text[first:]
    lines = pivot_lines(EDITION.read_text(encoding="utf-8"), EDITION, {S01: changed}, "A")
    assert lines.count == 27
    assert lines.file(S01).ordinals == tuple(range(10))


def test_pb_and_lacunae_after_a_comment_holding_other_openers_are_seen():
    text = ('<TEI><!-- a <? b --><!-- <![CDATA[ c --><pb edRef="#A" n="2r"/>'
            '<app><lem wit="#A">x</lem><rdg wit="#B"><lacunaStart/></rdg></app>'
            '<![CDATA[ <!-- ]]><pb n="a>b" edRef="#A"/></TEI>')
    assert [(edrefs, label) for _end, _facs, edrefs, label in _pb_tags(text)] == [(("A",), "2r"), (("A",), "a>b")]
    assert [(event.start, sorted(event.witnesses)) for event in lacuna_events(text)] == [(True, ["B"])]


@pytest.mark.parametrize("removed", ["<!--", "-", "?", "]"])
def test_removing_what_opens_or_closes_a_comment_rescans_the_lines(removed):
    text = f"<p>a{LB}<!-- {LB} --><?pi ?><![CDATA[ ]]>b</p>"
    index = LbIndex()
    index.set(LbIndex.scan(text, pivot_lb_pattern("T1")))
    position = {"<!--": text.index("<!--"), "-": text.index("-->"), "?": text.index("?>"),
                "]": text.index("]]>")}[removed]
    after = text[:position] + text[position + len(removed):]
    index.apply_edit(position, len(removed), 0, "", after[max(0, position - 4096):position], removed_text=removed,
                     following=after[position:position + 2])
    assert index.dirty


def test_a_letter_typed_inside_a_comment_closer_rescans_the_lines():
    text = f"<p>a<!-- {LB} -->{LB}b</p>"
    index = LbIndex()
    index.set(LbIndex.scan(text, pivot_lb_pattern("T1")))
    assert len(index.spans) == 1
    position = text.index("-->") + 1                     # « -x-> » ne ferme plus le commentaire
    after = text[:position] + "x" + text[position:]
    index.apply_edit(position, 0, 1, "x", after[:position], removed_text="", following=after[position + 1:position + 3])
    assert index.dirty and LbIndex.scan(after, pivot_lb_pattern("T1")) == []


def test_typing_ordinary_text_only_shifts_the_lines():
    text = f"<p>a{LB}b{LB}c</p>"
    index = LbIndex()
    index.set(LbIndex.scan(text, pivot_lb_pattern("T1")))
    index.apply_edit(4, 0, 3, "xyz", text[:4], removed_text="", following=text[4:6])
    assert not index.dirty and index.spans[0][0] == text.index(LB) + 3

def test_typing_just_before_or_after_a_tag_rescans_nothing():
    text = f"<p>ab{LB}cd</p>"
    for position in (text.index(LB), text.index(LB) + len(LB)):
        index = LbIndex()
        index.set(LbIndex.scan(text, pivot_lb_pattern("T1")))
        after = text[:position] + "q" + text[position:]
        index.apply_edit(position, 0, 1, "q", after[:position], removed_text="",
                         following=after[position + 1:position + 3])
        assert not index.dirty and index.spans == LbIndex.scan(after, pivot_lb_pattern("T1"))
