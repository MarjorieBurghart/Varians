# -*- coding: utf-8 -*-
"""Recherche dans l'aide de Varians (V0.9.2.8), sans Qt.

L'aide est une longue page découpée en sections (un titre et le texte qui
le suit). La recherche ne tient compte ni des accents ni de la casse, ni
des signes typographiques (« ’ » vaut « ' », « » » vaut « " », une espace
insécable une espace). Plusieurs mots : les sections qui les contiennent
tous, dans n'importe quel ordre ; entre guillemets, l'expression exacte.

Les positions sont celles du texte de l'aide (une par caractère) ; la
fenêtre d'aide les passe à Qt (text_search.Utf16Positions).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Signes typographiques ramenés à leur forme simple, comme les blancs.
_SIGNS = {"’": "'", "‘": "'", "ʼ": "'", "«": '"', "»": '"', "“": '"', "”": '"', "„": '"'}


@dataclass(frozen=True)
class Section:
    title: str
    start: int
    end: int


@dataclass(frozen=True)
class Hit:
    section: Section
    spans: tuple[tuple[int, int], ...]
    excerpt: str


def fold(text: str) -> tuple[str, list[int]]:
    """*text* sans accents, sans casse, sans signes typographiques, et pour
    chaque caractère du résultat sa position dans *text*."""
    folded, origin = [], []
    for index, char in enumerate(text):
        if char in _SIGNS:
            base = _SIGNS[char]
        elif char.isspace():
            base = " "
        else:
            base = "".join(c for c in unicodedata.normalize("NFD", char) if not unicodedata.combining(c)).casefold()
        for part in base:
            folded.append(part)
            origin.append(index)
    return "".join(folded), origin


def query_terms(query: str) -> list[str]:
    """Les termes de *query* : ses mots, et ses expressions entre guillemets."""
    terms = []
    for phrase, word in re.findall(r'"([^"]*)"|(\S+)', fold(query)[0]):
        term = " ".join((phrase or word).split())
        if term and term not in terms:
            terms.append(term)
    return terms


def search(text: str, sections, query: str, context: int = 50) -> list[Hit]:
    """Les sections de *sections* qui contiennent tous les termes de *query*,
    avec les occurrences de ces termes et un extrait d'une ligne."""
    terms = query_terms(query)
    if not terms:
        return []
    folded, origin = fold(text)
    found = {}
    for term in terms:
        spans = []
        for match in re.finditer(re.escape(term), folded):
            spans.append((origin[match.start()], origin[match.end() - 1] + 1))
        found[term] = spans
    hits = []
    for section in sections:
        inside = [[span for span in found[term] if section.start <= span[0] < section.end] for term in terms]
        if all(inside):
            spans = tuple(sorted({span for spans in inside for span in spans}))
            hits.append(Hit(section, spans, _excerpt(text, section, spans[0], context)))
    return hits


def _excerpt(text, section, span, context):
    start = max(section.start, span[0] - context)
    end = min(section.end, span[1] + context)
    # Coupé entre deux mots.
    if start > section.start:
        space = text.find(" ", start, span[0])
        start = space + 1 if space >= 0 else start
    if end < section.end:
        space = text.rfind(" ", span[1], end)
        end = space if space >= 0 else end
    excerpt = " ".join(text[start:end].split())
    return ("…" if start > section.start else "") + excerpt + ("…" if end < section.end else "")
