# -*- coding: utf-8 -*-
"""Extracteurs TEI de l'export web (``web_viewer.generator``).

Ce module, issu du générateur « V11 » du corpus de Troyes, ne garde que ce
dont l'export générique a besoin :

- ``extract_corrected_pages`` : les lignes physiques du pivot (texte, runs,
  variantes et notes), pour les panneaux des fac-similés ;
- ``extract_reading_document`` : le texte de lecture en blocs (divisions,
  titres, paragraphes, vers, entrées de liste, cellules, légendes, notes),
  dont chaque segment porte la clé de sa ligne du pivot ;
- ``extract_witness_labels``, ``attach_variant_metadata_to_runs``,
  ``load_json`` et les règles communes (leçons d'un ``<app>``, forme d'un
  ``<choice>``, lacunes).

Les ``<lb/>`` du pivot sont reliés aux lignes de son JSON par
``tei_line_anchors`` : le n-ième ``<lb/>`` reçoit la n-ième ligne, comme sur
le bureau. Le XML est lu avec ``xml.etree.ElementTree``.
"""

from __future__ import annotations

import json
import re
from collections import OrderedDict
from pathlib import Path
import xml.etree.ElementTree as ET

from web_viewer.tei_line_anchors import build_pivot_lb_index


# =============================================================================
# Utilitaires
# =============================================================================

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"


def lname(tag: str) -> str:
    """Nom local d'un tag XML, sans namespace."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def clean_text(s: str) -> str:
    return " ".join((s or "").split())


def wit_tokens(value: str | None):
    if not value:
        return []
    return [x.lstrip("#") for x in value.split() if x.strip()]


def witness_matches(value: str | None, target: str) -> bool:
    return target.lstrip("#") in wit_tokens(value)


# =============================================================================
# Lecture de la TEI corrigée, avec variantes et notes
# =============================================================================


def extract_witness_labels(root: ET.Element):
    labels = {}
    for wit in root.iter():
        if lname(wit.tag) != "witness":
            continue
        wid = wit.attrib.get(XML_ID) or wit.attrib.get("id")
        if wid:
            # Le <idno type="siglum"> (V0.9.2.8.2) n'est pas du libellé ; il
            # le remplace s'il est seul. Un élément qui ne contient que le
            # sigle ou l'identifiant (<abbr>, <label>…) n'en est pas non plus
            # (V0.9.3.0).
            siglum = next((clean_text("".join(child.itertext())) for child in wit
                           if lname(child.tag) == "idno" and child.attrib.get("type") == "siglum"), "")
            parts = [wit.text or ""]
            for child in wit:
                text = clean_text("".join(child.itertext()))
                if not (lname(child.tag) == "idno" and child.attrib.get("type") == "siglum") \
                        and text not in (siglum, wid):
                    parts.append("".join(child.itertext()))
                parts.append(child.tail or "")
            labels[wid] = clean_text("".join(parts)) or siglum or wid
    return labels


READING_TAGS = ("lem", "rdg", "wit")
# Forme montrée d'un <choice>, comme « Édition critique » : la première
# présente dans cet ordre, sinon le premier enfant.
CHOICE_ORDER = ("corr", "reg", "expan", "sic", "orig", "abbr")


def reading_witnesses(app: ET.Element):
    """``[(leçon, @wit)]`` d'un ``<app>`` dans l'ordre : ``<lem>``, ``<rdg>``
    (et la coquille ``<wit>``), celles d'un ``<rdgGrp>`` comprises ; le
    ``@wit`` est celui de la leçon, sinon celui de son ``<rdgGrp>``."""
    found = []

    def visit(node, inherited):
        for child in node:
            tag = lname(child.tag)
            if tag in READING_TAGS:
                found.append((child, child.attrib.get("wit") or inherited))
            elif tag == "rdgGrp":
                visit(child, child.attrib.get("wit") or inherited)

    visit(app, None)
    return found


def app_readings(app: ET.Element):
    """Leçons d'un ``<app>`` dans l'ordre (``reading_witnesses``)."""
    return [reading for reading, _wit in reading_witnesses(app)]


TEXT_MODES = ("established", "witness")


def choose_reading_status(app: ET.Element, target: str, mode: str = "witness", witness: str | None = None):
    """``(leçon, @wit, manque)`` : la leçon affichée d'un ``<app>`` (V0.9.3.0).

    ``witness`` : le témoin choisi, sinon le pivot ``target``. Mode
    ``established`` (texte établi, comme « Édition critique ») : le
    ``<lem>``, sinon la leçon du témoin choisi, sinon celle du pivot, sinon
    la première. Mode ``witness`` (texte d'un témoin) : la leçon du témoin
    choisi, sinon le ``<lem>``, sinon celle du pivot, sinon la première.
    ``manque`` : None, ou ``{"wit", "fallback"}`` quand on retombe faute
    d'une leçon du témoin choisi (aucune leçon ne le nomme ; une leçon vide
    qui le nomme est sa leçon) ; ``fallback`` : ``lem`` ou le premier témoin
    de la leçon affichée."""
    readings = reading_witnesses(app)
    chosen = (witness or target).lstrip("#")
    own = next((pair for pair in readings if witness_matches(pair[1], chosen)), None)
    lem = next((pair for pair in readings if lname(pair[0].tag) == "lem"), None)
    pivot = next((pair for pair in readings if witness_matches(pair[1], target)), None)
    first = readings[0] if readings else None
    if mode == "established":
        order, lacking = (lem, own, pivot, first), lem is None and own is None
    else:
        order, lacking = (own, lem, pivot, first), own is None
    shown = next((pair for pair in order if pair is not None), None)
    if shown is None:
        return None, None, None
    missing = None
    if lacking:
        fallback = "lem" if lname(shown[0].tag) == "lem" else next(iter(wit_tokens(shown[1])), "")
        missing = {"wit": chosen, "fallback": fallback}
    return shown[0], shown[1], missing


def choose_reading(app: ET.Element, target: str, mode: str = "witness", witness: str | None = None):
    """La leçon affichée d'un ``<app>`` (``choose_reading_status``) ; sans
    choix, celle du pivot ``target``, sinon le ``<lem>``, sinon la
    première."""
    return choose_reading_status(app, target, mode, witness)[0]


def pivot_marks_in(reading: ET.Element, is_mark):
    """``(début, suite)`` : les éléments ``is_mark`` (``<lb>``, ``<pb>`` du
    pivot) d'une leçon non affichée (V0.9.3.0). ``début`` : ceux qui
    précèdent tout texte de cette leçon ; ``suite`` : ``(élément, part)``,
    ``part`` étant la part du texte de la leçon qui le précède (de 0 à 1,
    espaces non comptées). Les notes ne sont pas parcourues."""
    leading, following = [], []
    count = 0

    def visit(node):
        nonlocal count
        count += len(re.sub(r"\s+", "", node.text or ""))
        for child in node:
            if is_mark(child):
                if count:
                    following.append((child, count))
                else:
                    leading.append(child)
            elif lname(child.tag) != "note":
                visit(child)
            count += len(re.sub(r"\s+", "", child.tail or ""))

    visit(reading)
    return leading, [(element, before / count) for element, before in following]


def describe_readings(app: ET.Element):
    return [{
        "role": lname(reading.tag),
        "wit": wit_tokens(reading.attrib.get("wit")),
        "text": flatten_editorial_text(reading, include_notes=False, include_refs=False),
        "notes": notes_inside(reading),
    } for reading in app_readings(app)]


def choose_choice_form(choice: ET.Element):
    forms = [child for child in choice if isinstance(child.tag, str)]
    for name in CHOICE_ORDER:
        form = next((child for child in forms if lname(child.tag) == name), None)
        if form is not None:
            return form
    return forms[0] if forms else None


def flatten_editorial_text(el: ET.Element, include_notes=False, include_refs=False) -> str:
    """Aplatit un fragment TEI pour l'affichage d'une lecture ou d'une note."""
    parts = []

    def walk(node):
        tag = lname(node.tag)
        if tag == "note" and not include_notes:
            return
        if tag == "ref" and not include_refs:
            return
        if tag in {"lb", "pb"}:
            parts.append(" ")
            return
        if tag == "choice":
            form = choose_choice_form(node)
            if form is not None:
                walk(form)
            return
        if node.text:
            parts.append(node.text)
        for child in list(node):
            walk(child)
            if child.tail:
                parts.append(child.tail)

    walk(el)
    return clean_text("".join(parts))


