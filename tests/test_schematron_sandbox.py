# -*- coding: utf-8 -*-
"""Red team (sécurité, B2) : des règles Schematron déclarées par un document
reçu sont exécutées par Saxon. Elles n'écrivent aucun fichier (un
xsl:result-document d'une feuille qu'elles incluent en écrivait un, n'importe
où), ne consultent pas le réseau (processus de validation, voir
test_check_without_network) ; celles qui sont hors du projet ne sont
appliquées qu'avec l'accord de l'utilisatrice (``rules_outside``)."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from lxml import etree

from schema_resolution import SchematronSource, default_schema_cache_dir, rules_outside

needs_saxon = pytest.mark.skipif(importlib.util.find_spec("saxonche") is None,
                                 reason="Saxon (saxonche) n'est pas installé")
APPLICATION = Path(__file__).resolve().parents[1]


@needs_saxon
def test_rules_write_no_file(tmp_path):
    import schematron

    written = tmp_path / "ailleurs" / "ecrit.txt"
    (tmp_path / "piege.xsl").write_text(
        '<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">'
        '<xsl:template match="/" mode="#all" priority="1000">'
        f'<xsl:result-document href="{written.as_uri()}" method="text">x</xsl:result-document>'
        '<xsl:next-match/></xsl:template></xsl:stylesheet>', encoding="utf-8")
    rules = tmp_path / "regles.sch"
    rules.write_text('<sch:schema xmlns:sch="http://purl.oclc.org/dsdl/schematron" queryBinding="xslt2"'
                     ' xmlns:xsl="http://www.w3.org/1999/XSL/Transform"><xsl:include href="piege.xsl"/>'
                     '<sch:pattern><sch:rule context="/*"><sch:assert test="false()">toujours</sch:assert>'
                     '</sch:rule></sch:pattern></sch:schema>', encoding="utf-8")
    tree = etree.fromstring(b"<TEI/>").getroottree()
    schematron.validate(tree, [rules], base=tmp_path / "doc.xml")
    assert not written.exists() and not written.parent.exists()


def test_rules_outside_the_project_are_those_to_confirm(tmp_path):
    project = tmp_path / "projet"
    inside = SchematronSource(project / "xml" / "regles.sch")
    elsewhere = SchematronSource(tmp_path / "ailleurs" / "regles.sch")
    cached = SchematronSource(default_schema_cache_dir() / "www.tei-c.org" / "tei_all.rng")
    shipped = SchematronSource(APPLICATION / "resources" / "regles.sch")
    declared = SchematronSource(tmp_path / "schemas" / "projet.rng")
    found = rules_outside((inside, elsewhere, cached, shipped, declared), project,
                          trusted=(tmp_path / "schemas" / "projet.rng",))
    assert found == (elsewhere,)
