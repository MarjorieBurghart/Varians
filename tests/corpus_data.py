# -*- coding: utf-8 -*-
"""Jeu « corpus » des tests de la V0.9.1.1 : le jeu « sermons »
(tests/data/sermons), avec des alignements fabriqués.

- s02 est synchronisé à part, avec B pour pivot (<part name="s02" base="B"/>) :
  alignments/s02/B.json (ses 8 lignes de B) et D.json ;
- s04 est synchronisé à part avec le pivot du projet, A :
  alignments/s04/A.json (5 lignes dans s04, 3 dans son exemplum) et C.json ;
- s01 et s03 suivent la numérotation continue : alignments/A.json (19 lignes)
  et C.json.

Les JSON n'ont pas d'image (témoins déclarés <images type="none"/>).
"""
from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SERMONS = Path(__file__).resolve().parent / "data" / "sermons"
# Projet de test (exclu des publications) et fichiers de Varians qu'il
# emploie : feuilles de rendu, traductions, ressources.
EXAMPLE = Path(__file__).resolve().parent / "data" / "exemple"
EXAMPLE_ITEMS = ((EXAMPLE, "project.xml"), (EXAMPLE, "xml"), (EXAMPLE, "alignments"),
                 (REPO, "rendering"), (REPO, "i18n"), (REPO, "resources"))


def alignment(witness, base, page, count, *, secondary_of=None):
    """JSON au format tei-manuscript-alignment : ``count`` lignes sur la page
    ``page`` ; pour un témoin secondaire, chaque ligne désigne la ligne de même
    rang de la page ``secondary_of`` du pivot."""
    lines = []
    for number in range(1, count + 1):
        line = {"line": number}
        if secondary_of is not None:
            line.update(order=number, base_keys=[f"{secondary_of}::{number}"])
        lines.append(line)
    return {"meta": {"format": "tei-manuscript-alignment", "format_version": 1, "witness": witness,
                     "base_witness": base, "role": "secondary" if secondary_of else "base"},
            "pages": [{"id": page, "lines": lines}]}


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def make_corpus(root: Path) -> Path:
    """Copie le jeu sermons dans ``root`` et y ajoute les alignements ;
    renvoie le chemin de project.xml."""
    shutil.copytree(SERMONS, root)
    alignments = root / "alignments"
    write_json(alignments / "A.json", alignment("A", "A", "A-12r", 19))
    write_json(alignments / "C.json", alignment("C", "A", "C-2r", 19, secondary_of="A-12r"))
    write_json(alignments / "s02" / "B.json", alignment("B", "B", "B-30r", 8))
    write_json(alignments / "s02" / "D.json", alignment("D", "B", "D-101r", 8, secondary_of="B-30r"))
    write_json(alignments / "s04" / "A.json", alignment("A", "A", "A-13r", 8))
    write_json(alignments / "s04" / "C.json", alignment("C", "A", "C-3r", 8, secondary_of="A-13r"))
    project = root / "project.xml"
    text = project.read_text(encoding="utf-8")
    text = text.replace('<witness id="A" label="A · Manuscrit fictif A" role="base">',
                        '<witness id="A" label="A · Manuscrit fictif A" role="base" alignment="alignments/A.json">')
    text = text.replace('<witness id="C" label="C · Manuscrit fictif C">',
                        '<witness id="C" label="C · Manuscrit fictif C" alignment="alignments/C.json">')
    text = text.replace("</teiManuscriptProject>",
                        '  <parts>\n    <part name="s02" base="B" />\n  </parts>\n</teiManuscriptProject>')
    project.write_text(text, encoding="utf-8")
    return project


def split_alignments(root: Path, text: str, pivot: str, first: int, count: int, witnesses):
    """Fait de ``text`` un texte synchronisé à part : les lignes ``first`` à
    ``first + count - 1`` (rangs, à partir de 0) du JSON du pivot, et les
    lignes des ``witnesses`` qui les désignent, passent de
    ``alignments/<témoin>.json`` à ``alignments/<text>/<témoin>.json``.
    Un témoin absent de ``witnesses`` perd ces lignes sans recevoir de JSON
    pour le texte."""
    alignments = root / "alignments"
    pivot_data = json.loads((alignments / f"{pivot}.json").read_text(encoding="utf-8"))
    keys = [f"{page['id']}::{line.get('line')}" for page in pivot_data["pages"] for line in page["lines"]]
    moved = set(keys[first:first + count])

    def split(data, belongs):
        kept, taken = [], []
        for page in data["pages"]:
            stay = [line for line in page["lines"] if not belongs(page, line)]
            go = [line for line in page["lines"] if belongs(page, line)]
            if stay:
                kept.append(dict(page, lines=stay))
            if go:
                taken.append(dict(page, lines=go))
        return dict(data, pages=kept), dict(data, pages=taken)

    rest, part = split(pivot_data, lambda page, line: f"{page['id']}::{line.get('line')}" in moved)
    write_json(alignments / f"{pivot}.json", rest)
    write_json(alignments / text / f"{pivot}.json", part)
    for path in sorted(alignments.glob("*.json")):
        if path.stem == pivot:
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        rest, part = split(data, lambda page, line: bool(set(line.get("base_keys") or []) & moved))
        write_json(path, rest)
        if path.stem in witnesses:
            write_json(alignments / text / path.name, part)


# PNG d'un pixel, pour les images locales des témoins par pages.
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d4944415478da6378ffe4fc7f00090a03a24c369af90000000049454e44ae426082")


