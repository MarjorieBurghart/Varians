# -*- coding: utf-8 -*-
"""Frappe dans une édition dont les pages ont des ``tei_surface_id`` (V0.9.3.2).

Chaque frappe déplace le curseur ; les panneaux des témoins se
resynchronisent alors, et ``_refresh_folio_navigation`` relisait les folios
de chaque témoin : le libellé de chaque page (chemin de son image résolu sur
le disque), puis tout le document analysé une fois par témoin, puis la liste
des folios du panneau reconstruite. Désormais :

- les libellés des pages sont calculés une fois par liste de pages ;
- les folios ne dépendent que du ``<facsimile>`` : analysé seul, une fois
  pour tous les témoins, et seulement quand il change ; un texte
  momentanément mal formé ailleurs (balise en cours de frappe) ne fait plus
  perdre les zones des folios ;
- la liste d'un panneau n'est reconstruite que si ses folios changent ;
"""
from __future__ import annotations

import textwrap
from types import SimpleNamespace

import pytest

import folio_navigation as F
from folio_navigation import folios_for_witness, split_surface_into_folios
from varians_source import method_source

BASE = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><facsimile>
 <surface xml:id="L-p0008" n="008"><graphic url="spread.jpg"/></surface>
 <surface xml:id="L-p0009" n="009"><graphic url="next.jpg"/></surface>
