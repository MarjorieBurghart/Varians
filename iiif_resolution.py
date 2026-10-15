# -*- coding: utf-8 -*-
"""Resolve synchronization page identities to IIIF canvases (Presentation 2/3).

Evidence is evaluated by precedence: manual page link, exact canvas URI,
Image API service URI, IIIF image URL (resolution-independent), unique label,
then explicit manual resolution. Neither selected rank nor manifest position is
identity evidence. The input synchronization pages and their lines are NEVER
modified; all overlays are shallow copies with presentation metadata.
"""
from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit, unquote
import re

from iiif_page_selection import canvas_key


@dataclass(frozen=True)
class Resolution:
    key: str | None
    status: str
    method: str = ''
    candidates: tuple[str, ...] = ()


def _uri(value):
    raw = str(value or '').strip()
    if not raw:
        return ''
    parts = urlsplit(raw)
    if not parts.scheme or not parts.netloc:
        return raw.rstrip('/')
    # Hostname is case-insensitive. Preserve path case, query (can be an ID),
    # encoding and significant path separators; discard fragment only.
    host = parts.netloc.lower()
    return urlunsplit((parts.scheme.lower(), host, parts.path.rstrip('/'), parts.query, ''))


def _iiif_image_identity(url):
    """Normalize only *recognized* IIIF Image API request suffixes.

    The underlying identifier may contain slashes. Avoid generic URL filename
    stripping, which would incorrectly equate unrelated photos and canvases.
    """
    value = _uri(url)
    if not value:
        return ''
    parts = urlsplit(value)
    path = parts.path
    segments = path.split('/')
    if len(segments) >= 5:
        region, size, rotation, quality = segments[-4:]
        if (re.fullmatch(r'(full|square|pct:\d+(?:\.\d+)?|(?:\d*,){3}\d+)', region, re.I)
            and re.fullmatch(r'(full|max|pct:\d+(?:\.\d+)?|!?\d*,\d*|\d+,)', size, re.I)
            and re.fullmatch(r'!?\d+(?:\.\d+)?', rotation)
            and re.fullmatch(r'(default|native|color|grey|gray|bitonal)\.(jpg|jpeg|png|webp|tif|tiff|jp2)', quality, re.I)):
            return urlunsplit((parts.scheme, parts.netloc, '/'.join(segments[:-4]).rstrip('/'), parts.query, ''))
    return value


def _service_of_image_url(url):
    value = _iiif_image_identity(url)
    return value if value != _uri(url) else ''


def _label(value):
    """Exact typographic normalization only, not fuzzy folio guessing."""
    import unicodedata
    return ' '.join(unicodedata.normalize('NFKC', str(value or '')).casefold().split())


def _page_meta(page):
    old = page.get('iiif') if isinstance(page.get('iiif'), dict) else {}
    new = page.get('image') if isinstance(page.get('image'), dict) else {}
    remote = new.get('remote_iiif') if isinstance(new.get('remote_iiif'), dict) else {}
    return old, new, remote


