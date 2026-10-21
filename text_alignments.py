# -*- coding: utf-8 -*-
"""Textes synchronisés à part dans une édition en parties (V0.9.1.1), sans Qt.

Dans un corpus dont les textes ne sont pas transmis par les mêmes témoins, ni
dans le même ordre, un texte (une partie de l'édition, incluse par
``xi:include``) peut avoir ses propres alignements : un JSON par témoin, au
format habituel, rangé selon une convention, sans déclaration :

    alignments/s02/B.json      (texte xml/sermons/s02.xml, témoin B)

Le dossier porte le nom du fichier du texte, sans extension. **Un texte qui a
son dossier d'alignements est synchronisé à part ; les autres suivent la
numérotation continue** (V0.9.1.0). Le pivot d'un texte est celui du projet,
sauf exception déclarée dans project.xml : ``<part name="s02" base="B"/>``.

``text_syncs`` trouve ces textes ; ``text_project`` réduit le projet à l'un
d'eux, pour ``witness_resource_refresh.assemble_resources`` : seuls les
témoins qui ont un JSON pour ce texte, avec ce JSON comme alignement.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from types import SimpleNamespace

from xml_assembly import path_key

ALIGNMENTS_DIR = "alignments"


@dataclass(frozen=True)
class TextSync:
    """Un texte synchronisé à part : son fichier, son dossier d'alignements,
    son pivot et ``{témoin: JSON}`` (témoins déclarés dans project.xml)."""
    name: str
    path: Path
    folder: Path
    base: str
    alignments: dict


@dataclass(frozen=True)
class TextSyncProblem:
    """Problème signalé par le diagnostic des témoins.

    ``code`` : ``unknown_witness`` (JSON d'un témoin non déclaré, ignoré),
    ``unknown_base`` (pivot inconnu : celui du projet est pris),
    ``no_base_alignment`` (pas de JSON pour le pivot du texte),
    ``unknown_part`` (``<part name>`` qui ne nomme aucun texte de l'édition),
    ``duplicate_name`` (deux textes de même nom : le premier garde le dossier).
    ``detail`` : le témoin ou le fichier concerné.
    """
    name: str
    code: str
    detail: str = ""


def text_syncs(project, part_paths):
    """``(textes synchronisés à part, problèmes)`` de l'édition dont les
    parties sont ``part_paths``, dans l'ordre d'inclusion."""
    declared = {w.id for w in project.witnesses}
    exceptions = {part.name: part.base for part in getattr(project, "parts", ())}
    root = Path(project.root_dir) / ALIGNMENTS_DIR
    syncs, problems, seen = [], [], {}
    for path in part_paths:
        path = Path(path)
        name = path.stem
        if name in seen:
            if path_key(seen[name]) != path_key(path) and (root / name).is_dir():
                problems.append(TextSyncProblem(name, "duplicate_name", str(path)))
            continue
        seen[name] = path
        folder = root / name
        files = sorted(folder.glob("*.json")) if folder.is_dir() else []
        if not files:
            continue
        alignments = {}
        for file in files:
            if file.stem in declared:
                alignments[file.stem] = file
            else:
                problems.append(TextSyncProblem(name, "unknown_witness", file.stem))
        base = exceptions.get(name, project.base_witness)
        if base not in declared:
            problems.append(TextSyncProblem(name, "unknown_base", base))
            base = project.base_witness
        if base not in alignments:
            problems.append(TextSyncProblem(name, "no_base_alignment", base))
        syncs.append(TextSync(name, path, folder, base, alignments))
    for name, base in exceptions.items():
        if name not in seen:
            problems.append(TextSyncProblem(name, "unknown_part", base))
    return tuple(syncs), tuple(problems)


def text_project(project, sync):
    """Projet réduit au texte ``sync`` : ses témoins (ceux qui ont un JSON pour
    lui, dans l'ordre de project.xml), ce JSON comme alignement, et son
    pivot. Les règles des images et des ALTO de chaque témoin restent les
    siennes."""
    witnesses = tuple(
        replace(w, alignment=sync.alignments[w.id], role="base" if w.id == sync.base else "secondary")
        for w in project.witnesses if w.id in sync.alignments)
    return SimpleNamespace(base_witness=sync.base, witnesses=witnesses, root_dir=project.root_dir,
                           witness_by_id={w.id: w for w in witnesses})
