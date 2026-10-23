# -*- coding: utf-8 -*-
"""Générateur de viewer web générique piloté par project.xml."""
from __future__ import annotations

import copy
import json
import hashlib
import html
import sys
import shutil
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from project_config import load_project, has_line_synchronization
from folio_navigation import folios_for_witness
from web_viewer.assembled_document import load_assembled
from web_viewer.page_resolver import PageResolver
from web_viewer.tei_line_anchors import build_pivot_lb_index, build_segment_lb_index
from resource_state import primary_sync_line_count
from i18n import I18nManager
from image_sources import normalized_image_block, apply_witness_image_policy
from alto_import import apply_witness_alto_policy
from iiif_local import apply_working_copy
from web_viewer.legacy_v11_core import (
    extract_corrected_pages,
    extract_reading_document,
    attach_variant_metadata_to_runs,
    load_json,
)


def _witness_cache(project, w):
    """``(JSON brut, JSON après les règles d'ALTO, d'images et d'IIIF)`` du
    témoin ``w`` (une configuration de project.xml, ou sa copie pour un texte
    synchronisé à part : ``text_project``)."""
    alignment_available = has_line_synchronization(w)
    raw_cache = (load_json(w.alignment) if alignment_available
                 else {"meta": {"witness": w.id, "role": w.role}, "pages": []})
    cache = apply_witness_alto_policy(
        raw_cache, getattr(w, "alto_source_type", "auto"),
        [x.path for x in getattr(w, "alto_files", ())], project.root_dir,
        w.id, w.role,
        strict_no_ordinal=(getattr(w, 'image_source_type', '') == 'iiif'),
    )
    cache = apply_witness_image_policy(
        cache, getattr(w, "image_source_type", "auto"),
        getattr(w, "image_source_value", None), project.root_dir,
        getattr(w, "image_files", ()), w.id,
        getattr(w, 'iiif_selection_mode', 'all'),
        getattr(w, 'iiif_selected_canvases', ()),
        getattr(w, 'iiif_ocr_links', ()),
        getattr(w, 'iiif_page_links', ()),
    )
    if getattr(w, 'iiif_web_local_copy', False) and w.image_source_type == 'iiif':
        cache = apply_working_copy(cache, project.root_dir, w.id)
    return raw_cache, cache


def _namespaced(cache, prefix):
    """Copie de ``cache`` dont les identifiants de pages, et les ``base_keys``
    des lignes d'un témoin secondaire, portent ``prefix`` (texte synchronisé
    à part : ses JSON peuvent reprendre les pages du JSON global)."""
    out = copy.deepcopy(cache)
    for page in out.get("pages", []) or []:
        if page.get("id") is not None:
            page["id"] = prefix + str(page["id"])
        for line in page.get("lines", []) or []:
            for field in ("base_keys", "keys816"):
                if line.get(field):
                    line[field] = [prefix + str(key) for key in line[field]]
    return out


def _pivot_pages(pages, corrected_by_key, variant_registry):
    """Pages du pivot avec, pour chaque ligne reliée au TEI, son texte
    corrigé, ses fragments et ses notes ; et leur nombre de lignes."""
    pages_out, total_lines = [], 0
    for cp in pages:
        out_lines = []
        for line in cp.get('lines', []):
            key = f"{cp['id']}::{line.get('line')}"
            c = corrected_by_key.get(key)
            entry = dict(line)
            if c is not None:
                attach_variant_metadata_to_runs(c, variant_registry)
                seen, anns = set(), []
                for ann in c.get('annotations', []):
                    if ann['id'] not in seen:
                        seen.add(ann['id']); anns.append(ann)
                entry.update(corrected=c['text'], runs=c['runs'],
                             annotations=anns, break_no=c.get('break_no', False))
            out_lines.append(entry)
        po = dict(cp)
        po['lines'] = out_lines
        pages_out.append(po)
        total_lines += len(out_lines)
    return pages_out, total_lines


def _normalized_pages(pages, project, is_base):
    """Pages d'un témoin pour le viewer : bloc d'image normalisé ; les
    anciens ``keys816`` deviennent ``base_keys``."""
    if not is_base:
        for p in pages:
            for line in p.get("lines", []):
                if "base_keys" not in line and "keys816" in line:
                    line["base_keys"] = line.get("keys816") or []
    normalized = []
    for p in pages:
        pp = dict(p)
        pp["image"] = normalized_image_block(p, project.root_dir)
        normalized.append(pp)
    return normalized


def _sync_state(w, raw_pages, normalized_pages, is_base, base_has_alignment, valid_base_keys, prefix=""):
    """``(synchronisé par lignes, diagnostic)`` d'un témoin : relié aux lignes
    du pivot réellement publiées, ou suivi par pages."""
    matched_secondary_keys = {
        prefix + str(key) for raw_page in raw_pages for raw_line in (raw_page.get('lines') or [])
        for key in (raw_line.get('base_keys') or raw_line.get('keys816') or [])
        if prefix + str(key) in valid_base_keys
    } if not is_base else set()
    witness_line_sync = bool(
        base_has_alignment and (is_base or
        (has_line_synchronization(w) and bool(matched_secondary_keys)))
    )
    return witness_line_sync, {
        "raw_lines": sum(len(rp.get('lines') or []) for rp in raw_pages),
        "matched_base_keys": len(matched_secondary_keys),
        "emitted_lines": sum(len(pp.get('lines') or []) for pp in normalized_pages),
        "state": ('line' if witness_line_sync else 'page'),
    }


def _folio_objects(edition_text, witness_id, pages):
    """Folios du témoin (``folios_for_witness``) pour ses pages."""
    ids = [str(p.get('tei_surface_id')) for p in pages if p.get('tei_surface_id')]
    labels = {str(p['tei_surface_id']): str((p.get('image') or {}).get('label') or p.get('label') or '')
              for p in pages if p.get('tei_surface_id')}
    return folios_for_witness(edition_text, witness_id, ids, labels)


def _folio_entries(folios):
    return [dict(ref=f.ref, surface=f.surface, label=f.label, region=f.region) for f in folios]


def _has_image(page):
    image = page.get('image') or {}
    return (image.get('type') in {'iiif', 'file'}
            and bool(image.get('path') or image.get('service') or image.get('image')))


def _text_caches(project, assembled):
    """Pour chaque texte synchronisé à part (k ≥ 1) : ``(témoins par pages,
    {témoin: (configuration, JSON brut, JSON après les règles)})``, et le
    contexte des règles du texte (``segment_model``)."""
    import segment_model
    from folio_navigation import witness_loci
    from text_alignments import text_project
    from xml_assembly import path_key
    try:
        master = Path(project.edition).read_text(encoding='utf-8-sig')
    except (OSError, UnicodeError):
        master = ''
    edition_loci = witness_loci(master)
    declared = {w.id for w in project.witnesses}
    found = {}
    for segment in assembled.segments[1:]:
        texts = {}
        for path in assembled.segment_files(segment.index):
            try:
                texts[path] = Path(path).read_text(encoding='utf-8-sig')
            except (OSError, UnicodeError):
                texts[path] = ''
        ids = segment_model.segment_ids(texts.values())
        own = next((text for path, text in texts.items() if path_key(path) == segment.key), None)
        loci = segment_model.segment_loci(edition_loci, own)
        page_witnesses = segment_model.text_page_witnesses(assembled.lines, segment.key, ids, loci, declared)
        tproject = text_project(project, segment.sync, page_witnesses)
        caches = {}
        for tw in tproject.witnesses:
            if tw.alignment is not None:
                raw, cache = _witness_cache(project, tw)
                caches[tw.id] = (tw, raw, cache)
        found[segment.index] = {"page_witnesses": set(tproject.page_witnesses), "caches": caches,
                                "ids": ids, "loci": loci}
    return found


def _line_order(order, keys_by_segment, prefixes):
    """Ordre de lecture de toutes les lignes : celui des ``<lb>`` du
    document ; une ligne d'un JSON sans ``<lb>`` vient après la dernière
    ligne de son texte."""
    order = list(order)
    placed = set(order)

    def segment_of(key):
        return next((k for k, prefix in prefixes.items() if prefix and key.startswith(prefix)), 0)

    for index, keys in keys_by_segment.items():
        missing = [key for key in keys if key not in placed]
        if not missing:
            continue
        last = max((i for i, key in enumerate(order) if segment_of(key) == index), default=len(order) - 1)
        order[last + 1:last + 1] = missing
        placed.update(missing)
    return order


