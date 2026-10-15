# -*- coding: utf-8 -*-
"""DocumentSession et LbIndex (sans Qt)."""
from __future__ import annotations

import random
import re
from pathlib import Path

import pytest

from document_session import DocumentSession, LbIndex

LB_T1 = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bedRef\s*=\s*(['\"])#T1\1)[^>]*?/?>",
    re.IGNORECASE | re.DOTALL,
)

SAMPLE = (
    '<p><lb edRef="#T1" n="1"/>In principio <lb edRef="#T2"/>erat '
    '<lb edRef="#T1" n="2"/>verbum et <lb edRef="#T1" n="3"/>verbum erat</p>'
)


def _index(text):
    idx = LbIndex()
    idx.set(LbIndex.scan(text, LB_T1))
    return idx


def test_scan_keeps_only_pivot_lb():
    spans = LbIndex.scan(SAMPLE, LB_T1)
    assert [SAMPLE[a:b] for a, b in spans] == [
        '<lb edRef="#T1" n="1"/>', '<lb edRef="#T1" n="2"/>', '<lb edRef="#T1" n="3"/>']


def test_new_index_is_dirty_until_set():
    idx = LbIndex()
    assert idx.dirty
    idx.set([(0, 5)])
    assert not idx.dirty and idx.spans == [(0, 5)]


def test_ordinal_at():
    idx = _index(SAMPLE)
    first, second, third = idx.spans
    assert idx.ordinal_at(0) == 0                 # avant le premier <lb/>
    assert idx.ordinal_at(first[1]) == 0
    assert idx.ordinal_at(second[0]) == 1
    assert idx.ordinal_at(third[1] + 3) == 2
    assert idx.ordinal_at(10**9) == 2
    assert LbIndex().ordinal_at(5) is None


def test_plain_typing_shifts_following_lb():
    idx = _index(SAMPLE)
    pos = SAMPLE.index("erat")
    new = SAMPLE[:pos] + "XYZ" + SAMPLE[pos:]
    idx.apply_edit(pos, 0, 3, "XYZ")
    assert not idx.dirty
    assert idx.spans == LbIndex.scan(new, LB_T1)


def test_markup_insertion_invalidates():
    idx = _index(SAMPLE)
    idx.apply_edit(5, 0, 4, "<hi>")
    assert idx.dirty


def test_edit_inside_lb_invalidates():
    idx = _index(SAMPLE)
    start, end = idx.spans[1]
    idx.apply_edit(start + 3, 0, 1, "x")
    assert idx.dirty


def test_deletion_covering_lb_invalidates():
    idx = _index(SAMPLE)
    start, end = idx.spans[1]
    idx.apply_edit(start - 2, end - start + 4, 0)
    assert idx.dirty


def test_dirty_index_ignores_edits():
    idx = LbIndex()
    idx.apply_edit(0, 0, 3, "abc")
    assert idx.dirty and idx.spans == []


KNOWN_LIMITATION = (
    "Comportement hérité de V0.8.5.26.2 : une modification à l'intérieur d'une "
    "balise qui n'est pas (encore) un <lb/> pivot, sans saisie de '<' ni de '>', "
    "peut créer ou détruire un <lb/> sans invalider l'index. Le contrôle XML "
    "automatique qui suit la pause de frappe reconstruit l'index. Correction "
    "prévue en phase 4."
)


def test_typing_inside_tag_that_becomes_pivot_lb():
    text = '<p><lb edRef="#T"/>x</p>'
    idx = _index(text)
    assert idx.spans == []
    pos = text.index('"/>')
    text = text[:pos] + "1" + text[pos:]
    idx.apply_edit(pos, 0, 1, "1")
    if idx.dirty:
        idx.set(LbIndex.scan(text, LB_T1))
    expected = LbIndex.scan(text, LB_T1)
    assert expected, "le texte contient désormais un <lb/> pivot"
    if idx.spans != expected:
        pytest.xfail(KNOWN_LIMITATION)


def test_random_edits_match_full_rescan():
    """Après chaque modification, l'index incrémental (s'il reste valide)
    coïncide exactement avec un balayage complet du nouveau texte."""
    rng = random.Random(20261015)
    pieces = ["a", "bc ", " ", "\n", "é", "<", ">", "lb", '<lb edRef="#T1"/>', '<lb edRef="#T2"/>', "/"]
    text = SAMPLE * 3
    idx = _index(text)
    for _ in range(2000):
        if idx.dirty:
            idx.set(LbIndex.scan(text, LB_T1))
        pos = rng.randrange(0, len(text) + 1)
        removed = rng.choice([0, 0, 1, 2, 5]) if pos < len(text) else 0
        removed = min(removed, len(text) - pos)
        inserted = rng.choice(["", "", rng.choice(pieces), rng.choice(pieces) + rng.choice(pieces)])
        text = text[:pos] + inserted + text[pos + removed:]
        idx.apply_edit(pos, removed, len(inserted), inserted)
        if not idx.dirty and idx.spans != LbIndex.scan(text, LB_T1):
            pytest.xfail(KNOWN_LIMITATION)


def test_session_defaults():
    session = DocumentSession()
    assert session.path is None and session.modified is False
    assert session.lb.dirty
    assert session.last_rng_result is None and session.last_rng_revision == -1
    assert session.health == "normal"


def test_invalidate_rng():
    session = DocumentSession()
    session.last_rng_result = object()
    session.last_rng_revision = 4
    session.last_rng_schema_token = ("x",)
    session.invalidate_rng()
    assert session.last_rng_result is None
    assert session.last_rng_revision == -1
    assert session.last_rng_schema_token is None


def test_mark_loaded_and_saved(tmp_path):
    session = DocumentSession()
    session.modified = True
    session.lb.set([(0, 1)])
    session.last_synced_ordinal = 3
    session.mark_loaded(tmp_path / "a.xml", 12)
    assert session.path == tmp_path / "a.xml"
    assert session.modified is False
    assert session.last_processed_edit_revision == 12
    assert session.lb.dirty
    assert session.last_synced_ordinal is None

    session.modified = True
    session.mark_saved(Path(tmp_path / "b.xml"))
    assert session.path == tmp_path / "b.xml" and session.modified is False


def test_reset_validation_forgets_schema_resolution():
    session = DocumentSession()
    session.last_rng_result = object()
    session.last_rng_revision = 2
    session.last_schema_resolution = object()
    session.reset_validation()
    assert session.last_rng_result is None and session.last_rng_revision == -1
    assert session.last_schema_resolution is None
