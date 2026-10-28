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
    assert ("a", "ipsum ] ipsam B") in _entries(tree) and ("b", "breve add. B") in _entries(tree)
    # Le lemme du deuxième vers (B) prime sur A, premier témoin de listWit.
    assert "consectetur adipiscing elit," in _text(tree.find(".//main"))
    assert ("a", "adipiscing ] adipiscens A") in _entries(tree)
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
    assert _entries(tree) == [("a", "fuit ] lacuna incipit C"), ("b", "sic ] lacuna desinit C")]
    assert _main(tree) == ["et fuit diu sic finis"]


def test_the_apparatus_and_the_notes_are_two_series(project):
    apps = "".join(f'<app><rdg wit="#A">u{i}</rdg><rdg wit="#B">v{i}</rdg></app> ' for i in range(28))
    name = _write(project, "series.xml", f'<div n="I"><p>{apps}<note>Première note.</note> fin'
                                         f'<note>Seconde.</note></p></div>')
    result, tree = _edition(project, name)
    assert result.ok, result.error
    calls = [_text(sup) for sup in tree.xpath("//main//sup[contains(@class, 'appel')]")]
    assert calls[:3] == ["a", "b", "c"] and calls[25:28] == ["z", "aa", "ab"] and calls[28:] == ["1", "2"]
    assert [_text(h) for h in tree.xpath("//aside//h3")] == ["Apparat critique", "Notes"]
    assert _entries(tree)[27] == ("ab", "u27 ] v27 B")
    assert _entries(tree, "notes") == [("1", "Première note."), ("2", "Seconde.")]
    # Chaque appel mène à son entrée, et l'entrée à son appel.
    for link in tree.xpath("//main//sup[contains(@class, 'appel')]/a"):
        target = link.get("href")[1:]
        assert tree.get_element_by_id(target).xpath(f".//a[@href='#{link.get('id')}']")


def test_the_readings_of_a_rdggrp_count(project):
    name = _write(project, "groupes.xml", '<div><p><app><lem>mortis</lem><rdg wit="#A">sue mortis</rdg><rdgGrp>'
                                          '<rdg wit="#B">mortes</rdg><rdg wit="#C">mortis sue</rdg></rdgGrp></app>'
                                          '</p></div>')
    _result, tree = _edition(project, name)
    assert _entries(tree) == [("a", "mortis ] sue mortis A ; mortes B ; mortis sue C")]


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