def build_dataset(project, display_witness_ids=None):
    """Build an export without rewriting the project's scientific witness order.

    ``display_witness_ids`` is an optional ordered snapshot of the GUI's
    visible witness IDs. None preserves the standalone/CLI behavior (all
    witnesses). The pivot remains an internal synchronization source even
    when its panel is hidden; hidden witnesses' facsimiles are not published.

    Édition en parties (V0.9.1.6) : l'édition assemblée ; chaque texte
    synchronisé à part (``meta.segments``) a ses JSON, son pivot et ses clés
    préfixées (``~1~``…), et chaque témoin une vue par texte (``views``).
    """
    base_id = project.base_witness
    known_ids = [w.id for w in project.witnesses]
    if display_witness_ids is None:
        displayed_ids = known_ids[:]
    else:
        valid = set(known_ids)
        displayed_ids = list(dict.fromkeys(
            str(wid) for wid in display_witness_ids if str(wid) in valid
        ))

    caches = {}
    # V0.8.4 : conserver séparément le JSON d'alignement *brut*. Une ressource
    # ALTO indépendante ajoute elle aussi des lignes numérotées ; si l'on jugeait
    # l'état de synchronisation après cette superposition, un JSON vide pourrait
    # activer à tort le mode ligne.
    raw_sync_caches = {}
    for w in project.witnesses:
        raw_sync_caches[w.id], caches[w.id] = _witness_cache(project, w)
    base_cache = caches[base_id]
    base_cfg = project.witness_by_id[base_id]
    base_sync_line_count = primary_sync_line_count(raw_sync_caches.get(base_id))
    base_has_alignment = bool(has_line_synchronization(base_cfg) and base_sync_line_count > 0)

    # Identical indexing contract to MainWindow/flatten_primary: the nth
    # eligible pivot <lb/> follows the nth physical pivot JSON line, regardless
    # of intervening TEI folio markers. Per-page <lb/> renumbering is unsafe:
    # page @n can be a folio and @facs a zone rather than a JSON page ID.
    physical_base_keys = [f"{p['id']}::{line.get('line')}"
                          for p in base_cache.get('pages', [])
                          for line in p.get('lines', [])] if base_has_alignment else []
    import xml.etree.ElementTree as ET
    # Édition en parties (V0.9.1.6) : l'édition assemblée, chaque élément
    # rattaché à son texte ; sinon le fichier de l'édition, comme avant.
    assembled = load_assembled(project)
    texts = {}
    if assembled is None:
        edition_root = ET.parse(project.edition).getroot()
        _, anchor_report = build_pivot_lb_index(edition_root, base_id, physical_base_keys)
        anchor_keys = physical_base_keys if base_has_alignment else None
        reading_options = {}
    else:
        edition_root = assembled.root
        texts = _text_caches(project, assembled) if len(assembled.segments) > 1 else {}
        keys_by_segment = {0: physical_base_keys}
        for segment in assembled.segments[1:]:
            entry = (texts[segment.index]["caches"].get(segment.pivot) or (None, None, None))
            raw, cache = entry[1], entry[2]
            texts[segment.index]["line_sync"] = bool(raw is not None and primary_sync_line_count(raw) > 0)
            keys_by_segment[segment.index] = ([f"{segment.prefix}{p['id']}::{line.get('line')}"
                                               for p in cache.get('pages', []) for line in p.get('lines', [])]
                                              if texts[segment.index]["line_sync"] else [])
        lookup, reports, lb_order = build_segment_lb_index(
            edition_root, assembled.segment, {s.index: s.pivot for s in assembled.segments}, keys_by_segment)
        anchor_report = reports[0]
        anchor_keys = None
        # Sans JSON du pivot, les clés de page des <pb> (mode page), comme avant.
        reading_options = dict(root=edition_root,
                               line_anchors=lookup if any(keys_by_segment.values()) else None,
                               segment_of=assembled.segment, target_of=assembled.target)
    page_resolver = PageResolver(edition_root, base_cache.get('pages', []), base_id)
    corr_pages, witness_labels = extract_corrected_pages(
        project.edition, f"#{base_id}", page_resolver=page_resolver,
        base_line_keys=anchor_keys, **reading_options)
    # Textes à part : chaque <pb> porte sa ligne, pour le parcours des témoins.
    reading_document = extract_reading_document(
        project.edition, f"#{base_id}", include_foreign_pagebreaks=True,
        page_resolver=page_resolver, base_line_keys=anchor_keys, pb_line_keys=bool(texts), **reading_options)

    # Do NOT use only TEI-extracted lines as the pivot's physical navigation
    # data. Desktop includes every JSON line (even when a TEI page lacks a
    # resolvable @facs), and secondary base_keys address that entire set.
    corrected_by_key = {}
    for corr_lines in corr_pages.values():
        for c in corr_lines:
            key = c.get('line_key')
            if key:
                corrected_by_key[key] = c
    missing, variant_registry = [], {}
    pages_out, total_lines = (_pivot_pages(base_cache.get('pages', []), corrected_by_key, variant_registry)
                              if base_has_alignment else ([], 0))
    # Page-only mode does not establish a TEI-to-line correspondence merely
    # because ALTO geometric line boxes happen to be present.
    # Publication navigation can only target *real emitted* pivot lines. The
    # raw alignment may contain links to vanished/unknown pages; those do not
    # turn a secondary witness into an operational line-synchronized witness.
    valid_base_keys = {f"{p['id']}::{line['line']}" for p in pages_out
                       for line in p['lines'] if p.get('id') and line.get('line') is not None}
    if not valid_base_keys:
        base_has_alignment = False
    # Lignes du pivot de chaque texte synchronisé à part.
    text_pivot_pages = {}
    for k, text in texts.items():
        segment = assembled.segments[k]
        entry = text["caches"].get(segment.pivot)
        if entry is None or not text["line_sync"]:
            text["line_sync"] = False
            continue
        pages, count = _pivot_pages(_namespaced(entry[2], segment.prefix).get('pages', []),
                                    corrected_by_key, variant_registry)
        text["valid_keys"] = {f"{p['id']}::{line['line']}" for p in pages
                              for line in p['lines'] if p.get('id') and line.get('line') is not None}
        text["line_sync"] = bool(text["valid_keys"])
        text_pivot_pages[k] = (pages, count)
    all_valid_keys = valid_base_keys.union(*(text.get("valid_keys", set()) for text in texts.values()))
    text_line_keys = [str(seg.get('line_key')) for block in reading_document.get('blocks', [])
                      for seg in block.get('segments', [])
                      if seg.get('kind') == 'text' and seg.get('line_key')]
    orphan_text_keys = sorted(set(text_line_keys) - all_valid_keys)
    unanchored_text_segments = sum(1 for block in reading_document.get('blocks', [])
                                   for seg in block.get('segments', [])
                                   if seg.get('kind') == 'text' and
                                   str(seg.get('text') or '').strip() and not seg.get('line_key'))
    unique_var, unique_notes = set(), set()
    for p in pages_out + [p for pages, _count in text_pivot_pages.values() for p in pages]:
        for line in p["lines"]:
            for ann in line.get("annotations", []):
                if ann.get("kind") == "variant": unique_var.add(ann["id"])
                elif ann.get("kind") == "note": unique_notes.add(ann["id"])
    witnesses = []
    for w in project.witnesses:
        cache = caches[w.id]
        is_base = w.id == base_id
        # Sans synchronisation ligne-à-ligne, conserver toutes les pages du
        # témoin de base. L'ALTO éventuel reste une géométrie de page, pas une
        # correspondance avec les lignes de l'édition.
        pages = (pages_out if base_has_alignment else cache.get("pages", [])) if is_base else cache.get("pages", [])
        normalized_pages = _normalized_pages(pages, project, is_base)
        raw_pages = (raw_sync_caches.get(w.id) or {}).get('pages', []) or []
        witness_line_sync, diagnostic = _sync_state(w, raw_pages, normalized_pages, is_base,
                                                    base_has_alignment, valid_base_keys)
        witnesses.append({"id": w.id, "label": w.label,
                          "role": "base" if is_base else "secondary",
                          "line_sync": witness_line_sync,
                          "sync_diagnostic": diagnostic,
                          "pages": normalized_pages, "meta": cache.get("meta", {})})
    # Same TEI zone semantics as desktop: one physical image may contain
    # two independently addressed folios. No image is duplicated in the export.
    if assembled is not None:
        edition_text = ET.tostring(edition_root, encoding='unicode')
    else:
        try:
            edition_text = project.edition.read_text(encoding='utf-8-sig')
        except (OSError, UnicodeError):
            edition_text = ''
    folio_objects = {}
    for witness in witnesses:
        folio_objects[witness['id']] = _folio_objects(edition_text, witness['id'], witness['pages'])
        witness['folios'] = _folio_entries(folio_objects[witness['id']])
    if texts:
        _add_text_views(project, assembled, texts, text_pivot_pages, witnesses, folio_objects,
                        raw_sync_caches, edition_text)
        _add_routes(assembled, texts, [w for w in witnesses if w['id'] in displayed_ids], caches,
                    caches[base_id] if base_has_alignment else None, folio_objects, reading_document)
    # Publish the selected witnesses in the exact on-screen order. Keep only
    # the pivot as a hidden, image-free technical witness if it is not visible:
    # its physical keys are indispensable for text->secondary navigation.
    # Les pivots des textes à part sont gardés de même (V0.9.1.6).
    by_id = {w['id']: w for w in witnesses}
    technical = [base_id] + [s.pivot for s in assembled.segments[1:]] if texts else [base_id]
    export_order = displayed_ids + [wid for wid in dict.fromkeys(technical) if wid not in displayed_ids]
    witnesses = [by_id[wid] for wid in export_order]
    for wid in export_order:
        if wid not in displayed_ids:
            for page in by_id[wid]['pages']:
                page['image'] = {'type': 'none'}
            for view in by_id[wid].get('views', {}).values():
                for page in view.get('pages', []) or []:
                    page['image'] = {'type': 'none'}
    has_images = any(
        _has_image(p)
        for w in witnesses if w['id'] in displayed_ids for p in w['pages']
    )
    i18n = I18nManager(project.translations_dir, project.language, project.fallback_language)
    meta_assembly = {} if assembled is None else {
        "assembled": True,
        "assembly_problems": [_problem_entry(problem, project) for problem in assembled.problems],
    }
    if texts:
        segments_meta = [{"index": 0, "name": None, "file": _relative(project.edition, project),
                          "pivot": base_id, "prefix": "", "anchor": 0,
                          "line_sync": bool(base_has_alignment), "lines": total_lines,
                          "pivot_lb_index": anchor_report.as_dict()}]
        for segment in assembled.segments[1:]:
            pages, count = text_pivot_pages.get(segment.index, ([], 0))
            segments_meta.append({"index": segment.index, "name": segment.name,
                                  "file": _relative(segment.path, project), "pivot": segment.pivot,
                                  "prefix": segment.prefix, "anchor": segment.anchor,
                                  "line_sync": bool(texts[segment.index]["line_sync"]), "lines": count,
                                  "pivot_lb_index": reports[segment.index].as_dict()})
        valid_by_segment = {0: valid_base_keys,
                            **{k: text.get("valid_keys", set()) for k, text in texts.items()}}
        published = {k: [key for key in keys if key in valid_by_segment[k]] for k, keys in keys_by_segment.items()}
        meta_assembly.update(
            segments=segments_meta,
            line_order=_line_order([key for key in lb_order if key in all_valid_keys], published,
                                   {s.index: s.prefix for s in assembled.segments}),
            text_sync_problems=[{"name": problem.name, "code": problem.code, "detail": problem.detail}
                                for problem in assembled.sync_problems],
        )
    lines_total = total_lines + sum(count for _pages, count in text_pivot_pages.values())
    line_sync = bool(base_has_alignment) or any(text.get("line_sync") for text in texts.values())
    return {
        "meta": {"title": project.title, "base_witness": base_id,
                 "display_witnesses": displayed_ids,
                 "pages": len(pages_out) if base_has_alignment else len(base_cache.get("pages", []) or []),
                 "lines": lines_total, "variants": len(unique_var), "notes": len(unique_notes),
                 "has_images": bool(has_images), "line_sync": line_sync,
                 "tei_page_resolution": page_resolver.stats.copy(),
                 "raw_pivot_lines": base_sync_line_count,
                 "matched_pivot_lines": len(corrected_by_key),
                 "pivot_lb_index": anchor_report.as_dict(),
                 "unresolvable_text_line_keys": len(orphan_text_keys),
                 "unanchored_text_segments": unanchored_text_segments,
                 "unmatched_tei_pages": sorted(set(missing)),
                 "external_iiif_images": sum(1 for ww in witnesses for pp in ww['pages']
                                             if (pp.get('image') or {}).get('type') == 'iiif'),
                 **meta_assembly},
        "witness_labels": witness_labels, "document": reading_document, "witnesses": witnesses,
        "i18n": i18n.export_catalogs(),
    }, missing


