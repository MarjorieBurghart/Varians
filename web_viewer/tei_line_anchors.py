# -*- coding: utf-8 -*-
"""Deterministic TEI lb -> physical pivot-line binding for web publication.

The desktop editor navigates using the ordinal of each literal pivot
``<lb edRef="#PIVOT"/>`` in the XML source, indexing the flattened pivot JSON
(page order, then line order).  ``pb/@n`` and ``pb/@facs`` govern folio navigation;
they are NOT scientific proof of a different line alignment.  This module
reuses the desktop line-indexing contract, without guessing cross-witness
links: secondary witnesses still require explicit ``base_keys``.
"""
from __future__ import annotations

from dataclasses import dataclass
import xml.etree.ElementTree as ET


def _local_name(tag: str) -> str:
    return str(tag).rsplit('}', 1)[-1]


@dataclass(frozen=True)
class AnchorReport:
    tei_lb_count: int
    physical_line_count: int
    mapped_lb_count: int
    unmapped_lb_count: int
    physical_without_lb: int

    def as_dict(self):
        return {
            'tei_lb_count': self.tei_lb_count,
            'physical_line_count': self.physical_line_count,
            'mapped_lb_count': self.mapped_lb_count,
            'unmapped_lb_count': self.unmapped_lb_count,
            'physical_without_lb': self.physical_without_lb,
            'count_match': self.tei_lb_count == self.physical_line_count,
        }


def build_pivot_lb_index(root: ET.Element, witness_id: str, physical_keys):
    """Return ``id(TEI lb) -> exact physical key`` plus mismatch diagnostics.

    Match the desktop's exact ``edRef='#PIVOT'`` eligibility, including XML
    namespace prefixes, and count all these elements in XML source order.
    This includes lb nodes in reading alternatives or notes: the desktop's
    lexical lb cache likewise counts these, even if the publication chooses
    not to display their text. No page label, text similarity, or geometric
    position is used to invent a line key.
    """
    target = '#' + str(witness_id).lstrip('#')
    elements = [el for el in root.iter()
                if _local_name(el.tag) == 'lb' and el.attrib.get('edRef') == target]
    keys = list(physical_keys or [])
    lookup = {id(el): keys[i] for i, el in enumerate(elements[:len(keys)])}
    mapped = len(lookup)
    report = AnchorReport(len(elements), len(keys), mapped,
                          len(elements)-mapped, len(keys)-mapped)
    return lookup, report