def resolve_pages(pages, manifest, selected_keys=None, explicit_links=(), ocr_links=(), project_root=None):
    """Return page-index -> Resolution; no changes to pages or project files.

    An ambiguous stronger signal never falls through to a weaker one. A manual
    link is authoritative, and one canvas cannot be assigned to two sync pages.
    OCR links are explicit evidence only when the parsed OCR *source path* is
    uniquely present on one page; filenames/ordinal positions are never used.
    """
    all_pages = list(manifest.pages)
    keys = [canvas_key(p) for p in all_pages]
    if not all(keys) or len(set(keys)) != len(keys):
        raise ValueError('Missing or duplicate IIIF canvas IDs')
    allowed = set(keys) if selected_keys is None else set(selected_keys)
    missing = allowed - set(keys)
    if missing:
        raise ValueError('Selected IIIF canvases not in manifest: ' + ', '.join(sorted(missing)[:5]))
    indices = {k: i for i, k in enumerate(keys) if k in allowed}

    from pathlib import Path
    def resolved_path(value):
        p = Path(str(value)).expanduser()
        if not p.is_absolute() and project_root is not None:
            p = Path(project_root) / p
        return str(p.resolve())

    manual = {}
    for pid, canvas in explicit_links or ():
        pid, canvas = str(pid), str(canvas)
        if pid in manual and manual[pid] != canvas:
            raise ValueError('Conflicting explicit IIIF links for page: ' + pid)
        if canvas not in indices:
            raise ValueError('Explicit IIIF canvas is not selected: ' + canvas)
        manual[pid] = canvas
    if len(set(manual.values())) != len(manual):
        raise ValueError('Two synchronized pages explicitly target one canvas')
    if len({str(p.get('id')) for p in pages}) != len(pages):
        raise ValueError('Duplicate synchronized page IDs; cannot resolve images safely')
    missing_ids = set(manual) - {str(p.get('id')) for p in pages}
    if missing_ids:
        raise ValueError('Unknown synchronized page IDs: ' + ', '.join(sorted(missing_ids)[:5]))

    path_map = {}
    for path, key in ocr_links or ():
        if key in indices:
            path_map.setdefault(resolved_path(path), set()).add(str(key))

    def manifest_signals(canvas):
        im = canvas.get('image') or {}
        return (
            {_uri(im.get('canvas') or canvas_key(canvas))} - {''},
            {_uri(im.get('service')), _service_of_image_url(im.get('image'))} - {''},
            {_iiif_image_identity(im.get('image'))} - {''},
            {_label(canvas.get('label')), _label(im.get('label'))} - {''},
        )

    canon = {k: manifest_signals(all_pages[i]) for k, i in indices.items()}
    proposed = {}
    for i, page in enumerate(pages):
        pid = str(page.get('id') or '')
        if pid in manual:
            proposed[i] = Resolution(manual[pid], 'resolved', 'manual')
            continue
        old, new, remote = _page_meta(page)
        canvas_refs = {_uri(d.get(key)) for d in (old, new, remote) for key in ('canvas', '@id', 'id') if d.get(key)} - {''}
        if page.get('iiif_canvas_key'):
            canvas_refs.add(_uri(page['iiif_canvas_key']))
        services = {_uri(d.get('service')) for d in (old, new, remote) if d.get('service')} - {''}
        urls = {_iiif_image_identity(d.get(k)) for d in (old, new, remote) for k in ('image', 'url') if d.get(k)} - {''}
        services.update({_service_of_image_url(d.get(k)) for d in (old, new, remote) for k in ('image', 'url') if d.get(k)} - {''})
        labels = {_label(d.get('label')) for d in (old, new, remote) if d.get('label')} - {''}
        if page.get('label'):
            labels.add(_label(page['label']))
        # Labels mechanically generated as page ordinals cannot establish a
        # physical folio identity; manuscript labels such as 'f. 14v' can.
        labels = {label for label in labels if not re.fullmatch(r'(?:page|vue|image)\s*\d+', label)}
        ocr_canvas = path_map.get(resolved_path(page['alto_source_file']), set()) if page.get('alto_source_file') else set()
        # The explicit OCR link is a declaration about this physical page;
        # it is more reliable than a label, less so than its own IIIF ID.
        for method, evidence, pos in (
            ('canvas', canvas_refs, 0), ('service', services, 1),
            ('image', urls, 2), ('ocr', ocr_canvas, None), ('label', labels, 3),
        ):
            if not evidence or (method == 'label' and canvas_refs):
                continue
            candidates = (set(evidence).intersection(indices) if pos is None else
                          {k for k, data in canon.items() if data[pos].intersection(evidence)})
            if len(candidates) == 1:
                proposed[i] = Resolution(next(iter(candidates)), 'resolved', method)
                break
            if len(candidates) > 1:
                proposed[i] = Resolution(None, 'ambiguous', method, tuple(sorted(candidates)))
                break
        else:
            # When an exact Canvas pointer was supplied but is no longer
            # present, do not silently accept a merely similar folio label.
            method = 'canvas_not_found' if canvas_refs else 'no_identifier'
            proposed[i] = Resolution(None, 'unresolved', method)

    # Independent collision check across all levels of evidence. Ambiguity
    # beats automatic guessing; manual reservations beat automatic guesses.
    reverse = {}
    for i, result in proposed.items():
        if result.key:
            reverse.setdefault(result.key, []).append(i)
    for key, positions in reverse.items():
        if len(positions) > 1:
            reserved = [i for i in positions if proposed[i].method == 'manual']
            for i in positions:
                if i not in reserved:
                    proposed[i] = Resolution(None, 'ambiguous', 'duplicate_canvas', (key,))
            if not reserved:
                for i in positions:
                    proposed[i] = Resolution(None, 'ambiguous', 'duplicate_canvas', (key,))
    return proposed


