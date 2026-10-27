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
XPath 3.1, quel que soit leur ``queryBinding``. Une source est un chemin,
ou (V0.9.2.4) un ``SchematronSource`` ou un couple ``(chemin, phase)`` : la
phase demandée, sinon celle de ``defaultPhase``, sinon toutes les règles
(``#ALL``) ; une phase qui n'existe pas dans le fichier est une erreur des
règles.

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
- ``errors`` : un ``ValidationIssue`` du domaine ``SCHEMATRON_RULES`` par
  source dont les règles sont incorrectes : c'est le schéma qui est en
  faute, pas le document. ``file`` et ``line`` : le fichier des règles et la
  ligne de la règle fautive (0 si elle est inconnue) ; ``type_name`` : un
  code (``missing``, ``malformed``, ``phase``, ``xpath``, ``compile``,
  ``runtime``) ; ``message`` : le détail de lxml ou de Saxon (pour
  ``phase``, la phase demandée puis, après une tabulation, celles du
  fichier) ;
- ``error`` : ``saxon_missing`` si des règles existent mais que Saxon n'est
  pas installé.

``check_compilation(text, path)`` (V0.9.2.4, pour ``schematron_check``)
compile le texte d'un fichier Schematron ouvert dans Varians, même non
enregistré, toutes phases comprises, avec un second transpileur qui
contrôle aussi l'assemblage des règles (``check-assembled-schema`` :
identifiant en double, phase qui cite un groupe absent…).

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
from schema_resolution import SchematronSource
from relaxng_validation import (STDERR_LOG, ValidationIssue, _dependency_path, _discover_schema_dependencies,
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
RULES_DOMAIN = "SCHEMATRON_RULES"
# Phases qui ne désignent pas un sch:phase du fichier.
_GENERIC_PHASES = ("", "#DEFAULT", "#ALL")
# Messages de l'assemblage des règles (SchXslt2, check-assembled-schema) :
# la valeur citée, et l'attribut de l'élément fautif qui la porte (pour
# ``id`` : le second élément qui la porte).
_ASSEMBLY_SITES = (
    (re.compile(r"The id (\S+) is not unique"), "id"),
    (re.compile(r"references (?:the|a) pattern (\S+), but"), "pattern"),
    (re.compile(r"abstract pattern (\S+?),? (?:but|requires|does)"), "is-a"),
    (re.compile(r"extends a rule (\S+), but"), "rule"),
    (re.compile(r"references a diagnostic (\S+), but"), "diagnostics"),
    (re.compile(r"references a property (\S+), but"), "properties"),
)


@dataclass(frozen=True)
class SchematronReport:
    issues: tuple[ValidationIssue, ...] = ()
    rules: tuple[str, ...] = ()
    errors: tuple[ValidationIssue, ...] = ()
    error: str = ""


@dataclass(frozen=True)
class _Compiled:
    """Une source compilée : ``executable`` est None si elle n'a pas de
    règles, ou si elles sont incorrectes (``error``, un ``ValidationIssue``)."""
    signature: tuple
    executable: object = None
    error: ValidationIssue | None = None
    saxon_missing: bool = False


def _rule_error(code, message, file, line=0) -> ValidationIssue:
    """Une erreur des règles (voir ``SchematronReport.errors``)."""
    return ValidationIssue(line=max(0, int(line or 0)), column=0, level="ERROR", message=message,
                           domain=RULES_DOMAIN, type_name=code, file=str(file))


def _source(item):
    """``(chemin, phase)`` d'une source : un chemin, un ``SchematronSource``
    ou un couple ``(chemin, phase)``."""
    if isinstance(item, SchematronSource):
        return Path(item.path), item.phase or ""
    if isinstance(item, (tuple, list)):
        return Path(item[0]), str(item[1] or "")
    return Path(item), ""


class _SaxonMissing(Exception):
    pass


_CACHE: dict[tuple[str, str], _Compiled] = {}
# Saxon (un processeur par processus) n'est appelé que sous ce verrou.
_LOCK = threading.RLock()
_COMPILATIONS = 0
# Les transpileurs compilés : celui de la validation (False) et celui de la
# vérification d'un fichier .sch (True, avec check-assembled-schema).
_TRANSPILERS = {}


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


def _parser():
    return etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)


