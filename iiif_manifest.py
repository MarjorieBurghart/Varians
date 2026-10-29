# -*- coding: utf-8 -*-
"""Import et cache de manifests IIIF Presentation 2/3 pour Varians."""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
import json, re

CACHE_FORMAT = "varians-iiif-manifest-cache"

@dataclass(frozen=True)
class IIIFManifest:
    source: str
    label: str
    presentation_version: int
    pages: tuple[dict, ...]
    raw: dict


def _text_label(value) -> str:
    if value is None: return ""
    if isinstance(value, str): return value
    if isinstance(value, list):
        return _text_label(value[0]) if value else ""
    if isinstance(value, dict):
        # v3 language map, or v2 @value object
        if "@value" in value: return str(value.get("@value") or "")
        for key in ("fr", "en", "none", "und"):
            if key in value and value[key]: return _text_label(value[key])
        for v in value.values():
            t = _text_label(v)
            if t: return t
    return str(value)


def _service_info(service):
    if isinstance(service, list):
        service = next((x for x in service if isinstance(x, dict)), None)
    if isinstance(service, str):
        return service.rstrip('/'), 2
    if not isinstance(service, dict): return None, 2
    sid = service.get("id") or service.get("@id")
    stype = str(service.get("type") or "")
    profile = str(service.get("profile") or "")
    context = str(service.get("@context") or "")
    v = 3 if ("ImageService3" in stype or "/image/3/" in profile or "/image/3/" in context) else 2
    if "ImageService1" in stype or "/image/1/" in profile or "/image/1/" in context: v = 1
    return (str(sid).rstrip("/") if sid else None), v


def _service_limits(service):
    """Read optional advertised Image API restrictions, without network I/O."""
    if isinstance(service, list):
        service = next((x for x in service if isinstance(x, dict)), None)
    if not isinstance(service, dict):
        return {}
    out = {}
    for key in ('maxWidth', 'maxHeight', 'maxArea'):
        try:
            val = int(service.get(key))
            if val > 0: out[key] = val
        except (TypeError, ValueError):
            continue
    return out


def _first_v3_image(canvas):
    for ap in canvas.get("items") or []:
        for ann in (ap or {}).get("items") or []:
            if ann.get("motivation") not in (None, "painting"): continue
            body = ann.get("body")
            bodies = body if isinstance(body, list) else [body]
            for b in bodies:
                if isinstance(b, dict) and b.get("type") == "Choice":
                    bodies.extend(b.get("items") or [])
                    continue
                if isinstance(b, dict) and (b.get("type") == "Image" or str(b.get("format") or "").startswith("image/")):
                    return b
    return None


def _web(url):
    """*url* si c'est une adresse web (http, https), sinon None : un
    manifeste ne désigne ni un fichier de l'ordinateur, ni un partage réseau
    (« file:// », que Windows ouvrirait avec les identifiants de la session ;
    red team, D3)."""
    return url if isinstance(url, str) and url.strip().lower().startswith(("http://", "https://")) else None


