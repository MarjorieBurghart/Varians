from pathlib import Path
import sys

import pytest
from varians_source import application_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

pytest.importorskip("lxml")
from xpath_search import search_xpath


def test_xpath_match_carries_complete_multiline_element_range():
    xml = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>
<note type="a">
  <p>alpha</p>
  <note>nested</note>
  <p>omega</p>
</note>
</body></text></TEI>'''
    result = search_xpath(xml, '//tei:note[@type="a"]')
    assert len(result.matches) == 1
    match = result.matches[0]
    selected = xml[match.position:match.end_position]
    assert selected.startswith('<note type="a">')
    assert selected.endswith('</note>')
    assert '<note>nested</note>' in selected
    assert selected == xml[xml.index('<note type="a">'): xml.rindex('</note>') + len('</note>')]


def test_xpath_match_range_handles_nested_same_named_elements_independently():
    xml = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><div><div>inner</div><p>x</p></div></body></text></TEI>'
    result = search_xpath(xml, '//tei:div')
    assert len(result.matches) == 2
    outer, inner = result.matches
    assert xml[outer.position:outer.end_position] == '<div><div>inner</div><p>x</p></div>'
    assert xml[inner.position:inner.end_position] == '<div>inner</div>'


def test_xpath_match_range_handles_self_closing_elements():
    xml = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>a<lb n="1"/>b</p></body></text></TEI>'
    result = search_xpath(xml, '//tei:lb')
    assert len(result.matches) == 1
    match = result.matches[0]
    assert xml[match.position:match.end_position] == '<lb n="1"/>'


def test_editor_goto_xpath_uses_selection_anchor_and_current_version():
    source = application_source()
    assert 'int(match.end_position)' in source
    assert 'QTextCursor.MoveMode.KeepAnchor' in source
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in source


def test_help_is_current_and_covers_new_workflows_in_both_languages():
    fr = (ROOT / 'help' / 'fr.html').read_text(encoding='utf-8')
    en = (ROOT / 'help' / 'en.html').read_text(encoding='utf-8')
    # V0.9.3.1 : l'aide n'annonce plus les versions.
    for text in (fr, en):
        assert '&lt;facsimile&gt;' in text
        assert 'base_keys' in text
        assert 'XPath' in text
        assert 'ALTO' in text
    assert 'sélectionne l’élément entier' in fr
    assert 'selects the whole element' in en
