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
import xml.etree.ElementTree as ET

from xml_tag_pairs import XmlTagToken, scan_xml_tags

_XML_SPACE_RE = re.compile(r"\bxml:space\s*=\s*(['\"])(.*?)\1", re.S | re.I)


def _local_qname(name: str) -> str:
    return (name or "").split(":", 1)[-1]


@dataclass
class _Node:
    name: str
    opening: XmlTagToken
    closing: XmlTagToken | None = None
    children: list["_Node"] = field(default_factory=list)

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


def _build_tree(xml_text: str) -> tuple[_Node | None, str]:
    """Construit l'arbre lexical des éléments après contrôle de bonne formation."""
    text = str(xml_text or "")
    try:
        ET.fromstring(text)
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
    return roots[0], ""


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

    def visit(node: _Node, depth: int, inherited_preserve: bool = False, inherited_inline: bool = False):
        nonlocal protected
        if node.self_closing or node.closing is None:
            return

        raw_open = text[node.opening.start:node.opening.end]
        own_xml_preserve = _xml_space_preserve(raw_open)
        custom_mode = _custom_formatting(custom_config, node.name)

        # xml:space=preserve et formatting=preserve protègent tout le sous-arbre.
        subtree_preserve = inherited_preserve or own_xml_preserve or custom_mode == "preserve"
        if subtree_preserve:
            protected += 1
            return

        gaps = _direct_gaps(text, node)
        direct_nonwhite_text = any(chunk.strip() for _, _, chunk in gaps)
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
                # ne réécrire que du blanc pur.
                if old_gap.strip() or old_gap == desired:
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
        for child in node.children:
            visit(child, depth + 1, False, child_inline)

    visit(root, 0)

    # Les gaps de niveaux différents sont disjoints. On applique en ordre
    # décroissant pour conserver les offsets calculés dans le texte original.
    unique: dict[tuple[int, int], FormatReplacement] = {}
    for repl in replacements:
        unique[(repl.start, repl.end)] = repl
    ordered = tuple(sorted(unique.values(), key=lambda r: r.start))
    out = text
    for repl in reversed(ordered):
        out = out[:repl.start] + repl.text + out[repl.end:]

    return FormatResult(
        text=out,
        replacements=ordered,
        formatted_elements=len(formatted_nodes),
        protected_elements=protected,
    )