def _parse(path):
    return etree.parse(str(path), _parser())


def _rules_trees(path, text=None):
    """``(fichier, racine)`` de *path* et des fichiers qu'il inclut, ceux qui
    sont lisibles ; avec *text* (le texte de l'éditeur, V0.9.2.4), *path* est
    lu dans ce texte, et ses inclusions d'après lui."""
    path = Path(path).expanduser().resolve()
    trees = []
    if text is None:
        sources = _discover_schema_dependencies(path)
    else:
        try:
            root = etree.fromstring(text.encode("utf-8"), _parser(), base_url=str(path))
        except etree.XMLSyntaxError:
            return []
        trees.append((path, root))
        sources = []
        for include in root.iter(f"{{{SCH_NS}}}include"):
            dependency = _dependency_path(path.parent, include.get("href") or "")
            if dependency is not None:
                sources += _discover_schema_dependencies(dependency)
    for source in dict.fromkeys(sources):
        if text is not None and source == path:
            continue
        try:
            trees.append((source, _parse(source).getroot()))
        except (OSError, etree.XMLSyntaxError):
            continue
    return trees


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


def _transpiler(check=False):
    """Le transpileur SchXslt2 compilé ; *check* : celui de la vérification
    d'un fichier .sch, qui contrôle l'assemblage des règles et garde ses
    messages (``get_xsl_messages``)."""
    if check not in _TRANSPILERS:
        processor = _processor()
        compiler = processor.new_xslt30_processor()
        for name, value in dict(_TRANSPILER_PARAMETERS, **{"check-assembled-schema": check}).items():
            compiler.set_parameter(f"{{{SCHXSLT_NS}}}{name}", processor.make_boolean_value(value))
        transpiler = compiler.compile_stylesheet(stylesheet_file=str(TRANSPILER))
        if check:
            transpiler.set_save_xsl_message(True)
        _TRANSPILERS[check] = transpiler
    return _TRANSPILERS[check]


def _expression_site(path, expression, text=None):
    """``(fichier, ligne)`` de l'élément Schematron de *path* (ou d'un
    fichier inclus ; *path* lu dans *text* s'il est donné) dont une
    expression figure dans *expression* (SchXslt2 entoure le test d'une
    assertion de ``not(…)``) ; la plus longue. Saxon abrège une longue
    expression (« … g... ») : une expression qui commence par ce qui en
    reste lui correspond aussi. Espaces normalisés."""
    expression = " ".join(expression.split())
    truncated = expression.endswith("...")
    stem = expression[:-3] if truncated else expression
    core = stem[4:] if stem.startswith("not(") else stem
    best = None
    for source, root in _rules_trees(path, text):
        for element in root.iter(f"{{{SCH_NS}}}*"):
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


def _saxon_error(exc, path, stderr="", text=None) -> ValidationIssue:
    """L'erreur de Saxon (de sa sortie d'erreur *stderr*, sinon de
    l'exception) pour les règles de *path* (lu dans *text* s'il est donné) :
    au fichier et à la ligne de la règle si l'expression fautive y est
    retrouvée, sinon suivie de l'expression, au fichier *path* ; le lieu que
    donne Saxon est dans la feuille produite par SchXslt2, il n'est pas
    repris."""
    from xslt_engines import _saxon_blocks
    blocks = [block for block in _saxon_blocks(stderr) if not block[0].startswith("Warning")]
    blocks = blocks or _saxon_blocks(str(exc).strip())
    if not blocks:
        return _rule_error("compile", type(exc).__name__, path)
    header, detail = blocks[0][0], " ".join(" ".join(blocks[0][1:]).split())
    match = _SAXON_EXPRESSION.search(header)
    if not (detail and match):
        return _rule_error("compile", detail or " ".join(header.split()), path)
    site = _expression_site(path, match.group(1), text)
    if site is not None:
        return _rule_error("xpath", detail, site[0], site[1])
    return _rule_error("xpath", f"{detail} : {match.group(1)}", path)