def parse_manifest(data: dict, source: str = "") -> IIIFManifest:
    if isinstance(data, dict) and data.get("_format") == CACHE_FORMAT and isinstance(data.get("manifest"), dict):
        source = source or str(data.get("source") or "")
        data = data["manifest"]
    if not isinstance(data, dict): raise ValueError("Manifest IIIF invalide : objet JSON attendu.")
    pages=[]
    if isinstance(data.get("sequences"), list):
        version=2
        canvases=((data.get("sequences") or [{}])[0] or {}).get("canvases") or []
        for i,c in enumerate(canvases,1):
            resource=None
            imgs=(c or {}).get("images") or []
            if imgs: resource=(imgs[0] or {}).get("resource")
            resource=resource if isinstance(resource,dict) else {}
            service, iv = _service_info(resource.get("service"))
            service, image_url = _web(service), _web(resource.get("@id") or resource.get("id"))
            label=_text_label(c.get("label")) or f"Page {i}"
            width=resource.get("width") or c.get("width"); height=resource.get("height") or c.get("height")
            if not (service or image_url): continue
            block={"type":"iiif","label":label,"iiif_version":iv}
            if service: block["service"]=service
            block.update(_service_limits(resource.get("service")))
            if image_url: block["image"]=image_url
            if width: block["width"]=int(width)
            if height: block["height"]=int(height)
            if c.get("@id"): block["canvas"]=c.get("@id")
            pages.append({"id":f"iiif-{i:04d}","label":label,"image":block,"lines":[]})
    elif isinstance(data.get("items"), list):
        version=3
        for i,c in enumerate(data.get("items") or [],1):
            if not isinstance(c,dict) or c.get("type") not in (None,"Canvas"): continue
            body=_first_v3_image(c) or {}
            service, iv=_service_info(body.get("service"))
            service, image_url = _web(service), _web(body.get("id") or body.get("@id"))
            label=_text_label(c.get("label")) or f"Page {i}"
            width=body.get("width") or c.get("width"); height=body.get("height") or c.get("height")
            if not (service or image_url): continue
            block={"type":"iiif","label":label,"iiif_version":iv}
            if service: block["service"]=service
            block.update(_service_limits(body.get("service")))
            if image_url: block["image"]=image_url
            if width: block["width"]=int(width)
            if height: block["height"]=int(height)
            if c.get("id"): block["canvas"]=c.get("id")
            pages.append({"id":f"iiif-{i:04d}","label":label,"image":block,"lines":[]})
    else:
        raise ValueError("Ce JSON ne ressemble pas à un Manifest IIIF Presentation 2 ou 3.")
    if not pages: raise ValueError("Le Manifest IIIF ne contient aucune image exploitable.")
    return IIIFManifest(source, _text_label(data.get("label")), version, tuple(pages), data)


def fetch_manifest(source: str, timeout: int = 20) -> dict:
    s=str(source or "").strip()
    if not s: raise ValueError("URL du Manifest IIIF manquante.")
    parsed=urlparse(s)
    if parsed.scheme in {"http","https"}:
        req=Request(s, headers={"Accept":"application/ld+json, application/json;q=0.9, */*;q=0.1","User-Agent":"Varians/0.7.4"})
        with urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8-sig"))
    p=Path(parsed.path if parsed.scheme=="file" else s).expanduser()
    return json.loads(p.read_text(encoding="utf-8-sig"))


def cache_path(project_root: str|Path, witness_id: str) -> Path:
    safe=re.sub(r"[^A-Za-z0-9_.-]+","_",witness_id).strip("._") or "witness"
    return Path(project_root).resolve()/"iiif"/f"{safe}.manifest.json"


def write_cache(path: str|Path, source: str, raw: dict) -> Path:
    p=Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"_format":CACHE_FORMAT,"source":source,"manifest":raw},ensure_ascii=False,indent=2),encoding="utf-8")
    return p


def read_cache(path: str|Path, source: str|None=None) -> IIIFManifest|None:
    p=Path(path)
    if not p.is_file(): return None
    data=json.loads(p.read_text(encoding="utf-8-sig"))
    cached_source=str(data.get("source") or "") if isinstance(data,dict) and data.get("_format")==CACHE_FORMAT else ""
    if source and cached_source and cached_source != source: return None
    return parse_manifest(data, source or cached_source)


def import_manifest(source: str, cache_file: str|Path|None=None, *, force=False, raw: dict|None=None) -> IIIFManifest:
    if cache_file and not force and raw is None:
        cached=read_cache(cache_file, source)
        if cached: return cached
    payload=raw if raw is not None else fetch_manifest(source)
    result=parse_manifest(payload, source)
    if cache_file: write_cache(cache_file, source, payload)
    return result


def overlay_manifest(cache: dict, manifest: IIIFManifest) -> dict:
    out=dict(cache or {}); old=list((cache or {}).get("pages") or []); new=[]
    count=max(len(old),len(manifest.pages))
    for i in range(count):
        p=dict(old[i]) if i < len(old) else {"id":f"page-{i+1:04d}","lines":[]}
        p.pop("iiif",None)
        if i < len(manifest.pages):
            mp=manifest.pages[i]
            p["image"]=dict(mp["image"])
            p["label"]=mp.get("label") or p.get("label") or p.get("id")
        else:
            p["image"]={"type":"none","label":p.get("label") or p.get("id") or ""}
        new.append(p)
    out["pages"]=new
    meta=dict(out.get("meta") or {}); meta["iiif_manifest"]=manifest.source; meta["iiif_presentation_version"]=manifest.presentation_version; out["meta"]=meta
    return out
