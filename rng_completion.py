# -*- coding: utf-8 -*-
"""Complétion contextuelle à partir d'un schéma RELAX NG (syntaxe XML).

Le module est volontairement indépendant de Qt. Il fournit deux briques :

* :func:`load_completion_model` analyse un RNG (y compris ``include`` et
  ``externalRef`` locaux) et construit un modèle des contenus et attributs ;
* :func:`analyze_xml_context` détermine, à partir du texte XML et de la
  position du curseur, si l'utilisateur attend plutôt un élément enfant ou un
  attribut. Le scanner lexical continue de fonctionner pendant une édition
  momentanément mal formée.

Depuis la V0.5.4, la complétion des éléments ne se contente plus de l'union des
éléments possibles dans le parent : elle conserve la structure RELAX NG
(``group``, ``choice``, répétitions et ``interleave``) et calcule les éléments
admissibles à la position du curseur à partir des frères déjà rencontrés. Si le
curseur est placé au milieu d'un contenu existant, les frères situés à droite
sont également utilisés pour éliminer les insertions incompatibles.

Depuis la V0.5.5, :class:`XmlContextCache` mémorise des points de reprise du
scanner lexical. Une modification invalide uniquement les points situés après
la zone modifiée ; les appels suivants de Ctrl+Espace ne rescannent donc plus
systématiquement tout le document depuis le premier caractère.

Les name classes ouvertes (``anyName`` / ``nsName``) ne sont pas énumérées.
Depuis la V0.5.7, les valeurs d'attributs explicitement finies dans le RNG
(``value`` / ``choice`` / ``ref``) sont en revanche proposées. Les patterns
ouverts (``data``, ``text``, listes libres, etc.) restent volontairement sans
complétion afin de ne pas présenter une liste partielle comme exhaustive.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse, unquote
import os
import re
import xml.etree.ElementTree as ET

from xml_references import parse_pointer

RNG_NS = "http://relaxng.org/ns/structure/1.0"
RNG = "{" + RNG_NS + "}"
_XML_NAME_RE = re.compile(r"[A-Za-z_][\w:.-]*")
_ATTR_RE = re.compile(r"\b([A-Za-z_][\w:.-]*)\s*=\s*(['\"]).*?\2", re.S)


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def _is_rng_node(node: ET.Element) -> bool:
    tag = getattr(node, "tag", "")
    return isinstance(tag, str) and (tag.startswith(RNG) or "}" not in tag)


def _local_qname(name: str) -> str:
    return (name or "").split(":", 1)[-1]


def _names_match(left: str, right: str) -> bool:
    return left == right or _local_qname(left) == _local_qname(right)


def _href_path(base_file: Path, href: str) -> Path | None:
    href = (href or "").strip()
    if not href:
        return None
    parsed = urlparse(href)
    if parsed.scheme == "file":
        raw = unquote(parsed.path)
        if os.name == "nt" and re.match(r"^/[A-Za-z]:/", raw):
            raw = raw[1:]
        return Path(raw).expanduser().resolve()
    if parsed.scheme:
        # Les RNG http(s) sont normalement déjà transformés en miroir local par
        # schema_resolution.py. Un href distant résiduel n'est pas téléchargé ici.
        return None
    return (base_file.parent / unquote(href)).expanduser().resolve()


def _explicit_names(pattern: ET.Element) -> tuple[str, ...]:
    """Retourne les noms finis d'un pattern element/attribute.

    RELAX NG autorise @name ou une name class enfant (<name>, <choice><name>…).
    Les classes ouvertes anyName/nsName ne sont pas énumérables et sont donc
    volontairement ignorées pour la complétion.
    """
    direct = (pattern.get("name") or "").strip()
    if direct:
        return (direct,)
    names: list[str] = []
    for child in pattern:
        if _local(child.tag) == "name" and (child.text or "").strip():
            names.append((child.text or "").strip())
        elif _local(child.tag) == "choice":
            for name_node in child:
                if _local(name_node.tag) == "name" and (name_node.text or "").strip():
                    names.append((name_node.text or "").strip())
    return tuple(dict.fromkeys(names))


# ---------------------------------------------------------------------------
# Petit automate régulier pour la séquence des ELEMENTS enfants uniquement.
# Les attributs et le texte n'ajoutent aucun jeton à cette séquence.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _Pattern:
    kind: str
    names: tuple[str, ...] = ()
    parts: tuple["_Pattern", ...] = ()


_FAIL = _Pattern("fail")
_EMPTY = _Pattern("empty")


def _token(names: tuple[str, ...] | list[str] | set[str]) -> _Pattern:
    vals = tuple(sorted(dict.fromkeys(n for n in names if n), key=str.casefold))
    return _Pattern("token", vals) if vals else _FAIL


def _choice(*patterns: _Pattern) -> _Pattern:
    flat: list[_Pattern] = []
    for pattern in patterns:
        if pattern == _FAIL:
            continue
        if pattern.kind == "choice":
            flat.extend(pattern.parts)
        else:
            flat.append(pattern)
    unique = tuple(dict.fromkeys(flat))
    if not unique:
        return _FAIL
    if len(unique) == 1:
        return unique[0]
    return _Pattern("choice", parts=unique)


def _seq(*patterns: _Pattern) -> _Pattern:
    flat: list[_Pattern] = []
    for pattern in patterns:
        if pattern == _FAIL:
            return _FAIL
        if pattern == _EMPTY:
            continue
        if pattern.kind == "seq":
            flat.extend(pattern.parts)
        else:
            flat.append(pattern)
    if not flat:
        return _EMPTY
    if len(flat) == 1:
        return flat[0]
    return _Pattern("seq", parts=tuple(flat))


def _interleave(*patterns: _Pattern) -> _Pattern:
    flat: list[_Pattern] = []
    for pattern in patterns:
        if pattern == _FAIL:
            return _FAIL
        if pattern == _EMPTY:
            continue
        if pattern.kind == "interleave":
            flat.extend(pattern.parts)
        else:
            flat.append(pattern)
    if not flat:
        return _EMPTY
    if len(flat) == 1:
        return flat[0]
    return _Pattern("interleave", parts=tuple(flat))


def _star(pattern: _Pattern) -> _Pattern:
    if pattern in {_FAIL, _EMPTY}:
        return _EMPTY
    if pattern.kind == "star":
        return pattern
    return _Pattern("star", parts=(pattern,))


@lru_cache(maxsize=None)
def _nullable(pattern: _Pattern) -> bool:
    if pattern.kind == "empty":
        return True
    if pattern.kind in {"fail", "token"}:
        return False
    if pattern.kind == "choice":
        return any(_nullable(part) for part in pattern.parts)
    if pattern.kind in {"seq", "interleave"}:
        return all(_nullable(part) for part in pattern.parts)
    if pattern.kind == "star":
        return True
    return False


@lru_cache(maxsize=None)
def _all_token_names(pattern: _Pattern) -> tuple[str, ...]:
    result: set[str] = set()
    if pattern.kind == "token":
        result.update(pattern.names)
    else:
        for part in pattern.parts:
            result.update(_all_token_names(part))
    return tuple(sorted(result, key=str.casefold))


@lru_cache(maxsize=None)
def _first_names(pattern: _Pattern) -> tuple[str, ...]:
    result: set[str] = set()
    if pattern.kind == "token":
        result.update(pattern.names)
    elif pattern.kind == "choice":
        for part in pattern.parts:
            result.update(_first_names(part))
    elif pattern.kind == "seq":
        for part in pattern.parts:
            result.update(_first_names(part))
            if not _nullable(part):
                break
    elif pattern.kind == "interleave":
        for part in pattern.parts:
            result.update(_first_names(part))
    elif pattern.kind == "star":
        result.update(_first_names(pattern.parts[0]))
    return tuple(sorted(result, key=str.casefold))


@lru_cache(maxsize=None)
def _derive(pattern: _Pattern, element_name: str) -> _Pattern:
    """Dérivée du pattern par un élément enfant nommé *element_name*."""
    kind = pattern.kind
    if kind in {"fail", "empty"}:
        return _FAIL
    if kind == "token":
        return _EMPTY if any(_names_match(element_name, name) for name in pattern.names) else _FAIL
    if kind == "choice":
        return _choice(*(_derive(part, element_name) for part in pattern.parts))
    if kind == "seq":
        alternatives: list[_Pattern] = []
        prefix_nullable = True
        for index, part in enumerate(pattern.parts):
            if not prefix_nullable:
                break
            derived = _derive(part, element_name)
            if derived != _FAIL:
                alternatives.append(_seq(derived, *pattern.parts[index + 1:]))
            prefix_nullable = prefix_nullable and _nullable(part)
        return _choice(*alternatives)
    if kind == "interleave":
        alternatives: list[_Pattern] = []
        for index, part in enumerate(pattern.parts):
            derived = _derive(part, element_name)
            if derived == _FAIL:
                continue
            rest = list(pattern.parts)
            rest[index] = derived
            alternatives.append(_interleave(*rest))
        return _choice(*alternatives)
    if kind == "star":
        inner = pattern.parts[0]
        return _seq(_derive(inner, element_name), pattern)
    return _FAIL


def _consume(pattern: _Pattern, element_names: tuple[str, ...] | list[str]) -> _Pattern:
    state = pattern
    for name in element_names:
        state = _derive(state, name)
        if state == _FAIL:
            break
    return state


@dataclass(frozen=True)
class CompletionModel:
    schema_path: Path
    start_elements: tuple[str, ...]
    children: dict[str, tuple[str, ...]]
    attributes: dict[str, tuple[str, ...]]
    attribute_values: dict[str, dict[str, tuple[str, ...]]]
    content_patterns: dict[str, _Pattern]
    # V0.8.1 : indique si le contenu direct d'un élément peut contenir du texte
    # au sens RELAX NG. False est une information positive (« element-only »),
    # tandis qu'un nom absent reste inconnu.
    content_allows_text: dict[str, bool]

    def _lookup(self, mapping: dict[str, tuple[str, ...]], element: str | None) -> tuple[str, ...]:
        if not element:
            return ()
        if element in mapping:
            return mapping[element]
        local = _local_qname(element)
        if local in mapping:
            return mapping[local]
        merged: list[str] = []
        for key, values in mapping.items():
            if _local_qname(key) == local:
                merged.extend(values)
        return tuple(sorted(set(merged), key=str.casefold))

    def _lookup_pattern(self, element: str | None) -> _Pattern | None:
        if not element:
            return None
        if element in self.content_patterns:
            return self.content_patterns[element]
        local = _local_qname(element)
        if local in self.content_patterns:
            return self.content_patterns[local]
        matches = [pattern for key, pattern in self.content_patterns.items()
                   if _local_qname(key) == local]
        if not matches:
            return None
        return _choice(*matches)

    def child_elements(self, parent: str | None) -> tuple[str, ...]:
        """Liste large historique : union des enfants possibles du parent."""
        return self.start_elements if not parent else self._lookup(self.children, parent)

    def child_elements_at(
        self,
        parent: str | None,
        preceding_siblings: tuple[str, ...] = (),
        following_siblings: tuple[str, ...] = (),
    ) -> tuple[str, ...]:
        """Éléments insérables à une position précise du contenu de *parent*.

        ``preceding_siblings`` et ``following_siblings`` sont les noms des
        éléments enfants directs situés respectivement avant et après le
        curseur. Les nœuds texte sont volontairement absents : pour la
        complétion des balises, ils ne changent pas l'ordre relatif des
        éléments enfants.

        Si le préfixe existant est déjà impossible pour le RNG (document en
        cours de correction), on revient à la liste large historique plutôt
        que de laisser la complétion totalement muette.
        """
        if not parent:
            return self.start_elements
        pattern = self._lookup_pattern(parent)
        if pattern is None:
            return self.child_elements(parent)

        residual = _consume(pattern, preceding_siblings)
        if residual == _FAIL:
            return self.child_elements(parent)

        candidates = list(_first_names(residual))
        if not candidates:
            return ()

        # Si le suffixe existant est lui-même compatible avec la position
        # actuelle, on peut l'utiliser comme contrainte à droite. Cela permet,
        # par exemple, de ne pas proposer un second <b> juste avant le <b>
        # obligatoire déjà présent dans une séquence <a>, <b>.
        if following_siblings and _consume(residual, following_siblings) != _FAIL:
            candidates = [
                name for name in candidates
                if _consume(_derive(residual, name), following_siblings) != _FAIL
            ]
        return tuple(sorted(dict.fromkeys(candidates), key=str.casefold))


    def allows_text(self, element: str | None) -> bool | None:
        """Indique si le RNG autorise du texte direct dans ``element``.

        ``None`` signifie que l'élément n'est pas connu du modèle ; le
        formateur TEI doit alors s'abstenir plutôt que supposer un contenu
        purement structurel.
        """
        if not element:
            return None
        if element in self.content_allows_text:
            return bool(self.content_allows_text[element])
        local = _local_qname(element)
        if local in self.content_allows_text:
            return bool(self.content_allows_text[local])
        matches = [bool(value) for key, value in self.content_allows_text.items()
                   if _local_qname(key) == local]
        return any(matches) if matches else None

    def allowed_attributes(self, element: str | None) -> tuple[str, ...]:
        return self._lookup(self.attributes, element)

    def allowed_attribute_values(self, element: str | None, attribute: str | None) -> tuple[str, ...]:
        """Valeurs explicitement finies autorisées pour ``element/@attribute``.

        Une valeur vide signifie ici « aucune liste finie connue » ; les
        attributs ouverts par ``data``/``text`` ne sont jamais réduits à une
        liste partielle de suggestions.
        """
        if not element or not attribute:
            return ()
        local_element = _local_qname(element)
        candidates = []
        for key, mapping in self.attribute_values.items():
            if key == element or _local_qname(key) == local_element:
                candidates.append(mapping)
        if not candidates:
            return ()
        local_attr = _local_qname(attribute)
        merged: list[str] = []
        for mapping in candidates:
            if attribute in mapping:
                merged.extend(value for value in mapping[attribute] if value != "")
            else:
                for key, values in mapping.items():
                    if _local_qname(key) == local_attr:
                        merged.extend(value for value in values if value != "")
        return tuple(sorted(dict.fromkeys(merged), key=str.casefold))


class _GrammarIndex:
    def __init__(self, schema_path: Path):
        self.schema_path = schema_path.resolve()
        self.roots: list[ET.Element] = []
        self.roots_by_path: dict[Path, ET.Element] = {}
        self.node_sources: dict[int, Path] = {}
        self.defines: dict[str, list[ET.Element]] = {}
        self.element_nodes: dict[str, list[ET.Element]] = {}
        self._compiled_ref_cache: dict[str, _Pattern] = {}
        self._loaded_paths: set[Path] = set()
        self._load_file(self.schema_path)
        self._index()

    def _load_file(self, path: Path) -> None:
        path = path.expanduser().resolve()
        if path in self._loaded_paths or not path.is_file():
            return
        self._loaded_paths.add(path)
        root = ET.parse(path).getroot()
        self.roots.append(root)
        self.roots_by_path[path] = root
        for node in root.iter():
            self.node_sources[id(node)] = path
        for node in root.iter():
            if _local(node.tag) not in {"include", "externalRef"}:
                continue
            dep = _href_path(path, node.get("href") or "")
            if dep is not None:
                self._load_file(dep)

    def _index(self) -> None:
        for root in self.roots:
            for node in root.iter():
                kind = _local(node.tag)
                if kind == "define":
                    name = (node.get("name") or "").strip()
                    if name:
                        self.defines.setdefault(name, []).append(node)
                elif kind == "element":
                    for name in _explicit_names(node):
                        self.element_nodes.setdefault(name, []).append(node)
                        local = _local_qname(name)
                        if local != name:
                            self.element_nodes.setdefault(local, []).append(node)

    def _external_root(self, node: ET.Element) -> ET.Element | None:
        source = self.node_sources.get(id(node))
        if source is None:
            return None
        dep = _href_path(source, node.get("href") or "")
        if dep is None:
            return None
        return self.roots_by_path.get(dep)

    def _all_child_elements(self, node: ET.Element, visiting: frozenset[str]) -> set[str]:
        """Union finie de tous les éléments atteignables au niveau courant."""
        kind = _local(node.tag)
        if kind == "element":
            return set(_explicit_names(node))
        if kind in {"ref", "parentRef"}:
            name = (node.get("name") or "").strip()
            if not name or name in visiting:
                return set()
            result: set[str] = set()
            for definition in self.defines.get(name, ()):
                for child in definition:
                    result.update(self._all_child_elements(child, visiting | {name}))
            return result
        if kind == "externalRef":
            root = self._external_root(node)
            if root is None:
                return set()
            return self._all_child_elements(root, visiting)
        if kind in {"attribute", "text", "data", "value", "empty", "notAllowed", "name", "anyName", "nsName", "list"}:
            return set()
        result: set[str] = set()
        for child in node:
            result.update(self._all_child_elements(child, visiting))
        return result

    def _attributes(self, node: ET.Element, visiting: frozenset[str]) -> set[str]:
        kind = _local(node.tag)
        if kind == "attribute":
            return set(_explicit_names(node))
        if kind == "element":
            return set()
        if kind in {"ref", "parentRef"}:
            name = (node.get("name") or "").strip()
            if not name or name in visiting:
                return set()
            result: set[str] = set()
            for definition in self.defines.get(name, ()):
                for child in definition:
                    result.update(self._attributes(child, visiting | {name}))
            return result
        if kind == "externalRef":
            root = self._external_root(node)
            return self._attributes(root, visiting) if root is not None else set()
        if kind in {"text", "data", "value", "empty", "notAllowed", "name", "anyName", "nsName", "list"}:
            return set()
        result: set[str] = set()
        for child in node:
            result.update(self._attributes(child, visiting))
        return result

    def _finite_values(self, node: ET.Element, visiting: frozenset[str]) -> set[str] | None:
        """Retourne une énumération finie sûre, ou ``None`` si le pattern est ouvert.

        Cette fonction est volontairement conservative. Elle couvre les formes
        usuelles produites par les schémas TEI (``value``, ``choice`` et
        références vers des définitions finies), sans prétendre énumérer les
        datatypes ou listes potentiellement infinies.
        """
        kind = _local(node.tag)
        if kind == "value":
            return {(node.text or "").strip()}
        if kind == "empty":
            return {""}
        if kind in {"data", "text", "list", "mixed", "anyName", "nsName", "name", "notAllowed"}:
            return None
        if kind in {"ref", "parentRef"}:
            name = (node.get("name") or "").strip()
            if not name or name in visiting:
                return None
            defs = self.defines.get(name, ())
            if not defs:
                return None
            result: set[str] = set()
            for definition in defs:
                values = self._finite_values_container(list(definition), visiting | {name})
                if values is None:
                    return None
                result.update(values)
            return result
        if kind == "externalRef":
            root = self._external_root(node)
            return self._finite_values(root, visiting) if root is not None else None
        if kind == "choice":
            result: set[str] = set()
            for child in node:
                values = self._finite_values(child, visiting)
                if values is None:
                    return None
                result.update(values)
            return result
        if kind == "optional":
            values = self._finite_values_container(list(node), visiting)
            if values is None:
                return None
            return set(values) | {""}
        if kind in {"define", "start", "grammar", "div", "include"}:
            return self._finite_values_container(list(node), visiting)
        # group/interleave/repetitions peuvent construire des chaînes ou une
        # infinité de valeurs : ne pas les présenter comme une énumération.
        return None

    def _finite_values_container(self, children: list[ET.Element], visiting: frozenset[str]) -> set[str] | None:
        # Les RNG TEI générés contiennent fréquemment des annotations dans un
        # autre namespace (a:documentation). Elles ne font pas partie du pattern.
        meaningful = [
            child for child in children
            if _is_rng_node(child) and _local(child.tag) not in {"name"}
        ]
        if not meaningful:
            return {""}
        if len(meaningful) != 1:
            return None
        return self._finite_values(meaningful[0], visiting)

    def _attribute_value_specs(
        self, node: ET.Element, visiting: frozenset[str]
    ) -> dict[str, list[set[str] | None]]:
        """Collecte les patterns de valeurs associés aux attributs atteignables."""
        kind = _local(node.tag)
        if kind == "attribute":
            values = self._finite_values_container(list(node), visiting)
            return {name: [values] for name in _explicit_names(node)}
        if kind == "element":
            return {}
        if kind in {"ref", "parentRef"}:
            name = (node.get("name") or "").strip()
            if not name or name in visiting:
                return {}
            out: dict[str, list[set[str] | None]] = {}
            for definition in self.defines.get(name, ()):
                for child in definition:
                    child_specs = self._attribute_value_specs(child, visiting | {name})
                    for attr, specs in child_specs.items():
                        out.setdefault(attr, []).extend(specs)
            return out
        if kind == "externalRef":
            root = self._external_root(node)
            return self._attribute_value_specs(root, visiting) if root is not None else {}
        if kind in {"text", "data", "value", "empty", "notAllowed", "name", "anyName", "nsName", "list"}:
            return {}
        out: dict[str, list[set[str] | None]] = {}
        for child in node:
            child_specs = self._attribute_value_specs(child, visiting)
            for attr, specs in child_specs.items():
                out.setdefault(attr, []).extend(specs)
        return out

    def _allows_text(self, node: ET.Element, visiting: frozenset[str]) -> bool:
        """Détecte conservativement les patterns RNG qui admettent du texte.

        Un élément enfant n'autorise pas, par lui-même, le texte dans son
        parent. Les références sont suivies, y compris dans les includes déjà
        indexés par ``_GrammarIndex``.
        """
        kind = _local(node.tag)
        if kind in {"text", "data", "value", "list", "mixed"}:
            return True
        if kind in {"element", "attribute", "empty", "notAllowed", "name", "anyName", "nsName"}:
            return False
        if kind in {"ref", "parentRef"}:
            name = (node.get("name") or "").strip()
            if not name or name in visiting:
                return False
            return any(
                self._allows_text(child, visiting | {name})
                for definition in self.defines.get(name, ())
                for child in definition
            )
        if kind == "externalRef":
            root = self._external_root(node)
            return self._allows_text(root, visiting) if root is not None else False
        return any(self._allows_text(child, visiting) for child in node if _is_rng_node(child))

    def _element_content_allows_text(self, nodes: list[ET.Element]) -> bool:
        return any(
            self._allows_text(child, frozenset())
            for elem in nodes
            for child in elem
            if _is_rng_node(child)
        )

    def _compile_ref(self, name: str, visiting: frozenset[str]) -> _Pattern:
        if not name or name in visiting:
            return _FAIL
        cached = self._compiled_ref_cache.get(name)
        if cached is not None:
            return cached
        definitions = self.defines.get(name, ())
        if not definitions:
            return _FAIL
        compiled = [self._compile_children(definition, visiting | {name}) for definition in definitions]
        # Plusieurs <define name="…"> utilisent obligatoirement combine en RNG.
        # En pratique TEI emploie largement combine="choice" ; on respecte
        # combine="interleave" lorsqu'il est explicitement demandé.
        combines = {(definition.get("combine") or "").strip() for definition in definitions}
        if "interleave" in combines:
            result = _interleave(*compiled)
        else:
            result = _choice(*compiled)
        self._compiled_ref_cache[name] = result
        return result

    def _compile_children(self, node: ET.Element, visiting: frozenset[str]) -> _Pattern:
        return _seq(*(self._compile_pattern(child, visiting) for child in node))

    def _compile_pattern(self, node: ET.Element, visiting: frozenset[str]) -> _Pattern:
        kind = _local(node.tag)
        if kind == "element":
            return _token(_explicit_names(node))
        if kind in {"attribute", "text", "data", "value", "empty", "list", "name", "anyName", "nsName"}:
            return _EMPTY
        if kind == "notAllowed":
            return _FAIL
        if kind in {"ref", "parentRef"}:
            return self._compile_ref((node.get("name") or "").strip(), visiting)
        if kind == "choice":
            return _choice(*(self._compile_pattern(child, visiting) for child in node))
        if kind == "group":
            return _seq(*(self._compile_pattern(child, visiting) for child in node))
        if kind == "interleave":
            return _interleave(*(self._compile_pattern(child, visiting) for child in node))
        if kind == "optional":
            return _choice(self._compile_children(node, visiting), _EMPTY)
        if kind == "zeroOrMore":
            return _star(self._compile_children(node, visiting))
        if kind == "oneOrMore":
            pattern = self._compile_children(node, visiting)
            return _seq(pattern, _star(pattern))
        if kind == "mixed":
            # mixed ajoute du texte intercalable ; l'ordre des éléments reste
            # celui du pattern enfant pour notre alphabet « balises enfants ».
            return self._compile_children(node, visiting)
        if kind == "externalRef":
            root = self._external_root(node)
            return self._compile_pattern(root, visiting) if root is not None else _FAIL
        if kind == "grammar":
            starts = [child for child in node if _local(child.tag) == "start"]
            return _choice(*(self._compile_children(start, visiting) for start in starts)) if starts else _FAIL
        if kind in {"start", "define"}:
            return self._compile_children(node, visiting)
        # include/div/unknown wrappers : leurs enfants grammaticaux ne sont
        # normalement pas des patterns de contenu. Les traiter en séquence est
        # néanmoins le comportement le plus conservateur pour un RNG simplifié.
        return self._compile_children(node, visiting)

    def start_elements(self) -> set[str]:
        result: set[str] = set()
        for root in self.roots:
            for node in root.iter():
                if _local(node.tag) == "start":
                    for child in node:
                        result.update(self._all_child_elements(child, frozenset()))
        return result

    def _content_pattern_for_nodes(self, nodes: list[ET.Element]) -> _Pattern:
        return _choice(*(self._compile_children(elem, frozenset()) for elem in nodes))

    def build(self) -> CompletionModel:
        children: dict[str, tuple[str, ...]] = {}
        attributes: dict[str, tuple[str, ...]] = {}
        attribute_values: dict[str, dict[str, tuple[str, ...]]] = {}
        content_patterns: dict[str, _Pattern] = {}
        content_allows_text: dict[str, bool] = {}
        canonical_names = sorted({name for name in self.element_nodes if ":" not in name}, key=str.casefold)
        for name in canonical_names:
            nodes = self.element_nodes.get(name, ())
            attr_names: set[str] = set()
            specs: dict[str, list[set[str] | None]] = {}
            for elem in nodes:
                for child in elem:
                    attr_names.update(self._attributes(child, frozenset()))
                    for attr, values in self._attribute_value_specs(child, frozenset()).items():
                        specs.setdefault(attr, []).extend(values)
            pattern = self._content_pattern_for_nodes(list(nodes))
            children[name] = _all_token_names(pattern)
            attributes[name] = tuple(sorted(attr_names, key=str.casefold))
            attribute_values[name] = {
                attr: tuple(sorted(set().union(*(v for v in values if v is not None)), key=str.casefold))
                for attr, values in specs.items()
                if values and all(v is not None for v in values)
            }
            content_patterns[name] = pattern
            content_allows_text[name] = self._element_content_allows_text(list(nodes))

        # Conserver aussi les noms explicitement préfixés s'ils existent.
        for name, nodes in self.element_nodes.items():
            if ":" not in name:
                continue
            attr_names: set[str] = set()
            specs: dict[str, list[set[str] | None]] = {}
            for elem in nodes:
                for child in elem:
                    attr_names.update(self._attributes(child, frozenset()))
                    for attr, values in self._attribute_value_specs(child, frozenset()).items():
                        specs.setdefault(attr, []).extend(values)
            pattern = self._content_pattern_for_nodes(list(nodes))
            children[name] = _all_token_names(pattern)
            attributes[name] = tuple(sorted(attr_names, key=str.casefold))
            attribute_values[name] = {
                attr: tuple(sorted(set().union(*(v for v in values if v is not None)), key=str.casefold))
                for attr, values in specs.items()
                if values and all(v is not None for v in values)
            }
            content_patterns[name] = pattern
            content_allows_text[name] = self._element_content_allows_text(list(nodes))

        return CompletionModel(
            schema_path=self.schema_path,
            start_elements=tuple(sorted(self.start_elements(), key=str.casefold)),
            children=children,
            attributes=attributes,
            attribute_values=attribute_values,
            content_patterns=content_patterns,
            content_allows_text=content_allows_text,
        )


def load_completion_model(schema_path: str | Path) -> CompletionModel:
    """Analyse *schema_path* et retourne le modèle de complétion statique."""
    path = Path(schema_path).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return _GrammarIndex(path).build()


@dataclass(frozen=True)
class XmlCompletionContext:
    kind: str  # "element", "attribute", "attribute_value" ou "none"
    parent_element: str | None = None
    current_element: str | None = None
    prefix: str = ""
    replace_start: int = 0
    replace_end: int = 0
    existing_attributes: tuple[str, ...] = ()
    typed_lt: bool = False
    preceding_siblings: tuple[str, ...] = ()
    following_siblings: tuple[str, ...] = ()
    current_attribute: str | None = None
    quote_char: str = ""


def adapt_pointer_list_value_context(
    context: XmlCompletionContext,
    xml_text: str,
    cursor_position: int,
    allowed_values,
):
    """Adapte une complétion de valeur pour les listes de pointeurs ``#id``.

    Les attributs TEI de type pointeur peuvent contenir plusieurs références
    séparées par des espaces. Lorsque toutes les valeurs proposées sont des
    pointeurs (``#id``, ou ``fichier.xml#id`` vers un autre document), on
    traite donc la valeur comme une liste de tokens :

    * les pointeurs déjà présents ne sont plus proposés ;
    * un token partiellement saisi est seul remplacé ;
    * si le curseur suit exactement un pointeur complet, la complétion prépare
      l'ajout d'un nouveau token au lieu de remplacer le pointeur existant.

    La fonction est volontairement indépendante de Qt. Elle ne prétend pas
    déduire le datatype RNG : le comportement « liste » n'est activé que pour
    une liste finie de suggestions qui sont toutes des pointeurs.
    """
    values = tuple(dict.fromkeys(str(v) for v in allowed_values if str(v)))
    if (
        context.kind != "attribute_value"
        or not values
        or not all(parse_pointer(value) is not None for value in values)
    ):
        return context, values

    text = xml_text or ""
    start = max(0, min(int(context.replace_start), len(text)))
    end = max(start, min(int(context.replace_end), len(text)))
    pos = max(start, min(int(cursor_position), end))
    full_value = text[start:end]
    offset = pos - start
    tokens = list(re.finditer(r"\S+", full_value))
    value_set = set(values)

    active_index = None
    for index, match in enumerate(tokens):
        # Curseur réellement à l'intérieur du token.
        if match.start() <= offset < match.end():
            active_index = index
            break
        # À la fin d'un token incomplet, continuer à filtrer/remplacer ce token.
        # À la fin d'un pointeur complet, préparer au contraire un nouvel item.
        if offset == match.end() and match.group(0) not in value_set:
            active_index = index
            break

    used = {
        match.group(0)
        for index, match in enumerate(tokens)
        if index != active_index
    }
    remaining = tuple(value for value in values if value not in used)

    if active_index is None:
        adapted = replace(
            context,
            prefix="",
            replace_start=pos,
            replace_end=pos,
        )
        return adapted, remaining

    match = tokens[active_index]
    token_prefix = full_value[match.start():offset]
    adapted = replace(
        context,
        prefix=token_prefix,
        replace_start=start + match.start(),
        replace_end=start + match.end(),
    )
    return adapted, remaining


def format_pointer_list_insertion(
    xml_text: str,
    start: int,
    end: int,
    value: str,
) -> tuple[str, int]:
    """Retourne le texte à insérer et la position du curseur qui le suit.

    Lors d'une insertion à largeur nulle dans une valeur de liste de pointeurs,
    ajoute les séparateurs nécessaires sans doubler les espaces déjà présents.
    Un remplacement de token existant reste inchangé.
    """
    text = xml_text or ""
    start = max(0, min(int(start), len(text)))
    end = max(start, min(int(end), len(text)))
    replacement = str(value)
    if start != end or parse_pointer(replacement) is None:
        return replacement, start + len(replacement)

    previous = text[start - 1:start] if start > 0 else ""
    following = text[start:start + 1]
    if previous and not previous.isspace() and previous not in {'"', "'"}:
        replacement = " " + replacement
    if following and not following.isspace() and following not in {'"', "'"}:
        replacement = replacement + " "
    return replacement, start + len(replacement)


def _find_tag_end(text: str, start: int, limit: int) -> int | None:
    quote = ""
    i = start
    while i < limit:
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


def _pop_stack(stack: list[str], child_stacks: list[list[str]], closing: str) -> None:
    if not stack:
        return
    close_local = _local_qname(closing)
    for idx in range(len(stack) - 1, -1, -1):
        if stack[idx] == closing or _local_qname(stack[idx]) == close_local:
            del stack[idx:]
            del child_stacks[idx:]
            return


def _following_direct_children(text: str, pos: int, parent: str | None) -> tuple[str, ...]:
    """Collecte lexicalement les enfants directs situés à droite du curseur."""
    if not parent:
        return ()
    result: list[str] = []
    depth = 0
    i = pos
    limit = len(text)
    while i < limit:
        lt = text.find("<", i)
        if lt < 0:
            break
        if text.startswith("<!--", lt):
            end = text.find("-->", lt + 4)
            if end < 0:
                break
            i = end + 3
            continue
        if text.startswith("<![CDATA[", lt):
            end = text.find("]]>", lt + 9)
            if end < 0:
                break
            i = end + 3
            continue
        if text.startswith("<?", lt):
            end = text.find("?>", lt + 2)
            if end < 0:
                break
            i = end + 2
            continue
        if text.startswith("<!", lt):
            end = _find_tag_end(text, lt + 2, limit)
            if end is None:
                break
            i = end + 1
            continue
        if text.startswith("</", lt):
            m = _XML_NAME_RE.match(text, lt + 2)
            end = _find_tag_end(text, lt + 2, limit)
            if end is None:
                break
            closing = m.group(0) if m else ""
            if depth == 0:
                if closing and _names_match(closing, parent):
                    break
                # Une fermeture inattendue au niveau du parent marque une zone
                # lexicale trop ambiguë : ne pas inventer de suffixe.
                break
            depth -= 1
            i = end + 1
            continue

        m = _XML_NAME_RE.match(text, lt + 1)
        end = _find_tag_end(text, lt + 1, limit)
        if end is None:
            break
        raw = text[lt:end + 1]
        self_closing = bool(re.search(r"/\s*>$", raw))
        if m:
            name = m.group(0)
            if depth == 0:
                result.append(name)
            if not self_closing:
                depth += 1
        i = end + 1
    return tuple(result)


def _attribute_context(
    text: str,
    name: str,
    name_end: int,
    pos: int,
    parent: str | None,
    preceding_siblings: tuple[str, ...] = (),
) -> XmlCompletionContext:
    segment = text[name_end:pos]
    existing = tuple(dict.fromkeys(m.group(1) for m in _ATTR_RE.finditer(segment)))

    # Détecter une valeur entre guillemets dont l'ouverture est située avant
    # le curseur et la fermeture après lui (ou pas encore saisie). On utilise
    # le dernier « attr=quote » du segment ; si le même guillemet n'apparaît
    # pas ensuite avant le curseur, celui-ci est à l'intérieur de la valeur.
    open_matches = list(re.finditer(r"([A-Za-z_][\w:.-]*)\s*=\s*([\"'])", segment))
    if open_matches:
        match = open_matches[-1]
        attr_name = match.group(1)
        quote = match.group(2)
        value_fragment = segment[match.end():]
        if quote not in value_fragment:
            value_start = name_end + match.end()
            tag_end = _find_tag_end(text, name_end, len(text))
            search_limit = tag_end if tag_end is not None else len(text)
            close_quote = text.find(quote, pos, search_limit + 1)
            value_end = close_quote if close_quote >= 0 else pos
            existing_with_current = tuple(dict.fromkeys(existing + (attr_name,)))
            return XmlCompletionContext(
                "attribute_value", parent, name, value_fragment,
                value_start, value_end, existing_with_current, False,
                preceding_siblings, (), attr_name, quote,
            )

    # Valeur non citée / saisie juste après « = » : ne pas inventer de
    # complétion car ce contexte XML est déjà syntaxiquement ambigu.
    # Une valeur *non citée* réellement en cours de saisie reste ambiguë.
    # Important : ne pas confondre ici un attribut déjà fermé, par exemple
    # ``<lb edRef="#T1"|/>``. La V0.5.7 tombait dans ce cas parce que le
    # motif générique acceptait aussi les guillemets et classait à tort le
    # contexte comme indisponible.
    if re.search(r"=\s*(?![\"'])[^\s>]*$", segment):
        return XmlCompletionContext(
            "none", parent, name, existing_attributes=existing,
            replace_start=pos, replace_end=pos,
            preceding_siblings=preceding_siblings,
        )

    m = re.search(r"([A-Za-z_][\w:.-]*)$", segment)
    prefix = m.group(1) if m else ""
    replace_start = name_end + (m.start(1) if m else len(segment))
    return XmlCompletionContext(
        "attribute", parent, name, prefix,
        replace_start, pos, existing, False,
        preceding_siblings, (),
    )


@dataclass(frozen=True)
class _XmlScanCheckpoint:
    position: int
    stack: tuple[str, ...]
    child_stacks: tuple[tuple[str, ...], ...]


class XmlContextCache:
    """Cache incrémental pour l'analyse lexicale au curseur.

    Le cache stocke uniquement des états à des frontières sûres, juste après
    une balise complète. ``invalidate_from(position)`` doit être appelé quand
    le document change : tous les points antérieurs restent valides, même si
    le texte situé après eux est remplacé ou décalé.

    Cette classe est volontairement indépendante de Qt afin de rester testable
    et réutilisable par l'éditeur de fragments.
    """

    def __init__(self, stride: int = 32768):
        self.stride = max(4096, int(stride))
        self._checkpoints: list[_XmlScanCheckpoint] = [
            _XmlScanCheckpoint(0, (), ())
        ]
        self.last_scan_start = 0

    def clear(self) -> None:
        self._checkpoints[:] = [_XmlScanCheckpoint(0, (), ())]
        self.last_scan_start = 0

    def invalidate_from(self, position: int) -> None:
        pos = max(0, int(position))
        if pos <= 0:
            self.clear()
            return
        # Un point exactement au début de la modification peut déjà dépendre
        # de la balise que l'utilisateur vient de modifier : on ne le conserve
        # donc que s'il est strictement antérieur.
        kept = [cp for cp in self._checkpoints if cp.position < pos]
        self._checkpoints[:] = kept or [_XmlScanCheckpoint(0, (), ())]

    def _checkpoint_before(self, position: int) -> _XmlScanCheckpoint:
        # Le nombre de points est volontairement faible (un par ~32 Kio), une
        # recherche linéaire inversée est plus simple et négligeable ici.
        for cp in reversed(self._checkpoints):
            if cp.position <= position:
                return cp
        return self._checkpoints[0]

    def _remember(self, position: int, stack: list[str], child_stacks: list[list[str]]) -> None:
        if position <= self._checkpoints[-1].position:
            return
        if position - self._checkpoints[-1].position < self.stride:
            return
        self._checkpoints.append(_XmlScanCheckpoint(
            position,
            tuple(stack),
            tuple(tuple(children) for children in child_stacks),
        ))

    def analyze(self, xml_text: str, position: int) -> XmlCompletionContext:
        text = xml_text or ""
        pos = max(0, min(int(position), len(text)))
        cp = self._checkpoint_before(pos)
        self.last_scan_start = cp.position
        stack = list(cp.stack)
        child_stacks = [list(children) for children in cp.child_stacks]
        return _analyze_xml_context_from(
            text, pos, cp.position, stack, child_stacks, self._remember
        )


def _analyze_xml_context_from(
    text: str,
    pos: int,
    start: int,
    stack: list[str],
    child_stacks: list[list[str]],
    checkpoint_callback=None,
) -> XmlCompletionContext:
    """Analyse lexicale depuis un état de pile déjà connu."""
    i = max(0, min(int(start), pos))
    while i < pos:
        lt = text.find("<", i, pos)
        if lt < 0:
            break
        i = lt
        if text.startswith("<!--", i):
            end = text.find("-->", i + 4, pos)
            if end < 0:
                return XmlCompletionContext("none", replace_start=pos, replace_end=pos)
            i = end + 3
            if checkpoint_callback:
                checkpoint_callback(i, stack, child_stacks)
            continue
        if text.startswith("<![CDATA[", i):
            end = text.find("]]>", i + 9, pos)
            if end < 0:
                return XmlCompletionContext("none", replace_start=pos, replace_end=pos)
            i = end + 3
            if checkpoint_callback:
                checkpoint_callback(i, stack, child_stacks)
            continue
        if text.startswith("<?", i):
            end = text.find("?>", i + 2, pos)
            if end < 0:
                return XmlCompletionContext("none", replace_start=pos, replace_end=pos)
            i = end + 2
            if checkpoint_callback:
                checkpoint_callback(i, stack, child_stacks)
            continue
        if text.startswith("<!", i):
            end = _find_tag_end(text, i + 2, pos)
            if end is None:
                return XmlCompletionContext("none", replace_start=pos, replace_end=pos)
            i = end + 1
            if checkpoint_callback:
                checkpoint_callback(i, stack, child_stacks)
            continue
        if text.startswith("</", i):
            m = _XML_NAME_RE.match(text, i + 2)
            end = _find_tag_end(text, i + 2, pos)
            if end is None:
                return XmlCompletionContext("none", replace_start=pos, replace_end=pos)
            if m:
                _pop_stack(stack, child_stacks, m.group(0))
            i = end + 1
            if checkpoint_callback:
                checkpoint_callback(i, stack, child_stacks)
            continue

        # Balise ouvrante.
        m = _XML_NAME_RE.match(text, i + 1)
        end = _find_tag_end(text, i + 1, pos)
        if end is None:
            parent = stack[-1] if stack else None
            preceding = tuple(child_stacks[-1]) if child_stacks else ()
            if m is None:
                return XmlCompletionContext(
                    "element", parent, None, "", pos, pos, (), True,
                    preceding, (),
                )
            name = m.group(0)
            name_start = i + 1
            name_end = m.end()

            # « <rdg|> » est un contexte d'attribut, pas un nom d'élément
            # incomplet. On regarde donc aussi le « > » situé après le curseur,
            # s'il ferme bien cette balise : celui d'une balise suivante
            # (« <h|</p> ») laisse le nom en cours de saisie (V0.9.2.1).
            future_end = _find_tag_end(text, i + 1, len(text))
            next_lt = text.find("<", pos)
            has_existing_tag_end = (future_end is not None and future_end >= pos
                                    and not 0 <= next_lt < future_end)

            if pos < name_end:
                prefix = text[name_start:pos]
                return XmlCompletionContext(
                    "element", parent, None, prefix,
                    name_start, name_end, (), True,
                    preceding, (),
                )

            if pos == name_end:
                if has_existing_tag_end:
                    return _attribute_context(text, name, name_end, pos, parent, preceding)
                return XmlCompletionContext(
                    "element", parent, None, name, name_start, pos, (), True,
                    preceding, (),
                )

            return _attribute_context(text, name, name_end, pos, parent, preceding)

        if m:
            name = m.group(0)
            raw = text[i:end + 1]
            self_closing = bool(re.search(r"/\s*>$", raw))
            if child_stacks:
                child_stacks[-1].append(name)
            if not self_closing:
                stack.append(name)
                child_stacks.append([])
        i = end + 1
        if checkpoint_callback:
            checkpoint_callback(i, stack, child_stacks)

    parent = stack[-1] if stack else None
    preceding = tuple(child_stacks[-1]) if child_stacks else ()
    following = _following_direct_children(text, pos, parent)
    return XmlCompletionContext(
        "element", parent, None, "", pos, pos, (), False,
        preceding, following,
    )


def analyze_xml_context(xml_text: str, position: int) -> XmlCompletionContext:
    """Détermine le contexte XML au curseur sans exiger un document bien formé.

    Cette fonction sans état conserve l'API historique. L'interface graphique
    utilise ``XmlContextCache`` pour les appels répétés sur un document édité.
    """
    text = xml_text or ""
    pos = max(0, min(int(position), len(text)))
    return _analyze_xml_context_from(text, pos, 0, [], [])

