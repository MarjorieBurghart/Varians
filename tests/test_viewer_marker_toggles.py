# -*- coding: utf-8 -*-
"""Viewer web : le lecteur peut masquer les marqueurs de variantes et de notes."""
from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from web_viewer.generator import make_html

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
KEYS = ("viewer.show_variants", "viewer.show_variants.tip", "viewer.show_notes", "viewer.show_notes.tip")


def marker_data():
    """Édition minimale avec un marqueur de variante et un marqueur de note."""
    key = "A-p1::1"
    line = {"line": 1, "bbox": [2, 2, 12, 10], "order": 1}
    return {
        "meta": {"title": "Marqueurs", "base_witness": "A", "display_witnesses": ["A"],
                 "has_images": False, "line_sync": True, "lines": 1, "variants": 1,
                 "pages": 1, "external_iiif_images": 0, "pivot_lb_index": {"count_match": True}},
        "witnesses": [{"id": "A", "label": "A", "role": "base", "line_sync": True, "folios": [], "meta": {},
                       "pages": [{"id": "A-p1", "image": {"type": "none"}, "alto_width": 40,
                                  "alto_height": 30, "lines": [line]}]}],
        "document": {"blocks": [{"type": "p", "segments": [
            {"kind": "text", "text": "In principio", "line_key": key},
            {"kind": "variant-marker", "ann_id": "v1", "line_key": key},
            {"kind": "text", "text": " erat verbum", "line_key": key},
            {"kind": "note", "ann_id": "n1", "line_key": key},
        ]}]},
        "annotations": {"v1": {"kind": "variant", "html": "lectio"}, "n1": {"kind": "note", "html": "nota"}},
        "i18n": {"default": "fr", "fallback": "fr", "languages": [{"code": "fr", "label": "Français"}],
                 "catalogs": {"fr": {"viewer.show_variants": "Variantes", "viewer.show_notes": "Notes",
                                     "viewer.show_variants.tip": "Marqueurs de variantes",
                                     "viewer.show_notes.tip": "Marqueurs de notes"}}},
    }


def test_viewer_offers_two_marker_toggles():
    html = make_html(marker_data())
    assert 'id="showVariants" type="checkbox" checked' in html
    assert 'id="showNotes" type="checkbox" checked' in html
    assert ".hide-variant-markers .ann-marker.v" in html
    assert ".hide-note-markers .ann-marker.n" in html
    for key in KEYS:
        assert f"t('{key}')" in html, key
    # Préférence du lecteur, mémorisée sans jamais modifier le texte publié.
    assert "safeStorage.setItem(storageKey" in html


def test_marker_toggle_labels_exist_in_the_seven_catalogs():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key"): string.text for string in root.findall("string")}
        for key in KEYS:
            assert catalog.get(key), (language, key)
