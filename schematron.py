# -*- coding: utf-8 -*-
"""Règles Schematron (V0.9.2.3), sans Qt.

Une *source* de règles est un fichier :

- un fichier Schematron (racine ``sch:schema``, ISO Schematron), pris tel
  quel, avec ses ``sch:include`` ;
- un autre schéma, en pratique un RNG : ses règles intégrées (``sch:ns``,
  ``sch:let``, ``sch:pattern``, ``sch:diagnostics`` hors d'un élément
  Schematron), y compris celles des RNG inclus, réunies dans un
  ``sch:schema queryBinding="xslt2"``. ``tei_all.rng`` en contient 91 groupes ;
  un RNG sans règles n'en donne aucune (``rules_text`` rend None).

SchXslt2 (``resources/schxslt2/transpile.xsl``, voir son LISEZMOI) transforme
la Schematron en feuille XSLT 3.0, que Saxon (``saxonche``) compile ; la
feuille compilée reste en cache (``compiled``) tant que la source et les
fichiers qu'elle inclut ne changent pas. Toutes les règles sont évaluées en
XPath 3.1, quel que soit leur ``queryBinding`` ; la phase est celle de
``defaultPhase``, sinon toutes les règles.

``validate(tree, sources, file_of)`` applique les règles à l'arbre lxml
(celui que le RNG vient de valider, l'édition assemblée pour une édition en
parties) et rend un ``SchematronReport`` :

- ``issues`` : un ``ValidationIssue`` du domaine ``SCHEMATRON`` par message
  (``failed-assert`` ou ``successful-report``) : la ligne de l'élément
  concerné (celle de son élément pour un attribut ou un texte), le fichier
  donné par ``file_of(élément)`` (la partie d'une édition assemblée), le
  niveau d'après ``@severity``, sinon ``@role`` (``ERROR``, ``WARNING``,
  ``INFO``), le texte aux espaces normalisés, et dans ``type_name``
  l'identifiant de l'assertion, sinon de la règle ou du groupe de règles ;
- ``rules`` : les sources dont les règles ont été appliquées ;
- ``errors`` : ``(source, détail)`` des sources dont les règles sont
  incorrectes (fichier absent ou mal formé, XPath fautif, erreur à
  l'exécution) : c'est le schéma qui est en faute, pas le document ;
- ``error`` : ``saxon_missing`` si des règles existent mais que Saxon n'est
  pas installé.

Le détail d'une règle incorrecte vient du message de Saxon, et de sa sortie
d'erreur quand le processus l'écrit dans un fichier
(``relaxng_validation.STDERR_LOG``, voir validation_worker) : sous Windows,
Saxon n'écrit qu'à cet endroit l'expression fautive.
"""
from __future__ import annotations

import copy
import importlib.util
import os
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from lxml import etree

from project_config import APPLICATION_ROOT
from relaxng_validation import (STDERR_LOG, ValidationIssue, _discover_schema_dependencies,
                                _schema_dependency_signature)

SCH_NS = "http://purl.oclc.org/dsdl/schematron"
SVRL_NS = "http://purl.oclc.org/dsdl/svrl"
SCHXSLT_NS = "http://dmaus.name/ns/2023/schxslt"
SCHXSLT_DIR = APPLICATION_ROOT / "resources" / "schxslt2"
TRANSPILER = SCHXSLT_DIR / "transpile.xsl"
# Paramètres statiques de transpile.xsl : un rapport limité aux messages, et
# une erreur d'exécution écrite dans le rapport plutôt qu'un arrêt de Saxon.
_TRANSPILER_PARAMETERS = {"compact-report": True, "terminate-validation-on-error": False}
# Éléments Schematron repris d'un schéma qui intègre ses règles.
_EMBEDDED = ("ns", "let", "pattern", "diagnostics")
_WARNING_LEVELS = {"warning", "warn", "nonfatal"}
_INFO_LEVELS = {"info", "information", "informational"}
_MESSAGES = (f"{{{SVRL_NS}}}failed-assert", f"{{{SVRL_NS}}}successful-report")
_ELEMENT_STEP = re.compile(r"Q\{([^}]*)\}([^/\[]+)\[(\d+)\]")
_STEPS = re.compile(r"Q\{[^}]*\}[^/\[]+\[\d+\]|[^/]+")
_SAXON_EXPRESSION = re.compile(r"Error in \{(.*)\} at char")
# Attributs Schematron qui contiennent une expression XPath.
_EXPRESSION_ATTRIBUTES = ("test", "context", "select", "value", "subject", "path")
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"