def _merge_detached_ocr_pages(source, meta, manifest, page_links, ocr_links, project_root):
    """Attach separately imported OCR geometry to its synchronized page.

    Only a UNIQUE common Canvas identity proves that two records are one
    physical page. Keep synchronization keys, line numbers and annotations.
    Unknown OCR line IDs never borrow `base_keys` by ordinal position.
    """
    if meta.get('format') != 'tei-manuscript-alignment':
        return source
    sync_indices = [i for i,p in enumerate(source) if not p.get('_ocr_unmerged')]
    ocr_indices = [i for i,p in enumerate(source) if p.get('_ocr_unmerged')]
    if not sync_indices or not ocr_indices:
        return source
    sync = [source[i] for i in sync_indices]
    synced = resolve_pages(sync, manifest, explicit_links=page_links,
                           project_root=project_root)
    ocr = [source[i] for i in ocr_indices]
    ocr_resolved = resolve_pages(ocr, manifest, ocr_links=ocr_links,
                                 project_root=project_root)
    by_canvas = {r.key: j for j,r in synced.items() if r.key}
    consumed = set()
    for n, ocr_page in enumerate(ocr):
        linked = ocr_resolved[n]
        if not linked.key or linked.key not in by_canvas:
            continue
        sync_page = sync[by_canvas[linked.key]]
        # Only merge one OCR geometry source into each sync page. A second
        # format (ALTO + PAGE) requires a user choice; no silent replacement.
        if sync_page.get('_ocr_geometry_merged'):
            continue
        combined = dict(sync_page)
        for field in ('alto_width', 'alto_height', 'alto_source_file',
                      'alto_source_image', 'geometry_format'):
            if ocr_page.get(field) is not None:
                combined[field] = ocr_page[field]
        old_lines = [dict(line) for line in sync_page.get('lines') or ()]
        new_lines = [dict(line) for line in ocr_page.get('lines') or ()]
        by_id = {}
        for i, line in enumerate(old_lines):
            line_id = str(line.get('alto_id') or '')
            if line_id:
                by_id.setdefault(line_id, []).append(i)
        used = set()
        for line in new_lines:
            line_id = str(line.get('alto_id') or '')
            candidates = by_id.get(line_id, []) if line_id else []
            if len(candidates) == 1:
                index = candidates[0]
                old_line = old_lines[index]
                for geom in ('bbox','polygon','baseline','geometry_format'):
                    if geom in line:
                        old_line[geom] = line[geom]
                used.add(id(line))
        # Imported lines without a matching ID have no established relation to
        # a synchronized line. They may still be drawn in page mode, but may
        # not inherit `base_keys` or ordinal `line` numbers.
        if not old_lines:
            combined['lines'] = new_lines
        else:
            combined['lines'] = old_lines
        combined['_ocr_geometry_merged'] = True
        sync[by_canvas[linked.key]] = combined
        consumed.add(ocr_indices[n])
    result = list(source)
    for j, original_index in enumerate(sync_indices):
        result[original_index] = sync[j]
    return [page for i,page in enumerate(result) if i not in consumed]


