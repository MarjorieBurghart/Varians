# -*- coding: utf-8 -*-
"""« Marquer la page » et les identifiants XML (V0.9.2.8.2).

Tout identifiant permis par XML (un NCName : lettres de toutes les
écritures, puis chiffres, « _ », « - », « . », « · », signes combinants)
est accepté pour le témoin (``@edRef``) et pour la surface (``@facs``) ;
l'identifiant de surface proposé par défaut garde ces caractères, si bien
que deux témoins « Σ » et « Δ » n'ont plus les mêmes surfaces. Les
identifiants en caractères latins de base ne changent pas. La même règle
vaut pour « Débugger l'apparat »."""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

from apparatus_xpath import witness_xpath
from tei_facsimile import FacsimilePage, default_surface_id, sync_facsimile_text, upsert_pb_at_position, valid_xml_id

TEI = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
WITNESSES = ["Σ", "σ1", "Ä", "Ж2", "伝本", "é", "é", "A·B", "_1760", "T1", "a.b-c"]


def _tei(body="<p>Lorem ipsum dolor</p>"):
    return (f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
            '<publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc>'
            f'</teiHeader><text><body>{body}</body></text></TEI>')


@pytest.mark.parametrize("wid", WITNESSES)
def test_mark_page_accepts_every_xml_identifier(wid):
    surface = default_surface_id(wid, 1)
    assert valid_xml_id(wid) and valid_xml_id(surface)
    text = _tei()
    out, _position, mode = upsert_pb_at_position(text, text.index("ipsum"), "12r", surface, witness_id=wid)
    assert mode == "inserted"
    assert f'<pb n="12r" edRef="#{wid}" facs="#{surface}"/>' in out
    ET.fromstring(out)


@pytest.mark.parametrize("wid", ["1760", "T 2", "a:b", "-x", ".a", "A/2", "a\"b"])
def test_values_that_are_not_xml_identifiers_are_still_refused(wid):
    assert not valid_xml_id(wid)
    text = _tei()
    with pytest.raises(ValueError):
        upsert_pb_at_position(text, text.index("ipsum"), "12r", "S-p0001", witness_id=wid)
    with pytest.raises(ValueError):
        upsert_pb_at_position(text, text.index("ipsum"), "12r", wid)


def test_default_surface_ids_keep_the_witness_identifier():
    assert default_surface_id("Σ", 1) == "Σ-p0001"
    assert default_surface_id("Δ", 1) == "Δ-p0001"
    assert default_surface_id("伝本", 12) == "伝本-p0012"
    # Caractères latins de base : comme avant.
    assert default_surface_id("T1", 3) == "T1-p0003"
    assert default_surface_id("T 2", 1) == "T-2-p0001"
    assert default_surface_id("1760", 1) == "W-1760-p0001"
    assert default_surface_id("", 1) == "W-p0001"


def test_the_facsimile_layer_takes_the_surfaces_of_every_witness():
    pages = [FacsimilePage("Σ", default_surface_id("Σ", 1), "1r", "images/s1.jpg"),
             FacsimilePage("Δ", default_surface_id("Δ", 1), "1r", "images/d1.jpg")]
    updated, report = sync_facsimile_text(_tei(), pages)
    assert not report.conflicts, report.conflicts
    ids = [el.get(XML_ID) for el in ET.fromstring(updated).iter(f"{{{TEI}}}surface")]
    assert ids == ["Σ-p0001", "Δ-p0001"]


@pytest.mark.parametrize("wid", ["Σ", "é", "A·B", "伝本"])
def test_the_apparatus_queries_accept_every_xml_identifier(wid):
    assert f" #{wid} " in witness_xpath(wid, present=True, rdg_only=False)
