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
import shutil
from pathlib import Path

SERMONS = Path(__file__).resolve().parent / "data" / "sermons"


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
