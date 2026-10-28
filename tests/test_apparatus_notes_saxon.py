# -*- coding: utf-8 -*-
"""Pré-passage « apparat en notes » (V0.9.2.7) : rendering/apparat-en-notes.xsl,
feuille TEI → TEI que les scénarios DOCX et ODT appliquent avant les TEI
Stylesheets. Chaque ``<app>`` devient sa leçon retenue (le lemme, sinon la
leçon du témoin choisi), suivie d'une note de bas de page
(``<note place="foot" type="apparatus">``) ; ses règles sont celles de la
feuille « Édition critique » (rendering/apparat-commun.xsl). Tests ignorés
sans Saxon."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from lxml import etree

from project_config import TransformScenario, load_project
from xslt_engines import run
from xslt_scenarios import VARIANS_PREFIX, saxon_available, scenario_request

DATA = Path(__file__).resolve().parent / "data" / "sermons"
TEI = "http://www.tei-c.org/ns/1.0"
NS = {"t": TEI}
pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")

SOURCE = f"""<TEI xmlns="{TEI}">
  <teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt><publicationStmt><p/></publicationStmt>
    <sourceDesc><listWit><witness xml:id="A">Paris</witness><witness xml:id="B">Rome</witness>
      <witness xml:id="C">Troyes</witness></listWit></sourceDesc></fileDesc></teiHeader>
  <text><body><div xml:id="d1"><p><pb edRef="#A" n="1r"/><pb edRef="#B" n="12v"/>Magna<lb edRef="#B" break="no"/>tes
    <app><rdg wit="#A">regem</rdg><rdg wit="#B #C"><seg xml:id="s1"><hi rend="italic" xml:id="h1">re</hi>ges</seg></rdg></app> <hi rend="italic">uiderunt</hi>
    <app><rdg wit="#A"/><rdg wit="#B">non</rdg></app> diem<lb edRef="#C"/><app><lem>mortis</lem><rdg wit="#A">sue <lb edRef="#A"/>mortis</rdg><rdgGrp><rdg wit="#B">mortes</rdg><rdg
      wit="#C">mortis sue</rdg></rdgGrp></app>
    <app><rdg wit="#A #B">et</rdg><rdg wit="#C"><lacunaStart/></rdg></app> fi <lb edRef="#A" break="no"/><lb edRef="#B"/>nis
    <app><rdg wit="#A #B">est</rdg><rdg wit="#C"><lacunaEnd/></rdg></app>.<note>Une note.</note>
    <note place="margin">En marge.</note></p></div></body></text>
