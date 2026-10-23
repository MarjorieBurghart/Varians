# -*- coding: utf-8 -*-
"""Règles des textes synchronisés à part et du parcours des témoins
(V0.9.1.6), sans Qt : communes à la fenêtre et à l'export web.

Un texte synchronisé à part (``text_alignments``) forme un *segment* de
l'édition assemblée (``pivot_lines``). Ces fonctions disent, pour un texte :
- ses identifiants (``segment_ids``) et les ``<locus>`` qui le visent
  (``segment_loci``, ``locus_start``) ;
- ses témoins par pages, qui y suivent leurs ``<pb>`` sans y avoir de JSON
  (``text_page_witnesses``), et leur page de départ (``start_folio``) ;
et, pour le parcours d'un témoin dans son propre ordre (``witness_route``) :
- le rang des pages tiré des images déclarées (``declared_page_ranks``) ;
- l'arrêt qui correspond à une page (``page_stop``) ou le texte dont le
  ``<locus from>`` est cette page (``locus_segment``) ;
- le premier arrêt dans le texte suivant ou précédent où le témoin est
  présent (``present_stop``).

La fenêtre (``text_segments``, ``witness_sync``) garde ses caches et lit les
textes de ses documents ; l'export web lit les fichiers. Les règles, elles,
sont les mêmes.
"""
from __future__ import annotations

import re

from folio_navigation import text_start_folio, witness_loci
from witness_route import page_identity

_XML_ID_RE = re.compile(r"(?<![\w:.-])xml:id\s*=\s*(['\"])(.*?)\1", re.S)
_SURFACE_NUMBER_RE = re.compile(r"-p(\d+)$")


def segment_ids(texts) -> set:
    """``xml:id`` des textes d'un segment : le texte à part et les parties
    qu'il inclut."""
    return {match.group(2) for text in texts for match in _XML_ID_RE.finditer(text or "")}


def segment_loci(edition_loci, own_text=None) -> dict:
    """``{témoin: (Locus, …)}`` qui valent pour un texte : ceux du
    ``<listWit>`` de l'édition (``edition_loci``, de ``witness_loci``), et
    ceux de l'en-tête du texte lui-même (``own_text`` : un document TEI
    complet inclus par ``xpointer``)."""
    loci = {wid: tuple(found) for wid, found in (edition_loci or {}).items()}
    if own_text is not None:
        for wid, found in witness_loci(own_text).items():
            loci[wid] = loci.get(wid, ()) + tuple(found)
    return loci


def locus_start(loci, witness_id, ids):
    """``@from`` du ``<locus>`` du témoin qui vise l'un des ``ids``, ou
    None."""
    return next((locus.start for locus in loci.get(witness_id, ())
                 if locus.start and locus.targets & set(ids)), None)


def text_page_witnesses(lines, segment, ids, loci, declared) -> set:
    """Témoins qui ont le texte ``segment`` sans y avoir de JSON : un ``<pb
    edRef>`` dans le texte, ou un ``<locus target>`` vers l'un de ses
    éléments ; parmi les témoins ``declared``."""
    found = set(lines.page_witnesses(segment)) if lines is not None else set()
    ids = set(ids)
    for wid, found_loci in loci.items():
        if any(locus.targets & ids for locus in found_loci):
            found.add(wid)
    return {wid for wid in found if wid in set(declared)}


def start_folio(lines, segment, witness_id, folios, loci, ids):
    """Page de départ du témoin dans le texte ``segment``, avant son premier
    ``<pb>`` dans ce texte : son ``<locus from>``, sinon la page qui précède
    celle de ce premier ``<pb>`` (``text_start_folio``)."""
    first = lines.first_page(segment, witness_id, folios) if lines is not None else None
    return text_start_folio(witness_id, folios, loci.get(witness_id, ()), ids, first)


def declared_page_ranks(caches, folios) -> dict:
    """Rang des pages d'un témoin tiré de ses images déclarées : le numéro de
    ``tei_surface_id`` (``…-p0003``), pour les pages de ses JSON
    (``caches``) et pour ses folios."""
    ranks, surfaces = {}, {}
    for cache in caches:
        for page in (cache or {}).get("pages", []) or []:
            sid = str(page.get("tei_surface_id") or "")
            match = _SURFACE_NUMBER_RE.search(sid)
            if match:
                ranks[page_identity(page)] = surfaces[sid] = int(match.group(1))
    for folio in folios:
        if folio.surface in surfaces:
            ranks[f"folio:{folio.ref}"] = surfaces[folio.surface]
    return ranks


def page_stop(route, identity, folio, folios):
    """Arrêt du parcours ``route`` sur la page affichée : celui de la page
    ``identity`` (une ligne d'un JSON du témoin), sinon celui du folio, ou
    un ``<pb>`` de la même image ; None s'il n'y en a pas."""
    stop = route.on_page(identity) if identity is not None else None
    if stop is None or (stop.location is None and stop.ordinal is None):
        surface = {f.ref for f in folios if f.surface == folio.surface}
        stop = route.on_page(f"folio:{folio.ref}") or next(
            (s for s in route.stops if s.location is not None and s.key in surface), None)
    return stop


def locus_segment(witness_id, folio, texts):
    """Texte dont le ``<locus from>`` du témoin est ``folio`` : parmi
    ``texts``, des ``(segment, loci, ids)`` ; None s'il n'y en a pas."""
    label = folio.label.strip().casefold()
    for segment, loci, ids in texts:
        if any(locus.start and locus.start.strip().casefold() == label and locus.targets & set(ids)
               for locus in loci.get(witness_id, ())):
            return segment
    return None


def present_stop(route, anchor_of, order, here_segment, here_ordinal, step):
    """Premier arrêt du témoin dans le texte suivant (``step`` > 0), ou
    dernier dans le texte précédent, où il est présent, dans l'ordre de
    l'édition ; None s'il n'y en a pas.

    ``anchor_of(segment)`` : le nombre de lignes de l'édition avant le texte ;
    ``order`` : les textes à part dans l'ordre de l'édition ; la place
    actuelle est ``here_segment`` (None : l'édition, à la ligne
    ``here_ordinal``)."""
    after = len(order) + 1

    def place(segment, ordinal=None):
        if segment is None:
            return (ordinal if ordinal is not None else -1, after)
        return (anchor_of(segment), order.index(segment) if segment in order else after)

    here = place(here_segment, here_ordinal or 0)
    found = None
    for stop in route.stops:
        key = place(stop.segment, stop.ordinal)
        if (key > here if step > 0 else key < here) and (
                found is None or (key < found[0] if step > 0 else key >= found[0])):
            found = (key, stop)
    if found is None:
        return None
    stop = found[1]
    if stop.segment is not None:
        stop = route.first(stop.segment) if step > 0 else route.last(stop.segment)
    return stop
