# -*- coding: utf-8 -*-
"""Sources de l'aperçu d'une édition assemblée (V0.9.1.5), sans Qt.

La Vue XSLT / CSS d'une édition en parties (XInclude) rend le document
assemblé. Pour y éditer un élément (✎), y cliquer une ligne ou y reporter
une sélection, chaque élément compté par l'aperçu est rattaché à son fichier
et à sa place dans ce fichier :

- ``paragraphs`` : chaque élément modifiable (``fragment_units``, V0.9.2.9 ;
  auparavant chaque ``<p>``) du ``<body>`` assemblé, dans l'ordre du
  document ; le texte de l'aperçu porte son rang (``vx:edit``), celui de
  son crayon ✎ ;
- ``lines`` : chaque ``<lb edRef="#pivot"/>`` du ``<body>`` assemblé (l'ordre
  des repères de ligne de l'aperçu).

Le fichier d'un élément vient de l'assemblage (``Assembly.origin``) ; sa
balise est retrouvée dans le texte du fichier par sa ligne et son rang dans la
ligne (``pivot_lines._match_by_line``), comme les ``<lb/>`` du pivot. Les
textes sont ceux de l'assemblage : celui des parties ouvertes et modifiées,
sinon le fichier. Les balises des commentaires, CDATA et instructions de
traitement ne comptent pas.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from document_session import LbIndex
from fragment_units import TEI_UNIT_NAMES, mark_unit_elements, unit_elements
from pivot_lines import _match_by_line, pivot_lb_pattern
from xml_assembly import assemble, path_key

TEI = "{http://www.tei-c.org/ns/1.0}"
_TAG_RE = re.compile(r"<(/?)(?:[A-Za-z_][\w.-]*:)?([A-Za-z_][\w.-]*)(?:[^>\"']|\"[^\"]*\"|'[^']*')*?(/?)>", re.S)
_IGNORED_RE = (
    re.compile(r"<!--.*?(?:-->|$)", re.S),
    re.compile(r"<!\[CDATA\[.*?(?:\]\]>|$)", re.S),
    re.compile(r"<\?.*?(?:\?>|$)", re.S),
)


@dataclass(frozen=True)
class SourceSpan:
    """Un élément modifiable dans son fichier : ``text[start:end]``."""
    path: Path
    start: int
    end: int


class PreviewSources:
    """Résultat de ``preview_sources`` : le texte assemblé de l'aperçu, et la
    source de chacun de ses paragraphes et repères de ligne (None si elle n'a
    pu être retrouvée)."""

    def __init__(self, text, paragraphs, lines, texts):
        self.text = text
        self.paragraphs = tuple(paragraphs)
        self.lines = tuple(lines)
        # Textes des fichiers, tels que l'assemblage les a lus.
        self.texts = dict(texts)

    def paragraph_at(self, path, position):
        """Rang de l'élément modifiable de l'aperçu qui contient ``position``
        dans le fichier ``path`` (le plus intérieur), ou None."""
        key = path_key(path)
        found = None
        for index, span in enumerate(self.paragraphs):
            if span is not None and path_key(span.path) == key and span.start <= position <= span.end:
                if found is None or span.start >= self.paragraphs[found].start:
                    found = index
        return found

    def line_before(self, path, position):
        """Rang du repère de ligne qui précède ``position`` dans le fichier
        ``path`` ; au début d'un fichier, celui qui précède son premier repère
        dans l'aperçu. None si le fichier n'a pas de repère."""
        key = path_key(path)
        mine = [(index, end) for index, line in enumerate(self.lines)
                if line is not None and path_key(line[0]) == key for end in (line[1],)]
        before = [index for index, end in mine if end <= position]
        if before:
            return max(before)
        if mine:
            return max(0, min(index for index, _end in mine) - 1)
        return None


def _ignored(text):
    return [match.span() for rx in _IGNORED_RE for match in rx.finditer(text)]


def _outside(spans, ignored):
    return [span for span in spans if not any(a <= span[0] < b for a, b in ignored)]


def _element_spans(text, names):
    """``(début, fin de la balise ouvrante, fin de l'élément)`` de chaque
    élément de ``text`` dont le nom est dans ``names``, à tout niveau, dans
    l'ordre des balises ouvrantes."""
    ignored = _ignored(text)
    found, stacks = [], defaultdict(list)
    for match in _TAG_RE.finditer(text):
        closing, name, empty = match.group(1), match.group(2), match.group(3)
        if name not in names or any(a <= match.start() < b for a, b in ignored):
            continue
        if closing:
            if stacks[name]:
                index = stacks[name].pop()
                found[index] = (found[index][0], found[index][1], match.end())
        elif empty:
            found.append((match.start(), match.end(), match.end()))
        else:
            stacks[name].append(len(found))
            found.append((match.start(), match.end(), None))
    return [span for span in found if span[2] is not None]


def _copy_root(assembly, element):
    """Copie (partie incluse) à laquelle appartient ``element`` ; None pour
    l'édition elle-même."""
    node = element
    while node is not None:
        if node in assembly._origins:
            return node
        node = node.getparent()
    return None


def _in_body(elements):
    elements = list(elements)
    inside = [e for e in elements if any(a.tag == f"{TEI}body" for a in e.iterancestors())]
    return inside if inside or not elements else elements


def _locate(assembly, elements, texts, positions_of):
    """Pour chaque élément, ``(fichier, valeur)`` : la valeur que
    ``positions_of(texte)`` donne à sa balise dans son fichier, ou None."""
    groups = defaultdict(list)       # (fichier, copie) -> [(ligne, rang de l'élément)]
    for index, element in enumerate(elements):
        path = assembly.origin(element)
        groups[(path_key(path), id(_copy_root(assembly, element)))].append((element.sourceline, index))
    paths = {path_key(assembly.origin(e)): assembly.origin(e) for e in elements}
    result = [None] * len(elements)
    for (key, _copy), events in groups.items():
        text = texts.get(key)
        if text is None:
            continue
        positions, values = positions_of(text)
        for value, index in zip(values, _match_by_line(text, positions, events)):
            if index is not None:
                result[index] = (paths[key], value)
    return result


def _file_texts(assembly, master_text, texts):
    """Textes des fichiers de l'assemblage, par clé de chemin."""
    found = {path_key(assembly.master): str(master_text or "")}
    given = {path_key(path): text for path, text in (texts or {}).items()}
    for path in assembly.parts:
        key = path_key(path)
        if key in given:
            found[key] = given[key]
        else:
            try:
                found[key] = Path(path).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                pass
    return found


def preview_sources(edition_text, edition_path, texts=None, base_id="", pattern=None, names=TEI_UNIT_NAMES):
    """Sources de l'aperçu de l'édition ``edition_text`` (fichier
    ``edition_path``), avec ``texts`` (``{chemin: texte}`` des parties
    ouvertes) ; ``base_id`` : le pivot du projet, dont les ``<lb/>`` font les
    repères de ligne ; ``names`` : les noms des éléments modifiables. None si
    l'édition est mal formée."""
    assembly = assemble(edition_text, edition_path, texts)
    if assembly.root is None:
        return None
    files = _file_texts(assembly, edition_text, texts)
    units = unit_elements(assembly.root, names)
    # Tous les éléments de ces noms sont retrouvés dans leur fichier, pour que
    # le rang de chacun dans sa ligne y soit le même que dans l'assemblage.
    named = [e for e in assembly.root.iter() if isinstance(e.tag, str) and etree.QName(e).localname in names]

    def unit_positions(text):
        spans = _element_spans(text, names)
        return [tag_end - 1 for _start, tag_end, _end in spans], [(start, end) for start, _tag_end, end in spans]

    located = dict(zip(map(id, named), _locate(assembly, named, files, unit_positions)))
    spans = [SourceSpan(item[0], *item[1]) if item else None for item in (located.get(id(e)) for e in units)]
    edref = f"#{base_id}"
    lbs = _in_body(e for e in assembly.root.iter(f"{TEI}lb") if e.get("edRef") == edref)
    regex = pattern or pivot_lb_pattern(base_id)

    def lb_positions(text):
        found = _outside(LbIndex.scan(text, regex), _ignored(text))
        return [end - 1 for _start, end in found], [end for _start, end in found]

    lines = _locate(assembly, lbs, files, lb_positions)
    texts_by_path = {path: files[path_key(path)] for path in [assembly.master, *assembly.parts]
                     if path_key(path) in files}
    # Le rang de chaque élément modifiable, pour la feuille enveloppe des
    # crayons (fragment_units.edit_stylesheet).
    mark_unit_elements(units)
    return PreviewSources(etree.tostring(assembly.root, encoding="unicode"), spans, lines, texts_by_path)
