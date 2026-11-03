# -*- coding: utf-8 -*-
"""Recherche XPath indépendante de Qt pour l'éditeur TEI.

Le moteur utilise lxml lorsque disponible afin d'offrir XPath 1.0 complet.
Pour les documents TEI portant l'espace de noms par défaut, une requête simple
comme ``//note`` est automatiquement réessayée comme ``//tei:note`` si la
requête XPath standard ne renvoie aucun résultat. Les utilisateurs avancés
peuvent employer explicitement le préfixe ``tei:``.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Iterable

from xml_tag_pairs import scan_xml_tags, tag_pairs

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"
_NAME_RE = re.compile(r"[A-Za-z_][\w:.-]*")


class XPathUnavailable(RuntimeError):
    pass


class XPathQueryError(ValueError):
    pass


@dataclass(frozen=True)
class XPathMatch:
    line: int
    position: int
    end_position: int
    tag: str
    path: str
    preview: str


@dataclass(frozen=True)
class XPathSearchResult:
    expression: str
    effective_expression: str
    matches: tuple[XPathMatch, ...]
    scalar_value: str | None = None
    ignored_non_elements: int = 0
    namespace_fallback_used: bool = False


def _local_name(tag: str) -> str:
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag.split(":", 1)[-1]


def _find_tag_end(text: str, start: int) -> int | None:
    quote = ""
    i = start
    while i < len(text):
        ch = text[i]
        if quote:
            if ch == quote:
                quote = ""
        else:
            if ch in {'"', "'"}:
                quote = ch
            elif ch == ">":
                return i
        i += 1
    return None


def _opening_tags(text: str) -> list[tuple[str, int]]:
    """Retourne les balises ouvrantes XML dans l'ordre du document."""
    result: list[tuple[str, int]] = []
    i = 0
    while i < len(text):
        lt = text.find("<", i)
        if lt < 0:
            break
        if text.startswith("<!--", lt):
            end = text.find("-->", lt + 4)
            i = len(text) if end < 0 else end + 3
            continue
        if text.startswith("<![CDATA[", lt):
            end = text.find("]]>", lt + 9)
            i = len(text) if end < 0 else end + 3
            continue
        if text.startswith("<?", lt):
            end = text.find("?>", lt + 2)
            i = len(text) if end < 0 else end + 2
            continue
        if text.startswith("<!", lt):
            end = _find_tag_end(text, lt + 2)
            i = len(text) if end is None else end + 1
            continue
        if text.startswith("</", lt):
            end = _find_tag_end(text, lt + 2)
            i = len(text) if end is None else end + 1
            continue
        m = _NAME_RE.match(text, lt + 1)
        end = _find_tag_end(text, lt + 1)
        if m:
            result.append((m.group(0), lt))
        i = len(text) if end is None else end + 1
    return result


def _rewrite_unprefixed_tei_steps(expression: str) -> str:
    """Préfixe les noms d'éléments simples situés après /, // ou ::.

    Cette transformation volontairement conservatrice ne touche ni les
    attributs, ni les fonctions, ni les axes. Elle suffit notamment pour
    ``//note``, ``//div/p`` et ``descendant::note``.
    """
    axis_names = {
        "ancestor", "ancestor-or-self", "attribute", "child", "descendant",
        "descendant-or-self", "following", "following-sibling", "namespace",
        "parent", "preceding", "preceding-sibling", "self",
    }
    pattern = re.compile(r"(?P<sep>//|/|::)(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)(?!\s*(?:::|\())")

    def repl(match: re.Match) -> str:
        name = match.group("name")
        if name in axis_names:
            return match.group(0)
        return f"{match.group('sep')}tei:{name}"

    out = pattern.sub(repl, expression)
    # Expression relative très simple : note, note/p, etc.
    out = re.sub(
        r"^(?P<name>[A-Za-z_][A-Za-z0-9_.-]*)(?!\s*(?:::|\())",
        lambda m: f"tei:{m.group('name')}" if m.group("name") not in axis_names else m.group(0),
        out,
        count=1,
    )
    return out


def _element_range_map(text: str) -> dict[int, int]:
    """Retourne ``début ouverture -> fin élément`` pour le XML source.

    Le calcul reste lexical afin que la sélection XPath recouvre exactement le
    texte saisi par l'utilisateur (préfixes, espaces et attributs compris). Les
    éléments autofermants se terminent à leur propre ``>``, les autres à la fin
    de leur balise fermante structurellement appariée.
    """
    ranges: dict[int, int] = {}
    for token in scan_xml_tags(text):
        if token.kind == "self":
            ranges[token.start] = token.end
    for pair in tag_pairs(text):
        ranges[pair.opening.start] = pair.closing.end
    return ranges


