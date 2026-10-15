# -*- coding: utf-8 -*-
"""Small pure helpers for transferring selections between XML and preview views.

The important rule is positional: repeated text is identified by its occurrence
inside the same TEI paragraph, not by a global first-match search.
"""
from __future__ import annotations


def containing_span_index(spans, position):
    """Return the index of the span containing *position*, or ``None``."""
    p = int(position)
    for i, (start, end) in enumerate(spans or ()):  # end is exclusive in normal use
        if int(start) <= p < int(end):
            return i
    return None


def occurrence_index_for_position(spans, position):
    """Return the occurrence whose span contains or is nearest to *position*."""
    if not spans:
        return None
    p = int(position)
    for i, (start, end) in enumerate(spans):
        start, end = int(start), int(end)
        if start <= p < end or (start == end == p):
            return i
    return min(range(len(spans)), key=lambda i: abs(int(spans[i][0]) - p))


def choose_occurrence(spans, occurrence_index=None, target_position=None):
    """Choose a span by occurrence index, with positional fallback."""
    if not spans:
        return None
    if occurrence_index is not None:
        try:
            i = int(occurrence_index)
        except (TypeError, ValueError):
            i = -1
        if 0 <= i < len(spans):
            return tuple(spans[i])
    if target_position is not None:
        p = int(target_position)
        return tuple(min(spans, key=lambda ab: abs(int(ab[0]) - p)))
    return tuple(spans[0])
