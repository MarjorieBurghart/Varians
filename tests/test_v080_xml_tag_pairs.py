from pathlib import Path

from xml_tag_pairs import (
    scan_xml_tags, tag_pairs, opening_pair_at_context,
    exact_selected_opening_pair, closing_rename_mirror, apply_rename_mirror,
)
from varians_source import application_source, CURRENT_VERSION


def test_nested_same_name_pairs_are_exact():
    src = '<root><seg id="outer">a<seg id="inner">b</seg>c</seg></root>'
    pairs = [p for p in tag_pairs(src) if p.opening.name == 'seg']
    assert len(pairs) == 2
    inner = next(p for p in pairs if 'inner' in src[p.opening.start:p.opening.end])
    outer = next(p for p in pairs if 'outer' in src[p.opening.start:p.opening.end])
    assert src[inner.closing.start:inner.closing.end] == '</seg>'
    assert inner.closing.start < outer.closing.start
    assert src[outer.opening.start:outer.opening.end] == '<seg id="outer">'


def test_comments_cdata_pi_and_fake_tags_are_ignored():
    src = '<?xml version="1.0"?><root><!-- <seg>x</seg> --><![CDATA[<seg>]]><seg>ok</seg></root>'
    names = [(t.kind, t.name) for t in scan_xml_tags(src)]
    assert names == [('open','root'), ('open','seg'), ('close','seg'), ('close','root')]


def test_self_closing_tag_has_no_pair():
    src = '<root><lb/><seg>x</seg></root>'
    assert any(t.name == 'lb' and t.kind == 'self' for t in scan_xml_tags(src))
    assert all(p.opening.name != 'lb' for p in tag_pairs(src))


def test_context_inside_opening_tag_finds_matching_close_but_boundaries_do_not():
    src = '<root><seg type="x">text</seg></root>'
    open_start = src.index('<seg')
    open_end = src.index('>', open_start) + 1
    inside = src.index('type') + 2
    pair = opening_pair_at_context(src, inside)
    assert pair is not None
    assert src[pair.closing.start:pair.closing.end] == '</seg>'
    assert opening_pair_at_context(src, open_start) is None
    assert opening_pair_at_context(src, open_end) is None


def test_selection_inside_or_equal_opening_tag_highlights_pair():
    src = '<root><seg type="x">text</seg></root>'
    a = src.index('<seg')
    b = src.index('>', a) + 1
    pair = opening_pair_at_context(src, b - 2, a, b)
    assert pair is not None
    assert exact_selected_opening_pair(src, a, b) == pair
    assert exact_selected_opening_pair(src, a + 1, b) is None


def test_rename_opening_name_mirrors_closing_name():
    old = '<root><seg type="x">text</seg></root>'
    new = old.replace('<seg ', '<quote ', 1)
    mirror = closing_rename_mirror(old, new)
    assert mirror is not None
    assert mirror.old_name == 'seg'
    assert mirror.new_name == 'quote'
    assert apply_rename_mirror(new, mirror) == '<root><quote type="x">text</quote></root>'


def test_rename_outer_same_name_updates_outer_close_not_inner_close():
    old = '<root><seg><seg>x</seg>y</seg></root>'
    new = old.replace('<seg>', '<quote>', 1)
    mirror = closing_rename_mirror(old, new)
    out = apply_rename_mirror(new, mirror)
    assert out == '<root><quote><seg>x</seg>y</quote></root>'


def test_attribute_edit_does_not_rename_closing_tag():
    old = '<root><seg type="x">text</seg></root>'
    new = old.replace('type="x"', 'type="y"')
    assert closing_rename_mirror(old, new) is None


def test_invalid_or_self_closing_new_opening_is_not_mirrored():
    old = '<root><seg>text</seg></root>'
    invalid = old.replace('<seg>', '< >', 1)
    assert closing_rename_mirror(old, invalid) is None


def test_static_editor_integration_v080():
    root = Path(__file__).resolve().parents[1]
    source = application_source()
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in source
    # opening_pair_at_context était importé sans être utilisé (import retiré en
    # V0.8.6.0) ; l'éditeur s'appuie sur pair_at_context.
    assert 'pair_at_context(' in source
    assert 'exact_selected_opening_pair' in source
    assert 'closing_rename_mirror' in source
    assert 'def _remove_pair_after_opening_deletion' in source
    assert 'def _pair_document_contents_changed' in source
    assert 'edit.joinPreviousEditBlock()' in source
    assert 'matching.format.setBackground(QColor("#d9ecff"))' in source


def test_crossed_markup_never_invents_pair():
    src = '<root><a><b>x</a></b></root>'
    # Le moteur refuse le croisement au lieu d'associer arbitrairement les tags.
    assert opening_pair_at_context(src, src.index('<a>') + 2) is None
    assert opening_pair_at_context(src, src.index('<b>') + 2) is None


def test_contents_change_variant_mirrors_without_global_diff():
    from xml_tag_pairs import closing_rename_mirror_for_change
    old = '<root><seg>texte</seg></root>'
    start = old.index('seg')
    new = old[:start] + 'quote' + old[start + 3:]
    mirror = closing_rename_mirror_for_change(old, new, start, 3, 5)
    assert mirror is not None
    assert apply_rename_mirror(new, mirror) == '<root><quote>texte</quote></root>'