</TEI>
"""


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(DATA, root)
    (root / "xml" / "essai.xml").write_text(SOURCE, encoding="utf-8")
    return load_project(root / "project.xml")


def _notes(project, witness=None, source="xml/essai.xml"):
    """Le TEI produit par le pré-passage, avec ``temoin-de-base=witness``."""
    params = () if witness is None else (("temoin-de-base", witness),)
    scenario = TransformScenario("Notes", VARIANS_PREFIX + "apparat-en-notes.xsl", "publications/notes.xml",
                                 source="file", file=source, engine="saxon", params=params)
    result = run(scenario_request(scenario, project))
    return result, (etree.parse(str(project.root_dir / "publications" / "notes.xml")) if result.ok else None)


def _text(element):
    return " ".join("".join(element.itertext()).split())


def _apparatus(tree):
    return [_text(note) for note in tree.iterfind(".//t:note[@type='apparatus']", NS)]


def test_each_app_becomes_its_reading_and_a_footnote(project):
    result, tree = _notes(project, "A")
    assert result.ok, result.error
    p = tree.find(".//t:body//t:p", NS)
    # Le texte de A, sans les sauts de ligne ni les balises de lacune.
    reading = " ".join("".join(t for t in p.xpath(".//text()[not(ancestor::t:note)]", namespaces=NS)).split())
    assert reading == "⟨1r⟩Magnates regem uiderunt diem mortis et finis est."
    assert _apparatus(tree) == [
        "regem ] reges B C",
        "non add. B",                                         # le texte établi omet : une addition
        "mortis ] sue mortis A ; mortes B ; mortis sue C",    # les leçons d'un rdgGrp comptent
        "et ] lacuna incipit C",
        "est ] lacuna desinit C",
    ]
    notes = tree.findall(".//t:note[@type='apparatus']", NS)
    assert {note.get("place") for note in notes} == {"foot"}
    # Les sigles en italique.
    sigla = notes[0].findall("t:hi", NS)[-1]
    assert (sigla.text, sigla.get("rend")) == ("B C", "italic")
    # La mise en forme d'une leçon est gardée dans sa note, sans ses identifiants.
    assert [hi.text for hi in notes[0].iterfind("t:hi", NS)] == ["re", "B C"]
    assert not notes[0].xpath(".//@xml:id")
    for name in ("app", "lb", "lacunaStart", "lacunaEnd", "rdg", "lem"):
        assert tree.find(f".//t:text//t:{name}", NS) is None, name


def test_only_the_pages_of_the_witness_are_kept_as_folio_marks(project):
    _result, tree = _notes(project, "A")
    assert tree.find(".//t:pb", NS) is None                   # pas de saut de page dans Word
    assert [seg.text for seg in tree.iterfind(".//t:seg[@type='folio']", NS)] == ["⟨1r⟩"]
    _result, tree = _notes(project, "B")
    assert [seg.text for seg in tree.iterfind(".//t:seg[@type='folio']", NS)] == ["⟨12v⟩"]


def test_the_notes_of_the_editor_become_endnotes(project):
    _result, tree = _notes(project, "A")
    editor = [(note.get("place"), _text(note)) for note in tree.iterfind(".//t:note", NS)
              if note.get("type") != "apparatus"]
    # Une note sans @place est une note de fin : une autre série que l'apparat.
    assert editor == [("end", "Une note."), ("margin", "En marge.")]


def test_another_witness_gives_another_text(project):
    result, tree = _notes(project, "#B")
    assert result.ok, result.error
    assert _apparatus(tree)[:2] == ["reges ] regem A", "non ] om. A"]
    # Sans valeur, le premier témoin déclaré.
    result, tree = _notes(project, "")
    assert result.ok and _apparatus(tree)[0] == "regem ] reges B C"


@pytest.mark.parametrize("witness, message", [
    ("Z", "Témoin inconnu : Z"),
    ("aucun", "4 apparat(s) sans lemme"),
])
def test_an_unknown_witness_or_missing_lemmas_stop_the_transformation(project, witness, message):
    result, _tree = _notes(project, witness)
    assert not result.ok and message in result.error + " ".join(detail for _code, detail in result.journal)
    assert not (project.root_dir / "publications" / "notes.xml").exists()


def test_the_lemmas_alone_establish_the_text_with_aucun(project):
    source = re.sub(r"<app><rdg wit=\"(#A[^\"]*)\">(\w+)</rdg>", r'<app><lem wit="\1">\2</lem>', SOURCE)
    source = source.replace('<app><rdg wit="#A"/>', '<app><lem wit="#A"/>')
    (project.root_dir / "xml" / "lemmes.xml").write_text(source, encoding="utf-8")
    result, tree = _notes(project, "aucun", "xml/lemmes.xml")
    assert result.ok, result.error
    assert _apparatus(tree)[0] == "regem ] reges B C"
    # Sans témoin choisi, tous les folios.
    assert [seg.text for seg in tree.iterfind(".//t:seg[@type='folio']", NS)] == ["⟨A : 1r⟩", "⟨B : 12v⟩"]


def test_the_spaces_between_two_elements_are_kept(project):
    # Les TEI Stylesheets perdent, dans Word, un texte fait d'espaces entre
    # deux éléments : le pré-passage le met dans un <seg>.
    _result, tree = _notes(project, "A")
    note = tree.find(".//t:note[@type='apparatus']", NS)
    space = note.getnext()
    assert etree.QName(space).localname == "seg" and space.text == " " and space.get("type") is None
    assert etree.QName(space.getnext()).localname == "hi" and space.getnext().text == "uiderunt"
    # Plus d'espaces doubles dans le texte établi.
    assert not [t for t in tree.xpath("//t:body//text()", namespaces=NS) if "  " in t]


def test_a_note_call_follows_its_word_without_double_spaces(project):
    source = SOURCE.replace("<note>Une note.</note>",
                            '<note>Une note.</note> Egyptii <app><rdg wit="#A"/><rdg wit="#B">enim</rdg></app> sunt'
                            ' <hi rend="italic"><lb edRef="#B"/>uos</hi> permansistis <app><rdg wit="#A"/>'
                            '<rdg wit="#B">mecum</rdg></app>, etc.')
    (project.root_dir / "xml" / "espaces.xml").write_text(source, encoding="utf-8")
    result, tree = _notes(project, "A", "xml/espaces.xml")
    assert result.ok, result.error
    p = tree.find(".//t:body//t:p", NS)
    marked = "".join(("¹" if node.get("type") == "apparatus" else "")
                     if isinstance(node, etree._Element) else str(node)
                     for node in p.xpath(".//text()[not(ancestor::t:note)] | .//t:note", namespaces=NS))
    assert "Egyptii¹ sunt uos permansistis¹, etc." in marked


def test_no_note_is_left_inside_another_note(project):
    # Word et LibreOffice n'admettent pas une note dans une note : une note
    # dans une note devient « (…) », un apparat garde sa leçon et son entrée
    # entre crochets.
    source = SOURCE.replace("<note>Une note.</note>",
                            '<note>Une note <note>interne</note> sur <app><rdg wit="#A">hoc</rdg><rdg wit="#B">hic'
                            '</rdg></app>.</note>')
    (project.root_dir / "xml" / "imbriquees.xml").write_text(source, encoding="utf-8")
    result, tree = _notes(project, "A", "xml/imbriquees.xml")
    assert result.ok, result.error
    assert not tree.xpath("//t:note[ancestor::t:note]", namespaces=NS)
    end = tree.find(".//t:note[@place='end']", NS)
    assert _text(end) == "Une note (interne) sur hoc [hoc ] hic B]."