def notes_inside(el: ET.Element):
    out = []
    for n in el.iter():
        if lname(n.tag) == "note":
            txt = flatten_editorial_text(n, include_notes=True, include_refs=True)
            if txt:
                out.append(txt)
    return out


LACUNA_TAGS = ("lacunaStart", "lacunaEnd")

# Texte de lecture (V0.9.3.0) : blocs affichés par le viewer. Un bloc « div »
# marque le début d'une division ; il n'a pas de texte.
RENDERED_BLOCKS = frozenset({"p", "head", "l", "item", "cell", "caption", "note"})
DIVISION_TAGS = frozenset({"div", "div1", "div2", "div3", "div4", "div5", "div6", "div7"})
# Repères posés entre deux blocs : ils ne font pas de bloc à eux seuls.
MILESTONE_TAGS = frozenset({"pb", "lb", "cb", "milestone", "anchor"})
# Éléments qui sortent d'un paragraphe ou d'une entrée de liste pour être
# affichés à part ; la suite du bloc est un bloc marqué « cont ».
SPLIT_TAGS = frozenset({"list", "table", "figure", "lg"})
# Contenu de phrase : un élément inconnu, posé entre deux blocs, qui ne
# contient que cela est lu comme un paragraphe ; sinon, comme un conteneur.
PHRASE_TAGS = frozenset({
    "hi", "emph", "foreign", "term", "gloss", "title", "name", "persName", "placeName", "orgName",
    "geogName", "roleName", "forename", "surname", "addName", "rs", "date", "time", "num", "measure",
    "quote", "q", "said", "cit", "ref", "ptr", "bibl", "author", "biblScope", "pubPlace", "publisher",
    "app", "lem", "rdg", "rdgGrp", "witDetail", "wit", "choice", "sic", "corr", "orig", "reg", "abbr",
    "expan", "am", "ex", "add", "del", "subst", "mod", "restore", "surplus", "supplied", "unclear",
    "damage", "gap", "space", "handShift", "note", "seg", "w", "pc", "c", "g", "index", "mentioned",
    "soCalled", "distinct", "metamark", "lacunaStart", "lacunaEnd", *MILESTONE_TAGS,
})


def reading_texts(root: ET.Element):
    """Les ``<text>`` les plus externes du document, dans l'ordre (ceux d'un
    ``<teiCorpus>`` compris) ; à défaut, son premier ``<body>``."""
    found = []

    def visit(node):
        tag = lname(node.tag)
        if tag == "teiHeader":
            return
        if tag == "text":
            found.append(node)
            return
        for child in node:
            visit(child)

    visit(root)
    if not found:
        body = next((e for e in root.iter() if lname(e.tag) == "body"), None)
        found = [body] if body is not None else []
    return found


def cit_is_biblical(cit) -> bool:
    """Une citation biblique : son ``@type`` contient « bible »."""
    return "bible" in (cit.attrib.get("type") or "").split()


def reference_notes(root) -> set:
    """``{id(ref)}`` des ``<ref>`` qui sont des notes (V0.9.3.0, comme
    « Édition critique ») : le ``<ref>`` d'une ``<cit>`` qui n'est pas
    biblique. Celui d'une citation biblique, ou hors d'une ``<cit>``, reste
    une référence éditoriale entre chevrons."""
    return {id(ref) for cit in root.iter() if lname(cit.tag) == "cit" and not cit_is_biblical(cit)
            for ref in cit if lname(ref.tag) == "ref"}


def _phrase_only(node) -> bool:
    """Vrai si ``node`` ne contient que du contenu de phrase (``PHRASE_TAGS``) ;
    le contenu d'une note n'est pas examiné."""
    for child in node:
        tag = lname(child.tag)
        if tag not in PHRASE_TAGS or (tag != "note" and not _phrase_only(child)):
            return False
    return True


def _span(value) -> int | None:
    """``@cols`` ou ``@rows`` d'une cellule, s'il vaut plus de 1."""
    value = (value or "").strip()
    return int(value) if value.isdigit() and int(value) > 1 else None


def list_is_numbered(node) -> bool:
    """Même règle que les feuilles livrées : ``@rend`` contient « numbered »,
    ou ``@type`` vaut « ordered » ou « numbered »."""
    return ("numbered" in (node.attrib.get("rend") or "").split()
            or (node.attrib.get("type") or "").strip() in ("ordered", "numbered"))


def lacuna_witnesses(root: ET.Element) -> dict:
    """``{id(élément): témoins}`` des ``<lacunaStart/>`` et ``<lacunaEnd/>``
    de ``root`` : leur ``@wit``, sinon celui de la leçon (``<rdg>``,
    ``<lem>``) qui les contient, comme sur le bureau (``pivot_lines``)."""
    found = {}

    def visit(node, reading_wit):
        tag = lname(node.tag)
        if tag in LACUNA_TAGS:
            wit = node.attrib.get("wit")
            tokens = wit_tokens(wit if wit is not None else reading_wit)
            if tokens:
                found[id(node)] = sorted(set(tokens))
            return
        if tag in ("rdg", "lem"):
            reading_wit = node.attrib.get("wit")
        for child in node:
            visit(child, reading_wit)

    visit(root, None)
    return found