</facsimile><text><body><p>abc</p></body></text></TEI>'''


def _spread():
    xml, ids = split_surface_into_folios(BASE, "L-p0008", "f002v", "f003r", 3924, 2704)
    return xml, ids


# --- Folios lus dans le seul <facsimile> ---------------------------------------

def test_a_malformed_text_outside_the_facsimile_keeps_the_zones():
    """Décision V0.9.3.2 : une balise en cours de frappe dans le texte ne fait
    plus disparaître les zones (jusqu'ici, retour aux seules surfaces)."""
    xml, ids = _spread()
    malformed = xml.replace("<p>abc</p>", "<p>ab<hi rend=</p>")
    assert [f.ref for f in folios_for_witness(malformed, "L", ["L-p0008"])] == ["L-p0008", *ids]


def test_a_malformed_facsimile_falls_back_to_the_surfaces():
    xml, ids = _spread()
    malformed = xml.replace('<graphic url="spread.jpg"/>', '<graphic url="spread.jpg">')
    assert [f.ref for f in folios_for_witness(malformed, "L", ["L-p0008"], {"L-p0008": "spread"})] == ["L-p0008"]


def test_the_facsimile_markup_ignores_the_text_and_the_comments():
    xml, _ids = _spread()
    markup = F.facsimile_markup(xml)
    assert markup.startswith("<facsimile>") and markup.endswith("</facsimile>") and "abc" not in markup
    assert F.facsimile_markup(xml.replace("abc", "abcd<hi")) == markup
    commented = xml.replace("<text>", '<!-- <facsimile><surface xml:id="X"/></facsimile> --><text>')
    assert F.facsimile_markup(commented) == markup
    prefixed = ('<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:facsimile><tei:surface xml:id="A"/>'
                '</tei:facsimile><tei:text/></tei:TEI>')
    assert F.facsimile_markup(prefixed) == '<tei:facsimile><tei:surface xml:id="A"/></tei:facsimile>'
    assert [f.ref for f in folios_for_witness(prefixed, "A", ["A"])] == ["A"]


def test_a_prefix_declared_above_the_facsimile_falls_back_to_the_whole_document():
    xml = ('<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:my="urn:x"><facsimile>'
           '<surface xml:id="S" my:k="1"><zone xml:id="S-a" n="1r" ulx="0" uly="0" lrx="5" lry="5"/></surface>'
           '</facsimile><text/></TEI>')
    assert [f.ref for f in folios_for_witness(xml, "W", ["S"])] == ["S", "S-a"]


# --- Rafraîchissement des panneaux (corps réel de la méthode) -------------------

class Counter:
    def __init__(self, function):
        self.function, self.calls = function, 0

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.function(*args, **kwargs)


class Document:
    def __init__(self, text):
        self.text, self._revision = text, 1

    def edit(self, text):
        self.text = text
        self._revision += 1

    def toPlainText(self):
        return self.text

    def revision(self):
        return self._revision


class Panel:
    sync_enabled = False

    def __init__(self, surfaces):
        self.items = [{"p": {"tei_surface_id": sid, "id": sid, "image": {"type": "file", "path": f"{sid}.jpg",
                                                                         "label": f"page {sid}"}}}
                      for sid in surfaces]
        self._surface_indices = {sid: index for index, sid in enumerate(surfaces)}
        self.folios = []
        self.folio_calls = []

    def set_folios(self, folios):
        self.folios = list(folios)
        self.folio_calls.append(list(folios))


@pytest.fixture
def window(tmp_path):
    import image_sources
    counters = {name: Counter(getattr(source, name)) for source, name in (
        (F, "facsimile_surfaces"), (image_sources, "page_label"))}
    namespace = {"folios_for_witness": folios_for_witness, "facsimile_markup": F.facsimile_markup,
                 "facsimile_surfaces": counters["facsimile_surfaces"]}
    namespace["surface_labels"] = lambda panel, root: image_sources.surface_labels(
        panel, root, label=counters["page_label"])
    exec(textwrap.dedent(method_source("MainWindow", "_refresh_folio_navigation")), namespace)
    xml, ids = _spread()
    document = Document(xml)
    session = SimpleNamespace(text_document=document)
    win = SimpleNamespace(edition_session=session, document=session, project=SimpleNamespace(root_dir=tmp_path),
                          panels={"L": Panel(["L-p0008", "L-p0009"]), "M": Panel(["L-p0009"])},
                          counters=counters, ids=ids)
    win.refresh = lambda text=None, force=False: namespace["_refresh_folio_navigation"](win, text, force)
    return win


def test_typing_in_the_text_rereads_neither_the_folios_nor_the_page_labels(window):
    window.refresh()
    assert [f.ref for f in window.panels["L"].folios] == ["L-p0008", *window.ids, "L-p0009"]
    assert window.counters["facsimile_surfaces"].calls == 1          # une analyse pour les deux témoins
    labels = window.counters["page_label"].calls
    assert labels == 3                                               # une fois par page
    document = window.edition_session.text_document
    base = document.text
    for typed in ("abcd", "abcd<hi", "abcd<hi rend=", "abcd<hi/>"):  # mal formé, puis de nouveau bien formé
        document.edit(base.replace("<p>abc</p>", f"<p>{typed}</p>"))
        window.refresh()
    assert window.counters["facsimile_surfaces"].calls == 1
    assert window.counters["page_label"].calls == labels
    assert [len(panel.folio_calls) for panel in window.panels.values()] == [1, 1]


def test_changing_the_facsimile_rereads_the_folios(window):
    window.refresh()
    document = window.edition_session.text_document
    document.edit(document.text.replace('<surface xml:id="L-p0009" n="009">', '<surface xml:id="L-p0009" n="9r">'))
    window.refresh()
    assert window.counters["facsimile_surfaces"].calls == 2
    assert [f.label for f in window.panels["M"].folios] == ["9r"]
    assert len(window.panels["M"].folio_calls) == 2


def test_new_pages_recompute_their_labels(window):
    window.refresh()
    labels = window.counters["page_label"].calls
    panel = window.panels["M"]
    panel.items = list(panel.items)                                  # pages rechargées
    window.refresh(force=True)
    assert window.counters["page_label"].calls == labels + 1


def test_a_forced_refresh_rereads_the_facsimile(window):
    window.refresh()
    window.refresh(force=True)
    assert window.counters["facsimile_surfaces"].calls == 2
