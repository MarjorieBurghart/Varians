# -*- coding: utf-8 -*-
"""Lignes du témoin pivot dans une édition assemblée par XInclude, sans Qt.

Dans une édition en un seul fichier, le n-ième ``<lb edRef="#pivot"/>`` du
texte correspond à la n-ième ligne du JSON du pivot. Une édition qui inclut
ses parties (V0.9.1.0, « numérotation continue ») les compte dans l'ordre du
document assemblé : chaque partie est décalée du nombre de lignes qui la
précèdent. Les JSON restent ceux d'une édition simple, un par témoin ; le
pivot doit contenir les textes dans l'ordre de l'édition.

``pivot_lines`` assemble l'édition (``xml_assembly``) et parcourt le document
assemblé. Chaque ``<lb/>`` du pivot y reçoit son numéro, puis il est rattaché,
dans son fichier, au ``<lb/>`` que trouve l'expression du pivot (même ligne,
même rang dans la ligne). Les positions viennent ensuite de l'index propre à
chaque document (``LbIndex``), tenu à jour pendant la saisie. Comme dans les
autres outils (XSLT, viewer web, ``xmllint --xinclude``), un ``<lb/>`` placé
dans un commentaire ou hors de l'élément inclus d'une partie ne compte pas.

Le même parcours relève les ``<pb>`` : la page d'un témoin tient compte de ce
qui précède dans les autres fichiers (page à la jonction de deux textes).

Textes synchronisés à part (V0.9.1.1, ``text_alignments``) : chacun forme un
*segment*, numéroté pour lui seul avec son propre pivot, inclusions
imbriquées comprises ; le segment de l'édition (clé None) ne compte pas leurs
lignes. Un fichier appartient à un seul segment.
"""
from __future__ import annotations

import bisect
import re
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from document_session import LbIndex
from folio_navigation import folio_lookup, last_folio_mark, pb_folio
from xml_assembly import assemble, path_key

# Balise ouvrante d'un xi:include (le préfixe est libre) ; un élément non vide
# se termine à sa balise fermante.
_INCLUDE_START = re.compile(r"<((?:[A-Za-z_][\w.-]*:)?include)\b(?:[^>\"']|\"[^\"]*\"|'[^']*')*>", re.S)


def pivot_lb_pattern(base_id):
    """Expression des ``<lb edRef="#pivot"/>`` dans un texte XML."""
    escaped = re.escape(base_id)
    return re.compile(
        rf"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bedRef\s*=\s*(['\"])#{escaped}\1)[^>]*?/?>",
        re.IGNORECASE | re.DOTALL,
    )


def _include_tags(text):
    """``(début, fin de l'élément, fin de la balise ouvrante)`` de chaque
    ``xi:include`` de ``text``, dans l'ordre."""
    found = []
    position = 0
    while True:
        match = _INCLUDE_START.search(text, position)
        if match is None:
            return found
        end = match.end()
        if not match.group(0).endswith("/>"):
            closing = re.compile(rf"</{re.escape(match.group(1))}\s*>").search(text, end)
            if closing is not None:
                end = closing.end()
        found.append((match.start(), end, match.end()))
        position = end


def include_spans(text):
    """Début et fin de chaque ``xi:include`` de ``text``, dans l'ordre."""
    return [(start, end) for start, end, _tag_end in _include_tags(str(text or ""))]


def _match_by_line(text, positions, events):
    """Rattache des événements ``(ligne, valeur)`` aux positions (croissantes)
    de ``text`` : même ligne, même rang dans la ligne. Une position sans
    événement reçoit None."""
    by_line = defaultdict(deque)
    for line, value in events:
        by_line[line].append(value)
    values = []
    line, counted = 1, 0
    for position in positions:
        line += text.count("\n", counted, position)
        counted = position
        pending = by_line.get(line)
        values.append(pending.popleft() if pending else None)
    return tuple(values)


@dataclass(frozen=True)
class FileLines:
    """Un fichier de l'édition assemblée : l'édition ou une partie.

    ``ordinals`` : numéro de chacun de ses ``<lb/>`` du pivot, dans l'ordre du
    texte, ou None s'il n'entre pas dans l'édition. ``includes`` : pour chacun
    de ses ``xi:include``, ``(dernier numéro, nombre de <pb>)`` à la fin de
    son contenu, ou None s'il n'a rien inclus. ``entry`` : la même paire avant
    le contenu du fichier (−1 : aucune ligne avant). Les numéros sont ceux du
    ``segment`` du fichier : None pour l'édition, sinon la clé (``path_key``)
    du texte synchronisé à part qui le contient.
    """
    ordinals: tuple
    includes: tuple
    entry: tuple
    segment: str | None = None


