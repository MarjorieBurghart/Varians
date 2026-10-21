# -*- coding: utf-8 -*-
"""Assemblage d'une édition par XInclude, sans Qt.

Une édition peut inclure ses parties, par exemple un fichier par sermon :

- un fragment, ``<xi:include href="s01.xml"/>`` : la racine du fichier ;
- un élément d'un document complet, par ``xpointer`` : un identifiant
  (``s02``), ``element(s02)``, ``element(/1/2/1)`` ou ``element(s02/1)``.

``assemble`` remplace chaque ``xi:include`` par une copie de l'élément inclus,
comme ``xinclude()`` de lxml (y compris l'ajout de ``xml:base`` quand la
partie est dans un autre dossier), avec trois différences :

- le texte des parties ouvertes dans Varians, même non enregistré, remplace
  celui du fichier ;
- chaque copie retient son fichier (``Assembly.origin``) et chaque élément
  garde sa ligne (``sourceline``) : une erreur de validation est rapportée
  dans le bon fichier, à la bonne ligne ;
- un problème (partie absente ou mal formée, inclusion circulaire, forme non
  prise en charge) est rapporté, à la ligne du ``xi:include`` ou de l'erreur,
  au lieu d'interrompre l'assemblage ; le ``xi:include`` concerné est retiré.

Non pris en charge, et signalé : ``parse="text"``, ``xi:fallback`` (utilisé
seulement si la partie manque), les autres schémas ``xpointer`` et les
``href`` qui ne désignent pas un fichier local.
"""
from __future__ import annotations

import copy
import os
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

from lxml import etree

XI_NS = "http://www.w3.org/2001/XInclude"
_INCLUDE = f"{{{XI_NS}}}include"
_FALLBACK = f"{{{XI_NS}}}fallback"
_XML_BASE = "{http://www.w3.org/XML/1998/namespace}base"
_XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_NCNAME = re.compile(r"[A-Za-z_][\w.\-]*\Z")
# Une partie de pointeur XPointer : schéma(données), sans parenthèses
# imbriquées (une telle forme relève d'un schéma non pris en charge).
_POINTER_PART = re.compile(r"\s*([A-Za-z_][\w.\-]*)\(([^()]*)\)\s*")
_MISSING = object()


@dataclass(frozen=True)
class Include:
    """Un ``xi:include`` tel qu'il est écrit, avec sa ligne."""
    href: str
    xpointer: str
    parse: str
    has_fallback: bool
    line: int


@dataclass(frozen=True)
class AssemblyProblem:
    """Problème d'assemblage dans ``file``, à ``line``.

    ``code`` : ``malformed`` (partie ou édition mal formée, à la ligne de
    l'erreur), ou, à la ligne du ``xi:include`` : ``missing``, ``fallback``
    (partie absente, ``xi:fallback`` non pris en charge), ``circular``,
    ``parse_text``, ``parse_invalid``, ``href_unsupported``,
    ``xpointer_unsupported``, ``xpointer_not_found``.
    """
    file: Path
    line: int
    code: str
    detail: str = ""


class Assembly:
    """Résultat de ``assemble``.

    ``root`` : racine du document assemblé (``None`` si l'édition est mal
    formée) ; ``parts`` : fichiers inclus qui existent, dans l'ordre de leur
    première inclusion ; ``problems`` : voir ``AssemblyProblem``.
    """

    def __init__(self, master, root, parts, problems, origins):
        self.master = master
        self.root = root
        self.parts = tuple(parts)
        self.problems = tuple(problems)
        self._origins = origins

    def origin(self, element) -> Path:
        """Fichier d'où vient ``element`` (l'édition, ou l'une des parties)."""
        node = element
        while node is not None:
            path = self._origins.get(node)
            if path is not None:
                return path
            node = node.getparent()
        return self.master

    def visible_ids(self) -> dict:
        """``{fichier: identifiants}`` des éléments du document assemblé,
        selon leur fichier d'origine. Pour une partie incluse par
        ``xpointer``, seuls ceux de l'élément inclus y figurent (pas ceux de
        son ``<teiHeader>``, par exemple)."""
        found = {}
        if self.root is not None:
            for element in self.root.iter():
                ident = element.get(_XML_ID) if isinstance(element.tag, str) else None
                if ident:
                    found.setdefault(self.origin(element), set()).add(ident)
        return {path: frozenset(ids) for path, ids in found.items()}


def path_key(path) -> str:
    """Clé de comparaison d'un chemin (absolu, normalisé, casse Windows)."""
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _parser():
    return etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)


def _include_of(element) -> Include:
    return Include(
        href=(element.get("href") or "").strip(),
        xpointer=(element.get("xpointer") or "").strip(),
        parse=(element.get("parse") or "xml").strip(),
        has_fallback=element.find(_FALLBACK) is not None,
        line=element.sourceline or 0,
    )


def _includes_in(element):
    """``xi:include`` de ``element``, hors de ceux d'un ``xi:fallback``."""
    return [include for include in element.iter(_INCLUDE)
            if not any(ancestor.tag == _FALLBACK for ancestor in include.iterancestors())]


def find_includes(text) -> list[Include]:
    """Les ``xi:include`` d'un texte XML ; aucun s'il est mal formé."""
    try:
        root = etree.fromstring(str(text or "").encode("utf-8"), _parser())
    except etree.XMLSyntaxError:
        return []
    return [_include_of(element) for element in _includes_in(root)]


