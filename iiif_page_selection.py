# -*- coding: utf-8 -*-
"""Explicit IIIF canvas selection and stable, non-positional PAGE/ALTO links.

The manifest is the catalogue, *not* the set of editorial pages.  IDs are
canvas URIs when supplied by the IIIF server, otherwise manifest page IDs.
Never infer an OCR/canvas association by ordinal position in explicit mode.
"""
from __future__ import annotations
from pathlib import Path
import re


def canvas_key(page: dict) -> str:
    image = page.get('image') or {}
    return str(image.get('canvas') or page.get('id') or '').strip()


def natural_key(value) -> tuple:
    """Folio-friendly numeric sorting: img_2v precedes img_10r.

    Equal keys remain in source order (Python's stable sort).  Caller retains
    explicit user ordering when the user does not request a new sort.
    """
    name = Path(str(value)).name.casefold()
    return tuple((0, int(part)) if part.isdigit() else (1, part)
                 for part in re.split(r'(\d+)', name))


def exact_image_stem(value) -> str:
    """Strict, extension-independent image basename (no fuzzy folio matching).

    Accept both ordinary paths and IIIF URLs. Case and Unicode compatibility
    are normalized, but punctuation and internal whitespace are retained.
    """
    import unicodedata
    from urllib.parse import unquote, urlsplit

    value = str(value or '').strip().replace('\\', '/')
    if not value:
        return ''
    path = unquote(urlsplit(value).path)
    filename = path.rstrip('/').rsplit('/', 1)[-1]
    suffix = Path(filename).suffix.casefold()
    if suffix in {'.jpg', '.jpeg', '.png', '.tif', '.tiff', '.jp2', '.webp',
                  '.bmp', '.xml', '.alto'}:
        filename = filename[:-len(suffix)]
    result = unicodedata.normalize('NFKC', filename).casefold().strip()
    # IIIF image URLs often end in generic endpoint names, not image names.
    return '' if result in {'', 'default', 'full', 'info'} else result


