# -*- coding: utf-8 -*-
"""V0.8.5.8: opt-in, conservative TEI scaffold from the pivot witness.

No positional links between OCR, sync pages and IIIF canvases. No Qt dependency.
Existing TEI content and synchronization JSON are never modified in-place.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import json
import os
import re
import shutil
import tempfile
from datetime import datetime
import xml.etree.ElementTree as ET

from alto_import import parse_layout_file
from iiif_page_selection import canvas_key, exact_image_stem, propose_exact_ocr_links
from tei_facsimile import (project_facsimile_pages, FacsimilePage, sync_facsimile_text,
                           default_surface_id, TEI_NS, XML_NS, valid_xml_id)


@dataclass(frozen=True)
class PivotPage:
    label: str
    surface_id: str
    line_count: int
    evidence: str


@dataclass
class PivotScaffoldPlan:
    witness_id: str
    pages: list[PivotPage] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    missing_surfaces: list[FacsimilePage] = field(default_factory=list)

    @property
    def line_count(self):
        return sum(p.line_count for p in self.pages)


def _resolve(root: Path, value):
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def _source_names(page):
    image = page.get('image') or {}
    iiif = page.get('iiif') or {}
    return {name for v in (page.get('label'), page.get('image_name'),
                             page.get('alto_source_image'), page.get('alto_source_file'),
                             page.get('id'), image.get('path'), image.get('label'),
                             iiif.get('label'))
            if (name := exact_image_stem(v))}


def _unique_name_match(surface, possible, *, explicit=None):
    """Match only by exact image filename / exact folio label, never by ordinal."""
    names = {exact_image_stem(surface.label), exact_image_stem(surface.graphic_url)} - {''}
    # Images imported by Varians's own "copy" mode are stored as
    # images/<witness>/0001_original-name.jpg. Strip *only* that known
    # transport prefix, never infer equivalence from its numeric value.
    filename = Path(str(surface.graphic_url).replace('\\', '/')).name
    if re.fullmatch(r'\d{4}_.+', filename) and '/images/' in ('/' + str(surface.graphic_url).replace('\\', '/')):
        names.add(exact_image_stem(filename[5:]))
    candidates = []
    for row in possible:
        # Explicit source-image metadata is stronger than the XML filename.
        # If it contradicts the image/folio we are about to associate, an
        # incidental filename or page ID match must never override it.
        declared = exact_image_stem(row.get('alto_source_image') or row.get('image_name'))
        if declared and declared not in names:
            continue
        if names & _source_names(row):
            candidates.append(row)
    return candidates[0] if len(candidates) == 1 else None


def _load_sync_pages(witness, root, warnings):
    raw = getattr(witness, 'alignment', None)
    if not raw:
        return []
    try:
        path = _resolve(root, raw)
        data = json.loads(path.read_text(encoding='utf-8-sig'))
        pages = data.get('pages') or []
        if not isinstance(pages, list):
            raise ValueError('pages is not a list')
        return [x for x in pages if isinstance(x, dict)]
    except (OSError, ValueError, TypeError) as exc:
        warnings.append(f'Synchronisation illisible : {exc}')
        return []



def _synced_line_count(page, label: str, warnings: list[str]) -> tuple[int, str]:
    """Count *documented* physical rows, not presumed lines 1..N.

    Varians-Synchro exports an extract of the physical page. For example,
    the first page of a study may have lines numbered 41..68. Those 28
    physical rows are meaningful, but do not prove that earlier lines 1..40
    were transcribed or that the source covers the entire folio.

    Reject duplicated/invalid line identities rather than silently inventing
    or collapsing them. A gap changes the exhaustiveness warning, *not* the
    number of line markers generated for the documented rows.
    """
    rows = page.get('lines')
    if not isinstance(rows, list):
        warnings.append(f'{label} : liste de lignes JSON invalide ; aucun lb généré')
        return 0, 'JSON invalide'
    if not rows:
        warnings.append(f'{label} : aucune ligne décrite dans le JSON (page conservée)')
        return 0, 'JSON sans lignes'
    if not all(isinstance(row, dict) for row in rows):
        warnings.append(f'{label} : lignes JSON invalides ; aucun lb généré')
        return 0, 'JSON invalide'
    numbers = [row.get('line') for row in rows]
    if not all(type(num) is int and num > 0 for num in numbers):
        warnings.append(f'{label} : numéros de lignes JSON invalides ; aucun lb généré')
        return 0, 'JSON invalide'
    if len(set(numbers)) != len(numbers):
        warnings.append(f'{label} : numéros de lignes JSON dupliqués ; aucun lb généré')
        return 0, 'JSON ambigu'
    # Do not require min(numbers) == 1: the synchronization can start in the
    # middle of a physical folio. Never fill gaps by fabricating extra <lb/>.
    continuous = sorted(numbers) == list(range(min(numbers), max(numbers) + 1))
    if min(numbers) > 1 or not continuous:
        warnings.append(f'{label} : extrait JSON de {len(rows)} lignes physiques '
                        f'(numéros {min(numbers)}–{max(numbers)}) ; '
                        'exhaustivité du folio à vérifier, lignes absentes non inventées')
        return len(rows), 'JSON partiel'
    warnings.append(f'{label} : exhaustivité des lignes JSON à vérifier')
    return len(rows), 'JSON'


def build_pivot_plan(witnesses, base_witness: str, root, edition_path) -> PivotScaffoldPlan:
    """Map physical pivot pages to their *existing* TEI surface IDs.

    Layout rows have precedence as the complete physical line inventory. A
    sync-only count is a documented lower bound (it may omit unaligned lines).
    Ambiguous page links yield no line markers, not speculative markers.
    """
    root = Path(root).resolve()
    wid = str(base_witness or '').strip()
    if not valid_xml_id(wid):
        raise ValueError('Invalid pivot witness xml:id')
    witness = next((w for w in witnesses if str(w.id) == wid), None)
    if witness is None:
        raise ValueError('Pivot witness not found in project')
    plan = PivotScaffoldPlan(wid)
    surfaces = [p for p in project_facsimile_pages([witness], root, edition_path)
                if p.witness_id == wid]
    sync_pages = _load_sync_pages(witness, root, plan.warnings)
    layout_rows = []
    layouts = list(getattr(witness, 'alto_files', ()) or ())
    for item in layouts:
        try:
            path = _resolve(root, item.path)
            parsed = parse_layout_file(path)
            for page in parsed.pages:
                layout_rows.append(dict(page, _layout_path=str(path)))
        except (OSError, ET.ParseError, ValueError) as exc:
            plan.warnings.append(f'OCR illisible : {getattr(item,"path","")} : {exc}')

    layout_by_surface = {}
    sync_by_surface = {}
    source_type = getattr(witness, 'image_source_type', 'auto')
    if source_type == 'auto' and not surfaces and sync_pages:
        # A historical Varians-Synchro JSON may itself carry a trusted IIIF
        # image URL. Make *only its listed pages* eligible for opt-in creation
        # of facsimile surfaces: no manifest enumeration and no guessed files.
        for i, page in enumerate(sync_pages, 1):
            remote = page.get('iiif') if isinstance(page.get('iiif'), dict) else {}
            img = page.get('image') if isinstance(page.get('image'), dict) else {}
            graphic = str(remote.get('image') or img.get('image') or '').strip()
            if img.get('type') == 'file' and img.get('path'):
                candidate = _resolve(root, img.get('path'))
                graphic = str(candidate) if candidate.is_file() else ''
            if not graphic:
                plan.warnings.append(f'Page JSON {page.get("id")}: aucune image fiable pour <surface>')
                continue
            sid = str(page.get('tei_surface_id') or default_surface_id(wid, i)).strip()
            if not valid_xml_id(sid):
                plan.warnings.append(f'Page JSON {page.get("id")}: surface id invalide')
                continue
            label = str(page.get('label') or remote.get('label') or
                        page.get('image_name') or page.get('id') or i).strip()
            facet = FacsimilePage(wid, sid, label, graphic)
            surfaces.append(facet)
            plan.missing_surfaces.append(facet)
            sync_by_surface[sid] = page
    if source_type == 'iiif':
        from iiif_manifest import cache_path, read_cache
        from iiif_resolution import resolve_pages
        manifest = read_cache(cache_path(root, wid), getattr(witness, 'image_source_value', None))
        if manifest:
            sid_by_canvas = {canvas_key(page): default_surface_id(wid, i+1)
                             for i, page in enumerate(manifest.pages)}
            try:
                resolutions = resolve_pages(sync_pages, manifest,
                       selected_keys=set(sid_by_canvas),
                       explicit_links=getattr(witness, 'iiif_page_links', ()))
                for index, match in resolutions.items():
                    if match.key and match.key in sid_by_canvas:
                        sync_by_surface[sid_by_canvas[match.key]] = sync_pages[index]
                    elif match.status == 'ambiguous':
                        plan.warnings.append(f'Canvas ambigu pour page JSON : {sync_pages[index].get("id")}')
            except ValueError as exc:
                plan.warnings.append(f'Liens IIIF invalides : {exc}')
            # Explicit OCR/canvas associations already curated by the editor.
            explicit = {}
            for path, canvas in getattr(witness, 'iiif_ocr_links', ()) or ():
                key = str(_resolve(root, path))
                explicit.setdefault(canvas, set()).add(key)
            try:
                suggested, problems = propose_exact_ocr_links(manifest, layouts,
                                               getattr(witness, 'iiif_ocr_links', ()))
                plan.warnings.extend(problems)
            except (OSError, ValueError) as exc:
                suggested = {}
                plan.warnings.append(str(exc))
            for canvas, path in suggested.items():
                explicit.setdefault(canvas, set()).add(str(_resolve(root, path)))
            rows_by_path = {}
            for row in layout_rows:
                rows_by_path.setdefault(row['_layout_path'], []).append(row)
            for canvas, paths in explicit.items():
                sid = sid_by_canvas.get(canvas)
                if not sid or len(paths) != 1:
                    if len(paths) > 1:
                        plan.warnings.append(f'Plusieurs OCR pour canvas {canvas}')
                    continue
                rows = rows_by_path.get(next(iter(paths)), [])
                if len(rows) == 1:
                    layout_by_surface[sid] = rows[0]
                elif rows:
                    plan.warnings.append(f'OCR multipage non résolu pour {canvas}')
    else:
        # Local image witness: file-name or folio exact matching only.
        for surface in surfaces:
            found = _unique_name_match(surface, layout_rows)
            if found:
                layout_by_surface[surface.surface_id] = found
            found_sync = _unique_name_match(surface, sync_pages)
            if found_sync:
                sync_by_surface[surface.surface_id] = found_sync

    # The JSON can list additional pages not part of the project's selected
    # images. Never create a phantom <surface> or <pb/> for those; report the
    # missing association instead (especially pages with zero `lines`).
    associated_sync_ids = {id(page) for page in sync_by_surface.values()}
    for page in sync_pages:
        if id(page) not in associated_sync_ids:
            label = str(page.get('label') or page.get('id') or '?')
            plan.warnings.append(f'{label} : page du JSON sans image/surface '
                                 'associée dans le périmètre sélectionné ; aucun pb généré')

    seen = set()
    for surface in surfaces:
        if surface.surface_id in seen:
            plan.warnings.append(f'Surface dupliquée : {surface.surface_id}')
            continue
        seen.add(surface.surface_id)
        layout = layout_by_surface.get(surface.surface_id)
        synced = sync_by_surface.get(surface.surface_id)
        if layout is not None:
            count = len(layout.get('lines') or [])
            evidence = 'ALTO/PAGE'
            if synced is not None:
                synclines = len(synced.get('lines') or [])
                if synclines != count:
                    plan.warnings.append(f'{surface.label} : {count} lignes OCR, {synclines} lignes JSON ; OCR prioritaire')
        elif synced is not None:
            count, evidence = _synced_line_count(synced, surface.label, plan.warnings)
        else:
            count = 0
            evidence = 'image seule'
            plan.warnings.append(f'{surface.label} : aucune liste de lignes sûrement associée')
        plan.pages.append(PivotPage(surface.label, surface.surface_id, count, evidence))
    if not plan.pages:
        plan.warnings.append('Aucune surface du témoin pivot disponible (sélectionnez les images utiles).')
    return plan


def scaffold_is_empty(xml_text: str) -> bool:
    """Only minimal TEI body with a single empty p/ab is editable."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return False
    ns = f'{{{TEI_NS}}}' if root.tag.startswith('{') else ''
    if root.tag != ns + 'TEI':
        return False
    body = root.find(f'./{ns}text/{ns}body')
    if body is None or len(body) != 1 or body[0].tag not in (ns+'p', ns+'ab'):
        return False
    para = body[0]
    return not para.attrib and not len(para) and not (para.text or '').strip() and not (para.tail or '').strip()


