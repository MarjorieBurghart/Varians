# -*- coding: utf-8 -*-
"""Déclarer dans la <listWit> de l'édition les témoins ajoutés au projet
(V0.9.2.8.2).

Le ``<witness>`` d'un témoin va à la fin de la première ``<listWit>`` de
l'en-tête (la plus extérieure), dans le style de celle-ci : une ligne par
témoin, ou à la suite. Il porte l'identifiant du témoin, son sigle dans un
``<idno type="siglum">`` quand il diffère de l'identifiant, et son libellé.
Un témoin déjà déclaré n'est pas répété, et un identifiant déjà porté par
un autre élément n'est pas employé. L'édition est modifiée comme du texte :
le reste du fichier ne change pas. Les commentaires et sections CDATA ne
comptent pas : la ``<listWit>`` d'exemple du mode d'emploi n'est jamais
prise pour la vraie.

Sans ``<listWit>``, Varians en crée une dans le ``<sourceDesc>`` de
l'en-tête, si la TEI le permet : ``<sourceDesc>`` contient soit des
paragraphes (``<p>``, ``<ab>``), soit des éléments structurés (``<bibl>``,
``<listWit>``…), jamais les deux. Le ``<bibl>`` de remplissage d'une
transcription sans témoin (:data:`SOURCE_BIBL_PLACEHOLDER`), intact, est
remplacé par la liste ; sinon la liste va à la suite du contenu. Avec des
paragraphes, rien n'est créé (``ListWitReport.paragraphs``).

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
_COMMENT_RE = re.compile(r"<!--.*?-->|<!\[CDATA\[.*?\]\]>", re.S)

# Seul contenu du <bibl> de remplissage d'une transcription sans témoin, par
# langue du gabarit (project_management.minimal_tei_text).
SOURCE_BIBL_PLACEHOLDER = {
    "fr": " Décrivez ici la source de votre document. ",
    "en": " Describe the source of your document here. ",
}


def _tag_re(name):
    return re.compile(rf"<(/?){_PREFIX}{name}\b[^>]*?(/?)>", re.S)


@dataclass
class ListWitReport:
    """Sigles des témoins, selon ce qu'il en est advenu."""
    added: list[str] = field(default_factory=list)
    declared: list[str] = field(default_factory=list)     # déjà un <witness> de ce nom
    id_used: list[str] = field(default_factory=list)      # identifiant d'un autre élément
    no_listwit: list[str] = field(default_factory=list)   # ni <listWit> ni <sourceDesc> dans l'en-tête
    paragraphs: list[str] = field(default_factory=list)   # <sourceDesc> en paragraphes : pas de <listWit>
    malformed: list[str] = field(default_factory=list)    # édition mal formée
    created: bool = False                                  # <listWit> créée
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


def _masked(text):
    """``text`` où commentaires et sections CDATA sont remplacés par des
    espaces (fins de ligne gardées) : mêmes positions, sans balise à y lire."""
    return _COMMENT_RE.sub(lambda m: re.sub(r"[^\n]", " ", m.group()), text)


def _element_span(masked, name, start, end):
    """``(début, fin de la balise ouvrante, début de la fermante, préfixe,
    vide)`` du premier élément ``name`` entre ``start`` et ``end`` de
    ``masked`` (le plus extérieur), ou None."""
    depth, outer = 0, None
    for match in _tag_re(name).finditer(masked, start, end):
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


def _listwit_span(text, masked=None):
    """``(début, fin de la balise ouvrante, début de la fermante, préfixe,
    vide)`` de la première <listWit> de l'en-tête, ou None."""
    masked = _masked(text) if masked is None else masked
    header = _HEADER_RE.search(masked)
    if header is None:
        return None
    return _element_span(masked, "listWit", header.start(2), header.end(2))


def _source_desc(root):
    """Le <sourceDesc> du premier en-tête de ``root``, ou None."""
    header = next((el for el in root.iter() if _local(el.tag) == "teiHeader"), None)
    if header is None:
        return None
    return next((el for el in header.iter() if _local(el.tag) == "sourceDesc"), None)


def _is_placeholder(element):
    """``element`` est-il le <bibl> de remplissage intact ?"""
    if _local(element.tag) != "bibl" or (element.text or "").strip():
        return False
    children = list(element)
    return (len(children) == 1 and not isinstance(children[0].tag, str)
            and (children[0].tail or "").strip() == ""
            and (children[0].text or "").strip() in {v.strip() for v in SOURCE_BIBL_PLACEHOLDER.values()})


def _indent_before(text, position):
    """Retrait de la ligne où commence ``position``, s'il n'y a que des
    blancs avant elle sur cette ligne ; sinon None."""
    line_start = text.rfind("\n", 0, position) + 1
    before = text[line_start:position]
    return before if before.strip(" \t") == "" else None