@dataclass(frozen=True)
class SchematronReport:
    issues: tuple[ValidationIssue, ...] = ()
    rules: tuple[str, ...] = ()
    errors: tuple[tuple[str, str], ...] = ()
    error: str = ""


@dataclass(frozen=True)
class _Compiled:
    """Une source compilée : ``executable`` est None si elle n'a pas de
    règles, ou si elles sont incorrectes (``error``)."""
    signature: tuple
    executable: object = None
    error: str = ""
    saxon_missing: bool = False


class _SaxonMissing(Exception):
    pass


_CACHE: dict[str, _Compiled] = {}
# Saxon (un processeur par processus) n'est appelé que sous ce verrou.
_LOCK = threading.RLock()
_COMPILATIONS = 0
_TRANSPILER = None


def available() -> bool:
    """Vrai si Saxon (paquet ``saxonche``) est installé ; il n'est pas chargé."""
    return importlib.util.find_spec("saxonche") is not None


def clear_cache() -> None:
    """Oublie les sources compilées (pour les tests ; l'invalidation
    ordinaire suit la signature des fichiers)."""
    global _COMPILATIONS
    with _LOCK:
        _CACHE.clear()
        _COMPILATIONS = 0


def cache_info() -> dict[str, int]:
    with _LOCK:
        return {"entries": len(_CACHE), "compilations": _COMPILATIONS}


def _parse(path):
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    return etree.parse(str(path), parser)


def rules_text(path) -> str | None:
    """La Schematron de la source *path* (voir le module) ; None si elle n'a
    pas de règles. Une source absente ou mal formée lève ``OSError`` ou
    ``etree.XMLSyntaxError``."""
    path = Path(path).expanduser().resolve()
    tree = _parse(path)
    if tree.getroot().tag == f"{{{SCH_NS}}}schema":
        return etree.tostring(tree, encoding="unicode")
    schema = etree.Element(f"{{{SCH_NS}}}schema", nsmap={"sch": SCH_NS}, queryBinding="xslt2")
    found = {name: [] for name in _EMBEDDED}
    prefixes = set()
    for source in _discover_schema_dependencies(path):
        try:
            source_tree = tree if source == path else _parse(source)
        except (OSError, etree.XMLSyntaxError):
            continue          # le RNG lui-même le signale
        for element in source_tree.iter(f"{{{SCH_NS}}}*"):
            parent = element.getparent()
            name = etree.QName(element).localname
            if name not in found or (parent is not None and etree.QName(parent).namespace == SCH_NS):
                continue
            if name == "ns":
                if element.get("prefix") in prefixes:
                    continue
                prefixes.add(element.get("prefix"))
                found["ns"].append(etree.Element(f"{{{SCH_NS}}}ns", prefix=element.get("prefix") or "",
                                                 uri=element.get("uri") or ""))
            else:
                clone = copy.deepcopy(element)
                clone.tail = None
                found[name].append(clone)
    if not found["pattern"]:
        return None
    for name in _EMBEDDED:
        schema.extend(found[name])
    return etree.tostring(schema, encoding="unicode")


def _processor():
    """Le processeur Saxon du processus, partagé avec les scénarios de
    transformation (SaxonC n'en veut qu'un)."""
    from xslt_engines import TransformError, _saxon_processor
    try:
        return _saxon_processor()
    except TransformError as exc:
        raise _SaxonMissing() from exc


def _transpiler():
    global _TRANSPILER
    if _TRANSPILER is None:
        processor = _processor()
        compiler = processor.new_xslt30_processor()
        for name, value in _TRANSPILER_PARAMETERS.items():
            compiler.set_parameter(f"{{{SCHXSLT_NS}}}{name}", processor.make_boolean_value(value))
        _TRANSPILER = compiler.compile_stylesheet(stylesheet_file=str(TRANSPILER))
    return _TRANSPILER


