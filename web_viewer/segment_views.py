# -*- coding: utf-8 -*-
"""Textes, parcours et positions de l'export web d'une édition assemblée
(V0.9.1.6), sans Qt.

``doc_positions`` : la position de chaque segment du texte de lecture,
comptée comme le viewer (``renderDocument``) et sa recherche plein texte
(``VariansFullText.makeIndex``) : chaque segment d'un bloc ``p``, dans
l'ordre, les autres blocs n'étant pas rendus.
"""
from __future__ import annotations


def doc_positions(reading) -> dict:
    """``{id(segment): position}`` des segments des blocs ``p``."""
    positions = {}
    for block in reading.get("blocks", []) or []:
        if block.get("type") != "p":
            continue
        for segment in block.get("segments", []) or []:
            positions[id(segment)] = len(positions)
    return positions
