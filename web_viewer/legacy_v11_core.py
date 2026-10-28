# -*- coding: utf-8 -*-
"""
Générateur Spyder : édition TEI + images de Troyes 816, Troyes 1760 et Paris BnF Latin 15940 -> visualiseur HTML autonome.

V11 : interface lecteur compacte, largeur du panneau images redimensionnable, métadonnées secondaires dans des fenêtres « … », taille du texte réglable.

T1 (Troyes 816) reste le témoin de base : son alignement TEI -> HTR -> ALTO est celui déjà vérifié.
T2 (Troyes 1760) et P (Paris BnF Latin 15940) sont ajoutés comme témoins visuels secondaires : ses TextLine ALTO sont alignées de façon
semi-automatique sur la lecture #Troyes1760 reconstruite depuis l'apparat TEI (avec repli sur Troyes 816
lorsque le relevé de variantes est absent).

MODE D'EMPLOI (Spyder)
----------------------
1. Ouvrir ce fichier dans Spyder.
2. Modifier au besoin les chemins dans la section CONFIGURATION ci-dessous.
   Si un fichier n'est pas trouvé, une boîte de dialogue vous permettra de le choisir.
3. Appuyer sur F5.
4. Le script crée « visualiseur_tei_alto.html » (ou le nom défini dans OUTPUT_HTML).
5. Ouvrir ce fichier HTML dans Firefox/Chrome/Edge.

Le HTML contient :
- la transcription TEI en lecture continue, structurée par paragraphes ;
- les <lb> utilisés comme ancres invisibles vers les images ;
- l'alignement transcription corrigée -> HTR -> ligne ALTO ;
- les coordonnées ALTO ;
- les informations IIIF du manifeste ;
- les variantes <app>/<lem>/<rdg> et les <note> éditoriales de la TEI corrigée ;
- les <ref> d'identification des citations rendus comme ajouts éditoriaux entre chevrons ;
- une séparation visible et un titre pour chaque <div xml:id="…"> de sermon ;
- pour chaque manuscrit, un viewer de trois lignes physiques (précédente, courante, suivante) ;
- les cadres de référence/correspondance sont désactivés par défaut et activables séparément dans chaque viewer ;
- un bouton « Page ↗ » ouvre dans un nouvel onglet la page IIIF entière contenant la ligne centrale de chaque viewer ;
- navigation ligne par ligne : la fenêtre de trois lignes se décale d’une seule ligne à chaque clic ;
- zoom par boutons/molette et déplacement à la souris pour Troyes 816, Troyes 1760 et BnF Latin 15940.
- largeur du panneau des manuscrits réglable par glisser-déposer (double-clic sur la poignée pour revenir à la largeur initiale) ;
- affichage compact des trois viewers ; les métadonnées HTR/ALTO et notes d’alignement sont accessibles via le bouton « … » ;
- taille du texte de l’édition réglable entre 75 % et 160 %, avec remise à 100 % ;

AUCUNE dépendance externe.
Ce script N'UTILISE NI lxml NI rapidfuzz : le XML est lu avec xml.etree.ElementTree
et les alignements déjà calculés sont lus depuis deux fichiers JSON de cache.

Cette version est destinée aux relectures : elle régénère rapidement le HTML après des
modifications éditoriales dans la TEI, tant que les <lb edRef="#T1"/> restent stables.
"""

from __future__ import annotations

import html
import json
import math
import re
import sys
import unicodedata
import zipfile
import tarfile
from collections import OrderedDict
from web_viewer.tei_line_anchors import build_pivot_lb_index
from pathlib import Path
import xml.etree.ElementTree as ET

Levenshtein = None
rapid_ratio = None


# =============================================================================
# CONFIGURATION — à modifier si nécessaire
# =============================================================================

HERE = Path(__file__).resolve().parent if "__file__" in globals() else Path.cwd()

# Vous pouvez mettre des chemins absolus, p. ex. r"C:\\Users\\Moi\\Documents\\JdlR-quotes.xml"
TEI_CORRIGEE = HERE / "JdlR-quotes_T1_T2_P_lb.xml"
TEI_HTR = HERE / "https___data_biblissima_fr_entity_Q412957(1).xml"
ALTO_ZIP = HERE / "f271-f-266v-267(1).zip"
MANIFEST_IIIF = HERE / "manifest-Troyes-816.json"

# Second témoin : ALTO de la numérisation couleur (pages simples) + manifeste Gallica.
ALTO_TROYES1760 = HERE / "mediatheque-de-troyes-champagne-metropole-ms-1760.tar.gz"
MANIFEST_TROYES1760 = HERE / "manifest-Troyes-1760.json"
TROYES1760_START_FOLIO = "240r"

# Alignements pré-calculés : c'est ce qui rend cette version très rapide.
ALIGNEMENT_816_CACHE = HERE / "alignement_T1_precalcule.json"
ALIGNEMENT_1760_CACHE = HERE / "alignement_T2_precalcule.json"
ALIGNEMENT_BNF_CACHE = HERE / "alignement_P_precalcule.json"

OUTPUT_HTML = HERE / "visualiseur_web_T1_T2_P.html"

# Témoin de base, seul utilisé pour structurer la lecture et sélectionner une ligne.
TARGET_WITNESS = "#T1"
SECONDARY_WITNESS = "#T2"

# Si True, une boîte de dialogue s'ouvre lorsqu'un fichier configuré est introuvable.
UTILISER_BOITES_DE_DIALOGUE = True

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


def normalize(s: str) -> str:
    """Normalisation légère pour comparer HTR et transcription corrigée."""
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    # Les caractères d'abréviation/signes médiévaux disparaissent ici ; on compare la charpente alphabétique.
    return re.sub(r"[^0-9a-z]+", "", s)


def bigrams(s: str):
    s = normalize(s)
    if len(s) < 2:
        return {s} if s else set()
    return {s[i : i + 2] for i in range(len(s) - 1)}


def similarity(a: str, b: str) -> float:
    """Coefficient de Dice sur bigrammes, volontairement sans dépendance externe."""
    A, B = bigrams(a), bigrams(b)
    if not A and not B:
        return 1.0
    if not A or not B:
        return 0.0
    return 2.0 * len(A & B) / (len(A) + len(B))


def wit_tokens(value: str | None):
    if not value:
        return []
    return [x.lstrip("#") for x in value.split() if x.strip()]


def witness_matches(value: str | None, target: str) -> bool:
    return target.lstrip("#") in wit_tokens(value)


def choose_file(path: Path, title: str, filetypes):
    """Retourne path s'il existe, sinon ouvre éventuellement un sélecteur."""
    path = Path(path)
    if path.exists():
        return path
    if not UTILISER_BOITES_DE_DIALOGUE:
        raise FileNotFoundError(f"Fichier introuvable : {path}")
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        chosen = filedialog.askopenfilename(title=title, filetypes=filetypes)
        root.destroy()
        if chosen:
            return Path(chosen)
    except Exception as exc:
        print(f"Boîte de dialogue indisponible ({exc}).")
    raise FileNotFoundError(f"Fichier introuvable : {path}")


def choose_output(path: Path):
    path = Path(path)
    parent = path.parent
    if parent.exists():
        return path
    return Path.cwd() / path.name


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
            # le remplace s'il est seul.
            siglum = ""
            parts = [wit.text or ""]
            for child in wit:
                if lname(child.tag) == "idno" and child.attrib.get("type") == "siglum":
                    siglum = siglum or clean_text("".join(child.itertext()))
                else:
                    parts.append("".join(child.itertext()))
                parts.append(child.tail or "")
            labels[wid] = clean_text("".join(parts)) or siglum or wid
    return labels


READING_TAGS = ("lem", "rdg", "wit")
# Forme montrée d'un <choice>, comme « Édition critique » : la première
# présente dans cet ordre, sinon le premier enfant.
CHOICE_ORDER = ("corr", "reg", "expan", "sic", "orig", "abbr")


def app_readings(app: ET.Element):
    """Leçons d'un ``<app>`` dans l'ordre : ``<lem>``, ``<rdg>`` (et la
    coquille ``<wit>``), celles d'un ``<rdgGrp>`` comprises."""
    found = []
    for child in app:
        tag = lname(child.tag)
        if tag in READING_TAGS:
            found.append(child)
        elif tag == "rdgGrp":
            found.extend(app_readings(child))
    return found


def choose_reading(app: ET.Element, target: str):
    """Leçon du témoin ``target``, sinon le ``<lem>``, sinon la première."""
    readings = app_readings(app)
    for reading in readings:
        if witness_matches(reading.attrib.get("wit"), target):
            return reading
    lem = next((reading for reading in readings if lname(reading.tag) == "lem"), None)
    return lem if lem is not None else (readings[0] if readings else None)


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
# Lecture TEI HTR
# =============================================================================


def extract_htr_pages(path: Path):
    tree = ET.parse(path)
    root = tree.getroot()
    body = next((e for e in root.iter() if lname(e.tag) == "body"), None)
    if body is None:
        raise ValueError(f"Aucun <body> TEI trouvé dans {path}")

    pages = OrderedDict()
    page = None
    current = None

    def walk(node):
        nonlocal page, current
        tag = lname(node.tag)
        if tag in {"teiHeader", "note", "fw"}:
            return
        if tag == "pb":
            page = node.attrib.get("n")
            if page:
                pages.setdefault(page, [])
            current = None
            return
        if tag == "lb":
            if not page:
                return
            current = {"text": "", "attrs": dict(node.attrib)}
            pages[page].append(current)
            return
        if node.text and current is not None:
            current["text"] += node.text
        for ch in list(node):
            walk(ch)
            if ch.tail and current is not None:
                current["text"] += ch.tail

    walk(body)
    for lines in pages.values():
        for line in lines:
            line["text"] = clean_text(line["text"])
    return pages


# =============================================================================
# ALTO
# =============================================================================


