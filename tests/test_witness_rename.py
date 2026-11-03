# -*- coding: utf-8 -*-
"""Changer le sigle d'un témoin (V0.9.4.0) : le plan des changements.

Le sigle P devient P2 (un nouveau manuscrit P1 a été trouvé). Le plan
(``witness_rename.plan_witness_rename``, sans Qt) dit tout ce qui change,
fichier par fichier, avant que rien ne soit écrit :

- project.xml : le témoin (identifiant, sigle, nom affiché), le pivot,
  les pivots des textes, le texte du viewer web, les paramètres des
  scénarios, les requêtes XPath, les chemins de ses fichiers ;
- les documents TEI du projet (l'édition, ses parties, les autres
  documents) : la déclaration du <witness>, chaque pointeur #P, les
  surfaces P-p0001… et leurs pointeurs, les chemins des <graphic> ;
- les JSON d'alignement : sigles de meta, surfaces, chemins des images ;
- les fichiers et dossiers nommés d'après le témoin, renommés.

Un sigle cité dans le texte (une note, un commentaire) n'est que signalé.
Un sigle pris, ou un identifiant déjà employé, est refusé."""
from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from corpus_data import TINY_PNG, copy_example
from project_config import load_project
from witness_rename import migrate_view_settings, plan_witness_rename

TEI = "http://www.tei-c.org/ns/1.0"

PROJECT = """<?xml version='1.0' encoding='utf-8'?>
<teiManuscriptProject version="1">
  <!-- commentaire gardé -->
  <title>Essai de sigles</title>
  <edition file="xml/edition.xml" />
  <webViewer outputDir="web_output" filename="viewer.html" text="witness" textWitness="P" />
  <witnesses base="T1">
    <witness id="T1" role="base" label="T1 · Troyes" alignment="alignments/T1.json" />
    <witness id="P" label="P · Paris" alignment="alignments/P.json">
      <images type="files">
        <image file="images/P/0001_1r.png" label="1r" surface="P-p0001" />
        <image file="images/P/0002_1v.png" label="1v" surface="P-p0002" />
        <image file="images/P/0003_2r.png" label="2r" surface="P-p0003" />
      </images>
      <alto type="files"><file file="alto/P/0001_1r.xml" label="1r" /></alto>
    </witness>
  </witnesses>
  <documents>
    <document file="xml/notes.xml" label="Notes" />
    <document file="xml/personnes.xml" label="Personnes" />
  </documents>
  <parts>
    <part name="s02" base="P" />
  </parts>
  <transformations>
    <scenario name="Critique" source="edition" engine="lxml" xslt="rendering/x.xsl" output="out.html">
      <param name="temoin-de-base" value="P" />
      <param name="titre" value="Paris" />
    </scenario>
  </transformations>
  <xpathQueries>
    <query name="Leçons de P">//rdg[contains(concat(' ', @wit, ' '), ' #P ')]</query>
  </xpathQueries>
</teiManuscriptProject>
"""

EDITION = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}" xmlns:xi="http://www.w3.org/2001/XInclude">
  <teiHeader>
    <fileDesc>
      <titleStmt><title>Essai</title></titleStmt>
      <sourceDesc>
        <listWit>
          <witness xml:id="T1">T1 · Troyes</witness>
          <witness xml:id="P">P · Paris</witness>
        </listWit>
      </sourceDesc>
    </fileDesc>
  </teiHeader>
  <facsimile>
    <surface xml:id="T1-p0001" n="1r"><graphic url="../images/T1/0001_1r.png"/></surface>
    <surface xml:id="P-p0001" n="1r"><graphic url="../images/P/0001_1r.png"/></surface>
    <surface xml:id="P-p0002" n="1v"><graphic url="../images/P/0002_1v.png"/>
      <zone xml:id="P-p0002-left"/><zone xml:id="P-p0002-right"/></surface>
    <surface xml:id="P-p0003" n="2r"><graphic url="../images/P/0003_2r.png"/></surface>
  </facsimile>
  <text>
    <body>
      <div xml:id="s01">
        <pb edRef="#T1" facs="#T1-p0001"/><pb edRef="#P" facs="#P-p0001"/>
        <p><lb edRef="#T1"/>Primum <app><lem wit="#T1">verbum</lem><rdg wit="#P">uerbum</rdg></app>
        <lb edRef="#P"/><pb edRef="#P" facs="#P-p0002-left"/>
        <note>leçon de P, corrigée</note> <!-- P à revoir --> P<lb edRef="#T1" break="no"/>raue</p>
      </div>
      <xi:include href="s02.xml"/>
    </body>
  </text>
</TEI>
"""

PART = f"""<?xml version="1.0" encoding="UTF-8"?>
<div xmlns="{TEI}" xml:id="s02">
  <pb edRef="P" facs="P-p0003"/>
  <p><lb edRef="#P"/>Secundum <app><rdg wit="#T1 #P">dictum</rdg></app></p>
</div>
"""

NOTES = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>Notes</title></titleStmt></fileDesc></teiHeader>
<text><body><p>Voir <ref target="edition.xml#P">le témoin</ref>.</p></body></text></TEI>
"""

