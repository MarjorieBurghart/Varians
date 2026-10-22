# -*- coding: utf-8 -*-
"""Parcours d'un témoin dans son propre ordre (V0.9.1.4), sans Qt.

Un témoin a des lignes dans le JSON global de l'édition (numérotation
continue, segment None) et dans les JSON des textes synchronisés à part ;
dans un texte où il n'a pas de JSON, ses ``<pb>`` (témoin par pages). Son
parcours est la suite de ces arrêts dans l'ordre du manuscrit :

1. l'ordre de ses pages : le rang déclaré (images du témoin, ``declared``)
   s'il est connu pour toutes ; sinon la fusion des listes de pages de ses
   JSON, chacune déjà dans l'ordre du manuscrit, rapprochées par l'identité
   des pages (canevas IIIF, puis nom d'image, puis ``id``) ;
2. un texte dont aucune page ne se rattache aux autres est placé par le
   ``<locus from>`` du témoin, sinon par la foliotation de sa première page
   (un numéro suivi de r ou v) ;
3. sinon, il garde sa place dans l'ordre de l'édition, et le parcours le
   signale (``uncertain``) ;

puis, sur une page, l'ordre des lignes (numéro de ligne ALTO, commun aux JSON
qui se partagent une page).

Chaque arrêt mène à une ligne du pivot de son segment : celle que la ligne
désigne (la première dans l'ordre du pivot), ou, pour une ligne non reliée, la
ligne reliée qui la précède dans le texte.
"""
from __future__ import annotations

import heapq
import re
from collections import Counter
from dataclasses import dataclass, field, replace

from witness_resource_refresh import flatten_primary, flatten_secondary

_FOLIO_RE = re.compile(r"(\d+)\s*([rRvV])(?![A-Za-z])")


@dataclass(frozen=True)
class PageMark:
    """``<pb>`` d'un témoin par pages dans un texte : son folio, sa place
    (fichier, position) et la ligne du pivot du texte à cet endroit."""
    folio: str
    label: str
    location: tuple
    ordinal: int | None
    identity: str | None = None


@dataclass(frozen=True)
class Source:
    """Ce qu'a un témoin dans un segment : son JSON (``cache``), ou ses
    ``<pb>`` (``marks``). ``base_by_key`` : clé → rang des lignes du pivot du
    segment ; ``anchor`` : nombre de lignes du pivot de l'édition avant le
    texte (pour le placer dans l'ordre de l'édition) ; ``locus`` : le @from
    du <locus> du témoin pour ce texte."""
    segment: str | None
    cache: dict | None = None
    is_base: bool = False
    base_by_key: dict = field(default_factory=dict)
    anchor: int = 0
    marks: tuple = ()
    locus: str | None = None


@dataclass(frozen=True)
class Stop:
    """Arrêt du parcours : une ligne (``key`` : la clé de l'élément du
    panneau) ou un ``<pb>`` (``key`` : le folio, ``location`` : sa place)."""
    segment: str | None
    key: str
    page: str
    ordinal: int | None
    linked: bool = True
    location: tuple | None = None


def page_identity(page) -> str:
    """Identité d'une page d'un JSON, la même d'un JSON à l'autre."""
    iiif = page.get("iiif") if isinstance(page.get("iiif"), dict) else {}
    image = page.get("image") if isinstance(page.get("image"), dict) else {}
    canvas = iiif.get("id") or image.get("canvas") or page.get("iiif_canvas_key")
    if canvas:
        return f"canvas:{canvas}"
    if page.get("image_name"):
        return f"image:{page['image_name']}"
    return f"id:{page.get('id')}"


def page_label(page) -> str:
    iiif = page.get("iiif") if isinstance(page.get("iiif"), dict) else {}
    image = page.get("image") if isinstance(page.get("image"), dict) else {}
    return str(iiif.get("label") or image.get("label") or page.get("label") or "")


def folio_number(label):
    """(numéro, 0 pour recto, 1 pour verso) d'une foliotation, ou None."""
    match = _FOLIO_RE.search(str(label or ""))
    return (int(match.group(1)), 0 if match.group(2) in "rR" else 1) if match else None


def _line_number(line, index):
    try:
        return int(line.get("line"))
    except (TypeError, ValueError):
        return index


def _line_stops(source):
    """Arrêts d'un JSON : (identité de page, numéro de ligne, Stop), dans
    l'ordre des éléments du panneau (``flatten_primary`` ou
    ``flatten_secondary``), avec la ligne du pivot de chacun."""
    cache = source.cache or {"pages": []}
    items = (flatten_primary if source.is_base else flatten_secondary)(cache)[0]
    out = []
    for index, item in enumerate(items):
        page, line = item["p"], item["l"]
        if source.is_base:
            # Le pivot du segment : le rang de la ligne dans son JSON.
            ordinal = index
        else:
            ranks = [source.base_by_key[str(k)] for k in (line.get("base_keys") or line.get("keys816") or [])
                     if str(k) in source.base_by_key]
            ordinal = min(ranks) if ranks else None
        identity = page_identity(page)
        out.append((identity, _line_number(line, index), Stop(source.segment, item["key"], identity, ordinal)))
    return out


def _page_lists(sources, entries):
    """Pour chaque source, la liste ordonnée des identités de ses pages, et
    leurs étiquettes."""
    lists, labels = [], {}
    for source, stops in zip(sources, entries):
        pages = []
        for identity, _number, _stop in stops:
            if identity not in pages:
                pages.append(identity)
        lists.append(pages)
    for source in sources:
        for page in (source.cache or {}).get("pages", []) or []:
            labels.setdefault(page_identity(page), page_label(page))
        for mark in source.marks:
            labels.setdefault(mark.identity or f"folio:{mark.folio}", mark.label)
    return lists, labels


