# -*- coding: utf-8 -*-
"""Red team 2 (cohérence) : « Édition critique », la référence choisie par
l'utilisatrice, ne perd rien de ce que disent les autres sorties.

- C7 : un apparat dans une note gardait sa seule leçon : sa leçon, puis
  son entrée entre crochets, comme dans le DOCX.
- C8 : un <pb> du témoin choisi dans une leçon non retenue était perdu :
  son folio est montré (avant le texte de l'apparat s'il précède tout texte
  de sa leçon, sinon après).
- C13 : <hi> exposant, indice, petites capitales ; « italic bold » est
  italique et gras (un seul rendu était gardé).
- C15 : « Préliminaires », « Annexes » et « éd. » dans la langue demandée.
- La note d'un lemme a son appel dans le texte : elle n'est plus répétée
  dans l'entrée de l'apparat. Tests ignorés sans Saxon."""
from __future__ import annotations

import pytest

from test_edition_critique_saxon import _catalog, _edition, _entries, _text, _write, project  # noqa: F401
from xslt_scenarios import saxon_available

pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


def _paragraph(tree):
    """Le texte du premier paragraphe, appels (« [1] », « [a] ») et folios compris."""
    p = tree.find(".//main").find(".//p")
    for call in p.xpath(".//sup[contains(@class, 'appel')]"):
        call.text, call.tail = f"[{_text(call)}]", call.tail
        for child in list(call):
            call.remove(child)
    return _text(p)


def test_an_apparatus_in_a_note_keeps_its_entry_in_brackets(project):
    name = _write(project, "note.xml", '<div><p>Lorem<note>Vide <app><lem wit="#A">alibi</lem>'
                                       '<rdg wit="#B">ibi</rdg></app> infra.</note> ipsum.</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _entries(tree, "notes") == [("a", "Vide alibi [alibi ] ibi B] infra.")]


@pytest.mark.parametrize("witness, expected", [
    ("A", "Lorem ⟨3r⟩ipsum dolor[1]⟨2r⟩ sit amet."),
    ("B", "Lorem ipsum dolor[1]⟨7v⟩ sit amet."),            # un folio de B, même dans la leçon de C
    ("aucun", "Lorem ⟨A : 3r⟩ipsum dolor[1]⟨A : 2r⟩⟨B : 7v⟩ sit amet."),
])
def test_a_folio_of_the_chosen_witness_in_a_reading_not_kept_is_shown(project, witness, expected):
    name = _write(project, "folios.xml", '<div><p>Lorem <app><lem wit="#B #C">ipsum dolor</lem>'
                                         '<rdg wit="#A"><pb edRef="#A" n="3r"/>ipsum <pb edRef="#A" n="2r"/>dolour</rdg>'
                                         '<rdg wit="#C">ipsum <pb edRef="#B" n="7v"/>dolor</rdg></app> sit amet.</p></div>')
    result, tree = _edition(project, name, witness)
    assert result.ok, result.error
    assert _paragraph(tree) == expected


def test_a_page_break_without_edref_in_a_reading_not_kept_belongs_to_its_witnesses(project):
    name = _write(project, "folios.xml", '<div><p>Lorem <app><lem wit="#B">ipsum</lem>'
                                         '<rdg wit="#A">ip<pb n="4r"/>sam</rdg><rdg wit="#C">ip<pb n="9r"/>sum</rdg>'
                                         '</app> dolor.</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _paragraph(tree) == "Lorem ipsum[1]⟨4r⟩ dolor."


def test_renditions_of_hi_are_combined(project):
    name = _write(project, "hi.xml", '<div><p>a <hi rend="sup">er</hi> b <hi rend="sub">2</hi> c '
                                     '<hi rend="smallcaps">sc</hi> d <hi rend="italic bold">ib</hi> e '
                                     '<hi rend="gras souligne">gs</hi> f <app><lem wit="#A">x</lem>'
                                     '<rdg wit="#B"><hi rend="italic bold">y</hi></rdg></app>.</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    main = tree.find(".//main")
    classes = {_text(e): set(e.get("class").split()) for e in main.iter() if e.get("class") and _text(e)}
    assert {"exposant"} <= classes["er"] and {"indice"} <= classes["2"]
    assert {"petites-capitales"} <= classes["sc"]
    assert {"italique", "gras"} <= classes["ib"] and {"gras", "souligne"} <= classes["gs"]
    # Dans l'apparat, en romain : le gras reste.
    entry = tree.xpath("//ol[contains(@class, 'apparat')]/li")[0]
    y = next(e for e in entry.iter() if _text(e) == "y" and e.get("class") != "variantes")
    assert y.get("class").split() == ["gras"]


@pytest.mark.parametrize("language", ["fr", "en", "ja"])
def test_front_and_back_matter_and_the_editor_are_named_in_the_language_asked(project, language):
    texts = _catalog(language)
    name = _write(project, "parties.xml", '<div><p>Lorem <app><lem wit="#A">sit</lem><rdg>sat</rdg></app>.</p></div>')
    source = project.root_dir / "xml" / name
    source.write_text(source.read_text(encoding="utf-8").replace(
        "<text><body>", "<text><front><div><p>Praefatio.</p></div></front><body>").replace(
        "</body></text>", "</body><back><div><p>Appendix.</p></div></back></text>"), encoding="utf-8")
    result, tree = _edition(project, name, "A", langue=language)
    assert result.ok, result.error
    assert [_text(h) for h in tree.find_class("titre-partie")] == [
        texts["publication.critique.front_matter"], texts["publication.critique.back_matter"]]
    assert ("1", f"sit ] sat {texts['publication.editor_siglum']}") in _entries(tree)


def test_the_note_of_the_lemma_is_not_repeated_in_the_apparatus(project):
    name = _write(project, "notes.xml", '<div><p>Lorem <app><lem wit="#A">ipsum<note>Nota lemmatis.</note></lem>'
                                        '<rdg wit="#B">ipsam<note>Nota lectionis.</note></rdg>'
                                        '<rdg wit="#C"><note>Omittit C.</note></rdg></app> dolor.</p></div>')
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _entries(tree) == [("1", "ipsum ] ipsam (Nota lectionis.) B ; om. (Omittit C.) C")]
    assert _entries(tree, "notes") == [("a", "Nota lemmatis.")]
