# -*- coding: utf-8 -*-
"""Éléments modifiables comme fragment (V0.9.2.9), sans Qt.

Le crayon ✎ de la Vue XSLT / CSS ouvre un élément de l'édition dans l'éditeur
de fragment. Sont modifiables les blocs posés dans une division : chaque
élément de ``model.divPart`` ou de ``model.inter``, et chaque ``<head>``,
``<figure>`` ou ``<note>``, du ``<body>``, sauf s'il est dans un autre
élément de cet ensemble. Un ``<lg>`` est modifiable, ses ``<l>`` non ; un
``<p>`` l'est, sa ``<quote>`` ou sa ``<note>`` non.

Les classes sont lues dans le schéma RELAX NG du projet
(:func:`unit_names_from_schema`), ce qui suit une personnalisation ODD ; à
défaut, Varians prend la liste de TEI P5 4.10.2 (:data:`TEI_UNIT_NAMES`).

La même règle est appliquée au texte (:func:`unit_spans`, pour la source
affichée) et à un arbre lxml (:func:`unit_elements`, pour l'édition
assemblée). Seul le ``<body>`` compte, ou tout le document s'il n'en a pas
(une partie, par exemple). :func:`mark_units` numérote les éléments
modifiables dans le texte donné à la XSLT de l'aperçu (attribut ``edit``
de l'espace de noms :data:`EDIT_NS`) : ce texte n'est ni validé ni
enregistré."""
from __future__ import annotations

import re
from pathlib import Path

from rng_completion import _GrammarIndex, _explicit_names, _local_qname

EDIT_NS = "urn:varians:fragment"

# Éléments ajoutés aux deux classes.
EXTRA_UNIT_NAMES = frozenset({"head", "figure", "note"})

# model.divPart et model.inter de TEI P5 4.10.2 (tei_all.rng), sous-classes
# comprises, plus EXTRA_UNIT_NAMES.
TEI_UNIT_NAMES = frozenset({
    # model.divPart
    "ab", "annotationBlock", "eTree", "forest", "graph", "l", "lg", "listForest", "p", "sp", "spGrp",
    "tree", "u",
    # model.inter
    "bibl", "biblFull", "biblStruct", "camera", "caption", "castList", "cit", "classSpec", "constraintSpec",
    "dataSpec", "desc", "eg", "egXML", "elementSpec", "floatingText", "label", "list", "listApp", "listBibl",
    "listEvent", "listNym", "listObject", "listOrg", "listPerson", "listPlace", "listRelation", "listWit",
    "macroSpec", "moduleSpec", "move", "msDesc", "outputRendition", "quote", "said", "sound", "specGrp",
    "specGrpRef", "stage", "table", "tech", "view",
}) | EXTRA_UNIT_NAMES

UNIT_CLASSES = ("model.divPart", "model.inter")

# Une balise, ou ce qui n'en contient pas : commentaire, CDATA, instruction
# de traitement, déclaration de type de document.
_TOKEN_RE = re.compile(
    r"(?P<skip><!--.*?(?:-->|$)|<!\[CDATA\[.*?(?:\]\]>|$)|<\?.*?(?:\?>|$)"
    r"|<!DOCTYPE(?:[^\[>]|\[.*?\])*>)"
    r"|<(?P<close>/?)(?:[^\s/>:!?\"'=<]+:)?(?P<name>[^\s/>:!?\"'=<]+)"
    r"(?:[^>\"']|\"[^\"]*\"|'[^']*')*?(?P<empty>/?)>",
    re.S,
)


def _unit_tags(text, names, whole):
    """``(début, fin de la balise ouvrante, fin, vide)`` de chaque élément
    modifiable de ``text`` ; ``whole`` : tout le document compte, sinon
    seulement le ``<body>``. Second résultat : le texte a-t-il un ``<body>`` ?"""
    found = []
    depth = 0          # éléments ouverts
    bodies = 0         # <body> ouverts
    has_body = False
    unit = None        # (début, fin de la balise, profondeur) de l'élément en cours
    for match in _TOKEN_RE.finditer(text):
        if match.group("skip"):
            continue
        name = match.group("name")
        if match.group("close"):
            depth -= 1
            if name == "body":
                bodies -= 1
            if unit is not None and depth == unit[2]:
                found.append((unit[0], unit[1], match.end(), False))
                unit = None
            continue
        empty = bool(match.group("empty"))
        if name == "body":
            has_body = True
        if unit is None and name in names and (whole or bodies > 0):
            if empty:
                found.append((match.start(), match.end(), match.end(), True))
            else:
                unit = (match.start(), match.end(), depth)
        if not empty:
            depth += 1
            if name == "body":
                bodies += 1
    return found, has_body


