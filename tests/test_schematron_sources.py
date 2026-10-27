# -*- coding: utf-8 -*-
"""Sources des règles Schematron (V0.9.2.3, ``schema_resolution``) : le RNG
employé pour la validation, puis chaque déclaration ``xml-model`` de type
Schematron, sans doublon ; les adresses distantes passent par le cache des
schémas. Sans Qt, sans réseau (``urlopen`` est remplacé)."""
from __future__ import annotations

from pathlib import Path

import pytest

import schema_resolution
from schema_resolution import RELAXNG_NS, SCHEMATRON_NS, resolve_schema

TEI_ALL = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
RNG = '<grammar xmlns="http://relaxng.org/ns/structure/1.0"><start><element name="r"><text/></element></start></grammar>'
SCH = f'<schema xmlns="{SCHEMATRON_NS}"><pattern><rule context="r"><assert test="1">x</assert></rule></pattern></schema>'


def _model(href, schematypens):
    return f'<?xml-model href="{href}" type="application/xml" schematypens="{schematypens}"?>\n'


def _document(tmp_path, *models, name="edition.xml"):
    text = '<?xml version="1.0"?>\n' + "".join(models) + "<r/>\n"
    path = tmp_path / name
    path.write_text(text, encoding="utf-8")
    return text, path


def _resolve(tmp_path, text, path, mode="auto", **options):
    options.setdefault("cache_dir", tmp_path / "cache")
    return resolve_schema(mode=mode, xml_text=text, xml_path=path, **options)


@pytest.fixture
def local(tmp_path):
    (tmp_path / "edition.rng").write_text(RNG, encoding="utf-8")
    (tmp_path / "regles.sch").write_text(SCH, encoding="utf-8")
    return tmp_path


class FakeWeb:
    """Remplace ``urlopen`` : ``pages`` donne le texte de chaque adresse."""

    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def __call__(self, request, timeout=None):
        url = request.full_url
        self.calls.append(url)
        if url not in self.pages:
            raise OSError(f"404 {url}")
        data = self.pages[url].encode("utf-8")

        class Response:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def read(self):
                return data

            def geturl(self):
                return url

        return Response()


@pytest.fixture
def web(monkeypatch):
    fake = FakeWeb({})
    monkeypatch.setattr(schema_resolution, "urlopen", fake)
    return fake


def test_the_rng_used_comes_first_then_the_declared_schematron(local):
    text, path = _document(local, _model("edition.rng", RELAXNG_NS), _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path)
    assert resolution.schematron_sources == ((local / "edition.rng").resolve(), (local / "regles.sch").resolve())
    assert resolution.schematron_errors == ()


def test_a_file_declared_twice_is_a_single_source(local):
    text, path = _document(local, _model("edition.rng", RELAXNG_NS), _model("edition.rng", SCHEMATRON_NS),
                           _model("./regles.sch", SCHEMATRON_NS), _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path)
    assert resolution.schematron_sources == ((local / "edition.rng").resolve(), (local / "regles.sch").resolve())


def test_with_the_project_schema_the_declarations_still_count(local):
    project_rng = local / "projet.rng"
    project_rng.write_text(RNG, encoding="utf-8")
    text, path = _document(local, _model("edition.rng", RELAXNG_NS), _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path, mode="file", project_schema=project_rng)
    assert resolution.schema_path == project_rng.resolve()
    assert resolution.schematron_sources == (project_rng.resolve(), (local / "regles.sch").resolve())


def test_without_validation_there_is_no_source(local):
    text, path = _document(local, _model("edition.rng", RELAXNG_NS), _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path, mode="none")
    assert resolution.schematron_sources == () and resolution.schematron_errors == ()
    # La déclaration reste détectée.
    assert [declaration.href for declaration in resolution.schematron] == ["regles.sch"]


def test_a_schematron_file_can_be_declared_without_rng(local):
    text, path = _document(local, _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path)
    assert resolution.schema_path is None and resolution.error == ""
    assert resolution.schematron_sources == ((local / "regles.sch").resolve(),)


def test_a_missing_schematron_file_is_reported_without_stopping_the_others(local):
    text, path = _document(local, _model("edition.rng", RELAXNG_NS), _model("absente.sch", SCHEMATRON_NS),
                           _model("regles.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path)
    assert resolution.error == ""
    assert resolution.schematron_sources == ((local / "edition.rng").resolve(), (local / "regles.sch").resolve())
    [(href, error)] = resolution.schematron_errors
    assert href == "absente.sch" and "absente.sch" in error


def test_the_tei_declarations_share_one_download_and_one_source(tmp_path, web):
    web.pages[TEI_ALL] = RNG
    text, path = _document(tmp_path, _model(TEI_ALL, RELAXNG_NS), _model(TEI_ALL, SCHEMATRON_NS))
    resolution = _resolve(tmp_path, text, path)
    assert resolution.schematron_sources == (resolution.schema_path,)
    assert web.calls == [TEI_ALL]
    # Même en demandant d'actualiser le cache.
    resolution = _resolve(tmp_path, text, path, force_refresh=True)
    assert resolution.schematron_sources == (resolution.schema_path,)
    assert web.calls == [TEI_ALL, TEI_ALL]


def test_a_remote_schematron_file_is_cached_with_its_includes(tmp_path, web):
    web.pages["https://example.org/regles/main.sch"] = (
        f'<schema xmlns="{SCHEMATRON_NS}"><include href="motifs/a.sch"/></schema>')
    web.pages["https://example.org/regles/motifs/a.sch"] = (
        f'<pattern xmlns="{SCHEMATRON_NS}"><rule context="r"><assert test="1">x</assert></rule></pattern>')
    text, path = _document(tmp_path, _model("https://example.org/regles/main.sch", SCHEMATRON_NS))
    resolution = _resolve(tmp_path, text, path)
    [source] = resolution.schematron_sources
    assert source.is_file() and tmp_path / "cache" in source.parents
    # L'inclusion désigne sa copie dans le cache.
    included = tmp_path / "cache" / "example.org" / "regles" / "motifs" / "a.sch"
    assert included.is_file() and included.resolve().as_uri() in source.read_text(encoding="utf-8")
    assert len(web.calls) == 2
    # La fois suivante : le cache, sans réseau.
    assert _resolve(tmp_path, text, path).schematron_sources == (source,)
    assert len(web.calls) == 2


def test_an_unreachable_remote_schematron_is_reported(tmp_path, web, local):
    text, path = _document(local, _model("edition.rng", RELAXNG_NS),
                           _model("https://example.org/absente.sch", SCHEMATRON_NS))
    resolution = _resolve(local, text, path)
    assert resolution.error == "" and resolution.schematron_sources == ((local / "edition.rng").resolve(),)
    [(href, error)] = resolution.schematron_errors
    assert href == "https://example.org/absente.sch" and "404" in error
