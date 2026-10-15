# -*- coding: utf-8 -*-
"""IIIF working copies: opt-in local, incremental, atomic, and export-independent.

Network access is ONLY performed by download_witness_copy(), never by opening
an offline project, applying a cache, or generating the web viewer.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import time
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from iiif_manifest import cache_path, read_cache

MAX_IMAGE_BYTES = 250 * 1024 * 1024


def _safe_id(wid: str) -> str:
    return re.sub(r'[^A-Za-z0-9_.-]+', '_', wid).strip('._') or 'witness'


def store_dir(root: str | Path, wid: str) -> Path:
    return Path(root).resolve() / 'iiif' / 'local' / _safe_id(wid)


def index_path(root: str | Path, wid: str) -> Path:
    return store_dir(root, wid) / 'index.json'


def remote_key(image: dict) -> str:
    return hashlib.sha256(json.dumps({key: image.get(key) for key in
        ('canvas', 'service', 'image', 'iiif_version', 'width', 'height')},
        sort_keys=True, ensure_ascii=False).encode('utf-8')).hexdigest()


def _request_url(image: dict) -> str:
    service = str(image.get('service') or '').rstrip('/')
    if service:
        ver = int(image.get('iiif_version') or 2)
        if ver == 1:
            return f'{service}/full/full/0/native.jpg'
        return f'{service}/full/{"max" if ver == 3 else "full"}/0/default.jpg'
    return str(image.get('image') or image.get('url') or '')


def _read_index(root: str | Path, wid: str) -> dict:
    try:
        idx = json.loads(index_path(root, wid).read_text(encoding='utf-8'))
        if idx.get('format') == 'varians-iiif-local-1':
            return idx.get('images') or {}
    except (OSError, ValueError, AttributeError):
        pass
    return {}


def _valid_entry(root: str | Path, wid: str, image: dict, entries: dict) -> Path | None:
    entry = entries.get(remote_key(image))
    if not isinstance(entry, dict):
        # A reloaded manifest may change image dimensions/quality while
        # retaining the same Image API source. Reuse only a UNIQUE identical
        # download source; never use a manifest/selection ordinal as evidence.
        source = _request_url(image)
        matches = [e for e in entries.values()
                   if isinstance(e, dict) and e.get('source') == source]
        if len(matches) != 1:
            return None
        entry = matches[0]
    file_name = entry.get('file', '')
    if not re.fullmatch(r'[0-9a-f]{32}\.([a-z0-9]+)', file_name):
        return None
    path = store_dir(root, wid) / file_name
    if path.is_file() and path.stat().st_size and entry.get('source') == _request_url(image):
        return path
    return None


def local_image_path(root: str | Path, wid: str, image: dict) -> Path | None:
    return _valid_entry(root, wid, image, _read_index(root, wid))


def apply_working_copy(cache: dict, root: str | Path, wid: str) -> dict:
    """Replace only available IIIF images with local files; preserve geometry.

    Incomplete offline copies keep their remote URLs for online fallback. No
    network traffic occurs here. Original IIIF metadata stays in ``remote_iiif``.
    """
    entries = _read_index(root, wid)
    out = dict(cache)
    pages = []
    for page in cache.get('pages', []) or []:
        p = dict(page)
        image = p.get('image')
        if isinstance(image, dict) and image.get('type') == 'iiif':
            path = _valid_entry(root, wid, image, entries)
            if path:
                p['image'] = {'type': 'file', 'path': str(path),
                              'width': image.get('width'), 'height': image.get('height'),
                              'label': image.get('label', page.get('label', '')),
                              'remote_iiif': image}
        pages.append(p)
    out['pages'] = pages
    return out


def _image_extension(header: bytes, content_type: str) -> str:
    if header.startswith(b'\xff\xd8\xff'):
        return 'jpg'
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png'
    if header[:4] in (b'II*\x00', b'MM\x00*'):
        return 'tif'
    if header.startswith(b'RIFF') and header[8:12] == b'WEBP':
        return 'webp'
    if header.startswith(b'GIF8'):
        return 'gif'
    raise ValueError(f'Unsupported image response (type={content_type})')


def _fetch_image(url: str, destination_without_extension: Path) -> Path:
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https') or not parsed.netloc:
        raise ValueError('IIIF image URL must use HTTP(S)')
    req = Request(url, headers={'User-Agent': 'Varians/0.8.5 (IIIF local working copy)',
                                'Accept': 'image/jpeg,image/png,image/tiff,image/webp,image/gif'})
    part = destination_without_extension.with_suffix('.part')
    try:
        with urlopen(req, timeout=25) as reply, part.open('wb') as stream:
            content_type = reply.headers.get('Content-Type', '')
            if 'text/html' in content_type or 'application/json' in content_type:
                raise ValueError(f'Not an image: {content_type}')
            total = 0
            while True:
                chunk = reply.read(512 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_IMAGE_BYTES:
                    raise ValueError('IIIF image exceeds the 250 MB per-image safety limit')
                stream.write(chunk)
        if part.stat().st_size == 0:
            raise ValueError('Empty IIIF image')
        with part.open('rb') as stream:
            extension = _image_extension(stream.read(20), content_type)
        dest = destination_without_extension.with_suffix('.' + extension)
        os.replace(part, dest)
        return dest
    finally:
        if part.exists():
            part.unlink()


def plan_witness_copy(root: str | Path, wid: str, manifest_url: str, *,
                      scope='all', layout_files=(), selection_mode='all',
                      selected_canvases=(), ocr_links=()) -> dict:
    """Build an offline manifest-based plan with no network access.

    ``scope='ocr'`` only selects confidently associated PAGE/ALTO canvases;
    absent OCR data never silently broadens to the entire manuscript.
    """
    manifest = read_cache(cache_path(root, wid), manifest_url)
    if manifest is None:
        raise FileNotFoundError(f'No cached IIIF manifest for witness {wid}')
    if scope not in ('all', 'ocr'):
        raise ValueError(f'Unknown IIIF download scope: {scope}')
    pages = list(manifest.pages)
    warnings = []
    if scope == 'ocr':
        from iiif_selection import select_ocr_pages
        layouts_to_match = list(layout_files or ())
        if selection_mode == 'selected':
            # Manual links are authoritative. Do not produce a misleading
            # 'unmatched OCR' warning for their deliberately unrelated names.
            linked_sources = {str(Path(path).expanduser().resolve()) for path, _ in (ocr_links or ())}
            layouts_to_match = [item for item in layouts_to_match
                                if str(Path(item.path).expanduser().resolve()) not in linked_sources]
        if layouts_to_match:
            selected, warnings = select_ocr_pages(pages, layouts_to_match)
        else:
            selected, warnings = set(), ([] if ocr_links else
                   ['No ALTO/PAGE layout files supplied (no IIIF images selected)'])
    else:
        selected = set(range(len(pages)))
    from iiif_page_selection import selected_manifest_pages, canvas_key
    allowed = {i for i, _ in selected_manifest_pages(manifest, selected_canvases, selection_mode)}
    if selection_mode == 'selected':
        linked = {canvas for _, canvas in (ocr_links or ())}
        if scope == 'ocr':
            selected = (selected | {i for i, p in enumerate(pages) if canvas_key(p) in linked}) & allowed
        else:
            selected = allowed
        warnings = [w for w in warnings if w] if scope == 'ocr' else []
    entries = _read_index(root, wid)
    cached = sum(bool(_valid_entry(root, wid, pages[i]['image'], entries)) for i in selected)
    return {'pages': pages, 'indices': sorted(selected), 'warnings': warnings,
            'total_pages': len(pages), 'total': len(selected), 'cached': cached,
            'pending': len(selected) - cached, 'excluded': len(pages) - len(selected)}


def download_witness_copy(root: str | Path, wid: str, manifest_url: str,
                          *, progress=None, force=False, scope='all',
                          layout_files=(), selection_mode='all', selected_canvases=(), ocr_links=(),
                          cancel_event=None, pause_event=None) -> dict:
    """Save selected IIIF canvas images; resume and report all failures.

    Background workers may supply ``cancel_event`` and ``pause_event`` (set
    means paused). Cancellation applies between files; an in-flight network
    operation has a 25 s timeout. Each completed file is indexed atomically.
    """
    plan = plan_witness_copy(root, wid, manifest_url, scope=scope,
                             layout_files=layout_files, selection_mode=selection_mode,
                             selected_canvases=selected_canvases, ocr_links=ocr_links)
    directory = store_dir(root, wid)
    directory.mkdir(parents=True, exist_ok=True)
    entries = _read_index(root, wid)
    selection = plan['indices']
    total = len(selection)
    results = {'downloaded': 0, 'skipped': 0, 'failed': [], 'cancelled': False,
               'total': total, 'total_pages': plan['total_pages'],
               'excluded': plan['excluded'], 'warnings': plan['warnings']}
    for done, page_index in enumerate(selection):
        while pause_event is not None and pause_event.is_set():
            if cancel_event is not None and cancel_event.is_set():
                results['cancelled'] = True
                return results
            time.sleep(0.1)
        if cancel_event is not None and cancel_event.is_set():
            results['cancelled'] = True
            break
        page = plan['pages'][page_index]
        if progress is not None and progress(done, total, page.get('label', '')) is False:
            results['cancelled'] = True
            break
        image = page.get('image', {})
        source = _request_url(image)
        if not source:
            results['failed'].append((page_index + 1, 'No image URL'))
            continue
        if not force and _valid_entry(root, wid, image, entries):
            results['skipped'] += 1
            continue
        key = remote_key(image)
        stem = hashlib.md5(key.encode('ascii')).hexdigest()
        try:
            dest = _fetch_image(source, directory / stem)
            entries[key] = {'file': dest.name, 'source': source}
            # Make each successful download durable before beginning the next.
            temp = index_path(root, wid).with_suffix('.json.tmp')
            temp.write_text(json.dumps({'format': 'varians-iiif-local-1',
                           'images': entries}, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, index_path(root, wid))
            results['downloaded'] += 1
        except Exception as exc:
            results['failed'].append((page_index + 1, str(exc)))
    if progress is not None and not results['cancelled']:
        progress(total, total, '')
    return results