def _layout_only_manifest_pages(cache, manifest, witness_id, selection,
                                page_links, ocr_links, project_root, *, selected_mode=False):
    """Keep a non-synchronized witness's selected IIIF images independent of OCR.

    The manifest/explicit Canvas selection defines its pages. Optional ALTO or
    PAGE files only *enrich* an identified Canvas. Unknown OCR cannot hide an
    image, change its stable page/surface ID, or be attached by list position.
    Unattached geometry stays in the derived cache for diagnosis and future
    manual association; no source files, alignment IDs or TEI are modified.
    """
    from pathlib import Path
    from tei_facsimile import default_surface_id
    from iiif_local import _read_index, _valid_entry

    source = list((cache or {}).get('pages') or ())
    allowed = {canvas_key(p) for _, p in selection}
    ids = [str(page.get('id') or '') for page in source]
    # Independent OCR exports routinely repeat page IDs across files. The
    # alignment resolver rightly rejects duplicate *synchronized* page IDs;
    # for standalone geometry we use positional surrogate IDs only inside the
    # resolver, never as evidence of Canvas identity or in the returned cache.
    duplicate_layout_ids = len(set(ids)) != len(ids)
    lookup_pages = ([dict(p, id=f'varians-temporary-layout-{i}') for i, p in enumerate(source)]
                    if duplicate_layout_ids else source)
    safe_page_links = () if duplicate_layout_ids else page_links
    resolutions = resolve_pages(lookup_pages, manifest, allowed,
                                safe_page_links, ocr_links, project_root)

    # A local working copy is a strong *physical identity* if the ALTO/PAGE
    # records that exact image filename. Every candidate must be unique.
    # This is NOT an OCR-file-order association and needs no HTTP access.
    by_filename = {}
    if project_root is not None:
        entries = _read_index(project_root, witness_id)
        for _index, canvas in selection:
            path = _valid_entry(project_root, witness_id, canvas.get('image') or {}, entries)
            if path is not None:
                by_filename.setdefault(path.name.casefold(), set()).add(canvas_key(canvas))
    resolved = {}
    for i, page in enumerate(source):
        match = resolutions[i]
        file_name = str(page.get('alto_source_image') or '').replace('\\', '/')
        file_name = Path(file_name).name.casefold() if file_name else ''
        local_candidates = by_filename.get(file_name, set()) if file_name else set()
        # When two independent strong identities disagree, do not select one.
        if match.key and local_candidates and match.key not in local_candidates:
            resolved[i] = Resolution(None, 'ambiguous', 'ocr_local_copy_conflict',
                                     tuple(sorted(local_candidates | {match.key})))
        elif match.key:
            resolved[i] = match
        elif match.status == 'unresolved' and len(local_candidates) == 1:
            resolved[i] = Resolution(next(iter(local_candidates)), 'resolved', 'local_copy')
        else:
            resolved[i] = match

    # Duplicate OCR files for one Canvas are not silently merged together.
    reverse = {}
    for i, match in resolved.items():
        if match.key:
            reverse.setdefault(match.key, []).append(i)
    for key, indices in reverse.items():
        if len(indices) > 1:
            for i in indices:
                resolved[i] = Resolution(None, 'ambiguous', 'duplicate_ocr_canvas', (key,))

    by_canvas = {r.key: i for i, r in resolved.items() if r.key}
    result = []
    for manifest_index, canvas in selection:
        key = canvas_key(canvas)
        page = {
            'id': canvas['id'], 'label': canvas.get('label') or '',
            'lines': [], 'image': dict(canvas['image']),
            'iiif_canvas_key': key,
            'tei_surface_id': default_surface_id(witness_id, manifest_index + 1),
            'iiif_resolution': {'status': 'resolved', 'method': 'canvas_selection', 'canvas': key},
        }
        src_idx = by_canvas.get(key)
        if src_idx is not None:
            ocr = source[src_idx]
            for field in ('alto_width', 'alto_height', 'alto_source_file',
                          'alto_source_image', 'geometry_format', 'lines'):
                if field in ocr:
                    page[field] = ocr[field]
            page['iiif_resolution'] = {
                'status': 'resolved', 'method': resolved[src_idx].method,
                'canvas': key,
            }
        result.append(page)

    unattached = []
    for i, p in enumerate(source):
        if not resolved[i].key:
            detached = dict(p)
            detached['iiif_resolution'] = {
                'status': resolved[i].status, 'method': resolved[i].method,
                'candidates': list(resolved[i].candidates),
            }
            unattached.append(detached)
    meta = dict((cache or {}).get('meta') or {})
    meta.update(iiif_manifest=manifest.source,
                iiif_presentation_version=manifest.presentation_version,
                iiif_selection_mode='selected' if selected_mode else 'all',
                iiif_unassociated_layout_count=len(unattached))
    out = dict(cache or {})
    out['meta'] = meta
    out['pages'] = result
    out['unassociated_layout_pages'] = unattached
    return out