def _href_path(href, including):
    """Fichier local désigné par ``href`` depuis le fichier ``including``."""
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.query or parsed.fragment:
        return None
    if parsed.scheme == "file":
        raw = unquote(parsed.path)
        if os.name == "nt" and raw.startswith("/") and raw[2:3] == ":":
            raw = raw[1:]
    elif len(parsed.scheme) > 1:                 # http:, etc. ; « C: » est un lecteur
        return None
    else:
        raw = unquote(href)
    return Path(os.path.normpath(os.path.join(os.path.dirname(os.fspath(including)), raw)))


def _by_id(root, ident):
    found = root.xpath("//*[@xml:id=$ident]", ident=ident)
    return found[0] if found else None


def _element_scheme(root, data):
    """``element(…)`` : identifiant, suite d'enfants (``/1/2``), ou les deux."""
    first, *steps = data.split("/")
    if first:
        node = _by_id(root, first)
    elif steps and steps[0] == "1":
        node, steps = root, steps[1:]
    else:
        node = None
    for step in steps:
        if node is None or not step.isdigit() or int(step) < 1:
            return None
        children = [child for child in node if isinstance(child.tag, str)]
        node = children[int(step) - 1] if int(step) <= len(children) else None
    return node


def _select(root, xpointer):
    """Élément désigné par ``xpointer``, ou le code du problème."""
    if not xpointer:
        return root
    if _NCNAME.match(xpointer):
        found = _by_id(root, xpointer)
        return "xpointer_not_found" if found is None else found
    parts = []
    position = 0
    while position < len(xpointer):
        match = _POINTER_PART.match(xpointer, position)
        if match is None:
            return "xpointer_unsupported"
        parts.append(match.groups())
        position = match.end()
    unsupported = False
    for scheme, data in parts:
        if scheme == "xmlns":
            continue
        if scheme != "element":
            unsupported = True
            continue
        found = _element_scheme(root, data.strip())
        if found is not None:
            return found
    return "xpointer_unsupported" if unsupported else "xpointer_not_found"


def _remove_keeping_tail(element):
    parent = element.getparent()
    if element.tail:
        previous = element.getprevious()
        if previous is not None:
            previous.tail = (previous.tail or "") + element.tail
        else:
            parent.text = (parent.text or "") + element.tail
    parent.remove(element)


class _Assembler:
    def __init__(self, texts):
        self._texts = {path_key(path): text for path, text in (texts or {}).items()}
        self._documents = {}
        self.parts = []
        self.problems = []
        self.origins = {}

    def _load(self, path):
        """Racine de la partie ``path`` (lue une fois) ; ``None`` si elle est mal
        formée, ``_MISSING`` si elle n'existe pas."""
        key = path_key(path)
        if key in self._documents:
            return self._documents[key]
        text = self._texts.get(key)
        try:
            data = text.encode("utf-8") if text is not None else path.read_bytes()
        except OSError:
            self._documents[key] = _MISSING
            return _MISSING
        self.parts.append(path)
        try:
            root = etree.fromstring(data, _parser(), base_url=str(path))
        except etree.XMLSyntaxError as exc:
            self.problems.append(AssemblyProblem(path, int(exc.lineno or 0), "malformed", str(exc)))
            root = None
        self._documents[key] = root
        return root

    def expand(self, element, path, chain):
        """Remplace les ``xi:include`` de ``element``, écrit dans ``path``."""
        for include in _includes_in(element):
            piece = self._piece(_include_of(include), path, chain)
            if piece is None:
                _remove_keeping_tail(include)
            else:
                piece.tail = include.tail
                include.getparent().replace(include, piece)

    def _piece(self, include, path, chain):
        """Copie, déjà assemblée, de l'élément que désigne ``include``."""
        def problem(code, detail=""):
            self.problems.append(AssemblyProblem(path, include.line, code, detail))

        if include.parse != "xml":
            return problem("parse_text" if include.parse == "text" else "parse_invalid", include.parse)
        target = _href_path(include.href, path)
        if target is None:
            return problem("href_unsupported", include.href)
        key = path_key(target)
        if key in chain:                             # avant la lecture : l'édition n'est pas sa propre partie
            return problem("circular", str(target))
        root = self._load(target)
        if root is _MISSING:
            return problem("fallback" if include.has_fallback else "missing", str(target))
        if root is None:
            return None                              # mal formée : signalé dans son fichier
        selected = _select(root, include.xpointer)
        if isinstance(selected, str):
            return problem(selected, include.xpointer)
        piece = copy.deepcopy(selected)
        piece.tail = None
        self.origins[piece] = target
        self.expand(piece, target, chain | {key})
        if os.path.dirname(key) != os.path.dirname(path_key(path)) and piece.get(_XML_BASE) is None:
            piece.set(_XML_BASE, include.href)
        return piece


def assemble(master_text, master_path, texts=None) -> Assembly:
    """Assemble l'édition ``master_text`` (fichier ``master_path``).

    ``texts`` : ``{chemin: texte}`` des parties ouvertes, prioritaire sur les
    fichiers ; les autres parties sont lues sur le disque.
    """
    master = Path(os.path.abspath(os.fspath(master_path)))
    assembler = _Assembler(texts)
    try:
        root = etree.fromstring(str(master_text or "").encode("utf-8"), _parser(), base_url=str(master))
    except etree.XMLSyntaxError as exc:
        problem = AssemblyProblem(master, int(exc.lineno or 0), "malformed", str(exc))
        return Assembly(master, None, (), (problem,), {})
    assembler.expand(root, master, frozenset({path_key(master)}))
    return Assembly(master, root, assembler.parts, assembler.problems, assembler.origins)
