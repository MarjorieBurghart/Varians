# -*- coding: utf-8 -*-
"""Un cache de Manifest IIIF abîmé (iiif/<témoin>.manifest.json : JSON
illisible, ou JSON qui n'est pas un manifeste) ne bloque pas l'ouverture du
projet : le témoin garde les images de son cache d'alignement, comme quand
le cache est absent. Les erreurs de liens explicites, elles, ne sont pas
masquées (règle inchangée)."""
from __future__ import annotations

import pytest

from iiif_manifest import cache_path
from image_sources import apply_witness_image_policy

CACHE = {"pages": [{"id": "p1", "image": {"type": "file", "path": "images/A/1.jpg"}, "lines": []}]}


@pytest.mark.parametrize("content", ["{ pas du JSON", '{"_format": "x", "manifest": {"foo": 1}}', "[]"])
def test_a_damaged_manifest_cache_does_not_block_the_project(tmp_path, content):
    path = cache_path(tmp_path, "A")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    result = apply_witness_image_policy(CACHE, "iiif", "https://example.org/iiif/manifest.json",
                                        project_root=tmp_path, witness_id="A")
    assert result == CACHE
