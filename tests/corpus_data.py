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