class PivotLines:
    """Résultat de ``pivot_lines``."""

    def __init__(self, files, locations, pbs, problems):
        self._files = files
        # {segment: ((fichier, rang), …)} ; voir location().
        self._locations = {segment: tuple(found) for segment, found in locations.items()}
        self._pbs = tuple(pbs)
        self.problems = tuple(problems)

    @property
    def count(self):
        """Nombre de lignes du pivot dans le segment de l'édition."""
        return self.segment_count(None)

    def segment_count(self, segment):
        """Nombre de lignes du pivot du segment ``segment``."""
        return len(self._locations.get(segment, ()))

    def file(self, path):
        return self._files.get(path_key(path))

    def matches(self, path, lb_count, include_count):
        """Le fichier compte encore ``lb_count`` lignes du pivot et
        ``include_count`` inclusions : sa numérotation reste valable."""
        lines = self.file(path)
        return (lines is not None and len(lines.ordinals) == lb_count
                and len(lines.includes) == include_count)

    def ordinal_at(self, path, position, spans, includes=()):
        """Numéro de la ligne du pivot à ``position`` dans ``path``.

        ``spans`` : ses ``<lb/>`` du pivot (``LbIndex``), ``includes`` : ses
        ``xi:include`` (``include_spans``). Un texte placé avant la première
        ligne d'un fichier appartient à la dernière ligne de ce qui le
        précède, comme dans une édition en un seul fichier. None si le
        fichier n'est pas dans l'édition ou si elle n'a aucune ligne.
        """
        lines = self.file(path)
        if lines is None or not self.segment_count(lines.segment):
            return None
        best = lines.entry[0]
        index = bisect.bisect_right([start for start, _end in spans], int(position)) - 1
        for index in range(min(index, len(lines.ordinals) - 1), -1, -1):
            if lines.ordinals[index] is not None:
                best = max(best, lines.ordinals[index])
                break
        for (_start, end), value in zip(includes, lines.includes):
            if end <= position and value is not None:
                best = max(best, value[0])
        return max(0, min(best, self.segment_count(lines.segment) - 1))

    def location(self, ordinal, segment=None):
        """``(fichier, rang du <lb/> dans ce fichier)`` de la ligne
        ``ordinal`` du segment ; None hors des limites."""
        found = self._locations.get(segment, ())
        if not 0 <= ordinal < len(found):
            return None
        return found[ordinal]

    def page_at(self, path, position, text, includes, witness_id, folios):
        """Folio du témoin ``witness_id`` à ``position`` dans ``path`` (texte
        ``text``) : le dernier ``<pb>`` qui le concerne avant cette position,
        dans l'ordre du document assemblé."""
        lines = self.file(path)
        if lines is None:
            return None
        count, after = lines.entry[1], -1
        for (_start, end), value in zip(includes, lines.includes):
            if end <= position and value is not None:
                count, after = value[1], end
        local = last_folio_mark(text, position, witness_id, folios)
        if local is not None and local[1] > after:
            return local[0]
        lookup = folio_lookup(folios)
        for facs, ed_ref, n in reversed(self._pbs[:count]):
            folio = pb_folio(facs, ed_ref, n, witness_id, lookup)
            if folio is not None:
                return folio
        return None


def _read(path):
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return ""


def pivot_lines(edition_text, edition_path, texts=None, base_id="", pattern=None, text_bases=None):
    """Lignes du pivot ``base_id`` dans l'édition assemblée.

    ``texts`` : ``{chemin: texte}`` des parties ouvertes, prioritaire sur les
    fichiers. ``text_bases`` : ``{fichier d'un texte synchronisé à part: son
    pivot}`` ; chacun de ces textes forme son propre segment. None si
    l'édition est mal formée. Une partie mal formée n'apporte aucune ligne
    (``problems``).
    """
    texts = dict(texts or {})
    assembly = assemble(edition_text, edition_path, texts)
    if assembly.root is None:
        return None
    apart = {path_key(path): base for path, base in (text_bases or {}).items()}
    bases = {None: base_id}
    patterns = {base_id: pattern or pivot_lb_pattern(base_id)}
    master = path_key(assembly.master)
    paths = {master: assembly.master}
    entries = {master: (-1, 0)}
    segments = {master: None}        # fichier -> segment
    counts = defaultdict(lambda: -1)  # segment -> dernier numéro
    lbs = defaultdict(list)          # fichier -> [(ligne, numéro)]
    ends = defaultdict(list)         # fichier -> [(ligne du xi:include, (numéro, pb))]
    pbs = []
    # Fichier courant et son segment ; le contenu d'un fichier inclus une
    # seconde fois est compté, mais rattaché à sa première inclusion seulement.
    stack = [(master, True, None)]
    for event, element in etree.iterwalk(assembly.root, events=("start", "end")):
        if not isinstance(element.tag, str):
            continue
        site = assembly.site(element)
        if event == "end":
            if site is not None:
                stack.pop()
                key, first, segment = stack[-1]
                if first:
                    ends[key].append((site, (counts[segment], len(pbs))))
            continue
        if site is not None:
            path = assembly.origin(element)
            key = path_key(path)
            segment = key if key in apart else stack[-1][2]
            if key in apart:
                bases.setdefault(segment, apart[key])
            first = key not in entries
            if first:
                paths[key] = path
                segments[key] = segment
                entries[key] = (counts[segment], len(pbs))
            stack.append((key, first, segment))
        name = etree.QName(element).localname
        key, first, segment = stack[-1]
        if name == "lb" and element.get("edRef") == f"#{bases[segment]}":
            counts[segment] += 1
            if first:
                lbs[key].append((element.sourceline, counts[segment]))
        elif name == "pb":
            pbs.append((element.get("facs"), element.get("edRef"), element.get("n")))
    by_key = {path_key(path): text for path, text in texts.items()}
    by_key[master] = str(edition_text or "")
    files = {}
    locations = {segment: [None] * (counts[segment] + 1) for segment in bases}
    for key, path in paths.items():
        segment = segments[key]
        base = bases[segment]
        if base not in patterns:
            patterns[base] = pivot_lb_pattern(base)
        text = by_key[key] if key in by_key else _read(path)
        spans = LbIndex.scan(text, patterns[base])
        ordinals = _match_by_line(text, [end - 1 for _start, end in spans], lbs[key])
        for index, ordinal in enumerate(ordinals):
            if ordinal is not None:
                locations[segment][ordinal] = (path, index)
        tags = _include_tags(text)
        includes = _match_by_line(text, [tag_end - 1 for _s, _e, tag_end in tags], ends[key])
        files[key] = FileLines(ordinals, includes, entries[key], segment)
    return PivotLines(files, locations, pbs, assembly.problems)
