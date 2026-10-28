# -*- coding: utf-8 -*-
"""Recherche et remplacement dans le XML et le fragment (V0.9.2.8), sans Qt.

La recherche est littérale ou par expression régulière (``re`` de Python),
casse respectée ou non :

- littérale, elle garde les occurrences qui se chevauchent (« aa » deux
  fois dans « aaa »), comme avant la 0.9.2.8 ;
- par expression régulière, ``^`` et ``$`` valent pour chaque ligne et une
  correspondance vide n'est pas une occurrence.

Les remplacements ne se chevauchent pas. Un texte de remplacement est mis
tel quel en recherche littérale ; avec une expression régulière, il peut
reprendre ses groupes (``\\1``, ``\\g<nom>``) et écrire ``\\n``.

Les positions sont celles de Python (une par caractère). Qt compte en
UTF-16 : un caractère au-delà de U+FFFF y occupe deux positions
(``Utf16Positions`` passe des unes aux autres).
"""
from __future__ import annotations

import re
from bisect import bisect_left, bisect_right
from dataclasses import dataclass

# Les caractères au-delà de U+FFFF : deux positions dans Qt.
_ASTRAL = re.compile("[\U00010000-\U0010FFFF]")


@dataclass(frozen=True)
class SearchOptions:
    case_sensitive: bool = False
    regex: bool = False


class SearchError(ValueError):
    """Expression (``pattern_invalid``) ou texte de remplacement
    (``template_invalid``) incorrect ; *detail* est le message de ``re``."""

    def __init__(self, code: str, detail: str):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail


def compile_search(query: str, options: SearchOptions) -> re.Pattern:
    flags = 0 if options.case_sensitive else re.IGNORECASE
    if not options.regex:
        return re.compile(re.escape(query), flags)
    try:
        return re.compile(query, flags | re.MULTILINE)
    except re.error as exc:
        raise SearchError("pattern_invalid", str(exc)) from exc


def find_spans(text: str, query: str, options: SearchOptions = SearchOptions()) -> list[tuple[int, int]]:
    """Les occurrences ``(début, fin)`` de *query* dans *text*."""
    if not query:
        return []
    pattern = compile_search(query, options)
    if options.regex:
        return [match.span() for match in pattern.finditer(text) if match.end() > match.start()]
    spans = []
    match = pattern.search(text)
    while match is not None:
        spans.append(match.span())
        match = pattern.search(text, match.start() + 1)
    return spans


def match_at(text: str, start: int, end: int, query: str, options: SearchOptions):
    """La correspondance de *query* qui occupe exactement ``text[start:end]``,
    ou None (l'occurrence surlignée a changé, ou n'est plus à sa place)."""
    if not query or not 0 <= start < end <= len(text):
        return None
    # Dans tout le texte : ^, $ et \b voient ce qui entoure l'occurrence.
    match = compile_search(query, options).match(text, start)
    return match if match is not None and match.end() == end else None


def replacement_for(match: re.Match, template: str, options: SearchOptions) -> str:
    if not options.regex:
        return template
    try:
        return match.expand(template)
    except (re.error, IndexError) as exc:
        raise SearchError("template_invalid", str(exc)) from exc


def replacements(text: str, query: str, template: str,
                 options: SearchOptions = SearchOptions()) -> list[tuple[int, int, str]]:
    """Les remplacements ``(début, fin, texte)``, sans chevauchement, dans
    l'ordre du texte."""
    if not query:
        return []
    pattern = compile_search(query, options)
    return [(match.start(), match.end(), replacement_for(match, template, options))
            for match in pattern.finditer(text) if match.end() > match.start()]


_BLANKS = re.compile(r"\s+")


@dataclass(frozen=True)
class Kwic:
    """Une occurrence ``text[start:end]`` en contexte (keyword in context) :
    sa ligne (à partir de 1) et, sur une seule ligne, le texte avant, le
    résultat et le texte après."""
    start: int
    end: int
    line: int
    before: str
    match: str
    after: str


def kwic(text: str, spans, width: int = 40) -> list[Kwic]:
    """Les occurrences *spans* de *text* en contexte : au plus *width*
    caractères avant et après ; les blancs, sauts de ligne compris,
    deviennent une espace."""
    newlines = [match.start() for match in re.finditer("\n", text)]
    rows = []
    for start, end in spans:
        before = _BLANKS.sub(" ", text[max(0, start - 4 * width):start])[-width:] if width else ""
        after = _BLANKS.sub(" ", text[end:end + 4 * width])[:width]
        rows.append(Kwic(start, end, bisect_left(newlines, start) + 1, before,
                         _BLANKS.sub(" ", text[start:end]), after))
    return rows


class Utf16Positions:
    """Positions Python ↔ positions Qt (UTF-16) dans *text*."""

    def __init__(self, text: str):
        self._astral = [match.start() for match in _ASTRAL.finditer(text)]
        # Position Qt qui suit chaque caractère au-delà de U+FFFF.
        self._after = [index + rank + 2 for rank, index in enumerate(self._astral)]

    def qt(self, index: int) -> int:
        return index + bisect_left(self._astral, index)

    def python(self, position: int) -> int:
        return position - bisect_right(self._after, position)
