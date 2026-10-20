# -*- coding: utf-8 -*-
"""Références entre documents XML du projet, sans Qt.

Une référence est un jeton de la valeur d'un attribut pointeur TEI (``ref``,
``corresp``, ``who``, ``wit``…) de la forme ``#id`` ou ``fichier.xml#id``. Les
adresses web et les valeurs sans ``#`` ne sont pas des références locales.

Résolution :

- ``fichier.xml#id`` vise ce fichier, relatif au document qui le cite ;
- ``#id`` est cherché d'abord dans le document lui-même, puis dans les autres
  documents du projet. Un identifiant présent plusieurs fois (dans le
  document, ou dans plusieurs autres documents) est ambigu.

L'analyse est lexicale (``xml_tag_pairs.scan_xml_tags``) : elle fonctionne sur
un document momentanément mal formé et ignore commentaires et CDATA.
"""
from __future__ import annotations

import bisect
import html
import os
import re
from dataclasses import dataclass
from pathlib import Path

from xml_tag_pairs import scan_xml_tags

# Attributs pointeurs TEI usuels (nom local, sans préfixe).
REFERENCE_ATTRIBUTES = frozenset({
    "ref", "corresp", "target", "who", "sameAs", "ana", "resp", "source", "prev", "next",
    "synch", "copyOf", "wit", "hand", "facs", "edRef",
})

_ATTRIBUTE_RE = re.compile(
    r"""(?<![\w:.-])([A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?)\s*=\s*(["'])(.*?)\2""", re.S)
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_ID_RE = re.compile(r"^[A-Za-z_][\w.-]*$")
_TAG_RE = re.compile(r"<[^>]*>")
LABEL_LENGTH = 60


_PERSONS = frozenset({"person", "personGrp", "persona"})
# Éléments visés par défaut, selon l'élément porteur de @ref ou l'attribut.
_REF_TARGETS = {"persName": _PERSONS, "placeName": frozenset({"place"}), "orgName": frozenset({"org"})}
_ATTRIBUTE_TARGETS = {"who": _PERSONS, "wit": frozenset({"witness"}), "edRef": frozenset({"witness"})}


def target_elements(element, attribute):
    """Noms locaux des éléments qu'un attribut vise d'ordinaire, ou None
    (tous) : ``persName/@ref`` vise ``person``, ``@wit`` vise ``witness``…"""
    attribute = _local_name(attribute or "")
    if attribute in _ATTRIBUTE_TARGETS:
        return _ATTRIBUTE_TARGETS[attribute]
    if attribute == "ref":
        return _REF_TARGETS.get(_local_name(element or ""))
    return None


def parse_pointer(token):
    """``(fichier ou None, id)`` pour un pointeur local, sinon ``None``."""
    token = str(token or "").strip()
    if "#" not in token or _SCHEME_RE.match(token):
        return None
    file, _, ident = token.partition("#")
    if not _ID_RE.match(ident):
        return None
    return (file or None, ident)


@dataclass(frozen=True)
class IdTarget:
    """Élément portant un ``xml:id`` : position de sa balise ouvrante."""
    id: str
    start: int
    end: int
    line: int
    element: str
    label: str = ""


@dataclass(frozen=True)
class Reference:
    """Jeton pointeur dans la valeur d'un attribut ; positions du jeton."""
    attribute: str
    element: str
    token: str
    file: str | None
    id: str
    start: int
    end: int
    line: int


@dataclass(frozen=True)
class Resolution:
    status: str                 # ok | missing | ambiguous | no_file
    targets: tuple = ()         # ((chemin, IdTarget), …)


@dataclass(frozen=True)
class ReferenceProblem:
    path: Path
    reference: Reference
    resolution: Resolution


def _line_starts(text):
    starts = [0]
    starts.extend(m.end() for m in re.finditer("\n", text))
    return starts


def _line(starts, position):
    return bisect.bisect_right(starts, position)


def _local_name(name):
    return name.rsplit(":", 1)[-1]


def _label(text):
    words = " ".join(html.unescape(_TAG_RE.sub(" ", text)).split())
    return words if len(words) <= LABEL_LENGTH else words[:LABEL_LENGTH - 1].rstrip() + "…"


