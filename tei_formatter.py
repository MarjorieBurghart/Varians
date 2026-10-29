# -*- coding: utf-8 -*-
"""Formateur XML/TEI conservateur de Varians.

Le formateur ne cherche pas à « pretty-printer » tout XML. Il ne modifie que
les nœuds de texte composés exclusivement de blancs dont le schéma (ou une
règle projet explicite) permet d'affirmer qu'ils séparent des enfants
structurels. Les zones mixtes restent octet-pour-octet inchangées.

Protections absolues :
* ``xml:space=\"preserve\"`` sur un élément ou un ancêtre ;
* texte direct non blanc (contenu mixte constaté) ;
* un ``<lb/>`` enfant direct ;
* une règle projet ``formatting=\"preserve\"`` ou ``formatting=\"inline\"``.

Les règles ``formatting=\"block\"`` peuvent raffiner/forcer la classification
RNG, mais ne contournent jamais les protections absolues ci-dessus.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import re

from lxml import etree

from xml_tag_pairs import XmlTagToken, scan_xml_tags

_XML_SPACE_RE = re.compile(r"\bxml:space\s*=\s*(['\"])(.*?)\1", re.S | re.I)
_XML_SPACE = "{http://www.w3.org/XML/1998/namespace}space"
# Les seuls blancs XML : espace, tabulation, retour chariot, saut de ligne.
# Une espace insécable ou idéographique est du texte (red team 2, B1).
_XML_BLANKS_RE = re.compile(r"[ \t\r\n]*")


def _is_blank(text: str) -> bool:
    return _XML_BLANKS_RE.fullmatch(text) is not None


def _local_qname(name: str) -> str:
    return (name or "").split(":", 1)[-1]


@dataclass
class _Node:
    name: str
    opening: XmlTagToken
    closing: XmlTagToken | None = None
    children: list["_Node"] = field(default_factory=list)
    # Valeur de xml:space dans l'arbre XML (valeurs par défaut du DTD
    # comprises), None si l'arbre n'a pas pu être apparié.
    xml_space: str | None = None

    @property
    def self_closing(self) -> bool:
        return self.opening.kind == "self"

    @property
    def end(self) -> int:
        return self.opening.end if self.self_closing else (self.closing.end if self.closing else self.opening.end)


@dataclass(frozen=True)
class FormatReplacement:
    start: int
    end: int
    text: str


@dataclass(frozen=True)
class FormatResult:
    text: str
    replacements: tuple[FormatReplacement, ...] = ()
    formatted_elements: int = 0
    protected_elements: int = 0
    error: str = ""

    @property
    def changed(self) -> bool:
        return bool(self.replacements) and not self.error

    def map_position(self, position: int) -> int:
        """Translate un offset de l'ancien texte vers le texte formaté."""
        pos = max(0, int(position))
        delta = 0
        for repl in sorted(self.replacements, key=lambda r: r.start):
            old_len = repl.end - repl.start
            if pos < repl.start:
                break
            if repl.start <= pos <= repl.end:
                if pos == repl.start:
                    return repl.start + delta
                return repl.start + delta + len(repl.text)
            delta += len(repl.text) - old_len
        return pos + delta


# Analyse de contrôle : entités non résolues, ni réseau ; valeurs par défaut
# des attributs du DTD ; documents profonds ou volumineux acceptés. Le texte
# est donné en UTF-8, quel que soit l'encodage qu'il déclare.
def _parser(attribute_defaults=True):
    return etree.XMLParser(encoding="utf-8", resolve_entities=False, no_network=True, huge_tree=True,
                           attribute_defaults=attribute_defaults, remove_blank_text=False)


def _parse(text: str):
    """L'arbre XML de *text* ; un DTD externe qui ne peut pas être lu (en
    ligne, par exemple) prive seulement des valeurs par défaut qu'il donne."""
    data = text.encode("utf-8")
    try:
        return etree.fromstring(data, _parser())
    except etree.XMLSyntaxError:
        return etree.fromstring(data, _parser(attribute_defaults=False))