def _expression_site(path, expression):
    """``(fichier, ligne)`` de l'élément Schematron de *path* (ou d'un
    fichier inclus) dont une expression figure dans *expression* (SchXslt2
    entoure le test d'une assertion de ``not(…)``) ; la plus longue. Saxon
    abrège une longue expression (« … g... ») : une expression qui commence
    par ce qui en reste lui correspond aussi. Espaces normalisés."""
    expression = " ".join(expression.split())
    truncated = expression.endswith("...")
    stem = expression[:-3] if truncated else expression
    core = stem[4:] if stem.startswith("not(") else stem
    best = None
    for source in _discover_schema_dependencies(path):
        try:
            tree = _parse(source)
        except (OSError, etree.XMLSyntaxError):
            continue
        for element in tree.iter(f"{{{SCH_NS}}}*"):
            for name in _EXPRESSION_ATTRIBUTES:
                value = " ".join((element.get(name) or "").split())
                if value and value in stem:
                    score = len(value)
                elif truncated and core and value.startswith(core):
                    score = len(core)
                else:
                    continue
                if best is None or score > best[0]:
                    best = (score, source, element.sourceline or 0)
    return best[1:] if best else None


def _stderr_size():
    """Taille actuelle du fichier de la sortie d'erreur (None sans fichier)."""
    try:
        return os.path.getsize(os.environ[STDERR_LOG])
    except (KeyError, OSError):
        return None


def _stderr_since(start):
    """Ce que Saxon a écrit sur la sortie d'erreur depuis *start*."""
    if start is None:
        return ""
    try:
        with open(os.environ[STDERR_LOG], "rb") as stream:
            stream.seek(start)
            return stream.read().decode("utf-8", errors="replace")
    except (KeyError, OSError):
        return ""


def _saxon_text(exc, path=None, stderr="") -> str:
    """Le message d'une erreur de Saxon (de sa sortie d'erreur *stderr*,
    sinon de l'exception), « fichier:ligne: message » si l'expression
    fautive est retrouvée dans la source *path*, sinon suivi de
    l'expression ; le lieu que donne Saxon est dans la feuille produite par
    SchXslt2, il n'est pas repris."""
    from xslt_engines import _saxon_blocks
    blocks = [block for block in _saxon_blocks(stderr) if not block[0].startswith("Warning")]
    blocks = blocks or _saxon_blocks(str(exc).strip())
    if not blocks:
        return type(exc).__name__
    header, detail = blocks[0][0], " ".join(" ".join(blocks[0][1:]).split())
    match = _SAXON_EXPRESSION.search(header)
    if not (detail and match):
        return detail or " ".join(header.split())
    site = _expression_site(path, match.group(1)) if path is not None else None
    if site is not None:
        return f"{site[0].name}:{site[1]}: {detail}"
    return f"{detail} : {match.group(1)}"


def _with_base(stylesheet, base) -> str:
    """La feuille produite par SchXslt2, avec l'adresse de la source pour
    URI de base : Saxon la compile depuis son texte, qui garde l'expression
    fautive dans ses messages d'erreur (pas depuis un nœud)."""
    root = etree.fromstring(stylesheet.encode("utf-8"), etree.XMLParser(huge_tree=True))
    root.set(_XML_BASE, base)
    return etree.tostring(root, encoding="unicode")


def _compile(path, signature) -> _Compiled:
    global _COMPILATIONS
    if not path.is_file():
        return _Compiled(signature, error=f"File not found: {path}")
    try:
        text = rules_text(path)
    except (OSError, etree.XMLSyntaxError) as exc:
        return _Compiled(signature, error=" ".join(str(exc).split()))
    if text is None:
        return _Compiled(signature)
    try:
        processor = _processor()
        transpiler = _transpiler()
    except _SaxonMissing:
        return _Compiled(signature, saxon_missing=True)
    from saxonche import PySaxonApiError
    base = path.as_uri()
    _COMPILATIONS += 1
    start = _stderr_size()
    try:
        builder = processor.new_document_builder()
        builder.set_base_uri(base)
        stylesheet = transpiler.transform_to_string(xdm_node=builder.parse_xml(xml_text=text))
        executable = processor.new_xslt30_processor().compile_stylesheet(
            stylesheet_text=_with_base(stylesheet, base))
    except PySaxonApiError as exc:
        return _Compiled(signature, error=_saxon_text(exc, path, _stderr_since(start)))
    return _Compiled(signature, executable)


