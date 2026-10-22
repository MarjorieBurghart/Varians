# -*- coding: utf-8 -*-
"""Lacunes des témoins (V0.9.1.3), sans Qt.

En TEI (*parallel segmentation*), le passage qu'un témoin n'a pas est encadré
par ``<lacunaStart/>`` et ``<lacunaEnd/>`` (classe ``att.rdgPart``). Le
témoin est donné de deux façons, toutes deux reconnues :

    <lacunaStart wit="#B"/> … <lacunaEnd wit="#B"/>
    <app><rdg wit="#B"><lacunaStart/></rdg>…</app> … <app><rdg wit="#B"><lacunaEnd/></rdg>…</app>

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

# Leçons et balises de lacune ; le préfixe est libre. Groupes : « / » d'une
# balise fermante, nom local, attributs (avec un éventuel « / » final).
_TAG_RE = re.compile(
    r"<(/?)(?:[A-Za-z_][\w.-]*:)?(rdg|lem|lacunaStart|lacunaEnd)\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", re.S)
_WIT_RE = re.compile(r"(?<![\w:.-])wit\s*=\s*(['\"])(.*?)\1", re.S)
_IGNORED_RE = (
    re.compile(r"<!--.*?(?:-->|$)", re.S),
    re.compile(r"<!\[CDATA\[.*?(?:\]\]>|$)", re.S),
    re.compile(r"<\?.*?(?:\?>|$)", re.S),
)


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
    if "lacuna" not in text:
        return ()
    ignored = [match.span() for rx in _IGNORED_RE for match in rx.finditer(text)]
    readings = []        # leçons ouvertes : (nom, témoins)
    events = []
    for match in _TAG_RE.finditer(text):
        if any(a <= match.start() < b for a, b in ignored):
            continue
        closing, name, attributes = match.group(1), match.group(2), match.group(3)
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
