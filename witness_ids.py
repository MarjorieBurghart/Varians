# -*- coding: utf-8 -*-
"""Sigle et identifiant d'un témoin (V0.9.2.8.2).

Le sigle est ce que l'éditeur saisit (« 1760 », « T 2 ») ; l'identifiant
est l'``xml:id`` du ``<witness>`` dans la TEI, la cible de ``@wit`` et
``@edRef``, la clé du témoin dans Varians. Un identifiant XML est un NCName
(XML 1.0, 5e éd., sans « : ») : quand le sigle n'en est pas un, Varians en
tire un identifiant valide par :func:`witness_id_for_siglum`, et garde le
sigle pour l'affichage (``siglum`` dans project.xml, ``<idno
type="siglum">`` dans la TEI).

Module sans Qt : la même règle peut être reprise par d'autres outils."""
from __future__ import annotations

# Caractères de début d'un nom XML (NameStartChar, XML 1.0 5e éd.), « : » exclu.
_START_RANGES = (
    (0x41, 0x5A), (0x5F, 0x5F), (0x61, 0x7A), (0xC0, 0xD6), (0xD8, 0xF6), (0xF8, 0x2FF),
    (0x370, 0x37D), (0x37F, 0x1FFF), (0x200C, 0x200D), (0x2070, 0x218F), (0x2C00, 0x2FEF),
    (0x3001, 0xD7FF), (0xF900, 0xFDCF), (0xFDF0, 0xFFFD), (0x10000, 0xEFFFF),
)
# Caractères permis ensuite (NameChar), en plus des précédents.
_NAME_RANGES = ((0x2D, 0x2E), (0x30, 0x39), (0xB7, 0xB7), (0x300, 0x36F), (0x203F, 0x2040))


def _in(ranges, ch):
    code = ord(ch)
    return any(low <= code <= high for low, high in ranges)


def _start_char(ch):
    return _in(_START_RANGES, ch)


def _name_char(ch):
    return _start_char(ch) or _in(_NAME_RANGES, ch)


def is_xml_id(value: str) -> bool:
    """``value`` peut-il servir d'``xml:id`` (NCName) ?"""
    return bool(value) and _start_char(value[0]) and all(_name_char(ch) for ch in value[1:])


def witness_id_for_siglum(siglum: str) -> str:
    """Identifiant XML tiré du sigle : le sigle lui-même s'il est valide ;
    sinon chaque caractère interdit devient « _ », et un « _ » est ajouté
    devant si le sigle ne commence pas par une lettre ou « _ ».
    « 1760 » → « _1760 », « T 2 » → « T_2 » ; sigle vide → ""."""
    siglum = (siglum or "").strip()
    if not siglum:
        return ""
    value = "".join(ch if _name_char(ch) else "_" for ch in siglum)
    return value if _start_char(value[0]) else "_" + value


def witness_title(witness_id: str, siglum: str, label: str) -> str:
    """Titre d'un témoin à l'écran : « sigle · nom affiché » ; le nom affiché
    seul s'il commence déjà par le sigle ou l'identifiant (« T1 · Troyes
    816 »), ou s'il n'est que l'un d'eux ; le sigle seul sans nom affiché."""
    label = (label or "").strip()
    siglum = (siglum or "").strip() or witness_id
    if not label:
        return siglum
    for name in (siglum, witness_id):
        if name and label.startswith(name) and not label[len(name):len(name) + 1].isalnum():
            return label
    return f"{siglum} · {label}"