def _merge(lists, labels, loci):
    """Fusionne les listes de pages : rang de chaque page, et sources qui
    n'ont pu être placées."""
    sequence = []
    pending = [i for i, pages in enumerate(lists) if pages]
    progress = True
    while pending and progress:
        progress = False
        for i in list(pending):
            pages = lists[i]
            shared = [p for p in pages if p in sequence]
            if sequence and not shared:
                continue
            cursor = sequence.index(shared[0]) if shared else 0
            for p in pages:
                if p in sequence:
                    cursor = sequence.index(p) + 1
                else:
                    sequence.insert(cursor, p)
                    cursor += 1
            pending.remove(i)
            progress = True
    # Par le <locus from>, sinon par la foliotation de la première page.
    for i in list(pending):
        number = folio_number(loci[i]) or folio_number(labels.get(lists[i][0]))
        numbered = [(n, k) for k, p in enumerate(sequence) if (n := folio_number(labels.get(p))) is not None]
        if number is None or not numbered:
            continue
        after = next((k for n, k in numbered if n > number), None)
        cursor = after if after is not None else numbered[-1][1] + 1
        sequence[cursor:cursor] = [p for p in lists[i] if p not in sequence]
        pending.remove(i)
    return {p: rank for rank, p in enumerate(sequence)}, pending


def _carry_ordinals(stops):
    """Une ligne non reliée mène à la ligne reliée qui la précède dans son
    texte (à défaut, à celle qui la suit)."""
    result, previous = [], {}
    for stop in stops:
        if stop.ordinal is not None:
            previous[stop.segment] = stop.ordinal
            result.append(stop)
        else:
            result.append(replace(stop, ordinal=previous.get(stop.segment), linked=False))
    following = {}
    for index in range(len(result) - 1, -1, -1):
        stop = result[index]
        if stop.linked:
            following[stop.segment] = stop.ordinal
        elif stop.ordinal is None and stop.segment in following:
            result[index] = replace(stop, ordinal=following[stop.segment])
    return result


@dataclass(frozen=True)
class WitnessRoute:
    witness: str
    stops: tuple
    texts: tuple
    uncertain: tuple

    def __post_init__(self):
        object.__setattr__(self, "_index", {(s.segment, s.key): i for i, s in enumerate(self.stops)})

    def index(self, segment, key):
        return self._index.get((segment, key))

    def step(self, segment, key, delta):
        """Arrêt à ``delta`` pas de (segment, key) ; None hors du parcours."""
        index = self.index(segment, key)
        if index is None:
            return None
        target = index + int(delta)
        return self.stops[target] if 0 <= target < len(self.stops) else None

    def first(self, segment):
        return next((s for s in self.stops if s.segment == segment), None)

    def last(self, segment):
        return next((s for s in reversed(self.stops) if s.segment == segment), None)

    def on_page(self, identity):
        """Premier arrêt sur la page ``identity``."""
        return next((s for s in self.stops if s.page == identity), None)


def witness_route(witness, sources, declared=None) -> WitnessRoute:
    """Parcours de ``witness`` dans ses ``sources`` (une par segment, dans
    l'ordre de l'édition) ; ``declared`` : rang des pages par leur identité,
    tiré des images déclarées du témoin."""
    sources = list(sources)
    entries = []
    for source in sources:
        stops = _line_stops(source)
        for mark in source.marks:
            identity = mark.identity or f"folio:{mark.folio}"
            stops.append((identity, -1, Stop(source.segment, mark.folio, identity, mark.ordinal,
                                             mark.ordinal is not None, tuple(mark.location))))
        entries.append(stops)
    lists, labels = _page_lists(sources, entries)
    every_page = {p for pages in lists for p in pages}
    if declared and every_page and every_page <= set(declared):
        ranks, pending = dict(declared), []
    else:
        ranks, pending = _merge(lists, labels, [s.locus for s in sources])
    # Chaque source garde son ordre (celui du panneau) ; les sources sont
    # entrelacées par rang de page, et, sur une page partagée par plusieurs
    # textes, par numéro de ligne.
    shared = {p for p, n in Counter(p for pages in lists for p in pages).items() if n > 1}

    def keyed(stops):
        for identity, number, stop in stops:
            yield (ranks[identity], number if identity in shared else 0), stop

    merged = heapq.merge(*(keyed(stops) for i, stops in enumerate(entries) if i not in pending),
                         key=lambda item: item[0])
    route = [stop for _key, stop in merged]
    # Sources qui n'ont pu être placées : dans l'ordre de l'édition, après le
    # dernier arrêt placé qui les précède dans l'édition.
    anchors = {s.segment: s.anchor for s in sources}
    uncertain = []
    for i in pending:
        source = sources[i]

        def position(stop):
            return stop.ordinal if stop.segment is None else anchors.get(stop.segment, 0)

        before = [k for k, stop in enumerate(route) if position(stop) is not None and position(stop) < source.anchor]
        cursor = max(before, key=lambda k: (position(route[k]), k)) + 1 if before else 0
        route[cursor:cursor] = [stop for _identity, _number, stop in entries[i]]
        uncertain.append(source.segment)
    route = _carry_ordinals(route)
    texts = []
    for stop in route:
        if stop.segment not in texts:
            texts.append(stop.segment)
    return WitnessRoute(str(witness), tuple(route), tuple(texts), tuple(uncertain))