def _add_text_views(project, assembled, texts, text_pivot_pages, witnesses, folio_objects,
                    raw_sync_caches, edition_text):
    """Vue de chaque témoin dans chaque texte synchronisé à part : par
    lignes (son JSON pour ce texte, relié au pivot du texte), par pages (son
    JSON sans lien, ou ses ``<pb>`` et ``<locus>`` dans le texte), ou
    absente. La vue de l'édition reste dans les champs du témoin."""
    import segment_model
    by_id = {w['id']: w for w in witnesses}
    for k, text in texts.items():
        segment = assembled.segments[k]
        for witness in witnesses:
            wid = witness['id']
            is_pivot = wid == segment.pivot
            entry = text["caches"].get(wid)
            view = None
            if entry is not None:
                tw, raw, cache = entry
                if is_pivot and k in text_pivot_pages:
                    pages = _normalized_pages(text_pivot_pages[k][0], project, True)
                else:
                    pages = _normalized_pages(_namespaced(cache, segment.prefix).get('pages', []), project, is_pivot)
                line_sync, diagnostic = _sync_state(tw, raw.get('pages', []) or [], pages, is_pivot,
                                                    text["line_sync"], text.get("valid_keys", set()),
                                                    prefix=segment.prefix)
                if line_sync or any(_has_image(page) for page in pages):
                    folios = _folio_objects(edition_text, wid, pages)
                    view = {"mode": "line" if line_sync else "page",
                            "role": "base" if is_pivot else "secondary", "line_sync": line_sync,
                            "sync_diagnostic": diagnostic, "pages": pages, "folios": _folio_entries(folios)}
                    if not line_sync:
                        start = segment_model.start_folio(assembled.lines, segment.key, wid, folios,
                                                          text["loci"], text["ids"])
                        if start is not None:
                            view["start"] = start.ref
            elif wid in text["page_witnesses"] and any(_has_image(page) for page in witness['pages']):
                view = {"mode": "page", "role": "secondary", "line_sync": False, "same_pages": True,
                        "sync_diagnostic": {"raw_lines": 0, "matched_base_keys": 0, "emitted_lines": 0,
                                            "state": "page"}}
                start = segment_model.start_folio(assembled.lines, segment.key, wid, folio_objects[wid],
                                                  text["loci"], text["ids"])
                if start is not None:
                    view["start"] = start.ref
            if view is not None:
                by_id[wid].setdefault("views", {})[str(k)] = view


def _add_routes(assembled, texts, witnesses, caches, base_cache, folio_objects, reading_document):
    """Parcours de chaque témoin affiché dans son propre ordre, d'un texte à
    l'autre (``witness_route``, comme sur le bureau), et pages qui mènent le
    texte : ``route``, ``route_uncertain``, ``lead`` (vue de l'édition ou
    d'un texte, par pages) et ``lead_locus``.

    Les sources du parcours sont les JSON après les règles d'ALTO, d'images
    et d'IIIF, sans préfixe (l'identité des pages est celle du bureau) ; les
    clés exportées portent le préfixe du texte."""
    from dataclasses import replace

    import segment_model
    from folio_navigation import Folio
    from web_viewer.segment_views import export_route, locus_leads, page_leads, page_marks
    from witness_resource_refresh import flatten_primary
    from witness_route import Source, witness_route
    segments = assembled.segments
    prefixes = {s.index: s.prefix for s in segments}
    pivot_caches = {0: base_cache}
    for segment in segments[1:]:
        entry = texts[segment.index]["caches"].get(segment.pivot)
        pivot_caches[segment.index] = entry[2] if entry is not None and texts[segment.index]["line_sync"] else None
    base_by_key, pivot_keys, ranks = {}, {}, {}
    for k, cache in pivot_caches.items():
        items, base_by_key[k] = flatten_primary(cache) if cache is not None else ([], {})
        pivot_keys[k] = [prefixes[k] + item["key"] for item in items]
        ranks[k] = {key: rank for rank, key in enumerate(pivot_keys[k])}
    locus_texts = [(s.index, texts[s.index]["loci"], texts[s.index]["ids"]) for s in segments[1:]]
    for witness in witnesses:
        wid = witness['id']
        # Ses vues : (texte, par lignes, JSON sans préfixe, folios).
        views = [(0, bool(witness['line_sync']), caches[wid], folio_objects[wid])]
        for segment in segments[1:]:
            view = witness.get('views', {}).get(str(segment.index))
            if view is None:
                continue
            if view.get('same_pages'):
                views.append((segment.index, False, caches[wid], folio_objects[wid]))
            else:
                views.append((segment.index, view['mode'] == 'line', texts[segment.index]["caches"][wid][2],
                              [Folio(**f) for f in view['folios']]))
        marks = page_marks(reading_document, wid, {k: folios for k, line, _cache, folios in views if not line},
                           ranks)
        sources = []
        for k, line, cache, _folios in views:
            anchor = segments[k].anchor if k else 0
            segment_key = k or None
            if line:
                source = Source(segment_key, cache, wid == segments[k].pivot, base_by_key[k], anchor)
            else:
                source = Source(segment_key, marks=tuple(marks.get(k, ())), anchor=anchor)
            if k == 0:
                sources.append(source)
            elif source.cache is not None or source.marks:
                sources.append(replace(source, locus=segment_model.locus_start(
                    texts[k]["loci"], wid, texts[k]["ids"])))
        declared = segment_model.declared_page_ranks(
            [caches[wid]] + [text["caches"][wid][2] for text in texts.values() if wid in text["caches"]],
            folio_objects[wid])
        route = witness_route(wid, sources, declared)
        witness['route'] = export_route(route, prefixes, pivot_keys)
        witness['route_uncertain'] = [0 if k is None else k for k in route.uncertain]
        page_folios = []
        for k, line, cache, folios in views:
            if line:
                continue
            leads = page_leads(route, cache.get('pages', []) or [], folios)
            if leads:
                (witness if k == 0 else witness['views'][str(k)])['lead'] = leads
            page_folios.extend(folios)
        leads = locus_leads(wid, page_folios, locus_texts)
        if leads:
            witness['lead_locus'] = leads


def _relative(path, project):
    """Chemin relatif au projet (aucun chemin absolu dans le viewer)."""
    path = Path(path)
    try:
        return path.resolve().relative_to(Path(project.root_dir).resolve()).as_posix()
    except ValueError:
        return path.name


def _problem_entry(problem, project):
    """Problème d'assemblage pour le diagnostic de l'export : fichier
    relatif au projet (aucun chemin absolu dans le viewer)."""
    path = Path(problem.file)
    try:
        name = path.resolve().relative_to(Path(project.root_dir).resolve()).as_posix()
    except ValueError:
        name = path.name
    return {"file": name, "line": int(problem.line or 0), "code": problem.code, "detail": problem.detail}


