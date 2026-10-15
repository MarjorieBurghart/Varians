# -*- coding: utf-8 -*-
"""Sources d'images génériques pour Varians.

V0.7.0 introduit une abstraction légère qui permet à une page d'utiliser :

- aucune image (``type='none'``) ;
- une image IIIF (``type='iiif'``) ;
- un fichier local (``type='file'``).

Les anciens caches d'alignement contenant un bloc ``iiif`` restent lisibles.
Les nouveaux projets peuvent utiliser un bloc ``image`` sans modifier les
informations ALTO ni les ``base_keys``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote
import re


@dataclass(frozen=True)
class PageImageSource:
    kind: str = "none"           # none | iiif | file
    label: str = ""
    width: int | None = None
    height: int | None = None
    service: str | None = None
    image_url: str | None = None
    iiif_version: int = 2
    file_path: Path | None = None
    raw: dict | None = None

    @property
    def available(self) -> bool:
        if self.kind == "iiif":
            return bool(self.service or self.image_url)
        if self.kind == "file":
            return self.file_path is not None
        return False


def _as_int(value):
    try:
        return int(value) if value not in (None, "") else None
    except (TypeError, ValueError):
        return None


def _resolve_file(path_value, project_root: str | Path | None) -> Path | None:
    if not path_value:
        return None
    p = Path(str(path_value)).expanduser()
    if not p.is_absolute() and project_root is not None:
        p = Path(project_root).expanduser().resolve() / p
    try:
        return p.resolve()
    except OSError:
        return p.absolute()


def page_image_source(page: dict, project_root: str | Path | None = None) -> PageImageSource:
    """Retourne une description normalisée de la source d'image d'une page.

    Nouveau format recommandé::

        "image": {"type": "iiif", ...}
        "image": {"type": "file", "path": "images/T1/001.jpg", ...}
        "image": {"type": "none"}

    Rétrocompatibilité : un ancien bloc ``"iiif": {...}`` est interprété comme
    une source ``iiif`` sans modifier le dictionnaire original.
    """
    page = page or {}
    raw = page.get("image")
    if isinstance(raw, dict):
        kind = str(raw.get("type") or raw.get("kind") or "").strip().lower()
        if not kind:
            # Si un bloc image nouveau omet @type mais porte des attributs IIIF,
            # rester permissif pour les premiers fichiers expérimentaux.
            kind = "iiif" if raw.get("service") or raw.get("image") or raw.get("url") else "none"
        label = str(raw.get("label") or page.get("label") or page.get("id") or "")
        width = _as_int(raw.get("width"))
        height = _as_int(raw.get("height"))
        if kind == "file":
            return PageImageSource(
                kind="file", label=label, width=width, height=height,
                file_path=_resolve_file(raw.get("path") or raw.get("file"), project_root), raw=raw,
            )
        if kind == "iiif":
            return PageImageSource(
                kind="iiif", label=label, width=width, height=height,
                service=raw.get("service"), image_url=raw.get("image") or raw.get("url") or raw.get("id"),
                iiif_version=int(raw.get("iiif_version") or raw.get("version") or 2), raw=raw,
            )
        return PageImageSource(kind="none", label=label, width=width, height=height, raw=raw)

    legacy = page.get("iiif")
    if isinstance(legacy, dict) and legacy:
        return PageImageSource(
            kind="iiif",
            label=str(legacy.get("label") or page.get("id") or ""),
            width=_as_int(legacy.get("width")),
            height=_as_int(legacy.get("height")),
            service=legacy.get("service"),
            image_url=legacy.get("image") or legacy.get("id"),
            iiif_version=int(legacy.get("iiif_version") or 2),
            raw=legacy,
        )

    return PageImageSource(kind="none", label=str(page.get("label") or page.get("id") or ""))


def page_label(page: dict, project_root: str | Path | None = None) -> str:
    src = page_image_source(page, project_root)
    return src.label or str((page or {}).get("id") or "")


def page_image_dimensions(page: dict, project_root: str | Path | None = None) -> tuple[float, float]:
    src = page_image_source(page, project_root)
    aw = float((page or {}).get("alto_width") or 1)
    ah = float((page or {}).get("alto_height") or 1)
    return float(src.width or aw), float(src.height or ah)



def image_scene_reference_crop(page: dict, pixmap_width: float, pixmap_height: float,
                               crop: dict | None = None,
                               project_root: str | Path | None = None) -> dict:
    """Geometry coordinates of the bitmap being drawn in the *source* image space.

    A IIIF Canvas may declare e.g. 3924x2704 while the image URL, a local
    working copy or a server fallback provides a 500px preview. The scene must
    scale ALTO/PAGE outlines into those 500 actual pixels, *not* treat the
    preview as a 500x350 section at native resolution. Otherwise lines live
    outside the bitmap and QGraphicsView fits a mostly empty scene.

    ``crop`` remains authoritative when the server returned a cropped region:
    its units are the same as ``page_image_dimensions``. Do not infer dimensions
    from the number of zoom clicks or from the displayed image's file size.
    """
    if crop is not None:
        return crop
    width, height = page_image_dimensions(page, project_root)
    return {"x": 0.0, "y": 0.0,
            "w": max(1.0, float(width or pixmap_width or 1)),
            "h": max(1.0, float(height or pixmap_height or 1))}


def _gallica_highres_url(service: str | None):
    if not service:
        return None
    m = re.search(r"https?://gallica\.bnf\.fr/iiif/(ark:/12148/[^/]+)/(f\d+)$", service, re.I)
    if not m:
        return None
    return f"https://gallica.bnf.fr/{m.group(1)}/{m.group(2)}.highres"


def page_image_request(page: dict, crop: dict | None, project_root: str | Path | None = None):
    """Construit une requête d'affichage pour une page.

    Le dictionnaire retourné conserve le contrat historique de Varians :
    ``url``, ``local_crop``, ``fallback_url`` et ``fallback_local_crop``.
    Pour un fichier local, l'image complète est lue puis recadrée localement.
    """
    src = page_image_source(page, project_root)
    if src.kind == "none":
        return None

    if src.kind == "file":
        remote = (src.raw or {}).get('remote_iiif')
        remote_request = (page_image_request({'image': remote}, crop, project_root)
                          if isinstance(remote, dict) and remote.get('type') == 'iiif'
                          else None)
        if src.file_path is None:
            return remote_request
        if remote_request and not src.file_path.is_file():
            # A copy may have been deleted since the last cache refresh.
            # Its underlying synchronized page remains the same physical leaf.
            return remote_request
        try:
            url = src.file_path.as_uri()
        except ValueError:
            url = "file://" + quote(str(src.file_path).replace("\\", "/"))
        return {
            "url": url,
            "local_crop": bool(crop),
            "fallback_url": remote_request.get('url') if remote_request else None,
            "fallback_local_crop": bool(remote_request and remote_request.get('local_crop')),
            "source_type": "file",
        }

    service = src.service
    if not crop:
        if service:
            # IIIF Presentation image body URLs are not guaranteed to be full
            # resolution: some institutions publish small display derivatives.
            # Prefer the Image API service, retaining the body URL as fallback.
            version = int(src.iiif_version or 2)
            quality = "native" if version == 1 else "default"
            size = "max" if version == 3 else "full"
            target = f"{str(service).rstrip('/')}/full/{size}/0/{quality}.jpg"
            fallback = src.image_url if src.image_url != target else None
            fallback = fallback or _gallica_highres_url(service)
            return {
                "url": target, "local_crop": False,
                "fallback_url": fallback, "fallback_local_crop": False,
                "source_type": "iiif",
            }
        if src.image_url:
            return {
                "url": src.image_url, "local_crop": False,
                "fallback_url": None, "fallback_local_crop": False,
                "source_type": "iiif",
            }
        return None
    if not service:
        # Une URL d'image IIIF complète peut être affichée mais pas recadrée à
        # distance ; on la charge alors entièrement et on recadre localement.
        if src.image_url:
            return {
                "url": src.image_url,
                "local_crop": True,
                "fallback_url": None,
                "fallback_local_crop": False,
                "source_type": "iiif",
            }
        return None

    version = int(src.iiif_version or 2)
    quality = "native" if version == 1 else "default"
    region = f"{crop['x']},{crop['y']},{crop['w']},{crop['h']}"

    if "gallica.bnf.fr" in service.lower():
        target_w = max(1, min(900, int(crop["w"])))
        return {
            "url": f"{service}/{region}/{target_w},/0/{quality}.jpg",
            "local_crop": False,
            "fallback_url": _gallica_highres_url(service),
            "fallback_local_crop": True,
            "source_type": "iiif",
        }

    size = "max" if version == 3 else "full"
    return {
        "url": f"{service}/{region}/{size}/0/{quality}.jpg",
        "local_crop": False,
        "fallback_url": None,
        "fallback_local_crop": False,
        "source_type": "iiif",
    }


def full_page_target(page: dict, project_root: str | Path | None = None):
    """Retourne (kind, target) pour ouvrir la page complète."""
    src = page_image_source(page, project_root)
    if src.kind == "file" and src.file_path is not None:
        if not src.file_path.exists() and isinstance((src.raw or {}).get('remote_iiif'), dict):
            old = {'image': (src.raw or {})['remote_iiif']}
            return full_page_target(old, project_root)
        return "file", src.file_path
    if src.kind == "iiif" and (src.image_url or src.service):
        return "url", (src.image_url or src.service)
    return "none", None


def normalized_image_block(page: dict, project_root: str | Path | None = None) -> dict:
    """Retourne une représentation JSON générique sans modifier *page*."""
    src = page_image_source(page, project_root)
    out = {"type": src.kind}
    if src.label:
        out["label"] = src.label
    if src.width is not None:
        out["width"] = src.width
    if src.height is not None:
        out["height"] = src.height
    if src.kind == "iiif":
        if src.service:
            out["service"] = src.service
        if src.image_url:
            out["image"] = src.image_url
        out["iiif_version"] = src.iiif_version
        for key in ("maxWidth", "maxHeight", "maxArea"):
            try:
                limit = int((src.raw or {}).get(key))
                if limit > 0: out[key] = limit
            except (TypeError, ValueError):
                pass
    elif src.kind == "file" and src.file_path is not None:
        remote = (src.raw or {}).get('remote_iiif')
        if isinstance(remote, dict):
            out['remote_iiif'] = dict(remote)
        if project_root is not None:
            try:
                out["path"] = src.file_path.relative_to(Path(project_root).resolve()).as_posix()
            except ValueError:
                out["path"] = str(src.file_path)
        else:
            out["path"] = str(src.file_path)
    return out


def _local_entries(source_value=None, source_files=None, project_root=None):
    entries = []
    for entry in source_files or []:
        path = getattr(entry, "path", None)
        if path is None and isinstance(entry, dict):
            path = entry.get("path") or entry.get("file")
        if not path:
            continue
        label = getattr(entry, "label", "") if not isinstance(entry, dict) else entry.get("label", "")
        width = getattr(entry, "width", None) if not isinstance(entry, dict) else entry.get("width")
        height = getattr(entry, "height", None) if not isinstance(entry, dict) else entry.get("height")
        surface_id = getattr(entry, "surface_id", "") if not isinstance(entry, dict) else entry.get("surface_id", entry.get("surface", ""))
        entries.append((_resolve_file(path, project_root), label or Path(str(path)).stem, _as_int(width), _as_int(height), str(surface_id or "")))
    if entries:
        return entries
    if source_value:
        base = _resolve_file(source_value, project_root)
        if base and base.is_dir():
            allowed = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
            for path in sorted((x for x in base.iterdir() if x.is_file() and x.suffix.lower() in allowed), key=lambda x: x.name.lower()):
                entries.append((path.resolve(), path.stem, None, None, ""))
    return entries



def _match_key(value):
    if not value:
        return ""
    try:
        text = Path(str(value)).stem.lower()
    except Exception:
        text = str(value).lower()
    return re.sub(r"[^a-z0-9]+", "", text)


def _associate_local_entries(pages_in, entries):
    """Associe images locales et pages par nom, puis par ordre.

    Les ALTO fournissent souvent ``sourceImageInformation/fileName``. Quand ce
    nom correspond à celui d'une photo locale, cette correspondance prime. Les
    pages restantes sont appariées dans leur ordre physique, ce qui permet à
    l'utilisateur de corriger simplement l'association avec les flèches du
    dialogue de témoin.
    """
    if not pages_in:
        return {}, set()
    entry_keys=[]
    for path,label,_w,_h,_surface in entries:
        keys={_match_key(path),_match_key(label)}-{""}
        entry_keys.append(keys)
    mapping={}; used=set()
    for pi,page in enumerate(pages_in):
        keys=set()
        for value in (page.get("alto_source_image"), page.get("label"), page.get("id")):
            key=_match_key(value)
            if key: keys.add(key)
        candidates=[ei for ei,ek in enumerate(entry_keys) if ei not in used and keys.intersection(ek)]
        if len(candidates)==1:
            mapping[pi]=candidates[0]; used.add(candidates[0])
    remaining=[i for i in range(len(entries)) if i not in used]
    cursor=0
    for pi in range(len(pages_in)):
        if pi in mapping: continue
        if cursor < len(remaining):
            mapping[pi]=remaining[cursor]; used.add(remaining[cursor]); cursor+=1
    return mapping, used

def apply_witness_image_policy(
    cache: dict,
    source_type: str = "auto",
    source_value: str | None = None,
    project_root: str | Path | None = None,
    source_files=None,
    witness_id: str | None = None,
    iiif_selection_mode: str = 'all',
    iiif_selected_canvases=(),
    iiif_ocr_links=(),
    iiif_page_links=(),
) -> dict:
    """Applique la source d'image déclarée au niveau du témoin.

    ``auto`` conserve les blocs d'images historiques du cache d'alignement.
    ``none`` neutralise les images sans toucher aux lignes ALTO/base_keys.
    ``files`` associe les fichiers locaux, dans l'ordre déclaré, aux pages
    existantes ou crée des pages autonomes lorsqu'aucun ALTO n'existe.
    """
    kind = (source_type or "auto").strip().lower()
    cache = cache or {}
    if kind == "auto":
        return cache
    if kind == "iiif":
        if not source_value or project_root is None:
            return cache
        try:
            from iiif_manifest import cache_path as iiif_cache_path, read_cache, overlay_manifest
            manifest = read_cache(iiif_cache_path(project_root, witness_id or "witness"), source_value)
            if not manifest:
                return cache
            # V0.8.5.5: never map synchronized pages to manifest ordinal indices.
            from iiif_resolution import overlay_resolved_manifest
            selected = (iiif_selected_canvases if iiif_selection_mode == 'selected' else None)
            return overlay_resolved_manifest(
                cache, manifest, witness_id or 'W', selected,
                iiif_page_links, iiif_ocr_links, project_root)
        except (FileNotFoundError, OSError):
            # Un manifest hors ligne ne bloque pas l'ouverture du projet.
            # Les erreurs de liens explicites ne doivent PAS être masquées.
            # L'ouverture d'un projet ne doit jamais être bloquée parce que le
            # cache du Manifest est absent ou corrompu. La configuration peut
            # être actualisée depuis les paramètres du témoin.
            return cache
    out = dict(cache)
    if kind == "none":
        pages = []
        for page in cache.get("pages", []) or []:
            p = dict(page)
            p.pop("iiif", None)
            old = page.get("image") if isinstance(page.get("image"), dict) else {}
            legacy = page.get("iiif") if isinstance(page.get("iiif"), dict) else {}
            neutral = {"type": "none"}
            label = old.get("label") or legacy.get("label") or page.get("label")
            if label:
                neutral["label"] = label
            p["image"] = neutral
            pages.append(p)
        out["pages"] = pages
        return out
    if kind != "files":
        return cache

    entries = _local_entries(source_value, source_files, project_root)
    pages_in = list(cache.get("pages", []) or [])
    pages = []
    mapping, used_entries = _associate_local_entries(pages_in, entries)
    for i, original in enumerate(pages_in):
        p = dict(original); p.pop("iiif", None)
        ei = mapping.get(i)
        if ei is not None:
            path, label, width, height, surface_id = entries[ei]
            block = {"type": "file", "path": str(path), "label": label or p.get("label") or p.get("id")}
            if width: block["width"] = width
            if height: block["height"] = height
            p["image"] = block
            if not surface_id:
                try:
                    from tei_facsimile import default_surface_id
                    surface_id = default_surface_id(witness_id or "W", ei + 1)
                except Exception:
                    surface_id = ""
            if surface_id:
                p["tei_surface_id"] = surface_id
            if not p.get("label"): p["label"] = block["label"]
        else:
            p["image"] = {"type": "none", "label": p.get("label") or p.get("id") or ""}
        pages.append(p)
    # Images non associées : créer des pages autonomes à la fin.
    for ei, (path, label, width, height, surface_id) in enumerate(entries):
        if ei in used_entries: continue
        block={"type":"file","path":str(path),"label":label or path.stem}
        if width: block["width"]=width
        if height: block["height"]=height
        page={"id":f"page-{len(pages)+1:04d}","label":block["label"],"image":block,"lines":[]}
        if not surface_id:
            try:
                from tei_facsimile import default_surface_id
                surface_id = default_surface_id(witness_id or "W", ei + 1)
            except Exception:
                surface_id = ""
        if surface_id: page["tei_surface_id"] = surface_id
        pages.append(page)
    # Aucun cache ALTO/image préexistant : chaque image devient une page.
    if not pages_in and entries:
        pages=[]
        for i,(path,label,width,height,surface_id) in enumerate(entries,1):
            block={"type":"file","path":str(path),"label":label or path.stem}
            if width: block["width"]=width
            if height: block["height"]=height
            page={"id":f"page-{i:04d}","label":block["label"],"image":block,"lines":[]}
            if not surface_id:
                try:
                    from tei_facsimile import default_surface_id
                    surface_id = default_surface_id(witness_id or "W", i)
                except Exception:
                    surface_id = ""
            if surface_id: page["tei_surface_id"] = surface_id
            pages.append(page)
    out["pages"] = pages
    return out




def page_navigation_items(cache: dict, project_root: str | Path | None = None):
    """Un item par page illustrée, même lorsque cette page contient de l'ALTO.

    Ce mode est utilisé tant qu'aucune vraie synchronisation TEI↔ALTO n'existe :
    l'ALTO peut alors dessiner des cadres, mais ne doit jamais déterminer une
    ligne courante ni provoquer un recadrage de l'image.
    """
    items = []
    for order, page in enumerate((cache or {}).get("pages", []) or []):
        if not page_image_source(page, project_root).available:
            continue
        items.append({
            "p": page,
            "l": {"line": None, "order": order, "_page_mode": True, "_image_only": not bool(page.get("lines"))},
            "key": f"{page.get('id') or 'page'}::page",
        })
    return items


def _same_physical_page(left: dict, right: dict) -> bool:
    """Only group lines from the *same* physical page.

    A witness may mix real UUIDs and temporary IDs. Identity is preferentially
    based on the containing page object, then on a non-empty page identifier.
    A coincidentally missing ID must never join two independent pages.
    """
    page_a, page_b = left.get("p") or {}, right.get("p") or {}
    if page_a is page_b:
        return True
    id_a, id_b = page_a.get("id"), page_b.get("id")
    return bool(id_a and id_b and str(id_a) == str(id_b))


def _adjacent_line_continuity(previous: dict, following: dict) -> bool:
    """Check physical continuity of two consecutive OCR lines.

    OCR reading order is logical, not strictly spatial: after the last line of
    a column, the following line jumps back to the top of the next column.
    Cropping the usual +/- one line around that boundary creates a rectangle
    covering most of the page. Prefer a single-line crop to an uncertain
    multi-column crop; never change alignment keys or displayed line numbers.
    """
    if not _same_physical_page(previous, following):
        return False
    a, b = previous.get("l") or {}, following.get("l") or {}
    if a.get("_page_mode") or b.get("_page_mode") or a.get("_image_only") or b.get("_image_only"):
        return False
    ba, bb = effective_line_bbox(a) or {}, effective_line_bbox(b) or {}
    try:
        xa, xb = float(ba["hpos"]), float(bb["hpos"])
        ya, yb = float(ba["vpos"]), float(bb["vpos"])
        wa, wb = float(ba["width"]), float(bb["width"])
        ha, hb = float(ba["height"]), float(bb["height"])
    except (KeyError, TypeError, ValueError, OverflowError):
        # Without usable geometry, preserve page-local context as before.
        return True
    from math import isfinite
    if not all(map(isfinite, (xa, xb, ya, yb, wa, wb, ha, hb))):
        return False
    if min(wa, wb, ha, hb) <= 0:
        return False
    # A return to the top of the page is a characteristic column transition.
    # Tolerate minor baseline slopes/OCR jitter within the same column.
    if yb < ya - max(ha, hb) * 0.65:
        return False
    # A strong horizontal discontinuity (two disjoint text strips) is another
    # boundary, including columns which begin at similar heights.
    x_overlap = max(0.0, min(xa + wa, xb + wb) - max(xa, xb))
    if x_overlap < 0.1 * min(wa, wb):
        page = previous.get("p") or {}
        try:
            page_width = float(page.get("alto_width") or 0)
        except (TypeError, ValueError):
            page_width = 0.0
        if abs((xa + wa / 2) - (xb + wb / 2)) > max(0.10 * page_width, 0.5 * max(wa, wb)):
            return False
    return True


def effective_line_bbox(line: dict) -> dict | None:
    """Return valid rectangular extents, or derive them from PAGE polygon data.

    Most importers already include a bbox, but synchronization JSON can carry
    polygon-only geometry. Never turn missing geometry into a fake frame at 0,0.
    """
    from math import isfinite
    raw = (line or {}).get('bbox') or {}
    try:
        x, y, w, h = (float(raw[k]) for k in ('hpos', 'vpos', 'width', 'height'))
        if all(map(isfinite, (x, y, w, h))) and w > 0 and h > 0:
            return {'hpos': x, 'vpos': y, 'width': w, 'height': h}
    except (KeyError, ValueError, TypeError, OverflowError):
        pass
    polygon = (line or {}).get('polygon') or []
    try:
        pts = [(float(pt[0]), float(pt[1])) for pt in polygon]
        if len(pts) < 3 or not all(isfinite(v) for xy in pts for v in xy):
            return None
        xs, ys = [pt[0] for pt in pts], [pt[1] for pt in pts]
        if max(xs) <= min(xs) or max(ys) <= min(ys):
            return None
        return {'hpos': min(xs), 'vpos': min(ys),
                'width': max(xs) - min(xs), 'height': max(ys) - min(ys)}
    except (TypeError, ValueError, OverflowError, IndexError):
        return None


def valid_matched_indices(matches, item_count: int) -> set[int]:
    """Validate secondary indices without reading-order or positional guesses."""
    valid = set()
    for raw in matches or ():
        try:
            if isinstance(raw, float) and not raw.is_integer():
                continue
            index = int(raw)
        except (TypeError, ValueError, OverflowError):
            continue
        if 0 <= index < item_count:
            valid.add(index)
    return valid


def matched_line_center(matches, previous_center: int, item_count: int) -> int | None:
    """Choose an actually matched line rather than the midpoint of indices.

    One base line may map to lines in separate columns, so the arithmetic
    midpoint may point to an unrelated physical line (with no frame to draw).
    Nearest to the previous displayed position minimizes unwanted jumps.
    """
    valid = valid_matched_indices(matches, item_count)
    if not valid:
        return None
    try:
        previous = int(previous_center)
    except (TypeError, ValueError, OverflowError):
        previous = 0
    return min(valid, key=lambda i: (abs(i - previous), i))


def visible_line_frame_indices(window_indices, current_index, synchronized_indices=()):
    """Return visible matched lines plus the current manually navigated line."""
    visible = set(window_indices or ())
    return (set(synchronized_indices or ()) & visible) | ({current_index} & visible)


def display_window_indices(items, center_index: int, radius: int = 1):
    """Choose an image crop window around a synchronized physical line.

    Keep the traditional +/- radius *within a continuous column*, but never
    let the contextual window bridge pages or a detected column transition.
    This affects viewport cropping only, not JSON base_keys or line alignment.
    """
    if not items:
        return []
    center = max(0, min(len(items) - 1, int(center_index)))
    if bool((items[center].get("l") or {}).get("_page_mode")) or bool((items[center].get("l") or {}).get("_image_only")):
        return [center]
    radius = max(0, int(radius))
    chosen = [center]
    prev = center
    for ix in range(center - 1, max(-1, center - radius - 1), -1):
        if not _adjacent_line_continuity(items[ix], items[prev]):
            break
        chosen.insert(0, ix)
        prev = ix
    prev = center
    for ix in range(center + 1, min(len(items), center + radius + 1)):
        if not _adjacent_line_continuity(items[prev], items[ix]):
            break
        chosen.append(ix)
        prev = ix
    return chosen


def image_only_items(cache: dict, project_root: str | Path | None = None):
    """Crée des items de navigation pour des pages qui n'ont aucune ligne ALTO."""
    items = []
    for order, page in enumerate((cache or {}).get("pages", []) or []):
        src = page_image_source(page, project_root)
        if not src.available:
            continue
        if page.get("lines"):
            continue
        items.append({
            "p": page,
            "l": {"line": None, "order": order, "_image_only": True},
            "key": f"{page.get('id') or 'page'}::image",
        })
    return items