def propose_exact_ocr_links(manifest, layout_files, existing_links=()):
    """Suggest unambiguous OCR-file / IIIF-canvas links by exact image names.

    Never use manifest position or approximate folio recognition. OCR source
    image filename and XML filename can *both* identify a page, but conflicting
    evidence is a reason not to guess. Explicit links always win. Multiple OCR
    files claiming the same canvas are ambiguous unless manually resolved.

    Returns (canvas_to_ocr_path, problematic_file_names). Only one-page PAGE
    or ALTO files are eligible, matching the editable dialog's constraints.
    """
    from alto_import import parse_layout_file
    import xml.etree.ElementTree as ET

    filenames_to_canvases = {}
    for page in manifest.pages:
        key = canvas_key(page)
        image = page.get('image') or {}
        # Include label because a manifest may expose a useful filename only
        # as its canvas label, but avoid interpreting numeric ordinal IDs.
        candidates = (image.get('image'), image.get('service'), page.get('label'))
        for candidate in candidates:
            name = exact_image_stem(candidate)
            if name:
                filenames_to_canvases.setdefault(name, set()).add(key)

    reserved_canvases = {str(canvas) for _, canvas in existing_links}
    reserved_paths = {_canonical_path(path) for path, _ in existing_links}
    proposed_by_canvas = {}
    candidates_by_canvas = {}
    problems = []
    for item in layout_files or ():
        path = Path(item.path).expanduser().resolve()
        canonical = str(path)
        if canonical in reserved_paths:
            continue
        try:
            parsed = parse_layout_file(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            problems.append(f'{path.name}: {exc}')
            continue
        if len(parsed.pages) != 1:
            problems.append(f'{path.name}: multi-page OCR')
            continue
        # Prefer exact image metadata when provided, but refuse contradictions
        # with any other exact match derived from the XML basename.
        page = parsed.pages[0]
        stems = {exact_image_stem(page.get('alto_source_image')),
                 exact_image_stem(path.name)} - {''}
        possible = set().union(*(filenames_to_canvases.get(stem, set()) for stem in stems))
        if len(possible) > 1:
            problems.append(f'{path.name}: conflicting or duplicate IIIF names')
            continue
        if not possible:
            continue  # Ordinary non-matches are not errors or guesses.
        key = next(iter(possible))
        if key not in reserved_canvases:
            candidates_by_canvas.setdefault(key, []).append(canonical)

    for key, paths in candidates_by_canvas.items():
        if len(paths) == 1:
            proposed_by_canvas[key] = paths[0]
        else:
            problems.extend(f'{Path(path).name}: multiple OCR files identify one canvas'
                            for path in paths)
    return proposed_by_canvas, problems


def selected_manifest_pages(manifest, selected_keys, selection_mode='all'):
    if selection_mode not in ('all', 'selected'):
        raise ValueError('Unknown IIIF selection mode')
    if selection_mode == 'all':
        return list(enumerate(manifest.pages))
    requested = set(selected_keys or ())
    all_keys = [canvas_key(p) for p in manifest.pages]
    if len(set(all_keys)) != len(all_keys) or not all(all_keys):
        raise ValueError('IIIF manifest has missing or duplicate canvas identifiers')
    missing = requested.difference(all_keys)
    if missing:
        raise ValueError('Selected IIIF canvases no longer exist: ' + ', '.join(sorted(missing)[:5]))
    return [(i, p) for i, p in enumerate(manifest.pages) if canvas_key(p) in requested]


def _canonical_path(path):
    return str(Path(path).expanduser().resolve())


def selected_page_overlay(cache: dict, manifest, selected_keys, links,
                          witness_id='W', project_root=None) -> dict:
    """Use ONLY selected canvases, merge their linked OCR pages without guessing.

    Unlinked OCR/synchronization pages are preserved with a neutral image.
    A misconfigured or ambiguous explicit link raises instead of attaching
    a manuscript line to the wrong page.
    """
    from tei_facsimile import default_surface_id
    source_pages = [dict(p) for p in (cache or {}).get('pages', ())]
    selections = selected_manifest_pages(manifest, selected_keys, 'selected')
    selection_ids = {canvas_key(p) for _, p in selections}
    links = list(links or ())
    paths_to_canvas = {}
    canvases_to_path = {}
    for source, canvas in links:
        path = _canonical_path(source if Path(source).is_absolute() else Path(project_root or '.') / source)
        if canvas not in selection_ids:
            raise ValueError(f'OCR link points to an unselected IIIF canvas: {canvas}')
        if path in paths_to_canvas and paths_to_canvas[path] != canvas:
            raise ValueError(f'An OCR file was assigned to multiple canvases: {path}')
        if canvas in canvases_to_path and canvases_to_path[canvas] != path:
            raise ValueError(f'Two OCR files were assigned to the same canvas: {canvas}')
        paths_to_canvas[path] = canvas
        canvases_to_path[canvas] = path
    by_source = {}
    for i, page in enumerate(source_pages):
        f = page.get('alto_source_file')
        if f:
            by_source.setdefault(_canonical_path(f), []).append(i)
    chosen = {}
    assigned = set()
    for path, canvas in paths_to_canvas.items():
        matches = by_source.get(path, [])
        if len(matches) != 1:
            raise ValueError(f'OCR link must identify exactly one PAGE/ALTO page: {path} ({len(matches)} found)')
        pos = matches[0]
        if pos in assigned:
            raise ValueError(f'OCR page assigned more than once: {path}')
        assigned.add(pos)
        chosen[canvas] = pos
    result = []
    for index, manifest_page in selections:
        key = canvas_key(manifest_page)
        if key in chosen:
            page = dict(source_pages[chosen[key]])
        else:
            page = {'id': manifest_page['id'], 'lines': []}
        page.pop('iiif', None)
        page['image'] = dict(manifest_page['image'])
        page['label'] = str(manifest_page.get('label') or page.get('label') or '')
        # ID is derived from *original* manifest position, never selection rank.
        page['tei_surface_id'] = default_surface_id(witness_id, index + 1)
        page['iiif_canvas_key'] = key
        result.append(page)
    for i, original in enumerate(source_pages):
        if i in assigned:
            continue
        page = dict(original)
        page.pop('iiif', None)
        page['image'] = {'type': 'none', 'label': page.get('label', '')}
        # Preserve editorial links but do not fabricate a IIIF surface.
        result.append(page)
    out = dict(cache or {})
    out['pages'] = result
    meta = dict(out.get('meta') or {})
    meta['iiif_manifest'] = manifest.source
    meta['iiif_selection_mode'] = 'selected'
    out['meta'] = meta
    return out
