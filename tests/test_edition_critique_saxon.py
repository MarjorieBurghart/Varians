# -*- coding: utf-8 -*-
"""Feuille « Édition critique » (V0.9.2.7) : rendering/edition-critique.xsl,
d'après le kit XSLT 3.0 « édition critique TEI », retouchée. Cas du kit
(tests/data/edition_critique, d'après son TESTS_XSLT.md), puis un test par
retouche, puis le scénario prédéfini sur le jeu d'essai « sermons ». Tests
ignorés sans Saxon."""
from __future__ import annotations

import re
import shutil
from pathlib import Path

import pytest
from lxml import html as lxml_html

from project_config import TransformScenario, load_project
from transform_worker import run_in_process
from xslt_engines import run
from xslt_scenarios import VARIANS_PREFIX, predefined_scenarios, saxon_available, scenario_request

TESTS = Path(__file__).resolve().parent / "data"
TEI = "http://www.tei-c.org/ns/1.0"
pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


@pytest.fixture
def project(tmp_path):
    root = tmp_path / "sermons"
    shutil.copytree(TESTS / "sermons", root)
    for path in (TESTS / "edition_critique").iterdir():
        shutil.copy2(path, root / "xml" / f"kit_{path.name}")
    return load_project(root / "project.xml")


def _edition(project, source, witness=None, **params):
    """Le HTML de la feuille sur ``xml/<source>`` : (résultat, arbre)."""
    values = (() if witness is None else (("temoin-de-base", witness),)) + tuple(params.items())
    scenario = TransformScenario("Critique", VARIANS_PREFIX + "edition-critique.xsl", "publications/critique.html",
                                 source="file", file=f"xml/{source}", engine="saxon", params=values)
    result = run(scenario_request(scenario, project))
    output = project.root_dir / "publications" / "critique.html"
    return result, (lxml_html.fromstring(output.read_text(encoding="utf-8")) if result.ok else None)


def _text(element):
    return " ".join(element.text_content().split())


def _main(tree):
    """Le texte établi, sans les appels de note ni les folios."""
    main = tree.find(".//main")
    for mark in main.xpath(".//sup[contains(@class, 'appel')] | .//span[@class='folio']"):
        mark.drop_tree()
    return [_text(p) for p in main.iter("p")]


def _entries(tree, kind="apparat"):
    """Les entrées d'une liste (``apparat`` ou ``notes``) : (repère, texte)."""
    return [(_text(li.find_class("repere")[0]), _text(li.find_class("entree")[0]).removesuffix("↩").strip())
            for li in tree.xpath(f"//aside//ol[contains(@class, '{kind}')]/li")]


# --- Cas du kit (TESTS_XSLT.md) ---------------------------------------------------------------

def test_the_example_with_lemmas(project):
    result, tree = _edition(project, "kit_edition.xml")
    assert result.ok, result.error
    assert [_text(h) for h in tree.find_class("titre-division")] == ["Lorem ipsum — prose", "Lorem ipsum — vers"]
    assert len(tree.find_class("strophe")) == 2 and len(tree.find_class("titre-strophe")) == 2
    assert [_text(n) for n in tree.find_class("vers-numero")] == ["1", "2", "3", "4", "5"]
    assert tree.find_class("cesure") and tree.find_class("folio")
    prose, second = _main(tree)[:2]
    assert prose.startswith("Lorem ipsum dolor sit amet") and second.startswith("Sed do eiusmod tempor")
    assert ("1", "ipsum ] ipsam B") in _entries(tree) and ("2", "breve add. B") in _entries(tree)
    # Le lemme du deuxième vers (B) prime sur A, premier témoin de listWit.
    assert "consectetur adipiscing elit," in _text(tree.find(".//main"))
    assert ("1", "adipiscing ] adipiscens A") in _entries(tree)
    # Les sigles, après la leçon, en italique.
    assert [_text(i) for i in tree.xpath("(//ol[contains(@class, 'apparat')]/li)[1]//i[contains(@class, 'temoin')]")] == ["B"]
    # « aucun » : le même texte établi, tous les apparats ayant un lemme.
    _result, eclectic = _edition(project, "kit_edition.xml", "aucun")
    assert _main(eclectic) == _main(tree)