def _created_listwit(text, masked, root, elements):
    """Texte de ``text`` avec une <listWit> nouvelle, contenant
    ``elements``, dans le <sourceDesc> de l'en-tête ; None si la TEI ne le
    permet pas ou s'il n'y a pas de <sourceDesc>."""
    source_desc = _source_desc(root)
    header = _HEADER_RE.search(masked)
    if source_desc is None or header is None:
        return None
    span = _element_span(masked, "sourceDesc", header.start(2), header.end(2))
    if span is None:
        return None
    start, open_end, close_start, prefix, empty = span
    p = f"{prefix}:" if prefix else ""
    newline = "\r\n" if "\r\n" in text else "\n"
    children = [el for el in source_desc if isinstance(el.tag, str)]
    own_indent = _indent_before(text, start)

    def block(indent, unit):
        if indent is None:
            return f"<{p}listWit>" + "".join(elements) + f"</{p}listWit>"
        lines = [f"<{p}listWit>"] + [indent + unit + e for e in elements] + [indent + f"</{p}listWit>"]
        return newline.join(lines)

    if empty:
        if own_indent is None:
            return text[:start] + re.sub(r"\s*/>$", ">", text[start:open_end]) + block(None, "") \
                + f"</{p}sourceDesc>" + text[open_end:]
        inner = own_indent + "  "
        return (text[:start] + re.sub(r"\s*/>$", ">", text[start:open_end]) + newline + inner
                + block(inner, "  ") + newline + own_indent + f"</{p}sourceDesc>" + text[open_end:])
    inner = masked[open_end:close_start]
    indents = re.findall(r"\n([ \t]*)<", inner)
    child_indent = indents[-1] if indents else None
    unit = "  "
    if child_indent is not None and own_indent is not None and child_indent.startswith(own_indent) \
            and len(child_indent) > len(own_indent):
        unit = child_indent[len(own_indent):]
    if len(children) == 1 and _is_placeholder(children[0]):
        bibl = re.compile(rf"<{re.escape(p)}bibl\b[^>]*>\s*</{re.escape(p)}bibl\s*>").search(
            masked, open_end, close_start)
        if bibl is not None:
            indent = _indent_before(text, bibl.start())
            return text[:bibl.start()] + block(indent, unit) + text[bibl.end():]
    trailing = re.search(r"\s*$", inner).group()
    insert_at = close_start - len(trailing)
    if "\n" in trailing:
        indent = child_indent if child_indent is not None else (own_indent or "") + unit
        return text[:insert_at] + newline + indent + block(indent, unit) + text[insert_at:]
    return text[:insert_at] + block(None, "") + text[insert_at:]


def add_witnesses_to_listwit(text: str, witnesses) -> tuple[str, ListWitReport]:
    """Ajoute à la <listWit> de l'en-tête de ``text`` le ``<witness>`` de
    chaque témoin de ``witnesses`` qui n'y est pas ; renvoie le texte et
    le compte rendu."""
    report = ListWitReport()
    witnesses = [w for w in witnesses if (w.id or "").strip()]
    if not witnesses:
        return text, report
    try:
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        root = ET.fromstring(re.sub(r"^\s*<\?xml[^>]*\?>", "", text.lstrip("\ufeff")), parser=parser)
    except ET.ParseError:
        report.malformed = [getattr(w, "display_siglum", w.id.strip()) for w in witnesses]
        return text, report
    ids = {}
    for element in root.iter():
        ident = element.get(XML_ID)
        if ident is not None:
            ids.setdefault(ident, _local(element.tag))
    masked = _masked(text)
    span = _listwit_span(text, masked)
    # Sans <listWit> : peut-on en créer une ? (pas de paragraphes à côté)
    missing = None
    if span is None:
        source_desc = _source_desc(root)
        if source_desc is None:
            missing = report.no_listwit
        elif any(_local(el.tag) in ("p", "ab") for el in source_desc):
            missing = report.paragraphs
    new = []
    for witness in witnesses:
        wid, siglum = witness.id.strip(), getattr(witness, "display_siglum", witness.id.strip())
        if ids.get(wid) == "witness":
            report.declared.append(siglum)
        elif wid in ids:
            report.id_used.append(siglum)
        elif missing is not None:
            missing.append(siglum)
        else:
            new.append(witness)
            ids[wid] = "witness"
            report.added.append(siglum)
    if not new:
        return text, report
    if span is None:
        header = _HEADER_RE.search(masked)
        source_span = _element_span(masked, "sourceDesc", header.start(2), header.end(2)) if header else None
        prefix = source_span[3] if source_span else ""
        updated = _created_listwit(text, masked, root, [witness_element(w, prefix) for w in new])
        if updated is None:
            report.no_listwit.extend(report.added)
            report.added = []
            return text, report
        report.created = report.changed = True
        return updated, report
    start, open_end, close_start, prefix, empty = span
    elements = [witness_element(w, prefix) for w in new]
    if empty:
        # <listWit/> : déployé autour des nouveaux témoins.
        p = f"{prefix}:" if prefix else ""
        tag = text[start:open_end]
        opening = re.sub(r"\s*/>$", ">", tag)
        updated = text[:start] + opening + "".join(elements) + f"</{p}listWit>" + text[open_end:]
    else:
        inner = masked[open_end:close_start]
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


def report_notes(report: ListWitReport, tr) -> list[str]:
    """Phrases du compte rendu (``tr`` : traduction d'une clé) : témoins
    ajoutés, ou liste créée avec eux, puis ceux qui n'ont pas pu l'être."""
    added = "project.listwit.created" if report.created else "project.listwit.added"
    return [tr(key, witnesses=", ".join(sigla)) for key, sigla in (
        (added, report.added),
        ("project.listwit.no_listwit", report.no_listwit),
        ("project.listwit.id_used", report.id_used),
        ("project.listwit.paragraphs", report.paragraphs),
        ("project.listwit.malformed", report.malformed)) if sigla]


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