PERSONS = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>Personnes</title></titleStmt></fileDesc></teiHeader>
<text><body><listPerson><person xml:id="P"><persName>Pierre</persName></person></listPerson>
<p><persName ref="#P">Pierre</persName></p></body></text></TEI>
"""


def _json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _project(tmp_path):
    root = tmp_path / "projet"
    (root / "xml").mkdir(parents=True)
    (root / "project.xml").write_text(PROJECT, encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(EDITION, encoding="utf-8")
    (root / "xml" / "s02.xml").write_text(PART, encoding="utf-8")
    (root / "xml" / "notes.xml").write_text(NOTES, encoding="utf-8")
    (root / "xml" / "personnes.xml").write_text(PERSONS, encoding="utf-8")
    for name in ("0001_1r.png", "0002_1v.png", "0003_2r.png"):
        (root / "images" / "P").mkdir(parents=True, exist_ok=True)
        (root / "images" / "P" / name).write_bytes(TINY_PNG)
    (root / "images" / "T1").mkdir(parents=True)
    (root / "images" / "T1" / "0001_1r.png").write_bytes(TINY_PNG)
    (root / "alto" / "P").mkdir(parents=True)
    (root / "alto" / "P" / "0001_1r.xml").write_text("<alto/>", encoding="utf-8")
    (root / "iiif").mkdir()
    (root / "iiif" / "P.manifest.json").write_text("{}", encoding="utf-8")
    meta = {"format": "tei-manuscript-alignment", "format_version": 1}
    _json(root / "alignments" / "T1.json", {"meta": dict(meta, witness="T1", base_witness="T1"),
                                            "pages": [{"id": "T1-1r", "lines": [{"line": 1}]}]})
    _json(root / "alignments" / "P.json", {
        "meta": dict(meta, witness="P", base_witness="T1", label="P"),
        "pages": [{"id": "P-1r", "tei_surface_id": "P-p0001",
                   "image": {"type": "file", "path": "images/P/0001_1r.png"},
                   "lines": [{"line": 1, "base_keys": ["T1-1r::1"]}]}]})
    _json(root / "alignments" / "s02" / "P.json", {"meta": dict(meta, witness="P", base_witness="P"),
                                                   "pages": [{"id": "P-2r", "lines": [{"line": 1}]}]})
    _json(root / "alignments" / "s02" / "T1.json", {"meta": dict(meta, witness="T1", base_witness="P"),
                                                    "pages": [{"id": "T1-9r", "lines": [{"line": 1}]}]})
    return root / "project.xml"


def _plan(project_xml, witness, siglum):
    return plan_witness_rename(load_project(project_xml), witness, siglum)


def _text(plan, path):
    path = Path(path).resolve()
    for change in plan.changes:
        if change.path == path:
            return change.text
    raise AssertionError(f"{path} n'est pas dans le plan")


def _keys(messages):
    return [message.key for message in messages]


def test_the_plan_renames_the_witness_in_every_file(tmp_path):
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    assert plan.problems == () and plan.ok
    assert (plan.old_id, plan.new_id, plan.old_siglum, plan.new_siglum) == ("P", "P2", "P", "P2")
    changed = {change.path.relative_to(root.resolve()).as_posix() for change in plan.changes}
    assert changed == {"project.xml", "xml/edition.xml", "xml/s02.xml", "xml/notes.xml",
                       "alignments/P.json", "alignments/s02/P.json", "alignments/s02/T1.json"}
    # Chaque changement ajoute « 2 » après un « P » : le reste du fichier,
    # commentaires et mise en forme compris, ne change pas.
    for change in plan.changes:
        assert "P2" not in change.original
        assert change.text.replace("P2", "P") == change.original, change.path
        assert change.count == change.text.count("P2") > 0, change.path

    project = _text(plan, project_xml)
    root_el = ET.fromstring(project.encode("utf-8"))
    witness = root_el.find("witnesses/witness[@id='P2']")
    assert witness is not None and witness.get("label") == "P2 · Paris"
    assert witness.get("alignment") == "alignments/P2.json" and witness.get("siglum") is None
    assert [(i.get("file"), i.get("surface")) for i in witness.iter("image")] == [
        ("images/P2/0001_1r.png", "P2-p0001"), ("images/P2/0002_1v.png", "P2-p0002"),
        ("images/P2/0003_2r.png", "P2-p0003")]
    assert witness.find("alto/file").get("file") == "alto/P2/0001_1r.xml"
    assert root_el.find("webViewer").get("textWitness") == "P2"
    assert root_el.find("parts/part").get("base") == "P2"
    assert [p.get("value") for p in root_el.iter("param")] == ["P2", "Paris"]
    assert root_el.find("xpathQueries/query").text == "//rdg[contains(concat(' ', @wit, ' '), ' #P2 ')]"
    assert "<!-- commentaire gardé -->" in project

    edition = _text(plan, root / "xml" / "edition.xml")
    assert '<witness xml:id="P2">P2 · Paris</witness>' in edition
    assert '<surface xml:id="P2-p0001" n="1r"><graphic url="../images/P2/0001_1r.png"/>' in edition
    assert '<zone xml:id="P2-p0002-left"/><zone xml:id="P2-p0002-right"/>' in edition
    assert '<pb edRef="#P" ' not in edition and '<pb edRef="#P2" facs="#P2-p0002-left"/>' in edition
    assert '<rdg wit="#P2">uerbum</rdg>' in edition and '<lb edRef="#T1"/>' in edition
    assert "<note>leçon de P, corrigée</note> <!-- P à revoir -->" in edition
    ET.fromstring(edition.encode("utf-8"))
    part = _text(plan, root / "xml" / "s02.xml")
    assert '<pb edRef="P2" facs="P2-p0003"/>' in part and 'wit="#T1 #P2"' in part
    assert 'target="edition.xml#P2"' in _text(plan, root / "xml" / "notes.xml")

    data = json.loads(_text(plan, root / "alignments" / "P.json"))
    # meta.label est un texte libre : il ne change pas.
    assert (data["meta"]["witness"], data["meta"]["base_witness"], data["meta"]["label"]) == ("P2", "T1", "P")
    assert data["pages"][0]["tei_surface_id"] == "P2-p0001"
    assert data["pages"][0]["image"]["path"] == "images/P2/0001_1r.png"
    assert json.loads(_text(plan, root / "alignments" / "s02" / "T1.json"))["meta"]["base_witness"] == "P2"

    moves = {(m.source.relative_to(root.resolve()).as_posix(), m.target.relative_to(root.resolve()).as_posix())
             for m in plan.moves}
    assert moves == {("alignments/P.json", "alignments/P2.json"),
                     ("alignments/s02/P.json", "alignments/s02/P2.json"),
                     ("images/P", "images/P2"), ("alto/P", "alto/P2"),
                     ("iiif/P.manifest.json", "iiif/P2.manifest.json")}
    assert plan.surfaces == {"P-p0001": "P2-p0001", "P-p0002": "P2-p0002", "P-p0003": "P2-p0003",
                             "P-p0002-left": "P2-p0002-left", "P-p0002-right": "P2-p0002-right"}


def test_a_siglum_cited_in_the_text_is_only_reported(tmp_path):
    project_xml = _project(tmp_path)
    plan = _plan(project_xml, "P", "P2")
    edition = (project_xml.parent / "xml" / "edition.xml").resolve()
    mentions = [(m.path, m.line, m.excerpt) for m in plan.mentions]
    line = next(n for n, text in enumerate(EDITION.splitlines(), 1) if "<note>leçon de P" in text)
    # « P<lb break="no"/>raue » est un mot (Praue), pas le sigle.
    assert [(path, number) for path, number, _ in mentions] == [(edition, line), (edition, line)]
    assert all("P" in excerpt for *_, excerpt in mentions)
    # Pierre (<person xml:id="P">) n'est pas le témoin : rien ne change dans
    # personnes.xml, et le plan le dit.
    persons = (project_xml.parent / "xml" / "personnes.xml").resolve()
    assert persons not in {change.path for change in plan.changes}
    assert [(n.key, n.values["element"]) for n in plan.notes] == [("witness_rename.other_target", "person")]


def test_the_changes_are_counted_per_file(tmp_path):
    project_xml = _project(tmp_path)
    plan = _plan(project_xml, "P", "P2")
    counts = {plan.display_path(change.path): dict(change.counts) for change in plan.changes}
    assert counts == {
        "project.xml": {"declaration": 2, "paths": 5, "surfaces": 3, "settings": 4},
        "xml/edition.xml": {"declaration": 2, "pointers": 4, "surfaces": 7, "paths": 3},
        "xml/s02.xml": {"pointers": 3, "surfaces": 1},
        "xml/notes.xml": {"pointers": 1},
        "alignments/P.json": {"declaration": 1, "surfaces": 1, "paths": 1},
        "alignments/s02/P.json": {"declaration": 2},
        "alignments/s02/T1.json": {"declaration": 1},
    }


def test_the_pivot_of_the_example_is_renamed(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    root = project_xml.parent
    plan = _plan(project_xml, "T1", "T0")
    assert plan.ok, plan.problems
    project = ET.fromstring(_text(plan, project_xml).encode("utf-8"))
    assert project.find("witnesses").get("base") == "T0"
    assert project.find("witnesses/witness[@id='T0']").get("alignment") == "alignments/T0.json"
    edition = _text(plan, root / "xml" / "edition.xml")
    original = (root / "xml" / "edition.xml").read_text(encoding="utf-8")
    assert "T0" not in original and edition.replace("T0", "T1") == original
    assert '"#T1"' not in edition and '<witness xml:id="T0">' in edition
    for name in ("T2.json", "P.json"):
        assert json.loads(_text(plan, root / "alignments" / name))["meta"]["base_witness"] == "T0"


def test_a_siglum_that_is_not_an_identifier_gets_an_idno(tmp_path):
    project_xml = copy_example(tmp_path / "exemple")
    root = project_xml.parent
    plan = _plan(project_xml, "P", "1761")
    assert plan.ok and (plan.new_id, plan.new_siglum) == ("_1761", "1761")
    witness = ET.fromstring(_text(plan, project_xml).encode("utf-8")).find("witnesses/witness[@id='_1761']")
    assert (witness.get("siglum"), witness.get("label")) == ("1761", "1761 · Paris, BnF, Latin 15940")
    # Fichier d'alignement nommé comme Varians le copie (alignments/1761.json).
    assert witness.get("alignment") == "alignments/1761.json"
    edition = _text(plan, root / "xml" / "edition.xml")
    assert '<witness xml:id="_1761"><idno type="siglum">1761</idno>Paris, BnF, Latin 15940</witness>' in edition
    assert 'edRef="#_1761"' in edition and 'edRef="#P"' not in edition


def test_only_the_siglum_changes_when_the_identifier_stays(tmp_path):
    project_xml = _project(tmp_path)
    root = project_xml.parent
    text = project_xml.read_text(encoding="utf-8").replace(
        '<witness id="P" label="P · Paris"', '<witness id="P" siglum="P*" label="P* · Paris"')
    project_xml.write_text(text, encoding="utf-8")
    edition = root / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace(
        '<witness xml:id="P">P · Paris</witness>', '<witness xml:id="P"><idno type="siglum">P*</idno>Paris</witness>'),
        encoding="utf-8")
    plan = _plan(project_xml, "P", "P")
    assert plan.ok and plan.new_id == "P" and plan.moves == () and plan.surfaces == {}
    assert {change.path.name for change in plan.changes} == {"project.xml", "edition.xml"}
    witness = ET.fromstring(_text(plan, project_xml).encode("utf-8")).find("witnesses/witness[@id='P']")
    assert (witness.get("siglum"), witness.get("label")) == (None, "P · Paris")
    assert '<witness xml:id="P"><idno type="siglum">P</idno>Paris</witness>' in _text(plan, edition)


@pytest.mark.parametrize("siglum, key", [
    ("", "witness_rename.empty"),
    ("  ", "witness_rename.empty"),
    ("P", "witness_rename.same"),
    ("T1", "witness_rename.taken"),
    ("t1", "witness_rename.taken"),          # mêmes noms de fichiers sous Windows
])
def test_a_siglum_already_taken_is_refused(tmp_path, siglum, key):
    plan = _plan(_project(tmp_path), "P", siglum)
    assert not plan.ok and _keys(plan.problems) == [key]


def test_an_unknown_witness_is_refused(tmp_path):
    plan = _plan(_project(tmp_path), "Q", "Q2")
    assert _keys(plan.problems) == ["witness_rename.unknown"]


def test_an_identifier_already_used_is_refused(tmp_path):
    project_xml = _project(tmp_path)
    part = project_xml.parent / "xml" / "s02.xml"
    part.write_text(PART.replace("<p>", '<p xml:id="P2">'), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.id_used"]
    assert (plan.problems[0].values["id"], plan.problems[0].values["element"]) == ("P2", "p")
    edition = project_xml.parent / "xml" / "edition.xml"
    part.write_text(PART, encoding="utf-8")
    edition.write_text(EDITION.replace('<div xml:id="s01">', '<div xml:id="P2-p0003">'), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.id_used"] and plan.problems[0].values["id"] == "P2-p0003"


def test_a_file_already_there_is_refused(tmp_path):
    project_xml = _project(tmp_path)
    _json(project_xml.parent / "alignments" / "s02" / "P2.json", {"meta": {}, "pages": []})
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.target_exists"]
    assert plan.problems[0].values["file"] == "alignments/s02/P2.json"


def test_a_malformed_document_to_change_is_refused(tmp_path):
    project_xml = _project(tmp_path)
    (project_xml.parent / "xml" / "s02.xml").write_text(PART.replace("</p>", ""), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.malformed"]
    assert plan.problems[0].values["file"] == "xml/s02.xml"


def test_a_case_only_change_is_planned(tmp_path):
    project_xml = _project(tmp_path)
    plan = _plan(project_xml, "P", "p")
    assert plan.ok, plan.problems
    assert ("alignments/P.json", "alignments/p.json") in {
        (m.source.relative_to(project_xml.parent.resolve()).as_posix(),
         m.target.relative_to(project_xml.parent.resolve()).as_posix()) for m in plan.moves}


class _Settings:
    """Réglages en mémoire, à la manière de QSettings."""

    def __init__(self, values):
        self.values = dict(values)

    def value(self, key, default=None):
        return self.values.get(key, default)

    def setValue(self, key, value):
        self.values[key] = value

    def remove(self, key):
        self.values.pop(key, None)

    def contains(self, key):
        return key in self.values


def test_the_view_settings_follow_the_witness():
    prefix = "projectView/abc/"
    other = "projectView/def/"
    settings = _Settings({
        prefix + "witnessOrder": json.dumps(["T1", "P", "T2"]),
        prefix + "visibleWitnesses": json.dumps(["P", "T1"]),
        prefix + "detachedWitnesses": json.dumps(["P"]),
        prefix + "witnessLeadsEdition": json.dumps({"T1": True, "P": False}),
        prefix + "witnessHeights": json.dumps({"P": 300, "T1": 200}),
        prefix + "gridSizes": json.dumps({"rows": [1, 2], "P": 400}),
        prefix + "floatingGeometry/P": b"geometry",
        prefix + "floatingAlwaysOnTop/P": True,
        other + "witnessOrder": json.dumps(["P"]),
    })
    migrate_view_settings(settings, prefix, "P", "P2")
    values = settings.values
    assert json.loads(values[prefix + "witnessOrder"]) == ["T1", "P2", "T2"]
    assert json.loads(values[prefix + "visibleWitnesses"]) == ["P2", "T1"]
    assert json.loads(values[prefix + "detachedWitnesses"]) == ["P2"]
    assert json.loads(values[prefix + "witnessLeadsEdition"]) == {"T1": True, "P2": False}
    assert json.loads(values[prefix + "witnessHeights"]) == {"P2": 300, "T1": 200}
    assert json.loads(values[prefix + "gridSizes"]) == {"rows": [1, 2], "P2": 400}
    assert values[prefix + "floatingGeometry/P2"] == b"geometry" and prefix + "floatingGeometry/P" not in values
    assert values[prefix + "floatingAlwaysOnTop/P2"] is True
    assert json.loads(values[other + "witnessOrder"]) == ["P"]


def test_the_messages_of_the_plan_exist_in_every_language():
    source = (Path(__file__).resolve().parents[1] / "witness_rename.py").read_text(encoding="utf-8")
    keys = set(re.findall(r'Message\(\s*"(witness_rename\.[\w.]+)"', source))
    assert {"witness_rename.empty", "witness_rename.same", "witness_rename.taken", "witness_rename.unknown",
            "witness_rename.id_used", "witness_rename.target_exists", "witness_rename.malformed",
            "witness_rename.other_target"} <= keys
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        root = ET.parse(Path(__file__).resolve().parents[1] / "i18n" / f"{language}.xml").getroot()
        assert keys <= {node.get("key") for node in root.findall("string")}, language


# --- Application (W.2) : tout ou rien -------------------------------------------------------

def _snapshot(root):
    """Contenu de tous les fichiers du dossier, par chemin relatif."""
    return {path.relative_to(root).as_posix(): path.read_bytes()
            for path in sorted(root.rglob("*")) if path.is_file()}


def test_the_plan_is_applied_in_one_block(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    result = apply_witness_rename(plan)
    renamed = {move.source: move.target for move in plan.moves}
    for change in plan.changes:
        assert renamed.get(change.path, change.path).read_text(encoding="utf-8") == change.text
        assert change.path.with_suffix(change.path.suffix + ".bak").read_text(encoding="utf-8") == change.original
    assert {m.source for m in result.moved} == {m.source for m in plan.moves}
    assert not (root / "images" / "P").exists() and (root / "images" / "P2" / "0001_1r.png").is_file()
    assert (root / "alignments" / "s02" / "P2.json").is_file() and not (root / "alignments" / "s02" / "P.json").exists()
    project = load_project(project_xml)
    witness = project.witness_by_id["P2"]
    assert witness.display_siglum == "P2" and witness.alignment == (root / "alignments" / "P2.json").resolve()
    assert [image.path for image in witness.image_files] == [
        (root / "images" / "P2" / name).resolve() for name in ("0001_1r.png", "0002_1v.png", "0003_2r.png")]
    assert all(image.path.is_file() for image in witness.image_files)
    assert project.parts[0].base == "P2" and project.web_text_witness == "P2"
    # Un second changement repart du projet modifié : P2 redevient P.
    plan = _plan(project_xml, "P2", "P")
    assert plan.ok, plan.problems
    apply_witness_rename(plan)
    assert (root / "xml" / "edition.xml").read_text(encoding="utf-8") == EDITION


def test_a_file_changed_since_the_preview_stops_everything(tmp_path):
    from witness_rename import RenameError, apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    edition = root / "xml" / "edition.xml"
    edition.write_text(EDITION.replace("Primum", "Primo"), encoding="utf-8")
    before = _snapshot(root)
    with pytest.raises(RenameError) as error:
        apply_witness_rename(plan)
    assert error.value.message.key == "witness_rename.changed"
    assert error.value.message.values["file"] == "xml/edition.xml"
    assert _snapshot(root) == before


def test_a_failure_while_writing_restores_every_file(tmp_path):
    from witness_rename import RenameError, apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    # Copies .bak d'enregistrements précédents : elles aussi sont retrouvées.
    (root / "project.xml.bak").write_text("copie précédente", encoding="utf-8")
    (root / "xml" / "edition.xml.bak").write_text("copie précédente", encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    last = plan.changes[-1].path
    before = _snapshot(root)
    last.chmod(0o444)
    try:
        with pytest.raises(RenameError) as error:
            apply_witness_rename(plan)
    finally:
        last.chmod(0o644)
    assert error.value.message.key == "witness_rename.failed"
    assert error.value.message.values["file"] == plan.display_path(last)
    assert _snapshot(root) == before


def test_a_failure_while_renaming_restores_every_file(tmp_path, monkeypatch):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    before = _snapshot(root)
    rename = witness_rename._rename
    calls = []

    def failing(move):
        calls.append(move)
        if len(calls) == 3:
            raise PermissionError(13, "Fichier ouvert dans un autre programme", str(move.source))
        rename(move)

    monkeypatch.setattr(witness_rename, "_rename", failing)
    with pytest.raises(witness_rename.RenameError) as error:
        witness_rename.apply_witness_rename(plan)
    assert error.value.message.key == "witness_rename.failed"
    assert "autre programme" in error.value.message.values["error"]
    assert _snapshot(root) == before
    assert not list(root.rglob("*P2*"))


def test_an_older_backup_gives_way_to_the_state_before_the_change(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    (root / "project.xml.bak").write_text("copie précédente", encoding="utf-8")
    apply_witness_rename(_plan(project_xml, "P", "P2"))
    assert (root / "project.xml.bak").read_text(encoding="utf-8") == PROJECT
    assert not [path for path in root.rglob("*") if "varians-rename" in path.name]


def test_a_case_only_change_is_applied(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    apply_witness_rename(_plan(project_xml, "P", "p"))
    names = {path.name for path in (root / "alignments").iterdir()}
    assert "p.json" in names and "P.json" not in names
    assert {path.name for path in (root / "images").iterdir()} == {"p", "T1"}
    assert load_project(project_xml).witness_by_id["p"].image_files[0].path.is_file()


def test_a_refused_plan_is_not_applied(tmp_path):
    from witness_rename import apply_witness_rename
    plan = _plan(_project(tmp_path), "P", "T1")
    with pytest.raises(ValueError):
        apply_witness_rename(plan)


# --- Sécurité des données (relecture avant la PR) ------------------------------------------

class _Crash(BaseException):
    """Arrêt brutal (Varians tué, coupure) : rien ne le rattrape."""


def test_an_interrupted_change_is_undone_at_the_next_opening(tmp_path, monkeypatch):
    import save_io
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    (root / "xml" / "edition.xml.bak").write_text("copie précédente", encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    before = _snapshot(root)
    write = save_io.atomic_write_text_with_backup
    calls = []

    def crash_on_the_fourth(path, text, **kwargs):
        calls.append(path)
        if len(calls) == 4:
            raise _Crash()
        return write(path, text, **kwargs)

    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", crash_on_the_fourth)
    with pytest.raises(_Crash):
        witness_rename.apply_witness_rename(plan)
    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", write)
    assert _snapshot(root) != before
    assert witness_rename.journal_path(root).is_file()
    # Pas de nouveau changement tant que l'interruption n'est pas réparée.
    assert _keys(_plan(project_xml, "T1", "T0").problems) == ["witness_rename.interrupted"]
    recovery = witness_rename.recover_interrupted_rename(root)
    assert (recovery.status, recovery.data["old"], recovery.data["new"], recovery.failed) == (
        "restored", "P", "P2", [])
    assert _snapshot(root) == before
    assert witness_rename.recover_interrupted_rename(root).status == "none"


def test_an_interruption_while_renaming_is_undone_too(tmp_path, monkeypatch):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    before = _snapshot(root)
    rename = witness_rename._rename
    calls = []

    def crash_on_the_third(move):
        calls.append(move)
        if len(calls) == 3:
            raise _Crash()
        rename(move)

    monkeypatch.setattr(witness_rename, "_rename", crash_on_the_third)
    with pytest.raises(_Crash):
        witness_rename.apply_witness_rename(plan)
    monkeypatch.setattr(witness_rename, "_rename", rename)
    recovery = witness_rename.recover_interrupted_rename(root)
    assert (recovery.status, recovery.failed) == ("restored", [])
    assert _snapshot(root) == before
    assert not list(root.rglob("*P2*"))


def test_the_project_is_checked_before_the_change_is_kept(tmp_path, monkeypatch):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    before = _snapshot(root)

    def unreadable(_plan):
        raise ValueError("project.xml illisible")

    monkeypatch.setattr(witness_rename, "_verify", unreadable)
    with pytest.raises(witness_rename.RenameError) as error:
        witness_rename.apply_witness_rename(plan)
    assert error.value.message.key == "witness_rename.failed"
    assert _snapshot(root) == before
    assert not witness_rename.journal_path(root).exists()


def test_a_damaged_alignment_file_is_refused_not_crashed(tmp_path):
    project_xml = _project(tmp_path)
    damaged = project_xml.parent / "alignments" / "s02" / "T1.json"
    damaged.write_text(damaged.read_text(encoding="utf-8").replace('"meta": {', '"meta": {,', 1), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.malformed"]
    assert plan.problems[0].values["file"] == "alignments/s02/T1.json"


def test_a_json_file_with_a_bom_keeps_it(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    path = project_xml.parent / "alignments" / "P.json"
    path.write_text("﻿" + path.read_text(encoding="utf-8"), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert plan.ok, plan.problems
    apply_witness_rename(plan)
    raw = (project_xml.parent / "alignments" / "P2.json").read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert json.loads(raw.decode("utf-8-sig"))["meta"]["witness"] == "P2"


def test_a_label_written_with_a_character_reference_is_left_whole(tmp_path):
    project_xml = _project(tmp_path)
    edition = project_xml.parent / "xml" / "edition.xml"
    edition.write_text(EDITION.replace('<witness xml:id="P">P · Paris</witness>',
                                       '<witness xml:id="P">&#80; · Paris</witness>'), encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert plan.ok, plan.problems
    assert '<witness xml:id="P2">&#80; · Paris</witness>' in _text(plan, edition)


def test_a_surface_stored_for_another_witness_is_an_identifier_in_use(tmp_path):
    project_xml = _project(tmp_path)
    text = project_xml.read_text(encoding="utf-8").replace(
        '<witness id="T1" role="base" label="T1 · Troyes" alignment="alignments/T1.json" />',
        '<witness id="T1" role="base" label="T1 · Troyes" alignment="alignments/T1.json">'
        '<images type="files"><image file="images/T1/0001_1r.png" label="1r" surface="P2-p0002" /></images>'
        '</witness>')
    project_xml.write_text(text, encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.id_used"]
    assert (plan.problems[0].values["id"], plan.problems[0].values["file"]) == ("P2-p0002", "project.xml")


# --- Relecture indépendante (avant la PR) ----------------------------------------------------

def _journal(root, data):
    import witness_rename
    path = witness_rename.journal_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def test_a_journal_pointing_outside_the_project_is_set_aside(tmp_path):
    """Un projet reçu (archive, dépôt) ne peut pas, par un faux journal,
    déplacer des fichiers hors de son dossier ni y attirer les vôtres."""
    import witness_rename
    home = tmp_path / "home"
    (home / "Documents" / "these").mkdir(parents=True)
    (home / "Documents" / "these" / "chapitre1.odt").write_bytes(b"des annees de travail")
    project = tmp_path / "projet-recu"
    project.mkdir()
    (project / "payload.desktop").write_text("[Desktop Entry]", encoding="utf-8")
    _journal(project, {"format": 1, "old": "P", "new": "P2", "files": [], "moves": [
        {"source": str(home / "autostart.desktop"), "target": "payload.desktop"},
        {"source": "documents-recuperes", "target": "../home/Documents"}]})
    recovery = witness_rename.recover_interrupted_rename(project)
    assert recovery.status == "rejected"
    assert (home / "Documents" / "these" / "chapitre1.odt").is_file()
    assert not (home / "autostart.desktop").exists() and (project / "payload.desktop").is_file()
    assert not witness_rename.journal_path(project).exists()
    assert (project / ".varians" / "witness-rename.rejected.json").is_file()


@pytest.mark.parametrize("data", [
    {"format": 1, "old": "P", "new": "P2"},
    {"format": 1, "old": "P", "new": "P2", "files": [{"path": "xml/edition.xml"}], "moves": []},
    {"format": 1, "old": "P", "new": "P2", "files": [], "moves": [{"source": "a/P", "target": "b/P2"}]},
    ["pas", "un", "journal"],
])
def test_a_damaged_journal_is_set_aside(tmp_path, data):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    before = _snapshot(root)
    _journal(root, data)
    assert witness_rename.recover_interrupted_rename(root).status == "rejected"
    rejected = root / ".varians" / "witness-rename.rejected.json"
    assert rejected.is_file()
    rejected.unlink()
    assert _snapshot(root) == before


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques")
def test_a_linked_images_folder_is_renamed_as_a_link(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    archive = tmp_path / "archive-des-images"
    (root / "images" / "P").rename(archive)
    (root / "images" / "P").symlink_to(archive, target_is_directory=True)
    apply_witness_rename(_plan(project_xml, "P", "P2"))
    assert (root / "images" / "P2").is_symlink() and not os.path.lexists(root / "images" / "P")
    assert sorted(x.name for x in archive.iterdir()) == ["0001_1r.png", "0002_1v.png", "0003_2r.png"]
    witness = load_project(project_xml).witness_by_id["P2"]
    assert all(image.path.is_file() for image in witness.image_files)


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques")
def test_the_same_file_under_two_names_is_changed_once(tmp_path):
    project_xml = _project(tmp_path)
    root = project_xml.parent
    (root / "xml" / "alias.xml").symlink_to(root / "xml" / "notes.xml")
    project_xml.write_text(project_xml.read_text(encoding="utf-8").replace(
        '<document file="xml/notes.xml" label="Notes" />',
        '<document file="xml/notes.xml" label="Notes" /><document file="xml/alias.xml" label="Alias" />'),
        encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert plan.ok, plan.problems
    assert [c.path.name for c in plan.changes].count("notes.xml") + [
        c.path.name for c in plan.changes].count("alias.xml") == 1


def test_a_failed_restore_keeps_the_copy_from_before_the_change(tmp_path, monkeypatch):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    notes = root / "xml" / "notes.xml"
    (root / "xml" / "notes.xml.bak").write_text("copie plus ancienne", encoding="utf-8")
    original = notes.read_text(encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    before = _snapshot(root)
    rename, replace = witness_rename._rename, os.replace
    calls = []

    def failing_rename(move):
        calls.append(move)
        if len(calls) == 3:
            raise PermissionError(13, "dossier ouvert ailleurs", str(move.source))
        rename(move)

    def locked(source, target):
        if str(source).endswith("notes.xml.bak") and str(target).endswith("notes.xml"):
            raise PermissionError(32, "fichier ouvert ailleurs", str(target))
        return replace(source, target)

    monkeypatch.setattr(witness_rename, "_rename", failing_rename)
    monkeypatch.setattr(os, "replace", locked)
    with pytest.raises(witness_rename.RenameError) as error:
        witness_rename.apply_witness_rename(plan)
    monkeypatch.setattr(os, "replace", replace)
    monkeypatch.setattr(witness_rename, "_rename", rename)
    assert error.value.message.key == "witness_rename.rollback_failed"
    # La copie d'avant le changement est toujours là…
    assert (root / "xml" / "notes.xml.bak").read_text(encoding="utf-8") == original
    # … et la reprise suivante remet tout, la copie plus ancienne comprise.
    assert witness_rename.recover_interrupted_rename(root).status == "restored"
    assert _snapshot(root) == before


NESTED_PROJECT = """<?xml version='1.0' encoding='utf-8'?>
<teiManuscriptProject version="1">
  <title>Familles</title>
  <edition file="xml/edition.xml" />
  <witnesses base="T1">
    <witness id="T1" label="T1 · Troyes" />
    <witness id="P" siglum="P*" label="P* · Paris" />
    <witness id="A" label="A · famille" />
  </witnesses>
