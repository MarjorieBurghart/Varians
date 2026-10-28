# -*- coding: utf-8 -*-
"""Varians: construction transactionnelle et diagnostic des ressources des témoins.

Ce module ne dépend pas de PySide6. Il ne modifie ni project.xml ni les JSON,
les ALTO/PAGE, les images ou le texte TEI. L'interface décide quand commettre
le nouvel état assemblé, seulement après construction complète et validation.
"""
from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

from project_config import has_line_synchronization
from resource_state import primary_sync_line_count, secondary_sync_link_count
from alto_import import apply_witness_alto_policy
from image_sources import (apply_witness_image_policy, page_image_source,
                           page_navigation_items, image_only_items)
from iiif_local import apply_working_copy


def read_alignment_json(path):
    """Raise explicitly on unreadable/invalid JSON; never return a fake empty file."""
    with Path(path).open('r', encoding='utf-8') as fh:
        value = json.load(fh)
    if not isinstance(value, dict) or not isinstance(value.get('pages', []), list):
        raise ValueError('Alignment root must be an object with a pages array')
    for page in value.get('pages', []):
        if not isinstance(page, dict) or not isinstance(page.get('lines', []), list):
            raise ValueError('Alignment page must be an object with a lines array')
        for line in page.get('lines', []):
            if not isinstance(line, dict):
                raise ValueError('Alignment lines must be objects')
            for field in ('base_keys', 'keys816'):
                keys = line.get(field)
                if keys is not None and (not isinstance(keys, list) or
                                         not all(isinstance(k, str) for k in keys)):
                    raise ValueError(f'{field} must be an array of string identifiers')
    return value


def flatten_primary(cache):
    items, by_key = [], {}
    for page in cache.get('pages', []):
        for line in page.get('lines', []):
            key = f"{page['id']}::{line.get('line')}"
            by_key[key] = len(items)
            items.append({'p': page, 'l': line, 'key': key})
    return items, by_key


def flatten_secondary(cache):
    items = [{'p': page, 'l': line,
              'key': f"{page['id']}::{line.get('alto_id') or line.get('line')}"}
             for page in cache.get('pages', []) for line in page.get('lines', [])]
    items.sort(key=lambda x: int(x['l'].get('order') or 0))
    by_base = defaultdict(list)
    for index, item in enumerate(items):
        for key in item['l'].get('base_keys') or item['l'].get('keys816') or []:
            by_base[str(key)].append(index)
    return items, dict(by_base)


def line_keys(cache):
    """Stable fingerprint of line associations, ignoring mutable OCR text."""
    result = []
    for page in cache.get('pages', []) or []:
        for line in page.get('lines', []) or []:
            result.append((str(page.get('id')), str(line.get('alto_id') or line.get('line')),
                           tuple(str(key) for key in (line.get('base_keys') or line.get('keys816') or []))))
    return tuple(result)


def sync_fingerprint(cache):
    data = json.dumps(line_keys(cache), ensure_ascii=False, separators=(',', ':'))
    return hashlib.sha256(data.encode('utf-8')).hexdigest()


@dataclass
class RuntimeState:
    raw: dict
    caches: dict
    witness_items: dict
    display_items: dict
    base_by_key: dict
    base_maps: dict
    base_items: list
    base_sync_count: int | None
    base_active: bool
    secondary_links: dict
    images_available: dict


def assemble_resources(project):
    """Stage all witness resources before touching any running GUI state.

    A malformed JSON or invalid mapping aborts the entire stage, preserving
    the editor, panels and prior cache. Avoid rank-based associations.
    """
    raw, caches, items_by_witness, base_maps, base_by_key = {}, {}, {}, {}, {}
    base_id = project.base_witness
    base_count = None
    secondary_links = {}
    for w in project.witnesses:
        if has_line_synchronization(w):
            source = read_alignment_json(w.alignment)
            if w.is_base:
                base_count = primary_sync_line_count(source)
            else:
                secondary_links[w.id] = secondary_sync_link_count(source)
        else:
            source = {'meta': {'witness': w.id, 'role': w.role}, 'pages': []}
            if not w.is_base:
                secondary_links[w.id] = 0
        raw[w.id] = source
        cache = apply_witness_alto_policy(
            source, getattr(w, 'alto_source_type', 'auto'),
            [x.path for x in getattr(w, 'alto_files', ())],
            project.root_dir, w.id, w.role,
            strict_no_ordinal=(getattr(w, 'image_source_type', '') == 'iiif'),
        )
        cache = apply_witness_image_policy(
            cache, getattr(w, 'image_source_type', 'auto'),
            getattr(w, 'image_source_value', None), project.root_dir,
            getattr(w, 'image_files', ()), w.id,
            getattr(w, 'iiif_selection_mode', 'all'),
            getattr(w, 'iiif_selected_canvases', ()),
            getattr(w, 'iiif_ocr_links', ()),
            getattr(w, 'iiif_page_links', ()),
        )
        if getattr(w, 'iiif_local_copy', False) and w.image_source_type == 'iiif':
            cache = apply_working_copy(cache, project.root_dir, w.id)
        caches[w.id] = cache
        if w.is_base:
            items_by_witness[w.id], base_by_key = flatten_primary(cache)
        else:
            items_by_witness[w.id], base_maps[w.id] = flatten_secondary(cache)
    base_active = bool(base_count and has_line_synchronization(project.witness_by_id[base_id]))
    display = {}
    images_available = {}
    for w in project.witnesses:
        cache = caches[w.id]
        if base_active and (w.is_base or secondary_links.get(w.id, 0) > 0):
            chosen = items_by_witness[w.id]
        else:
            chosen = page_navigation_items(cache, project.root_dir)
            if not chosen:
                chosen = items_by_witness[w.id] or image_only_items(cache, project.root_dir)
        display[w.id] = chosen
        images_available[w.id] = any(
            page_image_source(page, project.root_dir).available
            for page in cache.get('pages', [])
        )
    return RuntimeState(raw, caches, items_by_witness, display, base_by_key,
                        base_maps, items_by_witness.get(base_id, []), base_count,
                        base_active, secondary_links, images_available)


