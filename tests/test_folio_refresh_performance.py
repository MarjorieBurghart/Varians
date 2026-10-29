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
- les ``<pb>`` d'un témoin sont lus une fois par texte : déplacer le curseur
  sans modifier le texte ne relit plus le document.
"""
from __future__ import annotations

import textwrap
from types import SimpleNamespace

import pytest

import folio_navigation as F
from folio_navigation import folio_at_position, folio_marks, folios_for_witness, split_surface_into_folios
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


# --- <pb> d'un témoin lus une fois par texte ---------------------------------------

def test_moving_the_cursor_does_not_reread_the_pb(monkeypatch):
    xml, ids = _spread()
    xml = xml.replace("<p>abc</p>", "".join(
        f'<p>{i}<pb edRef="#L" n="f00{2 + i % 2}{"v" if i % 2 == 0 else "r"}" facs="#{ids[i % 2]}"/>x</p>'
        for i in range(6)))
    folios = folios_for_witness(xml, "L", ["L-p0008"])
    scans = Counter(F._scan_folio_marks)
    monkeypatch.setattr(F, "_scan_folio_marks", scans)
    positions = [xml.index(f"<p>{i}<pb") for i in range(6)] + [len(xml)]
    found = [folio_at_position(xml, position, "L", folios) for position in positions]
    assert scans.calls == 1
    assert [f.ref if f else None for f in found] == [None, ids[0], ids[1], ids[0], ids[1], ids[0], ids[1]]
    assert len(folio_marks(xml, "L", folios)) == 6 and scans.calls == 1
    edited = xml.replace("<p>0", "<p>00")
    assert folio_at_position(edited, len(edited), "L", folios).ref == ids[1] and scans.calls == 2


def _reference_folio_marks(text, witness_id, folios, stop=None):
    """``folio_marks`` d'avant V0.9.3.2 (référence) : tout relu à chaque appel."""
    import re
    from tei_facsimile import _PB_RE, _attr
    lookup = F.folio_lookup(folios)
    stop = len(text) if stop is None else max(0, min(int(stop), len(text)))
    ignored = [(m.start(), m.end()) for rx in (
        re.compile(r'<!--.*?(?:-->|$)', re.S), re.compile(r'<!\[CDATA\[.*?(?:\]\]>|$)', re.S),
        re.compile(r'<\?.*?(?:\?>|$)', re.S)) for m in rx.finditer(text)]
    marks = []
    for m in _PB_RE.finditer(text):
        if m.end() > stop:
            break
        if any(a <= m.start() < b for a, b in ignored):
            continue
        tag = m.group()
        folio = F.pb_folio(_attr(tag, 'facs'), _attr(tag, 'edRef'), _attr(tag, 'n'), witness_id, lookup)
        if folio is not None:
            marks.append((folio, m.end()))
    return marks


def test_the_cached_pb_match_a_fresh_reading():
    xml, ids = _spread()
    xml = xml.replace("<p>abc</p>", f'<p><!-- <pb edRef="#L" facs="#{ids[1]}"/> <?x <pb edRef="#L"?> -->'
                                    f'<pb edRef="#L" facs="#{ids[0]}"/>a<![CDATA[<pb edRef="#L" n="f003r"/>]]>'
                                    f'<?pi <pb edRef="#L" n="f003r"/>?><pb edRef="#L" facs="#{ids[1]}"/>b'
                                    f'<pb edRef="#L" n="f002v"/>c<!-- unterminated <pb edRef="#L"/></p>')
    folios = folios_for_witness(xml, "L", ["L-p0008"])
    assert len(_reference_folio_marks(xml, "L", folios)) == 3
    for stop in range(0, len(xml) + 1, 7):
        assert folio_marks(xml, "L", folios, stop=stop) == _reference_folio_marks(xml, "L", folios, stop)


def test_alternating_between_a_part_and_the_edition_reads_each_text_once(monkeypatch):
    xml, ids = _spread()
    part = '<div><pb edRef="#L" n="f003r"/>abc</div>'
    folios = folios_for_witness(xml, "L", ["L-p0008"])
    scans = Counter(F._scan_folio_marks)
    monkeypatch.setattr(F, "_scan_folio_marks", scans)
    for _ in range(3):
        folio_at_position(xml, len(xml), "L", folios)
        assert folio_at_position(part, len(part), "L", folios).ref == ids[1]
    assert scans.calls == 2


@pytest.mark.parametrize("tag", ['<pb edRef="#L" n="f003r"/>', "<pb EDREF='#L' N='F003R'/>", '<tei:pb xml:n="x" n="f002v" edRef="#L"/>',
                                 '<pb facs="#L-p0008-right"/>', '<pb facs="#L-p0008" n="f003r"/>', '<pb edRef="#L&#x20;#M" n="f002v"/>',
                                 '<pb edRef="#M" n="f002v"/>', '<pb n="f002v"/>'])
def test_the_attributes_of_a_pb_are_read_as_before(tag):
    from tei_facsimile import _attr
    for name in ("facs", "edRef", "n"):
        assert F._pb_attr(tag, name) == _attr(tag, name)
    xml, _ids = _spread()
    xml = xml.replace("<p>abc</p>", f"<p>a{tag}b</p>")
    folios = folios_for_witness(xml, "L", ["L-p0008"])
    assert folio_marks(xml, "L", folios) == _reference_folio_marks(xml, "L", folios)


def test_adding_moving_or_removing_a_pb_is_seen_at_once():
    """Les pb gardés le sont pour un texte : toute modification, ici d'un pb,
    donne un autre texte, relu aussitôt. Le curseur est sur « C »."""
    xml, ids = _spread()
    first, second = (f'<pb edRef="#L" facs="#{ids[0]}"/>', f'<pb edRef="#L" facs="#{ids[1]}"/>')
    texts = {
        "départ": f"<p>a{first}b</p><p>C</p><p>d</p>",
        "ajout": f"<p>a{first}b</p><p>{second}C</p><p>d</p>",           # nouveau pb avant le curseur
        "déplacement": f"<p>a{first}b</p><p>C</p><p>{second}d</p>",     # le même pb, après le curseur
        "retrait": "<p>ab</p><p>C</p><p>d</p>",                         # premier pb retiré
    }
    folios = folios_for_witness(xml, "L", ["L-p0008"])
    seen = {}
    for name, body in texts.items():
        text = xml.replace("<p>abc</p>", body)
        seen[name] = getattr(folio_at_position(text, text.index("C</p>"), "L", folios), "ref", None)
        assert folio_marks(text, "L", folios) == _reference_folio_marks(text, "L", folios), name
    assert seen == {"départ": ids[0], "ajout": ids[1], "déplacement": ids[0], "retrait": None}