def parse_alto(xml_bytes: bytes):
    root = ET.fromstring(xml_bytes)
    page_el = next((e for e in root.iter() if lname(e.tag) == "Page"), None)
    file_el = next((e for e in root.iter() if lname(e.tag) == "fileName"), None)
    page_w = int(float(page_el.attrib.get("WIDTH", 0))) if page_el is not None else 0
    page_h = int(float(page_el.attrib.get("HEIGHT", 0))) if page_el is not None else 0
    image_name = clean_text(file_el.text) if file_el is not None else ""
    lines = []
    for tl in (e for e in root.iter() if lname(e.tag) == "TextLine"):
        strings = [s.attrib.get("CONTENT", "") for s in tl.iter() if lname(s.tag) == "String"]
        bbox = {k.lower(): int(float(tl.attrib.get(k, 0))) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")}
        lines.append(
            {
                "id": tl.attrib.get("ID", ""),
                "text": clean_text(" ".join(strings)),
                "bbox": bbox,
                "baseline": tl.attrib.get("BASELINE", ""),
            }
        )
    return {"width": page_w, "height": page_h, "image": image_name, "lines": lines}


# =============================================================================
# Alignements
# =============================================================================


def align_monotonic(src, dst, skip_dst=0.08, skip_src=0.55):
    """Alignement global monotone. Chaque ligne source peut être alignée sur une ligne destination."""
    n, m = len(src), len(dst)
    if n == 0:
        return []
    if m == 0:
        return [None] * n
    sims = [[similarity(src[i], dst[j]) for j in range(m)] for i in range(n)]
    prev = [0.0] * (m + 1)  # lignes destination en tête gratuites
    bt = [[0] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        cur = [-i * skip_src] + [0.0] * m
        for j in range(1, m + 1):
            opts = (
                prev[j - 1] + sims[i - 1][j - 1] - 0.20,
                cur[j - 1] - skip_dst,
                prev[j] - skip_src,
            )
            k = max(range(3), key=opts.__getitem__)
            cur[j] = opts[k]
            bt[i][j] = k
        prev = cur
    j = max(range(m + 1), key=prev.__getitem__)
    i = n
    mapping = [None] * n
    while i > 0:
        k = bt[i][j]
        if k == 0 and j > 0:
            mapping[i - 1] = (j - 1, sims[i - 1][j - 1])
            i -= 1
            j -= 1
        elif k == 1 and j > 0:
            j -= 1
        else:
            i -= 1
    return mapping


def align_htr_to_alto(htr_lines, alto_lines):
    """HTR et ALTO proviennent du même résultat : exact séquentiel, puis fuzzy de secours."""
    mapping = [None] * len(htr_lines)
    j = 0
    for i, h in enumerate(htr_lines):
        nh = normalize(h["text"])
        found = None
        for k in range(j, len(alto_lines)):
            if normalize(alto_lines[k]["text"]) == nh:
                found = k
                break
        if found is not None:
            mapping[i] = (found, 1.0)
            j = found + 1
        else:
            suffix = align_monotonic(
                [x["text"] for x in htr_lines[i:]],
                [x["text"] for x in alto_lines[j:]],
                skip_dst=0.05,
                skip_src=0.80,
            )
            for off, item in enumerate(suffix):
                if item is not None:
                    mapping[i + off] = (j + item[0], item[1])
            break
    return mapping


# =============================================================================
# Manifeste IIIF
# =============================================================================


def label_to_string(label):
    if isinstance(label, str):
        return label
    if isinstance(label, dict):
        # IIIF v3 language map
        vals = []
        for v in label.values():
            if isinstance(v, list):
                vals.extend(str(x) for x in v)
            else:
                vals.append(str(v))
        return " / ".join(vals)
    return str(label or "")


def parse_manifest(path: Path):
    manifest = json.loads(path.read_text(encoding="utf-8"))
    canvases = []

    # IIIF Presentation 2
    if manifest.get("sequences"):
        for seq in manifest.get("sequences", []):
            for c in seq.get("canvases", []):
                resource = None
                imgs = c.get("images") or []
                if imgs:
                    resource = imgs[0].get("resource") or {}
                resource = resource or {}
                service = resource.get("service") or {}
                if isinstance(service, list):
                    service = service[0] if service else {}
                sid = service.get("@id") or service.get("id") or ""
                profile = service.get("profile", "")
                svc_context = service.get("@context") or service.get("context") or ""
                context_text = " ".join(svc_context) if isinstance(svc_context, list) else str(svc_context)
                profile_text = " ".join(profile) if isinstance(profile, list) else str(profile)
                if "/image/1/" in context_text or "image-api/1." in profile_text:
                    image_version = 1
                elif "/image/3/" in context_text or "image/3" in profile_text:
                    image_version = 3
                else:
                    image_version = 2 if sid else None
                canvases.append(
                    {
                        "id": c.get("@id") or c.get("id") or "",
                        "label": label_to_string(c.get("label")),
                        "width": int(c.get("width") or resource.get("width") or 0),
                        "height": int(c.get("height") or resource.get("height") or 0),
                        "image": resource.get("@id") or resource.get("id") or "",
                        "service": sid,
                        "iiif_version": image_version,
                        "profile": profile,
                    }
                )

    # IIIF Presentation 3
    elif manifest.get("items"):
        for c in manifest.get("items", []):
            body = {}
            try:
                body = c["items"][0]["items"][0]["body"]
            except Exception:
                pass
            service = body.get("service") or []
            if isinstance(service, dict):
                service = [service]
            svc = service[0] if service else {}
            sid = svc.get("id") or svc.get("@id") or ""
            canvases.append(
                {
                    "id": c.get("id") or c.get("@id") or "",
                    "label": label_to_string(c.get("label")),
                    "width": int(c.get("width") or body.get("width") or 0),
                    "height": int(c.get("height") or body.get("height") or 0),
                    "image": body.get("id") or body.get("@id") or "",
                    "service": sid,
                    "iiif_version": 3 if sid else None,
                    "profile": svc.get("profile", ""),
                }
            )

    if not canvases:
        raise ValueError("Aucun canvas IIIF trouvé dans le manifeste.")
    return manifest, canvases


def folio_tokens(s: str):
    s = (s or "").lower()
    return re.findall(r"\d+[rv]?", s)


def normalize_label(s: str):
    s = unicodedata.normalize("NFKD", s or "").lower()
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s)


def match_canvas(page_id: str, image_name: str, canvases):
    """Associe un <pb n='f271-f-266v-267'> au canvas « f. 266v - 267 »."""
    pid = page_id.lower()
    suffix = re.sub(r"^f\d+-", "", pid)
    ptoks = folio_tokens(suffix)
    pnorm = normalize_label(suffix)
    stem = normalize_label(Path(image_name or "").stem)
    best = None
    for idx, c in enumerate(canvases):
        hay = " ".join([c.get("label", ""), c.get("id", ""), c.get("image", ""), c.get("service", "")])
        hnorm = normalize_label(hay)
        ctoks = folio_tokens(c.get("label", ""))
        score = 0
        if pnorm and pnorm in hnorm:
            score += 1000
        if stem and stem in hnorm:
            score += 900
        if ptoks:
            # correspondance exacte de la séquence des folios = signal principal
            if ctoks[: len(ptoks)] == ptoks:
                score += 850
            score += 120 * sum(1 for t in ptoks if t in ctoks)
        # l'index numérique « f271 » correspond aussi à la position numérisée dans ce corpus,
        # mais on ne l'utilise qu'en signal faible.
        digital = re.match(r"^f(\d+)", pid)
        if digital and int(digital.group(1)) == idx:
            score += 30
        if best is None or score > best[0]:
            best = (score, c)
    if best and best[0] >= 200:
        return best[1], best[0]
    return None, 0




# =============================================================================
# Alignement auxiliaire du témoin Troyes 1760 sur les ALTO couleur
# =============================================================================

MEDIEVAL_EXPANSIONS = {
    "⁊": "et", "ꝑ": "per", "ꝓ": "pro", "ꝙ": "quod", "ꝗ": "qui",
    "ꝯ": "con", "ꝵ": "rum", "ꝰ": "us", "÷": "est", "ł": "l",
    "ħ": "h", "ẜ": "s", "ꝛ": "r", "ꝭ": "is", "ꝫ": "et",
    "Ꝓ": "pro", "Ꝑ": "per", "Ꝙ": "quod", "Ꝝ": "rum", "ꝝ": "rum",
    "ꝟ": "u", "Ꝟ": "u", "ꝧ": "d", "ꝺ": "d", "Ꝺ": "d",
    "Ꝼ": "f", "ꞇ": "t", "ꝥ": "p",
}


def normalize_medieval_piece(ch: str, htr=False) -> str:
    s = MEDIEVAL_EXPANSIONS.get(ch, ch) if htr else ch
    s = unicodedata.normalize("NFKD", (s or "").lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    # Neutralisation classique des couples u/v et i/j pour l'alignement.
    s = s.replace("v", "u").replace("j", "i")
    return "".join(c for c in s if "a" <= c <= "z")


def normalize_medieval(s: str, htr=False) -> str:
    return "".join(normalize_medieval_piece(ch, htr=htr) for ch in (s or ""))


def witness_matches_loose(value: str | None, target: str) -> bool:
    """Tolère #Troyes1760, Troyes1760, #1760 et quelques espaces parasites."""
    raw = re.sub(r"[^a-z0-9]+", "", (value or "").lower())
    tgt = re.sub(r"[^a-z0-9]+", "", target.lstrip("#").lower())
    if not raw or not tgt:
        return False
    if tgt in raw:
        return True
    m = re.search(r"(\d+)$", tgt)
    return bool(m and raw in {m.group(1), "troyes" + m.group(1)})


def choose_parallel_reading(node: ET.Element, target: str):
    choices = [c for c in list(node) if lname(c.tag) in {"lem", "rdg", "wit"}]
    for c in choices:
        if witness_matches_loose(c.attrib.get("wit"), target):
            return c
    # Après la fin du relevé des variantes, le texte de base sert de proxy pour 1760.
    if target.lstrip("#") == "Troyes1760":
        for c in choices:
            if witness_matches_loose(c.attrib.get("wit"), "#Troyes816"):
                return c
    lem = next((c for c in choices if lname(c.tag) == "lem"), None)
    return lem if lem is not None else (choices[0] if choices else None)


def build_parallel_witness_stream(path: Path, target: str):
    """Construit le texte normalisé des sermons RLS_* pour un témoin.

    Pour Troyes 816, on conserve en plus, caractère par caractère, la clé de la
    ligne physique 816 (page::numéro). Cette carte sert ensuite de pont entre
    les lignes ALTO de 1760 et les lignes cliquables du viewer.
    """
    root = ET.parse(path).getroot()
    body = next((e for e in root.iter() if lname(e.tag) == "body"), None)
    if body is None:
        raise ValueError("Aucun <body> TEI trouvé.")

    chars = []
    line_keys = []
    state = {"page": None, "line_index": -1, "line_key": None}

    def emit(text, active):
        if not active or not text:
            return
        for ch in text:
            piece = normalize_medieval_piece(ch, htr=False)
            if not piece:
                continue
            chars.extend(piece)
            line_keys.extend([state["line_key"]] * len(piece))

    def walk(node, active=False):
        tag = lname(node.tag)
        if tag == "div":
            xid = node.attrib.get(XML_ID, "")
            active = active or xid.startswith("RLS_")
        if tag in {"note", "ref"}:
            return
        if tag == "pb":
            state["page"] = node.attrib.get("n")
            state["line_index"] = -1
            state["line_key"] = None
            return
        if tag == "lb":
            # Même convention que la vue principale : les lignes 816 numérotent les ancres.
            edref = node.attrib.get("edRef") or ""
            if state["page"] and (not edref or witness_matches_loose(edref, "#Troyes816")):
                state["line_index"] += 1
                state["line_key"] = f"{state['page']}::{state['line_index'] + 1}"
            return
        if tag == "app":
            selected = choose_parallel_reading(node, target)
            if selected is not None:
                walk(selected, active)
            return

        emit(node.text, active)
        for child in list(node):
            walk(child, active)
            emit(child.tail, active)

    walk(body, False)
    return "".join(chars), line_keys


def project_positions(opcodes, positions, dest_len):
    """Projette une liste croissante de positions source à travers des opcodes Levenshtein."""
    ops = list(opcodes)
    out = []
    j = 0
    for p in positions:
        while j < len(ops) and p > ops[j].src_end:
            j += 1
        if j >= len(ops):
            out.append(dest_len)
            continue
        op = ops[j]
        if p < op.src_start:
            out.append(op.dest_start)
            continue
        ss, se, ds, de = op.src_start, op.src_end, op.dest_start, op.dest_end
        if se == ss:
            q = de
        elif op.tag == "equal":
            q = ds + (p - ss)
        elif op.tag == "delete":
            q = ds
        else:
            q = round(ds + (p - ss) * (de - ds) / (se - ss))
        out.append(max(0, min(dest_len, int(q))))
    return out


def _archive_xml_entries(path: Path):
    """Retourne [(nom, bytes)] pour un ZIP ou TAR(.GZ), triés par index fNNN."""
    path = Path(path)
    records = []
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as zf:
            names = [n for n in zf.namelist() if re.search(r"f\d+-.*\.xml$", Path(n).name, re.I)]
            names.sort(key=lambda n: int(re.match(r"f(\d+)", Path(n).name, re.I).group(1)))
            for n in names:
                records.append((Path(n).name, zf.read(n)))
    else:
        with tarfile.open(path, "r:*") as tf:
            members = [m for m in tf.getmembers() if m.isfile() and re.search(r"f\d+-.*\.xml$", Path(m.name).name, re.I)]
            members.sort(key=lambda m: int(re.match(r"f(\d+)", Path(m.name).name, re.I).group(1)))
            for m in members:
                fh = tf.extractfile(m)
                if fh is not None:
                    records.append((Path(m.name).name, fh.read()))
    return records


def match_single_folio_canvas(page_id: str, canvases):
    folio = re.sub(r"^f\d+-", "", page_id.lower())
    fnorm = normalize_label(folio)
    exact = [c for c in canvases if normalize_label(c.get("label", "")) == fnorm]
    if exact:
        return exact[0], 1000
    # repli : le folio doit être un token entier du label
    ftoks = folio_tokens(folio)
    best = None
    for c in canvases:
        ctoks = folio_tokens(c.get("label", ""))
        score = 500 if ftoks and ctoks == ftoks else 100 * sum(t in ctoks for t in ftoks)
        if best is None or score > best[0]:
            best = (score, c)
    return (best[1], best[0]) if best and best[0] >= 400 else (None, 0)


def build_secondary_alignment(corrected: Path, alto_archive: Path, manifest_path: Path,
                              target="#Troyes1760", start_folio="240r", valid_816_keys=None):
    if Levenshtein is None or rapid_ratio is None:
        raise RuntimeError(
            "L'alignement de Troyes 1760 nécessite 'rapidfuzz'. "
            "Installez-le dans l'environnement Python de Spyder avec : pip install rapidfuzz "
            "(ou conda install -c conda-forge rapidfuzz)."
        )

    text1760, _ = build_parallel_witness_stream(corrected, target)
    text816, key816 = build_parallel_witness_stream(corrected, "#Troyes816")
    if not text1760 or not text816:
        raise ValueError("Impossible de reconstruire les textes parallèles dans la TEI.")

    manifest, canvases = parse_manifest(manifest_path)
    entries = _archive_xml_entries(alto_archive)
    start_idx = None
    target_suffix = "-" + start_folio.lower() + ".xml"
    for i, (name, _) in enumerate(entries):
        if name.lower().endswith(target_suffix):
            start_idx = i
            break
    if start_idx is None:
        raise ValueError(f"Aucun ALTO correspondant au folio initial {start_folio}.")

    pages = []
    flat = []
    for name, payload in entries[start_idx:]:
        page_id = Path(name).stem
        alto = parse_alto(payload)
        canvas, canvas_score = match_single_folio_canvas(page_id, canvases)
        page = {
            "id": page_id,
            "image_name": alto["image"],
            "alto_width": alto["width"],
            "alto_height": alto["height"],
            "iiif": canvas,
            "iiif_match_score": canvas_score,
            "lines": [],
        }
        for li, line in enumerate(alto["lines"], start=1):
            rec = {
                "page": page_id,
                "page_obj": page,
                "line": li,
                "alto": line["text"],
                "norm": normalize_medieval(line["text"], htr=True),
                "bbox": line["bbox"],
                "alto_id": line["id"],
            }
            flat.append(rec)
        pages.append(page)

    if not flat:
        raise ValueError("Aucune ligne ALTO trouvée pour Troyes 1760.")

    # Détection automatique de la fin de la série RLS_* dans l'ALTO.
    # On compare la fin de la lecture reconstruite à des fenêtres de 7 lignes ALTO.
    probe = text1760[-240:-20] if len(text1760) > 300 else text1760[-200:]
    best_score, best_i = -1.0, len(flat) - 1
    for i in range(len(flat)):
        window = "".join(x["norm"] for x in flat[i:i + 7])
        if not window:
            continue
        sc = rapid_ratio(window, probe)
        if sc > best_score:
            best_score, best_i = sc, i
    flat = flat[: min(len(flat), best_i + 10)]

    htr = ""
    bounds = [0]
    for rec in flat:
        htr += rec["norm"]
        bounds.append(len(htr))

    # 1) HTR 1760 -> lecture 1760 reconstruite ; 2) lecture 1760 -> texte 816.
    ops_htr = Levenshtein.opcodes(htr, text1760)
    target_bounds = project_positions(ops_htr, bounds, len(text1760))
    unique_target_bounds = sorted(set(target_bounds))
    ops_witnesses = Levenshtein.opcodes(text1760, text816)
    projected_816 = project_positions(ops_witnesses, unique_target_bounds, len(text816))
    to816 = dict(zip(unique_target_bounds, projected_816))

    page_lookup = {p["id"]: p for p in pages}
    mapped_count = 0
    scores = []
    low_count = 0
    keys_seen = set()

    for i, rec in enumerate(flat):
        a, b = target_bounds[i], target_bounds[i + 1]
        if b < a:
            b = a
        target_seg = text1760[a:b]
        score100 = rapid_ratio(rec["norm"], target_seg) if (rec["norm"] or target_seg) else 100.0
        score = score100 / 100.0
        scores.append(score)
        if score < 0.50:
            low_count += 1

        ua, ub = to816[a], to816[b]
        if ub < ua:
            ub = ua
        keys = []
        seen = set()
        lo = max(0, ua)
        hi = min(len(key816), max(ub, ua + 1))
        for k in key816[lo:hi]:
            if k and k not in seen:
                seen.add(k)
                keys.append(k)
        if not keys:
            # Cas de frontière exacte : recherche du premier caractère voisin rattaché à une ligne 816.
            for delta in range(0, 120):
                hit = None
                for pos in (ua - delta, ua + delta):
                    if 0 <= pos < len(key816) and key816[pos]:
                        hit = key816[pos]
                        break
                if hit:
                    keys = [hit]
                    break

        if valid_816_keys is not None:
            keys = [k for k in keys if k in valid_816_keys]

        # Élimine quelques numéros de folio / artefacts très courts sans supprimer les vraies lignes faibles.
        if len(rec["norm"]) < 3 and score < 0.35:
            keys = []

        if not keys:
            continue

        out = {
            "line": rec["line"],
            "alto": rec["alto"],
            "score": round(score, 4),
            "bbox": rec["bbox"],
            "alto_id": rec["alto_id"],
            "keys816": keys,
            "order": i + 1,
        }
        page_lookup[rec["page"]]["lines"].append(out)
        mapped_count += 1
        keys_seen.update(keys)

    used_pages = [p for p in pages if p["lines"]]
    mean_score = sum(scores) / len(scores) if scores else 0.0
    return {
        "meta": {
            "label": label_to_string(manifest.get("label")) or "Troyes 1760",
            "target_witness": target.lstrip("#"),
            "start_folio": start_folio,
            "end_page": used_pages[-1]["id"] if used_pages else "",
            "pages": len(used_pages),
            "lines": mapped_count,
            "mapped_816_lines": len(keys_seen),
            "mean_score": round(mean_score, 4),
            "low_under_50": low_count,
            "end_probe_score": round(best_score / 100.0, 4),
            "source_alto": Path(alto_archive).name,
            "source_manifest": Path(manifest_path).name,
            "status": "proposed",
        },
        "pages": used_pages,
    }

# =============================================================================
# Vue de lecture continue de la TEI corrigée
# =============================================================================

def extract_reading_document(path: Path, target: str, include_foreign_pagebreaks: bool = False, page_resolver=None, base_line_keys=None, *,
                             root=None, line_anchors=None, segment_of=None, target_of=None, pb_line_keys=False):
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
        return choose_reading(node, target_of(node))

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
            if edref and not witness_matches(edref, target_of(node)):
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
            if edref and not witness_matches(edref, target_of(node)):
                # Les <lb> de l'autre témoin sont des ancres invisibles et ne
                # doivent surtout pas casser la lecture continue de Troyes 816.
                return
            if lb_anchor_lookup is not None:
                state["line_key"] = lb_anchor_lookup.get(id(node))
            elif state["page"]:
                state["line_index"] += 1
                if page_resolver is not None:
                    state["line_counts_by_physical_page"][state["page"]] = state["line_index"]
                state["line_key"] = f"{state['page']}::{state['line_index'] + 1}"
            trim_last_visible_right()
            state["pending_lb_sep"] = "\u2060" if node.attrib.get("break") == "no" else " "
            return
        if tag in LACUNA_TAGS:
            add_lacuna(node)
            return
        if tag == "note":
            add_lacunae_in(node)
            enter(node)
            txt = flatten_editorial_text(node, include_notes=True, include_refs=True)
            if txt:
                aid = new_ann_id("n")
                annotations[aid] = {
                    "id": aid, "kind": "note", "text": txt,
                    "type": node.attrib.get("type", ""),
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
            selected = choose_app_reading(node)
            if selected is None:
                return
            aid = new_ann_id("v")
            ann = {
                "id": aid, "kind": "variant",
                "selected": flatten_editorial_text(selected, include_notes=False, include_refs=False),
                "target": target_of(node).lstrip("#"), "readings": describe_app(node),
            }
            annotations[aid] = ann

            def readings_of(container):
                # Dans l'ordre : la leçon retenue, les repères de lacune des autres.
                for other in list(container):
                    if other is selected:
                        walk(selected, styles=styles, variant_id=aid, alt=alt)
                    elif lname(other.tag) == "rdgGrp" and any(x is selected for x in other.iter()):
                        readings_of(other)
                    else:
                        add_lacunae_in(other)

            readings_of(node)
            enter(node)
            add_marker("variant-marker", aid, variant_tooltip(ann, witness_labels))
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
        selected = choose_app_reading(node)
        if selected is None:
            return
        aid = new_ann_id("v")
        ann = {
            "id": aid, "kind": "variant",
            "selected": flatten_editorial_text(selected, include_notes=False, include_refs=False),
            "target": target_of(node).lstrip("#"), "readings": describe_app(node),
        }
        annotations[aid] = ann
        for other in app_readings(node):
            if other is not selected:
                add_lacunae_in(other)
        walk_children(selected, level)
        enter(node)
        add_marker("variant-marker", aid, variant_tooltip(ann, witness_labels))

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
    document = {"blocks": cleaned, "annotations": annotations}
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


def build_dataset_fast(corrected: Path, cache816_path: Path, cache1760_path: Path, cachebnf_path: Path, target: str):
    """Construit le viewer sans recalculer aucun alignement HTR/ALTO.

    Le cache 816 contient les correspondances déjà vérifiées page/ligne -> ALTO/IIIF.
    Le cache 1760 contient les correspondances proposées calculées une fois pour toutes.
    La TEI est relue à chaque lancement afin que les corrections de texte, variantes,
    notes, italiques et identifications éditoriales apparaissent immédiatement.
    """
    corr_pages, witness_labels = extract_corrected_pages(corrected, target)
    reading_document = extract_reading_document(corrected, target)
    cache816 = load_json(cache816_path)
    secondary = load_json(cache1760_path)
    third = load_json(cachebnf_path)

    pages_out = []
    total_lines = 0
    variant_registry = {}
    missing = []

    cached_pages = {p["id"]: p for p in cache816.get("pages", [])}
    for page_name, corr_lines in corr_pages.items():
        cp = cached_pages.get(page_name)
        if not cp:
            missing.append(page_name)
            continue
        by_line = {int(l.get("line", i + 1)): l for i, l in enumerate(cp.get("lines", []))}
        out_lines = []
        for ci, c in enumerate(corr_lines, start=1):
            base = by_line.get(ci)
            if base is None:
                continue
            attach_variant_metadata_to_runs(c, variant_registry)
            anns = c.get("annotations", [])
            seen = set(); dedup_anns = []
            for ann in anns:
                if ann["id"] not in seen:
                    seen.add(ann["id"]); dedup_anns.append(ann)
            line_out = dict(base)
            # Le cache ne décide jamais du texte éditorial : celui-ci vient de la TEI actuelle.
            line_out["line"] = ci
            line_out["corrected"] = c["text"]
            line_out["runs"] = c["runs"]
            line_out["annotations"] = dedup_anns
            line_out["break_no"] = c.get("break_no", False)
            out_lines.append(line_out)
        if not out_lines:
            continue
        po = dict(cp)
        po["lines"] = out_lines
        pages_out.append(po)
        total_lines += len(out_lines)

    unique_var = set(); unique_notes = set()
    for p in pages_out:
        for line in p["lines"]:
            for ann in line.get("annotations", []):
                if ann.get("kind") == "variant": unique_var.add(ann["id"])
                elif ann.get("kind") == "note": unique_notes.add(ann["id"])

    meta0 = cache816.get("meta", {})
    data = {
        "meta": {
            "title": "Visualiseur TEI – ALTO – IIIF",
            "target_witness": target.lstrip("#"),
            "pages": len(pages_out),
            "lines": total_lines,
            "variants": len(unique_var),
            "notes": len(unique_notes),
            "manifest_label": meta0.get("manifest_label", ""),
            "source_corrected": corrected.name,
            "source_htr": meta0.get("source_htr", "alignement pré-calculé"),
            "source_alto": meta0.get("source_alto", "alignement pré-calculé"),
            "source_manifest": meta0.get("source_manifest", "alignement pré-calculé"),
            "generator_mode": "cache rapide · viewer web V10 · sommaire",
        },
        "witnesses": witness_labels,
        "document": reading_document,
        "pages": pages_out,
        "troyes1760": secondary,
        "bnflat15940": third,
    }
    return data, missing


# =============================================================================
# HTML autonome
# =============================================================================

HTML_TEMPLATE = r'''<!doctype html>
<html lang="fr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Édition TEI — T1 / T2 / P</title>
<style>
:root{--paper:#fbfaf6;--bg:#eeeae3;--ink:#28231e;--muted:#746b61;--line:#d8d0c5;--accent:#684786;--note:#a55531;--sel:#fff0b8;--panel:#fffdf9;--shadow:0 10px 28px rgba(55,42,28,.12);--side-width:430px;--reader-scale:1}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--bg);color:var(--ink);font-family:system-ui,-apple-system,"Segoe UI",sans-serif}
header{position:sticky;top:0;z-index:30;background:rgba(251,250,246,.96);backdrop-filter:blur(6px);border-bottom:1px solid var(--line);padding:12px 22px}.header-row{display:flex;align-items:center;gap:16px;justify-content:space-between;flex-wrap:wrap}.brand h1{font:600 22px/1.1 Georgia,serif;margin:0}.brand .sub{font-size:12px;color:var(--muted);margin-top:4px}.controls{display:flex;gap:8px;align-items:center;flex-wrap:wrap}.controls select,.controls input[type=search],.controls button{border:1px solid var(--line);background:white;border-radius:8px;padding:7px 9px;color:inherit}.controls input[type=search]{width:190px}.toggle{font-size:12px;color:var(--muted);display:inline-flex;gap:5px;align-items:center}
.layout{max-width:1800px;margin:auto;display:grid;grid-template-columns:minmax(0,1fr) 8px minmax(300px,var(--side-width));gap:8px;padding:18px 22px;align-items:start}.reader{background:var(--paper);border:1px solid var(--line);border-radius:14px;box-shadow:var(--shadow);padding:46px clamp(28px,6vw,78px);min-height:calc(100vh - 110px)}.reader-inner{max-width:850px;margin:0 auto}.doc-title{font:600 calc(27px * var(--reader-scale))/1.25 Georgia,serif;margin:0 0 32px;text-align:center}.toc{margin:0 0 34px;padding:14px 16px;border:1px solid var(--line);border-radius:10px;background:#f5f0e8}.toc-title{font:700 11px/1.2 system-ui;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-bottom:9px}.toc-list{display:flex;flex-wrap:wrap;gap:5px 12px}.toc a{font:600 12px/1.4 system-ui;color:var(--accent);text-decoration:none;white-space:nowrap}.toc a:hover{text-decoration:underline}.tei-p{font:calc(18px * var(--reader-scale))/1.72 Georgia,"Times New Roman",serif;margin:0 0 1.15em;text-align:justify;hyphens:auto}.tei-head{font:600 calc(21px * var(--reader-scale))/1.45 Georgia,serif;margin:1.8em 0 .8em}.tei-item{font:calc(18px * var(--reader-scale))/1.68 Georgia,serif;margin:.35em 0 .35em 1.4em}.tei-item:before{content:"•";margin-left:-1.1em;margin-right:.55em}.sermon-start{margin:3.1em 0 1.55em}.sermon-start:first-child{margin-top:.4em}.sermon-rule{border:0;border-top:2px solid #b9afa3;margin:0 0 .9em}.sermon-id{font:700 calc(24px * var(--reader-scale))/1.2 Georgia,"Times New Roman",serif;letter-spacing:.02em;color:#3d352e}.tei-italic{font-style:italic}.tei-bold{font-weight:700}.tei-smallcaps{font-variant:small-caps}.tei-unclear{text-decoration:underline dotted;text-underline-offset:3px}.tei-sic{text-decoration:underline dashed;text-underline-offset:3px}.editorial-ref{font-size:.84em;color:#746c82;font-style:normal;white-space:nowrap}.line-frag{border-radius:3px;cursor:pointer;transition:background .12s}.line-frag:hover{background:#f1ede6}.line-frag.selected-line{background:var(--sel);box-shadow:0 0 0 2px var(--sel)}.variant-text{box-shadow:inset 0 -2px 0 #cfbfdd}.ann-marker{display:inline-grid;place-items:center;width:17px;height:17px;border:0;border-radius:50%;padding:0;margin-left:2px;vertical-align:super;font:700 9px/1 system-ui;cursor:pointer;color:white}.ann-marker.v{background:var(--accent)}.ann-marker.n{background:var(--note)}.pb{display:inline-block;font:11px/1 system-ui;color:#8b8176;border:1px solid #d7cec1;background:#f0ebe3;border-radius:999px;padding:3px 6px;margin:0 .35em;vertical-align:.15em;white-space:nowrap}.pb.hidden{display:none}
.side{position:sticky;top:82px;display:grid;gap:8px;max-height:calc(100vh - 102px);overflow:auto;scrollbar-gutter:stable}.card{background:var(--panel);border:1px solid var(--line);border-radius:13px;box-shadow:var(--shadow);overflow:hidden}.card-h{display:flex;align-items:center;justify-content:space-between;gap:8px;padding:7px 9px;border-bottom:1px solid var(--line);min-height:34px}.card-h h2{font-size:13px;margin:0}.small{font-size:11px;color:var(--muted)}.image-toolbar{display:flex;align-items:center;gap:4px;padding:4px 6px;border-bottom:1px solid var(--line);background:#faf7f2}.image-toolbar button{width:30px;height:28px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--ink);font:600 15px/1 system-ui;cursor:pointer}.image-toolbar button:hover{background:#f1ece5}.zoom-label{min-width:46px;text-align:center;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.zoom-help{margin-left:auto;font-size:10px;color:var(--muted)}.image-wrap{height:162px;display:block;background:#e8e3db;overflow-y:scroll;overflow-x:hidden;scrollbar-gutter:stable;cursor:grab;overscroll-behavior:contain;contain:layout paint}.image-wrap.dragging{cursor:grabbing;user-select:none}.window-stage{display:block;width:100%;max-width:none;transform-origin:0 0}.window-slice{position:relative;width:100%;line-height:0;background:#e8e3db}.window-slice+.window-slice{border-top:3px solid #c8beb1}.window-slice img{display:block;width:100%;max-width:none;height:auto;user-select:none;-webkit-user-drag:none}.line-highlight{position:absolute;z-index:2;border:2px solid rgba(166,91,36,.9);background:rgba(255,209,126,.12);pointer-events:none;box-shadow:0 0 0 1px rgba(255,255,255,.65) inset}.line-highlight.secondary-match{border-color:rgba(104,71,134,.95);background:rgba(190,164,215,.14)}.window-stage.highlights-off .line-highlight{display:none}.highlight-toggle{width:auto!important;min-width:54px!important;padding:0 8px!important;font-size:10px!important;font-weight:600!important}.highlight-toggle.active{background:#eee5f5!important;border-color:#b9a2ce!important;color:#5c3977!important}.page-open{width:auto!important;min-width:64px!important;padding:0 8px!important;font-size:10px!important;font-weight:600!important}.placeholder{height:100%;display:flex;align-items:center;justify-content:center;padding:28px;color:var(--muted);font-size:12px;text-align:center}.side-body{padding:7px 9px}.selected-text{font:16px/1.5 Georgia,serif;margin-bottom:9px}.navrow{display:flex;gap:6px}.navrow button{flex:1;border:1px solid var(--line);border-radius:7px;background:white;padding:6px;cursor:pointer}.meta{font-size:11px;color:var(--muted);line-height:1.45;margin-top:8px}.ann-list{display:grid;gap:8px}.ann-card{border:1px solid var(--line);border-radius:8px;padding:8px 9px;background:#fff;cursor:pointer}.ann-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.05em;color:var(--muted);margin-bottom:5px}.reading{display:grid;grid-template-columns:100px 1fr;gap:8px;font:13px/1.35 Georgia,serif;padding:4px 0;border-top:1px dotted #ddd}.reading:first-child{border-top:0}.wit{font:10px/1.3 system-ui;color:var(--accent)}details summary{cursor:pointer;font-size:12px;color:var(--muted)}.source{font:11px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;background:#f4f0ea;border-radius:7px;padding:7px;margin-top:7px;overflow-wrap:anywhere}.pop{position:fixed;z-index:100;display:none;width:min(510px,calc(100vw - 24px));max-height:70vh;overflow:auto;background:white;border:1px solid var(--line);border-radius:12px;box-shadow:0 18px 50px rgba(0,0,0,.22)}.pop.show{display:block}.pop-h{display:flex;justify-content:space-between;align-items:center;padding:10px 12px;border-bottom:1px solid var(--line);font-weight:700;font-size:12px}.pop-b{padding:11px 12px}.pop button{border:0;background:transparent;font-size:18px;cursor:pointer}.secondary-stack{display:grid;gap:10px}.secondary-line{border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#fff}.secondary-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:7px 9px;background:#faf7f2;border-bottom:1px solid var(--line);font-size:11px}.secondary-head b{font-size:12px}.secondary-score{font-variant-numeric:tabular-nums;color:var(--muted)}.secondary-score.low{color:#a23d35;font-weight:700}.secondary-toolbar{display:flex;align-items:center;gap:5px;padding:6px 8px;border-bottom:1px solid var(--line);background:#fffdf9}.secondary-toolbar button{min-width:28px;height:27px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--ink);font:600 14px/1 system-ui;cursor:pointer;padding:0 7px}.secondary-toolbar button:hover{background:#f1ece5}.secondary-toolbar button:disabled{opacity:.35;cursor:default}.secondary-toolbar .secondary-nav{font-size:12px;min-width:36px}.secondary-toolbar .secondary-reset-match{margin-left:auto;font-size:11px;min-width:32px}.secondary-zoom-label{min-width:43px;text-align:center;font-size:10px;color:var(--muted);font-variant-numeric:tabular-nums}.secondary-wrap{height:162px;overflow-y:scroll;overflow-x:hidden;scrollbar-gutter:stable;background:#e8e3db;cursor:grab;overscroll-behavior:contain;contain:layout paint}.secondary-wrap.dragging{cursor:grabbing;user-select:none}.secondary-wrap .window-stage{display:block;width:100%;max-width:none}.secondary-wrap .window-slice img{display:block;width:100%;max-width:none;height:auto;user-select:none;-webkit-user-drag:none}.secondary-help{padding:5px 8px;font-size:9px;color:var(--muted);border-top:1px solid var(--line);background:#fcfaf6}.secondary-source{font:10px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;padding:6px 8px;color:#5f574f;background:#f7f3ed;overflow-wrap:anywhere}.secondary-empty{padding:18px 12px;color:var(--muted);font-size:11px;text-align:center}.witness-note{font-size:10px;color:var(--muted);line-height:1.35;margin-top:7px}.third-stack{display:grid;gap:10px}.third-line{border:1px solid var(--line);border-radius:9px;overflow:hidden;background:#fff}.third-head{display:flex;justify-content:space-between;align-items:center;gap:8px;padding:7px 9px;background:#faf7f2;border-bottom:1px solid var(--line);font-size:11px}.third-head b{font-size:12px}.third-score{font-variant-numeric:tabular-nums;color:var(--muted)}.third-score.low{color:#a23d35;font-weight:700}.third-toolbar{display:flex;align-items:center;gap:5px;padding:6px 8px;border-bottom:1px solid var(--line);background:#fffdf9}.third-toolbar button{min-width:28px;height:27px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--ink);font:600 14px/1 system-ui;cursor:pointer;padding:0 7px}.third-toolbar button:hover{background:#f1ece5}.third-toolbar button:disabled{opacity:.35;cursor:default}.third-toolbar .third-nav{font-size:12px;min-width:36px}.third-toolbar .third-reset-match{margin-left:auto;font-size:11px;min-width:32px}.third-zoom-label{min-width:43px;text-align:center;font-size:10px;color:var(--muted);font-variant-numeric:tabular-nums}.third-wrap{height:162px;overflow-y:scroll;overflow-x:hidden;scrollbar-gutter:stable;background:#e8e3db;cursor:grab;overscroll-behavior:contain;contain:layout paint}.third-wrap.dragging{cursor:grabbing;user-select:none}.third-wrap .window-stage{display:block;width:100%;max-width:none}.third-wrap .window-slice img{display:block;width:100%;max-width:none;height:auto;user-select:none;-webkit-user-drag:none}.third-help{padding:5px 8px;font-size:9px;color:var(--muted);border-top:1px solid var(--line);background:#fcfaf6}.third-source{font:10px/1.35 ui-monospace,SFMono-Regular,Menlo,monospace;padding:6px 8px;color:#5f574f;background:#f7f3ed;overflow-wrap:anywhere}.third-empty{padding:18px 12px;color:var(--muted);font-size:11px;text-align:center}.witness-note{font-size:10px;color:var(--muted);line-height:1.35;margin-top:7px}
/* V11 — interface compacte */
#score,#secondaryStatus,#thirdStatus,.side .selected-text,.side .meta,.secondary-head,.third-head,.secondary-help,.third-help,.secondary-line details,.third-line details,.witness-note,.legacy-htr-card{display:none!important}
.navrow{margin-top:5px}.navrow button{padding:4px 6px;font-size:11px}.secondary-line,.third-line{border:0;border-radius:0}.secondary-stack,.third-stack{gap:0}.secondary-toolbar,.third-toolbar{padding:4px 6px}.secondary-toolbar button,.third-toolbar button{height:25px}.card-actions{display:flex;align-items:center;gap:5px}.info-btn{width:27px;height:25px;border:1px solid var(--line);border-radius:7px;background:white;color:var(--muted);font:700 14px/1 system-ui;cursor:pointer}.info-btn:hover{background:#f1ece5;color:var(--ink)}
.column-resizer{position:sticky;top:82px;height:calc(100vh - 102px);cursor:col-resize;border-radius:999px;touch-action:none;display:flex;align-items:center;justify-content:center}.column-resizer:before{content:"";display:block;width:3px;height:68px;border-radius:3px;background:#c7bdb1;transition:background .12s,width .12s}.column-resizer:hover:before,.column-resizer.dragging:before{width:5px;background:var(--accent)}
.font-tools{display:inline-flex;align-items:center;gap:3px;padding-left:5px;border-left:1px solid var(--line)}.font-tools button{min-width:30px!important;padding:6px 7px!important}.font-scale-label{min-width:44px;text-align:center;font-size:11px;color:var(--muted);font-variant-numeric:tabular-nums}.font-tools button:disabled{opacity:.35}
.info-dialog{width:min(650px,calc(100vw - 30px));max-height:min(78vh,760px);padding:0;border:1px solid var(--line);border-radius:13px;box-shadow:0 24px 70px rgba(0,0,0,.28);color:var(--ink);background:var(--panel)}.info-dialog::backdrop{background:rgba(28,24,21,.35)}.info-dialog-h{position:sticky;top:0;background:var(--panel);display:flex;align-items:center;justify-content:space-between;gap:12px;padding:10px 12px;border-bottom:1px solid var(--line);z-index:2}.info-dialog-h strong{font-size:13px}.info-dialog-h button{border:0;background:transparent;font-size:21px;cursor:pointer;color:var(--muted)}.info-dialog-b{padding:12px 14px;overflow:auto}.info-section{margin:0 0 13px}.info-section:last-child{margin-bottom:0}.info-label{font:700 10px/1.3 system-ui;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin-bottom:4px}.info-value{font:13px/1.45 Georgia,serif}.info-mono{font:11px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;background:#f4f0ea;border-radius:7px;padding:7px;overflow-wrap:anywhere;margin:5px 0}.info-row{padding:6px 0;border-top:1px dotted var(--line)}.info-row:first-child{border-top:0}
body.hide-variants .ann-marker.v{display:none}body.hide-variants .variant-text{box-shadow:none}body.hide-notes .ann-marker.n{display:none}body.hide-refs .editorial-ref{display:none}@media(max-width:980px){.layout{grid-template-columns:1fr;padding:12px}.column-resizer{display:none}.side{position:relative;top:auto;max-height:none;grid-row:1}.reader{grid-row:2;padding:30px 24px}.tei-p{text-align:left}}@media print{header,.side,.column-resizer,.ann-marker,.pb{display:none!important}.layout{display:block;padding:0}.reader{box-shadow:none;border:0;padding:0}.tei-p{font-size:12pt}.line-frag.selected-line{background:transparent;box-shadow:none}}
</style>
</head>
<body>
<header><div class="header-row"><div class="brand"><h1>Transcription TEI — T1 / T2 / P · comparaison de trois témoins</h1><div class="sub" id="stats"></div></div><div class="controls"><select id="pageSelect" title="Aller au folio"></select><input id="search" type="search" placeholder="Rechercher dans le texte…"><div class="font-tools" title="Taille du texte de l’édition"><button id="fontSmaller" type="button" title="Réduire la police">A−</button><button id="fontReset" class="font-scale-label" type="button" title="Taille actuelle ; cliquer pour revenir à 100 %">100 %</button><button id="fontLarger" type="button" title="Augmenter la police">A+</button></div><label class="toggle"><input id="showVariants" type="checkbox" checked> variantes</label><label class="toggle"><input id="showNotes" type="checkbox" checked> notes</label><label class="toggle"><input id="showRefs" type="checkbox" checked> identifications</label><label class="toggle"><input id="showPb" type="checkbox" checked> folios</label></div></div></header>
<div class="layout"><article class="reader"><div class="reader-inner"><div class="doc-title" id="docTitle"></div><nav class="toc" id="toc" aria-label="Sommaire des sermons"></nav><div id="document"></div></div></article><div class="column-resizer" id="columnResizer" role="separator" aria-orientation="vertical" title="Faire glisser pour modifier la largeur du panneau des manuscrits ; double-clic pour réinitialiser"></div><aside class="side"><section class="card"><div class="card-h"><h2 id="imageTitle">T1 · Troyes 816 · fenêtre de 3 lignes</h2><div class="card-actions"><span class="small" id="score"></span><button class="info-btn" id="infoT1" type="button" title="Informations sur T1">…</button></div></div><div class="image-toolbar"><button id="zoomOut" type="button" title="Dézoomer">−</button><button id="zoomReset" type="button" title="Réinitialiser le zoom">↺</button><button id="zoomIn" type="button" title="Zoomer">+</button><span class="zoom-label" id="zoomLabel">100 %</span><button id="toggleHighlights" class="highlight-toggle" type="button" aria-pressed="false" title="Afficher les cadres">Cadres</button><button id="openPage816" class="page-open" type="button" title="Ouvrir la page entière dans un nouvel onglet">Page ↗</button><span class="zoom-help">molette · glisser</span></div><div class="image-wrap" id="imageWrap" title="Molette pour zoomer ; glisser l’image pour se déplacer ; double-clic pour revenir à 100 %"><div id="cropStage" class="window-stage" hidden></div><div class="placeholder" id="imgPlaceholder">Cliquez dans la transcription pour afficher la ligne correspondante.</div></div><div class="side-body"><div class="selected-text" id="selectedText">—</div><div class="navrow"><button id="prevLine">← ligne</button><button id="nextLine">ligne →</button></div><div class="meta" id="altoMeta"></div></div></section><section class="card"><div class="card-h"><h2>T2 · Troyes 1760 · fenêtre de 3 lignes</h2><div class="card-actions"><span class="small" id="secondaryStatus">alignement proposé</span><button class="info-btn" id="infoT2" type="button" title="Informations sur T2">…</button></div></div><div class="side-body"><div class="secondary-stack" id="secondaryLines"><div class="secondary-empty">Cliquez dans la transcription pour afficher le témoin correspondant.</div></div><div class="witness-note">Correspondances calculées automatiquement à partir de l'ALTO couleur et de la lecture #Troyes1760 de l'apparat. Elles sont proposées à titre de contrôle visuel.</div></div></section><section class="card"><div class="card-h"><h2>P · Paris, BnF, Latin 15940 · fenêtre de 3 lignes</h2><div class="card-actions"><span class="small" id="thirdStatus">alignement proposé</span><button class="info-btn" id="infoP" type="button" title="Informations sur P">…</button></div></div><div class="side-body"><div class="third-stack" id="thirdLines"><div class="third-empty">Cliquez dans la transcription pour afficher le témoin correspondant.</div></div><div class="witness-note">Correspondances calculées automatiquement à partir de l'ALTO du manuscrit. Aucune variante de ce témoin n'étant encore encodée, l'alignement est projeté sur le texte de base Troyes 816.</div></div></section><section class="card"><div class="card-h"><h2>Apparat et notes</h2><span class="small">ligne sélectionnée</span></div><div class="side-body ann-list" id="annotationList"><div class="small">Aucune ligne sélectionnée.</div></div></section><section class="card legacy-htr-card"><div class="side-body"><details><summary>Contrôle HTR / ALTO</summary><div class="source" id="htrText"></div><div class="source" id="altoText"></div></details></div></section></aside></div>
<div class="pop" id="popover"><div class="pop-h"><span id="popTitle"></span><button id="popClose">×</button></div><div class="pop-b" id="popBody"></div></div><dialog class="info-dialog" id="witnessInfoDialog"><div class="info-dialog-h"><strong id="witnessInfoTitle">Informations</strong><button id="witnessInfoClose" type="button" aria-label="Fermer">×</button></div><div class="info-dialog-b" id="witnessInfoBody"></div></dialog><script id="data" type="application/json">__DATA_JSON__</script>
<script>
const DATA=JSON.parse(document.getElementById('data').textContent), $=id=>document.getElementById(id);const esc=s=>String(s??'').replace(/[&<>\"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;'}[c]));const lineMap=new Map(),lineOrder=[];DATA.pages.forEach((p,pi)=>p.lines.forEach((l,li)=>{const k=`${p.id}::${l.line}`;lineMap.set(k,{p,l,pi,li,key:k});lineOrder.push(k)}));const docAnn=DATA.document?.annotations||{};let selectedKey=lineOrder[0]||null;let zoomLevel=1,dragging=false,dragStartX=0,dragStartY=0,dragScrollLeft=0,dragScrollTop=0;let primaryHighlightsVisible=false,secondaryHighlightsVisible=false;let secondaryCenterIndex=null,secondaryOriginCenterIndex=null,secondaryMatchKeys=new Set();const secondaryBy816=new Map(),secondaryPageById=new Map(),secondaryPhysical=[];const secondaryIndex=new Map();(DATA.troyes1760?.pages||[]).forEach(p=>{secondaryPageById.set(p.id,p);(p.lines||[]).forEach(l=>{const item={p,l},sk=`${p.id}::${l.alto_id||l.line}`;secondaryPhysical.push(item);secondaryIndex.set(sk,item);(l.keys816||[]).forEach(k=>{if(!secondaryBy816.has(k))secondaryBy816.set(k,[]);secondaryBy816.get(k).push(item)})})});secondaryPhysical.sort((a,b)=>(a.l.order||0)-(b.l.order||0));const secondaryPhysicalIndex=new Map();secondaryPhysical.forEach((it,i)=>secondaryPhysicalIndex.set(`${it.p.id}::${it.l.alto_id||it.l.line}`,i));let thirdHighlightsVisible=false;let thirdCenterIndex=null,thirdOriginCenterIndex=null,thirdMatchKeys=new Set();const thirdBy816=new Map(),thirdPageById=new Map(),thirdPhysical=[];const thirdIndex=new Map();(DATA.bnflat15940?.pages||[]).forEach(p=>{thirdPageById.set(p.id,p);(p.lines||[]).forEach(l=>{const item={p,l},sk=`${p.id}::${l.alto_id||l.line}`;thirdPhysical.push(item);thirdIndex.set(sk,item);(l.keys816||[]).forEach(k=>{if(!thirdBy816.has(k))thirdBy816.set(k,[]);thirdBy816.get(k).push(item)})})});thirdPhysical.sort((a,b)=>(a.l.order||0)-(b.l.order||0));const thirdPhysicalIndex=new Map();thirdPhysical.forEach((it,i)=>thirdPhysicalIndex.set(`${it.p.id}::${it.l.alto_id||it.l.line}`,i));
function storedGet(k,d){try{const v=localStorage.getItem(k);return v==null?d:v}catch{return d}}function storedSet(k,v){try{localStorage.setItem(k,String(v))}catch{}}
let readerScale=parseFloat(storedGet('tei-reader-scale','1'))||1;let sideWidth=parseInt(storedGet('tei-side-width','430'),10)||430;
function readerAnchor(){if(selectedKey){const el=document.querySelector(`.line-frag[data-line="${CSS.escape(selectedKey)}"]`);if(el)return{el,top:el.getBoundingClientRect().top}}const els=[...document.querySelectorAll('.line-frag[data-line]')],cy=innerHeight/2;let best=null,bd=Infinity;for(const el of els){const r=el.getBoundingClientRect(),d=Math.abs((r.top+r.bottom)/2-cy);if(d<bd){bd=d;best=el}}return best?{el:best,top:best.getBoundingClientRect().top}:null}
function setReaderScale(v){const a=readerAnchor();readerScale=Math.max(.75,Math.min(1.6,Math.round(v*20)/20));document.documentElement.style.setProperty('--reader-scale',readerScale);storedSet('tei-reader-scale',readerScale);if($('fontReset'))$('fontReset').textContent=Math.round(readerScale*100)+' %';if($('fontSmaller'))$('fontSmaller').disabled=readerScale<=.751;if($('fontLarger'))$('fontLarger').disabled=readerScale>=1.599;requestAnimationFrame(()=>{if(a?.el?.isConnected){const nt=a.el.getBoundingClientRect().top;scrollBy(0,nt-a.top)}})}
function applySideWidth(v,save=true){if(innerWidth<=980)return;const max=Math.max(320,Math.min(760,innerWidth-430));sideWidth=Math.max(300,Math.min(max,Math.round(v)));document.documentElement.style.setProperty('--side-width',sideWidth+'px');if(save)storedSet('tei-side-width',sideWidth)}
function initColumnResizer(){const r=$('columnResizer');if(!r)return;applySideWidth(sideWidth,false);let active=false,startX=0,startW=0;r.addEventListener('pointerdown',e=>{if(innerWidth<=980)return;active=true;startX=e.clientX;startW=sideWidth;r.classList.add('dragging');r.setPointerCapture?.(e.pointerId);e.preventDefault()});r.addEventListener('pointermove',e=>{if(!active)return;applySideWidth(startW+(startX-e.clientX),false)});const end=e=>{if(!active)return;active=false;r.classList.remove('dragging');storedSet('tei-side-width',sideWidth);try{r.releasePointerCapture?.(e.pointerId)}catch{}};r.addEventListener('pointerup',end);r.addEventListener('pointercancel',end);r.ondblclick=()=>applySideWidth(430,true);window.addEventListener('resize',()=>{if(innerWidth>980)applySideWidth(sideWidth,false)})}

function witnessLabel(w){return DATA.witnesses?.[w]||w}function styleClasses(seg){const out=[];for(const s of seg.styles||[])out.push('tei-'+s);for(const c of seg.classes||[])out.push(c);if(seg.variant_id)out.push('variant-text');return out.join(' ')}function renderSegment(seg){if(seg.kind==='pb')return `<span class="pb" data-page="${esc(seg.page)}">${esc(seg.label)}</span>`;if(seg.kind==='note')return `<button class="ann-marker n annotation-trigger" data-ann="${esc(seg.ann_id)}" data-line="${esc(seg.line_key||'')}" title="${esc(seg.tooltip||'Note')}">n</button>`;if(seg.kind==='variant-marker')return `<button class="ann-marker v annotation-trigger" data-ann="${esc(seg.ann_id)}" data-line="${esc(seg.line_key||'')}" title="${esc(seg.tooltip||'Variante')}">v</button>`;if(seg.kind==='editorial-ref')return ` <span class="editorial-ref">&lt;${esc(seg.text)}&gt;</span>`;if(seg.kind==='text'){const lk=seg.line_key||'',sel=lk&&lk===selectedKey?' selected-line':'',cl=styleClasses(seg);return `<span class="line-frag ${cl}${sel}" ${lk?`data-line="${esc(lk)}"`:''}>${esc(seg.text)}</span>`}return ''}
function renderDocument(){const blocks=DATA.document?.blocks||[],sermons=blocks.filter(b=>b.type==='sermon').map(b=>({sid:b.attrs?.xml_id||'',label:b.attrs?.display_id||(b.attrs?.xml_id||'').replaceAll('_',' ')})).filter(x=>x.sid);$('toc').innerHTML=sermons.length?`<div class="toc-title">Sommaire</div><div class="toc-list">${sermons.map(s=>`<a href="#${esc(s.sid)}">${esc(s.label)}</a>`).join('')}</div>`:'';$('toc').hidden=!sermons.length;let out='';blocks.forEach((b,i)=>{if(b.type==='sermon'){const sid=b.attrs?.xml_id||'',label=b.attrs?.display_id||sid.replaceAll('_',' ');out+=`<section class="sermon-start" id="${esc(sid)}" data-sermon="${esc(sid)}"><hr class="sermon-rule"><div class="sermon-id">${esc(label)}</div></section>`;return}const cls=b.type==='head'?'tei-head':b.type==='item'?'tei-item':'tei-p';out+=`<div class="${cls}" data-block="${i}">${b.segments.map(renderSegment).join('')}</div>`});$('document').innerHTML=out;document.querySelectorAll('.line-frag[data-line]').forEach(el=>el.onclick=()=>selectLine(el.dataset.line,false));document.querySelectorAll('.annotation-trigger').forEach(el=>el.onclick=e=>{e.stopPropagation();if(el.dataset.line)selectLine(el.dataset.line,false);showPopover(el.dataset.ann,e)});document.querySelectorAll('.pb[data-page]').forEach(el=>el.onclick=()=>selectPage(el.dataset.page))}
function pageLabel(id){const m=String(id||'').match(/^f(\d+)-np$/i);if(m)return 'vue '+(Number(m[1])+1);return String(id||'').replace(/^f\d+-/,'').replaceAll('-',' – ')}function populatePages(){DATA.pages.forEach(p=>$('pageSelect').insertAdjacentHTML('beforeend',`<option value="${esc(p.id)}">${esc(pageLabel(p.id))}</option>`));$('stats').textContent=`Troyes 816 : ${DATA.meta.pages} folios, ${DATA.meta.lines} lignes · T2 : ${DATA.troyes1760?.meta?.lines||0} lignes · P  : ${DATA.bnflat15940?.meta?.lines||0} lignes · ${DATA.meta.variants} variantes · ${DATA.meta.notes} notes`;$('docTitle').textContent=DATA.meta.manifest_label||'Transcription'}function selectPage(pid){const pb=document.querySelector(`.pb[data-page="${CSS.escape(pid)}"]`);if(pb)pb.scrollIntoView({block:'center'});$('pageSelect').value=pid}
function readingHTML(r){const who=(r.wit&&r.wit.length)?r.wit.map(witnessLabel).join(' · '):(r.role==='lem'?'lemme':'lecture');const txt=r.text||'∅';const notes=r.notes?.length?`<div class="small">${r.notes.map(esc).join(' · ')}</div>`:'';return `<div class="reading"><div class="wit">${esc(who)}</div><div>${esc(txt)}${notes}</div></div>`}function annHTML(a){if(a.kind==='variant')return `<div class="ann-card annotation-trigger" data-ann="${esc(a.id)}"><div class="ann-title">Variante</div>${a.readings.map(readingHTML).join('')}</div>`;return `<div class="ann-card annotation-trigger" data-ann="${esc(a.id)}"><div class="ann-title">Note éditoriale${a.type?` · ${esc(a.type)}`:''}</div><div style="font:13px/1.45 Georgia,serif">${esc(a.text)}</div></div>`}
function renderAnnotations(){const x=lineMap.get(selectedKey);if(!x){$('annotationList').innerHTML='<div class="small">Aucune ligne sélectionnée.</div>';return}const anns=x.l.annotations||[];$('annotationList').innerHTML=anns.length?anns.map(annHTML).join(''):'<div class="small">Aucune annotation sur cette ligne.</div>';$('annotationList').querySelectorAll('.annotation-trigger').forEach(el=>el.onclick=e=>showLineAnnotation(el.dataset.ann,e))}function findAnyAnn(id){if(docAnn[id])return docAnn[id];const x=lineMap.get(selectedKey);return x?.l.annotations?.find(a=>a.id===id)}function showLineAnnotation(id,e){const x=lineMap.get(selectedKey),a=x?.l.annotations?.find(a=>a.id===id);if(a)showAnnObject(a,e)}function showPopover(id,e){const a=findAnyAnn(id);if(a)showAnnObject(a,e)}function showAnnObject(a,e){$('popTitle').textContent=a.kind==='variant'?'Variante textuelle':'Note éditoriale';$('popBody').innerHTML=a.kind==='variant'?a.readings.map(readingHTML).join(''):`<div style="font:14px/1.5 Georgia,serif">${esc(a.text)}</div>`;const pop=$('popover'),x=Math.max(10,Math.min((e?.clientX||500)+10,innerWidth-530)),y=Math.max(10,Math.min((e?.clientY||90)+10,innerHeight-280));pop.style.left=x+'px';pop.style.top=y+'px';pop.classList.add('show')}
function infoRows(items,matchKeys,keyFn){if(!items?.length)return'<div class="small">Aucune ligne disponible.</div>';return items.map(it=>{const mark=matchKeys?.has(keyFn(it))?'★ ':'';const sc=it.l.score==null?'':` · confiance ${Math.round(it.l.score*100)} %`;return `<div class="info-row"><div class="info-value"><b>${mark}${esc(pageLabel(it.p.id))} · ligne ${esc(it.l.line)}</b>${sc}</div><div class="info-mono">${esc(it.l.alto||'')}</div></div>`}).join('')}
function witnessInfo(which){if(which==='T1'){const x=lineMap.get(selectedKey);if(!x)return['T1 · Troyes 816','<div class="small">Aucune ligne sélectionnée.</div>'];const b=x.l.bbox||{};return['T1 · Troyes 816',`<div class="info-section"><div class="info-label">Passage sélectionné</div><div class="info-value">${esc(x.l.corrected||'')}</div></div><div class="info-section"><div class="info-label">Repérage</div><div class="info-value">${esc(pageLabel(x.p.id))} · ligne ${esc(x.l.line)} · confiance ${Math.round((x.l.score||0)*100)} %</div><div class="info-mono">${esc(x.l.alto_id||'')} · x=${esc(b.hpos??'')}, y=${esc(b.vpos??'')}, w=${esc(b.width??'')}, h=${esc(b.height??'')}</div></div><div class="info-section"><div class="info-label">HTR</div><div class="info-mono">${esc(x.l.htr||'')}</div></div><div class="info-section"><div class="info-label">ALTO</div><div class="info-mono">${esc(x.l.alto||'')}</div></div>`]}
if(which==='T2'){const items=secondaryCenterIndex==null?[]:secondaryWindowItems(secondaryCenterIndex);return['T2 · Troyes 1760',`<div class="info-section"><div class="info-label">Alignement</div><div class="info-value">Correspondances calculées automatiquement à partir de l’ALTO couleur et de la lecture T2 de l’apparat ; elles sont proposées pour contrôle visuel.</div></div><div class="info-section"><div class="info-label">Fenêtre de trois lignes</div>${infoRows(items,secondaryMatchKeys,secondaryKey)}</div>`]}
const items=thirdCenterIndex==null?[]:thirdWindowItems(thirdCenterIndex);return['P · Paris, BnF, Latin 15940',`<div class="info-section"><div class="info-label">Alignement</div><div class="info-value">Correspondances calculées automatiquement à partir de l’ALTO. Les variantes de P n’étant pas encore encodées systématiquement, l’alignement est projeté sur le texte de base.</div></div><div class="info-section"><div class="info-label">Fenêtre de trois lignes</div>${infoRows(items,thirdMatchKeys,thirdKey)}</div>`]}
function showWitnessInfo(which){const [title,body]=witnessInfo(which);$('witnessInfoTitle').textContent=title;$('witnessInfoBody').innerHTML=body;const d=$('witnessInfoDialog');if(typeof d.showModal==='function')d.showModal();else d.setAttribute('open','')}

function scaledBBox(p,l,pad=0){const c=p.iiif;if(!c||!l?.bbox)return null;const aw=p.alto_width||1,ah=p.alto_height||1,iw=c.width||aw,ih=c.height||ah,sx=iw/aw,sy=ih/ah,b=l.bbox;return{x:Math.max(0,(b.hpos-pad)*sx),y:Math.max(0,(b.vpos-pad)*sy),w:Math.max(1,(b.width+2*pad)*sx),h:Math.max(1,(b.height+2*pad)*sy),iw,ih}}
function cropGroup(items,pad=18){if(!items.length)return null;const p=items[0].p,c=p.iiif;if(!c)return null;const boxes=items.map(it=>scaledBBox(it.p,it.l,0)).filter(Boolean);if(!boxes.length)return null;const iw=boxes[0].iw,ih=boxes[0].ih,x=Math.max(0,Math.floor(Math.min(...boxes.map(b=>b.x))-pad)),y=Math.max(0,Math.floor(Math.min(...boxes.map(b=>b.y))-pad)),x1=Math.min(iw,Math.ceil(Math.max(...boxes.map(b=>b.x+b.w))+pad)),y1=Math.min(ih,Math.ceil(Math.max(...boxes.map(b=>b.y+b.h))+pad));return{x,y,w:Math.max(1,x1-x),h:Math.max(1,y1-y)}}
function iiifUrl(c,r){if(!c?.service||!r)return null;const quality=c.iiif_version===1?'native':'default',region=`${r.x},${r.y},${r.w},${r.h}`;if(String(c.service).includes('gallica.bnf.fr')){const w=Math.max(1,Math.min(900,Math.round(r.w)));return `${c.service}/${region}/${w},/0/${quality}.jpg`}const size=c.iiif_version===3?'max':'full';return `${c.service}/${region}/${size}/0/${quality}.jpg`}
function fullPageUrl(c){if(!c)return null;if(c.image)return c.image;if(!c.service)return null;const size=c.iiif_version===3?'max':'full',quality=c.iiif_version===1?'native':'default';return `${c.service}/full/${size}/0/${quality}.jpg`}
function openFullPage(c){const u=fullPageUrl(c);if(!u)return;const w=window.open(u,'_blank','noopener,noreferrer');if(w)w.opener=null}
function groupByPage(items){const groups=[];for(const it of items){const last=groups[groups.length-1];if(last&&last.p.id===it.p.id)last.items.push(it);else groups.push({p:it.p,items:[it]})}return groups}
function updateHighlightButton(btn,visible){if(!btn)return;btn.classList.toggle('active',visible);btn.setAttribute('aria-pressed',visible?'true':'false');btn.title=visible?'Masquer les cadres':'Afficher les cadres'}
function stageMarkup(items,highlightKeys=new Set(),secondary=false){const groups=groupByPage(items);return groups.map(g=>{const r=cropGroup(g.items,18),u=iiifUrl(g.p.iiif,r);if(!u)return `<div class="secondary-empty">Image IIIF indisponible pour ${esc(pageLabel(g.p.id))}.</div>`;const overlays=g.items.filter(it=>highlightKeys.has(secondary?secondaryKey(it):it.key)).map(it=>{const b=scaledBBox(it.p,it.l,0);if(!b||!r)return'';const left=Math.max(0,100*(b.x-r.x)/r.w),top=Math.max(0,100*(b.y-r.y)/r.h),width=Math.min(100-left,100*b.w/r.w),height=Math.min(100-top,100*b.h/r.h);return `<span class="line-highlight${secondary?' secondary-match':''}" style="left:${left.toFixed(3)}%;top:${top.toFixed(3)}%;width:${width.toFixed(3)}%;height:${height.toFixed(3)}%"></span>`}).join('');return `<div class="window-slice" data-page="${esc(g.p.id)}"><img src="${esc(u)}" alt="${esc(pageLabel(g.p.id))}, fenêtre de ${g.items.length} ligne(s)" width="${Math.round(r.w)}" height="${Math.round(r.h)}" decoding="async" draggable="false">${overlays}</div>`}).join('')}
function primaryWindowItems(){const idx=lineOrder.indexOf(selectedKey);if(idx<0)return[];return lineOrder.slice(Math.max(0,idx-1),Math.min(lineOrder.length,idx+2)).map(k=>lineMap.get(k)).filter(Boolean)}
function setZoom(z,anchorX=null,anchorY=null){const wrap=$('imageWrap'),stage=$('cropStage');if(!wrap||!stage||stage.hidden)return;zoomLevel=Math.max(1,Math.min(6,Math.round(z*100)/100));const rect=wrap.getBoundingClientRect(),ax=anchorX==null?wrap.clientWidth/2:anchorX-rect.left,ay=anchorY==null?wrap.clientHeight/2:anchorY-rect.top,rx=(wrap.scrollLeft+ax)/(wrap.scrollWidth||1),ry=(wrap.scrollTop+ay)/(wrap.scrollHeight||1);stage.style.width=(zoomLevel*100)+'%';wrap.style.overflowX=zoomLevel>1.001?'auto':'hidden';requestAnimationFrame(()=>{wrap.scrollLeft=Math.max(0,rx*wrap.scrollWidth-ax);wrap.scrollTop=Math.max(0,ry*wrap.scrollHeight-ay)});$('zoomLabel').textContent=Math.round(zoomLevel*100)+' %';$('zoomOut').disabled=zoomLevel<=1.001;$('zoomIn').disabled=zoomLevel>=5.999}
function resetZoom(){zoomLevel=1;const wrap=$('imageWrap'),stage=$('cropStage');if(stage)stage.style.width='100%';if(wrap){wrap.style.overflowX='hidden';wrap.scrollLeft=0;wrap.scrollTop=0}$('zoomLabel').textContent='100 %';$('zoomOut').disabled=true;$('zoomIn').disabled=false}
function secondaryKey(it){return `${it.p.id}::${it.l.alto_id||it.l.line}`}
function secondaryWindowItems(centerIdx){if(centerIdx==null||centerIdx<0)return[];return secondaryPhysical.slice(Math.max(0,centerIdx-1),Math.min(secondaryPhysical.length,centerIdx+2))}
function chooseSecondaryCenter(indices){if(!indices.length)return null;const avg=indices.reduce((a,b)=>a+b,0)/indices.length;let best=indices[0],bestCount=-1,bestDist=Infinity;const lo=Math.max(0,Math.min(...indices)-1),hi=Math.min(secondaryPhysical.length-1,Math.max(...indices)+1);for(let c=lo;c<=hi;c++){const count=indices.filter(i=>Math.abs(i-c)<=1).length,dist=Math.abs(c-avg);if(count>bestCount||(count===bestCount&&dist<bestDist)){best=c;bestCount=count;bestDist=dist}}return best}
function secondaryWindowMarkup(centerIdx){const items=secondaryWindowItems(centerIdx);if(!items.length)return '<div class="secondary-empty">Aucune ligne disponible.</div>';const first=items[0],last=items[items.length-1],center=secondaryPhysical[centerIdx],folios=[...new Set(items.map(it=>pageLabel(it.p.id)))].join(' / '),matchVisible=items.filter(it=>secondaryMatchKeys.has(secondaryKey(it))),scores=matchVisible.map(it=>Math.round((it.l.score||0)*100)),scoreText=scores.length?(scores.length===1?`${scores[0]} %`:`${Math.min(...scores)}–${Math.max(...scores)} %`):'hors correspondance';const low=scores.length&&Math.min(...scores)<50?' low':'';const details=items.map(it=>`<div class="secondary-source">${secondaryMatchKeys.has(secondaryKey(it))?'★ ':''}${esc(pageLabel(it.p.id))} · ligne ${it.l.line} — ${esc(it.l.alto||'')}</div>`).join('');return `<div class="secondary-line"><div class="secondary-head"><b>${esc(folios)} · lignes ${first.l.line}–${last.l.line}</b><span class="secondary-score${low}">${scoreText}</span></div><div class="secondary-toolbar"><button class="secondary-nav" id="secPrev" type="button" title="Décaler la fenêtre d’une ligne vers le haut" ${centerIdx<=0?'disabled':''}>←</button><button id="secZoomOut" type="button" title="Dézoomer">−</button><button id="secZoomReset" type="button" title="Réinitialiser le zoom">↺</button><button id="secZoomIn" type="button" title="Zoomer">+</button><span class="secondary-zoom-label" id="secZoomLabel">100 %</span><button class="secondary-nav" id="secNext" type="button" title="Décaler la fenêtre d’une ligne vers le bas" ${centerIdx>=secondaryPhysical.length-1?'disabled':''}>→</button><button id="secToggleHighlights" class="highlight-toggle" type="button" aria-pressed="false" title="Afficher les cadres">Cadres</button><button id="secOpenPage" class="page-open" type="button" title="Ouvrir la page entière de la ligne centrale dans un nouvel onglet">Page ↗</button><button class="secondary-reset-match" id="secResetMatch" type="button" title="Revenir aux lignes correspondant à la sélection dans T1">⤺</button></div><div class="secondary-wrap" id="secondaryWrap" title="Molette pour zoomer ; glisser l’image pour se déplacer ; double-clic pour revenir à 100 %"><div class="window-stage${secondaryHighlightsVisible?'':' highlights-off'}" id="secondaryStage">${stageMarkup(items,secondaryMatchKeys,true)}</div></div><div class="secondary-help">fenêtre de 3 lignes · cadres optionnels · navigation par pas d’1 ligne · molette : zoom · glisser : déplacer</div><details><summary class="secondary-source">HTR / ALTO des 3 lignes</summary>${details}</details></div>`}
function initSecondaryViewer(){const wrap=$('secondaryWrap'),stage=$('secondaryStage'),label=$('secZoomLabel'),zout=$('secZoomOut'),zin=$('secZoomIn'),zreset=$('secZoomReset'),htoggle=$('secToggleHighlights');if(stage)stage.classList.toggle('highlights-off',!secondaryHighlightsVisible);updateHighlightButton(htoggle,secondaryHighlightsVisible);let z=1,drag=false,sx=0,sy=0,sl=0,st=0;const update=()=>{if(label)label.textContent=Math.round(z*100)+' %';if(zout)zout.disabled=z<=1.001;if(zin)zin.disabled=z>=5.999};const apply=(nz,cx=null,cy=null)=>{if(!wrap||!stage)return;const rect=wrap.getBoundingClientRect(),ax=cx==null?wrap.clientWidth/2:cx-rect.left,ay=cy==null?wrap.clientHeight/2:cy-rect.top,rx=(wrap.scrollLeft+ax)/(wrap.scrollWidth||1),ry=(wrap.scrollTop+ay)/(wrap.scrollHeight||1);z=Math.max(1,Math.min(6,Math.round(nz*100)/100));stage.style.width=(z*100)+'%';wrap.style.overflowX=z>1.001?'auto':'hidden';requestAnimationFrame(()=>{wrap.scrollLeft=Math.max(0,rx*wrap.scrollWidth-ax);wrap.scrollTop=Math.max(0,ry*wrap.scrollHeight-ay)});update()};const reset=()=>{z=1;if(stage)stage.style.width='100%';if(wrap){wrap.style.overflowX='hidden';wrap.scrollLeft=0;wrap.scrollTop=0}update()};if(wrap&&stage){wrap.addEventListener('wheel',e=>{e.preventDefault();apply(z*(e.deltaY<0?1.16:1/1.16),e.clientX,e.clientY)},{passive:false});wrap.ondblclick=e=>{e.preventDefault();reset()};wrap.onmousedown=e=>{if(z<=1||e.button!==0)return;drag=true;sx=e.clientX;sy=e.clientY;sl=wrap.scrollLeft;st=wrap.scrollTop;wrap.classList.add('dragging');e.preventDefault()};window.addEventListener('mousemove',e=>{if(!drag)return;wrap.scrollLeft=sl-(e.clientX-sx);wrap.scrollTop=st-(e.clientY-sy)});window.addEventListener('mouseup',()=>{if(drag){drag=false;wrap.classList.remove('dragging')}})}if(zout)zout.onclick=()=>apply(z/1.25);if(zin)zin.onclick=()=>apply(z*1.25);if(zreset)zreset.onclick=reset;if(htoggle)htoggle.onclick=()=>{secondaryHighlightsVisible=!secondaryHighlightsVisible;stage?.classList.toggle('highlights-off',!secondaryHighlightsVisible);updateHighlightButton(htoggle,secondaryHighlightsVisible)};const pageBtn=$('secOpenPage');if(pageBtn){const centerItem=secondaryCenterIndex==null?null:secondaryPhysical[secondaryCenterIndex];pageBtn.disabled=!fullPageUrl(centerItem?.p?.iiif);pageBtn.onclick=()=>{if(centerItem)openFullPage(centerItem.p.iiif)}};$('secPrev')?.addEventListener('click',()=>moveSecondary(-1));$('secNext')?.addEventListener('click',()=>moveSecondary(1));$('secResetMatch')?.addEventListener('click',()=>{secondaryCenterIndex=secondaryOriginCenterIndex;renderSecondaryWindow()});update()}
function moveSecondary(d){if(secondaryCenterIndex==null)return;const ni=Math.max(0,Math.min(secondaryPhysical.length-1,secondaryCenterIndex+d));if(ni===secondaryCenterIndex)return;secondaryCenterIndex=ni;renderSecondaryWindow()}
function renderSecondaryWindow(){const host=$('secondaryLines');if(secondaryCenterIndex==null){host.innerHTML='<div class="secondary-empty">Aucune correspondance T2 (Troyes 1760) proposée pour cette ligne.</div>';return}host.innerHTML=secondaryWindowMarkup(secondaryCenterIndex);initSecondaryViewer()}
function renderSecondary(){const host=$('secondaryLines'),items=(secondaryBy816.get(selectedKey)||[]).slice().sort((a,b)=>(a.l.order||0)-(b.l.order||0)),uniq=[],seen=new Set();for(const it of items){const id=secondaryKey(it);if(!seen.has(id)){seen.add(id);uniq.push(it)}}if(!uniq.length){secondaryCenterIndex=secondaryOriginCenterIndex=null;secondaryMatchKeys=new Set();host.innerHTML='<div class="secondary-empty">Aucune correspondance T2 (Troyes 1760) proposée pour cette ligne.</div>';$('secondaryStatus').textContent='aucune correspondance';return}secondaryMatchKeys=new Set(uniq.map(secondaryKey));const indices=uniq.map(it=>secondaryPhysicalIndex.get(secondaryKey(it))).filter(i=>i!=null);secondaryOriginCenterIndex=chooseSecondaryCenter(indices);secondaryCenterIndex=secondaryOriginCenterIndex;$('secondaryStatus').textContent=`${uniq.length} ligne${uniq.length>1?'s':''} correspondante${uniq.length>1?'s':''} · contexte ±1`;renderSecondaryWindow()}
function thirdKey(it){return `${it.p.id}::${it.l.alto_id||it.l.line}`}
function thirdWindowItems(centerIdx){if(centerIdx==null||centerIdx<0)return[];return thirdPhysical.slice(Math.max(0,centerIdx-1),Math.min(thirdPhysical.length,centerIdx+2))}
function chooseThirdCenter(indices){if(!indices.length)return null;const avg=indices.reduce((a,b)=>a+b,0)/indices.length;let best=indices[0],bestCount=-1,bestDist=Infinity;const lo=Math.max(0,Math.min(...indices)-1),hi=Math.min(thirdPhysical.length-1,Math.max(...indices)+1);for(let c=lo;c<=hi;c++){const count=indices.filter(i=>Math.abs(i-c)<=1).length,dist=Math.abs(c-avg);if(count>bestCount||(count===bestCount&&dist<bestDist)){best=c;bestCount=count;bestDist=dist}}return best}
function thirdWindowMarkup(centerIdx){const items=thirdWindowItems(centerIdx);if(!items.length)return '<div class="third-empty">Aucune ligne disponible.</div>';const first=items[0],last=items[items.length-1],center=thirdPhysical[centerIdx],folios=[...new Set(items.map(it=>pageLabel(it.p.id)))].join(' / '),matchVisible=items.filter(it=>thirdMatchKeys.has(thirdKey(it))),scores=matchVisible.map(it=>Math.round((it.l.score||0)*100)),scoreText=scores.length?(scores.length===1?`${scores[0]} %`:`${Math.min(...scores)}–${Math.max(...scores)} %`):'hors correspondance';const low=scores.length&&Math.min(...scores)<50?' low':'';const details=items.map(it=>`<div class="third-source">${thirdMatchKeys.has(thirdKey(it))?'★ ':''}${esc(pageLabel(it.p.id))} · ligne ${it.l.line} — ${esc(it.l.alto||'')}</div>`).join('');return `<div class="third-line"><div class="third-head"><b>${esc(folios)} · lignes ${first.l.line}–${last.l.line}</b><span class="third-score${low}">${scoreText}</span></div><div class="third-toolbar"><button class="third-nav" id="thirdPrev" type="button" title="Décaler la fenêtre d’une ligne vers le haut" ${centerIdx<=0?'disabled':''}>←</button><button id="thirdZoomOut" type="button" title="Dézoomer">−</button><button id="thirdZoomReset" type="button" title="Réinitialiser le zoom">↺</button><button id="thirdZoomIn" type="button" title="Zoomer">+</button><span class="third-zoom-label" id="thirdZoomLabel">100 %</span><button class="third-nav" id="thirdNext" type="button" title="Décaler la fenêtre d’une ligne vers le bas" ${centerIdx>=thirdPhysical.length-1?'disabled':''}>→</button><button id="thirdToggleHighlights" class="highlight-toggle" type="button" aria-pressed="false" title="Afficher les cadres">Cadres</button><button id="thirdOpenPage" class="page-open" type="button" title="Ouvrir la page entière de la ligne centrale dans un nouvel onglet">Page ↗</button><button class="third-reset-match" id="thirdResetMatch" type="button" title="Revenir aux lignes correspondant à la sélection dans T1">⤺</button></div><div class="third-wrap" id="thirdWrap" title="Molette pour zoomer ; glisser l’image pour se déplacer ; double-clic pour revenir à 100 %"><div class="window-stage${thirdHighlightsVisible?'':' highlights-off'}" id="thirdStage">${stageMarkup(items,thirdMatchKeys,true)}</div></div><div class="third-help">fenêtre de 3 lignes · cadres optionnels · navigation par pas d’1 ligne · molette : zoom · glisser : déplacer</div><details><summary class="third-source">HTR / ALTO des 3 lignes</summary>${details}</details></div>`}
function initThirdViewer(){const wrap=$('thirdWrap'),stage=$('thirdStage'),label=$('thirdZoomLabel'),zout=$('thirdZoomOut'),zin=$('thirdZoomIn'),zreset=$('thirdZoomReset'),htoggle=$('thirdToggleHighlights');if(stage)stage.classList.toggle('highlights-off',!thirdHighlightsVisible);updateHighlightButton(htoggle,thirdHighlightsVisible);let z=1,drag=false,sx=0,sy=0,sl=0,st=0;const update=()=>{if(label)label.textContent=Math.round(z*100)+' %';if(zout)zout.disabled=z<=1.001;if(zin)zin.disabled=z>=5.999};const apply=(nz,cx=null,cy=null)=>{if(!wrap||!stage)return;const rect=wrap.getBoundingClientRect(),ax=cx==null?wrap.clientWidth/2:cx-rect.left,ay=cy==null?wrap.clientHeight/2:cy-rect.top,rx=(wrap.scrollLeft+ax)/(wrap.scrollWidth||1),ry=(wrap.scrollTop+ay)/(wrap.scrollHeight||1);z=Math.max(1,Math.min(6,Math.round(nz*100)/100));stage.style.width=(z*100)+'%';wrap.style.overflowX=z>1.001?'auto':'hidden';requestAnimationFrame(()=>{wrap.scrollLeft=Math.max(0,rx*wrap.scrollWidth-ax);wrap.scrollTop=Math.max(0,ry*wrap.scrollHeight-ay)});update()};const reset=()=>{z=1;if(stage)stage.style.width='100%';if(wrap){wrap.style.overflowX='hidden';wrap.scrollLeft=0;wrap.scrollTop=0}update()};if(wrap&&stage){wrap.addEventListener('wheel',e=>{e.preventDefault();apply(z*(e.deltaY<0?1.16:1/1.16),e.clientX,e.clientY)},{passive:false});wrap.ondblclick=e=>{e.preventDefault();reset()};wrap.onmousedown=e=>{if(z<=1||e.button!==0)return;drag=true;sx=e.clientX;sy=e.clientY;sl=wrap.scrollLeft;st=wrap.scrollTop;wrap.classList.add('dragging');e.preventDefault()};window.addEventListener('mousemove',e=>{if(!drag)return;wrap.scrollLeft=sl-(e.clientX-sx);wrap.scrollTop=st-(e.clientY-sy)});window.addEventListener('mouseup',()=>{if(drag){drag=false;wrap.classList.remove('dragging')}})}if(zout)zout.onclick=()=>apply(z/1.25);if(zin)zin.onclick=()=>apply(z*1.25);if(zreset)zreset.onclick=reset;if(htoggle)htoggle.onclick=()=>{thirdHighlightsVisible=!thirdHighlightsVisible;stage?.classList.toggle('highlights-off',!thirdHighlightsVisible);updateHighlightButton(htoggle,thirdHighlightsVisible)};const pageBtn=$('thirdOpenPage');if(pageBtn){const centerItem=thirdCenterIndex==null?null:thirdPhysical[thirdCenterIndex];pageBtn.disabled=!fullPageUrl(centerItem?.p?.iiif);pageBtn.onclick=()=>{if(centerItem)openFullPage(centerItem.p.iiif)}};$('thirdPrev')?.addEventListener('click',()=>moveThird(-1));$('thirdNext')?.addEventListener('click',()=>moveThird(1));$('thirdResetMatch')?.addEventListener('click',()=>{thirdCenterIndex=thirdOriginCenterIndex;renderThirdWindow()});update()}
function moveThird(d){if(thirdCenterIndex==null)return;const ni=Math.max(0,Math.min(thirdPhysical.length-1,thirdCenterIndex+d));if(ni===thirdCenterIndex)return;thirdCenterIndex=ni;renderThirdWindow()}
function renderThirdWindow(){const host=$('thirdLines');if(thirdCenterIndex==null){host.innerHTML='<div class="third-empty">Aucune correspondance P (Paris, BnF, Latin 15940) proposée pour cette ligne.</div>';return}host.innerHTML=thirdWindowMarkup(thirdCenterIndex);initThirdViewer()}
function renderThird(){const host=$('thirdLines'),items=(thirdBy816.get(selectedKey)||[]).slice().sort((a,b)=>(a.l.order||0)-(b.l.order||0)),uniq=[],seen=new Set();for(const it of items){const id=thirdKey(it);if(!seen.has(id)){seen.add(id);uniq.push(it)}}if(!uniq.length){thirdCenterIndex=thirdOriginCenterIndex=null;thirdMatchKeys=new Set();host.innerHTML='<div class="third-empty">Aucune correspondance P (Paris, BnF, Latin 15940) proposée pour cette ligne.</div>';$('thirdStatus').textContent='aucune correspondance';return}thirdMatchKeys=new Set(uniq.map(thirdKey));const indices=uniq.map(it=>thirdPhysicalIndex.get(thirdKey(it))).filter(i=>i!=null);thirdOriginCenterIndex=chooseThirdCenter(indices);thirdCenterIndex=thirdOriginCenterIndex;$('thirdStatus').textContent=`${uniq.length} ligne${uniq.length>1?'s':''} correspondante${uniq.length>1?'s':''} · contexte ±1`;renderThirdWindow()}
function renderSide(){const x=lineMap.get(selectedKey);if(!x)return;const{p,l}=x,items=primaryWindowItems(),stage=$('cropStage');$('imageTitle').textContent=`T1 · Troyes 816 · ${pageLabel(p.id)} · ligne ${l.line} · contexte ±1`;$('pageSelect').value=p.id;const pageBtn=$('openPage816');if(pageBtn)pageBtn.disabled=!fullPageUrl(p.iiif);$('selectedText').textContent=l.corrected;$('score').textContent=`${Math.round(l.score*100)} %`;$('altoMeta').textContent=`ligne centrale : ${l.alto_id} · x=${l.bbox.hpos}, y=${l.bbox.vpos}, w=${l.bbox.width}, h=${l.bbox.height}`;$('htrText').textContent='HTR : '+l.htr;$('altoText').textContent='ALTO : '+l.alto;resetZoom();const markup=stageMarkup(items,new Set([selectedKey]),false);if(markup){stage.innerHTML=markup;stage.classList.toggle('highlights-off',!primaryHighlightsVisible);updateHighlightButton($('toggleHighlights'),primaryHighlightsVisible);stage.hidden=false;$('imgPlaceholder').hidden=true}else{stage.hidden=true;$('imgPlaceholder').hidden=false;$('imgPlaceholder').textContent='Image IIIF indisponible.'}renderAnnotations();renderSecondary();renderThird()}
function selectLine(k,scroll=true){if(!lineMap.has(k))return;selectedKey=k;document.querySelectorAll('.selected-line').forEach(e=>e.classList.remove('selected-line'));document.querySelectorAll(`.line-frag[data-line="${CSS.escape(k)}"]`).forEach(e=>e.classList.add('selected-line'));if(scroll)document.querySelector(`.line-frag[data-line="${CSS.escape(k)}"]`)?.scrollIntoView({block:'center'});renderSide()}function moveLine(d){const i=lineOrder.indexOf(selectedKey),n=Math.max(0,Math.min(lineOrder.length-1,i+d));selectLine(lineOrder[n],true)}function doSearch(){const q=$('search').value.trim().toLocaleLowerCase('fr');if(!q)return;const spans=[...document.querySelectorAll('.line-frag')],here=spans.findIndex(s=>s.classList.contains('selected-line'));for(let z=1;z<=spans.length;z++){const sp=spans[(Math.max(here,0)+z)%spans.length];if(sp.textContent.toLocaleLowerCase('fr').includes(q)){if(sp.dataset.line)selectLine(sp.dataset.line,false);sp.scrollIntoView({block:'center'});return}}}
$('pageSelect').onchange=e=>selectPage(e.target.value);$('fontSmaller').onclick=()=>setReaderScale(readerScale-.1);$('fontLarger').onclick=()=>setReaderScale(readerScale+.1);$('fontReset').onclick=()=>setReaderScale(1);$('infoT1').onclick=()=>showWitnessInfo('T1');$('infoT2').onclick=()=>showWitnessInfo('T2');$('infoP').onclick=()=>showWitnessInfo('P');$('witnessInfoClose').onclick=()=>$('witnessInfoDialog').close?.();$('witnessInfoDialog').addEventListener('click',e=>{if(e.target===$('witnessInfoDialog'))$('witnessInfoDialog').close?.()});$('search').onkeydown=e=>{if(e.key==='Enter')doSearch()};$('prevLine').onclick=()=>moveLine(-1);$('nextLine').onclick=()=>moveLine(1);$('zoomOut').onclick=()=>setZoom(zoomLevel/1.25);$('zoomIn').onclick=()=>setZoom(zoomLevel*1.25);$('zoomReset').onclick=()=>resetZoom();$('toggleHighlights').onclick=()=>{primaryHighlightsVisible=!primaryHighlightsVisible;$('cropStage').classList.toggle('highlights-off',!primaryHighlightsVisible);updateHighlightButton($('toggleHighlights'),primaryHighlightsVisible)};updateHighlightButton($('toggleHighlights'),primaryHighlightsVisible);$('openPage816').onclick=()=>{const x=lineMap.get(selectedKey);if(x)openFullPage(x.p.iiif)};$('imageWrap').addEventListener('wheel',e=>{if($('cropStage').hidden)return;e.preventDefault();setZoom(zoomLevel*(e.deltaY<0?1.16:1/1.16),e.clientX,e.clientY)},{passive:false});$('imageWrap').ondblclick=e=>{e.preventDefault();resetZoom()};$('imageWrap').onmousedown=e=>{if(zoomLevel<=1||e.button!==0)return;dragging=true;const w=$('imageWrap');dragStartX=e.clientX;dragStartY=e.clientY;dragScrollLeft=w.scrollLeft;dragScrollTop=w.scrollTop;w.classList.add('dragging');e.preventDefault()};window.addEventListener('mousemove',e=>{if(!dragging)return;const w=$('imageWrap');w.scrollLeft=dragScrollLeft-(e.clientX-dragStartX);w.scrollTop=dragScrollTop-(e.clientY-dragStartY)});window.addEventListener('mouseup',()=>{dragging=false;$('imageWrap').classList.remove('dragging')});$('showVariants').onchange=e=>document.body.classList.toggle('hide-variants',!e.target.checked);$('showNotes').onchange=e=>document.body.classList.toggle('hide-notes',!e.target.checked);$('showRefs').onchange=e=>document.body.classList.toggle('hide-refs',!e.target.checked);$('showPb').onchange=e=>document.querySelectorAll('.pb').forEach(x=>x.classList.toggle('hidden',!e.target.checked));$('popClose').onclick=()=>$('popover').classList.remove('show');document.addEventListener('click',e=>{if(!$('popover').contains(e.target)&&!e.target.closest('.annotation-trigger'))$('popover').classList.remove('show')});document.addEventListener('keydown',e=>{if(e.target.matches('input,select,textarea'))return;if(e.key==='ArrowDown'&&e.altKey){e.preventDefault();moveLine(1)}if(e.key==='ArrowUp'&&e.altKey){e.preventDefault();moveLine(-1)}if((e.key==='+'||e.key==='=')&&e.altKey){e.preventDefault();setZoom(zoomLevel*1.25)}if(e.key==='-'&&e.altKey){e.preventDefault();setZoom(zoomLevel/1.25)}if(e.key==='0'&&e.altKey){e.preventDefault();resetZoom()}});setReaderScale(readerScale);initColumnResizer();populatePages();renderDocument();resetZoom();if(selectedKey)selectLine(selectedKey,false);
</script></body></html>'''


def make_html(data):
    # Évite la fermeture accidentelle de la balise script JSON si une note contenait « </script> ».
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return HTML_TEMPLATE.replace("__DATA_JSON__", payload)


# =============================================================================
# Programme principal
# =============================================================================


def main():
    import time
    t0 = time.perf_counter()
    print("=" * 72)
    print("GÉNÉRATEUR WEB RAPIDE V11 — T1 / T2 / P")
    print("=" * 72)
    print("Aucun recalcul RapidFuzz : utilisation des alignements pré-calculés.\n")

    corrected = choose_file(Path(TEI_CORRIGEE), "Choisir la TEI corrigée/enrichie", [("XML", "*.xml"), ("Tous les fichiers", "*.*")])
    cache816 = choose_file(Path(ALIGNEMENT_816_CACHE), "Choisir alignement_T1_precalcule.json", [("JSON", "*.json"), ("Tous les fichiers", "*.*")])
    cache1760 = choose_file(Path(ALIGNEMENT_1760_CACHE), "Choisir alignement_T2_precalcule.json", [("JSON", "*.json"), ("Tous les fichiers", "*.*")])
    cachebnf = choose_file(Path(ALIGNEMENT_BNF_CACHE), "Choisir alignement_P_precalcule.json", [("JSON", "*.json"), ("Tous les fichiers", "*.*")])
    output = choose_output(Path(OUTPUT_HTML))

    print(f"TEI               : {corrected}")
    print(f"Cache T1          : {cache816}")
    print(f"Cache T2          : {cache1760}")
    print(f"Cache P           : {cachebnf}")
    print("\nLecture de la TEI et construction du HTML…")
    data, missing = build_dataset_fast(corrected, cache816, cache1760, cachebnf, TARGET_WITNESS)
    output.write_text(make_html(data), encoding="utf-8")
    dt = time.perf_counter() - t0

    print("\nTerminé.")
    print(f"HTML créé : {output}")
    print(f"Folios    : {data['meta']['pages']}")
    print(f"Lignes T1 : {data['meta']['lines']}")
    sec = data.get("troyes1760", {}).get("meta", {})
    print(f"T2 : {sec.get('pages', 0)} folios, {sec.get('lines', 0)} lignes proposées")
    bnf = data.get("bnflat15940", {}).get("meta", {})
    print(f"P  : {bnf.get('pages', 0)} vues, {bnf.get('lines', 0)} lignes proposées")
    print(f"Durée : {dt:.1f} s")
    if missing:
        print("[AVERTISSEMENT] Pages 816 absentes du cache : " + ", ".join(missing))
    print("\nOuvrez maintenant le fichier HTML dans votre navigateur.")


if __name__ == "__main__":
    main()