def _with_base(stylesheet, base) -> str:
    """La feuille produite par SchXslt2, avec l'adresse de la source pour
    URI de base : Saxon la compile depuis son texte, qui garde l'expression
    fautive dans ses messages d'erreur (pas depuis un nœud)."""
    root = etree.fromstring(stylesheet.encode("utf-8"), etree.XMLParser(huge_tree=True))
    root.set(_XML_BASE, base)
    return etree.tostring(root, encoding="unicode")


def _phases(path):
    """Identifiants des ``sch:phase`` de *path* et des fichiers qu'il inclut."""
    found = [phase.get("id") for _source, root in _rules_trees(path)
             for phase in root.iter(f"{{{SCH_NS}}}phase") if phase.get("id")]
    return list(dict.fromkeys(found))


def _phase_error(path, text, phase):
    """L'erreur ``phase`` si la phase demandée, ou la phase par défaut du
    schéma, n'existe pas dans le fichier ; sinon None."""
    if phase in _GENERIC_PHASES[:2]:
        phase = etree.fromstring(text.encode("utf-8"), etree.XMLParser(huge_tree=True)).get("defaultPhase") or ""
    if phase in _GENERIC_PHASES:
        return None
    phases = _phases(path)
    if phase in phases:
        return None
    return _rule_error("phase", f"{phase}\t{', '.join(phases)}", path)


def _compile(path, phase, signature) -> _Compiled:
    global _COMPILATIONS
    if not path.is_file():
        return _Compiled(signature, error=_rule_error("missing", "", path))
    try:
        text = rules_text(path)
    except OSError as exc:
        return _Compiled(signature, error=_rule_error("missing", " ".join(str(exc).split()), path))
    except etree.XMLSyntaxError as exc:
        message = getattr(exc, "msg", "") or str(exc)
        return _Compiled(signature, error=_rule_error("malformed", " ".join(message.split()), path,
                                                      getattr(exc, "lineno", 0)))
    if text is None:
        return _Compiled(signature)
    failure = _phase_error(path, text, phase)
    if failure is not None:
        return _Compiled(signature, error=failure)
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
        transpiler.set_parameter(f"{{{SCHXSLT_NS}}}phase", processor.make_string_value(phase or "#DEFAULT"))
        builder = processor.new_document_builder()
        builder.set_base_uri(base)
        stylesheet = transpiler.transform_to_string(xdm_node=builder.parse_xml(xml_text=text))
        executable = processor.new_xslt30_processor().compile_stylesheet(
            stylesheet_text=_with_base(stylesheet, base))
    except PySaxonApiError as exc:
        return _Compiled(signature, error=_saxon_error(exc, path, _stderr_since(start)))
    return _Compiled(signature, executable)


def compiled(path, phase="") -> _Compiled:
    """La source *path* compilée pour la phase *phase*, d'après le cache si
    aucun fichier n'a changé."""
    path = Path(path).expanduser().resolve()
    key = (str(path), phase or "")
    signature = _schema_dependency_signature(path)
    with _LOCK:
        cached = _CACHE.get(key)
        if cached is None or cached.signature != signature:
            cached = _CACHE[key] = _compile(path, phase or "", signature)
        return cached


def _assembly_errors(messages, path, text) -> tuple[ValidationIssue, ...]:
    """Les erreurs de l'assemblage des règles (messages ``svrl:error`` de
    SchXslt2, en anglais), chacune à la ligne de l'élément fautif quand il
    est retrouvé."""
    try:
        root = etree.fromstring(f"<messages>{messages}</messages>".encode("utf-8"))
    except etree.XMLSyntaxError:
        return ()
    trees = _rules_trees(path, text)
    errors = []
    for error in root.iter(f"{{{SVRL_NS}}}error"):
        message = " ".join("".join(error.itertext()).split())
        site = (path, 0)
        for pattern, attribute in _ASSEMBLY_SITES:
            match = pattern.search(message)
            if match is None:
                continue
            value = match.group(1)
            hits = [(source, element) for source, tree in trees for element in tree.iter(f"{{{SCH_NS}}}*")
                    if value in (element.get(attribute) or "").split()]
            if attribute == "id":
                hits = hits[1:]
            if hits:
                site = (hits[0][0], hits[0][1].sourceline or 0)
            break
        errors.append(_rule_error("assembly", message, site[0], site[1]))
    return tuple(errors)