@pytest.mark.parametrize("witness, expected", [
    (None, "Lorem ipsum dolor sit amet."),
    ("B", "Lorem ipsam dolor breve sit amet."),
    ("#B", "Lorem ipsam dolor breve sit amet."),
])
def test_the_example_without_lemmas_follows_the_chosen_witness(project, witness, expected):
    result, tree = _edition(project, "kit_edition_sans_lem.xml", witness)
    assert result.ok, result.error
    assert _main(tree) == [expected]


@pytest.mark.parametrize("witness, message", [("aucun", "2 apparat(s) sans lemme"), ("Z", "Témoin inconnu : Z")])
def test_aucun_without_lemmas_or_an_unknown_witness_is_refused(project, witness, message):
    result, _tree = _edition(project, "kit_edition_sans_lem.xml", witness)
    assert not result.ok and message in result.error + " ".join(detail for _code, detail in result.journal)


# --- Retouches ----------------------------------------------------------------------------------

def _write(project, name, body, witnesses=("A", "B", "C")):
    listwit = "".join(f'<witness xml:id="{w}">Témoin {w}</witness>' for w in witnesses)
    (project.root_dir / "xml" / name).write_text(
        f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt>'
        f'<publicationStmt><p/></publicationStmt><sourceDesc><listWit>{listwit}</listWit></sourceDesc>'
        f'</fileDesc></teiHeader><text><body>{body}</body></text></TEI>', encoding="utf-8")
    return name