def compiled(path) -> _Compiled:
    """La source *path* compilée, d'après le cache si aucun fichier n'a
    changé."""
    path = Path(path).expanduser().resolve()
    key = str(path)
    signature = _schema_dependency_signature(path)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is None or cached.signature != signature:
            cached = _CACHE[key] = _compile(path, signature)
        return cached


def _level(severity, role) -> str:
    value = (severity or role or "").strip().lower()
    if value in _WARNING_LEVELS:
        return "WARNING"
    if value in _INFO_LEVELS:
        return "INFO"
    return "ERROR"


def _element_at(root, location):
    """L'élément désigné par l'emplacement SVRL (``fn:path()`` :
    ``/Q{ns}TEI[1]/Q{ns}text[1]/@when``) ; pour un attribut, un texte ou
    un commentaire, son élément."""
    element = None
    for step in _STEPS.findall(location):
        match = _ELEMENT_STEP.fullmatch(step)
        if match is None:
            break
        namespace, name, index = match.group(1), match.group(2), int(match.group(3))
        tag = f"{{{namespace}}}{name}" if namespace else name
        candidates = [root] if element is None else list(element)
        candidates = [candidate for candidate in candidates if candidate.tag == tag]
        if index > len(candidates):
            break
        element = candidates[index - 1]
    return element


def _issues(report, root, file_of):
    for item in report.iter(*_MESSAGES):
        element = _element_at(root, item.get("location") or "")
        text = item.find(f"{{{SVRL_NS}}}text")
        yield ValidationIssue(
            line=(element.sourceline or 0) if element is not None else 0,
            column=0,
            level=_level(item.get("severity"), item.get("role")),
            message=" ".join("".join(text.itertext()).split()) if text is not None else "",
            domain="SCHEMATRON",
            type_name=(item.get("id") or item.get("ruleId") or item.get("patternId")
                       or item.get("groupId") or ""),
            file=(file_of(element) if file_of is not None and element is not None else "") or "",
        )


def validate(tree, sources, file_of=None) -> SchematronReport:
    """Applique les règles de *sources* à *tree* (voir le module)."""
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    issues, rules, errors = [], [], []
    seen = set()
    document = None
    with _LOCK:
        for source in sources:
            entry = compiled(source)
            if entry.saxon_missing:
                return SchematronReport(error="saxon_missing")
            if entry.error:
                errors.append((str(source), entry.error))
                continue
            if entry.executable is None:
                continue
            from saxonche import PySaxonApiError
            start = _stderr_size()
            try:
                if document is None:
                    builder = _processor().new_document_builder()
                    url = root.getroottree().docinfo.URL
                    if url and "://" not in url:
                        builder.set_base_uri(Path(url).resolve().as_uri())
                    document = builder.parse_xml(xml_text=etree.tostring(root.getroottree(), encoding="unicode"))
                svrl = entry.executable.transform_to_string(xdm_node=document)
            except PySaxonApiError as exc:
                errors.append((str(source), _saxon_text(exc, Path(source), _stderr_since(start))))
                continue
            report = etree.fromstring(svrl.encode("utf-8"))
            failures = report.findall(f"{{{SVRL_NS}}}error")
            if failures:
                errors.append((str(source), " ; ".join(
                    " ".join(f"{failure.get('code') or ''} {''.join(failure.itertext())}".split())
                    for failure in failures)))
                continue
            rules.append(str(source))
            for issue in _issues(report, root, file_of):
                key = (issue.file, issue.line, issue.level, issue.message, issue.type_name)
                if key not in seen:
                    seen.add(key)
                    issues.append(issue)
    return SchematronReport(tuple(issues), tuple(rules), tuple(errors))