def _units_of(text, names):
    found, has_body = _unit_tags(text, names, whole=False)
    if not has_body:
        found, _ = _unit_tags(text, names, whole=True)
    return found


def unit_spans(text, names=TEI_UNIT_NAMES):
    """``(début, fin)`` de chaque élément modifiable de ``text``, dans
    l'ordre du texte."""
    return [(start, end) for start, _tag_end, end, _empty in _units_of(str(text or ""), names)]


def mark_units(text, names=TEI_UNIT_NAMES):
    """``text`` où chaque élément modifiable porte ``vx:edit="N"`` (N : son
    rang), et les plages de ces éléments dans ``text``."""
    text = str(text or "")
    found = _units_of(text, names)
    pieces, last = [], 0
    for index, (_start, tag_end, _end, empty) in enumerate(found):
        at = tag_end - (2 if empty else 1)
        pieces += [text[last:at], f' xmlns:vx="{EDIT_NS}" vx:edit="{index}"']
        last = at
    pieces.append(text[last:])
    return "".join(pieces), [(start, end) for start, _tag_end, end, _empty in found]


def _local(element):
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else None


def unit_elements(root, names=TEI_UNIT_NAMES):
    """Éléments modifiables de l'arbre lxml ``root``, dans l'ordre du
    document : même règle que :func:`unit_spans`."""
    whole = not any(_local(e) == "body" for e in root.iter())
    found = []
    pending = [(root, whole)]
    while pending:
        element, inside = pending.pop()
        name = _local(element)
        if name is None:
            continue
        if inside and name in names:
            found.append(element)
            continue
        inside = inside or name == "body"
        pending.extend((child, inside) for child in reversed(element))
    return found


def mark_unit_elements(elements):
    """Numérote ``elements`` (attribut ``edit`` de :data:`EDIT_NS`), comme
    :func:`mark_units` le fait dans un texte."""
    for index, element in enumerate(elements):
        element.set(f"{{{EDIT_NS}}}edit", str(index))


_SCHEMA_CACHE = {}


def _class_members(index, name, seen):
    """Noms des éléments d'une classe RELAX NG (ses ``<define>``), sous-classes
    comprises."""
    members = set()
    for define in index.defines.get(name, ()):
        for ref in define.iter():
            if _local(ref) != "ref":
                continue
            target = (ref.get("name") or "").strip()
            if not target or target in seen:
                continue
            seen.add(target)
            elements = [child for define_ in index.defines.get(target, ())
                        for child in define_ if _local(child) == "element"]
            if elements:
                members.update(_local_qname(n) for element in elements for n in _explicit_names(element))
            else:
                members |= _class_members(index, target, seen)
    return members


def unit_names_from_schema(schema_path):
    """Noms des éléments modifiables selon le schéma RELAX NG ``schema_path``
    : ``model.divPart`` et ``model.inter``, sous-classes comprises, plus
    ``<head>``, ``<figure>``, ``<note>``. None si le schéma est illisible ou
    ne définit pas ces classes. Le résultat est gardé tant que le fichier ne
    change pas."""
    try:
        path = Path(schema_path).expanduser().resolve()
        stat = path.stat()
    except (OSError, TypeError, ValueError):
        return None
    key = (str(path), stat.st_mtime_ns, stat.st_size)
    if key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[key]
    try:
        index = _GrammarIndex(path)
    except Exception:
        names = None
    else:
        if any(cls in index.defines for cls in UNIT_CLASSES):
            members = set()
            for cls in UNIT_CLASSES:
                members |= _class_members(index, cls, {cls})
            names = frozenset(members) | EXTRA_UNIT_NAMES
        else:
            names = None
    for old in [k for k in _SCHEMA_CACHE if k[0] == key[0]]:
        del _SCHEMA_CACHE[old]
    _SCHEMA_CACHE[key] = names
    return names
