# -*- coding: utf-8 -*-
"""Small pure helper for transferring selections between XML and preview views.

The selection itself is found by its text and context (``selection_quote``,
V0.9.4.5); this module only tells which editable element holds a position.
"""
from __future__ import annotations


def containing_span_index(spans, position):
    """Return the index of the span containing *position*, or ``None``."""
    p = int(position)
    for i, (start, end) in enumerate(spans or ()):  # end is exclusive in normal use
        if int(start) <= p < int(end):
            return i
    return None
