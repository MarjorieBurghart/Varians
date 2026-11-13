# -*- coding: utf-8 -*-
"""Adresses venues d'un projet (V0.9.4.6).

Le bouton « Page ↗ » d'un témoin ouvre l'image IIIF de la page hors de
Varians. L'adresse vient du projet, qui peut venir d'un tiers : seules les
adresses web (http, https) sont ouvertes, comme dans la boîte des pages
IIIF ; une adresse ``file:``, ``smb:``, ``javascript:``… ne l'est pas."""
from __future__ import annotations

import pytest

from image_sources import full_page_target


def _iiif_page(**image):
    return {"id": "p1", "image": {"type": "iiif", **image}}


@pytest.mark.parametrize("url", ["https://gallica.bnf.fr/iiif/ark:/12148/x/f1/full/full/0/native.jpg",
                                 "http://example.org/iiif/f1/full/max/0/default.jpg"])
def test_a_web_address_is_opened(url):
    assert full_page_target(_iiif_page(image=url)) == ("url", url)


@pytest.mark.parametrize("url", ["file:///etc/passwd", "FILE:///C:/Windows/win.ini", "smb://serveur/partage/f1.jpg",
                                 "javascript:alert(1)", "vbscript:msgbox", "ms-settings:privacy", "../images/f1.jpg"])
def test_another_address_is_not_opened(url):
    assert full_page_target(_iiif_page(image=url)) == ("none", None)
    assert full_page_target(_iiif_page(service=url)) == ("none", None)