HTML_TEMPLATE = r'''<!doctype html><html lang="__LANG__"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title>
<style>
:root{--paper:#fbfaf6;--bg:#eeeae3;--ink:#28231e;--muted:#746b61;--line:#d8d0c5;--accent:#684786;--sel:#fff0b8;--panel:#fffdf9;--shadow:0 8px 24px rgba(55,42,28,.12);--side-width:430px;--reader-scale:1}*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}header{position:sticky;top:0;z-index:30;background:rgba(251,250,246,.97);border-bottom:1px solid var(--line);padding:10px 18px}.header-row{display:flex;gap:14px;justify-content:space-between;align-items:center;flex-wrap:wrap}.brand h1{font:600 21px/1.15 Georgia,serif;margin:0}.sub,.status{font-size:10px;color:var(--muted)}.controls{display:flex;gap:6px;align-items:center;flex-wrap:wrap}.controls input,.controls button,.controls select,.toolbar button,.card-h button{border:1px solid var(--line);background:white;border-radius:7px;padding:6px 8px}.layout{max-width:1900px;margin:auto;display:grid;grid-template-columns:minmax(0,1fr) 8px minmax(300px,var(--side-width));gap:8px;padding:14px 18px;align-items:start}.resizer{cursor:col-resize}.resizer:hover{background:#cfc4b6}.reader{background:var(--paper);border:1px solid var(--line);border-radius:12px;box-shadow:var(--shadow);padding:38px clamp(24px,5vw,70px);min-height:calc(100vh - 96px)}.reader-inner{max-width:900px;margin:auto}.doc-title{font:600 calc(26px * var(--reader-scale))/1.2 Georgia,serif;text-align:center;margin-bottom:24px}.toc{margin:0 0 28px;padding:12px;border:1px solid var(--line);border-radius:9px;background:#f5f0e8}.toc-title{font:700 11px system-ui;color:var(--muted);margin-bottom:6px}.toc-list{display:flex;flex-wrap:wrap;gap:4px 12px}.toc a{font:600 12px system-ui;color:var(--accent);text-decoration:none}.tei-p{font:calc(18px * var(--reader-scale))/1.72 Georgia,serif;margin:0 0 1.1em;text-align:justify;hyphens:auto}.sermon-start{margin:2.8em 0 1.3em}.sermon-rule{border:0;border-top:2px solid #b9afa3}.sermon-id{font:700 calc(23px * var(--reader-scale)) Georgia,serif}.tei-italic{font-style:italic}.tei-bold{font-weight:700}.tei-unclear{text-decoration:underline dotted}.tei-sic{text-decoration:underline dashed}.editorial-ref{font-size:.84em;color:#746c82}.line-frag{border-radius:3px;cursor:pointer}.line-frag:not([data-line]){cursor:text}.line-frag:hover{background:#f1ede6}.selected-line{background:var(--sel)}.ann-marker{display:inline-grid;place-items:center;width:16px;height:16px;border-radius:50%;border:0;color:white;font:700 9px system-ui;vertical-align:super;cursor:pointer}.ann-marker.v{background:var(--accent)}.ann-marker.n{background:#a55531}.hide-variant-markers .ann-marker.v,.hide-note-markers .ann-marker.n{display:none}.pb{font:10px system-ui;color:#8b8176;border:1px solid #d7cec1;border-radius:99px;padding:2px 5px;margin:0 .3em;cursor:pointer}.pb.selected-page{background:var(--sel);border-color:#bcae83}.pb.foreign-page-anchor{display:none}.side{position:sticky;top:74px;display:grid;gap:7px;max-height:calc(100vh - 88px);overflow:auto;scrollbar-gutter:stable}.card{background:var(--panel);border:1px solid var(--line);border-radius:11px;box-shadow:var(--shadow);overflow:hidden}.card-h{display:flex;align-items:center;gap:6px;padding:6px 8px;border-bottom:1px solid var(--line)}.card-h h2{font-size:12px;margin:0;flex:1}.toolbar{display:flex;gap:4px;padding:4px 6px;border-bottom:1px solid var(--line)}.toolbar button{min-width:28px;height:27px;padding:0 6px;cursor:pointer}.toolbar .home{margin-left:auto}.image-wrap{height:156px;overflow-y:scroll;overflow-x:hidden;scrollbar-gutter:stable;background:#e8e3db;cursor:grab;contain:layout paint}.image-wrap.dragging{cursor:grabbing}.stage{width:100%;transform-origin:0 0}.slice{position:relative;width:100%;line-height:0}.slice+.slice{border-top:2px solid #c8beb1}.slice img{display:block;width:100%;height:auto;user-select:none;-webkit-user-drag:none}.hl{position:absolute;border:2px solid #d45735;background:transparent;pointer-events:none}.poly-overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none}.hl-poly{stroke:#d45735;fill:none;stroke-width:2;vector-effect:non-scaling-stroke}.hl.current-box{border-color:#3272a6}.hl-poly.current-poly{stroke:#3272a6}.highlights-off .hl:not(.current-box),.highlights-off .poly-overlay:not(.current-overlay){display:none}.empty{padding:24px 10px;text-align:center;color:var(--muted);font-size:11px}.iiif-failure{display:flex;align-items:center;justify-content:center;min-height:95px;padding:12px;text-align:center;font-size:11px;color:var(--muted);background:#efe9e2}.info-dialog{max-width:620px;border:1px solid var(--line);border-radius:12px}.info-dialog pre{white-space:pre-wrap;font-size:11px}.pop{position:fixed;display:none;z-index:100;background:white;border:1px solid var(--line);border-radius:10px;box-shadow:var(--shadow);max-width:520px;max-height:70vh;overflow:auto;padding:10px}.pop.show{display:block}.no-images .layout{grid-template-columns:minmax(0,1fr)}.no-images .resizer,.no-images .side{display:none}.no-images .reader{width:100%}@media(max-width:1000px){.layout{grid-template-columns:1fr}.resizer{display:none}.side{position:relative;top:auto;max-height:none}}

.search-option{font:11px system-ui;display:inline-flex;align-items:center;gap:3px;white-space:nowrap}.search-option input{accent-color:var(--accent)}.search-panel{position:absolute;top:100%;right:16px;z-index:42;background:var(--paper);border:1px solid var(--line);padding:10px;border-radius:0 0 10px 10px;box-shadow:var(--shadow);width:min(490px,calc(100vw - 32px));max-height:55vh;overflow:auto}.search-panel[hidden]{display:none}.search-nav{display:flex;gap:6px;align-items:center;font-size:12px;margin-bottom:6px}.search-nav strong{flex:1}.search-nav button{cursor:pointer;border:1px solid var(--line);border-radius:5px;background:white;padding:3px 6px}.search-results{display:flex;flex-direction:column;gap:3px}.search-result{font:12px/1.4 system-ui;text-align:left;cursor:pointer;border:1px solid transparent;background:white;border-radius:5px;padding:6px}.search-result:hover,.search-result.active{border-color:var(--accent);background:#f5eff8}.search-hit{background:#ffdb75;color:inherit;border-radius:2px}.search-hit.active-hit{background:#f4a93b;outline:1px solid #784e14}
</style></head><body class="__BODY_CLASS__">
<header><div class="header-row"><div class="brand"><h1 id="title"></h1><div class="sub" id="stats"></div><div class="sub" id="onlineNotice"></div><div class="sub" id="syncNotice" role="status" aria-live="polite"></div></div><div class="controls"><input id="search" type="search" aria-label="Search full text"><button id="searchButton" type="button" aria-label="Search">⌕</button><span class="search-option" id="searchModeLabel"></span><label class="search-option"><input id="searchUV" type="checkbox">u/v</label><label class="search-option"><input id="searchIJ" type="checkbox">i/j</label><label class="search-option"><input id="searchCT" type="checkbox">c/t</label><button id="fontMinus">A−</button><button id="fontReset">100 %</button><button id="fontPlus">A+</button><button id="prevBase"></button><button id="nextBase"></button><label class="search-option" id="showVariantsOption" hidden><input id="showVariants" type="checkbox" checked><span id="showVariantsLabel"></span></label><label class="search-option" id="showNotesOption" hidden><input id="showNotes" type="checkbox" checked><span id="showNotesLabel"></span></label><label><span id="languageLabel"></span> <select id="languageSelect"></select></label></div></div><section id="searchPanel" class="search-panel" hidden aria-live="polite"><div class="search-nav"><strong id="searchSummary"></strong><button id="searchPrev" type="button">◀</button><span id="searchPosition"></span><button id="searchNext" type="button">▶</button><button id="searchClose" type="button" aria-label="Close search">×</button></div><div id="searchResults" class="search-results"></div></section></header>
<div class="layout"><article class="reader"><div class="reader-inner"><div class="doc-title" id="docTitle"></div><nav class="toc" id="toc"></nav><div id="document"></div></div></article><div class="resizer" id="resizer"></div><aside class="side" id="witnessCards"></aside></div><div class="pop" id="popover"></div><dialog class="info-dialog" id="infoDialog"><button id="infoClose"></button><h3 id="infoTitle"></h3><div id="infoBody"></div></dialog>
<script id="data" type="application/json">__DATA_JSON__</script><script>
__GEOMETRY_JS__
__IIIF_JS__
__SEARCH_JS__
const DATA=JSON.parse(document.getElementById('data').textContent),$=id=>document.getElementById(id),esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const safeStorage={getItem(k){try{return window.localStorage.getItem(k)}catch(_){return null}},setItem(k,v){try{window.localStorage.setItem(k,v)}catch(_){}},removeItem(k){try{window.localStorage.removeItem(k)}catch(_){}}};
const I18N=DATA.i18n||{default:'fr',fallback:'en',languages:[],catalogs:{}};let uiLang=safeStorage.getItem('tei-ui-language')||I18N.default||'fr';if(!I18N.catalogs?.[uiLang])uiLang=I18N.default||I18N.fallback||Object.keys(I18N.catalogs||{})[0]||'fr';function t(key,vars={}){let s=I18N.catalogs?.[uiLang]?.[key]??I18N.catalogs?.[I18N.fallback]?.[key]??key;return String(s).replace(/\{([A-Za-z0-9_]+)\}/g,(m,k)=>Object.prototype.hasOwnProperty.call(vars,k)?vars[k]:m)}
const baseId=DATA.meta.base_witness,witnessMap=new Map(DATA.witnesses.map(w=>[w.id,w])),states=new Map(),lineMap=new Map(),lineOrder=[];const lineMode=!!DATA.meta.line_sync;
// The pivot can be an invisible technical witness. All DOM cards and their
// order come strictly from the exporting editor's visible panel snapshot.
const displayWitnesses=(Array.isArray(DATA.meta.display_witnesses)?DATA.meta.display_witnesses:DATA.witnesses.map(w=>w.id)).map(id=>witnessMap.get(id)).filter(Boolean);let selectedKey=null,selectedSurface=null,readerScale=Math.max(.75,Math.min(1.6,Number(safeStorage.getItem('tei-reader-scale')||1)));
function pageLabel(x){return String(x||'').replace(/^f\d+-/,'').replaceAll('-',' – ')}
function imageSource(p){return VariansGeometry.imageSource(p)}
const scaledBBox=VariansGeometry.scaledBBox,scaledPolygon=VariansGeometry.scaledPolygon,crop=VariansGeometry.crop;
function itemKey(w,it){if(it?.l?._page_mode)return it.p.tei_surface_id||it.p.id;return w.role==='base'?`${it.p.id}::${it.l.line}`:`${it.p.id}::${it.l.alto_id||it.l.line}`}
function fullPageUrl(p){return VariansIIIF.fullPageURL(imageSource(p),VariansGeometry.fullRegion(p))}
for(const w of DATA.witnesses){const pageMode=!lineMode||!w.line_sync,physical=[];if(pageMode){for(const p of w.pages||[]){const src=imageSource(p);if(src.type!=='none')physical.push({p,l:{_page_mode:true}})}}else{for(const p of w.pages||[])for(const l of p.lines||[])physical.push({p,l});if(w.role!=='base')physical.sort((a,b)=>Number(a.l.order||0)-Number(b.l.order||0))}const index=new Map(physical.map((it,i)=>[itemKey(w,it),i])),byBase=new Map(),surfaceIndex=new Map(),labelIndex=new Map();for(let i=0;i<physical.length;i++){const page=physical[i].p,sid=page?.tei_surface_id;if(sid)surfaceIndex.set(String(sid),i);if(pageMode&&sid){const label=String(imageSource(page).label||page?.label||'').trim().toLocaleLowerCase();if(label){if(labelIndex.has(label))labelIndex.set(label,null);else labelIndex.set(label,String(sid))}}}const folioByRef=new Map((w.folios||[]).map(f=>[String(f.ref),f]));for(const f of (w.folios||[])){const i=surfaceIndex.get(String(f.surface));if(i!=null){surfaceIndex.set(String(f.ref),i);if(pageMode){const label=String(f.label||'').trim().toLocaleLowerCase();if(label){if(labelIndex.has(label))labelIndex.set(label,null);else labelIndex.set(label,String(f.ref))}}}}const folioChoices=(w.folios||[]).filter(f=>f.region||!(w.folios||[]).some(x=>x.region&&x.surface===f.surface));if(!pageMode&&w.role==='base'){for(const it of physical){const k=itemKey(w,it);lineMap.set(k,it);lineOrder.push(k)}}else if(!pageMode)for(let i=0;i<physical.length;i++)for(const k of (physical[i].l.base_keys||physical[i].l.keys816||[])){if(!byBase.has(k))byBase.set(k,[]);byBase.get(k).push(i)}states.set(w.id,{physical,index,byBase,surfaceIndex,labelIndex,pageMode,center:physical.length?0:null,origin:physical.length?0:null,matches:new Set(),zoom:1,frames:false,folioByRef,folioChoices,folioRef:null})}
function groupByPage(items){const a=[];for(const it of items){const last=a[a.length-1];if(!last||last.p.id!==it.p.id)a.push({p:it.p,items:[it]});else last.items.push(it)}return a}
function stageMarkup(w,items,matchKeys,pageMode,folioRef=null,centerKey=null,displayWidth=900){
  return groupByPage(items).map(g=>{
    const source=imageSource(g.p);
    let r=VariansGeometry.fullRegion(g.p),overlayItems;
    if(pageMode){
      const focus=(w.folios||[]).find(f=>f.ref===folioRef&&f.surface===g.p.tei_surface_id&&f.region);
      if(focus)r=VariansGeometry.folioRegion(g.p,focus.region);
      overlayItems=(g.p.lines||[]).map(l=>({p:g.p,l}));
    }else{
      r=crop(g.items)||VariansGeometry.fullRegion(g.p);
      overlayItems=g.items.filter(it=>matchKeys.has(itemKey(w,it))||itemKey(w,it)===centerKey);
    }
    const full=VariansGeometry.fullRegion(g.p);
    const partial=(r.x!==0||r.y!==0||r.w!==full.w||r.h!==full.h);
    const plans=VariansIIIF.plan(source,r,full,displayWidth,window.devicePixelRatio||1);
    if(!plans.length)return`<div class="empty">${esc(t('viewer.image_unavailable'))}</div>`;
    const ov=overlayItems.map(it=>{
      const points=scaledPolygon(it.p,it.l),isCurrent=!pageMode&&itemKey(w,it)===centerKey;
      if(points.length>=3){
        const coords=points.map(v=>v.join(',')).join(' ');
        return`<svg class="poly-overlay${isCurrent?' current-overlay':''}" viewBox="${r.x} ${r.y} ${r.w} ${r.h}" preserveAspectRatio="none"><polygon class="hl-poly${isCurrent?' current-poly':''}" points="${coords}"></polygon></svg>`;
      }
      const b=scaledBBox(it.p,it.l);
      if(!b)return''; // never draw false (0,0) rectangles
      return`<span class="hl${isCurrent?' current-box':''}" style="left:${100*(b.x-r.x)/r.w}%;top:${100*(b.y-r.y)/r.h}%;width:${100*b.w/r.w}%;height:${100*b.h/r.h}%"></span>`;
    }).join('');
    const sliceStyle=partial?` style="aspect-ratio:${r.w}/${r.h};overflow:hidden"`:'';
    // Each fallback carries its display mode. A full-image or low-res
    // derivative is clipped locally; a IIIF region fills the entire slice.
    const planAttr=esc(JSON.stringify(plans));
    const cropAttrs=partial?` data-full-width="${full.w}" data-full-height="${full.h}" data-crop="${[r.x,r.y,r.w,r.h].join(',')}"`:'';
    return`<div class="slice"${sliceStyle}><img src="${esc(plans[0].url)}" data-iiif-plan="${planAttr}" draggable="false"${cropAttrs}>${ov}</div>`;
  }).join('');
}
function cardHTML(w){const st=states.get(w.id),count=st.pageMode?(w.pages||[]).length:st.physical.length,unit=st.pageMode?t('viewer.pages'):t('common.lines');return`<section class="card" data-w="${esc(w.id)}"><div class="card-h"><h2>${esc(w.label)} · ${count} ${esc(unit)}</h2><span class="status" data-role="status">—</span><button data-act="info" title="${esc(t('viewer.details'))}">…</button></div><div class="toolbar"><button data-act="prev">←</button><button data-act="minus">−</button><button data-act="reset">↺</button><button data-act="plus">+</button><span class="status" data-role="zoom">100 %</span><button data-act="next">→</button>${st.pageMode?`<select data-folio aria-label="${esc(t('folio.navigator.label'))}"></select>`:''}<button data-act="frames">${esc(t('viewer.frames'))}</button><button data-act="page">${esc(t('viewer.page'))}</button>${w.role==='base'?'':`<button class="home" data-act="home" title="${esc(t('viewer.return_match'))}">⤺</button>`}</div><div class="image-wrap"><div class="stage highlights-off"></div></div></section>`}
function buildCards(){$('witnessCards').innerHTML=displayWitnesses.map(cardHTML).join('');$('witnessCards').onclick=e=>{const b=e.target.closest('button');if(!b)return;const card=b.closest('[data-w]');if(card)action(card.dataset.w,b.dataset.act)};$('witnessCards').onchange=e=>{const sel=e.target.closest('select[data-folio]');const card=sel?.closest('[data-w]');if(card&&sel.value)selectSurface('#'+sel.value,false)};for(const card of document.querySelectorAll('[data-w]'))initPanZoom(card)}
function updateCardLanguage(){for(const w of displayWitnesses){const card=document.querySelector(`[data-w="${CSS.escape(w.id)}"]`);if(!card)continue;const st=states.get(w.id),count=st.pageMode?(w.pages||[]).length:st.physical.length;card.querySelector('h2').textContent=`${w.label} · ${count} ${st.pageMode?t('viewer.pages'):t('common.lines')}`;const f=card.querySelector('[data-act=frames]');if(f)f.textContent=t('viewer.frames');const p=card.querySelector('[data-act=page]');if(p)p.textContent=t('viewer.page');const i=card.querySelector('[data-act=info]');if(i)i.title=t('viewer.details');const h=card.querySelector('[data-act=home]');if(h)h.title=t('viewer.return_match')}}
function windowItems(st){if(st.center==null)return[];return VariansGeometry.windowIndices(st.physical,st.center,1).map(i=>st.physical[i])}
function syncWitness(w,focus=false){const st=states.get(w.id);if(st.pageMode){if(selectedSurface&&st.surfaceIndex.has(selectedSurface)){st.center=st.surfaceIndex.get(selectedSurface);st.origin=st.center;st.folioRef=selectedSurface}renderWitness(w.id);return}if(w.role==='base'){st.center=st.index.get(selectedKey);st.origin=st.center;st.matches=new Set(selectedKey?[selectedKey]:[])}else{const m=st.byBase.get(selectedKey)||[];st.matches=new Set(m.map(i=>itemKey(w,st.physical[i])));st.center=VariansGeometry.nearestIndex(m,st.center??0,st.physical.length);st.origin=st.center}renderWitness(w.id);if(focus)focusCurrentLine(w.id)}
function focusCurrentLine(id){
 const st=states.get(id);if(!st||st.pageMode||st.center==null)return;
 const current=st.physical[st.center],bbox=VariansGeometry.scaledBBox(current.p,current.l),region=VariansGeometry.crop(windowItems(st));
 const wrap=document.querySelector(`[data-w="${CSS.escape(id)}"] .image-wrap`),slice=wrap?.querySelector('.slice');
 if(!wrap||!slice){return}
 if(!bbox||!region){wrap.scrollLeft=0;wrap.scrollTop=0;return}
 // The bitmap can still be loading; the crop aspect ratio already reserves
 // this rectangle and yields the same navigation coordinates as the overlay.
 const sw=slice.getBoundingClientRect().width,sh=slice.getBoundingClientRect().height;
 const focusX=sw*((bbox.x+bbox.w/2-region.x)/region.w),focusY=sh*((bbox.y+bbox.h/2-region.y)/region.h);
 wrap.scrollLeft=Math.max(0,focusX-wrap.clientWidth/2);
 wrap.scrollTop=Math.max(0,focusY-wrap.clientHeight/2)
}
function syncAll(focus=false){for(const w of displayWitnesses)syncWitness(w,focus)}
function selectSurface(ref,scroll=false){const sid=String(ref||'').trim().split(/\s+/).find(x=>x.startsWith('#'))?.slice(1)||String(ref||'').replace(/^#/,'');if(!sid)return;selectedSurface=sid;document.querySelectorAll('.pb.selected-page').forEach(x=>x.classList.remove('selected-page'));document.querySelectorAll('.pb[data-facs]').forEach(x=>{const refs=(x.dataset.facs||'').split(/\s+/).map(y=>y.replace(/^#/,''));if(refs.includes(sid))x.classList.add('selected-page')});if(scroll)document.querySelector('.pb.selected-page')?.scrollIntoView({block:'center'});for(const w of displayWitnesses){const st=states.get(w.id);if(st.pageMode&&st.surfaceIndex.has(sid)){st.center=st.surfaceIndex.get(sid);st.origin=st.center;st.folioRef=sid}renderWitness(w.id)}}
function renderWitness(id){
  const w=witnessMap.get(id),st=states.get(id),card=document.querySelector(`[data-w="${CSS.escape(id)}"]`);
  if(!card||!w||!st)return; // hidden pivot has no rendered card
  const stage=card.querySelector('.stage'),status=card.querySelector('[data-role=status]');
  VariansIIIF.cancelStage(stage);
  if(st.center==null){stage.innerHTML=`<div class="empty">${esc(t('viewer.no_match'))}</div>`;status.textContent=t('viewer.none');return}
  const its=windowItems(st),center=st.physical[st.center],viewWidth=(card.querySelector('.image-wrap').clientWidth||430)*st.zoom;
  stage.innerHTML=stageMarkup(w,its,st.matches,st.pageMode,st.folioRef,itemKey(w,center),viewWidth);
  VariansIIIF.bindStage(stage,t('viewer.image_unavailable'));
  // Metadata discovery is optional and never blocks an image request. CORS,
  // authentication, offline operation and timeouts cannot stop page display.
  for(const it of its){const source=imageSource(it.p);if(source.type==='iiif')VariansIIIF.discover(source)}
  stage.classList.toggle('highlights-off',!st.frames);
  const folioSelect=card.querySelector('[data-folio]');if(folioSelect){folioSelect.innerHTML=(w.folios||[]).map(f=>`<option value="${esc(f.ref)}">${esc(f.region?f.label:((w.folios||[]).some(x=>x.region&&x.surface===f.surface)?t('folio.full_image')+' · ':'')+f.label)}</option>`).join('');folioSelect.value=st.folioRef||String(center.p.tei_surface_id||'')}
  stage.style.width=`${st.zoom*100}%`;card.querySelector('[data-role=zoom]').textContent=Math.round(st.zoom*100)+' %';card.querySelector('.image-wrap').style.overflowX=st.zoom>1.001?'auto':'hidden';
  if(st.pageMode){status.textContent=t('manuscript.status.page_only_count',{page:pageLabel(st.folioByRef.get(st.folioRef)?.label||imageSource(center.p).label||center.p.id),current:st.center+1,total:st.physical.length})}
  else{const score=w.role==='base'||center.l.score==null?'':t('viewer.score',{score:Math.round(center.l.score*100)});status.textContent=t('viewer.status',{page:pageLabel(imageSource(center.p).label||center.p.id),line:center.l.line,score})}
}
function action(id,a){const w=witnessMap.get(id),st=states.get(id);if(a==='prev'||a==='next'){if(st.center==null)return;if(st.pageMode&&st.folioChoices?.length){const available=st.folioChoices,where=available.findIndex(f=>f.ref===st.folioRef),pos=where>=0?where:available.findIndex(f=>st.surfaceIndex.get(f.ref)===st.center),target=available[Math.max(0,Math.min(available.length-1,(pos<0?0:pos)+(a==='prev'?-1:1)))];if(target){st.center=st.surfaceIndex.get(target.ref);st.folioRef=target.ref;if(w.role==='base')selectSurface('#'+target.ref,false);else renderWitness(id)}return}st.center=Math.max(0,Math.min(st.physical.length-1,st.center+(a==='prev'?-1:1)));if(st.pageMode){const sid=st.physical[st.center].p?.tei_surface_id;if(w.role==='base'&&sid)selectSurface(sid,false);else renderWitness(id)}else if(w.role==='base')selectLine(itemKey(w,st.physical[st.center]),false);else renderWitness(id)}else if(a==='home'){st.center=st.origin;renderWitness(id)}else if(a==='minus'||a==='plus'){st.zoom=Math.max(1,Math.min(6,st.zoom*(a==='plus'?1.25:1/1.25)));renderWitness(id)}else if(a==='reset'){st.zoom=1;renderWitness(id)}else if(a==='frames'){st.frames=!st.frames;renderWitness(id)}else if(a==='page'){const it=st.center==null?null:st.physical[st.center],u=it&&fullPageUrl(it.p);if(u)window.open(u,'_blank','noopener')}else if(a==='info')showInfo(id)}
function initPanZoom(card){const wrap=card.querySelector('.image-wrap');let drag=false,sx=0,sy=0,sl=0,st=0;wrap.addEventListener('wheel',e=>{e.preventDefault();const S=states.get(card.dataset.w);S.zoom=Math.max(1,Math.min(6,S.zoom*(e.deltaY<0?1.16:1/1.16)));renderWitness(card.dataset.w)},{passive:false});wrap.ondblclick=()=>{states.get(card.dataset.w).zoom=1;renderWitness(card.dataset.w)};wrap.onmousedown=e=>{const S=states.get(card.dataset.w);if(S.zoom<=1||e.button!==0)return;drag=true;sx=e.clientX;sy=e.clientY;sl=wrap.scrollLeft;st=wrap.scrollTop;wrap.classList.add('dragging')};window.addEventListener('mousemove',e=>{if(drag){wrap.scrollLeft=sl-(e.clientX-sx);wrap.scrollTop=st-(e.clientY-sy)}});window.addEventListener('mouseup',()=>{drag=false;wrap.classList.remove('dragging')})}
function styles(s){return(s.styles||[]).map(x=>x==='italic'||x==='quote'?'tei-italic':x==='bold'?'tei-bold':x==='unclear'?'tei-unclear':x==='sic'?'tei-sic':'').filter(Boolean).join(' ')}
function ptrs(v){return String(v||'').trim().split(/\s+/).filter(Boolean).map(x=>x.replace(/^#/,''))}
function pbWitnessIds(pb,sids){const explicit=ptrs(pb.dataset.edref);if(explicit.length)return explicit.filter(id=>states.has(id));const out=[];for(const [id,st] of states){if(st.pageMode&&sids.some(sid=>st.surfaceIndex.has(sid)))out.push(id)}return out}
function syncPagesToDocPosition(docPos){if(!Number.isFinite(docPos))return;const latest=new Map();for(const pb of document.querySelectorAll('.pb[data-doc-pos]')){if(Number(pb.dataset.docPos)>docPos)break;const sids=ptrs(pb.dataset.facs);for(const wid of pbWitnessIds(pb,sids)){const st=states.get(wid);if(!st?.pageMode)continue;const label=String(pb.dataset.n||'').trim().toLocaleLowerCase();let sid=sids.length?sids.find(x=>st.surfaceIndex.has(x)):(label?st.labelIndex.get(label):null);if(sid&&label){const full=st.folioByRef.get(sid);if(full&&!full.region){const children=(witnessMap.get(wid)?.folios||[]).filter(f=>f.region&&f.surface===full.surface&&String(f.label).trim().toLocaleLowerCase()===label);if(children.length===1)sid=children[0].ref}}if(sid)latest.set(wid,sid)}}if(!latest.size)return;selectedSurface=null;document.querySelectorAll('.pb.selected-page').forEach(x=>x.classList.remove('selected-page'));for(const [wid,sid] of latest){const st=states.get(wid),i=st?.surfaceIndex.get(sid);if(i==null)continue;st.center=i;st.origin=i;st.folioRef=sid;renderWitness(wid);for(const pb of document.querySelectorAll('.pb[data-facs]')){if(ptrs(pb.dataset.facs).includes(sid))pb.classList.add('selected-page')}}}
function segHTML(s,pos){const dp=` data-doc-pos="${pos}"`;if(s.kind==='pb'){const foreign=s.foreign?' foreign-page-anchor':'';return`<span class="pb${foreign}"${dp}${s.facs?` data-facs="${esc(s.facs)}"`:''}${s.page?` data-n="${esc(s.page)}"`:''}${s.edref?` data-edref="${esc(s.edref)}"`:''}>${esc(s.label||s.page)}</span>`}if(s.kind==='editorial-ref')return`<span class="editorial-ref"${dp}${s.line_key?` data-line="${esc(s.line_key)}"`:""}>&lt;${searchHits.length?VariansFullText.splitText(String(s.text||''),pos,searchSpans,esc):esc(s.text)}&gt;</span>`;if(s.kind==='variant-marker')return`<button class="ann-marker v"${dp} data-ann="${esc(s.ann_id)}"${s.line_key?` data-line="${esc(s.line_key)}"`:""}>v</button>`;if(s.kind==='note')return`<button class="ann-marker n"${dp} data-ann="${esc(s.ann_id)}"${s.line_key?` data-line="${esc(s.line_key)}"`:""}>n</button>`;if(s.kind==='text')return`<span class="line-frag ${styles(s)}"${dp}${s.line_key?` data-line="${esc(s.line_key)}"`:(s.text?.trim()?` data-no-line="true"`: '')}>${searchHits.length?VariansFullText.splitText(String(s.text||''),pos,searchSpans,esc):esc(s.text)}</span>`;return''}
function renderDocument(){const h=[];let docPos=0;for(const b of DATA.document.blocks||[]){if(b.type==='sermon')h.push(`<div class="sermon-start" id="${esc(b.attrs.xml_id)}"><hr class="sermon-rule"><div class="sermon-id">${esc(b.attrs.display_id||String(b.attrs.xml_id).replaceAll('_',' '))}</div></div>`);else if(b.type==='p')h.push(`<p class="tei-p">${(b.segments||[]).map(s=>segHTML(s,docPos++)).join('')}</p>`)}$('document').innerHTML=h.join('');updateMarkerToggleAvailability();const toc=(DATA.document.blocks||[]).filter(b=>b.type==='sermon');$('toc').innerHTML=toc.length?`<div class="toc-title">${esc(t('viewer.toc'))}</div><div class="toc-list">${toc.map(b=>`<a href="#${esc(b.attrs.xml_id)}">${esc(b.attrs.display_id||String(b.attrs.xml_id).replaceAll('_',' '))}</a>`).join('')}</div>`:'';$('document').onclick=e=>{const f=e.target.closest('[data-line]');const a=e.target.closest('[data-ann]');const pb=e.target.closest('.pb[data-facs]');if(f&&lineMode){selectLine(f.dataset.line,false)}else if(pb){selectSurface(pb.dataset.facs,false)}else{const carrier=e.target.closest('[data-doc-pos]');if(carrier)syncPagesToDocPosition(Number(carrier.dataset.docPos));if(lineMode&&e.target.closest('[data-no-line]'))$('syncNotice').textContent=t('viewer.line_no_anchor')}if(a)showAnnotation(a.dataset.ann,e)}}
function defaultSyncNotice(){const a=DATA.meta.pivot_lb_index;return(lineMode&&a&&!a.count_match)?t('viewer.pivot_lb_mismatch',{markers:a.tei_lb_count,physical:a.physical_line_count}):''}
function selectLine(k,scroll=false){
 if(!lineMode||!lineMap.has(k)){$('syncNotice').textContent=t('viewer.line_unresolved',{key:String(k||'')});return false}
 $('syncNotice').textContent=defaultSyncNotice();selectedKey=k;
 document.querySelectorAll('.selected-line').forEach(x=>x.classList.remove('selected-line'));
 const fragments=document.querySelectorAll(`[data-line="${CSS.escape(k)}"]`);
 fragments.forEach(x=>x.classList.add('selected-line'));
 const fragment=[...fragments].find(x=>x.classList.contains('line-frag'))||fragments[0];
 if(scroll)fragment?.scrollIntoView({block:'center'});
 const docPos=fragment?Number(fragment.dataset.docPos):NaN;
 if(Number.isFinite(docPos))syncPagesToDocPosition(docPos);
 syncAll(true);return true
}
function moveBase(d){const w=witnessMap.get(baseId),st=states.get(baseId);if(st?.pageMode){if(st.center==null||!st.physical.length)return;st.center=Math.max(0,Math.min(st.physical.length-1,st.center+d));const sid=st.physical[st.center].p?.tei_surface_id;if(sid)selectSurface(sid,true);else renderWitness(baseId);return}const i=lineOrder.indexOf(selectedKey),n=Math.max(0,Math.min(lineOrder.length-1,i+d));if(lineOrder[n])selectLine(lineOrder[n],true)}
function showAnnotation(id,e){const a=DATA.document.annotations?.[id];if(!a)return;const kind=a.kind==='variant'?t('viewer.variant'):a.kind==='note'?t('viewer.note'):a.kind;let h=`<b>${esc(kind)}</b>`;if(a.kind==='variant')h+=(a.readings||[]).map(r=>`<div><b>${esc((r.wit||[]).join(', '))}</b> : ${esc(r.text||'∅')}</div>`).join('');else h+=`<div>${esc(a.text||'')}</div>`;const p=$('popover');p.innerHTML=h;p.style.left=Math.min(innerWidth-540,e.clientX+10)+'px';p.style.top=Math.min(innerHeight-300,e.clientY+10)+'px';p.classList.add('show')}
function showInfo(id){const w=witnessMap.get(id),st=states.get(id),its=windowItems(st);$('infoTitle').textContent=w.label;if(st.pageMode&&its.length){const it=its[0],lines=it.p.lines||[],label=pageLabel(imageSource(it.p).label||it.p.id);$('infoBody').innerHTML=`<pre>${esc(label)}\n${esc(t('viewer.info.page_lines',{count:lines.length}))}</pre>`}else{$('infoBody').innerHTML=its.length?its.map(it=>`<pre>${esc(t('viewer.info.line',{page:pageLabel(imageSource(it.p).label||it.p.id),line:it.l.line}))}\n${esc(it.l.alto||it.l.corrected||'')}\n${esc(JSON.stringify(it.l.bbox||{}))}</pre>`).join(''):esc(t('viewer.info.no_line'))}$('infoDialog').showModal()}
function setScale(v){readerScale=Math.max(.75,Math.min(1.6,Math.round(v*100)/100));document.documentElement.style.setProperty('--reader-scale',readerScale);$('fontReset').textContent=Math.round(readerScale*100)+' %';safeStorage.setItem('tei-reader-scale',readerScale)}
// A03 — l'index ne dépend ni des images IIIF ni du DOM reconstruit.
const searchIndex=VariansFullText.makeIndex(DATA.document.blocks||[]);
let searchHits=[],searchSpans=new Map(),activeSearchHit=-1,searchDelay=null;
function searchOptions(){const uv=$('searchUV').checked,ij=$('searchIJ').checked,ct=$('searchCT').checked;return {medieval:uv||ij||ct,uv,ij,ct}}
function updateSearchPanel(){
 const hasTerm=!!$('search').value.trim();$('searchPanel').hidden=!hasTerm;
 $('searchSummary').textContent=t('viewer.search.count',{count:searchHits.length});
 $('searchPosition').textContent=searchHits.length?(Math.max(0,activeSearchHit)+1)+' / '+searchHits.length:'';
 $('searchPrev').disabled=!searchHits.length;$('searchNext').disabled=!searchHits.length;
 const page=activeSearchHit<0?0:Math.floor(activeSearchHit/12);
 $('searchResults').innerHTML=searchHits.slice(page*12,page*12+12).map((hit,i)=>{
 const id=page*12+i;return`<button class="search-result${id===activeSearchHit?' active':''}" type="button" data-result="${id}">${esc((id+1)+'. '+hit.excerpt)}</button>`;
 }).join('');
 $('searchResults').onclick=e=>{const b=e.target.closest('[data-result]');if(b)selectSearchResult(Number(b.dataset.result))};
}
function searchUpdate(selectFirst=false){
 searchHits=VariansFullText.find(searchIndex,$('search').value,searchOptions());
 searchSpans=VariansFullText.spansByPosition(searchHits);
 activeSearchHit=-1;renderDocument();updateSearchPanel();
 if(selectFirst&&searchHits.length)selectSearchResult(0);
}
function selectSearchResult(i){
 if(!searchHits.length)return;
 activeSearchHit=(i+searchHits.length)%searchHits.length;
 document.querySelectorAll('.search-hit.active-hit').forEach(x=>x.classList.remove('active-hit'));
 document.querySelectorAll('.search-hit[data-hit="'+activeSearchHit+'"]').forEach(x=>x.classList.add('active-hit'));
 const hit=searchHits[activeSearchHit];
 const target=document.querySelector('.search-hit[data-hit="'+activeSearchHit+'"]');
 if(hit.lineKey&&lineMode&&lineMap.has(hit.lineKey))selectLine(hit.lineKey,false);
 else if(hit.docPos!=null)syncPagesToDocPosition(hit.docPos);
 target?.scrollIntoView({block:'center',behavior:'auto'});
 updateSearchPanel();
}
function search(){searchUpdate(true)}
function queueSearch(){if(searchDelay)clearTimeout(searchDelay);searchDelay=setTimeout(()=>searchUpdate(false),180)}
function initResizer(){const r=$('resizer'),root=document.documentElement;let drag=false;r.onmousedown=e=>{drag=true;e.preventDefault()};window.onmousemove=e=>{if(!drag)return;const w=Math.max(300,Math.min(innerWidth*.72,innerWidth-e.clientX-20));root.style.setProperty('--side-width',w+'px');safeStorage.setItem('tei-side-width',w)};window.onmouseup=()=>drag=false;r.ondblclick=()=>{root.style.setProperty('--side-width','430px');safeStorage.removeItem('tei-side-width')};const saved=Number(safeStorage.getItem('tei-side-width'));if(saved)root.style.setProperty('--side-width',saved+'px')}
function firstDocumentSurface(){const pb=document.querySelector('.pb[data-facs]');if(!pb)return null;return String(pb.dataset.facs||'').trim().split(/\s+/).find(x=>x.startsWith('#'))?.slice(1)||null}
function populateLanguages(){const sel=$('languageSelect');sel.innerHTML='';for(const lang of (I18N.languages||[])){const o=document.createElement('option');o.value=lang.code;o.textContent=lang.label;sel.appendChild(o)}sel.value=uiLang;sel.onchange=()=>setLanguage(sel.value)}
function applyMarkerVisibility(){document.body.classList.toggle('hide-variant-markers',!$('showVariants').checked);document.body.classList.toggle('hide-note-markers',!$('showNotes').checked);$('popover').classList.remove('show')}
function initMarkerToggles(){for(const [id,storageKey] of [['showVariants','tei-show-variants'],['showNotes','tei-show-notes']]){const box=$(id);box.checked=safeStorage.getItem(storageKey)!=='0';box.onchange=()=>{safeStorage.setItem(storageKey,box.checked?'1':'0');applyMarkerVisibility()}}applyMarkerVisibility()}
function updateMarkerToggleAvailability(){$('showVariantsOption').hidden=!document.querySelector('.ann-marker.v');$('showNotesOption').hidden=!document.querySelector('.ann-marker.n')}
function applyLanguage(){document.documentElement.lang=uiLang;$('search').placeholder=t('viewer.search.placeholder');$('searchModeLabel').textContent=t('viewer.search.medieval');$('searchButton').title=t('viewer.search.run');$('searchClose').title=t('viewer.search.close');const basePageMode=!!states.get(baseId)?.pageMode;$('prevBase').textContent=t(basePageMode?'viewer.prev_page':'viewer.prev_base');$('nextBase').textContent=t(basePageMode?'viewer.next_page':'viewer.next_base');$('infoClose').textContent=t('viewer.info.close');$('languageLabel').textContent=t('viewer.language')+':';$('showVariantsLabel').textContent=t('viewer.show_variants');$('showVariantsOption').title=t('viewer.show_variants.tip');$('showNotesLabel').textContent=t('viewer.show_notes');$('showNotesOption').title=t('viewer.show_notes.tip');$('stats').textContent=t('viewer.stats',{witnesses:displayWitnesses.length,lines:DATA.meta.lines,variants:DATA.meta.variants});$('onlineNotice').textContent=DATA.meta.external_iiif_images?t('viewer.external_iiif_notice',{count:DATA.meta.external_iiif_images}):'';$('syncNotice').textContent=defaultSyncNotice();updateCardLanguage();renderDocument();updateSearchPanel();if(lineMode&&selectedKey)syncAll();else if(selectedSurface)selectSurface('#'+selectedSurface,false);else for(const w of displayWitnesses)renderWitness(w.id)}
function setLanguage(code){if(!I18N.catalogs?.[code])return;uiLang=code;safeStorage.setItem('tei-ui-language',code);applyLanguage()}
$('title').textContent=DATA.meta.title;$('docTitle').textContent=DATA.meta.title;$('prevBase').onclick=()=>moveBase(-1);$('nextBase').onclick=()=>moveBase(1);$('fontMinus').onclick=()=>setScale(readerScale-.1);$('fontPlus').onclick=()=>setScale(readerScale+.1);$('fontReset').onclick=()=>setScale(1);$('search').onkeydown=e=>{if(e.key==='Enter')search()};$('search').oninput=queueSearch;$('searchButton').onclick=search;$('searchPrev').onclick=()=>selectSearchResult(activeSearchHit-1);$('searchNext').onclick=()=>selectSearchResult(activeSearchHit+1);$('searchClose').onclick=()=>{$('search').value='';searchUpdate()};for(const id of ['searchUV','searchIJ','searchCT'])$(id).onchange=()=>searchUpdate(false);$('infoClose').onclick=()=>$('infoDialog').close();document.addEventListener('click',e=>{if(!e.target.closest('.ann-marker'))$('popover').classList.remove('show')});setScale(readerScale);initResizer();buildCards();populateLanguages();initMarkerToggles();selectedKey=lineMode?(lineOrder[0]||null):null;applyLanguage();if(lineMode&&selectedKey)selectLine(selectedKey,false);else if(!selectedSurface){const base=states.get(baseId),sid=base?.physical?.[0]?.p?.tei_surface_id;if(sid||firstDocumentSurface())selectSurface('#'+(firstDocumentSurface()||sid),false)};
</script></body></html>'''