def _reading_options(path, target, base_line_keys, root, line_anchors, segment_of, target_of):
    """Arbre, ``{id(lb): clé}``, texte et pivot de chaque nœud. Sans options,
    un fichier unique et un seul pivot, comme avant ; pour une édition
    assemblée (V0.9.1.6), l'arbre de ``assembled_document``, l'index de
    ``build_segment_lb_index``, et le texte et le pivot de chaque nœud."""
    if root is None:
        root = ET.parse(path).getroot()
    if line_anchors is None and base_line_keys is not None:
        line_anchors = build_pivot_lb_index(root, target, base_line_keys)[0]
    return (root, line_anchors, segment_of or (lambda node: 0),
            target_of or (lambda node: target))


def extract_corrected_pages(path: Path, target: str, page_resolver=None, base_line_keys=None, *,
                            root=None, line_anchors=None, segment_of=None, target_of=None):
    """
    Extrait les lignes physiques de la TEI corrigée.

    Chaque ligne contient :
      - text : texte du témoin cible, hors <note> et <ref>
      - runs : fragments pour rendu HTML (texte / variante / note)
      - annotations : notices structurées des variantes et notes
    Les <lb> à l'intérieur des <note> sont ignorés.

    Édition assemblée (V0.9.1.6) : ``root``, ``line_anchors``, ``segment_of``
    et ``target_of`` (voir ``_reading_options``) ; dans un texte
    synchronisé à part, les lignes, les leçons et les pages sont celles de
    son pivot, et une ligne ne se poursuit pas d'un texte à l'autre.
    """
    root, lb_anchor_lookup, segment_of, target_of = _reading_options(
        path, target, base_line_keys, root, line_anchors, segment_of, target_of)
    witness_labels = extract_witness_labels(root)
    texts = reading_texts(root)
    if not texts:
        raise ValueError(f"Aucun <body> TEI trouvé dans {path}")

    pages = OrderedDict()
    state = {"page": None, "current": None, "ann": 0, "seg": 0, "current_by_seg": {}}

    def enter(node):
        """Le texte de ``node`` devient le texte courant : sa ligne courante
        est reprise là où ce texte l'avait laissée."""
        index = segment_of(node)
        if index != state["seg"]:
            state["current_by_seg"][state["seg"]] = state["current"]
            state["seg"] = index
            state["current"] = state["current_by_seg"].get(index)
        return index

    def new_annotation_id(prefix):
        state["ann"] += 1
        return f"{prefix}{state['ann']}"

    def ensure_run(kind, text, **extra):
        cur = state["current"]
        if cur is None or text is None or text == "":
            return
        # Fusion des fragments adjacents de même nature. Cela évite de poser
        # plusieurs marqueurs « v » lorsqu'une même variante contient <hi>, <sic>, etc.
        prev = cur["runs"][-1] if cur["runs"] else None
        merge_text = kind == "text" and prev and prev.get("type") == "text"
        merge_variant = (
            kind == "variant" and prev and prev.get("type") == "variant"
            and prev.get("ann_id") == extra.get("ann_id")
        )
        if merge_text or merge_variant:
            prev["text"] += text
        else:
            run = {"type": kind, "text": text}
            run.update(extra)
            cur["runs"].append(run)
        cur["raw_text"].append(text)

    def add_note(node):
        cur = state["current"]
        if cur is None:
            return
        txt = flatten_editorial_text(node, include_notes=True, include_refs=True)
        if not txt:
            return
        aid = new_annotation_id("n")
        ann = {
            "id": aid,
            "kind": "note",
            "text": txt,
            "type": node.attrib.get("type", ""),
            "anchored": node.attrib.get("anchored", ""),
        }
        cur["annotations"].append(ann)
        # Le run ne contribue pas au texte manuscrit : marqueur cliquable uniquement.
        cur["runs"].append({"type": "note", "text": "", "ann_id": aid, "tooltip": txt})

    def walk(node, active_variant=None):
        tag = lname(node.tag)
        if tag == "teiHeader":
            return
        enter(node)
        if tag == "note":
            add_note(node)
            return
        if tag == "ref":
            # Les références normalisées de l'éditeur ne sont pas du texte du manuscrit.
            return
        if tag == "pb":
            edref = node.attrib.get("edRef")
            if edref and not witness_matches(edref, target_of(node)):
                return
            page = page_resolver.resolve(node) if page_resolver is not None else node.attrib.get("n")
            state["page"] = page
            state["current"] = None
            if page:
                pages.setdefault(page, [])
            return
        if tag == "lb":
            edref = node.attrib.get("edRef")
            if edref and not witness_matches(edref, target_of(node)):
                return
            if lb_anchor_lookup is not None:
                canonical_key = lb_anchor_lookup.get(id(node))
                if not canonical_key:
                    state["current"] = None
                    return
                # The physical page id comes from the pivot JSON. TEI pb/@n
                # may instead name a folio, or be absent entirely.
                page = canonical_key.rsplit('::', 1)[0]
            else:
                canonical_key = None
                page = state["page"]
                if not page:
                    return
            line = {
                "line_key": canonical_key,
                "text": "",
                "raw_text": [],
                "runs": [],
                "annotations": [],
                "attrs": dict(node.attrib),
            }
            pages.setdefault(page, []).append(line)
            state["current"] = line
            return
        if tag == "choice":
            form = choose_choice_form(node)
            if form is not None:
                walk(form, active_variant=active_variant)
            return
        if tag == "app":
            # Une coquille rencontrée dans une TEI fournie, <wit wit="#…">, est
            # lue comme une leçon vide (app_readings).
            selected = choose_reading(node, target_of(node))
            if selected is None:
                return
            aid = new_annotation_id("v")
            selected_text = flatten_editorial_text(selected, include_notes=False, include_refs=False)
            ann = {
                "id": aid,
                "kind": "variant",
                "selected": selected_text,
                "target": target_of(node).lstrip("#"),
                "readings": describe_readings(node),
            }
            if state["current"] is not None:
                state["current"]["annotations"].append(ann)
            # On parcourt réellement la lecture choisie pour respecter d'éventuels <lb>.
            walk(selected, active_variant=(aid, ann))
            return

        if node.text:
            if active_variant:
                aid, ann = active_variant
                ensure_run("variant", node.text, ann_id=aid, tooltip=variant_tooltip(ann, witness_labels))
            else:
                ensure_run("text", node.text)

        for child in list(node):
            walk(child, active_variant=active_variant)
            enter(node)           # la suite (tail) est dans le texte de ``node``
            if child.tail:
                if active_variant:
                    aid, ann = active_variant
                    ensure_run("variant", child.tail, ann_id=aid, tooltip=variant_tooltip(ann, witness_labels))
                else:
                    ensure_run("text", child.tail)

    # Tous les textes : <front>, <body> et <back>, ceux d'un <group> compris.
    for text in texts:
        walk(text)

    # Nettoyage des lignes pour l'alignement + nettoyage minimal des runs.
    for page_lines in pages.values():
        for line in page_lines:
            line["text"] = clean_text("".join(line.pop("raw_text")))
            # Normalise les espaces de chaque run sans effacer l'information de séparation.
            for run in line["runs"]:
                if run["type"] in {"text", "variant"}:
                    run["text"] = re.sub(r"\s+", " ", run.get("text", ""))
            # Supprime seulement les espaces de bord globaux.
            visible = [r for r in line["runs"] if r["type"] in {"text", "variant"} and r.get("text")]
            if visible:
                visible[0]["text"] = visible[0]["text"].lstrip()
                visible[-1]["text"] = visible[-1]["text"].rstrip()
            # Déduplique les annotations de variante si un <app> franchit un <lb> :
            # la variante doit être présente sur chaque ligne où elle est rendue.
            present_variant_ids = {r.get("ann_id") for r in line["runs"] if r["type"] == "variant"}
            known_ids = {a["id"] for a in line["annotations"]}
            # Les apps qui commencent avant un lb peuvent ne pas avoir été ajoutés à cette nouvelle ligne.
            # On les récupère depuis les tooltips/runs lors du rendu ; on laisse annotations vide si besoin.
            line["present_variant_ids"] = [x for x in present_variant_ids if x]
            line["break_no"] = line["attrs"].get("break") == "no"
    return pages, witness_labels


