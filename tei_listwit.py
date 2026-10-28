# -*- coding: utf-8 -*-
"""Déclarer dans la <listWit> de l'édition les témoins ajoutés au projet
(V0.9.2.8.2).

Le ``<witness>`` d'un témoin va à la fin de la première ``<listWit>`` de
l'en-tête (la plus extérieure), dans le style de celle-ci : une ligne par
témoin, ou à la suite. Il porte l'identifiant du témoin, son sigle dans un
``<idno type="siglum">`` quand il diffère de l'identifiant, et son libellé.
Varians ne crée jamais de ``<listWit>`` ; un témoin déjà déclaré n'est pas
répété, et un identifiant déjà porté par un autre élément n'est pas employé.
L'édition est modifiée comme du texte : le reste du fichier ne change pas.

Module sans Qt."""
from __future__ import annotations

import html
import os
import re
import shutil
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
_PREFIX = r"(?:([A-Za-z_][\w.-]*):)?"
_HEADER_RE = re.compile(rf"<{_PREFIX}teiHeader\b[^>]*>(.*?)</(?:[A-Za-z_][\w.-]*:)?teiHeader\s*>", re.S)
_LISTWIT_TAG_RE = re.compile(rf"<(/?){_PREFIX}listWit\b[^>]*?(/?)>", re.S)


@dataclass
class ListWitReport:
    """Sigles des témoins, selon ce qu'il en est advenu."""
    added: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)     # déjà un <witness> de ce nom
    id_used: list[str] = field(default_factory=list)      # identifiant d'un autre élément
    no_listwit: list[str] = field(default_factory=list)   # pas de <listWit> dans l'en-tête
    malformed: list[str] = field(default_factory=list)    # édition mal formée
    changed: bool = False


def _local(tag):
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def witness_element(witness, prefix: str = "") -> str:
    """``<witness xml:id="…">[<idno type="siglum">…</idno>]libellé</witness>``."""
    wid = witness.id.strip()
    siglum = getattr(witness, "display_siglum", wid)
    label = (witness.label or "").strip() or siglum
    p = f"{prefix}:" if prefix else ""
    idno = f'<{p}idno type="siglum">{html.escape(siglum, quote=False)}</{p}idno>' if siglum != wid else ""
    return f'<{p}witness xml:id="{html.escape(wid)}">{idno}{html.escape(label, quote=False)}</{p}witness>'


def _listwit_span(text):
    """``(début, fin de la balise ouvrante, début de la fermante, préfixe,
    vide)`` de la première <listWit> de l'en-tête, ou None."""
    header = _HEADER_RE.search(text)
    if header is None:
        return None
    start, end = header.start(2), header.end(2)
    depth, outer = 0, None
    for match in _LISTWIT_TAG_RE.finditer(text, start, end):
        closing, prefix, empty = match.group(1), match.group(2) or "", match.group(3)
        if outer is None:
            if closing:
                continue
            if empty:
                return match.start(), match.end(), match.end(), prefix, True
            outer = (match.start(), match.end(), prefix)
            depth = 1
            continue
        if empty:
            continue
        depth += -1 if closing else 1
        if depth == 0:
            return outer[0], outer[1], match.start(), outer[2], False
    return None


def add_witnesses_to_listwit(text: str, witnesses) -> tuple[str, ListWitReport]:
    """Ajoute à la <listWit> de l'en-tête de ``text`` le ``<witness>`` de
    chaque témoin de ``witnesses`` qui n'y est pas ; renvoie le texte et
    le compte rendu."""
    report = ListWitReport()
    witnesses = [w for w in witnesses if (w.id or "").strip()]
    if not witnesses:
        return text, report
    try:
        root = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", text.lstrip("\ufeff")))
    except ET.ParseError:
        report.malformed = [getattr(w, "display_siglum", w.id.strip()) for w in witnesses]
        return text, report
    ids = {}
    for element in root.iter():
        ident = element.get(XML_ID)
        if ident is not None:
            ids.setdefault(ident, _local(element.tag))
    span = _listwit_span(text)
    new = []
    for witness in witnesses:
        wid, siglum = witness.id.strip(), getattr(witness, "display_siglum", witness.id.strip())
        if ids.get(wid) == "witness":
            report.declared.append(siglum)
        elif wid in ids:
            report.id_used.append(siglum)
        elif span is None:
            report.no_listwit.append(siglum)
        else:
            new.append(witness)
            ids[wid] = "witness"
            report.added.append(siglum)
    if not new:
        return text, report
    start, open_end, close_start, prefix, empty = span
    elements = [witness_element(w, prefix) for w in new]
    if empty:
        # <listWit/> : déployé autour des nouveaux témoins.
        p = f"{prefix}:" if prefix else ""
        tag = text[start:open_end]
        opening = re.sub(r"\s*/>$", ">", tag)
        updated = text[:start] + opening + "".join(elements) + f"</{p}listWit>" + text[open_end:]
    else:
        inner = text[open_end:close_start]
        trailing = re.search(r"\s*$", inner).group()
        if "\n" in trailing:
            # Une ligne par témoin, au retrait du dernier, avec les fins de
            # ligne du fichier.
            newline = "\r\n" if "\r\n" in trailing else "\n"
            indents = re.findall(r"\n([ \t]*)<", inner)
            indent = indents[-1] if indents else ""
            insert_at = close_start - len(trailing)
            addition = "".join(f"{newline}{indent}{element}" for element in elements)
        else:
            insert_at = close_start
            addition = "".join(elements)
        updated = text[:insert_at] + addition + text[insert_at:]
    report.changed = True
    return updated, report


def add_witnesses_to_listwit_file(edition_path, witnesses) -> ListWitReport:
    """Même chose dans le fichier de l'édition, avec une copie ``.bak``
    préalable si le fichier change."""
    path = Path(edition_path).expanduser().resolve()
    # En octets : les fins de ligne du fichier restent les siennes.
    source = path.read_bytes().decode("utf-8")
    updated, report = add_witnesses_to_listwit(source, witnesses)
    if report.changed and updated != source:
        shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_bytes(updated.encode("utf-8"))
        os.replace(tmp, path)
    return report
