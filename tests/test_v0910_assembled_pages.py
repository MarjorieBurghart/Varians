# -*- coding: utf-8 -*-
"""Témoins en mode page dans une édition en parties (V0.9.1.0), sans Qt : le
corps réel de ``_sync_page_panels_to_cursor`` et de
``_refresh_folio_navigation``, sur des objets factices.

Jeu « sermons » : dans l'ordre de l'édition, A a ses pages 12v et 13r dans
s01, aucune dans s02, 14v, 15r et 15v dans s03, 13v dans s04 et 14r dans
l'exemplum qu'inclut s04."""
from __future__ import annotations

import textwrap
from pathlib import Path
from types import SimpleNamespace

from folio_navigation import Folio, folio_at_position, folios_for_witness
from image_sources import page_label as image_page_label
from pivot_lines import include_spans, pivot_lines
from tei_facsimile import facsimile_ref_at_position
from varians_source import method_source

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
SERMONS = DATA / "sermons"
FOLIOS_A = [Folio(f"A{n}", f"A{n}", n) for n in ("12v", "13r", "13v", "14r", "14v", "15r", "15v")]


def _method(name):
    namespace = {"folio_at_position": folio_at_position, "facsimile_ref_at_position": facsimile_ref_at_position,
                 "folios_for_witness": folios_for_witness, "include_spans": include_spans,
                 "image_page_label": image_page_label}
    exec(textwrap.dedent(method_source("MainWindow", name)), namespace)
    return namespace[name]


class Panel:
    sync_enabled = False

    def __init__(self, folios=(), surfaces=()):
        self.folios = list(folios)
        self._surface_indices = {sid: index for index, sid in enumerate(surfaces)}
        self.items = []
        self.surface = None
        self.folio_calls = []

    def set_surface(self, ref):
        self.surface = ref
        return True

    def set_folios(self, folios):
        self.folio_calls.append(list(folios))


class Editor:
    def __init__(self, text, position):
        self.text, self.position = text, position

    def textCursor(self):
        return SimpleNamespace(position=lambda: self.position)

    def toPlainText(self):
        return self.text

    def document(self):
        return self

    def revision(self):
        return 1


class PageWindow:
    """Fenêtre réduite à la synchronisation des pages ; ``path`` affiché."""
    _sync_page_panels_to_cursor = _method("_sync_page_panels_to_cursor")

    def __init__(self, path, needle):
        text = path.read_text(encoding="utf-8")
        self.document = SimpleNamespace(path=path)
        self.editor = Editor(text, text.index(needle))
        self.panels = {"A": Panel(FOLIOS_A)}
        self.has_any_images = True
        self._last_synced_surface = None
        self.lines = pivot_lines(EDITION.read_text(encoding="utf-8"), EDITION, {}, "A")

    def _pivot_lines(self):
        return self.lines


def _page(path, needle):
    window = PageWindow(path, needle)
    window._sync_page_panels_to_cursor(True)
    return window.panels["A"].surface


def test_a_page_witness_follows_the_pb_of_the_displayed_part():
    assert _page(SERMONS / "s01.xml", "virgine") == "A12v"
    assert _page(SERMONS / "s03.xml", "Tria sunt") == "A14v"


def test_a_page_witness_keeps_its_page_at_the_junction_of_two_parts():
    assert _page(SERMONS / "s03.xml", "<head>") == "A13r"               # fin de s01
    assert _page(SERMONS / "s04.xml", "<head>") == "A15v"               # fin de s03
    assert _page(SERMONS / "s04_exemplum.xml", "Narrat") == "A13v"      # s04, avant l'exemplum


def test_without_parts_the_page_comes_from_the_displayed_text():
    window = PageWindow(SERMONS / "s03.xml", "<head>")
    window.lines = None
    window._sync_page_panels_to_cursor(True)
    assert window.panels["A"].surface is None                          # aucun pb avant, dans ce texte


class FolioWindow:
    """Fenêtre réduite à la liste des folios ; une partie est affichée."""
    _refresh_folio_navigation = _method("_refresh_folio_navigation")

    def __init__(self, edition_text):
        self.edition_session = SimpleNamespace(text_document=Editor(edition_text, 0))
        self.document = SimpleNamespace(path=SERMONS / "s01.xml")
        self.editor = Editor("<div/>", 0)
        self.panels = {"A": Panel(surfaces=["A-12v"])}
        self.project = SimpleNamespace(root_dir=DATA.parent)


def test_the_folios_are_read_in_the_facsimile_of_the_edition_when_a_part_is_displayed():
    edition = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><facsimile>'
               '<surface xml:id="A-12v" n="12v"/></facsimile><text/></TEI>')
    window = FolioWindow(edition)
    window._refresh_folio_navigation("<div/>")           # texte de la partie affichée
    assert [[(f.ref, f.label) for f in folios] for folios in window.panels["A"].folio_calls] == [
        [("A-12v", "12v")]]
    window._refresh_folio_navigation()                   # même révision de l'édition
    assert len(window.panels["A"].folio_calls) == 1
