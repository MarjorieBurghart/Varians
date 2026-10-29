# -*- coding: utf-8 -*-
"""Red team (intégrité et sécurité, B1) : un schéma distant déclaré par
``<?xml-model href="http://…">`` est gardé dans le cache des schémas, et
jamais ailleurs. Le chemin du cache venait du chemin de l'adresse, décodé
(« %2e%2e » donnait « .. »), sans contrôle : ouvrir un fichier reçu pouvait
écrire n'importe quel contenu n'importe où (dossier « Démarrage » de
Windows, par exemple). Sans réseau : ``urlopen`` est remplacé."""
from __future__ import annotations

from pathlib import Path

import pytest

import schema_resolution
from schema_resolution import _fetch_remote_rng, _url_cache_path


@pytest.mark.parametrize("url", [
    "http://host/%2e%2e/%2e%2e/%2e%2e/Startup/evil.bat",
    "http://host/../../outside.rng",
    "http://host/a/%2E%2E/%2e%2E/../../outside.rng",
    "http://host/%2e%2e%2f%2e%2e%2foutside.rng",
    "http://host/..%5c..%5coutside.rng",
    "http://host/C:/Windows/evil.rng",
    "http://host/%5c%5cserver%5cshare%5cevil.rng",
    "http://host//etc/evil.rng",
])
def test_a_remote_schema_path_never_leaves_the_cache(tmp_path, url):
    cache = tmp_path / "cache"
    path = _url_cache_path(url, cache)
    assert path.resolve().is_relative_to(cache.resolve()), path
    assert ".." not in path.relative_to(cache).parts and ":" not in str(path.relative_to(cache))


def test_an_ordinary_schema_keeps_its_place_in_the_cache(tmp_path):
    cache = tmp_path / "cache"
    url = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
    assert _url_cache_path(url, cache) == cache / "www.tei-c.org" / "release/xml/tei/custom/schema/relaxng/tei_all.rng"
    query = _url_cache_path("https://h/s.rng?v=2", cache)
    assert query.parent == cache / "h" and query.name.startswith("s.rng.q-")


class Response:
    def __init__(self, url, data):
        self.url, self.data = url, data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self.data

    def geturl(self):
        return self.url


def test_a_hostile_schema_is_written_inside_the_cache(tmp_path, monkeypatch):
    cache = tmp_path / "home" / "cache"
    url = "http://127.0.0.1/%2e%2e/%2e%2e/%2e%2e/Startup/evil.bat"
    monkeypatch.setattr(schema_resolution, "urlopen", lambda request, timeout=None: Response(url, b"@echo off\r\n"))
    path, _from_cache = _fetch_remote_rng(url, cache, may_fetch=lambda url: True)
    assert path.resolve().is_relative_to(cache.resolve()) and path.read_bytes() == b"@echo off\r\n"
    assert not (tmp_path / "Startup").exists() and not (tmp_path / "home" / "Startup").exists()
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert written == [path]


def test_a_hostile_dependency_is_written_inside_the_cache(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    main = "http://127.0.0.1/schema/main.rng"
    dependency = "http://127.0.0.1/%2e%2e/%2e%2e/%2e%2e/%2e%2e/evil.rng"
    pages = {main: ('<grammar xmlns="http://relaxng.org/ns/structure/1.0">'
                    f'<include href="{dependency}"/><start><empty/></start></grammar>').encode(),
             dependency: b'<grammar xmlns="http://relaxng.org/ns/structure/1.0"/>'}
    monkeypatch.setattr(schema_resolution, "urlopen",
                        lambda request, timeout=None: Response(request.full_url, pages[request.full_url]))
    path, _from_cache = _fetch_remote_rng(main, cache, may_fetch=lambda url: True)
    written = [p for p in tmp_path.rglob("*") if p.is_file()]
    assert len(written) == 2 and all(p.resolve().is_relative_to(cache.resolve()) for p in written), written