def collect_ids(text):
    """``{id: [IdTarget, …]}`` ; un identifiant répété a plusieurs cibles."""
    text = str(text or "")
    starts = _line_starts(text)
    result = {}
    open_elements = []          # (nom, jeton, id ou None)
    for token in scan_xml_tags(text):
        if token.kind == "close":
            # Tolérance : remonter jusqu'à la balise ouvrante de même nom.
            for depth in range(len(open_elements) - 1, -1, -1):
                if open_elements[depth][0] == token.name:
                    for name, opening, ident in open_elements[depth:][::-1]:
                        if ident is not None:
                            _add_target(result, starts, text, opening, ident, token.start)
                    del open_elements[depth:]
                    break
            continue
        ident = None
        for match in _ATTRIBUTE_RE.finditer(text, token.name_end, token.end):
            if match.group(1) == "xml:id":
                ident = html.unescape(match.group(3)).strip()
                break
        if token.kind == "self":
            if ident:
                _add_target(result, starts, text, token, ident, token.end)
        else:
            open_elements.append((token.name, token, ident or None))
    for name, opening, ident in open_elements:          # éléments non refermés
        if ident is not None:
            _add_target(result, starts, text, opening, ident, min(len(text), opening.end + 400))
    for targets in result.values():
        targets.sort(key=lambda target: target.start)
    return result


def _add_target(result, starts, text, opening, ident, content_end):
    label = _label(text[opening.end:content_end]) if content_end > opening.end else ""
    result.setdefault(ident, []).append(IdTarget(
        ident, opening.start, opening.end, _line(starts, opening.start),
        _local_name(opening.name), label))


def collect_references(text):
    """Références locales des attributs pointeurs, dans l'ordre du texte."""
    text = str(text or "")
    starts = _line_starts(text)
    result = []
    for token in scan_xml_tags(text):
        if token.kind == "close":
            continue
        for match in _ATTRIBUTE_RE.finditer(text, token.name_end, token.end):
            attribute = match.group(1)
            if _local_name(attribute) not in REFERENCE_ATTRIBUTES:
                continue
            value_start = match.start(3)
            for piece in re.finditer(r"\S+", match.group(3)):
                raw = piece.group(0)
                pointer = parse_pointer(html.unescape(raw))
                if pointer is None:
                    continue
                start = value_start + piece.start()
                result.append(Reference(
                    attribute, _local_name(token.name), raw, pointer[0], pointer[1],
                    start, start + len(raw), _line(starts, start)))
    return result


def _key(path):
    return os.path.normcase(str(Path(path).resolve()))


class ReferenceResolver:
    """Résout les références à partir des textes des documents du projet.

    ``documents`` : couples ``(chemin, texte)``, l'édition d'abord. Un fichier
    cité qui n'en fait pas partie est lu sur le disque s'il existe.
    """

    def __init__(self, documents):
        self._paths = {}
        self._texts = {}
        self._order = []
        for path, text in documents:
            key = _key(path)
            if key in self._texts:
                continue
            self._paths[key] = Path(path).resolve()
            self._texts[key] = str(text or "")
            self._order.append(key)
        self._ids = {}

    def documents(self):
        return [self._paths[key] for key in self._order]

    def text(self, path):
        key = _key(path)
        if key not in self._texts:
            try:
                self._texts[key] = Path(path).read_text(encoding="utf-8")
                self._paths[key] = Path(path).resolve()
            except (OSError, UnicodeError):
                return None
        return self._texts[key]

    def ids(self, path):
        """Index des identifiants d'un document, ou None s'il est illisible."""
        key = _key(path)
        if key not in self._ids:
            text = self.text(path)
            self._ids[key] = None if text is None else collect_ids(text)
        return self._ids[key]

    def resolve(self, reference, source_path):
        source = Path(source_path).resolve()
        if reference.file:
            target = (source.parent / reference.file).resolve()
            index = self.ids(target)
            if index is None:
                return Resolution("no_file")
            return self._status([(self._paths[_key(target)], t) for t in index.get(reference.id, ())])
        own = self.ids(source) or {}
        if reference.id in own:
            return self._status([(self._paths[_key(source)], t) for t in own[reference.id]])
        found = []
        for key in self._order:
            if key == _key(source):
                continue
            for target in (self.ids(self._paths[key]) or {}).get(reference.id, ()):
                found.append((self._paths[key], target))
        return self._status(found)

    @staticmethod
    def _status(found):
        if not found:
            return Resolution("missing")
        return Resolution("ok" if len(found) == 1 else "ambiguous", tuple(found))

    def problems(self):
        """Références introuvables ou ambiguës de tous les documents."""
        result = []
        for key in self._order:
            path = self._paths[key]
            for reference in collect_references(self._texts[key]):
                resolution = self.resolve(reference, path)
                if resolution.status != "ok":
                    result.append(ReferenceProblem(path, reference, resolution))
        return result
