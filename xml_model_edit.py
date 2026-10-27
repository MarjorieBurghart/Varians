# -*- coding: utf-8 -*-
"""Lecture et réécriture des déclarations Schematron ``<?xml-model?>``
(V0.9.2.5), sans Qt.

La boîte « Règles Schematron du document… » (``schematron_rules_dialog``)
choisit la phase d'une déclaration, en ajoute ou en retire une, en
réécrivant le texte du document : la déclaration reste standard, comme si
on l'avait écrite à la main. Seule la déclaration visée change ; les
guillemets et les autres pseudo-attributs sont gardés.

Les déclarations sont lues comme ``schema_resolution.detect_xml_models`` ;
une déclaration est désignée par son rang parmi les déclarations
Schematron du texte.
"""
from __future__ import annotations

import html
import re
from dataclasses import dataclass

from schema_resolution import _ATTR_RE, _XML_MODEL_RE, SCHEMATRON_NS

_XML_DECLARATION = re.compile(r"\s*<\?xml\s[^?]*\?>")


@dataclass(frozen=True)
class Declaration:
    """Une déclaration Schematron : sa place dans le texte (``start``,
    ``end``), son adresse et sa phase (vide si elle n'en a pas)."""
    start: int
    end: int
    href: str
    phase: str


def _attributes(body):
    return {name: html.unescape(value.strip()) for name, _quote, value in _ATTR_RE.findall(body)}


def schematron_declarations(text) -> tuple[Declaration, ...]:
    """Les déclarations ``xml-model`` de type Schematron de *text*."""
    found = []
    for match in _XML_MODEL_RE.finditer(text or ""):
        attributes = _attributes(match.group(1))
        if attributes.get("schematypens", "").rstrip("/") == SCHEMATRON_NS.rstrip("/") and attributes.get("href"):
            found.append(Declaration(match.start(), match.end(), attributes["href"], attributes.get("phase", "")))
    return tuple(found)


def _quoted(value):
    return '"' + html.escape(value, quote=True) + '"'


def set_phase(text, index, phase) -> str:
    """*text* où la déclaration Schematron de rang *index* demande la phase
    *phase* (vide : plus de phase, celle par défaut). IndexError si elle
    n'existe pas."""
    declaration = schematron_declarations(text)[index]
    pi = text[declaration.start:declaration.end]
    existing = next((m for m in _ATTR_RE.finditer(pi) if m.group(1) == "phase"), None)
    if existing is not None:
        if phase:
            quote = existing.group(2)
            value = html.escape(phase, quote=True) if quote == '"' else html.escape(phase, quote=False).replace("'", "&apos;")
            pi = pi[:existing.start(3)] + value + pi[existing.end(3):]
        else:
            start = existing.start()
            while start > 0 and pi[start - 1].isspace():
                start -= 1
            pi = pi[:start] + pi[existing.end():]
    elif phase:
        end = len(pi) - 2                                   # avant « ?> »
        while end > 0 and pi[end - 1].isspace():
            end -= 1
        pi = pi[:end] + f" phase={_quoted(phase)}" + pi[end:]
    return text[:declaration.start] + pi + text[declaration.end:]


def declaration_text(href, phase="") -> str:
    """Une déclaration Schematron pour le fichier *href*."""
    phase = f" phase={_quoted(phase)}" if phase else ""
    return f'<?xml-model href={_quoted(href)} type="application/xml" schematypens="{SCHEMATRON_NS}"{phase}?>'


def add_declaration(text, href, phase="") -> str:
    """*text* avec une nouvelle déclaration Schematron, après la dernière
    déclaration ``xml-model``, sinon après la déclaration XML, sinon au
    début."""
    models = list(_XML_MODEL_RE.finditer(text or ""))
    pi = declaration_text(href, phase)
    if models:
        position = models[-1].end()
        return text[:position] + "\n" + pi + text[position:]
    declaration = _XML_DECLARATION.match(text or "")
    if declaration is not None:
        position = declaration.end()
        return text[:position] + "\n" + pi + text[position:]
    return pi + "\n" + (text or "")


def remove_declaration(text, index) -> str:
    """*text* sans la déclaration Schematron de rang *index* ; seule sur sa
    ligne, elle part avec sa ligne. IndexError si elle n'existe pas."""
    declaration = schematron_declarations(text)[index]
    start, end = declaration.start, declaration.end
    if (start == 0 or text[start - 1] == "\n") and text[end:end + 1] == "\n":
        end += 1
    return text[:start] + text[end:]
