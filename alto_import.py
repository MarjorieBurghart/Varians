# -*- coding: utf-8 -*-
"""Import et fusion de fichiers ALTO indépendants des synchronisations.

Varians accepte des fichiers ALTO comme ressource propre d'un témoin. Le module
ne dépend pas de Qt : il parse les XML, construit le cache de pages/lignes et
peut le fusionner avec un ancien JSON de synchronisation sans perdre les
``base_keys`` ni les autres métadonnées d'alignement.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import math
import json
import re
import xml.etree.ElementTree as ET


def _local(tag: str) -> str:
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _num(value, default=None):
    if value in (None, ''):
        return default
    try:
        f = float(value)
        return int(f) if f.is_integer() else f
    except (TypeError, ValueError):
        return default


def _safe_id(text: str, fallback: str) -> str:
    text = (text or '').strip()
    text = re.sub(r'[^A-Za-z0-9_.:-]+', '-', text).strip('-')
    return text or fallback


def _norm(text: str | None) -> str:
    text = (text or '').strip().lower()
    text = Path(text).stem if text else ''
    return re.sub(r'[^a-z0-9]+', '', text)


def _first_text(root: ET.Element, local_name: str) -> str:
    for el in root.iter():
        if _local(el.tag) == local_name and (el.text or '').strip():
            return (el.text or '').strip()
    return ''


def _line_text(line: ET.Element) -> str:
    pieces = []
    has_sp = False
    strings = []
    for child in line.iter():
        name = _local(child.tag)
        if name == 'SP':
            has_sp = True
            pieces.append(' ')
        elif name in {'String', 'HYP'}:
            content = child.get('CONTENT') or child.get('content') or ''
            if content:
                strings.append(content)
                pieces.append(content)
    if has_sp:
        return ''.join(pieces).strip()
    return ' '.join(strings).strip()


def _polygon_bbox(line: ET.Element):
    for el in line.iter():
        if _local(el.tag) != 'Polygon':
            continue
        raw = el.get('POINTS') or el.get('points') or ''
        pts=[]
        for token in raw.replace(';', ' ').split():
            if ',' not in token:
                continue
            try:
                x,y=token.split(',',1); pts.append((float(x),float(y)))
            except ValueError:
                continue
        if pts:
            xs=[x for x,_ in pts]; ys=[y for _,y in pts]
            x0,y0=min(xs),min(ys); x1,y1=max(xs),max(ys)
            return x0,y0,max(1,x1-x0),max(1,y1-y0)
    return None


def _points(raw: str) -> list[list[float]]:
    """PAGE/ALTO polygon coordinates, never approximated to a rectangle."""
    result = []
    for token in (raw or '').replace(';', ' ').split():
        try:
            x, y = map(float, token.split(',', 1))
            if math.isfinite(x) and math.isfinite(y):
                result.append([x, y])
        except (ValueError, TypeError):
            continue
    return result


def _bbox_from_points(points):
    if not points:
        return None
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return {'hpos': min(xs), 'vpos': min(ys),
            'width': max(1, max(xs)-min(xs)),
            'height': max(1, max(ys)-min(ys))}


def _child(element, name):
    return next((x for x in element if _local(x.tag) == name), None)


def parse_page_file(path: str | Path) -> AltoParsedFile:
    """PAGE XML (PcGts, with or without namespace): polygons + optional baselines.

    The line's direct TextEquiv is authoritative; word-level transcriptions are
    concatenated only when a line transcription is absent. Region order is
    preserved and alternate TextEquiv readings are not silently conflated.
    """
    path = Path(path).expanduser().resolve()
    root = ET.parse(path).getroot()
    if _local(root.tag) != 'PcGts':
        raise ValueError(f'Not a PAGE XML document: {path}')
    pages = []
    for page_index, page in enumerate((x for x in root.iter() if _local(x.tag) == 'Page'), 1):
        pid = _safe_id(page.get('id') or '', f'{path.stem}-{page_index:04d}')
        source_image = page.get('imageFilename') or ''
        lines = []
        for region in page.iter():
            if _local(region.tag) != 'TextLine':
                continue
            line_no = len(lines) + 1
            lid = region.get('id') or f'{pid}-line-{line_no:04d}'
            coords = _child(region, 'Coords')
            polygon = _points(coords.get('points', '') if coords is not None else '')
            bbox = _bbox_from_points(polygon)
            if bbox is None:
                # A PAGE line without a polygon is retained and diagnosed, but
                # cannot be visualized accurately until its geometry is supplied.
                bbox = {'hpos': 0, 'vpos': 0, 'width': 1, 'height': 1}
            equivs = [x for x in region if _local(x.tag) == 'TextEquiv']
            equivs.sort(key=lambda e: int(e.get('index') or 0))
            text = ''
            for equiv in equivs:
                uni = _child(equiv, 'Unicode')
                if uni is not None and uni.text is not None:
                    text = uni.text
                    break
                plain = _child(equiv, 'PlainText')
                if plain is not None and plain.text is not None:
                    text = plain.text
                    break
            if not text:
                words = []
                for word in region.iter():
                    if _local(word.tag) != 'Word':
                        continue
                    we = _child(word, 'TextEquiv')
                    wu = _child(we, 'Unicode') if we is not None else None
                    if wu is not None and wu.text:
                        words.append(wu.text)
                text = ' '.join(words)
            row = {'line': line_no, 'alto_id': lid, 'alto': text,
                   'bbox': bbox, 'geometry_format': 'page'}
            if polygon:
                row['polygon'] = polygon
            baseline = _child(region, 'Baseline')
            if baseline is not None:
                bp = _points(baseline.get('points', ''))
                if bp:
                    row['baseline'] = bp
            lines.append(row)
        pages.append({'id': pid, 'alto_width': _num(page.get('imageWidth')),
                      'alto_height': _num(page.get('imageHeight')),
                      'alto_source_file': str(path), 'alto_source_image': source_image,
                      'label': Path(source_image).stem if source_image else path.stem,
                      'geometry_format': 'page', 'lines': lines})
    if not pages:
        raise ValueError(f'PAGE XML without Page: {path}')
    return AltoParsedFile(path, tuple(pages), pages[0]['alto_source_image'])


def parse_layout_file(path: str | Path) -> AltoParsedFile:
    """Auto-detect ALTO or PAGE independently for every witness and file."""
    root_tag = None
    for _event, root in ET.iterparse(path, events=('start',)):
        root_tag = _local(root.tag)
        break
    if root_tag == 'PcGts':
        return parse_page_file(path)
    if root_tag.lower() == 'alto':
        return parse_alto_file(path)
    raise ValueError(f'Unsupported layout XML root {root_tag!r}: {path}')


@dataclass(frozen=True)
class AltoParsedFile:
    path: Path
    pages: tuple[dict, ...]
    source_image: str = ''


def parse_alto_file(path: str | Path) -> AltoParsedFile:
    """Parse les structures ALTO courantes (2/3/4, namespace indifférent)."""
    path = Path(path).expanduser().resolve()
    root = ET.parse(path).getroot()
    source_image = _first_text(root, 'fileName')
    pages = []
    page_index = 0
    for page in root.iter():
        if _local(page.tag) != 'Page':
            continue
        page_index += 1
        pid = _safe_id(page.get('ID') or page.get('id') or '', f'{path.stem}-{page_index:04d}')
        width = _num(page.get('WIDTH') or page.get('width'))
        height = _num(page.get('HEIGHT') or page.get('height'))
        lines = []
        line_no = 0
        for line in page.iter():
            if _local(line.tag) != 'TextLine':
                continue
            line_no += 1
            lid = line.get('ID') or line.get('id') or f'{pid}-line-{line_no:04d}'
            hpos = _num(line.get('HPOS') or line.get('hpos'))
            vpos = _num(line.get('VPOS') or line.get('vpos'))
            lwidth = _num(line.get('WIDTH') or line.get('width'))
            lheight = _num(line.get('HEIGHT') or line.get('height'))
            if None in (hpos, vpos, lwidth, lheight):
                poly = _polygon_bbox(line)
                if poly is not None:
                    hpos, vpos, lwidth, lheight = poly
            hpos = 0 if hpos is None else hpos
            vpos = 0 if vpos is None else vpos
            lwidth = 1 if lwidth is None else lwidth
            lheight = 1 if lheight is None else lheight
            polygon = []
            for descendant in line.iter():
                if _local(descendant.tag) == 'Polygon':
                    polygon = _points(descendant.get('POINTS') or descendant.get('points') or '')
                    break
            entry = {
                'line': line_no,
                'alto_id': lid,
                'alto': _line_text(line),
                'bbox': {
                    'hpos': hpos or 0, 'vpos': vpos or 0,
                    'width': lwidth or 1, 'height': lheight or 1,
                },
            }
            if polygon:
                entry['polygon'] = polygon
            lines.append(entry)
        pages.append({
            'id': pid,
            'alto_width': width,
            'alto_height': height,
            'alto_source_file': str(path),
            'alto_source_image': source_image,
            'label': Path(source_image).stem if source_image else path.stem,
            'lines': lines,
        })
    if not pages:
        raise ValueError(f'ALTO sans élément Page : {path}')
    return AltoParsedFile(path, tuple(pages), source_image)


def build_alto_cache(paths, witness_id: str, role: str = 'secondary') -> dict:
    pages = []
    for raw in paths or []:
        parsed = parse_layout_file(raw)
        pages.extend(dict(p) for p in parsed.pages)
    return {
        'meta': {
            'format': 'varians-layout-cache',
            'format_version': 2,
            'witness': witness_id,
            'role': role,
        },
        'pages': pages,
    }


def _page_keys(page: dict) -> set[str]:
    out = set()
    for value in (
        page.get('id'), page.get('label'), page.get('alto_source_image'),
        page.get('alto_source_file'),
    ):
        n = _norm(str(value)) if value else ''
        if n:
            out.add(n)
    image = page.get('image') if isinstance(page.get('image'), dict) else {}
    legacy = page.get('iiif') if isinstance(page.get('iiif'), dict) else {}
    for value in (image.get('label'), image.get('path'), legacy.get('label')):
        n = _norm(str(value)) if value else ''
        if n:
            out.add(n)
    return out


_UUID_LINE_ID_RE = re.compile(
    r"^(?:line_|id_)([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$",
    re.IGNORECASE,
)


def _line_uuid(line: dict) -> str | None:
    """Stable PERO line identity shared by ALTO ``line_UUID`` and PAGE ``id_UUID``.

    Only a well-formed UUID after an explicit known prefix is interpreted;
    unrelated identifiers must not be conflated through fuzzy matching.
    """
    match = _UUID_LINE_ID_RE.fullmatch(str(line.get('alto_id') or ''))
    return match.group(1).lower() if match else None


def _merge_lines(existing_lines: list[dict], imported_lines: list[dict]) -> list[dict]:
    """Replace source geometry/text, preserving synchronizations by stable identity.

    Exact and shared PERO UUID matches are resolved *before* the ordinal legacy
    fallback, so a changed PAGE reading order cannot attach the original
    ``base_keys`` to an unrelated line. Ambiguous duplicate IDs are excluded.
    """
    by_id = {}
    by_uuid = {}
    duplicate_ids = set()
    duplicate_uuids = set()
    for old in existing_lines:
        aid = str(old.get('alto_id') or '')
        if aid:
            if aid in by_id:
                duplicate_ids.add(aid)
            else:
                by_id[aid] = old
        uuid = _line_uuid(old)
        if uuid:
            if uuid in by_uuid:
                duplicate_uuids.add(uuid)
            else:
                by_uuid[uuid] = old
    for aid in duplicate_ids:
        by_id.pop(aid, None)
    for uuid in duplicate_uuids:
        by_uuid.pop(uuid, None)

    matches = [None] * len(imported_lines)
    used = set()
    # First assign uniquely identified lines, regardless of their new order.
    for i, fresh in enumerate(imported_lines):
        aid = str(fresh.get('alto_id') or '')
        old = by_id.get(aid) if aid else None
        if old is None:
            uuid = _line_uuid(fresh)
            old = by_uuid.get(uuid) if uuid else None
        if old is not None and id(old) not in used:
            matches[i] = old
            used.add(id(old))

    # Legacy imports without matching identifiers retain their ordinal fallback,
    # but never consume a row reserved for a uniquely matched line.
    for i, old in enumerate(matches):
        if old is None and i < len(existing_lines):
            candidate = existing_lines[i]
            # A different stable UUID is evidence of a different line, not
            # permission to silently borrow its editorial synchronization.
            previous_uuid = _line_uuid(candidate)
            incoming_uuid = _line_uuid(imported_lines[i])
            if (id(candidate) not in used and
                not (previous_uuid and incoming_uuid and previous_uuid != incoming_uuid)):
                matches[i] = candidate
                used.add(id(candidate))

    merged = []
    for fresh, old in zip(imported_lines, matches):
        row = dict(old or {})
        preserved_line = row.get('line')
        for key in ('polygon', 'baseline', 'geometry_format'):
            row.pop(key, None)
        row.update(fresh)
        if preserved_line is not None:
            row['line'] = preserved_line
        merged.append(row)
    # Unmatched old lines remain inspectable for diagnosing changed segmentation.
    for old in existing_lines:
        if id(old) not in used:
            merged.append(dict(old))
    return merged


def overlay_alto(existing: dict, imported: dict, *, strict_no_ordinal=False) -> dict:
    """Fusionne ALTO et cache existant en préservant les synchronisations.

    Association des pages : identifiants/libellés/noms de fichiers lorsqu'ils
    concordent sans ambiguïté, puis ordre physique pour les pages restantes.
    """
    existing = existing or {'pages': []}
    imported = imported or {'pages': []}
    out = dict(existing)
    old_pages = [dict(p) for p in (existing.get('pages') or [])]
    new_pages = [dict(p) for p in (imported.get('pages') or [])]
    if not old_pages:
        out['pages'] = new_pages
        meta = dict(out.get('meta') or {})
        meta.update(imported.get('meta') or {})
        out['meta'] = meta
        return out
    if not new_pages:
        return existing

    pairs = {}
    used_new = set()
    # D'abord les correspondances nominales uniques.
    new_keys = [_page_keys(p) for p in new_pages]
    for oi, old in enumerate(old_pages):
        ok = _page_keys(old)
        candidates = [ni for ni, nk in enumerate(new_keys) if ni not in used_new and ok.intersection(nk)]
        if len(candidates) == 1:
            pairs[oi] = candidates[0]
            used_new.add(candidates[0])
    # Legacy positional fallback is forbidden when the user explicitly maps
    # IIIF canvases to local OCR: order is not evidence of identity.
    if not strict_no_ordinal:
        remaining_new = [i for i in range(len(new_pages)) if i not in used_new]
        cursor = 0
        for oi in range(len(old_pages)):
            if oi in pairs:
                continue
            if cursor < len(remaining_new):
                pairs[oi] = remaining_new[cursor]
                used_new.add(remaining_new[cursor])
                cursor += 1

    merged_pages = []
    for oi, old in enumerate(old_pages):
        if oi not in pairs:
            merged_pages.append(old)
            continue
        fresh = new_pages[pairs[oi]]
        page = dict(old)
        # Conserver l'id de page existant : les base_keys peuvent le référencer.
        old_id = page.get('id')
        for key in ('alto_width', 'alto_height', 'alto_source_file', 'alto_source_image', 'geometry_format'):
            if fresh.get(key) is not None:
                page[key] = fresh.get(key)
        if not page.get('label') and fresh.get('label'):
            page['label'] = fresh['label']
        page['lines'] = _merge_lines(list(old.get('lines') or []), list(fresh.get('lines') or []))
        if old_id is not None:
            page['id'] = old_id
        merged_pages.append(page)
    for ni, fresh in enumerate(new_pages):
        if ni not in used_new:
            if strict_no_ordinal and old_pages:
                # A detached OCR page must not become an independent physical
                # leaf if it later resolves to the same IIIF canvas as a JSON
                # synchronization page. The resolver handles the safe merge.
                fresh['_ocr_unmerged'] = True
            merged_pages.append(fresh)
    out['pages'] = merged_pages
    meta = dict(out.get('meta') or {})
    meta['alto_source'] = 'files'
    out['meta'] = meta
    return out


def source_signature(paths) -> list[dict]:
    sig = []
    for raw in paths or []:
        p = Path(raw).expanduser().resolve()
        st = p.stat()
        sig.append({'path': str(p), 'size': st.st_size, 'mtime_ns': st.st_mtime_ns})
    return sig


def cache_path(project_root: str | Path, witness_id: str) -> Path:
    safe = re.sub(r'[^A-Za-z0-9_.-]+', '_', witness_id or 'witness')
    return Path(project_root).resolve() / '.varians' / 'alto' / f'{safe}.json'


def load_or_build_cache(project_root: str | Path, witness_id: str, role: str, paths) -> dict:
    paths = [Path(x).expanduser().resolve() for x in paths or []]
    if not paths:
        return {'meta': {'witness': witness_id, 'role': role}, 'pages': []}
    current = source_signature(paths)
    cp = cache_path(project_root, witness_id)
    if cp.is_file():
        try:
            data = json.loads(cp.read_text(encoding='utf-8'))
            if (data.get('_source_signature') == current and
                (data.get('cache', {}).get('meta') or {}).get('format_version') == 2):
                return data.get('cache') or {'pages': []}
        except Exception:
            pass
    cache = build_alto_cache(paths, witness_id, role)
    payload = {'_source_signature': current, 'cache': cache}
    try:
        cp.parent.mkdir(parents=True, exist_ok=True)
        cp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding='utf-8')
    except OSError:
        # Un projet en lecture seule reste consultable ; le cache n'est qu'une
        # optimisation et peut toujours être reconstruit depuis les XML ALTO.
        pass
    return cache


def apply_witness_alto_policy(cache: dict, source_type: str = 'auto', source_files=(),
                              project_root: str | Path | None = None,
                              witness_id: str = 'witness', role: str = 'secondary',
                              strict_no_ordinal: bool = False) -> dict:
    kind = (source_type or 'auto').strip().lower()
    if kind == 'auto':
        return cache
    if kind != 'files' or project_root is None:
        return cache
    imported = load_or_build_cache(project_root, witness_id, role, source_files)
    return overlay_alto(cache, imported, strict_no_ordinal=strict_no_ordinal)