def _build_tree(xml_text: str) -> tuple[_Node | None, str]:
    """Construit l'arbre lexical des éléments après contrôle de bonne formation."""
    text = str(xml_text or "")
    try:
        document = _parse(text)
    except Exception as exc:
        return None, str(exc)

    roots: list[_Node] = []
    stack: list[_Node] = []
    for token in scan_xml_tags(text):
        if token.kind in {"open", "self"}:
            node = _Node(token.name, token)
            if stack:
                stack[-1].children.append(node)
            else:
                roots.append(node)
            if token.kind == "open":
                stack.append(node)
        elif token.kind == "close":
            if not stack or stack[-1].name != token.name:
                return None, "structure XML ambiguë"
            stack[-1].closing = token
            stack.pop()
    if stack or len(roots) != 1:
        return None, "structure XML incomplète"
    _attach_xml_space(roots[0], document)
    return roots[0], ""


def _attach_xml_space(root: _Node, document) -> None:
    """Les éléments lexicaux et ceux de l'arbre XML se suivent dans le même
    ordre : chaque nœud reçoit son xml:space (red team 2, B7). Si les deux
    listes diffèrent, rien n'est attaché (lecture de la balise, plus bas)."""
    elements = [element for element in document.iter() if isinstance(element.tag, str)]
    nodes, pending = [], [root]
    while pending:
        node = pending.pop()
        nodes.append(node)
        pending.extend(reversed(node.children))
    if len(nodes) != len(elements):
        return
    for node, element in zip(nodes, elements):
        node.xml_space = element.get(_XML_SPACE) or ""


def _xml_space_preserve(raw_opening: str) -> bool:
    match = _XML_SPACE_RE.search(raw_opening or "")
    return bool(match and match.group(2).strip().lower() == "preserve")


def _custom_formatting(custom_config, element_name: str) -> str:
    if custom_config is None:
        return ""
    method = getattr(custom_config, "formatting_for", None)
    if callable(method):
        try:
            return (method(element_name) or "").strip().lower()
        except Exception:
            return ""
    return ""


def _rng_text_state(rng_model, element_name: str) -> bool | None:
    if rng_model is None:
        return None
    method = getattr(rng_model, "allows_text", None)
    if callable(method):
        try:
            return method(element_name)
        except Exception:
            return None
    mapping = getattr(rng_model, "content_allows_text", None)
    if isinstance(mapping, dict):
        if element_name in mapping:
            return bool(mapping[element_name])
        local = _local_qname(element_name)
        matches = [bool(v) for k, v in mapping.items() if _local_qname(k) == local]
        return any(matches) if matches else None
    return None


def _direct_gaps(text: str, node: _Node) -> list[tuple[int, int, str]]:
    if node.self_closing or node.closing is None:
        return []
    cursor = node.opening.end
    gaps: list[tuple[int, int, str]] = []
    for child in node.children:
        gaps.append((cursor, child.opening.start, text[cursor:child.opening.start]))
        cursor = child.end
    gaps.append((cursor, node.closing.start, text[cursor:node.closing.start]))
    return gaps