def variant_tooltip(ann, witness_labels):
    bits = []
    for r in ann.get("readings", []):
        names = []
        for w in r.get("wit", []):
            names.append(witness_labels.get(w, w))
        who = ", ".join(names) if names else r.get("role", "lecture")
        txt = r.get("text") or "∅"
        bits.append(f"{who}: {txt}")
    return " | ".join(bits)


# =============================================================================
# Vue de lecture continue de la TEI corrigée
# =============================================================================

def extract_reading_document(path: Path, target: str, include_foreign_pagebreaks: bool = False, page_resolver=None, base_line_keys=None, *,
                             root=None, line_anchors=None, segment_of=None, target_of=None, pb_line_keys=False,
                             text_mode="witness", text_witness=None):
    """Construit une vue de lecture par blocs (paragraphes/titres) sans matérialiser les <lb>.

    Les <lb> restent uniquement des ancres vers les lignes physiques. Chaque segment
    de texte porte donc une clé ``page::index`` qui permet au HTML d'ouvrir l'image
    de la ligne correspondante au clic.

    Édition assemblée (V0.9.1.6) : ``root``, ``line_anchors``, ``segment_of``
    et ``target_of`` (voir ``_reading_options``). Dans un texte synchronisé
    à part, les segments portent ``seg`` (son numéro) ; ses lignes, ses
    leçons et ses pages sont celles de son pivot ; la ligne courante est
    propre à chaque texte. Avec ``pb_line_keys``, chaque saut de page porte
    aussi la ligne du pivot ouverte à cet endroit (``line_key``), comme
    ``pivot_lines`` sur le bureau : le parcours d'un témoin par pages en a
    besoin, car un ``<pb>`` placé juste après un ``<lb/>`` précède le texte
    de cette ligne.

    Blocs (V0.9.3.0) : tous les textes sont lus (``reading_texts``). Chaque
    division (``<div>``, ``<front>``, ``<back>``, texte d'un ``<group>``)
    est un bloc ``div`` : ``id`` (son ``@xml:id``, sinon un identifiant
    produit), ``level``, ``part`` (``front``, ``back``), ``label`` (le
    texte de son premier ``<head>``, sinon son ``@n``) et ``title`` (son
    ``@n``, s'il n'a pas de ``<head>``). Les blocs rendus
    (``RENDERED_BLOCKS``) : ``head`` (``div_title`` pour le titre d'une
    division, ``table`` pour celui d'un tableau), ``p`` (``<p>``, ``<ab>``,
    contenu de phrase entre deux blocs), ``l`` (``n``, ``group`` : le rang
    de son ``<lg>``), ``item`` (``list``, ``numbered``, ``depth``,
    ``label``), ``cell`` (``table``, ``row``, ``label``, ``cols``,
    ``rows``), ``caption`` (``<figDesc>``) et ``note`` (note posée entre
    deux blocs). Une liste, un tableau, une figure ou une strophe sortent du
    paragraphe ou de l'entrée qui les contient ; la suite en est un bloc
    marqué ``cont``.

    Texte, comme « Édition critique » : un ``<choice>`` montre une forme
    (``CHOICE_ORDER``), les autres dans ``alt`` ; ``<del>`` et
    ``<surplus>`` ont le style ``del``, ``<add>`` le style ``add`` ;
    ``<supplied>`` est entre crochets ; ``<gap>`` donne « […] », son
    ``@reason`` et son ``@extent`` dans ``alt`` ; ``<space>`` une espace.
    Les leçons d'un ``<rdgGrp>`` sont lues (``app_readings``). ``lang`` :
    le ``@xml:lang`` du texte, sinon de la racine.

    Choix du texte (V0.9.3.0) : ``text_mode`` (``established`` : le
    ``<lem>`` d'abord ; ``witness`` : la leçon du témoin d'abord) et
    ``text_witness`` (le témoin choisi, sinon le pivot de chaque texte),
    voir ``choose_reading_status`` ; sans eux, le pivot, comme avant. Le
    texte de repli d'un ``<app>`` où le témoin choisi n'a pas de leçon porte
    ``missing`` (``{"wit", "fallback"}``), un repli vide un segment
    ``missing`` (« ∅ ») ; ``missing_readings`` les compte. Les ``<lb>`` et
    ``<pb>`` du pivot d'une leçon non affichée restent des repères
    (``pivot_marks_in``) : chaque ligne du pivot garde sa clé.
    """
    # The very same ordinal-to-JSON association that drives desktop cursor
    # navigation. PageResolver remains relevant for page-only witnesses, but
    # cannot be used to renumber line keys in a synchronised pivot.
    root, lb_anchor_lookup, segment_of, target_of = _reading_options(
        path, target, base_line_keys, root, line_anchors, segment_of, target_of)
    witness_labels = extract_witness_labels(root)
    texts = reading_texts(root)
    if not texts:
        raise ValueError(f"Aucun <body> TEI trouvé dans {path}")
    # Lacunes (V0.9.1.6) : un repère invisible par balise, à sa place.
    lacunae = {}
    for text in texts:
        lacunae.update(lacuna_witnesses(text))
    taken_ids = {e.attrib.get(XML_ID) for e in root.iter()}
    ref_notes = reference_notes(root)

    blocks = []
    annotations = {}
    state = {
        "page": None,
        "line_index": -1,
        "line_key": None,
        "line_counts_by_physical_page": {},
        "block": None,
        "ann": 0,
        "pending_lb_sep": None,
        "seg": 0,
        "line_key_by_seg": {},
        # Dans une strophe, une liste, un tableau ou une figure, ce qui tombe
        # entre deux blocs (<pb/>, lacune…) reste dans le bloc précédent.
        "sticky": False,
        "divs": 0, "lists": 0, "tables": 0, "groups": {}, "list_depth": 0,
        # Choix du texte : le manque en cours (témoin choisi sans leçon), le
        # @wit de la leçon affichée, le nombre de manques.
        "missing": None, "shown_wit": None, "missing_count": 0,
    }

    def enter(node):
        """Le texte de ``node`` devient le texte courant : sa ligne courante
        est reprise là où ce texte l'avait laissée."""
        index = segment_of(node)
        if index != state["seg"]:
            state["line_key_by_seg"][state["seg"]] = state["line_key"]
            state["seg"] = index
            state["line_key"] = state["line_key_by_seg"].get(index)
        return index

    def tagged(seg):
        if state["seg"]:
            seg["seg"] = state["seg"]
        return seg

    def new_ann_id(prefix):
        state["ann"] += 1
        return f"r{prefix}{state['ann']}"

    def current_line_key():
        return state["line_key"]

    def start_block(kind="p", attrs=None):
        block = {"type": kind, "attrs": attrs or {}, "segments": []}
        blocks.append(block)
        state["pending_lb_sep"] = None
        return block

    def ensure_block():
        # Un bloc déjà suivi d'autres blocs n'est plus le bloc courant : ce
        # qui vient ensuite irait sinon avant eux.
        if state["block"] is None or blocks[-1] is not state["block"]:
            state["block"] = start_block("p")
        return state["block"]

    def trim_last_visible_right():
        block = state.get("block")
        if not block:
            return
        for seg in reversed(block["segments"]):
            if seg.get("kind") == "text" and seg.get("text"):
                seg["text"] = seg["text"].rstrip()
                return

    def add_text(text, styles=None, variant_id=None, extra_classes=None, alt=None):
        if text is None or text == "":
            return
        block = ensure_block()
        text = re.sub(r"\s+", " ", text)
        sep = state.get("pending_lb_sep")
        if sep is not None:
            text = text.lstrip()
            if text:
                text = sep + text
            state["pending_lb_sep"] = None
        if not text:
            return
        seg = tagged({
            "kind": "text",
            "text": text,
            "line_key": current_line_key(),
            "styles": list(styles or []),
        })
        if variant_id:
            seg["variant_id"] = variant_id
        if state["missing"]:
            seg["missing"] = dict(state["missing"])
        if extra_classes:
            seg["classes"] = list(extra_classes)
        if alt:
            # Autres formes d'un <choice>, détail d'un <gap> : [[élément, texte], …].
            seg["alt"] = [list(item) for item in alt]
        prev = block["segments"][-1] if block["segments"] else None
        if (prev and prev.get("kind") == "text" and
            prev.get("line_key") == seg.get("line_key") and
            prev.get("styles") == seg.get("styles") and
            prev.get("variant_id") == seg.get("variant_id") and
            prev.get("classes") == seg.get("classes") and
            prev.get("alt") == seg.get("alt") and
            prev.get("missing") == seg.get("missing") and
            prev.get("seg") == seg.get("seg")):
            prev["text"] += text
        else:
            block["segments"].append(seg)

    def add_marker(kind, ann_id, tooltip=""):
        block = ensure_block()
        block["segments"].append(tagged({
            "kind": kind,
            "ann_id": ann_id,
            "tooltip": tooltip,
            "line_key": current_line_key(),
        }))

    def add_pagebreak(label, facs="", edref="", foreign=False):
        block = ensure_block()
        seg = {
            "kind": "pb",
            "label": label or "",
            "page": label or "",
            "facs": facs or "",
            "edref": edref or "",
            "foreign": bool(foreign),
        }
        if pb_line_keys:
            seg["line_key"] = current_line_key()
        block["segments"].append(tagged(seg))

    def add_lacuna(node):
        """Repère invisible d'un ``<lacunaStart/>`` ou ``<lacunaEnd/>``, avec
        la ligne du pivot ouverte à sa place."""
        witnesses = lacunae.get(id(node))
        if not witnesses:
            return
        enter(node)
        block = ensure_block()
        block["segments"].append(tagged({
            "kind": "lacuna",
            "start": lname(node.tag) == "lacunaStart",
            "wit": list(witnesses),
            # La ligne du pivot ouverte à cet endroit : celle où la lacune
            # commence ou finit (le repère précède le texte de la ligne).
            "line_key": current_line_key(),
        }))

    def add_lacunae_in(node):
        """Repères des lacunes contenues dans ``node``, qui n'est pas rendu
        (leçon non retenue, note, référence)."""
        for element in node.iter():
            if lname(element.tag) in LACUNA_TAGS:
                add_lacuna(element)

    def add_editorial_ref(text):
        """Ajoute une identification éditoriale de citation, hors texte manuscrit."""
        text = clean_text(text)
        if not text:
            return
        block = ensure_block()
        block["segments"].append(tagged({
            "kind": "editorial-ref",
            "text": text,
            "line_key": current_line_key(),
        }))

    def choose_app_reading(node):
        """``(leçon, @wit, manque)`` selon le choix du texte."""
        return choose_reading_status(node, target_of(node), text_mode, text_witness)

    def foreign_to_shown(node):
        """Un ``<lb>`` ou ``<pb>`` sans ``@edRef`` d'une leçon affichée qui
        n'est pas celle du pivot : une coupure de ses témoins, pas du pivot."""
        shown = state["shown_wit"]
        return shown is not None and not witness_matches(shown, target_of(node))

    def is_pivot_mark(element, wit, pivot):
        """Un ``<lb>`` ou ``<pb>`` du pivot dans une leçon non affichée de
        témoins ``wit`` : son ``@edRef`` est le pivot, ou il n'en a pas et la
        leçon est celle du pivot. Avec un index des lignes, un ``<lb>`` doit
        y être."""
        tag = lname(element.tag)
        if tag not in ("lb", "pb"):
            return False
        edref = element.attrib.get("edRef")
        if not (witness_matches(edref, pivot) if edref else witness_matches(wit, pivot)):
            return False
        return tag == "pb" or lb_anchor_lookup is None or id(element) in lb_anchor_lookup

    def hidden_marks(node, selected):
        """``(début, fin)`` : repères du pivot des leçons non affichées."""
        pivot = target_of(node)
        leading, following = [], []
        for reading, wit in reading_witnesses(node):
            if reading is not selected:
                first, rest = pivot_marks_in(reading, lambda e, w=wit: is_pivot_mark(e, w, pivot))
                leading += first
                following += rest
        return leading, following

    def spread_lines(segments, start, marks):
        """Les ``<lb>`` du pivot de sa leçon non affichée (``(élément,
        part)``) : la ligne change dans le texte affiché (``segments[start:]``)
        à la même part, au début d'un mot ; s'il n'y en a plus, après lui.
        Chaque ligne du pivot garde ainsi du texte ; sans texte affiché (le
        témoin omet le passage), un repère ``line-anchor`` marque sa place."""
        full = "".join(segments[i]["text"] for i in range(start, len(segments)) if segments[i]["kind"] == "text")
        letters = [k for k, ch in enumerate(full) if not ch.isspace()]
        cuts = []
        for element, part in marks:
            advance_line(element)
            if not letters:
                segments.append(tagged({"kind": "line-anchor", "line_key": state["line_key"]}))
                continue
            target = letters[min(len(letters) - 1, int(part * len(letters)))]
            if target and not full[target - 1].isspace():
                word = re.search(r"\s\S", full[target:])
                target = target + word.start() + 1 if word else None
            if target is not None:
                cuts.append((max(target, cuts[-1][0]) if cuts else target, state["line_key"]))
        if not cuts:
            return
        out, offset, current, index = segments[:start], 0, None, 0
        for seg in segments[start:]:
            if seg["kind"] != "text":
                if current is not None and "line_key" in seg:
                    seg["line_key"] = current
                out.append(seg)
                continue
            text, begin, piece = seg["text"], offset, 0
            offset += len(text)
            while index < len(cuts) and cuts[index][0] < offset:
                cut = cuts[index][0] - begin
                if cut > piece:
                    out.append(dict(seg, text=text[piece:cut], **({"line_key": current} if current is not None else {})))
                    piece = cut
                current = cuts[index][1]
                index += 1
            out.append(dict(seg, text=text[piece:], **({"line_key": current} if current is not None else {})))
        segments[:] = out

    def add_hidden_marks(elements):
        """Repères invisibles : la ligne ou la page du pivot change, sans
        texte ni espace."""
        for element in elements:
            enter(element)
            if lname(element.tag) == "lb":
                advance_line(element)
            else:
                walk(element)

    def walk_shown(selected, wit, missing, walker):
        """Parcourt la leçon affichée (``walker``), marquée si le témoin
        choisi n'en a pas ; un repli vide donne le repère « ∅ »."""
        saved = state["missing"], state["shown_wit"]
        state["missing"] = missing or saved[0]
        state["shown_wit"] = wit
        walker()
        state["missing"], state["shown_wit"] = saved
        if missing:
            state["missing_count"] += 1
            if not clean_text(flatten_editorial_text(selected)):
                block = ensure_block()
                block["segments"].append(tagged({"kind": "missing", "missing": dict(missing),
                                                 "line_key": current_line_key()}))

    def describe_app(node):
        return describe_readings(node)

    def style_for(node, inherited):
        styles = list(inherited)
        tag = lname(node.tag)
        if tag == "hi":
            rend = (node.attrib.get("rend") or "").lower()
            tokens = set(re.split(r"[\s,;]+", rend))
            if "italic" in rend or "italics" in rend:
                styles.append("italic")
            if "bold" in rend:
                styles.append("bold")
            if "smallcaps" in rend or "small-caps" in rend:
                styles.append("smallcaps")
            if tokens & {"sup", "superscript", "super"}:
                styles.append("sup")
            if tokens & {"sub", "subscript"}:
                styles.append("sub")
            if "underline" in rend:
                styles.append("underline")
        elif tag in {"del", "surplus"}:
            styles.append("del")
        elif tag == "add":
            styles.append("add")
        elif tag == "supplied":
            styles.append("supplied")
        elif tag in {"foreign", "title"}:
            styles.append("italic")
        elif tag == "unclear":
            styles.append("unclear")
        elif tag == "sic":
            styles.append("sic")
        elif tag == "quote":
            styles.append("quote")
        return styles

    def advance_line(node):
        """Un ``<lb>`` du pivot : la ligne courante devient la sienne."""
        if lb_anchor_lookup is not None:
            state["line_key"] = lb_anchor_lookup.get(id(node))
        elif state["page"]:
            state["line_index"] += 1
            if page_resolver is not None:
                state["line_counts_by_physical_page"][state["page"]] = state["line_index"]
            state["line_key"] = f"{state['page']}::{state['line_index'] + 1}"

    def walk(node, styles=None, variant_id=None, alt=None):
        styles = list(styles or [])
        tag = lname(node.tag)
        if tag == "teiHeader":
            return
        enter(node)
        if tag == "pb":
            edref = node.attrib.get("edRef") or ""
            page = node.attrib.get("n")
            facs = node.attrib.get("facs") or ""
            if (edref and not witness_matches(edref, target_of(node))) or (not edref and foreign_to_shown(node)):
                # V0.8.2 : le texte de lecture reste celui du témoin cible, mais
                # les changements de page des autres témoins peuvent être gardés
                # comme ancres invisibles par le viewer générique. Ils ne doivent
                # surtout pas modifier l'état de ligne/page du témoin cible.
                if include_foreign_pagebreaks and (page or facs):
                    add_pagebreak(page, facs, edref, True)
                return
            state["page"] = page_resolver.resolve(node) if page_resolver is not None else page
            # A double-page image can have two TEI <pb> (left/right zones)
            # but only one physical alignment page. The legacy implementation
            # restarted numbering at every <pb>, yielding repeated page::1
            # keys for the second part of that same image.
            if page_resolver is not None and state["page"]:
                state["line_index"] = state["line_counts_by_physical_page"].get(state["page"], -1)
            else:
                state["line_index"] = -1
            if lb_anchor_lookup is None:
                state["line_key"] = None
            if page or facs:
                add_pagebreak(page, facs, edref, False)
            return
        if tag == "lb":
            edref = node.attrib.get("edRef")
            if (edref and not witness_matches(edref, target_of(node))) or (not edref and foreign_to_shown(node)):
                # Les <lb> d'un autre témoin sont des ancres invisibles et ne
                # doivent pas casser la lecture continue du pivot.
                return
            advance_line(node)
            trim_last_visible_right()
            state["pending_lb_sep"] = "\u2060" if node.attrib.get("break") == "no" else " "
            return
        if tag in LACUNA_TAGS:
            add_lacuna(node)
            return
        if tag == "note" or (tag == "ref" and id(node) in ref_notes):
            # La référence d'une citation non biblique est une note (V0.9.3.0).
            add_lacunae_in(node)
            enter(node)
            txt = flatten_editorial_text(node, include_notes=True, include_refs=True)
            if txt:
                aid = new_ann_id("n")
                annotations[aid] = {
                    "id": aid, "kind": "note", "text": txt,
                    "type": "ref" if tag == "ref" else node.attrib.get("type", ""),
                    "anchored": node.attrib.get("anchored", ""),
                }
                add_marker("note", aid, txt)
            return
        if tag == "ref":
            # Dans cette édition, <cit>/<ref> est une identification éditoriale
            # de la source de la citation : elle ne fait pas partie du manuscrit.
            add_lacunae_in(node)
            enter(node)
            add_editorial_ref(flatten_editorial_text(node, include_notes=True, include_refs=True))
            return
        if tag == "app":
            selected, wit, missing = choose_app_reading(node)
            if selected is None:
                return
            aid = new_ann_id("v")
            ann = {
                "id": aid, "kind": "variant",
                "selected": flatten_editorial_text(selected, include_notes=False, include_refs=False),
                "target": target_of(node).lstrip("#"), "readings": describe_app(node),
            }
            if missing:
                ann["missing"] = dict(missing)
            annotations[aid] = ann
            leading, following = hidden_marks(node, selected)
            add_hidden_marks(leading)
            block = ensure_block()
            start = len(block["segments"])

            def readings_of(container):
                # Dans l'ordre : la leçon retenue, les repères de lacune des autres.
                for other in list(container):
                    if other is selected:
                        walk_shown(selected, wit, missing,
                                   lambda: walk(selected, styles=styles, variant_id=aid, alt=alt))
                    elif lname(other.tag) == "rdgGrp" and any(x is selected for x in other.iter()):
                        readings_of(other)
                    else:
                        add_lacunae_in(other)

            readings_of(node)
            # Les <lb> qui précèdent le premier <pb> se répartissent dans le
            # texte affiché ; le reste suit l'<app>.
            spread = []
            while following and lname(following[0][0].tag) == "lb":
                spread.append(following.pop(0))
            if spread and state["block"] is block:
                spread_lines(block["segments"], start, spread)
            else:
                following = spread + following
            enter(node)
            add_marker("variant-marker", aid, variant_tooltip(ann, witness_labels))
            add_hidden_marks([element for element, _part in following])
            return
        if tag == "choice":
            # Comme « Édition critique » : une forme, les autres en infobulle.
            form = choose_choice_form(node)
            if form is None:
                return
            others = [[lname(other.tag), flatten_editorial_text(other)] for other in node
                      if other is not form and isinstance(other.tag, str)]
            for other in node:
                if other is not form:
                    add_lacunae_in(other)
            walk(form, styles=styles, variant_id=variant_id,
                 alt=[item for item in others if item[1]] or alt)
            return
        if tag == "gap":
            detail = " · ".join(clean_text(value) for value in (
                node.attrib.get("reason"),
                node.attrib.get("extent") or " ".join(filter(None, (node.attrib.get("quantity"),
                                                                     node.attrib.get("unit"))))) if clean_text(value))
            add_text("[…]", styles + ["gap"], variant_id=variant_id, alt=[["gap", detail]])
            return
        if tag == "space":
            add_text(" ", styles, variant_id=variant_id, alt=alt)
            return

        new_styles = style_for(node, styles)
        if tag == "supplied":
            add_text("[", new_styles, variant_id=variant_id, alt=alt)
        if node.text:
            add_text(node.text, new_styles, variant_id=variant_id, alt=alt)
        for child in list(node):
            walk(child, styles=new_styles, variant_id=variant_id, alt=alt)
            enter(node)           # la suite (tail) est dans le texte de ``node``
            if child.tail:
                add_text(child.tail, new_styles, variant_id=variant_id, alt=alt)
        if tag == "supplied":
            add_text("]", new_styles, variant_id=variant_id, alt=alt)

    def new_div_id():
        while True:
            state["divs"] += 1
            candidate = f"div-{state['divs']}"
            if candidate not in taken_ids:
                taken_ids.add(candidate)
                return candidate

    def finish_block(block, old):
        """Après un bloc : dans un conteneur « collant », il reste le bloc
        courant ; ailleurs, le bloc courant redevient ``old``."""
        state["block"] = block if state["sticky"] else old

    def walk_block(node, kind, attrs=None, split=(), level=0):
        """``node`` devient un bloc ``kind``. Ses enfants de ``split`` en
        sortent pour être affichés à part ; la suite est un bloc ``kind``
        marqué ``cont``. Renvoie le premier bloc."""
        old = state["block"]
        first = block = state["block"] = start_block(kind, attrs)
        enter(node)
        styles = style_for(node, [])
        if node.text:
            add_text(node.text, styles)
        for child in list(node):
            if lname(child.tag) in split:
                sticky = state["sticky"]
                state["sticky"] = False
                walk_container(child, level, node)
                state["sticky"] = sticky
                block = state["block"] = start_block(kind, dict(attrs or {}, cont=True))
            else:
                walk(child, styles=styles)
            enter(node)
            if child.tail:
                add_text(child.tail, styles)
        finish_block(block, old)
        return first

    def walk_inline_block(node, kind="p"):
        """``node`` et son contenu de phrase forment un bloc ``kind`` : une
        note y est un repère, une référence une identification éditoriale."""
        old = state["block"]
        block = state["block"] = start_block(kind)
        walk(node, styles=[])
        finish_block(block, old)

    def walk_children(node, level, sticky=False, special=None):
        """Enfants d'un conteneur ; ``special(enfant)`` en traite certains."""
        old_block, old_sticky = state["block"], state["sticky"]
        state["sticky"] = sticky
        if node.text and node.text.strip():
            add_text(node.text, [])
        for child in list(node):
            if special is None or not special(child):
                walk_container(child, level, node)
            enter(node)
            if child.tail and child.tail.strip():
                add_text(child.tail, [])
        state["block"], state["sticky"] = old_block, old_sticky

    def walk_division(node, level, part=None):
        attrs = {"id": node.attrib.get(XML_ID) or new_div_id(), "level": level}
        if part:
            attrs["part"] = part
        blocks.append({"type": "div", "attrs": attrs, "segments": []})
        head = next((child for child in node if lname(child.tag) == "head"), None)

        def title(child):
            if child is not head:
                return False
            block = walk_block(child, "head", {"div_title": True}, level=level)
            label = clean_text("".join(seg.get("text", "") for seg in block["segments"] if seg["kind"] == "text"))
            if label:
                attrs["label"] = label
            return True

        walk_children(node, level, special=title)
        n = clean_text(node.attrib.get("n") or "")
        if "label" not in attrs and n:
            attrs["title"] = attrs["label"] = n

    def walk_lg(node, level):
        def special(child):
            tag = lname(child.tag)
            if tag == "head":
                walk_block(child, "head", level=level)
            elif tag == "l":
                walk_line(child, node, level)
            elif tag == "lg":
                walk_lg(child, level)
            else:
                return False
            return True

        walk_children(node, level, sticky=True, special=special)

    def walk_line(node, parent, level):
        groups = state["groups"]
        attrs = {"group": groups.setdefault(id(parent), len(groups) + 1)}
        n = clean_text(node.attrib.get("n") or "")
        if n:
            attrs["n"] = n
        walk_block(node, "l", attrs, level=level)

    def walk_list(node, level):
        state["lists"] += 1
        depth = state["list_depth"] = state["list_depth"] + 1
        attrs = {"list": state["lists"], "numbered": list_is_numbered(node), "depth": depth}

        def special(child):
            tag = lname(child.tag)
            if tag == "head":
                walk_block(child, "head", level=level)
            elif tag == "item":
                walk_block(child, "item", dict(attrs), split=SPLIT_TAGS, level=level)
            elif tag == "label":
                walk_block(child, "item", dict(attrs, label=True), level=level)
            else:
                return False
            return True

        walk_children(node, level, sticky=True, special=special)
        state["list_depth"] = depth - 1

    def walk_table(node, level):
        state["tables"] += 1
        table = state["tables"]
        rows = 0

        def cell(child, row):
            if lname(child.tag) != "cell":
                return False
            attrs = {"table": table, "row": rows}
            if (child.attrib.get("role") or row.attrib.get("role")) == "label":
                attrs["label"] = True
            for name in ("cols", "rows"):
                span = _span(child.attrib.get(name))
                if span:
                    attrs[name] = span
            walk_block(child, "cell", attrs, level=level)
            return True

        def special(child):
            nonlocal rows
            tag = lname(child.tag)
            if tag == "head":
                walk_block(child, "head", {"table": table}, level=level)
            elif tag == "row":
                rows += 1
                walk_children(child, level, sticky=True, special=lambda c: cell(c, child))
            else:
                return False
            return True

        walk_children(node, level, sticky=True, special=special)

    def walk_figure(node, level):
        def special(child):
            if lname(child.tag) != "head":
                return False
            walk_block(child, "head", level=level)
            return True

        walk_children(node, level, sticky=True, special=special)

    def walk_container(node, level=0, parent=None):
        tag = lname(node.tag)
        enter(node)
        if tag == "teiHeader":
            return
        if tag in LACUNA_TAGS:
            add_lacuna(node)
            return
        if tag in MILESTONE_TAGS:
            walk(node, styles=[])
            return
        if tag in DIVISION_TAGS:
            walk_division(node, level + 1)
        elif tag in ("front", "back"):
            walk_division(node, level + 1, part=tag)
        elif tag == "text" and parent is not None and lname(parent.tag) == "group":
            walk_division(node, level + 1)
        elif tag in ("text", "body", "group"):
            walk_children(node, level)
        elif tag in ("p", "ab"):
            walk_block(node, "p", dict(node.attrib), split=SPLIT_TAGS, level=level)
        elif tag == "head":
            walk_block(node, "head", level=level)
        elif tag == "l":
            walk_line(node, parent, level)
        elif tag == "lg":
            walk_lg(node, level)
        elif tag == "list":
            walk_list(node, level)
        elif tag == "item":
            walk_block(node, "item", {"list": 0, "numbered": False, "depth": max(1, state["list_depth"])},
                       split=SPLIT_TAGS, level=level)
        elif tag == "table":
            walk_table(node, level)
        elif tag == "figure":
            walk_figure(node, level)
        elif tag == "figDesc":
            walk_block(node, "caption", level=level)
        elif tag == "note":
            walk_inline_block(node, "note")
        elif _phrase_only(node):
            # Contenu de phrase entre deux blocs (citation, <cit>, <app>…) : un paragraphe.
            walk_inline_block(node)
        elif tag == "app":
            walk_structural_app(node, level)
        else:
            # Conteneur inconnu (<quote> de paragraphes, <titlePage>, <sp>…).
            walk_children(node, level)

    def walk_structural_app(node, level):
        """``<app>`` dont la leçon retenue contient des blocs : ses blocs, puis
        le repère de la variante."""
        selected, wit, missing = choose_app_reading(node)
        if selected is None:
            return
        aid = new_ann_id("v")
        ann = {
            "id": aid, "kind": "variant",
            "selected": flatten_editorial_text(selected, include_notes=False, include_refs=False),
            "target": target_of(node).lstrip("#"), "readings": describe_app(node),
        }
        if missing:
            ann["missing"] = dict(missing)
        annotations[aid] = ann
        leading, following = hidden_marks(node, selected)
        add_hidden_marks(leading)
        for other in app_readings(node):
            if other is not selected:
                add_lacunae_in(other)
        walk_shown(selected, wit, missing, lambda: walk_children(selected, level))
        enter(node)
        add_marker("variant-marker", aid, variant_tooltip(ann, witness_labels))
        add_hidden_marks([element for element, _part in following])

    for text in texts:
        walk_container(text)

    # Les blocs non rendus ne gardent pas de repère de lacune : ils passent au
    # début du bloc rendu suivant (sinon à la fin du précédent).
    pending = []
    last_rendered = None
    for b in blocks:
        if b.get("type") in RENDERED_BLOCKS:
            if pending:
                b["segments"][0:0] = pending
                pending = []
            last_rendered = b
        elif b.get("segments"):
            moved = [seg for seg in b["segments"] if seg.get("kind") == "lacuna"]
            if moved:
                b["segments"] = [seg for seg in b["segments"] if seg.get("kind") != "lacuna"]
                pending.extend(moved)
    if pending and last_rendered is not None:
        last_rendered["segments"].extend(pending)

    # Élimine les blocs ne contenant que du blanc / un marqueur de page isolé
    # sans texte utile ; les divisions et les cellules (vides comprises) restent.
    cleaned = []
    for b in blocks:
        if b.get("type") in ("div", "cell") or any(seg.get("kind") != "text" or seg.get("text", "").strip()
                                                    for seg in b["segments"]):
            cleaned.append(b)
    document = {"blocks": cleaned, "annotations": annotations, "missing_readings": state["missing_count"]}
    # Langue du texte (césure, lecteurs d'écran) : @xml:lang du <text>, sinon de la racine.
    lang = next((value for value in [text.attrib.get(XML_LANG) for text in texts] + [root.attrib.get(XML_LANG)]
                 if value and value.strip()), None)
    if lang:
        document["lang"] = lang.strip()
    return document

# =============================================================================
# Construction des données du viewer
# =============================================================================


def attach_variant_metadata_to_runs(line, global_variant_registry):
    """S'assure que les apps franchissant un lb restent cliquables sur la ligne suivante."""
    line_ann = {a["id"]: a for a in line.get("annotations", [])}
    for r in line.get("runs", []):
        if r.get("type") == "variant" and r.get("ann_id"):
            aid = r["ann_id"]
            if aid in line_ann:
                global_variant_registry[aid] = line_ann[aid]
            elif aid in global_variant_registry:
                line.setdefault("annotations", []).append(global_variant_registry[aid])


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
