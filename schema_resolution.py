# -*- coding: utf-8 -*-
"""Résolution des schémas déclarés par ``<?xml-model?>``.

Ce module est indépendant de Qt. Il détecte les associations RELAX NG et
Schematron dans le prologue XML, résout les chemins locaux et met en cache les
schémas RNG distants. Pour un RNG distant, les ``include`` et ``externalRef``
sont récupérés récursivement et réécrits vers le cache local afin que lxml
puisse ensuite compiler le schéma avec ``no_network=True``. Depuis la
V0.9.2.3, il donne aussi les sources des règles Schematron appliquées
(``SchemaResolution.schematron_sources``).
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import Request, urlopen
import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET

RELAXNG_NS = "http://relaxng.org/ns/structure/1.0"
SCHEMATRON_NS = "http://purl.oclc.org/dsdl/schematron"
_XML_MODEL_RE = re.compile(r"<\?xml-model\s+(.*?)\?>", re.I | re.S)
_ATTR_RE = re.compile(r"([A-Za-z_:][\w:.-]*)\s*=\s*(['\"])(.*?)\2", re.S)


@dataclass(frozen=True)
class XmlModelDeclaration:
    href: str
    schematypens: str = ""
    type: str = ""
    title: str = ""
    group: str = ""
    phase: str = ""

    @property
    def is_relaxng(self) -> bool:
        return self.schematypens.rstrip("/") == RELAXNG_NS.rstrip("/")

    @property
    def is_schematron(self) -> bool:
        return self.schematypens.rstrip("/") == SCHEMATRON_NS.rstrip("/")


@dataclass(frozen=True)
class SchematronSource:
    """Une source de règles Schematron (V0.9.2.4) : un fichier, et la phase
    que demande sa déclaration (``phase`` de ``xml-model`` ; vide : celle
    par défaut). Elle s'emploie comme un chemin (``Path(source)``)."""
    path: Path
    phase: str = ""

    def __fspath__(self):
        return os.fspath(self.path)

    def __str__(self):
        return str(self.path)


@dataclass(frozen=True)
class SchemaResolution:
    mode: str
    schema_path: Path | None
    source: str
    href: str = ""
    remote: bool = False
    from_cache: bool = False
    schematron: tuple[XmlModelDeclaration, ...] = ()
    error: str = ""
    # V0.9.2.3 : voir resolve_schema.
    schematron_sources: tuple[SchematronSource, ...] = ()
    schematron_errors: tuple[tuple[str, str], ...] = ()


def detect_xml_models(xml_text: str) -> tuple[XmlModelDeclaration, ...]:
    """Retourne les instructions ``xml-model`` même si le corps XML est cassé."""
    declarations = []
    for match in _XML_MODEL_RE.finditer(xml_text or ""):
        attrs = {
            name: html.unescape(value.strip())
            for name, _quote, value in _ATTR_RE.findall(match.group(1))
        }
        href = attrs.get("href", "").strip()
        if href:
            declarations.append(XmlModelDeclaration(
                href=href,
                schematypens=attrs.get("schematypens", "").strip(),
                type=attrs.get("type", "").strip(),
                title=attrs.get("title", "").strip(),
                group=attrs.get("group", "").strip(),
                phase=attrs.get("phase", "").strip(),
            ))
    return tuple(declarations)


def default_schema_cache_dir() -> Path:
    override = os.environ.get("TEI_EDITOR_SCHEMA_CACHE", "").strip()
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "TEIManuscriptEditor" / "schema_cache"
    return Path.home() / ".cache" / "tei-manuscript-editor" / "schema_cache"


def _url_cache_path(url: str, cache_dir: Path) -> Path:
    parsed = urlparse(url)
    host = re.sub(r"[^A-Za-z0-9._-]+", "_", parsed.netloc or "remote")
    rel = unquote(parsed.path or "/schema.rng").lstrip("/") or "schema.rng"
    path = cache_dir / host / rel
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:12]
        path = path.with_name(path.name + ".q-" + digest)
    return path