def format_tei_xml(xml_text: str, *, rng_model=None, custom_config=None, indent: str = "  ") -> FormatResult:
    """Indente uniquement les zones structurelles démontrées sûres.

    Le texte source est retourné inchangé en cas d'erreur XML. Les remplacements
    sont également fournis afin que l'interface puisse les appliquer en un seul
    bloc Undo sans réécrire le contenu éditorial.
    """
    text = str(xml_text or "")
    root, error = _build_tree(text)
    if root is None:
        return FormatResult(text=text, error=error)
    indent = str(indent or "  ")

    replacements: list[FormatReplacement] = []
    formatted_nodes: set[int] = set()
    protected = 0

    # Parcours sans récursion : une imbrication de milliers de niveaux ne
    # lève pas RecursionError (red team 2, A10).
    pending: list[tuple[_Node, int, bool]] = [(root, 0, False)]
    while pending:
        node, depth, inherited_inline = pending.pop()
        if node.self_closing or node.closing is None:
            continue

        if node.xml_space is not None:
            own_xml_preserve = node.xml_space.strip() == "preserve"
        else:
            own_xml_preserve = _xml_space_preserve(text[node.opening.start:node.opening.end])
        custom_mode = _custom_formatting(custom_config, node.name)

        # xml:space=preserve et formatting=preserve protègent tout le sous-arbre.
        if own_xml_preserve or custom_mode == "preserve":
            protected += 1
            continue

        gaps = _direct_gaps(text, node)
        direct_nonwhite_text = any(not _is_blank(chunk) for _, _, chunk in gaps)
        direct_special_markup = any("<" in chunk for _, _, chunk in gaps)
        has_direct_lb = any(_local_qname(child.name) == "lb" for child in node.children)
        has_direct_inline_override = any(
            _custom_formatting(custom_config, child.name) == "inline" for child in node.children
        )
        rng_allows_text = _rng_text_state(rng_model, node.name)

        # Protections de contenu : un contenu mixte réel ou <lb/> direct ne doit
        # jamais recevoir de blancs supplémentaires, même avec formatting=block.
        actual_inline = direct_nonwhite_text or has_direct_lb or custom_mode == "inline"
        schema_inline = (rng_allows_text is True and custom_mode != "block")
        inline_context = inherited_inline or actual_inline or schema_inline

        can_format_here = False
        if not inherited_inline and not direct_nonwhite_text and not has_direct_lb and not direct_special_markup \
                and not has_direct_inline_override and node.children:
            if custom_mode == "block":
                can_format_here = True
            elif custom_mode in {"inline", "preserve"}:
                can_format_here = False
            elif rng_allows_text is False:
                can_format_here = True
            else:
                # Aucun renseignement suffisant : s'abstenir.
                can_format_here = False

        if can_format_here:
            desired_gaps: list[str] = []
            for index in range(len(node.children) + 1):
                level = depth + 1 if index < len(node.children) else depth
                desired_gaps.append("\n" + indent * level)
            changed_this_node = False
            for (start, end, old_gap), desired in zip(gaps, desired_gaps):
                # Les gaps sont déjà connus sans texte significatif. Par sécurité,
                # ne réécrire que des blancs XML.
                if not _is_blank(old_gap) or old_gap == desired:
                    continue
                replacements.append(FormatReplacement(start, end, desired))
                changed_this_node = True
            if changed_this_node:
                formatted_nodes.add(node.opening.start)
        elif actual_inline or schema_inline or inherited_inline:
            protected += 1

        # Une zone réellement inline/mixte protège aussi ses descendants : on ne
        # « beautifie » pas un <app> ou <note> inclus dans une phrase à l'insu de
        # l'éditeur. Une simple ambiguïté RNG, en revanche, n'interdit pas aux
        # enfants de se classifier eux-mêmes.
        child_inline = inherited_inline or actual_inline or schema_inline
        for child in reversed(node.children):
            pending.append((child, depth + 1, child_inline))

    # Les gaps de niveaux différents sont disjoints : le texte formaté est
    # assemblé en un seul passage (red team 2, A4 : une copie du texte par
    # remplacement coûtait le carré de leur nombre).
    unique: dict[tuple[int, int], FormatReplacement] = {}
    for repl in replacements:
        unique[(repl.start, repl.end)] = repl
    ordered = tuple(sorted(unique.values(), key=lambda r: r.start))
    pieces, cursor = [], 0
    for repl in ordered:
        pieces.append(text[cursor:repl.start])
        pieces.append(repl.text)
        cursor = repl.end
    pieces.append(text[cursor:])
    out = "".join(pieces)

    return FormatResult(
        text=out,
        replacements=ordered,
        formatted_elements=len(formatted_nodes),
        protected_elements=protected,
    )