</teiManuscriptProject>
"""

NESTED_EDITION = f"""<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>t</title></titleStmt>
<sourceDesc>
  <listWit>
    <witness xml:id="T1">T1 · Troyes</witness>
    <witness xml:id="A">A · famille
      <listWit>
        <witness xml:id="P"><idno type="siglum">P*</idno>Paris</witness>
      </listWit>
    </witness>
  </listWit>
</sourceDesc></fileDesc></teiHeader>
<text><body><p><app><lem wit="#T1">a</lem><rdg wit="#A">b</rdg><rdg wit="#P">c</rdg></app></p></body></text></TEI>
"""


def test_a_witness_inside_another_keeps_its_siglum(tmp_path):
    root = tmp_path / "projet"
    (root / "xml").mkdir(parents=True)
    (root / "project.xml").write_text(NESTED_PROJECT, encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(NESTED_EDITION, encoding="utf-8")
    plan = _plan(root / "project.xml", "A", "B")
    assert plan.ok, plan.problems
    edition = _text(plan, root / "xml" / "edition.xml")
    assert '<witness xml:id="P"><idno type="siglum">P*</idno>Paris</witness>' in edition
    assert '<witness xml:id="B"><idno type="siglum">B</idno>B · famille' not in edition
    assert '<witness xml:id="B">B · famille' in edition and 'wit="#B"' in edition


GREEK_PROJECT = """<?xml version='1.0' encoding='utf-8'?>
<teiManuscriptProject version="1">
  <title>Grec</title>
  <edition file="xml/edition.xml" />
  <witnesses base="α">
    <witness id="α" label="α · Vat. gr. 1" />
    <witness id="β" label="β · Par. gr. 2">
      <images type="iiif" manifest="https://example.org/beta/manifest.json" localCopy="true" />
    </witness>
  </witnesses>