def _position_map(root, text: str) -> dict:
    """``{élément: début de sa balise ouvrante}``, par l'élément lui-même
    (red team 2, A3) : son chemin (``getpath``) comptait ses frères, pour
    chaque élément du document. Le dictionnaire garde les éléments en vie :
    lxml rend alors les mêmes objets aux résultats d'une requête."""
    lexical = _opening_tags(text)
    elements = [el for el in root.iter() if isinstance(getattr(el, "tag", None), str)]
    mapping: dict = {}
    j = 0
    for el in elements:
        target = _local_name(el.tag)
        found = None
        # En XML bien formé, les deux séquences sont normalement identiques.
        # La petite recherche en avant rend le mapping tolérant à d'éventuelles
        # constructions que le scanner lexical aurait ignorées.
        for k in range(j, min(len(lexical), j + 12)):
            if _local_name(lexical[k][0]) == target:
                found = k
                break
        if found is None:
            continue
        _raw_name, pos = lexical[found]
        j = found + 1
        mapping[el] = pos
    return mapping


def _display_path(el, ranks=None) -> str:
    """Chemin lisible, indépendant des préfixes de namespace lxml. *ranks* :
    ``{parent: ({nom: nombre}, {enfant: rang})}``, fait une fois par parent
    et partagé entre les résultats d'une requête (red team 2, A3)."""
    ranks = {} if ranks is None else ranks
    parts: list[str] = []
    current = el
    while current is not None and isinstance(getattr(current, "tag", None), str):
        name = _local_name(current.tag)
        parent = current.getparent()
        index_suffix = ""
        if parent is not None:
            known = ranks.get(parent)
            if known is None:
                counts, rank = {}, {}
                for child in parent:
                    if isinstance(getattr(child, "tag", None), str):
                        child_name = _local_name(child.tag)
                        counts[child_name] = counts.get(child_name, 0) + 1
                        rank[child] = counts[child_name]
                known = ranks[parent] = (counts, rank)
            counts, rank = known
            if counts.get(name, 0) > 1 and current in rank:
                index_suffix = f"[{rank[current]}]"
        parts.append(name + index_suffix)
        current = parent
    return "/" + "/".join(reversed(parts))


def _preview(el, limit: int = 180) -> str:
    text = " ".join("".join(el.itertext()).split())
    if not text:
        attrs = " ".join(f'{_local_name(k)}="{v}"' for k, v in el.attrib.items())
        text = f"<{_local_name(el.tag)}{(' ' + attrs) if attrs else ''}>"
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def search_xpath(xml_text: str, expression: str) -> XPathSearchResult:
    expression = (expression or "").strip()
    if not expression:
        raise XPathQueryError("EMPTY_XPATH")
    try:
        from lxml import etree as LET
    except Exception as exc:  # pragma: no cover - dépend de l'environnement
        raise XPathUnavailable(str(exc)) from exc

    try:
        parser = LET.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)
        root = LET.fromstring((xml_text or "").encode("utf-8"), parser=parser)
    except Exception as exc:
        raise XPathQueryError(str(exc)) from exc

    namespaces = {"tei": TEI_NS, "xml": XML_NS}
    effective = expression
    fallback = False
    try:
        value = root.xpath(expression, namespaces=namespaces, smart_strings=False)
    except Exception as exc:
        raise XPathQueryError(str(exc)) from exc

    # Confort TEI : XPath 1.0 n'applique jamais l'espace de noms par défaut aux
    # noms non préfixés. Si //note ne trouve rien dans une TEI namespacée, on
    # réessaie donc automatiquement avec //tei:note.
    root_ns = root.tag[1:].split("}", 1)[0] if isinstance(root.tag, str) and root.tag.startswith("{") else ""
    if isinstance(value, list) and not value and root_ns == TEI_NS and "tei:" not in expression:
        rewritten = _rewrite_unprefixed_tei_steps(expression)
        if rewritten != expression:
            try:
                retry = root.xpath(rewritten, namespaces=namespaces, smart_strings=False)
            except Exception:
                retry = []
            if retry:
                value = retry
                effective = rewritten
                fallback = True

    if not isinstance(value, list):
        return XPathSearchResult(
            expression=expression,
            effective_expression=effective,
            matches=(),
            scalar_value=str(value),
            namespace_fallback_used=fallback,
        )

    position_map = _position_map(root, xml_text or "")
    range_map = _element_range_map(xml_text or "")
    ranks: dict = {}
    starts: list[int] = []
    matches: list[XPathMatch] = []
    ignored = 0
    for item in value:
        if not isinstance(item, LET._Element) or not isinstance(getattr(item, "tag", None), str):
            ignored += 1
            continue
        pos = position_map.get(item, -1)
        line = int(getattr(item, "sourceline", 0) or 0)
        if pos < 0 and line > 0:
            # Repli : au minimum, aller au début de la ligne source.
            if not starts:
                starts = [0]
                starts.extend(m.end() for m in re.finditer("\n", xml_text or ""))
            pos = starts[line - 1] if line - 1 < len(starts) else 0
        start = max(0, pos)
        end = range_map.get(start, start)
        matches.append(XPathMatch(
            line=line,
            position=start,
            end_position=max(start, end),
            tag=_local_name(item.tag),
            path=_display_path(item, ranks),
            preview=_preview(item),
        ))

    return XPathSearchResult(
        expression=expression,
        effective_expression=effective,
        matches=tuple(matches),
        ignored_non_elements=ignored,
        namespace_fallback_used=fallback,
    )
