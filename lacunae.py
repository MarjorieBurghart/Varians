# -*- coding: utf-8 -*-
"""Lacunes des témoins (V0.9.1.3), sans Qt.

En TEI (*parallel segmentation*), le passage qu'un témoin n'a pas est encadré
par ``<lacunaStart/>`` et ``<lacunaEnd/>`` (``model.rdgPart``), que la TEI
n'admet que dans ``<rdg>`` et ``<lem>``. Le témoin est celui de la leçon qui
contient la balise, ou, dans une leçon de plusieurs témoins, celui du ``@wit``
de la balise (``att.rdgPart``) :

    <app><lem wit="#A"/><rdg wit="#B"><lacunaStart/></rdg></app> … <app><lem wit="#A"/><rdg wit="#B"><lacunaEnd/></rdg></app>
    <rdg wit="#B #C">… <lacunaStart wit="#C"/></rdg>

La balise isolée avec ``@wit`` (``<lacunaStart wit="#B"/>`` hors d'une leçon)
est reconnue aussi, bien que la validation TEI la signale.

``lacuna_events`` relève les débuts et fins d'un texte, ``lacunae_at`` donne
les témoins en lacune à une position. Une lacune sans fin court jusqu'à la fin
du texte ; une fin sans début est ignorée ; une balise sans témoin (ni
``@wit``, ni leçon englobante qui en ait un) ne compte pas. Les balises des
commentaires, CDATA et instructions de traitement sont ignorées.

Dans une édition en parties, ``pivot_lines`` relève les mêmes événements dans
le document assemblé (``PivotLines.lacunae_at``).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from xml_tag_pairs import element_tag_pattern, element_tags

# Leçons et balises de lacune ; le préfixe est libre. Groupes : « / » d'une
# balise fermante, nom local, attributs (avec un éventuel « / » final).
# Hors commentaires, CDATA, instructions et DOCTYPE, lus dans l'ordre (red
# team 2, B6).
_TAGS = element_tag_pattern("rdg", "lem", "lacunaStart", "lacunaEnd")
_WIT_RE = re.compile(r"(?<![\w:.-])wit\s*=\s*(['\"])(.*?)\1", re.S)


@dataclass(frozen=True)
class LacunaEvent:
    """Début (``start``) ou fin d'une lacune des ``witnesses``, à
    ``position`` : la fin de la balise."""
    position: int
    start: bool
    witnesses: frozenset


@dataclass(frozen=True)
class Lacuna:
    """Lacune en cours d'un témoin. Son début est soit à ``position`` dans le
    texte considéré, soit dans un autre fichier de l'édition assemblée :
    ``ordinal`` est alors la ligne du pivot où elle commence."""
    witness: str
    position: int | None = None
    ordinal: int | None = None


def witness_tokens(value):
    """Identifiants des témoins d'une valeur ``@wit`` (``"#A #B"``)."""
    return frozenset(token[1:] for token in str(value or "").split() if token.startswith("#") and len(token) > 1)


def lacuna_events(text):
    """Débuts et fins de lacune de ``text``, dans l'ordre."""
    text = str(text or "")
    if "lacunaStart" not in text and "lacunaEnd" not in text:
        return ()
    readings = []        # leçons ouvertes : (nom, témoins)
    events = []
    for match in element_tags(_TAGS, text):
        closing, name, attributes = match.group("close"), match.group("name"), match.group("attrs")
        if name in ("rdg", "lem"):
            if closing:
                while readings and readings.pop()[0] != name:
                    pass
            elif not attributes.rstrip().endswith("/"):
                wit = _WIT_RE.search(attributes)
                readings.append((name, witness_tokens(wit.group(2) if wit else "")))
            continue
        if closing:
            continue                      # </lacunaStart> d'un élément non vide
        wit = _WIT_RE.search(attributes)
        witnesses = witness_tokens(wit.group(2)) if wit else (readings[-1][1] if readings else frozenset())
        if witnesses:
            events.append(LacunaEvent(match.end(), name == "lacunaStart", witnesses))
    return tuple(events)


def apply_events(state, events, position=None, start=None):
    """Applique à ``state`` (``{témoin: Lacuna}``) les ``events`` antérieurs à
    ``position`` (tous si None) et postérieurs à ``start``."""
    for event in events:
        if start is not None and event.position <= start:
            continue
        if position is not None and event.position > position:
            break
        for witness in event.witnesses:
            if event.start:
                state.setdefault(witness, Lacuna(witness, position=event.position))
            else:
                state.pop(witness, None)
    return state


def lacunae_at(text, position, events=None):
    """``{témoin: Lacuna}`` des témoins en lacune à ``position`` dans
    ``text`` (``events`` : ``lacuna_events(text)``, s'il est déjà connu)."""
    return apply_events({}, lacuna_events(text) if events is None else events, int(position))