</teiManuscriptProject>
"""


def test_a_cache_named_like_another_witness_is_left_to_it(tmp_path):
    """Les noms des caches IIIF sont en ASCII : α et β ont le même. Changer
    le sigle de α ne prend pas les images de β."""
    from iiif_local import store_dir
    from iiif_manifest import cache_path
    from witness_rename import apply_witness_rename
    root = tmp_path / "projet"
    (root / "xml").mkdir(parents=True)
    (root / "project.xml").write_text(GREEK_PROJECT, encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(
        f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>t</title></titleStmt><sourceDesc><listWit>'
        '<witness xml:id="α">α · Vat.</witness><witness xml:id="β">β · Par.</witness></listWit></sourceDesc>'
        '</fileDesc></teiHeader><text><body><p><app><lem wit="#α">a</lem><rdg wit="#β">b</rdg></app></p>'
        '</body></text></TEI>', encoding="utf-8")
    store = store_dir(root, "β")
    store.mkdir(parents=True)
    (store / "index.json").write_text("{}", encoding="utf-8")
    cache_path(root, "β").write_text("{}", encoding="utf-8")
    plan = _plan(root / "project.xml", "α", "α1")
    assert plan.ok and plan.moves == ()
    assert {note.key for note in plan.notes} == {"witness_rename.shared_kept"}
    apply_witness_rename(plan)
    assert (store / "index.json").is_file() and cache_path(root, "β").is_file()


def test_a_journal_that_cannot_be_deleted_does_not_undo_the_change(tmp_path, monkeypatch):
    import witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    plan = _plan(project_xml, "P", "P2")
    unlink = Path.unlink

    def locked(self, missing_ok=False):
        if self.name == "witness-rename.json":
            raise PermissionError(32, "fichier ouvert ailleurs", str(self))
        return unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", locked)
    witness_rename.apply_witness_rename(plan)
    monkeypatch.setattr(Path, "unlink", unlink)
    assert witness_rename.journal_path(root).is_file()
    # À l'ouverture suivante, le changement achevé est reconnu et gardé.
    assert witness_rename.recover_interrupted_rename(root).status == "completed"
    assert [w.id for w in load_project(project_xml).witnesses] == ["T1", "P2"]
    assert not witness_rename.journal_path(root).exists()


@pytest.mark.parametrize("declared", ["ISO-8859-1", "US-ASCII"])
def test_a_file_declaring_another_encoding_is_refused(tmp_path, declared):
    project_xml = _project(tmp_path)
    edition = project_xml.parent / "xml" / "edition.xml"
    text = EDITION.replace('encoding="UTF-8"', f'encoding="{declared}"')
    text = "".join(ch if ord(ch) < 128 else f"&#{ord(ch)};" for ch in text)
    edition.write_bytes(text.encode("ascii"))
    for siglum in ("P2", "P′", "Π"):
        plan = _plan(project_xml, "P", siglum)
        assert _keys(plan.problems) == ["witness_rename.encoding"], siglum
        assert plan.problems[0].values == {"file": "xml/edition.xml", "encoding": declared}


def test_every_path_into_a_renamed_folder_follows_it(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    root = project_xml.parent
    project_xml.write_text(project_xml.read_text(encoding="utf-8").replace(
        '<document file="xml/notes.xml" label="Notes" />',
        '<document file="xml/notes.xml" label="Notes" /><document file="alto/P/0001_1r.xml" label="ALTO" />'),
        encoding="utf-8")
    part = root / "xml" / "s02.xml"
    part.write_text(PART.replace('<pb edRef="P" facs="P-p0003"/>',
                                 '<pb edRef="P" facs="P-p0003"/><pb n="x" facs="../images/P/0002_1v.png"/>'
                                 '<figure><media mimeType="image/png" url="../images/P/0001_1r.png"/></figure>'
                                 '<ref target="../images/P/0003_2r.png">planche</ref>'), encoding="utf-8")
    apply_witness_rename(_plan(project_xml, "P", "P2"))
    assert all(document.path.is_file() for document in load_project(project_xml).documents)
    text = part.read_text(encoding="utf-8")
    for value in ("../images/P2/0002_1v.png", "../images/P2/0001_1r.png", "../images/P2/0003_2r.png"):
        assert f'"{value}"' in text and (part.parent / value).is_file(), value


def test_an_xml_document_outside_the_project_is_refused(tmp_path):
    project_xml = _project(tmp_path)
    shared = tmp_path / "commun"
    shared.mkdir()
    (shared / "commentaire.xml").write_text(
        f'<TEI xmlns="{TEI}"><text><body><p><rdg wit="#P">x</rdg></p></body></text></TEI>', encoding="utf-8")
    project_xml.write_text(project_xml.read_text(encoding="utf-8").replace(
        '<document file="xml/notes.xml" label="Notes" />',
        '<document file="xml/notes.xml" label="Notes" /><document file="../commun/commentaire.xml" label="C" />'),
        encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.external_file"]


def test_a_surface_shared_by_another_witness_follows(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    project_xml.write_text(project_xml.read_text(encoding="utf-8").replace(
        "  </witnesses>",
        '    <witness id="Pc" label="Pc · correcteur"><images type="files">'
        '<image file="images/P/0001_1r.png" label="1r" surface="P-p0001" /></images></witness>\n  </witnesses>'),
        encoding="utf-8")
    apply_witness_rename(_plan(project_xml, "P", "P2"))
    image = load_project(project_xml).witness_by_id["Pc"].image_files[0]
    assert image.surface_id == "P2-p0001" and image.path.is_file()


def test_a_pointer_meant_for_a_person_is_left_alone(tmp_path):
    project_xml = _project(tmp_path)
    notes = project_xml.parent / "xml" / "notes.xml"
    notes.write_text(NOTES.replace("</ref>.", '</ref>. Copié par <persName ref="#P">Pierre</persName>.'),
                     encoding="utf-8")
    plan = _plan(project_xml, "P", "P2")
    text = _text(plan, notes)
    assert 'target="edition.xml#P2"' in text and '<persName ref="#P">Pierre</persName>' in text


def test_two_witnesses_never_get_the_same_identifier(tmp_path):
    from witness_rename import apply_witness_rename
    project_xml = _project(tmp_path)
    stale = load_project(project_xml)               # la fenêtre ouverte avant l'ajout
    project_xml.write_text(project_xml.read_text(encoding="utf-8").replace(
        "  </witnesses>", '    <witness id="P2" label="P2 · Poitiers" />\n  </witnesses>'), encoding="utf-8")
    plan = plan_witness_rename(stale, "P", "P2")
    assert _keys(plan.problems) == ["witness_rename.taken"]


def test_a_character_reference_is_not_a_pointer(tmp_path):
    project_xml = _project(tmp_path)
    root = project_xml.parent
    text = project_xml.read_text(encoding="utf-8").replace(
        '<witness id="P" label="P · Paris"', '<witness id="xa" label="xa · Paris"').replace(
        '<param name="titre" value="Paris" />', '<param name="separateur" value="fin&#xa;debut" />')
    project_xml.write_text(text, encoding="utf-8")
    for path in (root / "xml" / "edition.xml", root / "xml" / "s02.xml", root / "xml" / "notes.xml"):
        path.write_text(path.read_text(encoding="utf-8").replace('"P"', '"xa"').replace("#P\"", '#xa"')
                        .replace("#P ", "#xa ").replace('edRef="P"', 'edRef="xa"'), encoding="utf-8")
    plan = _plan(project_xml, "xa", "xd")
    assert plan.ok, plan.problems
    assert 'value="fin&#xa;debut"' in _text(plan, project_xml)