def check_compilation(text, path) -> tuple[ValidationIssue, ...] | None:
    """Les erreurs de compilation du texte *text* du fichier Schematron
    *path* (V0.9.2.4, voir schematron_check), toutes phases comprises :
    l'assemblage des règles (code ``assembly``), puis chaque expression
    XPath (``xpath``), ou une autre erreur (``compile``). None sans Saxon."""
    path = Path(path).expanduser().resolve()
    with _LOCK:
        try:
            processor = _processor()
            transpiler = _transpiler(check=True)
        except _SaxonMissing:
            return None
        from saxonche import PySaxonApiError
        base = path.as_uri()
        start = _stderr_size()
        transpiler.clear_xsl_messages()
        try:
            transpiler.set_parameter(f"{{{SCHXSLT_NS}}}phase", processor.make_string_value("#ALL"))
            builder = processor.new_document_builder()
            builder.set_base_uri(base)
            stylesheet = transpiler.transform_to_string(xdm_node=builder.parse_xml(xml_text=text))
        except PySaxonApiError as exc:
            messages = transpiler.get_xsl_messages()
            assembly = _assembly_errors(str(messages), path, text) if messages is not None else ()
            return assembly or (_saxon_error(exc, path, _stderr_since(start), text),)
        try:
            processor.new_xslt30_processor().compile_stylesheet(stylesheet_text=_with_base(stylesheet, base))
        except PySaxonApiError as exc:
            return (_saxon_error(exc, path, _stderr_since(start), text),)
    return ()


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


def _document_uri(base):
    """L'URI de base du document validé, d'après son chemin *base* (None
    s'il n'en a pas). Celle que garde lxml ne sert pas : sous Windows, elle
    peut perdre la barre qui suit le lecteur (« D:a/… »)."""
    if base is None:
        return None
    try:
        return Path(base).expanduser().resolve().as_uri()
    except (OSError, ValueError):
        return None


def validate(tree, sources, file_of=None, base=None) -> SchematronReport:
    """Applique les règles de *sources* à *tree* (voir le module) ; *base* :
    le chemin du document (``base-uri()`` des règles)."""
    root = tree.getroot() if hasattr(tree, "getroot") else tree
    issues, rules, errors = [], [], []
    seen = set()
    document = None
    with _LOCK:
        for source in sources:
            path, phase = _source(source)
            entry = compiled(path, phase)
            if entry.saxon_missing:
                return SchematronReport(error="saxon_missing")
            if entry.error is not None:
                errors.append(entry.error)
                continue
            if entry.executable is None:
                continue
            from saxonche import PySaxonApiError
            start = _stderr_size()
            try:
                if document is None:
                    builder = _processor().new_document_builder()
                    uri = _document_uri(base)
                    if uri is not None:
                        builder.set_base_uri(uri)
                    document = builder.parse_xml(xml_text=etree.tostring(root.getroottree(), encoding="unicode"))
                svrl = entry.executable.transform_to_string(xdm_node=document)
            except PySaxonApiError as exc:
                errors.append(_saxon_error(exc, path, _stderr_since(start)))
                continue
            report = etree.fromstring(svrl.encode("utf-8"))
            failures = report.findall(f"{{{SVRL_NS}}}error")
            if failures:
                errors.append(_rule_error("runtime", " ; ".join(
                    " ".join(f"{failure.get('code') or ''} {''.join(failure.itertext())}".split())
                    for failure in failures), path))
                continue
            rules.append(str(path))
            for issue in _issues(report, root, file_of):
                key = (issue.file, issue.line, issue.level, issue.message, issue.type_name)
                if key not in seen:
                    seen.add(key)
                    issues.append(issue)
    return SchematronReport(tuple(issues), tuple(rules), tuple(errors))