def _safe_web_name(value: str) -> str:
    out = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "")).strip("._")
    return out or "witness"

def package_local_images(data: dict, project, output_dir: str | Path) -> None:
    """Copie les images locales utilisées par le viewer dans web_output/images.

    Le HTML exporté ne dépend ainsi ni de ``file://`` ni de l'emplacement
    original des photographies. Les chemins du dataset deviennent relatifs au
    fichier HTML.
    """
    out = Path(output_dir).resolve()
    warnings = data.setdefault("meta", {}).setdefault("export_warnings", [])
    witnesses = data.get("witnesses", []) or []
    # Preserve historical paths for ordinary witness IDs, and disambiguate
    # only names that collide after portable filename sanitization.
    safe_ids = [_safe_web_name(w.get("id")) for w in witnesses]
    for witness in witnesses:
        raw_id = str(witness.get("id") or "")
        wid = _safe_web_name(raw_id)
        if safe_ids.count(wid) > 1:
            wid += "_" + hashlib.sha256(raw_id.encode('utf-8')).hexdigest()[:8]
        # Les pages des vues par texte (V0.9.1.6) suivent celles de
        # l'édition ; une image déjà copiée pour ce témoin n'est pas recopiée.
        pages = list(witness.get("pages", []) or [])
        for view in (witness.get("views") or {}).values():
            pages.extend(view.get("pages", []) or [])
        copied = {}
        for i, page in enumerate(pages, 1):
            image = page.get("image") if isinstance(page.get("image"), dict) else None
            if not image or image.get("type") != "file" or not image.get("path"):
                continue
            src = Path(str(image["path"])).expanduser()
            if not src.is_absolute():
                src = project.root_dir / src
            try:
                src = src.resolve()
            except OSError:
                src = src.absolute()
            if src in copied:
                image["path"] = copied[src]
                continue
            if not src.is_file():
                warnings.append({"witness": raw_id, "page": str(page.get("id") or ""),
                                 "problem": "local_image_missing", "filename": src.name})
                remote = image.get("remote_iiif")
                image.clear()
                image.update(remote if isinstance(remote, dict) and remote.get("type") == "iiif" else {"type": "none"})
                continue
            dest_dir = out / "images" / wid
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{i:04d}_{_safe_web_name(src.name)}"
            if src != dest.resolve():
                shutil.copy2(src, dest)
            image["path"] = copied[src] = dest.relative_to(out).as_posix()


