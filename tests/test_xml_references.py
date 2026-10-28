# -*- coding: utf-8 -*-
"""Références entre documents XML du projet (« #id », « fichier.xml#id »), sans Qt."""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from xml_references import (
    REFERENCE_ATTRIBUTES, ReferenceResolver, collect_ids, collect_references, explicit_pointer,
    parse_pointer,
)

ROOT = Path(__file__).resolve().parents[1]

PERSONNES = """<?xml version="1.0" encoding="UTF-8"?>
<listPerson xmlns="http://www.tei-c.org/ns/1.0">
  <person xml:id="bernard"><persName>Bernardus</persName> <note>abbas</note></person>
  <person xml:id="petrus"><persName>Petrus</persName></person>
  <!-- <person xml:id="commente"/> -->
</listPerson>
"""
LIEUX = """<listPlace><place xml:id="clairvaux"><placeName>Clara Vallis</placeName></place>
<place xml:id="petrus"/></listPlace>"""


@pytest.mark.parametrize("token, expected", [
    ("#bernard", (None, "bernard")),
    ("personnes.xml#bernard", ("personnes.xml", "bernard")),
    ("../autorites/lieux.xml#clairvaux", ("../autorites/lieux.xml", "clairvaux")),
    ("https://example.org/p#bernard", None),
    ("urn:x#y", None),
    ("bernard", None),
    ("iiif_manifest", None),
    ("#", None),
    ("#xpointer(id('a'))", None),
    ("personnes.xml", None),
])
def test_parse_pointer(token, expected):
    assert parse_pointer(token) == expected


def test_reference_attributes_are_the_usual_tei_pointers():
    assert {"ref", "corresp", "target", "who", "wit", "edRef", "facs", "sameAs"} <= REFERENCE_ATTRIBUTES
    assert "rend" not in REFERENCE_ATTRIBUTES and "n" not in REFERENCE_ATTRIBUTES


def test_collect_ids_gives_position_line_element_and_label():
    ids = collect_ids(PERSONNES)
    assert set(ids) == {"bernard", "petrus"}                       # commentaire ignoré
    (bernard,) = ids["bernard"]
    assert bernard.element == "person"
    assert bernard.label == "Bernardus abbas"
    assert bernard.line == 3
    assert PERSONNES[bernard.start:bernard.end] == '<person xml:id="bernard">'


def test_collect_ids_tolerates_malformed_text_and_records_duplicates():
    text = '<a xml:id="x"><b xml:id="x">un<c xml:id="y">'
    ids = collect_ids(text)
    assert len(ids["x"]) == 2 and len(ids["y"]) == 1


def test_collect_references_splits_pointer_lists_and_ignores_other_values():
    text = ('<p><persName ref="#bernard">B</persName> <rdg wit="#T1 #T2">x</rdg>'
            ' <ptr target="https://example.org/a#b"/> <msIdentifier facs="iiif_manifest"/>'
            ' <hi rend="#color">y</hi> <name tei:ref="personnes.xml#petrus"/></p>')
    refs = collect_references(text)
    assert [(r.attribute, r.token) for r in refs] == [
        ("ref", "#bernard"), ("wit", "#T1"), ("wit", "#T2"), ("tei:ref", "personnes.xml#petrus")]
    second = refs[2]
    assert text[second.start:second.end] == "#T2"
    assert second.element == "rdg" and second.id == "T2" and second.file is None
    assert refs[3].file == "personnes.xml" and refs[3].line == 1


