from pathlib import Path
import textwrap

from custom_completion import load_custom_completion
from rng_completion import load_completion_model
from tei_formatter import format_tei_xml

ROOT = Path(__file__).resolve().parents[1]


class FakeRng:
    def __init__(self, mapping):
        self.mapping = dict(mapping)
    def allows_text(self, name):
        local = (name or '').split(':', 1)[-1]
        return self.mapping.get(local)


def test_structural_nodes_are_indented_but_mixed_phrase_content_is_untouched():
    src = '<TEI><text><body><div><p>Et dixit <hi>Dominus</hi> ei.</p><p>Fin.</p></div></body></text></TEI>'
    model = FakeRng({'TEI': False, 'text': False, 'body': False, 'div': False, 'p': True, 'hi': True})
    result = format_tei_xml(src, rng_model=model)
    assert result.error == ''
    assert '<p>Et dixit <hi>Dominus</hi> ei.</p>' in result.text
    assert '<div>\n        <p>Et dixit <hi>Dominus</hi> ei.</p>\n        <p>Fin.</p>\n      </div>' in result.text


def test_lb_never_receives_new_whitespace_even_without_break_no():
    src = '<TEI><text><body><p>uer<lb/>bum</p></body></text></TEI>'
    model = FakeRng({'TEI': False, 'text': False, 'body': False, 'p': False, 'lb': False})
    result = format_tei_xml(src, rng_model=model)
    assert 'uer<lb/>bum' in result.text
    assert 'uer\n' not in result.text
    assert '<lb/>\n' not in result.text


def test_empty_mixed_element_is_protected_by_rng_not_just_actual_text():
    src = '<root><p><hi>x</hi><hi>y</hi></p></root>'
    model = FakeRng({'root': False, 'p': True, 'hi': True})
    out = format_tei_xml(src, rng_model=model).text
    assert '<p><hi>x</hi><hi>y</hi></p>' in out


def test_xml_space_preserve_protects_whole_subtree():
    src = '<root><div xml:space="preserve"><a/><b/></div><div><a/><b/></div></root>'
    model = FakeRng({'root': False, 'div': False, 'a': False, 'b': False})
    out = format_tei_xml(src, rng_model=model).text
    assert '<div xml:space="preserve"><a/><b/></div>' in out
    assert '<div>\n    <a/>\n    <b/>\n  </div>' in out


def test_custom_formatting_block_inline_and_preserve(tmp_path):
    cfg = tmp_path / 'custom-elements.xml'
    cfg.write_text('''<customElements>
      <element name="force" formatting="block"/>
      <element name="inline" formatting="inline"/>
      <element name="keep" formatting="preserve"/>
    </customElements>''', encoding='utf-8')
    custom = load_custom_completion(cfg)
    model = FakeRng({'root': False, 'force': True, 'inline': False, 'keep': False, 'x': False, 'y': False})
    src = '<root><force><x/><y/></force><inline><x/><y/></inline><keep><x/><y/></keep></root>'
    out = format_tei_xml(src, rng_model=model, custom_config=custom).text
    assert '<force>\n    <x/>\n    <y/>\n  </force>' in out
    assert '<inline><x/><y/></inline>' in out
    assert '<keep><x/><y/></keep>' in out


def test_inline_child_override_prevents_parent_from_adding_whitespace_adjacent(tmp_path):
    cfg = tmp_path / 'custom-elements.xml'
    cfg.write_text('<customElements><element name="i" formatting="inline"/></customElements>', encoding='utf-8')
    custom = load_custom_completion(cfg)
    model = FakeRng({'root': False, 'box': False, 'i': False})
    src = '<root><box><i/></box></root>'
    out = format_tei_xml(src, rng_model=model, custom_config=custom).text
    assert '<box><i/></box>' in out


def test_invalid_xml_is_never_rewritten():
    src = '<root><a></root>'
    result = format_tei_xml(src, rng_model=FakeRng({'root': False, 'a': False}))
    assert result.error
    assert result.text == src
    assert not result.changed


def test_rng_model_reports_text_content(tmp_path):
    rng = tmp_path / 'schema.rng'
    rng.write_text(textwrap.dedent('''\
      <grammar xmlns="http://relaxng.org/ns/structure/1.0">
        <start><ref name="root"/></start>
        <define name="root"><element name="root"><zeroOrMore><ref name="p"/></zeroOrMore></element></define>
        <define name="p"><element name="p"><mixed><zeroOrMore><element name="hi"><text/></element></zeroOrMore></mixed></element></define>
      </grammar>
    '''), encoding='utf-8')
    model = load_completion_model(rng)
    assert model.allows_text('root') is False
    assert model.allows_text('p') is True
    assert model.allows_text('hi') is True
    assert model.allows_text('unknown') is None


def test_custom_unknown_formatting_is_rejected(tmp_path):
    cfg = tmp_path / 'custom-elements.xml'
    cfg.write_text('<customElements><element name="x" formatting="pretty"/></customElements>', encoding='utf-8')
    try:
        load_custom_completion(cfg)
    except ValueError as exc:
        assert str(exc) == 'UNKNOWN_FORMATTING_MODE:pretty'
    else:
        raise AssertionError('unknown formatting mode should fail')


def test_static_v081_integration():
    source = (ROOT / 'editeur_tei.py').read_text(encoding='utf-8')
    assert 'APP_VERSION = "0.8.5.26.2"' in source
    assert 'from tei_formatter import format_tei_xml' in source
    assert 'self.action_format_xml' in source
    assert 'def format_xml_source(self):' in source
    assert '_pair_edit_guard = True' in source
    assert (ROOT / 'TEI_FORMATTER.md').is_file()
