# -*- coding: utf-8 -*-
"""Validation RELAX NG indépendante de Qt.

Le module valide le texte XML courant contre un fichier RNG déclaré par le
projet et retourne des erreurs structurées. Depuis la V0.5.6, les schémas
RELAX NG compilés sont mis en cache avec invalidation automatique dès que le
fichier racine ou l'une de ses dépendances locales (include/externalRef) change.

Depuis la V0.9.0.0, une édition qui inclut ses parties par XInclude est
validée assemblée (``validate_assembled``) : chaque erreur est rapportée dans
son fichier (``ValidationIssue.file``), à sa ligne.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse, unquote
import os
import threading
import xml.etree.ElementTree as StdET

try:
    from lxml import etree
except ImportError:  # pragma: no cover - dépend de l'environnement utilisateur
    etree = None


@dataclass(frozen=True)
class ValidationIssue:
    line: int
    column: int
    level: str
    message: str
    domain: str = ""
    type_name: str = ""
    # Fichier de l'erreur quand ce n'est pas le document validé : une partie
    # d'une édition assemblée (chemin absolu).
    file: str = ""


@dataclass(frozen=True)
class ValidationResult:
    available: bool
    schema_loaded: bool
    well_formed: bool
    valid: bool
    issues: tuple[ValidationIssue, ...]
    error: str = ""


@dataclass
class _CompiledSchema:
    signature: tuple
    relaxng: object
    validate_lock: threading.Lock


_RELAXNG_CACHE: dict[str, _CompiledSchema] = {}
_RELAXNG_CACHE_LOCK = threading.RLock()
_RELAXNG_CACHE_COMPILATIONS = 0
_SCHEMA_GRAPH_CACHE: dict[str, tuple[tuple[Path, ...], tuple]] = {}


def lxml_available() -> bool:
    return etree is not None


def clear_relaxng_cache(schema_path: str | Path | None = None) -> None:
    """Vide le cache des RNG compilés.

    Principalement utile aux tests et à un éventuel rafraîchissement explicite.
    L'invalidation ordinaire est automatique grâce à la signature des fichiers.
    """
    global _RELAXNG_CACHE_COMPILATIONS
    with _RELAXNG_CACHE_LOCK:
        if schema_path is None:
            _RELAXNG_CACHE.clear()
            _SCHEMA_GRAPH_CACHE.clear()
            _RELAXNG_CACHE_COMPILATIONS = 0
            return
        key = str(Path(schema_path).expanduser().resolve())
        _RELAXNG_CACHE.pop(key, None)
        _SCHEMA_GRAPH_CACHE.pop(key, None)


def relaxng_cache_info() -> dict[str, int]:
    """Informations légères destinées aux diagnostics/tests."""
    with _RELAXNG_CACHE_LOCK:
        return {
            "entries": len(_RELAXNG_CACHE),
            "compilations": int(_RELAXNG_CACHE_COMPILATIONS),
        }


def relaxng_schema_token(schema_path: str | Path) -> tuple:
    """Jeton changeant si le RNG ou une dépendance locale change."""
    return _schema_dependency_signature(Path(schema_path).expanduser().resolve())


def _issue_from_log(entry, file="") -> ValidationIssue:
    return ValidationIssue(
        line=max(0, int(getattr(entry, "line", 0) or 0)),
        column=max(0, int(getattr(entry, "column", 0) or 0)),
        level=str(getattr(entry, "level_name", "ERROR") or "ERROR"),
        message=str(getattr(entry, "message", "") or "").strip(),
        domain=str(getattr(entry, "domain_name", "") or ""),
        type_name=str(getattr(entry, "type_name", "") or ""),
        file=file,
    )


def _unique_issues(entries, file_of=None) -> tuple[ValidationIssue, ...]:
    """Erreurs du journal lxml, sans doublons ; ``file_of(entrée)`` donne le
    fichier de chacune (document assemblé)."""
    result = []
    seen = set()
    for entry in entries:
        issue = _issue_from_log(entry, file_of(entry) if file_of else "")
        key = (issue.file, issue.line, issue.column, issue.level, issue.message, issue.type_name)
        if key not in seen:
            seen.add(key)
            result.append(issue)
    return tuple(result)


def _file_uri_to_path(href: str) -> Path | None:
    parsed = urlparse(href)
    if parsed.scheme == "file":
        raw = unquote(parsed.path)
        if os.name == "nt" and raw.startswith("/") and len(raw) >= 3 and raw[2] == ":":
            raw = raw[1:]
        return Path(raw)
    return None


def _dependency_path(parent: Path, href: str) -> Path | None:
    href = (href or "").strip()
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        return _file_uri_to_path(href)
    if parsed.scheme:
        # Les dépendances HTTP du miroir distant sont réécrites en file: par
        # schema_resolution.py. Une URI réseau résiduelle n'est pas suivie ici.
        return None
    raw = unquote(parsed.path or href)
    return parent / raw


def _stat_signature(paths: tuple[Path, ...]) -> tuple:
    result = []
    for path in paths:
        try:
            st = path.stat()
            result.append((str(path), int(st.st_mtime_ns), int(st.st_size)))
        except OSError:
            result.append((str(path), -1, -1))
    return tuple(result)


def _discover_schema_dependencies(schema_path: Path) -> tuple[Path, ...]:
    visited: set[Path] = set()
    ordered: list[Path] = []

    def walk(path: Path) -> None:
        try:
            path = path.expanduser().resolve()
        except Exception:
            return
        if path in visited:
            return
        visited.add(path)
        ordered.append(path)
        try:
            root = StdET.parse(path).getroot()
        except (OSError, StdET.ParseError):
            return
        for elem in root.iter():
            tag = elem.tag if isinstance(elem.tag, str) else ""
            local = tag.rsplit("}", 1)[-1]
            if local not in {"include", "externalRef"}:
                continue
            dep = _dependency_path(path.parent, elem.get("href") or "")
            if dep is not None:
                walk(dep)

    walk(schema_path)
    return tuple(ordered)


def _schema_dependency_signature(schema_path: Path) -> tuple:
    """Signature récursive avec graphe d'include lui-même mis en cache.

    Tant qu'aucun fichier connu n'a changé, une sauvegarde ne fait que quelques
    ``stat()`` et ne reparcourt plus le XML des fichiers RNG. Si l'un d'eux est
    modifié, le graphe est redécouvert afin de détecter aussi de nouveaux href.
    """
    schema_path = schema_path.expanduser().resolve()
    key = str(schema_path)
    cached_graph = _SCHEMA_GRAPH_CACHE.get(key)
    if cached_graph is not None:
        paths, previous_signature = cached_graph
        current = _stat_signature(paths)
        if current == previous_signature:
            return current

    paths = _discover_schema_dependencies(schema_path)
    signature = _stat_signature(paths)
    _SCHEMA_GRAPH_CACHE[key] = (paths, signature)
    return signature


def _compiled_relaxng(schema_path: Path) -> _CompiledSchema:
    """Retourne un RNG compilé, en recompilant uniquement si nécessaire."""
    global _RELAXNG_CACHE_COMPILATIONS
    schema_path = schema_path.expanduser().resolve()
    signature = _schema_dependency_signature(schema_path)
    key = str(schema_path)

    with _RELAXNG_CACHE_LOCK:
        cached = _RELAXNG_CACHE.get(key)
        if cached is not None and cached.signature == signature:
            return cached

        schema_parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False)
        schema_doc = etree.parse(str(schema_path), schema_parser)
        relaxng = etree.RelaxNG(schema_doc)
        compiled = _CompiledSchema(signature, relaxng, threading.Lock())
        _RELAXNG_CACHE[key] = compiled
        _RELAXNG_CACHE_COMPILATIONS += 1
        return compiled


def _load_schema(schema_path) -> tuple[_CompiledSchema | None, ValidationResult | None]:
    """``(schéma compilé, None)``, ou ``(None, résultat d'échec)``."""
    if etree is None:
        return None, ValidationResult(False, False, False, False, (), "lxml is not installed")
    schema_path = Path(schema_path).expanduser().resolve()
    if not schema_path.is_file():
        return None, ValidationResult(True, False, False, False, (), f"Schema file not found: {schema_path}")
    try:
        return _compiled_relaxng(schema_path), None
    except (OSError, etree.XMLSyntaxError, etree.RelaxNGParseError) as exc:
        log = getattr(exc, "error_log", None)
        issues = _unique_issues(log or ())
        return None, ValidationResult(True, False, False, False, issues, str(exc))


def validate_relaxng(xml_text: str, schema_path: str | Path, *, base_url: str | Path | None = None) -> ValidationResult:
    """Valide *xml_text* contre *schema_path*.

    La compilation du schéma est mise en cache. Le document XML reste reparsé à
    chaque validation, ce qui est nécessaire pour valider la révision courante,
    mais ce coût est très inférieur à la recompilation d'un gros RNG TEI.
    """
    compiled, failure = _load_schema(schema_path)
    if failure is not None:
        return failure

    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)
        base = str(Path(base_url).expanduser().resolve()) if base_url else None
        document = etree.fromstring(xml_text.encode("utf-8"), parser=parser, base_url=base)
    except etree.XMLSyntaxError as exc:
        issues = _unique_issues(exc.error_log or ())
        if not issues:
            issues = (ValidationIssue(
                line=max(0, int(getattr(exc, "lineno", 0) or 0)),
                column=max(0, int(getattr(exc, "offset", 0) or 0)),
                level="ERROR",
                message=str(exc),
                domain="PARSER",
                type_name="XMLSyntaxError",
            ),)
        return ValidationResult(True, True, False, False, issues, str(exc))

    # error_log appartient à l'objet RelaxNG et reflète sa dernière validation :
    # protéger validate()+lecture du log rend le cache sûr si un worker est
    # introduit ou utilisé plus tard.
    with compiled.validate_lock:
        valid = bool(compiled.relaxng.validate(document))
        issues = () if valid else _unique_issues(compiled.relaxng.error_log)
    return ValidationResult(True, True, True, valid, issues, "")


