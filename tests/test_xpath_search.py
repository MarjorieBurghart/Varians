from pathlib import Path
import sys
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("lxml")
from xpath_search import search_xpath, XPathQueryError

XML = '''<?xml version="1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <text><body>
    <p>Avant <note xml:id="n1">Première note</note>.</p>
    <p><note type="editorial">Deuxième note</note></p>
  </body></text>
</TEI>'''


def test_simple_unprefixed_xpath_is_retried_in_tei_namespace():
    result = search_xpath(XML, "//note")
    assert result.namespace_fallback_used is True
    assert result.effective_expression == "//tei:note"
    assert [m.tag for m in result.matches] == ["note", "note"]
    assert all(XML[m.position:m.position+5] == "<note" for m in result.matches)


def test_explicit_tei_xpath_and_predicate():
    result = search_xpath(XML, '//tei:note[@type="editorial"]')
    assert result.namespace_fallback_used is False
    assert len(result.matches) == 1
    assert "Deuxième note" in result.matches[0].preview


def test_xpath_positions_are_exact_enough_for_inline_elements():
    result = search_xpath(XML, "//note")
    positions = [m.position for m in result.matches]
    assert positions[0] == XML.index('<note xml:id="n1"')
    assert positions[1] == XML.index('<note type="editorial"')


def test_scalar_xpath_result_is_reported():
    result = search_xpath(XML, "count(//tei:note)")
    assert result.matches == ()
    assert result.scalar_value in {"2.0", "2"}


def test_invalid_xpath_is_reported():
    with pytest.raises(XPathQueryError):
        search_xpath(XML, "//*[" )