@dataclass(frozen=True)
class WitnessDiagnostic:
    id: str
    label: str
    is_base: bool
    pages: int
    geometry_lines: int
    images: int
    missing_images: int
    linked_lines: int
    usable_links: int
    unknown_keys: int
    issue_codes: tuple[str, ...]
    active: bool
    fingerprint: str
    # Sigle montré à l'écran, s'il diffère de l'identifiant (V0.9.2.8.2).
    siglum: str = ""


def diagnostic_rows(project, state):
    """Build an explicit, read-only report; an ALTO alone is not a sync."""
    rows = []
    # Only genuine reference lines from the raw pivot alignment count as
    # scientific targets. OCR-only lines added by ALTO do not establish sync.
    valid = {
        f"{page['id']}::{line.get('line')}"
        for page in state.raw.get(project.base_witness, {}).get('pages', [])
        if page.get('id')
        for line in page.get('lines', []) if line.get('line') is not None
    }
    for w in project.witnesses:
        raw = state.raw[w.id]
        cache = state.caches[w.id]
        issues = []
        meta = raw.get('meta') or {}
        configured = bool(w.alignment)
        path_ok = has_line_synchronization(w)
        if configured and not path_ok:
            issues.append('alignment_missing')
        if path_ok:
            # Le JSON peut nommer un témoin par son identifiant ou par son
            # sigle (V0.9.2.8.2).
            if meta.get('witness') and str(meta['witness']) not in {w.id, getattr(w, 'display_siglum', w.id)}:
                issues.append('witness_mismatch')
            pivot = next((x for x in project.witnesses if x.id == project.base_witness), None)
            pivot_names = {project.base_witness, getattr(pivot, 'display_siglum', project.base_witness)}
            if not w.is_base and meta.get('base_witness') and str(meta['base_witness']) not in pivot_names:
                issues.append('pivot_mismatch')
        line_count = sum(len(p.get('lines', [])) for p in cache.get('pages', []))
        image_count = 0
        missing_images = 0
        for page in cache.get('pages', []):
            src = page_image_source(page, project.root_dir)
            if src.available:
                image_count += 1
                if src.kind == 'file' and (not src.file_path or not src.file_path.is_file()):
                    missing_images += 1
        if missing_images:
            issues.append('local_images_missing')
        orphan_ocr = int((cache.get('meta') or {}).get('iiif_unassociated_layout_count') or 0)
        if orphan_ocr:
            issues.append('ocr_unassociated')
        all_keys = []
        linked = 0
        for page in raw.get('pages', []):
            for line in page.get('lines', []):
                keys = line.get('base_keys') or line.get('keys816') or []
                if keys:
                    linked += 1
                    all_keys.extend(map(str, keys))
        unknown = sum(k not in valid for k in all_keys) if not w.is_base else 0
        usable = len(all_keys) - unknown if not w.is_base else 0
        if not w.is_base and path_ok:
            if linked == 0:
                issues.append('no_base_keys')
            elif not state.base_active:
                issues.append('pivot_unavailable')
            elif usable == 0:
                issues.append('all_keys_unknown')
            elif unknown:
                issues.append('some_keys_unknown')
        if not w.is_base and not path_ok and any(cache.get('pages', [])):
            # This is normal: images or ALTO without JSON are useful witnesses.
            issues.append('pages_only')
        if w.is_base and path_ok and not state.base_active:
            issues.append('pivot_no_lines')
        active = (state.base_active if w.is_base else
                  bool(state.base_active and usable))
        rows.append(WitnessDiagnostic(
            w.id, w.label, w.is_base, len(cache.get('pages', [])),
            line_count, image_count, missing_images, linked, usable, unknown,
            tuple(issues), active, sync_fingerprint(raw), getattr(w, "siglum", ""),
        ))
    return tuple(rows)


def changed_witnesses(before, after):
    """Changes can have the same number of lines but different associations."""
    previous = {row.id: row for row in before}
    return [row.id for row in after if row.id not in previous or row != previous[row.id]]