def add_page_witness(project_xml: Path, witness: str, labels) -> None:
    """Ajoute au projet un témoin par pages (V0.9.1.3) : des images locales,
    sans JSON ; ses folios portent les ``labels``, dans cet ordre (surfaces
    ``<witness>-p0001``…)."""
    folder = project_xml.parent / "images" / witness
    folder.mkdir(parents=True, exist_ok=True)
    images = []
    for index, label in enumerate(labels, 1):
        (folder / f"{index:04d}.png").write_bytes(TINY_PNG)
        images.append(f'<image file="images/{witness}/{index:04d}.png" label="{label}"/>')
    declaration = (f'<witness id="{witness}" label="{witness} · par pages">'
                   f'<images type="files">{"".join(images)}</images></witness>\n  ')
    text = project_xml.read_text(encoding="utf-8")
    project_xml.write_text(text.replace("</witnesses>", declaration + "</witnesses>", 1), encoding="utf-8")


# --- Projet exemple et ses variantes (tests GUI et tests de l'export web) ------

def insert_at(text, inserts):
    """Insère chaque ``(position, texte)`` de ``inserts`` dans ``text``."""
    for position, value in sorted(inserts, reverse=True):
        text = text[:position] + value + text[position:]
    return text


def copy_example(root: Path) -> Path:
    """Copie le projet de test (tests/data/exemple) dans ``root``, avec les
    fichiers de Varians qu'il emploie ; renvoie le chemin de project.xml."""
    root.mkdir(parents=True, exist_ok=True)
    for folder, name in EXAMPLE_ITEMS:
        source = folder / name
        if source.is_dir():
            shutil.copytree(source, root / name)
        else:
            shutil.copy2(source, root / name)
    (root / "web_output").mkdir(exist_ok=True)
    return root / "project.xml"


def move_to_part(project_xml: Path, first="RLS_185", following="RLS_186", name="rls185.xml") -> Path:
    """Passe le sermon ``first`` (jusqu'à ``following``) de l'édition dans
    une partie, xml/``name``, incluse par ``xi:include`` ; renvoie le fichier
    de la partie."""
    edition = project_xml.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start = text.index(f'<div xml:id="{first}">')
    end = text.index(f'<div xml:id="{following}">')
    part = text[start:end].rstrip()
    assert part.endswith("</div>")
    part = part.replace(f'<div xml:id="{first}">',
                        f'<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="{first}">', 1)
    path = edition.parent / name
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + part + "\n", encoding="utf-8")
    text = text[:start] + f'<xi:include href="{name}"/>\n' + text[end:]
    text = re.sub(r"<TEI\b", '<TEI xmlns:xi="http://www.w3.org/2001/XInclude"', text, count=1)
    edition.write_text(text, encoding="utf-8")
    return path


def _pivot_lb_spans(text, base="T1"):
    from pivot_lines import pivot_lb_pattern
    return [match.span() for match in pivot_lb_pattern(base).finditer(text)]


# Lacunes du projet exemple (V0.9.1.3) : T2 en lacune de la ligne 20 du pivot
# (après son <lb/>) à la ligne 25 ; un passage absent de T1 avant la ligne 41 ;
# X, témoin par pages (1r, 1v), a son <pb n="1r"/> au début du <body> et son
# <pb n="1v"/> dans le passage absent de T1.
T2_START, T2_END, PIVOT_GAP = 20, 25, 41
LACUNA_GAP = '<lacunaStart wit="#T1"/>PASSAGE <pb edRef="#X" n="1v"/>ABSENS<lacunaEnd wit="#T1"/>'


def add_example_lacunae(project_xml: Path) -> None:
    add_page_witness(project_xml, "X", ("1r", "1v"))
    edition = project_xml.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = _pivot_lb_spans(text)
    body = text.index("<body>") + len("<body>")
    edition.write_text(insert_at(text, [
        (body, '<pb edRef="#X" n="1r"/>'),
        (lbs[T2_START][1], '<lacunaStart wit="#T2"/>'),
        (lbs[T2_END][1], '<lacunaEnd wit="#T2"/>'),
        (lbs[PIVOT_GAP][0], LACUNA_GAP),
    ]), encoding="utf-8")


# Témoins par pages dans rls185 synchronisé à part (V0.9.1.3, V0.9.1.4) :
# X (12r, 12v, 13r, 13v) a ses <pb> dans rls185, 12v après la ligne 4 du pivot
# (rang 3), 13r après la ligne 21 (rang 20) ; 13v n'a pas de <pb>. Y (1r, 1v)
# n'a pas de <pb> ; avec ``y_locus``, son <locus from="1v" target="#RLS_185">.
PB_12V = '<pb edRef="#X" n="12v"/>'
PB_13R = '<pb edRef="#X" n="13r"/>'


def add_text_pages(project_xml: Path, *, y_locus=False) -> None:
    add_page_witness(project_xml, "X", ("12r", "12v", "13r", "13v"))
    add_page_witness(project_xml, "Y", ("1r", "1v"))
    part = project_xml.parent / "xml" / "rls185.xml"
    text = part.read_text(encoding="utf-8")
    lbs = _pivot_lb_spans(text)
    part.write_text(insert_at(text, [(lbs[3][1], PB_12V), (lbs[20][1], PB_13R)]), encoding="utf-8")
    if y_locus:
        edition = project_xml.parent / "xml" / "edition.xml"
        text = edition.read_text(encoding="utf-8")
        edition.write_text(text.replace("</listWit>", '<witness xml:id="Y">Y <locus from="1v" target="#RLS_185"/>'
                                                      '</witness></listWit>', 1), encoding="utf-8")
