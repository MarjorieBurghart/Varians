# -*- coding: utf-8 -*-
"""Textes synchronisés à part (V0.9.1.1), sans Qt : dossiers
alignments/<texte>/, pivot d'un texte (<part name base>), projet réduit à un
texte pour assemble_resources, et numérotation des lignes par segment
(pivot_lines). Jeu « corpus » (tests/corpus_data.py)."""
from __future__ import annotations

from pathlib import Path

import pytest

from corpus_data import alignment, make_corpus, write_json
from document_session import LbIndex
from pivot_lines import include_spans, pivot_lb_pattern, pivot_lines
from project_config import load_project
from text_alignments import text_project, text_syncs
from witness_resource_refresh import assemble_resources
from xml_assembly import assemble


@pytest.fixture
def corpus(tmp_path):
    return make_corpus(tmp_path / "corpus")


def _parts(project):
    edition = project.edition
    return list(assemble(edition.read_text(encoding="utf-8"), edition).parts)


def _syncs(project):
    return text_syncs(project, _parts(project))


def _by_name(syncs):
    return {sync.name: sync for sync in syncs}


# --- Dossiers par texte ----------------------------------------------------------

def test_each_text_with_a_folder_is_synchronized_apart(corpus):
    project = load_project(corpus)
    syncs, problems = _syncs(project)
    assert problems == ()
    found = _by_name(syncs)
    assert sorted(found) == ["s02", "s04"]
    s02 = found["s02"]
    assert s02.path.name == "s02.xml" and s02.folder == corpus.parent / "alignments" / "s02"
    assert s02.base == "B"                                    # <part name="s02" base="B"/>
    assert sorted(s02.alignments) == ["B", "D"]
    assert found["s04"].base == "A" and sorted(found["s04"].alignments) == ["A", "C"]


def test_a_project_without_text_folders_has_no_text_synchronized_apart(corpus):
    for folder in ("s02", "s04"):
        for path in (corpus.parent / "alignments" / folder).iterdir():
            path.unlink()
    assert _syncs(load_project(corpus)) == ((), ())


def test_problems_are_reported(corpus):
    root = corpus.parent
    write_json(root / "alignments" / "s02" / "X.json", alignment("X", "B", "X-1r", 8))
    (root / "alignments" / "s04" / "A.json").unlink()
    text = corpus.read_text(encoding="utf-8").replace(
        '<part name="s02" base="B" />', '<part name="s02" base="Z" /><part name="s09" base="B" />')
    corpus.write_text(text, encoding="utf-8")
    syncs, problems = _syncs(load_project(corpus))
    assert sorted((p.name, p.code, p.detail) for p in problems) == [
        ("s02", "no_base_alignment", "A"),                   # pivot du projet, sans JSON ici
        ("s02", "unknown_base", "Z"),
        ("s02", "unknown_witness", "X"),
        ("s04", "no_base_alignment", "A"),
        ("s09", "unknown_part", "B"),
    ]
    found = _by_name(syncs)
    assert found["s02"].base == "A"                          # pivot inconnu : celui du projet
    assert "X" not in found["s02"].alignments


def test_the_project_of_a_text_gives_its_witness_state(corpus):
    project = load_project(corpus)
    s02 = _by_name(_syncs(project)[0])["s02"]
    state = assemble_resources(text_project(project, s02))
    assert [w.id for w in text_project(project, s02).witnesses] == ["B", "D"]
    assert state.base_active and state.base_sync_count == 8
    assert [item["key"] for item in state.base_items][:2] == ["B-30r::1", "B-30r::2"]
    assert state.secondary_links == {"D": 8}
    assert state.base_maps["D"]["B-30r::3"] == [2]


# --- Numérotation par segment ----------------------------------------------------

def _lines(project, syncs):
    edition = project.edition
    return pivot_lines(edition.read_text(encoding="utf-8"), edition, {}, project.base_witness,
                       text_bases={sync.path: sync.base for sync in syncs})


def _path(corpus, name):
    if name == "edition":
        return corpus.parent / "xml" / "edition.xml"
    return corpus.parent / "xml" / "sermons" / f"{name}.xml"


def test_each_text_synchronized_apart_has_its_own_numbering(corpus):
    project = load_project(corpus)
    syncs = _syncs(project)[0]
    lines = _lines(project, syncs)
    s02, s04 = (_path(corpus, name) for name in ("s02", "s04"))
    # Segment de l'édition : s01 (10 lignes de A) et s03 (9), sans s02 ni s04.
    assert lines.count == 19
    assert lines.file(_path(corpus, "s01")).ordinals == tuple(range(0, 10))
    assert lines.file(_path(corpus, "s03")).ordinals == tuple(range(10, 19))
    assert lines.file(_path(corpus, "s01")).segment is None
    # s02 : ses 8 lignes de B ; s04 : 5 lignes, puis 3 dans son exemplum.
    assert lines.segment_count(lines.file(s02).segment) == 8
    assert lines.file(s02).ordinals == tuple(range(0, 8))
    segment = lines.file(s04).segment
    assert segment is not None and lines.file(_path(corpus, "s04_exemplum")).segment == segment
    assert lines.segment_count(segment) == 8
    assert lines.file(s04).ordinals == tuple(range(0, 5))
    assert lines.file(_path(corpus, "s04_exemplum")).ordinals == (5, 6, 7)
    assert lines.location(6, segment) == (_path(corpus, "s04_exemplum"), 1)


def test_a_position_in_a_text_is_numbered_in_its_segment(corpus):
    project = load_project(corpus)
    lines = _lines(project, _syncs(project)[0])

    def at(name, needle, base="A"):
        path = _path(corpus, name)
        text = path.read_text(encoding="utf-8")
        return lines.ordinal_at(path, text.index(needle), LbIndex.scan(text, pivot_lb_pattern(base)),
                                include_spans(text))

    assert at("s02", "<head>", base="B") == 0
    assert at("s02", "nativitatem", base="B") == 2
    assert at("s04", "<head>") == 0                           # début du texte : sa première ligne
    assert at("s03", "<head>") == 9                           # édition : dernière ligne de s01
    # Dans l'édition, après l'inclusion de s02 (synchronisé à part) : s01 encore.
    assert at("edition", '<xi:include href="sermons/s03.xml"') == 9
    assert at("edition", "</body>") == 18


def test_without_texts_apart_the_numbering_is_unchanged(corpus):
    project = load_project(corpus)
    edition = project.edition
    lines = pivot_lines(edition.read_text(encoding="utf-8"), edition, {}, "A")
    assert lines.count == 27 and lines.file(_path(corpus, "s04")).segment is None
