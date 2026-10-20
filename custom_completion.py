# -*- coding: utf-8 -*-
"""Configuration d'aide à la saisie issue de ``custom-elements.xml``.

Ce module est volontairement indépendant de Qt et du moteur RELAX NG.
Il décrit la *commodité éditoriale* du projet, jamais sa validité XML/RNG.

Format rétrocompatible::

    <customElements>
      <element name="rdg">
        <attribute name="wit"/>
      </element>
    </customElements>

Valeurs suggérées explicites::

    <attribute name="type" valuesMode="replace">
      <value>editorial</value>
      <value>textual</value>
    </attribute>

Valeurs dynamiques tirées des témoins du projet::

    <attribute name="wit" valuesMode="replace">
      <values source="witnesses" prefix="#"/>
    </attribute>

Valeurs dynamiques tirées des identifiants (``xml:id``) des documents du
projet, éventuellement limités à certains éléments::

    <attribute name="ref" valuesMode="replace">
      <values source="ids" elements="person personGrp" prefix="#"/>
    </attribute>

``valuesMode="append"`` (défaut) ajoute les valeurs personnalisées aux valeurs
finies du RNG. ``valuesMode="replace"`` remplace uniquement la *liste proposée*
par l'interface ; le schéma RELAX NG reste seul juge de la validité.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


def _local_qname(name: str) -> str:
    return (name or "").split(":", 1)[-1]


def _name_matches(left: str, right: str) -> bool:
    return left == right or _local_qname(left) == _local_qname(right)


@dataclass(frozen=True)
class DynamicValues:
    source: str
    prefix: str = ""
    suffix: str = ""
    # Source « ids » : noms locaux des éléments retenus ; vide = tous.
    elements: tuple[str, ...] = ()


@dataclass(frozen=True)
class CustomAttributeSpec:
    name: str
    default_value: str = ""
    has_default: bool = False
    values: tuple[str, ...] = ()
    dynamic_values: tuple[DynamicValues, ...] = ()
    values_mode: str = "append"

    def resolved_values(self, witness_ids=(), ids_for=None) -> tuple[str, ...]:
        """``ids_for(elements)`` fournit les identifiants de la source « ids »
        (aucun si l'appelant ne la connaît pas) : « bernard », ou le pointeur
        qualifié « personnes.xml#molesme » d'un identifiant ambigu, repris tel
        quel lorsque la source produit des pointeurs (``prefix="#"``)."""
        out: list[str] = list(self.values)
        for source in self.dynamic_values:
            if source.source == "witnesses":
                out.extend(f"{source.prefix}{wid}{source.suffix}" for wid in witness_ids if wid)
            elif source.source == "ids" and ids_for is not None:
                pointers = source.prefix == "#" and not source.suffix
                for ident in ids_for(source.elements):
                    if "#" in ident:
                        if pointers:
                            out.append(ident)
                            continue
                        ident = ident.rsplit("#", 1)[1]
                    if ident:
                        out.append(f"{source.prefix}{ident}{source.suffix}")
        return tuple(dict.fromkeys(v for v in out if v != ""))


@dataclass(frozen=True)
class CustomElementSpec:
    name: str
    attributes: tuple[CustomAttributeSpec, ...] = ()
    # Aide au formateur TEI uniquement : "inline", "block" ou "preserve".
    # Une valeur vide laisse le RNG et le contenu réel décider.
    formatting: str = ""


@dataclass(frozen=True)
class CustomCompletionConfig:
    elements: tuple[CustomElementSpec, ...] = ()

    def element_names(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys(e.name for e in self.elements if e.name))

    def matching_elements(self, element: str | None) -> tuple[CustomElementSpec, ...]:
        if not element:
            return ()
        return tuple(e for e in self.elements if _name_matches(e.name, element))

    def attributes_for(self, element: str | None) -> tuple[CustomAttributeSpec, ...]:
        attrs: list[CustomAttributeSpec] = []
        seen: set[str] = set()
        for elem in self.matching_elements(element):
            for attr in elem.attributes:
                key = _local_qname(attr.name)
                if key not in seen:
                    seen.add(key)
                    attrs.append(attr)
        return tuple(attrs)

    def attribute_names(self, element: str | None) -> tuple[str, ...]:
        return tuple(attr.name for attr in self.attributes_for(element))

    def attribute_spec(self, element: str | None, attribute: str | None) -> CustomAttributeSpec | None:
        if not attribute:
            return None
        for attr in self.attributes_for(element):
            if _name_matches(attr.name, attribute):
                return attr
        return None

    def attribute_values(self, element: str | None, attribute: str | None, witness_ids=(),
                         ids_for=None) -> tuple[tuple[str, ...], str]:
        spec = self.attribute_spec(element, attribute)
        if spec is None:
            return (), "append"
        return spec.resolved_values(witness_ids, ids_for), spec.values_mode

    def formatting_for(self, element: str | None) -> str:
        """Retourne la règle de mise en forme projet pour un élément.

        Si plusieurs déclarations locales équivalentes existent, la dernière
        règle explicite gagne. Une chaîne vide signifie « aucune surcharge ».
        """
        value = ""
        for elem in self.matching_elements(element):
            if elem.formatting:
                value = elem.formatting
        return value


def load_custom_completion(path: str | Path) -> CustomCompletionConfig:
    """Charge un ``custom-elements.xml`` rétrocompatible.

    Le parseur est strict sur les modes/sources connus afin qu'une faute de
    configuration ne ressemble pas silencieusement à une absence de suggestion.
    """
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        return CustomCompletionConfig()
    root = ET.parse(path).getroot()
    if root.tag != "customElements":
        raise ValueError("ROOT_NOT_CUSTOM_ELEMENTS")

    elements: list[CustomElementSpec] = []
    for elem in root.findall("element"):
        name = (elem.get("name") or "").strip()
        if not name:
            continue
        formatting = (elem.get("formatting") or "").strip().lower()
        if formatting not in {"", "inline", "block", "preserve"}:
            raise ValueError(f"UNKNOWN_FORMATTING_MODE:{formatting}")
        attrs: list[CustomAttributeSpec] = []
        for attr in elem.findall("attribute"):
            attr_name = (attr.get("name") or "").strip()
            if not attr_name:
                continue
            mode = (attr.get("valuesMode") or "append").strip().lower()
            if mode not in {"append", "replace"}:
                raise ValueError(f"UNKNOWN_VALUES_MODE:{mode}")
            explicit: list[str] = []
            dynamic: list[DynamicValues] = []
            for child in attr:
                if child.tag == "value":
                    value = child.get("value") if "value" in child.attrib else child.text
                    if value is not None:
                        explicit.append(str(value).strip())
                elif child.tag == "values":
                    source = (child.get("source") or "").strip().lower()
                    if source not in {"witnesses", "ids"}:
                        raise ValueError(f"UNKNOWN_VALUES_SOURCE:{source}")
                    dynamic.append(DynamicValues(
                        source=source,
                        prefix=child.get("prefix", ""),
                        suffix=child.get("suffix", ""),
                        elements=tuple((child.get("elements") or "").split()),
                    ))
            attrs.append(CustomAttributeSpec(
                name=attr_name,
                default_value=attr.get("defaultValue", ""),
                has_default="defaultValue" in attr.attrib,
                values=tuple(dict.fromkeys(v for v in explicit if v != "")),
                dynamic_values=tuple(dynamic),
                values_mode=mode,
            ))
        elements.append(CustomElementSpec(name=name, attributes=tuple(attrs), formatting=formatting))
    return CustomCompletionConfig(tuple(elements))


def merge_suggestion_sources(rng_values, custom_values, custom_mode="append"):
    """Fusionne deux listes en conservant leur provenance.

    Renvoie ``[(valeur, source)]`` avec source ``rng``, ``custom`` ou ``both``.
    En mode ``replace``, seules les valeurs projet sont proposées ; cela ne dit
    rien sur leur validité RNG.
    """
    rng = tuple(dict.fromkeys(str(v) for v in rng_values if str(v) != ""))
    custom = tuple(dict.fromkeys(str(v) for v in custom_values if str(v) != ""))
    rng_set = set(rng)
    custom_set = set(custom)
    if custom_mode == "replace" and custom:
        return [(value, "both" if value in rng_set else "custom") for value in custom]

    out = []
    for value in rng:
        out.append((value, "both" if value in custom_set else "rng"))
    for value in custom:
        if value not in rng_set:
            out.append((value, "custom"))
    return out
