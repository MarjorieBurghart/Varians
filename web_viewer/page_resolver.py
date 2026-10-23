# -*- coding: utf-8 -*-
"""Conservative TEI page-anchor -> physical alignment-page resolution for web export.

``pb/@n`` is an editorial page label, NOT necessarily an alignment JSON
page identifier. Prefer explicit ``@facs`` pointing to a known surface or zone,
then legacy exact technical page identifiers. Never correlate by page order or
fuzzy matching. A missing/ambiguous reference must stay unresolved.
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import xml.etree.ElementTree as ET

XML_ID = '{http://www.w3.org/XML/1998/namespace}id'


def _local(tag):
    return str(tag).rsplit('}', 1)[-1]


def _unique(mapping, key):
    values = mapping.get(key, ())
    return next(iter(values)) if len(values) == 1 else None


class PageResolver:
    """Maps TEI ``pb`` markers to exact page IDs emitted from an alignment.

    All maps store *sets*, retaining collisions as ambiguous instead of letting
    the last duplicated surface/label silently win.
    """

    def __init__(self, edition: str | Path, pages: list[dict], witness_id: str):
        self.witness_id = str(witness_id).lstrip('#')
        self.ids = defaultdict(set)
        self.references = defaultdict(set)
        self.labels = defaultdict(set)
        self.stats = {'resolved_facs': 0, 'resolved_id': 0,
                      'resolved_label': 0, 'unresolved': 0, 'ambiguous': 0}
        owned_surfaces = defaultdict(set)
        pages_by_graphic = defaultdict(set)
        for p in pages or ():
            pid = str(p.get('id') or '').strip()
            if not pid:
                continue
            self.ids[pid].add(pid)
            # Another explicit proof of identity is an *exact* graphic URL
            # shared by a TEI surface and a known image resource. In contrast,
            # similar labels or page ordinals are never used as evidence.
            for image in (p.get('image'), p.get('iiif')):
                if isinstance(image, dict):
                    for key in ('url', 'image', 'service', 'path'):
                        url = str(image.get(key) or '').strip()
                        if url:
                            pages_by_graphic[url].add(pid)
            sid = str(p.get('tei_surface_id') or '').lstrip('#').strip()
            if sid:
                self.references[sid].add(pid)
                owned_surfaces[sid].add(pid)
            for label in (p.get('label'), (p.get('image') or {}).get('label'),
                          (p.get('iiif') or {}).get('label')):
                label = str(label or '').strip().casefold()
                if label:
                    self.labels[label].add(pid)
        # A zone's xml:id points to its parent surface, never to a new page.
        # Record every declaration; duplicate zone IDs remain ambiguous.
        # ``edition`` : a file, or the already parsed root of an assembled
        # edition (V0.9.1.6).
        root = edition if isinstance(edition, ET.Element) else ET.parse(edition).getroot()
        for surface in root.iter():
            if _local(surface.tag) != 'surface':
                continue
            sid = str(surface.attrib.get(XML_ID) or '').strip()
            if not sid:
                continue
            for child in surface:
                if _local(child.tag) == 'graphic':
                    url = str(child.attrib.get('url') or '').strip()
                    owned_surfaces[sid].update(pages_by_graphic.get(url, ()))
            if not owned_surfaces.get(sid):
                continue
            self.references[sid].update(owned_surfaces[sid])
            for child in surface.iter():
                if child is surface or _local(child.tag) != 'zone':
                    continue
                zid = str(child.attrib.get(XML_ID) or '').strip()
                if zid:
                    self.references[zid].update(owned_surfaces[sid])
        # For repeated XML ids, avoid treating either occurrence as unique.
        declarations = defaultdict(int)
        for element in root.iter():
            if _local(element.tag) in {'surface', 'zone'}:
                eid = str(element.attrib.get(XML_ID) or '').strip()
                if eid:
                    declarations[eid] += 1
        for ref, count in declarations.items():
            if count > 1:
                self.references[ref].add('__AMBIGUOUS_XML_ID__')

    def resolve(self, pb: ET.Element) -> str | None:
        """Return the physical JSON page id, or None on uncertainty."""
        facs = str(pb.attrib.get('facs') or '').strip().split()
        name = str(pb.attrib.get('n') or '').strip()
        edref = {part.lstrip('#') for part in str(pb.attrib.get('edRef') or '').split()}
        if facs:
            found = set()
            for ref in facs:
                if ref.startswith('#'):
                    found.update(self.references.get(ref[1:], ()))
            if len(found) == 1:
                resolved = next(iter(found))
                # Contradictory exact technical ids must not be concealed by
                # a superficially valid facsimile pointer.
                from_name = _unique(self.ids, name)
                if from_name is not None and from_name != resolved:
                    self.stats['ambiguous'] += 1
                    return None
                self.stats['resolved_facs'] += 1
                return resolved
            # Legacy projects may carry a stale/non-indexed facs pointer but
            # still have an explicit witness-scoped *exact* JSON page ID.
            # Never use editorial labels as a fallback over an unknown facs.
            if not found and self.witness_id in edref:
                pid = _unique(self.ids, name)
                if pid is not None:
                    self.stats['resolved_id'] += 1
                    return pid
            self.stats['ambiguous' if len(found) > 1 else 'unresolved'] += 1
            return None
        # Old TEI projects may use an exact JSON id in pb/@n, without @facs.
        pid = _unique(self.ids, name)
        if pid is not None:
            self.stats['resolved_id'] += 1
            return pid
        # An explicit @edRef permits unique *exact* labels, never an ordinal.
        if self.witness_id in edref and name:
            pid = _unique(self.labels, name.casefold())
            if pid is not None:
                self.stats['resolved_label'] += 1
                return pid
        self.stats['unresolved'] += 1
        return None
