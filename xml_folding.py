# -*- coding: utf-8 -*-
"""Conservative line-oriented folding of XML structures, with no Qt dependency.

A fold hides whole QTextBlocks only.  If either boundary carries significant
text / sibling markup, or the pair is not structurally balanced, the region is
not foldable: it is safer to show XML than to conceal a partial line.
"""
from __future__ import annotations

from bisect import bisect_left
from dataclasses import dataclass

from xml_tag_pairs import scan_xml_tags, XmlTagToken


@dataclass(frozen=True)
class FoldRegion:
    name: str
    opening_offset: int
    opening_line: int  # zero-based number for gutter triangle
    first_hidden_line: int
    closing_line: int  # inclusive; closing tag is included in hidden blocks
    closing_offset: int


def foldable_xml_regions(xml_text: str) -> tuple[FoldRegion, ...]:
    """Balanced multi-line elements whose contents can be hidden by blocks.

    Broken markup does not induce guessed pairs. Multi-line attribute lists are
    permitted; folding begins only after the *last* line of the opening tag.
    Self-closing and single-line elements are deliberately excluded.
    """
    text = str(xml_text or "")
    newlines = [i for i, ch in enumerate(text) if ch == '\n']

    def line(offset):
        return bisect_left(newlines, offset)

    def before_markup(offset):
        return text[text.rfind('\n', 0, offset) + 1:offset]

    def after_markup(offset):
        end = text.find('\n', offset)
        return text[offset:end if end >= 0 else len(text)]

    stack: list[XmlTagToken] = []
    regions: list[FoldRegion] = []
    for token in scan_xml_tags(text):
        if token.kind == 'open':
            stack.append(token)
        elif token.kind == 'close':
            if not stack or stack[-1].name != token.name:
                # Bad nesting: no speculative recovery across an invalid pair.
                stack.clear()
                continue
            opening = stack.pop()
            first_hidden = line(opening.end) + 1
            closing = line(token.start)
            if (closing >= first_hidden
                and not before_markup(opening.start).strip()
                and not after_markup(opening.end).strip()
                and not before_markup(token.start).strip()
                and not after_markup(token.end).strip()):
                regions.append(FoldRegion(
                    token.name, opening.start, line(opening.start),
                    first_hidden, closing, token.start,
                ))
    return tuple(sorted(regions, key=lambda r: (r.opening_line, r.closing_line)))


def region_at_header(regions, line_number):
    """Return a fold marker at an opening line (prefer outermost there)."""
    return next((r for r in regions if r.opening_line == line_number), None)


def region_for_cursor(regions, line_number):
    """Return smallest enclosing foldable element at current line."""
    valid = (r for r in regions if r.opening_line <= line_number <= r.closing_line)
    return min(valid, key=lambda r: (r.closing_line - r.opening_line, -r.opening_line), default=None)


def visible_line_numbers(regions, folded_opening_lines, line_count):
    """Pure reference function for the Qt visibility map and tests."""
    hidden = set()
    for region in regions:
        if region.opening_line in folded_opening_lines:
            hidden.update(range(region.first_hidden_line, region.closing_line + 1))
    return tuple(i for i in range(line_count) if i not in hidden)
