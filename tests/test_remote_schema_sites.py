# -*- coding: utf-8 -*-
"""Red team (sécurité, B2) : un document reçu peut déclarer un schéma ou des
règles Schematron sur n'importe quel site. Varians les téléchargeait dès
l'ouverture du document : le site apprenait que le document était ouvert,
et choisissait les règles appliquées. Seul le site de la TEI (tei-c.org)
est désormais consulté sans accord ; pour tout autre site, ``may_fetch``
(l'interface demande à l'utilisatrice) décide, y compris pour les fichiers
inclus et les redirections."""
from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse

import pytest

import schema_resolution
from schema_resolution import RELAXNG_NS, SCHEMATRON_NS, resolve_schema, trusted_schema_site

TEI_ALL = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
RNG = '<grammar xmlns="http://relaxng.org/ns/structure/1.0"><start><element name="TEI"><text/></element></start></grammar>'


def _model(href, ns):
    return f'<?xml version="1.0"?>\n<?xml-model href="{href}" schematypens="{ns}"?>\n<TEI/>'


class _Response:
    def __init__(self, url, data):
        self.url, self.data = url, data.encode("utf-8")

    def read(self):
        return self.data

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


@pytest.fixture
def web(monkeypatch):
    """Remplace ``urlopen`` : ``pages`` donne le texte de chaque adresse,
    ``requested`` les adresses demandées."""
    class Web:
        pages, requested = {}, []

    def fake(request, timeout=None):
        url = request.full_url
        Web.requested.append(url)
        return _Response(url, Web.pages[url])

    Web.pages, Web.requested = {}, []
    monkeypatch.setattr(schema_resolution, "urlopen", fake)
    return Web


def _resolve(tmp_path, text, **options):
    return resolve_schema(mode="auto", xml_text=text, xml_path=tmp_path / "doc.xml",
                          cache_dir=tmp_path / "cache", **options)


@pytest.mark.parametrize("url, trusted", [
    (TEI_ALL, True),
    ("http://tei-c.org/release/xml/tei/custom/schema/relaxng/tei_lite.rng", True),
    ("https://jenkins.tei-c.org/job/x.rng", True),
    ("https://tei-c.org.example.net/tei_all.rng", False),
    ("https://evil-tei-c.org/tei_all.rng", False),
    ("https://example.org/www.tei-c.org/tei_all.rng", False),
    ("https://user@example.org/tei_all.rng", False),
])
def test_only_the_tei_site_is_consulted_without_consent(url, trusted):
    assert trusted_schema_site(url) is trusted


def test_a_schema_on_another_site_is_not_fetched_without_consent(tmp_path, web):
    web.pages["https://example.org/schema.rng"] = RNG
    resolution = _resolve(tmp_path, _model("https://example.org/schema.rng", RELAXNG_NS))
    assert web.requested == []
    assert resolution.schema_path is None and resolution.refused_sites == ("example.org",)
    assert resolution.rng_refused_site == "example.org"


def test_rules_on_another_site_are_not_fetched_without_consent(tmp_path, web):
    web.pages["https://example.org/regles.sch"] = '<schema xmlns="http://purl.oclc.org/dsdl/schematron"/>'
    resolution = _resolve(tmp_path, _model("https://example.org/regles.sch", SCHEMATRON_NS))
    assert web.requested == []
    assert resolution.schematron_sources == () and resolution.schematron_errors == ()
    assert resolution.refused_sites == ("example.org",) and resolution.rng_refused_site == ""


def test_the_tei_schema_is_fetched_without_a_question(tmp_path, web):
    web.pages[TEI_ALL] = RNG
    asked = []
    resolution = _resolve(tmp_path, _model(TEI_ALL, RELAXNG_NS), may_fetch=lambda url: asked.append(url))
    assert web.requested == [TEI_ALL] and asked == []
    assert resolution.schema_path is not None and resolution.refused_sites == ()


def test_each_site_is_asked_for_including_included_files(tmp_path, web):
    web.pages["https://example.org/schema.rng"] = (
        '<grammar xmlns="http://relaxng.org/ns/structure/1.0"><include href="https://other.example/part.rng"/>'
        '<start><element name="TEI"><text/></element></start></grammar>')
    web.pages["https://other.example/part.rng"] = RNG
    asked = []

    def may_fetch(url):
        asked.append(url)
        return urlparse(url).hostname == "example.org"

    resolution = _resolve(tmp_path, _model("https://example.org/schema.rng", RELAXNG_NS), may_fetch=may_fetch)
    assert asked == ["https://example.org/schema.rng", "https://other.example/part.rng"]
    assert web.requested == ["https://example.org/schema.rng"]
    assert resolution.schema_path is None and resolution.refused_sites == ("other.example",)


def test_an_accepted_site_is_fetched(tmp_path, web):
    web.pages["https://example.org/schema.rng"] = RNG
    resolution = _resolve(tmp_path, _model("https://example.org/schema.rng", RELAXNG_NS), may_fetch=lambda url: True)
    assert web.requested == ["https://example.org/schema.rng"]
    assert resolution.schema_path is not None and resolution.refused_sites == ()


@pytest.fixture
def server():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append((self.headers.get("Host", "").split(":")[0], self.path))
            if self.path == "/redirige.rng":
                self.send_response(302)
                self.send_header("Location", f"http://localhost:{self.server.server_address[1]}/cible.rng")
                self.end_headers()
                return
            data = RNG.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield httpd.server_address[1], hits
    finally:
        httpd.shutdown()


def test_a_redirection_to_another_site_needs_consent_too(tmp_path, server):
    port, hits = server
    url = f"http://127.0.0.1:{port}/redirige.rng"
    asked = []

    def may_fetch(address):
        asked.append(address)
        return urlparse(address).hostname == "127.0.0.1"

    resolution = _resolve(tmp_path, _model(url, RELAXNG_NS), may_fetch=may_fetch)
    assert asked == [url, f"http://localhost:{port}/cible.rng"]
    assert hits == [("127.0.0.1", "/redirige.rng")]
    assert resolution.schema_path is None and resolution.refused_sites == ("localhost",)
