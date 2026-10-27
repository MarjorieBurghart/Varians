# -*- coding: utf-8 -*-
"""Racine d'un document XML, lue sans l'analyser (V0.9.2.4) : son nom et
ses attributs, même pendant la frappe, quand la suite du document est
inachevée ou mal formée.

Elle sert à reconnaître le document affiché : une feuille XSLT
(``xslt_scenarios.stylesheet_info``) ou un fichier Schematron
(``schematron_info``)."""
from __future__ import annotations

import re
from dataclasses import dataclass

SCHEMATRON_NS = "http://purl.oclc.org/dsdl/schematron"
_COMMENT_OR_PI = re.compile(r"\s*(?:<\?.*?\?>|<!--.*?-->|<!DOCTYPE[^>\[]*(?:\[.*?\])?\s*>)", re.S)
_START_TAG = re.compile(r"\s*<([A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?)((?:\s+[^\s=/>]+\s*=\s*(?:\"[^\"]*\"|'[^']*'))*)",
                        re.S)
_ATTRIBUTE = re.compile(r"([^\s=/>]+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")


def root_tag(text) -> tuple[str, dict[str, str]] | None:
    """``(nom, attributs)`` de la balise ouvrante de la racine de *text*
    (après déclaration, commentaires, instructions de traitement et
    DOCTYPE), sinon None."""
    position, text = 0, str(text or "")
    while True:
        match = _COMMENT_OR_PI.match(text, position)
        if match is None or match.end() == position:
            break
        position = match.end()
    match = _START_TAG.match(text, position)
    if match is None:
        return None
    attributes = {m.group(1): m.group(2) if m.group(2) is not None else m.group(3)
                  for m in _ATTRIBUTE.finditer(match.group(2))}
    return match.group(1), attributes


@dataclass(frozen=True)
class SchematronInfo:
    """Ce qu'on lit à la racine d'un fichier Schematron : le préfixe lié à
    l'espace de noms Schematron (``""`` s'il est l'espace de noms par
    défaut) et le ``queryBinding`` (``""`` s'il manque)."""
    prefix: str
    query_binding: str


def schematron_info(text) -> SchematronInfo | None:
    """La racine de *text* si c'est un ``schema`` de l'espace de noms ISO
    Schematron, sinon None."""
    tag = root_tag(text)
    if tag is None:
        return None
    name, attributes = tag
    prefix, _colon, local = name.rpartition(":")
    if local == "schema" and attributes.get(f"xmlns:{prefix}" if prefix else "xmlns") == SCHEMATRON_NS:
        return SchematronInfo(prefix, attributes.get("queryBinding", ""))
    return None
