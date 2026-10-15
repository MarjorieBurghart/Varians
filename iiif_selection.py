# -*- coding: utf-8 -*-
"""Conservative selection of IIIF canvases documented by PAGE or ALTO XML.

Never infer a mapping from ordinal position: IIIF manifests often include
covers, blank leaves or different ordering from the supplied OCR files.
Unmatched or ambiguous OCR pages are *not* downloaded in selective mode.
"""
from __future__ import annotations

from pathlib import Path
import re
import xml.etree.ElementTree as ET
from urllib.parse import urlsplit, unquote

from alto_import import parse_layout_file


def _stem(raw):
    name = Path(raw).name
    # 'f. 1r' is a folio label, not a file named 'f' with an extension.
    if Path(name).suffix.lower() in {'.jpg', '.jpeg', '.png', '.jp2', '.tif',
                                    '.tiff', '.webp', '.xml', '.alto'}:
        return Path(name).stem
    return name


def _norm(value):
    """Match normalized basenames only, without path/query or file extension."""
    raw = unquote(urlsplit(str(value or '')).path).replace('\\', '/')
    stem = _stem(raw)
    return re.sub(r'[^a-z0-9]+', '', stem.casefold())


def _folio(value):
    """Recognize a terminal recto/verso marker, e.g. 'Assisi541-test-1r'."""
    raw = unquote(urlsplit(str(value or '')).path).replace('\\', '/')
    stem = _stem(raw).casefold()
    found = re.search(r'(?:^|[^a-z0-9])(?:f(?:ol)?\.?\s*)?(\d{1,5})\s*([rv])$', stem)
    if found:
        return f'{int(found.group(1))}{found.group(2)}'
    return None


def _page_names(page):
    im = page.get('image') if isinstance(page.get('image'), dict) else {}
    names = [page.get('label'), im.get('label'), im.get('canvas'), im.get('image'), im.get('service')]
    return {_norm(v) for v in names if _norm(v)}, {_folio(v) for v in names if _folio(v)}


def _ocr_names(layout_page, label, path):
    names = [layout_page.get('alto_source_image'), label,
             layout_page.get('label'), Path(path).name]
    return {_norm(v) for v in names if _norm(v)}, {_folio(v) for v in names if _folio(v)}


def select_ocr_pages(manifest_pages, layout_files):
    """Return (indices, warnings) for unambiguous OCR→IIIF canvas matches.

    Every declared PAGE/ALTO is parsed (not merely counted). Each file may have
    multiple pages. An OCR page can match by exact normalized page or image
    basename, or by an unambiguous folio suffix (1r/1v) explicitly present in
    the metadata. Duplicate or conflicting matches are rejected. Indexes are
    zero-based in manifest order.
    """
    manifest_keys = [_page_names(page) for page in manifest_pages]
    proposed = set()
    warnings = []
    ocr_records = []
    for item in layout_files or ():
        path = Path(item.path)
        label = str(getattr(item, 'label', '') or '')
        try:
            parsed = parse_layout_file(path)
        except (OSError, ValueError, ET.ParseError) as exc:
            warnings.append(f'{path.name}: {exc}')
            continue
        for page in parsed.pages:
            ocr_records.append((path.name, *_ocr_names(page, label, path)))

    if not ocr_records:
        warnings.append('No ALTO/PAGE layout files supplied (no IIIF images selected)')
    # Never use the same ambiguous name as evidence for two different canvases.
    for filename, exact, folios in ocr_records:
        exact_matches = [i for i, (mk, mf) in enumerate(manifest_keys) if mk & exact]
        if len(exact_matches) == 1:
            proposed.add(exact_matches[0])
            continue
        if len(exact_matches) > 1:
            warnings.append(f'{filename}: multiple IIIF canvases have the same image/page name')
            continue
        folio_matches = [i for i, (mk, mf) in enumerate(manifest_keys) if mf & folios]
        if len(folio_matches) == 1:
            proposed.add(folio_matches[0])
        elif len(folio_matches) > 1:
            warnings.append(f'{filename}: ambiguous folio label in IIIF manifest')
        else:
            warnings.append(f'{filename}: no matching IIIF canvas (not downloaded)')
    return proposed, warnings
