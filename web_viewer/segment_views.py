# -*- coding: utf-8 -*-
"""Textes, parcours et positions de l'export web d'une édition assemblée
(V0.9.1.6), sans Qt.

``doc_positions`` : la position de chaque segment du texte de lecture,
comptée comme le viewer (``renderDocument``) et sa recherche plein texte
(``VariansFullText.makeIndex``) : chaque segment d'un bloc rendu
(``RENDERED_BLOCKS`` : paragraphes, titres, vers, entrées de liste,
cellules, légendes, notes ; V0.9.3.0), dans l'ordre ; un bloc ``div`` n'a
pas de segment.

Parcours d'un témoin (``witness_route``, mêmes règles que le bureau) : ses
``<pb>`` dans chaque texte, situés dans le texte de lecture (``page_marks``) ;
ses arrêts pour le viewer (``export_route``) ; les pages qui mènent le texte,
par leur ``<pb>`` ou leur première ligne (``page_leads``) ou par le ``<locus
from>`` d'un texte à part (``locus_leads``). Le texte suivant ou précédent qui
a le témoin se déduit du parcours et de la place des textes
(``segment_model.present_stop``) : le viewer le calcule lui-même, car il
dépend de la ligne affichée.
"""
from __future__ import annotations

from web_viewer.legacy_v11_core import RENDERED_BLOCKS


def doc_positions(reading) -> dict:
    """``{id(segment): position}`` des segments des blocs rendus."""
    positions = {}
    for block in reading.get("blocks", []) or []:
        if block.get("type") not in RENDERED_BLOCKS:
            continue
        for segment in block.get("segments", []) or []:
            positions[id(segment)] = len(positions)
    return positions


def page_marks(reading, witness_id, folios_by_segment, ranks_by_segment) -> dict:
    """``{texte: [PageMark, …]}`` : les ``<pb>`` du témoin dans chaque texte
    (``folios_by_segment``, ses folios dans ce texte), comme
    ``pivot_lines.pb_marks`` sur le bureau. Leur place est leur position
    dans le texte de lecture (``doc_positions`` ; un ``<pb>`` hors d'un bloc
    rendu prend celle du segment rendu suivant), et
    leur ligne le rang (``ranks_by_segment``) de la ligne du pivot du texte
    ouverte à cet endroit : celle que porte le ``<pb>``
    (``extract_reading_document(pb_line_keys=True)``), sinon la dernière
    ligne qui le précède, 0 avant la première."""
    from folio_navigation import folio_lookup, pb_folio
    from witness_route import PageMark
    lookups = {k: folio_lookup(list(folios)) for k, folios in folios_by_segment.items() if folios}
    marks, last, position = {}, {}, 0
    for block in reading.get("blocks", []) or []:
        counted = block.get("type") in RENDERED_BLOCKS
        for segment in block.get("segments", []) or []:
            k = segment.get("seg", 0)
            if segment.get("kind") == "text" and segment.get("line_key"):
                rank = ranks_by_segment.get(k, {}).get(segment["line_key"])
                if rank is not None:
                    last[k] = rank
            elif segment.get("kind") == "pb":
                rank = ranks_by_segment.get(k, {}).get(segment.get("line_key"))
                if rank is not None:
                    last[k] = rank
                folio = (pb_folio(segment.get("facs"), segment.get("edref"), segment.get("label"),
                                  witness_id, lookups[k]) if k in lookups else None)
                if folio is not None:
                    marks.setdefault(k, []).append(PageMark(folio.ref, folio.label, (position,), last.get(k, 0)))
            if counted:
                position += 1
    return marks


def export_route(route, prefixes, pivot_keys) -> list:
    """Arrêts du parcours pour le viewer : ``s`` (texte : 0 pour l'édition),
    ``k`` (clé de l'élément du panneau dans la vue du texte, ou folio d'un
    ``<pb>``), ``t`` (ligne du pivot du texte), ``u`` (1 : ligne non reliée,
    qui mène à la ligne reliée qui la précède), ``p`` (position du
    ``<pb>``)."""
    out = []
    for stop in route.stops:
        k = 0 if stop.segment is None else stop.segment
        keys = pivot_keys.get(k, ())
        entry = {"s": k}
        if stop.location is not None:
            entry.update(k=stop.key, p=stop.location[0])
        else:
            entry["k"] = prefixes.get(k, "") + stop.key
        entry["t"] = keys[stop.ordinal] if stop.ordinal is not None and 0 <= stop.ordinal < len(keys) else None
        if not stop.linked:
            entry["u"] = 1
        out.append(entry)
    return out


def page_leads(route, pages, folios) -> dict:
    """``{folio: rang de l'arrêt}`` des pages d'un témoin par pages qui
    mènent le texte (``segment_model.page_stop``) : sa première ligne dans
    un JSON du témoin, sinon son ``<pb>``. ``pages`` : les pages du témoin
    (identifiants sans préfixe)."""
    import segment_model
    from witness_route import page_identity
    identities = {str(page["tei_surface_id"]): page_identity(page) for page in pages
                  if page.get("tei_surface_id")}
    leads = {}
    for folio in folios:
        stop = segment_model.page_stop(route, identities.get(str(folio.surface)), folio, folios)
        if stop is not None:
            leads[folio.ref] = route.index(stop.segment, stop.key)
    return leads


def locus_leads(witness_id, folios, texts) -> dict:
    """``{folio: texte}`` : les pages qui sont le ``<locus from>`` du témoin
    pour un texte à part (``segment_model.locus_segment``) ; ``texts`` :
    des ``(texte, loci, identifiants)``."""
    import segment_model
    texts = list(texts)
    leads = {}
    for folio in folios:
        k = segment_model.locus_segment(witness_id, folio, texts)
        if k is not None:
            leads.setdefault(folio.ref, k)
    return leads
