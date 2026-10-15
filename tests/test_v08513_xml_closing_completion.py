"""V0.8.5.13: close-tag suggestion from a partially edited TEI, without Qt."""
from pathlib import Path
import ast

from xml_tag_pairs import closing_tag_suggestion, complete_closing_tag

ROOT = Path(__file__).resolve().parents[1]


def _suggest(xml, cursor=None):
    if cursor is None:
        cursor = len(xml)
    obj = closing_tag_suggestion(xml, cursor)
    return None if obj is None else obj.label


def test_requested_example_closes_nearest_div_after_closed_p_and_void_lb():
    xml = '''<div>
      <p>
        <lb n="7" edRef="#Mu"/>
        <lb n="8" edRef="#Mu"/>
        <lb n="9" edRef="#Mu"/>
        <lb n="10" edRef="#Mu"/>
        <lb n="11" edRef="#Mu"/>
      </p>
    </'''
    assert _suggest(xml) == 'div>'
    assert complete_closing_tag(xml, len(xml)) == (xml + 'div>', len(xml) + 4)


def test_shows_nearest_unclosed_element_at_different_nested_depths():
    assert _suggest('<div><p></') == 'p>'
    assert _suggest('<div><p></p></') == 'div>'
    assert _suggest('<div><p></p></div></') is None


def test_partial_qname_accepts_prefix_but_not_wrong_name():
    assert _suggest('<div></d') == 'div>'
    assert _suggest('<div></di') == 'div>'
    assert _suggest('<div></div') == 'div>'
    assert _suggest('<div></p') is None
    assert _suggest('<div></DIV') is None
    assert _suggest('<div></1') is None
    assert complete_closing_tag('<div></di', len('<div></di'))[0] == '<div></div>'


def test_does_not_duplicate_already_typed_angle_bracket():
    xml = '<div></di>'
    result = complete_closing_tag(xml, xml.index('>') + 1 if False else len(xml)-1)
    assert result == ('<div></div>', len('<div></div>'))


def test_ignores_self_closed_tei_elements_and_nested_repeated_names():
    assert _suggest('<div><div><lb/><pb facs="x" /></') == 'div>'
    assert _suggest('<div><div></div></') == 'div>'
    assert _suggest('<a><a></a></a></') is None


def test_ignores_comments_cdata_pi_doctype_and_quoted_ends():
    text = ('<?xml version="1.0"?>'
            '<!DOCTYPE div [<!ENTITY example "<p>" >]>'
            '<div rend="x > y" note="&lt;p&gt;">'
            '<!-- </p> -->'
            '<![CDATA[</no>]]>'
            '<?pi a="</z>"?>'
            '</')
    assert _suggest(text) == 'div>'
    assert _suggest('<div><!-- unfinished </') is None
    assert _suggest('<div><![CDATA[ unfinished </') is None
    assert _suggest('<div><?pi unfinished </') is None
    assert _suggest('<div a="unfinished </') is None


def test_rejects_crossed_closing_tags_or_incomplete_markup():
    assert _suggest('<div><p></div></') is None
    assert _suggest('<div><p foo="bar"</') is None
    assert _suggest('</') is None
    assert _suggest('<div></', -1) is None


def test_namespaces_preserved_character_for_character():
    assert _suggest('<tei:div><tei:p></tei:p></') == 'tei:div>'
    assert _suggest('<tei:div></tei:') == 'tei:div>'
    assert complete_closing_tag('<tei:div></tei:', len('<tei:div></tei:'))[0] == '<tei:div></tei:div>'


def test_position_inside_existing_doc_does_not_look_ahead():
    xml = '<TEI><text><div></</text></TEI>'
    assert _suggest(xml, xml.index('</</') + 2) == 'div>'
    assert _suggest(xml, len(xml)) is None


def test_editor_wires_popup_enter_escape_and_ctrl_space_without_qt():
    source = (ROOT / 'editeur_tei.py').read_text('utf8')
    main = ast.parse(source)
    cls = next(n for n in main.body if isinstance(n, ast.ClassDef) and n.name == 'CodeEditor')
    methods = {m.name for m in cls.body if isinstance(m, ast.FunctionDef)}
    assert {'keyPressEvent','show_closing_tag_completion','_accept_closing_completion'} <= methods
    assert 'self._closing_completer.activated[str].connect(self._accept_closing_completion)' in source
    assert 'Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab' in source
    assert 'Qt.Key.Key_Escape' in source
    assert 'if editor.show_closing_tag_completion(force=True):' in source
    assert 'APP_VERSION = "0.8.5.26.2"' in source
    assert 'QCompleter' in source and 'QStringListModel' in source
