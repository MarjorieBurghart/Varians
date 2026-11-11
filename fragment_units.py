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
enregistré.

La XSLT de la vue n'a pas à connaître ces éléments : la feuille enveloppe
(:func:`edit_stylesheet`) l'importe et écrit un crayon devant ce qu'elle
produit pour chaque élément numéroté, puis :func:`place_edit_markers` met
chaque crayon au début du premier bloc qui le suit. Le crayon porte le rang
de l'élément : il ouvre le bon élément même si la feuille en omet ou en
déplace."""
from __future__ import annotations

import html
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


class ChosenUnits(frozenset):
    """Éléments modifiables choisis par une vue (``<view units="…">``,
    V0.9.4.4) : ils comptent où qu'ils soient dans le document, et non
    seulement dans le ``<body>`` ; un élément choisi dans un autre ne compte
    pas (le plus extérieur l'emporte)."""


def chosen_units(names):
    """Les éléments ``names`` (noms locaux) choisis par une vue."""
    return ChosenUnits(names)

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
    if isinstance(names, ChosenUnits):
        return _unit_tags(text, names, whole=True)[0]
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
    whole = isinstance(names, ChosenUnits) or not any(_local(e) == "body" for e in root.iter())
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


def stylesheet_needs_saxon(xsl_path):
    """La feuille ``xsl_path`` est en XSLT 2.0 ou 3.0 (V0.9.4.4) : l'aperçu la
    confie à Saxon. Une feuille 1.0, sans version, illisible ou absente
    reste à lxml, qui signale l'erreur s'il y en a une."""
    from xslt_scenarios import stylesheet_info
    try:
        with open(xsl_path, encoding="utf-8", errors="replace") as handle:
            text = handle.read(65536)
    except OSError:
        return False
    info = stylesheet_info(text)
    if info is None:
        return False
    try:
        return float(info.version) >= 2.0
    except ValueError:
        return False


def edit_stylesheet(xsl_path, version="1.0"):
    """Feuille enveloppe de la XSLT ``xsl_path`` : celle-ci est importée, et
    chaque élément numéroté par :func:`mark_units` reçoit un crayon
    ``<a class="tei-edit-marker" href="tei-edit://p/N">`` devant ce qu'elle
    produit pour lui ; rien si elle ne produit rien (élément masqué). Les
    paramètres de la feuille importée restent ceux de la transformation.

    En 1.0 (lxml), seul le mode par défaut est intercepté. Pour une feuille
    2.0 ou 3.0 (``version`` autre que 1.0, Saxon, V0.9.4.4), l'enveloppe est
    en 3.0 et intercepte l'élément dans tous ses modes (``mode="#all"``) :
    les feuilles 3.0 rendent souvent le texte dans un mode ; un élément
    rendu plusieurs fois n'aura qu'un crayon (:func:`place_edit_markers`)."""
    href = html.escape(Path(xsl_path).expanduser().resolve().as_uri(), quote=True)
    if str(version) != "1.0":
        return f'''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="3.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:vx="{EDIT_NS}" exclude-result-prefixes="vx">
  <xsl:import href="{href}"/>
  <xsl:template match="*[@vx:edit]" mode="#all">
    <xsl:variable name="out"><xsl:apply-imports/></xsl:variable>
    <xsl:if test="normalize-space($out) or $out//*">
      <a class="tei-edit-marker" href="tei-edit://p/{{@vx:edit}}">&#x270E;</a>
    </xsl:if>
    <xsl:copy-of select="$out"/>
  </xsl:template>
</xsl:stylesheet>
'''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:vx="{EDIT_NS}" xmlns:exsl="http://exslt.org/common" exclude-result-prefixes="vx exsl">
  <xsl:import href="{href}"/>
  <xsl:template match="*[@vx:edit]">
    <xsl:variable name="out"><xsl:apply-imports/></xsl:variable>
    <xsl:if test="normalize-space($out) or exsl:node-set($out)//*">
      <a class="tei-edit-marker" href="tei-edit://p/{{@vx:edit}}">&#x270E;</a>
    </xsl:if>
    <xsl:copy-of select="$out"/>
  </xsl:template>
</xsl:stylesheet>
'''


def edit_stylesheet_url(xsl_path):
    """Adresse de base de la feuille enveloppe : à côté de ``xsl_path``,
    sous un autre nom (une feuille ne peut s'importer elle-même)."""
    path = Path(xsl_path).expanduser().resolve()
    return path.with_name(path.name + ".varians-edit.xsl").as_uri()


_MARKER = (r'<a\b(?=[^>]*\bclass="tei-edit-marker")(?=[^>]*\bhref="tei-edit://p/(\d+)")[^>]*>'
           r'(?:\u270e|&#9998;|&#x270[eE];)</a>')
_MARKER_RE = re.compile(_MARKER)
# Le crayon passe les blancs et les ancres vides (<a name="…"></a>) pour
# entrer dans le bloc qui suit, puis dans le premier bloc de celui-ci, etc.
_DIVE_RE = re.compile(
    r"(?P<marker>" + _MARKER.replace("(\\d+)", "\\d+") + r")(?P<gap>(?:\s|<a\b[^>]*>\s*</a>)*)"
    r"(?P<block><(?:p|div|h[1-6]|li|ul|ol|dl|dt|dd|blockquote|figure|figcaption|section|article|header"
    r"|footer|aside|nav|table|caption|thead|tbody|tfoot|tr|td|th|pre|center|address)\b[^>]*>)",
    re.I,
)


def place_edit_markers(html_text, title=""):
    """Met chaque crayon écrit par la feuille enveloppe au début du premier
    bloc qui le suit, avec l'infobulle ``title`` et une espace après lui.
    Un élément rendu plusieurs fois (le texte, puis ses notes) garde son
    premier crayon, les suivants sont écartés (V0.9.4.4). Retourne le HTML
    et le nombre de crayons."""
    for _ in range(64):
        moved = _DIVE_RE.sub(r"\g<gap>\g<block>\g<marker>", html_text)
        if moved == html_text:
            break
        html_text = moved
    title = html.escape(title or "", quote=True)
    seen = set()

    def final(match):
        index = match.group(1)
        if index in seen:
            return ""
        seen.add(index)
        return (f'<a href="tei-edit://p/{index}" class="tei-edit-marker" title="{title}">'
                '\u270e</a> ')

    html_text = _MARKER_RE.sub(final, html_text)
    return html_text, len(seen)