def overlay_resolved_manifest(cache, manifest, witness_id, selected_keys=None,
                              page_links=(), ocr_links=(), project_root=None):
    from tei_facsimile import default_surface_id
    from iiif_page_selection import selected_manifest_pages
    source = list((cache or {}).get('pages') or ())
    source = _merge_detached_ocr_pages(
        source, (cache or {}).get('meta') or {}, manifest,
        page_links, ocr_links, project_root)
    selection = selected_manifest_pages(manifest, selected_keys or (), 'selected') if selected_keys is not None else list(enumerate(manifest.pages))
    if (cache or {}).get('meta', {}).get('format') == 'varians-layout-cache':
        # An independent ALTO/PAGE is not a synchronization. Its addition must
        # never replace or remove the witness's existing IIIF working images.
        return _layout_only_manifest_pages(cache, manifest, witness_id, selection,
                                           page_links, ocr_links, project_root,
                                           selected_mode=(selected_keys is not None))
    allowed = {canvas_key(page) for _, page in selection}
    resolutions = resolve_pages(source, manifest, allowed, page_links, ocr_links, project_root)
    lookup = {canvas_key(p): (index, p) for index, p in selection}
    assigned = set()
    result = []
    for i, page in enumerate(source):
        out = dict(page)
        match = resolutions[i]
        if match.key:
            original_index, mp = lookup[match.key]
            out['image'] = dict(mp['image'])
            out['label'] = str(mp.get('label') or page.get('label') or page.get('id') or '')
            out['iiif_canvas_key'] = match.key
            out['tei_surface_id'] = out.get('tei_surface_id') or default_surface_id(witness_id, original_index + 1)
            out['iiif_resolution'] = {'status': 'resolved', 'method': match.method, 'canvas': match.key}
            assigned.add(match.key)
        else:
            # Keep sync page+lines even when the image cannot be found; do not
            # carry an unrelated image from an earlier (positional) overlay.
            out['image'] = {'type': 'none', 'label': str(page.get('label') or page.get('id') or '')}
            out.pop('iiif_canvas_key', None)
            out['iiif_resolution'] = {'status': match.status, 'method': match.method,
                                      'candidates': list(match.candidates)}
        result.append(out)
    # Explicitly selected canvases without a synchronized page can still be
    # displayed as images; in an 'all' legacy manifest with existing sync
    # data, never materialize hundreds of superfluous physical pages.
    if selected_keys is not None or not source:
        for original_index, page in selection:
            key = canvas_key(page)
            if key not in assigned:
                # An unresolved synchronized page may be this canvas: do not
                # fabricate a second physical page for it automatically.
                if source and any(r.key is None for r in resolutions.values()):
                    continue
                result.append({'id': page['id'], 'label': page.get('label', ''),
                               'lines': [], 'image': dict(page['image']),
                               'iiif_canvas_key': key,
                               'tei_surface_id': default_surface_id(witness_id, original_index + 1),
                               'iiif_resolution': {'status': 'resolved', 'method': 'canvas_selection', 'canvas': key}})
    # Legacy PAGE/ALTO-only imports follow manifest order. Genuine JSON
    # synchronization always preserves the producer's original page order.
    is_alignment = (cache or {}).get('meta', {}).get('format') == 'tei-manuscript-alignment'
    if not is_alignment and source and all(r.key for r in resolutions.values()):
        rank = {canvas_key(p): j for j, p in enumerate(manifest.pages)}
        result.sort(key=lambda p: rank.get(p.get('iiif_canvas_key'), len(rank)))
    meta = dict((cache or {}).get('meta') or {})
    meta.update(iiif_manifest=manifest.source,
                iiif_presentation_version=manifest.presentation_version,
                iiif_selection_mode='selected' if selected_keys is not None else 'all')
    out = dict(cache or {})
    out['meta'], out['pages'] = meta, result
    return out