def render_pivot_scaffold(xml_text: str, plan: PivotScaffoldPlan, *, include_lb=True):
    """Pure preview+render: never change a nonblank TEI, no implicit overwrite."""
    if not scaffold_is_empty(xml_text):
        raise ValueError('TEI_NOT_EMPTY')
    if not plan.pages:
        raise ValueError('PIVOT_HAS_NO_PAGES')
    if plan.missing_surfaces:
        xml_text, report = sync_facsimile_text(xml_text, plan.missing_surfaces)
        if report.conflicts:
            raise ValueError('SURFACE_CREATION_CONFLICT: ' + '; '.join(report.conflicts))
    tree = ET.fromstring(xml_text)
    all_ids = {node.get(f'{{{XML_NS}}}id') for node in tree.iter() if node.get(f'{{{XML_NS}}}id')}
    surfaces = {node.get(f'{{{XML_NS}}}id') for node in tree.iter()
                if node.tag.rsplit('}', 1)[-1] == 'surface'}
    if plan.witness_id not in all_ids:
        raise ValueError('PIVOT_WITNESS_NOT_DECLARED')
    if any(p.surface_id not in surfaces for p in plan.pages):
        raise ValueError('MISSING_TEI_SURFACE')
    import html
    wid = html.escape(plan.witness_id, quote=True)
    marks = []
    for page in plan.pages:
        label = html.escape(page.label, quote=True)
        sid = html.escape(page.surface_id, quote=True)
        marks.append(f'<pb n="{label}" edRef="#{wid}" facs="#{sid}"/>')
        if include_lb:
            marks.extend(f'<lb edRef="#{wid}"/>' for _ in range(page.line_count))
    # Retain the original declaration, xml-model, header, facsimile and all
    # other bytes. Restrict the exact replacement to within <body>.
    open_body = re.search(r'<(?P<pre>[\w.-]+:)?body(?:\s[^<>]*)?>', xml_text)
    if not open_body:
        raise ValueError('TEI_BODY_NOT_FOUND')
    pre = open_body.group('pre') or ''
    close_body = re.search(rf'</{re.escape(pre)}body\s*>', xml_text[open_body.end():])
    if not close_body:
        raise ValueError('TEI_BODY_NOT_FOUND')
    stop = open_body.end() + close_body.start()
    segment = xml_text[open_body.end():stop]
    p_re = re.compile(r'<(?P<pre>[\w.-]+:)?(?P<tag>p|ab)\s*(?:/>|>\s*</(?P=pre)?(?P=tag)\s*>)', re.S)
    matches = list(p_re.finditer(segment))
    if len(matches) != 1:
        raise ValueError('TEI_EMPTY_CONTAINER_NOT_FOUND')
    m = matches[0]
    pfx = m.group('pre') or ''
    local = m.group('tag')
    # prefix must be the body prefix in a genuine TEI document
    indentation = '    '
    content = '\n' + '\n'.join(indentation + x.replace('<', '<'+pfx, 1) for x in marks) + '\n  '
    replacement = f'<{pfx}{local}>{content}</{pfx}{local}>'
    return xml_text[:open_body.end()+m.start()] + replacement + xml_text[open_body.end()+m.end():]


def write_pivot_scaffold(edition_path, plan, *, include_lb=True):
    """Atomic, explicit file write with timestamped backup; caller confirms UI."""
    path = Path(edition_path).resolve()
    source = path.read_text(encoding='utf-8-sig')
    output = render_pivot_scaffold(source, plan, include_lb=include_lb)
    if source == output:
        return None
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup = path.with_name(path.name + '.pre-pivot-' + timestamp + '.bak')
    shutil.copy2(path, backup)
    temp = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', newline='\n', dir=path.parent,
                                         prefix='.varians-pivot-', suffix='.tmp', delete=False) as f:
            temp = Path(f.name)
            f.write(output)
        os.replace(temp, path)
    finally:
        if temp is not None and temp.exists():
            temp.unlink()
    return backup