# Problèmes d'assemblage (xml_assembly.AssemblyProblem.code) ; le panneau
# RELAX NG les traduit d'après ``type_name``.
_XINCLUDE_MESSAGES = {
    "missing": "Included file not found: {detail}",
    "fallback": "Included file not found (xi:fallback is not supported): {detail}",
    "circular": "Circular inclusion: {detail}",
    "parse_text": 'parse="text" inclusions are not supported',
    "parse_invalid": "Invalid parse value: {detail}",
    "href_unsupported": "Unsupported href, a local file is expected: {detail}",
    "xpointer_unsupported": "Unsupported xpointer: {detail}",
    "xpointer_not_found": "No element matches the xpointer: {detail}",
}


def validate_assembled(master_text: str, schema_path: str | Path, master_path: str | Path,
                       parts: dict | None = None) -> ValidationResult:
    """Valide l'édition *master_text* assemblée avec ses parties (XInclude).

    *parts* : ``{chemin: texte}`` des parties ouvertes, prioritaire sur les
    fichiers. Les erreurs d'une partie portent son chemin (``file``) et sa
    ligne ; celles de l'édition, ``file`` vide. Une édition mal formée donne
    le même résultat que ``validate_relaxng``.
    """
    if etree is None:
        return ValidationResult(False, False, False, False, (), "lxml is not installed")
    # Importé ici : xml_assembly exige lxml, dont ce module se passe à l'import.
    from xml_assembly import assemble

    assembly = assemble(master_text, master_path, parts)
    if assembly.root is None:
        return validate_relaxng(master_text, schema_path, base_url=master_path)
    compiled, failure = _load_schema(schema_path)
    if failure is not None:
        return failure

    def file_name(path):
        return "" if path == assembly.master else str(path)

    problems = tuple(ValidationIssue(
        line=problem.line, column=0, level="ERROR",
        message=problem.detail if problem.code == "malformed" else
        _XINCLUDE_MESSAGES.get(problem.code, problem.code).format(detail=problem.detail),
        domain="XINCLUDE", type_name=problem.code, file=file_name(problem.file),
    ) for problem in assembly.problems)

    tree = assembly.root.getroottree()

    def file_of(entry):
        path = getattr(entry, "path", None)
        try:
            found = tree.xpath(path) if path else []
        except etree.XPathError:
            found = []
        if found and isinstance(found[0], etree._Element):
            return file_name(assembly.origin(found[0]))
        return ""

    with compiled.validate_lock:
        valid = bool(compiled.relaxng.validate(tree))
        issues = () if valid else _unique_issues(compiled.relaxng.error_log, file_of)
    return ValidationResult(True, True, True, valid and not problems, problems + issues, "")


def validate_document(xml_text: str, schema_path: str | Path, base_url: str | Path | None = None,
                      parts: dict | None = None) -> ValidationResult:
    """Point d'entrée commun au processus de validation et au repli dans
    Varians : l'édition est assemblée quand *parts* est donné (même vide)."""
    if parts is None:
        return validate_relaxng(xml_text, schema_path, base_url=base_url)
    return validate_assembled(xml_text, schema_path, base_url or "document.xml", parts)
