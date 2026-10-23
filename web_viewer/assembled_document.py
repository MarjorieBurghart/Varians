# -*- coding: utf-8 -*-
"""Édition assemblée lue par l'export web (V0.9.1.6).

Une édition qui inclut ses parties par XInclude est assemblée comme sur le
bureau (``xml_assembly.assemble``, fichiers enregistrés). Chaque élément du
document assemblé est rattaché à son *texte* : l'édition (0), ou un texte
synchronisé à part (``text_alignments``), numéroté 1, 2… dans l'ordre de
l'édition, avec son pivot et le préfixe de ses clés de ligne (``~1~``…).

Les extracteurs de l'export (``legacy_v11_core``) travaillent sur
``xml.etree`` : l'arbre assemblé (lxml) est donc sérialisé, puis relu. Les
commentaires et instructions de traitement disparaissent alors, comme quand
``xml.etree`` lit un fichier unique ; le DOCTYPE et ses entités internes
restent. Le texte de chaque copie de partie est marqué par un attribut
technique (``VX_SEG``), relevé puis retiré : il n'atteint jamais l'export.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

VX_SEG = "{urn:x-varians:export}seg"


@dataclass(frozen=True)
class ExportSegment:
    """Un texte de l'édition : 0 pour l'édition, k ≥ 1 pour un texte
    synchronisé à part. ``key`` : sa clé de chemin (None pour l'édition) ;
    ``anchor`` : le nombre de lignes de l'édition avant lui ; ``sync`` : le
    ``TextSync`` du texte à part."""
    index: int
    key: str | None
    name: str | None
    path: Path
    pivot: str
    prefix: str
    anchor: int = 0
    sync: object = None


@dataclass
class AssembledDocument:
    """Résultat de ``load_assembled``. ``lines`` : la numérotation du bureau
    (``pivot_lines``), ``problems`` : ceux de l'assemblage, ``sync_problems``
    : ceux des textes à part (``text_syncs``)."""
    root: ET.Element
    segments: list
    lines: object
    problems: tuple = ()
    sync_problems: tuple = ()
    parts: tuple = ()
    _segment_of: dict = field(default_factory=dict)

    def segment(self, node) -> int:
        """Texte de l'élément ``node`` de ``root``."""
        return self._segment_of.get(id(node), 0)

    def target(self, node) -> str:
        """Pivot (``#id``) du texte de ``node``."""
        return "#" + self.segments[self.segment(node)].pivot

    def segment_files(self, index):
        """Fichiers du texte ``index`` : le texte à part et les parties qu'il
        inclut (l'édition et ses parties pour 0)."""
        key = self.segments[index].key
        found = []
        for path in [self.segments[0].path, *self.parts]:
            lines = self.lines.file(path) if self.lines is not None else None
            if lines is not None and lines.segment == key:
                found.append(Path(path))
        return found


def _has_includes(text):
    from pivot_lines import include_spans
    return bool(include_spans(text))


def load_assembled(project):
    """Édition assemblée du projet, ou None si l'édition n'inclut pas de
    partie (elle est alors lue comme avant). ``ValueError`` si l'édition est
    mal formée."""
    edition = Path(project.edition)
    text = edition.read_text(encoding="utf-8-sig")
    if not _has_includes(text):
        return None
    from lxml import etree

    from pivot_lines import pivot_lines
    from text_alignments import text_syncs
    from xml_assembly import assemble, path_key

    assembly = assemble(text, edition)
    if assembly.root is None:
        raise ValueError(f"Édition mal formée : {edition}")
    syncs, sync_problems = text_syncs(project, assembly.parts)
    lines = pivot_lines(text, edition, {}, project.base_witness,
                        text_bases={sync.path: sync.base for sync in syncs})
    segments = [ExportSegment(0, None, None, edition, project.base_witness, "")]
    apart = {}
    for index, sync in enumerate(syncs, 1):
        key = path_key(sync.path)
        apart[key] = index
        anchor = lines.anchor(key) if lines is not None else 0
        segments.append(ExportSegment(index, key, sync.name, Path(sync.path), sync.base, f"~{index}~",
                                      anchor, sync))
    # Même règle que pivot_lines : une partie qui est un texte à part ouvre
    # son texte ; les parties qu'elle inclut en font partie.
    stack = [0]
    for event, element in etree.iterwalk(assembly.root, events=("start", "end")):
        if not isinstance(element.tag, str) or assembly.site(element) is None:
            continue
        if event == "end":
            stack.pop()
            continue
        key = path_key(assembly.origin(element))
        stack.append(apart.get(key, stack[-1]))
        if stack[-1]:
            element.set(VX_SEG, str(stack[-1]))
    data = etree.tostring(assembly.root.getroottree(), encoding="utf-8", xml_declaration=True)
    root = ET.fromstring(data)
    segment_of = {}

    def mark(node, index):
        value = node.attrib.pop(VX_SEG, None)
        if value is not None:
            index = int(value)
        if index:
            segment_of[id(node)] = index
        for child in node:
            mark(child, index)

    mark(root, 0)
    return AssembledDocument(root, segments, lines, tuple(assembly.problems), tuple(sync_problems),
                             tuple(assembly.parts), segment_of)
