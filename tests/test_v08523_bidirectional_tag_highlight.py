"""V0.8.5.23 : surbrillance sûre dans les deux sens sans réécriture XML."""
from pathlib import Path

from xml_tag_pairs import (
    closing_pair_at_context, pair_at_context, opening_pair_at_context,
)
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def _token(src, token):
    return src.index(token) + 2


def test_pair_highlight_both_directions_and_same_tokens():
    src = '<TEI><text><app><lem wit="#Mu">mot</lem><rdg wit="#L">motz</rdg></app></text></TEI>'
    a = pair_at_context(src, _token(src, '<app>'))
    b = pair_at_context(src, _token(src, '</app>'))
    assert a == b
    assert src[a.opening.start:a.opening.end] == '<app>'
    assert src[a.closing.start:a.closing.end] == '</app>'


def test_nested_same_qname_closing_maps_to_correct_opening():
    src = '<seg n="outer"><seg n="inner">x</seg>y</seg>'
    inner = closing_pair_at_context(src, src.index('</seg>') + 3)
    outer = closing_pair_at_context(src, src.rindex('</seg>') + 3)
    assert inner.opening.start == src.index('<seg n="inner">')
    assert outer.opening.start == 0


def test_namespaces_do_not_conflate_prefixes():
    src = '<tei:TEI><tei:app><ms:app>var</ms:app></tei:app></tei:TEI>'
    inner = pair_at_context(src, src.index('</ms:app>') + 4)
    outer = pair_at_context(src, src.index('</tei:app>') + 4)
    assert inner.opening.name == inner.closing.name == 'ms:app'
    assert outer.opening.name == outer.closing.name == 'tei:app'


def test_self_closing_and_special_markup_do_not_create_pairs():
    src = '<root><!-- <app>faux</app> --><![CDATA[<app>]]><lb/><app>vrai</app></root>'
    assert pair_at_context(src, src.index('<lb/>') + 2) is None
    assert pair_at_context(src, src.index('<app>faux') + 2) is None
    assert pair_at_context(src, src.index('CDATA[<app>') + 9) is None
    pair = pair_at_context(src, src.index('</app></root>') + 3)
    assert src[pair.opening.start:pair.opening.end] == '<app>'


def test_malformed_crossed_tags_and_orphan_close_refuse_to_guess():
    for src, closing in (
        ('<root><a><b>x</a></b></root>', '</a>'),
        ('<root><a><b>x</a></root>', '</a>'),
        ('<root></oops><a>x</a></root>', '</a>'),
        ('<root><a>x</a', '</a'),
    ):
        assert closing_pair_at_context(src, src.index(closing) + 2) is None


def test_unfinished_markup_after_pair_does_not_hide_valid_pair():
    src = '<root><app>x</app><rdg'
    pair = pair_at_context(src, src.index('</app>') + 2)
    assert pair is not None and pair.opening.name == 'app'


def test_selection_inside_closing_tag_and_boundaries():
    src = '<app type="x">z</app>'
    start = src.index('</app>')
    end = start + len('</app>')
    assert pair_at_context(src, start) is None
    assert pair_at_context(src, end) is None
    assert pair_at_context(src, end - 1, start, end) is not None
    assert pair_at_context(src, end - 1, start, end + 1) is None


def test_opening_legacy_behavior_unchanged():
    src = '<app>x</app>'
    assert opening_pair_at_context(src, 2) == pair_at_context(src, 2)
    assert opening_pair_at_context(src, src.index('</app>') + 2) is None


def test_editor_highlights_both_tokens_and_is_pure_visual():
    text = application_source()
    fragment = text.split('    def highlightCurrentLine(self):', 1)[1].split('    def setSearchMatch(', 1)[0]
    assert 'pair_at_context(' in fragment
    assert 'for token in (pair.opening, pair.closing):' in fragment
    assert 'matching.format.setBackground(QColor("#d9ecff"))' in fragment
    # Indices Python des balises, positions Qt du curseur (red team, A2).
    assert 'matching.cursor.setPosition(qt.qt(token.start))' in fragment
    assert 'matching.cursor.setPosition(qt.qt(token.end), QTextCursor.MoveMode.KeepAnchor)' in fragment
    assert 'setPlainText' not in fragment and 'insertText' not in fragment
