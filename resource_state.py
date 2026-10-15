# -*- coding: utf-8 -*-
"""État effectif des ressources d'un témoin Varians.

V0.8.4 consolide une distinction devenue essentielle au fil des versions :
la *présence* d'un fichier JSON d'alignement ne suffit pas à activer le mode
ligne. Un JSON peut être vide, provisoire, ou ne contenir encore aucune
correspondance utilisable. Les fonctions de ce module travaillent sur le cache
JSON brut, avant superposition d'un ALTO indépendant, afin qu'un ALTO ne puisse
jamais être confondu avec une synchronisation TEI.
"""
from __future__ import annotations

from dataclasses import dataclass


def primary_sync_line_count(cache: dict | None) -> int:
    """Nombre de lignes de référence réellement présentes dans un alignement.

    Une ligne de base utilisable doit appartenir à une page identifiée et avoir
    un numéro ``line``. Cette règle correspond au contrat des ``base_keys``
    (``page_id::line``) et évite qu'un ALTO ajouté plus tard transforme un JSON
    d'alignement vide en fausse synchronisation.
    """
    total = 0
    for page in (cache or {}).get("pages", []) or []:
        if not page.get("id"):
            continue
        for line in page.get("lines", []) or []:
            if line.get("line") is not None:
                total += 1
    return total


def secondary_sync_link_count(cache: dict | None) -> int:
    """Nombre de lignes secondaires reliées à au moins une ligne de base.

    ``keys816`` reste accepté en lecture pour les projets historiques, mais les
    nouveaux producteurs doivent écrire ``base_keys``.
    """
    total = 0
    for page in (cache or {}).get("pages", []) or []:
        for line in page.get("lines", []) or []:
            keys = line.get("base_keys")
            if keys is None:
                keys = line.get("keys816")
            if keys:
                total += 1
    return total


def effective_base_line_sync(alignment_available: bool, raw_cache: dict | None) -> bool:
    """Le témoin de base possède une synchronisation ligne réellement usable."""
    return bool(alignment_available and primary_sync_line_count(raw_cache) > 0)


def effective_secondary_line_sync(
    alignment_available: bool,
    raw_cache: dict | None,
    *,
    base_line_sync: bool,
) -> bool:
    """Le témoin secondaire possède des liens vers une base elle-même active."""
    return bool(base_line_sync and alignment_available and secondary_sync_link_count(raw_cache) > 0)


@dataclass(frozen=True)
class SynchronizationState:
    """Résumé sans Qt utilisé par les tests et les diagnostics futurs."""

    alignment_available: bool
    primary_lines: int = 0
    secondary_links: int = 0
    effective: bool = False


def synchronization_state(
    raw_cache: dict | None,
    *,
    alignment_available: bool,
    is_base: bool,
    base_line_sync: bool = False,
) -> SynchronizationState:
    primary = primary_sync_line_count(raw_cache) if is_base else 0
    links = 0 if is_base else secondary_sync_link_count(raw_cache)
    effective = (
        effective_base_line_sync(alignment_available, raw_cache)
        if is_base
        else effective_secondary_line_sync(
            alignment_available, raw_cache, base_line_sync=base_line_sync
        )
    )
    return SynchronizationState(
        alignment_available=bool(alignment_available),
        primary_lines=primary,
        secondary_links=links,
        effective=effective,
    )
