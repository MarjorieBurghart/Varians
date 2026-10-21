# -*- coding: utf-8 -*-
"""Édition assemblée par XInclude, sans Qt : références d'une partie à
l'autre (xml_references), témoins d'une partie pour « Débugger l'apparat »
(apparatus_xpath). Jeu « sermons » (tests/data/sermons)."""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from apparatus_xpath import incomplete_app_xpath, part_witnesses
from xml_assembly import assemble
from xml_references import ReferenceResolver, collect_references

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
SERMONS = DATA / "sermons"
FILES = [EDITION] + [SERMONS / f"{name}.xml" for name in ("s01", "s02", "s03", "s04", "s04_exemplum")] + [
    DATA / "personnes.xml"]


def _texts(**changes):
    texts = {path: path.read_text(encoding="utf-8") for path in FILES}
    for name, text in changes.items():
        texts[SERMONS / f"{name}.xml"] = text
    return texts


def _resolver(texts, grouped=True):
    groups = ()
    if grouped:
        parts = {path: text for path, text in texts.items() if path.parent == SERMONS}
        groups = (assemble(texts[EDITION], EDITION, parts).visible_ids(),)
    return ReferenceResolver(list(texts.items()), groups)


def _resolve(resolver, texts, path, token):
    reference = next(r for r in collect_references(texts[path]) if r.token == token)
    return resolver.resolve(reference, path)


def test_an_id_of_another_part_is_found_in_the_assembled_edition():
    texts = _texts()
    resolver = _resolver(texts)
    found = _resolve(resolver, texts, EDITION, "#s02")
    assert found.status == "ok" and found.targets[0][0].name == "s02.xml"
    found = _resolve(resolver, texts, SERMONS / "s01.xml", "#s03_p1")
    assert found.status == "ok" and found.targets[0][0].name == "s03.xml"
    # Sans groupe (V0.8.9.x) : « #s02 » n'est pas dans l'édition elle-même ;
    # il est seulement signalé dans un autre document du projet.
    assert _resolve(_resolver(texts, grouped=False), texts, EDITION, "#s02").status == "other_document"


def test_a_witness_declared_in_the_header_of_its_sermon_is_found_there():
    texts = _texts()
    found = _resolve(_resolver(texts), texts, SERMONS / "s03.xml", "#E")
    assert found.status == "ok" and found.targets[0][0].name == "s03.xml"


def test_an_id_outside_the_included_element_is_not_in_the_assembled_edition():
    # E n'est déclaré que dans l'en-tête de s03, qui n'entre pas dans l'édition.
    s01 = (SERMONS / "s01.xml").read_text(encoding="utf-8").replace(
        '<lem wit="#A">vigilantes', '<lem wit="#A #E">vigilantes')
    texts = _texts(s01=s01)
    found = _resolve(_resolver(texts), texts, SERMONS / "s01.xml", "#E")
    assert found.status == "other_document" and found.targets[0][0].name == "s03.xml"


def test_only_the_missing_sermon_is_a_problem():
    texts = _texts()
    count, problems = _resolver(texts).check()
    assert count > 20
    assert [(p.path.name, p.reference.token, p.resolution.status) for p in problems] == [
        ("s04.xml", "#s05", "missing")]


def test_an_id_defined_in_two_parts_is_ambiguous_except_in_its_own_file():
    s04 = (SERMONS / "s04.xml").read_text(encoding="utf-8").replace(
        '<p xml:id="s04_p2">', '<p xml:id="s01_p2">')
    texts = _texts(s04=s04.replace("#s05", "#s01_p2"))
    resolver = _resolver(texts)
    assert _resolve(resolver, texts, SERMONS / "s02.xml", "#s01_p2").status == "ambiguous"
    assert _resolve(resolver, texts, SERMONS / "s04.xml", "#s01_p2").status == "ok"


def test_the_assembly_tells_which_ids_each_file_brings():
    visible = assemble(EDITION.read_text(encoding="utf-8"), EDITION).visible_ids()
    by_name = {path.name: ids for path, ids in visible.items()}
    assert "s03_p1" in by_name["s03.xml"] and "E" not in by_name["s03.xml"]
    assert {"A", "B", "C", "D"} <= by_name["edition.xml"]
    assert "s04_exemplum" in by_name["s04_exemplum.xml"]


# --- Témoins d'une partie ------------------------------------------------------

def test_a_part_with_its_own_list_wit():
    assert part_witnesses((SERMONS / "s03.xml").read_text(encoding="utf-8"),
                          EDITION.read_text(encoding="utf-8")) == (["A", "C", "D", "E"], "part")


def test_a_fragment_takes_the_witnesses_cited_by_its_wit_attributes():
    assert part_witnesses((SERMONS / "s01.xml").read_text(encoding="utf-8"),
                          EDITION.read_text(encoding="utf-8")) == (["A", "B", "C"], "wit")


def test_the_locus_of_the_edition_tells_the_witnesses_of_a_part():
    edition = EDITION.read_text(encoding="utf-8").replace(
        "sermons 1 (f. 12r-13r)", 'sermons <locus from="12r" to="13r" target="#s01">1</locus>').replace(
        "sermons 1 (f. 2r-3r)", 'sermons <locus from="2r" to="3r" target="#s01_p1">1</locus>')
    assert part_witnesses((SERMONS / "s01.xml").read_text(encoding="utf-8"), edition) == (["A", "C"], "locus")


def test_the_incomplete_check_of_a_part_uses_its_own_witnesses():
    text = (SERMONS / "s01.xml").read_text(encoding="utf-8")
    ids, _source = part_witnesses(text, EDITION.read_text(encoding="utf-8"))
    root = etree.fromstring(text.encode("utf-8"))
    found = root.xpath(incomplete_app_xpath(ids), namespaces={"tei": "http://www.tei-c.org/ns/1.0"})
    assert [app.findtext("{http://www.tei-c.org/ns/1.0}lem") for app in found] == ["vigilantes"]