def test_a_division_without_head_is_titled_by_its_n_only(project):
    name = _write(project, "titres.xml", '<div xml:id="RLS_184" n="Sermo 1"><p>a</p></div>'
                                         '<div xml:id="pr" type="prologue"><p>b</p></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    assert [_text(h) for h in tree.find_class("titre-division")] == ["Sermo 1"]


def test_only_the_pages_of_the_chosen_witness_are_shown(project):
    name = _write(project, "folios.xml", '<div><p><pb n="0"/><pb edRef="#A" n="1r"/>un <pb edRef="#B #C" n="12v"/>'
                                         'deux</p></div>')
    assert [_text(f) for f in _edition(project, name)[1].find_class("folio")] == ["⟨0⟩", "⟨1r⟩"]
    assert [_text(f) for f in _edition(project, name, "C")[1].find_class("folio")] == ["⟨0⟩", "⟨12v⟩"]
    _result, tree = _edition(project, name, **{"montrer-folios": "false"})
    assert not tree.find_class("folio")


def test_the_pages_of_all_witnesses_are_shown_with_aucun(project):
    name = _write(project, "folios.xml", '<div><p><pb edRef="#A" n="1r"/>un <pb edRef="#B #C" n="12v"/>deux</p></div>')
    result, tree = _edition(project, name, "aucun")
    assert result.ok, result.error
    assert [_text(f) for f in tree.find_class("folio")] == ["⟨A : 1r⟩", "⟨B C : 12v⟩"]


def test_a_lacuna_is_named_in_the_apparatus(project):
    name = _write(project, "lacunes.xml", '<div><p>et <app><rdg wit="#A #B">fuit</rdg><rdg wit="#C"><lacunaStart/>'
                                          '</rdg></app> diu <app><rdg wit="#A #B">sic</rdg><rdg wit="#C">'
                                          '<lacunaEnd/></rdg></app> finis</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _entries(tree) == [("1", "fuit ] lacuna incipit C"), ("2", "sic ] lacuna desinit C")]
    assert _main(tree) == ["et fuit diu sic finis"]


def test_the_words_of_the_editor_in_the_apparatus_are_in_italics(project):
    # Tout texte de l'apparat qui ne vient pas d'un témoin est en italique :
    # sigles, om., add., lacuna incipit / desinit, leçon non disponible ;
    # les leçons restent en romain.
    name = _write(project, "mentions.xml", '<div><p>et <app><rdg wit="#A">fuit</rdg><rdg wit="#B"/><rdg wit="#C">'
                                           '<lacunaStart/></rdg></app> <app><rdg wit="#A"/><rdg wit="#B">breue</rdg>'
                                           '</app> diu <app><rdg wit="#B">sic</rdg><rdg wit="#C"><lacunaEnd/></rdg>'
                                           '</app> finis</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    entries = tree.xpath("//aside//ol[contains(@class, 'apparat')]/li//span[@class='entree']")
    italics = [[" ".join(i.text_content().split()) for i in entry.iter("i")] for entry in entries]
    assert italics == [["om.", "B", "lacuna incipit", "C"], ["add.", "B"],
                       ["[lecture du témoin non disponible]", "B", "lacuna desinit", "C"]]
    roman = [" ".join("".join(entry.xpath(".//text()[not(ancestor::i) and not(ancestor::a)]")).split())
             for entry in entries]
    assert roman == ["fuit ] ;", "breue", "] sic ;"]


def test_the_readings_of_the_apparatus_are_in_roman_and_a_sic_is_marked(project):
    # Dans l'apparat, une leçon est en romain, même un <sic>, une citation ou
    # une mise en relief ; un <sic> y est suivi de « sic » en italique. Le
    # texte établi garde ses styles.
    name = _write(project, "romain.xml", '<div><p>et <app><rdg wit="#A">ministerium</rdg><rdg wit="#B">ministerium '
                                         '<sic>corelectionis</sic></rdg></app> <app><rdg wit="#A"><quote>Uos estis'
                                         '</quote></rdg><rdg wit="#B"><hi rend="italic">Uos</hi> <title>estis</title>'
                                         '</rdg></app> finis</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _entries(tree) == [("1", "ministerium ] ministerium corelectionis sic B"), ("2", "Uos estis ] Uos estis B")]
    entries = tree.xpath("//aside//ol[contains(@class, 'apparat')]/li//span[@class='entree']")
    assert [[_text(i) for i in entry.iter("i")] for entry in entries] == [["sic", "B"], ["B"]]
    styled = [element.get("class") for entry in entries for element in entry.iter()
              if {"sic", "citation", "italique"} & set((element.get("class") or "").split())]
    assert styled == []
    assert [_text(span) for span in tree.xpath("//main//span[contains(@class, 'citation')]")] == ["Uos estis"]


def test_the_apparatus_and_the_notes_are_two_series(project):
    # L'apparat, nombreux, appelé par des chiffres ; les notes par des lettres.
    apps = "".join(f'<app><rdg wit="#A">u{i}</rdg><rdg wit="#B">v{i}</rdg></app> ' for i in range(3))
    notes = "".join(f'<note>Note {i}.</note> ' for i in range(28))
    name = _write(project, "series.xml", f'<div n="I"><p>{apps}{notes}fin</p></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    calls = [_text(sup) for sup in tree.xpath("//main//sup[contains(@class, 'appel')]")]
    assert calls[:3] == ["1", "2", "3"] and calls[3:6] == ["a", "b", "c"] and calls[28:] == ["z", "aa", "ab"]
    assert [_text(h) for h in tree.xpath("//aside//h3")] == ["Apparat critique", "Notes"]
    assert _entries(tree) == [("1", "u0 ] v0 B"), ("2", "u1 ] v1 B"), ("3", "u2 ] v2 B")]
    assert _entries(tree, "notes")[:2] == [("a", "Note 0."), ("b", "Note 1.")]
    assert _entries(tree, "notes")[27] == ("ab", "Note 27.")
    # Chaque appel mène à son entrée, et l'entrée à son appel.
    for link in tree.xpath("//main//sup[contains(@class, 'appel')]/a"):
        target = link.get("href")[1:]
        assert tree.get_element_by_id(target).xpath(f".//a[@href='#{link.get('id')}']")


def test_the_readings_of_a_rdggrp_count(project):
    name = _write(project, "groupes.xml", '<div><p><app><lem>mortis</lem><rdg wit="#A">sue mortis</rdg><rdgGrp>'
                                          '<rdg wit="#B">mortes</rdg><rdg wit="#C">mortis sue</rdg></rdgGrp></app>'
                                          '</p></div>')
    _result, tree = _edition(project, name)
    assert _entries(tree) == [("1", "mortis ] sue mortis A ; mortes B ; mortis sue C")]


def test_the_numbers_stay_in_their_column_and_the_wording_is_varians(project):
    _result, tree = _edition(project, "kit_edition.xml")
    style = tree.find(".//style").text
    assert re.search(r"\.appareil li \{[^}]*display:\s*grid", style)
    assert "text-indent:-2.5em" not in style
    text = (Path(__file__).resolve().parents[1] / "rendering" / "edition-critique.xsl").read_text(encoding="utf-8")
    for word in ("témoin de base", "sermon", "OCR"):
        assert word not in text.lower() and word not in tree.text_content().lower(), word


def test_line_breaks_of_several_witnesses_are_one_break(project):
    name = _write(project, "lignes.xml", '<div><p>fi <lb edRef="#A" break="no"/><lb edRef="#B"/>nis et '
                                         '<lb edRef="#B"/>alter</p></div>')
    assert _main(_edition(project, name)[1]) == ["finis et alter"]
    tree = _edition(project, name, "B", **{"sauts-lb": "true"})[1]
    assert len(tree.xpath("//main//br")) == 1


# --- Scénario prédéfini -------------------------------------------------------------------------

def test_a_list_is_numbered_by_its_rend_or_its_type_and_titled_before_it(project):
    """V0.9.2.9 : une liste est numérotée si @rend contient « numbered » ou
    si @type vaut « ordered » ou « numbered », comme dans la feuille de
    l'aperçu ; son <head> est placé avant elle, hors de la liste HTML."""
    name = _write(project, "listes.xml", '<div><p>x</p><list rend="numbered"><head>Index</head><item>a</item></list>'
                                         '<list type="ordered"><item>b</item></list>'
                                         '<list rend="bulleted"><item>c</item></list></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    main = tree.find(".//main")
    lists = [(element.tag, [_text(li) for li in element.iter("li")])
             for element in main.xpath(".//*[contains(@class, 'liste-tei')]")]
    assert lists == [("ol", ["a"]), ("ol", ["b"]), ("ul", ["c"])]
    head = next(h for h in main.iter("h3") if _text(h) == "Index")
    assert head.getparent().tag not in ("ol", "ul") and head.getnext().tag == "ol"


def test_a_table_has_its_caption_its_header_cells_and_its_merged_cells(project):
    """V0.9.3.0 : le <head> d'un tableau est sa légende ; une cellule
    @role="label", ou d'une ligne @role="label", est un en-tête ; @cols et
    @rows fusionnent les cellules, comme dans la feuille de l'aperçu."""
    name = _write(project, "tableau.xml", '<div><p>x</p><table><head>Tabula</head>'
                                          '<row role="label"><cell>Nomen</cell><cell>Folium</cell></row>'
                                          '<row><cell role="label">Petrus</cell><cell cols="2" rows="2">12r</cell>'
                                          '</row></table></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    table = tree.find(".//main").xpath(".//table")[0]
    assert [_text(caption) for caption in table.xpath("caption")] == ["Tabula"]
    assert [[(cell.tag, _text(cell), cell.get("colspan"), cell.get("rowspan")) for cell in row]
            for row in table.xpath(".//tr")] == [[("th", "Nomen", None, None), ("th", "Folium", None, None)],
                                                 [("th", "Petrus", None, None), ("td", "12r", "2", "2")]]
    assert not table.xpath(".//h3")


def test_the_reference_of_a_biblical_quotation_is_in_angle_brackets_the_others_are_notes(project):
    """V0.9.3.0 : le <ref> d'une <cit type="bible"> suit la citation entre
    chevrons ; celui d'une autre <cit> est une note de l'éditeur, appelée
    par une lettre dans la même série que les <note> ; un <ref> hors d'une
    <cit> ne change pas."""
    name = _write(project, "citations.xml",
                  '<div><p>Dixit <cit type="bible"><quote>Uos estis</quote><ref>Lc. 22:28</ref></cit> et '
                  '<cit><quote>Ait Augustinus</quote><ref>Aug. Conf. 1</ref></cit> '
                  'uidelicet<note>Nota editoris</note> <ref target="#x">alia</ref>.</p></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    main = tree.find(".//main")
    assert [_text(sup) for sup in main.xpath(".//sup[contains(@class, 'appel-note')]")] == ["a", "b"]
    assert _entries(tree, "notes") == [("a", "Aug. Conf. 1"), ("b", "Nota editoris")]
    assert _main(tree) == ["Dixit Uos estis <Lc. 22:28> et Ait Augustinus uidelicet alia."]


def test_a_speech_has_its_speaker_and_a_stage_direction_between_two_blocks_is_a_block(project):
    """V0.9.3.1 : chaque réplique est un bloc, son locuteur en tête ; une
    didascalie est entre parenthèses, en italique : un bloc entre deux
    blocs (entre deux répliques, deux vers), dans la phrase sinon."""
    name = _write(project, "scene.xml",
                  '<div><head>Scena prima</head><stage>Intrat Hamletus.</stage>'
                  '<sp who="#h"><speaker>HAMLETUS</speaker><lg><l>Esse aut non esse,</l><stage>ridet</stage>'
                  '<l>haec quaestio.</l></lg></sp>'
                  '<sp who="#o"><speaker>OPHELIA</speaker><p>Domine <stage>susurrat</stage> quomodo uales?</p>'
                  '<stage>Exit.</stage></sp></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    main = tree.find(".//main")
    speeches = main.find_class("discours")
    assert [[_text(e) for e in sp.find_class("locuteur")] for sp in speeches] == [["HAMLETUS"], ["OPHELIA"]]
    assert [(e.tag, _text(e)) for e in main.find_class("didascalie")] == [
        ("div", "(Intrat Hamletus.)"), ("div", "(ridet)"), ("span", "(susurrat)"), ("div", "(Exit.)")]
    assert [_text(e) for e in speeches[0].find_class("vers")] == ["Esse aut non esse,", "haec quaestio."]


def test_the_parentheses_of_a_stage_direction_hug_its_text(project):
    name = _write(project, "scene-blancs.xml", '<div><sp><speaker>A</speaker><p>Ita <stage>\n  ridet\n</stage> est.</p>'
                                               '<stage>\n    Exeunt\n  </stage></sp></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    assert [e.text_content() for e in tree.find(".//main").find_class("didascalie")] == ["(ridet)", "(Exeunt)"]


def test_the_predefined_scenario_publishes_the_edition_of_the_project(project):
    scenario = next(s for s in predefined_scenarios() if s.name == "edition-critique")
    result = run_in_process(scenario_request(scenario, project), timeout=120)
    assert result.ok, result.error
    output = project.root_dir / "publications" / "edition-critique.html"
    assert result.outputs == [str(output)]
    tree = lxml_html.fromstring(output.read_text(encoding="utf-8"))
    assert "Sermo in adventu Domini" in _text(tree)
    # Le témoin pivot du projet (A) : son texte, et les variantes en apparat.
    assert [_text(i) for i in tree.xpath("//p[@class='chapeau']/i")] == ["A"]
    assert "significant ] signant B" in [entry for _mark, entry in _entries(tree)]
