# -*- coding: utf-8 -*-
"""Libellé de repli d'une surface IIIF sans libellé : « Page n » compté à
partir de 1, comme son identifiant (<témoin>-p0001) et comme les libellés
qu'attend ``removable_generated_iiif_surfaces``. (Le lecteur de manifestes
nomme déjà ainsi les canevas sans libellé ; ce repli ne sert que si une page
arrive sans aucun libellé.)"""
from __future__ import annotations

from types import SimpleNamespace

import iiif_manifest
from tei_facsimile import project_facsimile_pages


def test_an_unlabelled_iiif_page_is_numbered_from_one(tmp_path, monkeypatch):
    pages = [{"id": f"iiif-000{i}", "image": {"image": f"https://example.org/i{i}.jpg",
                                               "canvas": f"https://example.org/c{i}"}, "lines": []} for i in (1, 2)]
    monkeypatch.setattr(iiif_manifest, "read_cache", lambda path, source=None: SimpleNamespace(pages=pages))
    witness = SimpleNamespace(id="A", image_source_type="iiif", image_source_value="https://example.org/m.json",
                              iiif_selected_canvases=(), iiif_selection_mode="all", alignment=None)
    result = project_facsimile_pages([witness], tmp_path, tmp_path / "edition.xml")
    assert [(page.surface_id, page.label) for page in result] == [("A-p0001", "Page 1"), ("A-p0002", "Page 2")]
