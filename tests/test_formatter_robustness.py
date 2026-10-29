# -*- coding: utf-8 -*-
"""Red team 2 (robustesse) : le formateur (Indenter) ne change jamais le
texte, sur tout document bien formé.

- B1 : une espace insécable (U+00A0), une espace idéographique (U+3000)…
  entre deux éléments structurels étaient prises pour des blancs et
  remplacées par un retour à la ligne : seuls les blancs XML (espace,
  tabulation, retour chariot, saut de ligne) sont des blancs.
- B7 : xml:space="preserve" lu dans l'arbre XML (valeur d'un autre attribut,
  référence de caractère, valeur par défaut du DTD) ; un commentaire du
  DOCTYPE qui contient une apostrophe ne fait plus refuser le document.
- A4 : le temps croissait comme le carré du nombre de zones indentées
  (62 s pour 40 000).
- A10 : une imbrication profonde levait RecursionError, sans message."""
from __future__ import annotations

import random
import time

import pytest
from lxml import etree

from tei_formatter import format_tei_xml

WRAP = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>{}</body></text></TEI>'
STRUCTURE = {"TEI": False, "text": False, "body": False, "div": False, "lg": False, "listPerson": False,
             "person": False, "facsimile": False, "surface": False, "app": False,
             "p": True, "l": True, "lem": True, "rdg": True, "hi": True, "persName": True, "zone": False}


class FakeRng:
    def allows_text(self, name):
        return STRUCTURE.get((name or "").split(":", 1)[-1])


def _format(text):
    return format_tei_xml(text, rng_model=FakeRng())


@pytest.mark.parametrize("blank", [" ", " ", "　", "\u0085", " ", "​"])
def test_a_non_xml_blank_between_structural_elements_is_text(blank):
    source = WRAP.format(f"<div><p>a</p>{blank}<p>b</p></div><div><p>c</p> <p>d</p></div>")
    result = _format(source)
    assert result.error == ""
    assert f"<p>a</p>{blank}<p>b</p>" in result.text
    assert "<p>c</p>\n" in result.text                   # la division voisine est indentée


@pytest.mark.parametrize("division", [
    '<div n="xml:space=\'default\'" xml:space="preserve">',
    '<div xml:space="&#112;reserve">',
    "<div xml:space = 'preserve' >",
])
def test_xml_space_preserve_is_read_from_the_xml_tree(division):
    source = WRAP.format(f"{division}<p>a</p> <p>b</p></div>")
    result = _format(source)
    assert result.error == "" and "<p>a</p> <p>b</p>" in result.text


def test_xml_space_preserve_given_by_the_dtd_is_respected():
    source = ('<!DOCTYPE TEI [<!ATTLIST div xml:space (default|preserve) "preserve">]>'
              + WRAP.format("<div><p>a</p> <p>b</p></div>"))
    result = _format(source)
    assert result.error == "" and "<p>a</p> <p>b</p>" in result.text


def test_an_apostrophe_in_a_doctype_comment_does_not_refuse_the_document():
    source = "<!DOCTYPE TEI [ <!-- l'entité --> ]>" + WRAP.format("<div><p>l'homme</p> <p>b</p></div>")
    result = _format(source)
    assert result.error == "" and "<p>l'homme</p>\n" in result.text


def test_an_external_dtd_that_cannot_be_read_does_not_refuse_the_document():
    source = '<!DOCTYPE TEI SYSTEM "http://127.0.0.1:9/absent.dtd">' + WRAP.format("<div><p>a</p> <p>b</p></div>")
    result = _format(source)
    assert result.error == "" and "<p>a</p>\n" in result.text


def test_formatting_many_zones_takes_linear_time():
    persons = "".join(f'<person xml:id="p{i}"><persName>N{i}</persName></person>' for i in range(20000))
    source = WRAP.format(f"<div><listPerson>{persons}</listPerson></div>")
    started = time.perf_counter()
    result = _format(source)
    elapsed = time.perf_counter() - started
    assert result.error == "" and result.text.count("\n") > 20000
    assert elapsed < 4.0, elapsed


def test_a_very_deep_document_gives_a_result_and_no_exception():
    depth = 1500
    source = WRAP.format("<div>" * depth + "<p>x</p>" + "</div>" * depth)
    result = _format(source)
    assert result.error == "" and "<p>x</p>" in result.text
    etree.fromstring(result.text.encode("utf-8"), etree.XMLParser(huge_tree=True))


# --- Invariants sur des documents variés ----------------------------------------------

PIECES = ["<p>a</p>", "<p>b <hi>c</hi> d</p>", "<lg><l>v</l> <l>w</l></lg>", "<!-- note -->", "<?pi x?>",
          "<p>x<lb/>y</p>", "<app><lem>u</lem> <rdg>v</rdg></app>", "<![CDATA[ <p> ]]>",
          "<div xml:space=\"preserve\"> <p>k</p>  </div>", "　", " ", "\n  ", "\t", "<p/>"]


def _text_of(tree):
    return ["".join(element.itertext()) for element in tree.iter()]


def _xml_blank(text):
    return not (text or "").strip(" \t\r\n")


@pytest.mark.parametrize("seed", range(40))
def test_the_text_is_never_changed(seed):
    rng = random.Random(seed)

    def division(level):
        parts = []
        for _ in range(rng.randint(1, 5)):
            parts.append(division(level + 1) if level < 3 and rng.random() < 0.3 else rng.choice(PIECES))
        return "<div>" + "".join(parts) + "</div>"

    source = WRAP.format("".join(division(0) for _ in range(3)))
    result = _format(source)
    assert result.error == ""
    before = etree.fromstring(source.encode("utf-8"))
    after = etree.fromstring(result.text.encode("utf-8"))
    # Mêmes éléments, mêmes textes ; seuls changent des blancs XML entre éléments.
    assert [e.tag for e in before.iter()] == [e.tag for e in after.iter()]
    for old, new in zip(before.iter(), after.iter()):
        for a, b in ((old.text, new.text), (old.tail, new.tail)):
            assert a == b or (_xml_blank(a) and _xml_blank(b)), (seed, a, b)
    # Formater deux fois revient à formater une fois.
    assert _format(result.text).text == result.text