def _all_pages(witness):
    """Pages d'un témoin : celles de l'édition, puis celles de ses vues par
    texte (V0.9.1.6)."""
    yield from witness.get('pages', []) or []
    for view in (witness.get('views') or {}).values():
        yield from view.get('pages', []) or []


def make_html(data):
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    body_class = "" if data.get("meta", {}).get("has_images") else "no-images"
    geometry_js = (HERE / "geometry.js").read_text(encoding="utf-8")
    iiif_js = (HERE / "iiif.js").read_text(encoding="utf-8")
    search_js = (HERE / "fulltext_search.js").read_text(encoding="utf-8")
    return (HTML_TEMPLATE.replace("__DATA_JSON__", payload)
            .replace("__GEOMETRY_JS__", geometry_js)
            .replace("__IIIF_JS__", iiif_js)
            .replace("__SEARCH_JS__", search_js)
            .replace("__TITLE__", html.escape(str(data["meta"]["title"]), quote=True))
            .replace("__LANG__", html.escape(str(data.get("i18n", {}).get("default", "en")), quote=True))
            .replace("__BODY_CLASS__", body_class))


def generate(project_path: str | Path, output: str | Path | None = None,
             *, display_witness_ids=None):
    project = load_project(project_path)
    data, missing = build_dataset(project, display_witness_ids=display_witness_ids)
    project.web_output_dir.mkdir(parents=True, exist_ok=True)
    output = Path(output) if output else project.web_output_dir / project.web_filename
    if not output.is_absolute(): output = (project.root_dir / output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    package_local_images(data, project, output.parent)
    data['meta']['has_images'] = any(
        ((img := page.get('image') or {}).get('type') == 'file' and bool(img.get('path')))
        or (img.get('type') == 'iiif' and bool(img.get('service') or img.get('image')))
        for witness in data.get('witnesses', [])
        if witness.get('id') in data['meta']['display_witnesses']
        for page in _all_pages(witness))
    data['meta']['external_iiif_images'] = sum(
        1 for witness in data.get('witnesses', []) for page in _all_pages(witness)
        if (page.get('image') or {}).get('type') == 'iiif')
    output.write_text(make_html(data), encoding="utf-8")
    return output, missing, data


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    project_path = Path(argv[0]).resolve() if argv else ROOT / "project.xml"
    out, missing, data = generate(project_path)
    project = load_project(project_path)
    i18n = I18nManager(project.translations_dir, project.language, project.fallback_language)
    print(i18n.tr("console.viewer_generated", path=out))
    print(i18n.tr("console.viewer_stats", witnesses=len(data["witnesses"]), lines=data["meta"]["lines"]))
    if missing:
        print(i18n.tr("console.missing_pages", pages=", ".join(missing)))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