def _fetch_remote_rng(url: str, cache_dir: Path, visited: set[str] | None = None, *, force: bool = False) -> tuple[Path, bool]:
    """Télécharge un RNG et ses dépendances dans un miroir local.

    Renvoie ``(path, from_cache)``. Les href RNG sont réécrits en URI ``file:``
    afin que la compilation ultérieure reste entièrement hors-ligne.
    """
    visited = visited if visited is not None else set()
    if url in visited:
        return _url_cache_path(url, cache_dir), True
    visited.add(url)

    dest = _url_cache_path(url, cache_dir)
    if dest.is_file() and not force:
        return dest, True

    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "TEI-Manuscript-Editor/0.5.2"})
    with urlopen(req, timeout=25) as response:
        data = response.read()
        final_url = response.geturl() or url

    try:
        root = ET.fromstring(data)
    except ET.ParseError:
        # Laisser lxml produire le diagnostic détaillé plus tard.
        dest.write_bytes(data)
        return dest, False

    changed = False
    for elem in root.iter():
        local = elem.tag.rsplit("}", 1)[-1] if isinstance(elem.tag, str) else ""
        if local not in {"include", "externalRef"}:
            continue
        href = (elem.get("href") or "").strip()
        if not href:
            continue
        dep_url = urljoin(final_url, href)
        parsed = urlparse(dep_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        dep_path, _ = _fetch_remote_rng(dep_url, cache_dir, visited, force=force)
        elem.set("href", dep_path.resolve().as_uri())
        changed = True

    if changed:
        ET.ElementTree(root).write(dest, encoding="utf-8", xml_declaration=True)
    else:
        dest.write_bytes(data)
    return dest, False


def _local_href_path(href: str, xml_path: Path) -> Path:
    parsed = urlparse(href)
    if parsed.scheme == "file":
        # Windows file:///C:/... et POSIX sont gérés par urllib + Path.
        raw = unquote(parsed.path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
        return Path(raw).expanduser().resolve()
    return (xml_path.parent / unquote(href)).expanduser().resolve()


def _path_key(path) -> str:
    """Clé de comparaison d'un chemin (comme ``xml_assembly.path_key``)."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _with_schematron_sources(resolution, declarations, xml_path, cache_root, force_refresh, fetched):
    """*resolution* complétée des sources Schematron (voir ``resolve_schema``)."""
    sources, index, errors = [], {}, []

    def add(path, phase=""):
        key = _path_key(path)
        if key not in index:
            index[key] = len(sources)
            sources.append(SchematronSource(path, phase))
        elif phase:                                  # la phase déclarée l'emporte
            sources[index[key]] = SchematronSource(sources[index[key]].path, phase)

    if resolution.schema_path is not None:
        add(resolution.schema_path)
    for declaration in declarations:
        href = declaration.href
        try:
            if urlparse(href).scheme in {"http", "https"}:
                path = fetched.get(href)
                if path is None:
                    path, _cached = _fetch_remote_rng(href, cache_root, force=force_refresh)
                    fetched[href] = path
            else:
                path = _local_href_path(href, xml_path)
        except Exception as exc:
            errors.append((href, str(exc)))
            continue
        if not path.is_file():
            errors.append((href, f"Schematron file not found: {path}"))
            continue
        add(path.resolve(), declaration.phase)
    return replace(resolution, schematron_sources=tuple(sources), schematron_errors=tuple(errors))


def resolve_schema(
    *,
    mode: str,
    xml_text: str,
    xml_path: str | Path,
    project_schema: str | Path | None = None,
    cache_dir: str | Path | None = None,
    force_refresh: bool = False,
) -> SchemaResolution:
    """Résout le RNG à utiliser selon le mode de projet.

    ``mode`` vaut ``auto`` (xml-model), ``file`` (schéma explicite) ou ``none``.
    Les déclarations Schematron sont toujours détectées (``schematron``).

    Depuis la V0.9.2.3, ``schematron_sources`` donne, en modes ``auto`` et
    ``file``, les fichiers dont les règles Schematron seront appliquées
    (``SchematronSource`` : chemin et phase, V0.9.2.4), sans doublon ; une
    déclaration qui donne une phase l'impose à la source du même fichier : le
    RNG employé (``schema_path``, ses règles intégrées), puis
    chaque déclaration Schematron (RNG ou ``.sch``), locale ou distante (mise
    en cache comme un RNG distant, avec ses ``sch:include``). Une même adresse
    n'est téléchargée qu'une fois : la déclaration Schematron de la TEI
    désigne le même ``tei_all.rng`` que son RNG. Une déclaration introuvable
    va dans ``schematron_errors`` (``(href, erreur)``), sans arrêter le reste.
    """
    mode = (mode or "auto").strip().lower()
    xml_path = Path(xml_path).expanduser().resolve()
    declarations = detect_xml_models(xml_text)
    schematron = tuple(d for d in declarations if d.is_schematron)
    cache_root = Path(cache_dir).expanduser().resolve() if cache_dir else default_schema_cache_dir()
    fetched: dict[str, Path] = {}
    resolution = _resolve_rng(mode, declarations, schematron, xml_path, project_schema, cache_root,
                              force_refresh, fetched)
    if mode not in {"auto", "file"}:
        return resolution
    return _with_schematron_sources(resolution, schematron, xml_path, cache_root, force_refresh, fetched)


def _resolve_rng(mode, declarations, schematron, xml_path, project_schema, cache_root, force_refresh, fetched):
    if mode == "none":
        return SchemaResolution(mode, None, "none", schematron=schematron)

    if mode == "file":
        if project_schema is None:
            return SchemaResolution(mode, None, "project", schematron=schematron,
                                    error="No project RELAX NG schema is configured")
        path = Path(project_schema).expanduser().resolve()
        if not path.is_file():
            return SchemaResolution(mode, None, "project", schematron=schematron,
                                    error=f"Schema file not found: {path}")
        return SchemaResolution(mode, path, "project", href=str(path), schematron=schematron)

    if mode != "auto":
        return SchemaResolution(mode, None, "unknown", schematron=schematron,
                                error=f"Unknown schema mode: {mode}")

    rng = next((d for d in declarations if d.is_relaxng), None)
    if rng is None:
        return SchemaResolution(mode, None, "xml-model", schematron=schematron)

    parsed = urlparse(rng.href)
    if parsed.scheme in {"http", "https"}:
        try:
            path, cached = _fetch_remote_rng(rng.href, cache_root, force=force_refresh)
        except Exception as exc:
            return SchemaResolution(mode, None, "xml-model", href=rng.href, remote=True,
                                    schematron=schematron, error=str(exc))
        fetched[rng.href] = path
        return SchemaResolution(mode, path, "xml-model", href=rng.href, remote=True,
                                from_cache=cached, schematron=schematron)

    try:
        path = _local_href_path(rng.href, xml_path)
    except Exception as exc:
        return SchemaResolution(mode, None, "xml-model", href=rng.href,
                                schematron=schematron, error=str(exc))
    if not path.is_file():
        return SchemaResolution(mode, None, "xml-model", href=rng.href,
                                schematron=schematron, error=f"Schema file not found: {path}")
    return SchemaResolution(mode, path, "xml-model", href=rng.href, schematron=schematron)