def _resolver(tmp_path, edition_text):
    edition = tmp_path / "xml" / "edition.xml"
    personnes = tmp_path / "xml" / "personnes.xml"
    lieux = tmp_path / "xml" / "lieux.xml"
    for path, text in ((edition, edition_text), (personnes, PERSONNES), (lieux, LIEUX)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    documents = [(edition, edition_text), (personnes, PERSONNES), (lieux, LIEUX)]
    return ReferenceResolver(documents), edition, personnes, lieux


def _reference(text, token):
    return next(r for r in collect_references(text) if r.token == token)


def test_short_reference_designates_the_document_itself(tmp_path):
    # Sens standard des URI : « #id » vise le document qui contient la
    # référence. Un identifiant trouvé seulement dans un autre document du
    # projet est signalé, avec sa cible, pour écrire « fichier.xml#id ».
    text = ('<TEI><witness xml:id="T1"/><persName ref="#bernard"/><rdg wit="#T1"/>'
            '<placeName ref="#clairvaux"/><persName ref="#absent"/></TEI>')
    resolver, edition, personnes, lieux = _resolver(tmp_path, text)
    own = resolver.resolve(_reference(text, "#T1"), edition)
    assert own.status == "ok" and own.targets[0][0] == edition
    elsewhere = resolver.resolve(_reference(text, "#bernard"), edition)
    assert elsewhere.status == "other_document"
    path, target = elsewhere.targets[0]
    assert path == personnes and target.element == "person"
    assert resolver.resolve(_reference(text, "#clairvaux"), edition).targets[0][0] == lieux
    assert resolver.resolve(_reference(text, "#absent"), edition).status == "missing"


def test_short_reference_to_an_identifier_of_two_other_documents(tmp_path):
    text = '<TEI><persName ref="#petrus"/></TEI>'
    resolver, edition, personnes, lieux = _resolver(tmp_path, text)
    resolution = resolver.resolve(_reference(text, "#petrus"), edition)
    assert resolution.status == "other_document"
    assert {path for path, _ in resolution.targets} == {personnes, lieux}


def test_identifier_defined_in_the_document_itself(tmp_path):
    text = '<TEI><person xml:id="petrus"/><persName ref="#petrus"/></TEI>'
    resolver, edition, *_ = _resolver(tmp_path, text)
    resolution = resolver.resolve(_reference(text, "#petrus"), edition)
    assert resolution.status == "ok" and resolution.targets[0][0] == edition


def test_identifier_repeated_in_the_target_document_is_ambiguous(tmp_path):
    text = '<TEI><seg xml:id="x"/><seg xml:id="x"/><ref target="#x"/><ref target="edition.xml#x"/></TEI>'
    resolver, edition, *_ = _resolver(tmp_path, text)
    for token in ("#x", "edition.xml#x"):
        resolution = resolver.resolve(_reference(text, token), edition)
        assert resolution.status == "ambiguous" and len(resolution.targets) == 2


def test_explicit_file_reference(tmp_path):
    text = ('<TEI><persName ref="personnes.xml#petrus"/><persName ref="personnes.xml#clairvaux"/>'
            '<persName ref="inconnu.xml#x"/></TEI>')
    resolver, edition, personnes, _ = _resolver(tmp_path, text)
    ok = resolver.resolve(_reference(text, "personnes.xml#petrus"), edition)
    assert ok.status == "ok" and ok.targets[0][0] == personnes
    assert resolver.resolve(_reference(text, "personnes.xml#clairvaux"), edition).status == "missing"
    assert resolver.resolve(_reference(text, "inconnu.xml#x"), edition).status == "no_file"


def test_file_outside_the_project_is_read_from_disk(tmp_path):
    other = tmp_path / "ailleurs.xml"
    other.write_text('<list><item xml:id="i1"/></list>', encoding="utf-8")
    text = '<TEI><ref target="../ailleurs.xml#i1"/></TEI>'
    resolver, edition, *_ = _resolver(tmp_path, text)
    resolution = resolver.resolve(_reference(text, "../ailleurs.xml#i1"), edition)
    assert resolution.status == "ok" and resolution.targets[0][0] == other.resolve()


def test_problems_lists_every_reference_other_tools_cannot_follow(tmp_path):
    text = ('<TEI><persName ref="personnes.xml#bernard"/><persName ref="#bernard"/>'
            '<persName ref="#absent"/><persName ref="#petrus"/></TEI>')
    resolver, edition, *_ = _resolver(tmp_path, text)
    problems = resolver.problems()
    assert [(p.path, p.reference.token, p.resolution.status) for p in problems] == [
        (edition, "#bernard", "other_document"), (edition, "#absent", "missing"),
        (edition, "#petrus", "other_document")]


def test_check_counts_every_reference_and_lists_the_problems(tmp_path):
    text = '<TEI><persName ref="personnes.xml#bernard"/><rdg wit="#absent #petrus"/></TEI>'
    resolver, edition, *_ = _resolver(tmp_path, text)
    count, problems = resolver.check()
    assert count == 3
    assert problems == resolver.problems()
    assert [p.reference.token for p in problems] == ["#absent", "#petrus"]


def test_explicit_pointer_is_relative_to_the_citing_document(tmp_path):
    edition = tmp_path / "xml" / "edition.xml"
    assert explicit_pointer(edition, tmp_path / "xml" / "personnes.xml", "bernard") == "personnes.xml#bernard"
    assert explicit_pointer(edition, tmp_path / "autorites" / "lieux.xml", "x") == "../autorites/lieux.xml#x"
    assert parse_pointer(explicit_pointer(edition, tmp_path / "autorites" / "lieux.xml", "x"))


def test_example_project_has_no_reference_problem():
    edition = ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    assert len(collect_references(text)) > 10000                 # edRef, wit…
    assert ReferenceResolver([(edition, text)]).problems() == []


def test_paths_are_resolved_once_per_file_not_per_reference(monkeypatch):
    # Path.resolve() est coûteux, surtout sous Windows : 10 000 références
    # ne doivent pas donner 30 000 résolutions.
    edition = ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    calls = []
    original = Path.resolve
    monkeypatch.setattr(Path, "resolve", lambda self, *a, **k: calls.append(self) or original(self, *a, **k))
    count, problems = ReferenceResolver([(edition, text)]).check()
    assert count > 10000 and problems == []
    assert len(calls) < 10, len(calls)


def test_checking_the_example_project_is_fast():
    # Temps de calcul du processus (environ 0,15 s), insensible à la charge
    # de la machine ; la marge couvre les postes lents.
    edition = ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    started = time.process_time()
    ReferenceResolver([(edition, text)]).problems()
    elapsed = time.process_time() - started
    assert elapsed < 5.0, elapsed
