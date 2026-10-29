# -*- coding: utf-8 -*-
"""Red team 2 (cohérence des textes, D7) : des messages s'affichaient dans
une seule langue, quelle que soit celle de l'interface.

- conflits du <facsimile> (« XML non bien formé », « cet xml:id existe
  déjà », « Aucun élément <text> ») ;
- squelette du témoin pivot : erreurs (« Invalid pivot witness xml:id »,
  « TEI_NOT_EMPTY »…), avertissements et sources des lignes du détail ;
- associations OCR ↔ IIIF (« multi-page OCR »…) ;
- position d'une erreur XML (« — ligne 3, colonne 7 ») ;
- viewer web : libellés d'accessibilité de la recherche, en anglais, et
  « 1 lignes » dans l'en-tête d'un panneau.

Ces modules, sans interface, rendent des messages (i18n.Message) : leur
texte est le français des catalogues, et l'interface les traduit dans sa
langue avec leur clé."""
from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from i18n import I18nManager, Message, message_text
from project_management import LocalImageDraft, WitnessDraft, minimal_tei_text
from tei_facsimile import FacsimilePage, sync_facsimile_text
from tei_pivot_scaffold import PivotPage, PivotScaffoldPlan, build_pivot_plan, render_pivot_scaffold

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")


def _english():
    return I18nManager(ROOT / "i18n", "en", "en").tr


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {node.get("key") for node in root.findall("string")}


def test_a_message_keeps_its_key_and_reads_as_french():
    message = Message("facsimile.conflict.no_text")
    assert message.key == "facsimile.conflict.no_text" and message.startswith("Aucun élément <text>")
    assert message_text(message, _english()).startswith("No <text> element")
    assert message_text("texte ordinaire", _english()) == "texte ordinaire"
    nested = Message("pivot.error.surface_conflict", conflicts=[Message("facsimile.conflict.no_text")])
    assert "Aucun élément <text>" in nested and "No <text> element" in message_text(nested, _english())


def test_the_conflicts_of_the_facsimile_are_translated():
    page = FacsimilePage("A", "A-p0001", "1r", "images/1r.jpg")
    _text, report = sync_facsimile_text("<TEI><text>", [page])
    assert [c.key for c in report.conflicts] == ["facsimile.conflict.malformed"]
    assert message_text(report.conflicts[0], _english()).startswith("XML not well formed")
    tei = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/></TEI>'
    _text, report = sync_facsimile_text(tei, [page])
    assert [c.key for c in report.conflicts] == ["facsimile.conflict.no_text"]
    tei = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body><p xml:id="A-p0001"/></body>'
           '</text></TEI>')
    _text, report = sync_facsimile_text(tei, [page])
    assert [(c.key, c.values["surface"]) for c in report.conflicts] == [("facsimile.conflict.id_used", "A-p0001")]


def _witness(tmp_path):
    rows = [{"id": "p1", "label": "1r", "image": {"type": "file", "path": str(tmp_path / "1r.jpg")},
             "lines": [{"line": n} for n in range(3, 6)]}]
    source = tmp_path / "A.json"
    source.write_text(json.dumps({"pages": rows}), encoding="utf-8")
    images = [LocalImageDraft(tmp_path / "1r.jpg", "1r", surface_id="A-p0001")]
    return WitnessDraft("A", "Pivot", image_source_type="files", image_files=images, alignment=source)


def test_the_scaffold_of_the_pivot_speaks_the_language_of_the_interface(tmp_path):
    witness = _witness(tmp_path)
    plan = build_pivot_plan([witness], "A", tmp_path, tmp_path / "edition.xml")
    assert plan.warnings and all(isinstance(w, Message) for w in plan.warnings)
    english = [message_text(w, _english()) for w in plan.warnings]
    assert any("lines absent from it are not invented" in w for w in english), english
    assert plan.pages[0].evidence == "JSON partiel"
    assert message_text(plan.pages[0].evidence, _english()) == "partial JSON"
    with pytest.raises(ValueError) as error:
        build_pivot_plan([witness], "1 A", tmp_path, tmp_path / "edition.xml")
    assert error.value.message.key == "pivot.error.invalid_witness"
    with pytest.raises(ValueError) as error:
        build_pivot_plan([witness], "B", tmp_path, tmp_path / "edition.xml")
    assert error.value.message.key == "pivot.error.unknown_witness"
    edition = minimal_tei_text("Essai", [witness], "A").replace("<p/>", "<p>texte</p>").replace(
        "<p></p>", "<p>texte</p>")
    with pytest.raises(ValueError, match="TEI_NOT_EMPTY") as error:
        render_pivot_scaffold(edition, PivotScaffoldPlan("A", [PivotPage("1r", "A-p0001", 3, "OCR")]))
    assert error.value.message.key == "pivot.not_empty"


def test_the_problems_of_ocr_links_are_translated(tmp_path):
    from iiif_manifest import parse_manifest
    from iiif_page_selection import propose_exact_ocr_links
    from types import SimpleNamespace
    manifest = parse_manifest({
        "@context": "http://iiif.io/api/presentation/2/context.json", "@id": "https://example.org/m",
        "@type": "sc:Manifest", "label": "M",
        "sequences": [{"canvases": [{"@id": "https://example.org/c1", "@type": "sc:Canvas", "label": "1r",
                                     "images": [{"resource": {"@id": "https://example.org/1r.jpg"}}]}]}]})
    broken = tmp_path / "1r.xml"
    broken.write_text("<alto", encoding="utf-8")
    _links, problems = propose_exact_ocr_links(manifest, [SimpleNamespace(path=broken)])
    assert [p.key for p in problems] == ["iiif.ocr_link.unreadable"]


def test_every_message_key_used_by_the_modules_exists_in_every_language():
    keys = set()
    for path in ROOT.glob("*.py"):
        keys |= set(re.findall(r'Message\(\s*["\']([\w.]+)["\']', path.read_text(encoding="utf-8")))
    assert len(keys) >= 30
    for language in LANGUAGES:
        assert keys - _catalog(language) == set(), language


def test_the_place_of_an_xml_error_is_translated():
    source = (ROOT / "editeur_tei.py").read_text(encoding="utf-8")
    assert "ligne {line}, colonne" not in source
    for language in LANGUAGES:
        assert "xml.invalid.where" in _catalog(language)


def test_the_viewer_names_its_search_controls_in_the_interface_language():
    from web_viewer.generator import HTML_TEMPLATE
    assert not re.search(r'aria-label="[A-Z][a-z]', HTML_TEMPLATE)
    language = HTML_TEMPLATE.split("function applyLanguage(){", 1)[1].split("\n", 1)[0]
    for key in ("viewer.search.placeholder", "viewer.search.run", "viewer.search.close"):
        assert f"setAttribute('aria-label',t('{key}'))" in language, key
    cards = HTML_TEMPLATE.split("function cardHTML(w){", 1)[1].split("\n", 1)[0]
    assert "t('common.lines')" not in cards and "viewer.card.lines" in cards
