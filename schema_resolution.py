# -*- coding: utf-8 -*-
"""Résolution des schémas déclarés par ``<?xml-model?>``.

Ce module est indépendant de Qt. Il détecte les associations RELAX NG et
Schematron dans le prologue XML, résout les chemins locaux et met en cache les
schémas RNG distants. Pour un RNG distant, les ``include`` et ``externalRef``
sont récupérés récursivement et réécrits vers le cache local afin que lxml
puisse ensuite compiler le schéma avec ``no_network=True``. Depuis la
V0.9.2.3, il donne aussi les sources des règles Schematron appliquées
(``SchemaResolution.schematron_sources``).

Un document reçu peut déclarer un schéma ou des règles sur n'importe quel
site (red team, B2) : seul le site de la TEI (``trusted_schema_site``) est
consulté sans accord ; pour les autres, ``may_fetch`` décide (l'interface
demande à l'utilisatrice), y compris pour les fichiers inclus et les
redirections. Un site refusé figure dans ``SchemaResolution.refused_sites``.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import urljoin, urlparse, unquote
from urllib.request import HTTPRedirectHandler, Request, build_opener
import hashlib
import html
import os
import re
import xml.etree.ElementTree as ET

from relaxng_validation import dependency_reference

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
    # Red team (B2) : les sources hors du projet que l'utilisatrice n'a pas
    # acceptées, retirées de schematron_sources par l'interface.
    schematron_refused: tuple[SchematronSource, ...] = ()
    # Red team (B2) : les sites dont un fichier n'a pas été téléchargé, faute
    # d'accord (voir le module) ; celui qui prive du RNG déclaré.
    refused_sites: tuple[str, ...] = ()
    rng_refused_site: str = ""


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


# Site de la TEI : ses schémas sont téléchargés sans question (red team, B2).
TEI_SITE = "tei-c.org"


def schema_site(url: str) -> str:
    """Le site (nom d'hôte, en minuscules) de l'adresse *url*."""
    return (urlparse(url).hostname or "").lower()


def trusted_schema_site(url: str) -> bool:
    """Vrai pour une adresse du site de la TEI, consultée sans accord."""
    site = schema_site(url)
    return urlparse(url).scheme in {"http", "https"} and (site == TEI_SITE or site.endswith("." + TEI_SITE))


class RemoteSchemaRefused(OSError):
    """Téléchargement refusé : le site de l'adresse n'est pas autorisé."""

    def __init__(self, url: str):
        self.url, self.site = url, schema_site(url)
        super().__init__(f"Download not allowed from {self.site}: {url}")


def _check_site(url, may_fetch) -> None:
    """Lève RemoteSchemaRefused si le site de *url* n'est ni celui de la TEI
    ni accepté par *may_fetch* (``may_fetch(url) -> bool``)."""
    if not (trusted_schema_site(url) or (may_fetch is not None and may_fetch(url))):
        raise RemoteSchemaRefused(url)


class _CheckedRedirects(HTTPRedirectHandler):
    """Une redirection vers un autre site est soumise à la même règle,
    avant toute requête vers lui."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        may_fetch = getattr(req, "may_fetch", None)
        if schema_site(newurl) != schema_site(req.full_url):
            _check_site(newurl, may_fetch)
        new = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new is not None:
            new.may_fetch = may_fetch
        return new


_OPENER = build_opener(_CheckedRedirects)


def urlopen(request, timeout=None):
    """``urllib.request.urlopen``, redirections comprises dans la règle des
    sites (``_CheckedRedirects`` ; *request* porte ``may_fetch``)."""
    return _OPENER.open(request, timeout=timeout)


def _url_cache_path(url: str, cache_dir: Path) -> Path:
    """Place du schéma distant ``url`` dans le cache : son hôte, puis le
    chemin de l'adresse. Ce chemin ne sort jamais du cache (V0.9.3.3) : les
    segments vides, « . » et « .. » sont écartés, « \\ » sépare aussi, et les
    caractères qui désignent un lecteur ou sont interdits sous Windows sont
    remplacés, quel que soit l'encodage de l'adresse (« %2e%2e »…)."""
    parsed = urlparse(url)
    host = re.sub(r"[^A-Za-z0-9._-]+", "_", parsed.netloc or "remote")
    segments = [re.sub(r'[<>:"|?*\x00-\x1f]', "_", segment)
                for segment in re.split(r"[/\\]+", unquote(parsed.path or ""))
                if segment not in ("", ".", "..")]
    path = cache_dir.joinpath(host, *(segments or ["schema.rng"]))
    if parsed.query:
        digest = hashlib.sha256(parsed.query.encode("utf-8")).hexdigest()[:12]
        path = path.with_name(path.name + ".q-" + digest)
    return path


def _fetch_remote_rng(url: str, cache_dir: Path, visited: set[str] | None = None, *, force: bool = False,
                      may_fetch=None) -> tuple[Path, bool]:
    """Télécharge un RNG et ses dépendances dans un miroir local.

    Renvoie ``(path, from_cache)``. Les href RNG sont réécrits en URI ``file:``
    afin que la compilation ultérieure reste entièrement hors-ligne. Un
    fichier d'un site ni TEI ni accepté par *may_fetch* n'est ni téléchargé
    ni pris dans le cache (RemoteSchemaRefused).
    """
    visited = visited if visited is not None else set()
    if url in visited:
        return _url_cache_path(url, cache_dir), True
    visited.add(url)

    dest = _url_cache_path(url, cache_dir)
    if not dest.resolve().is_relative_to(Path(cache_dir).resolve()):
        raise ValueError(f"Chemin hors du cache des schémas : {url}")
    _check_site(url, may_fetch)
    if dest.is_file() and not force:
        return dest, True

    dest.parent.mkdir(parents=True, exist_ok=True)
    req = Request(url, headers={"User-Agent": "TEI-Manuscript-Editor/0.5.2"})
    req.may_fetch = may_fetch
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
        # RNG, Schematron (href), XSD (schemaLocation, V0.9.2.5).
        reference = dependency_reference(elem)
        if reference is None:
            continue
        attribute, href = reference
        dep_url = urljoin(final_url, href)
        parsed = urlparse(dep_url)
        if parsed.scheme not in {"http", "https"}:
            continue
        dep_path, _ = _fetch_remote_rng(dep_url, cache_dir, visited, force=force, may_fetch=may_fetch)
        elem.set(attribute, dep_path.resolve().as_uri())
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


# Règles livrées avec Varians (red team, B2) : voir ``rules_outside``.
SHIPPED_RESOURCES = Path(__file__).resolve().parent / "resources"


def _inside(key: str, root: str) -> bool:
    return key == root or key.startswith(root.rstrip(os.sep) + os.sep)


def rules_outside(sources, project_root, trusted=()) -> tuple:
    """Les sources de règles Schematron de *sources* à confirmer avant de les
    appliquer (red team, B2) : celles qui ne sont ni dans le dossier du
    projet *project_root*, ni dans le cache des schémas distants, ni parmi
    les fichiers livrés avec Varians, ni dans *trusted* (le schéma choisi
    dans les paramètres du projet). Un document reçu peut déclarer des
    règles prises n'importe où : Saxon les exécute."""
    roots = [_path_key(Path(root).expanduser().resolve())
             for root in (project_root, default_schema_cache_dir(), SHIPPED_RESOURCES) if root]
    known = {_path_key(Path(path).expanduser().resolve()) for path in trusted if path}
    found = []
    for source in sources:
        key = _path_key(Path(source).expanduser().resolve())
        if key not in known and not any(_inside(key, root) for root in roots):
            found.append(source)
    return tuple(found)


def _with_schematron_sources(resolution, declarations, xml_path, cache_root, force_refresh, fetched,
                             may_fetch=None):
    """*resolution* complétée des sources Schematron (voir ``resolve_schema``)."""
    sources, index, errors, refused = [], {}, [], list(resolution.refused_sites)

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
                    path, _cached = _fetch_remote_rng(href, cache_root, force=force_refresh, may_fetch=may_fetch)
                    fetched[href] = path
            else:
                path = _local_href_path(href, xml_path)
        except RemoteSchemaRefused as exc:
            refused.append(exc.site)
            continue
        except Exception as exc:
            errors.append((href, str(exc)))
            continue
        if not path.is_file():
            errors.append((href, f"Schematron file not found: {path}"))
            continue
        add(path.resolve(), declaration.phase)
    return replace(resolution, schematron_sources=tuple(sources), schematron_errors=tuple(errors),
                   refused_sites=tuple(dict.fromkeys(refused)))


def resolve_schema(
    *,
    mode: str,
    xml_text: str,
    xml_path: str | Path,
    project_schema: str | Path | None = None,
    cache_dir: str | Path | None = None,
    force_refresh: bool = False,
    may_fetch=None,
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

    ``may_fetch(url) -> bool`` (red team, B2) : faut-il télécharger *url*,
    hors du site de la TEI ? Sans elle, seul ce site est consulté. Un site
    refusé figure dans ``refused_sites``.
    """
    mode = (mode or "auto").strip().lower()
    xml_path = Path(xml_path).expanduser().resolve()
    declarations = detect_xml_models(xml_text)
    schematron = tuple(d for d in declarations if d.is_schematron)
    cache_root = Path(cache_dir).expanduser().resolve() if cache_dir else default_schema_cache_dir()
    fetched: dict[str, Path] = {}
    resolution = _resolve_rng(mode, declarations, schematron, xml_path, project_schema, cache_root,
                              force_refresh, fetched, may_fetch)
    if mode not in {"auto", "file"}:
        return resolution
    return _with_schematron_sources(resolution, schematron, xml_path, cache_root, force_refresh, fetched,
                                    may_fetch)


def _resolve_rng(mode, declarations, schematron, xml_path, project_schema, cache_root, force_refresh, fetched,
                 may_fetch=None):
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
            path, cached = _fetch_remote_rng(rng.href, cache_root, force=force_refresh, may_fetch=may_fetch)
        except RemoteSchemaRefused as exc:
            return SchemaResolution(mode, None, "xml-model", href=rng.href, remote=True,
                                    schematron=schematron, error=str(exc), refused_sites=(exc.site,),
                                    rng_refused_site=exc.site)
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
