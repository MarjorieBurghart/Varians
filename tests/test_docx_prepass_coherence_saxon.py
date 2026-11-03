# -*- coding: utf-8 -*-
"""Red team 2 (cohérence) : le pré-passage des scénarios DOCX et ODT
(rendering/apparat-en-notes.xsl) suit la règle commune, celle de
« Édition critique » (décision de l'utilisatrice), au lieu de laisser
certains éléments aux TEI Stylesheets.

- <choice> : la forme retenue seule (corr, reg, expan…), pas les deux.
- <stage> : entre parenthèses, en italique ; dans un paragraphe ou un vers,
  sans y couper une ligne.
- <cit> : la référence d'une citation biblique suit la citation, espacée,
  entre chevrons ; celle d'une autre citation est une note de fin.
- Une note en marge (ou à une autre place que foot, end, inline) devient
  une note de fin : elle coupait le paragraphe.
- <space/> : une espace ; <gap/> : « [lacune] », traduit, comme dans
  l'apparat (C+ : une lacune dans une leçon était « […] », sans étendue).
- C9 : l'espace après un élément vide qui se voit (image, <ptr>) reste.
- C8 : un <pb> du témoin choisi dans une leçon non retenue garde son folio.
- La note d'un lemme n'est plus répétée dans la note de l'apparat.
Tests ignorés sans Saxon."""
from __future__ import annotations

import pytest

from test_apparatus_notes_saxon import NS, SOURCE, _apparatus, _notes, _text, project  # noqa: F401
from xslt_scenarios import saxon_available

pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


def _source(project, body, name="coherence.xml"):
    head, _rest = SOURCE.split("<text>", 1)
    (project.root_dir / "xml" / name).write_text(f"{head}<text><body><div>{body}</div></body></text></TEI>",
                                                 encoding="utf-8")
    return f"xml/{name}"


def _body(tree):
    """Le texte du corps, notes comprises, tel quel (blancs gardés)."""
    return "".join(tree.find(".//t:body", NS).itertext())


def test_choice_gives_its_chosen_form_only(project):
    result, tree = _notes(project, "A", _source(project, '<p>A <choice><sic>ipsvm</sic><corr>ipsum</corr></choice> '
                                                         '<choice><abbr>dns</abbr><expan>dominus</expan></choice> '
                                                         '<choice><orig>vt</orig><reg>ut</reg></choice>.</p>'))
    assert result.ok, result.error
    assert _text(tree.find(".//t:body", NS)) == "A ipsum dominus ut."
    assert tree.find(".//t:body//t:choice", NS) is None


def test_stage_directions_are_in_parentheses_and_italics(project):
    result, tree = _notes(project, "A", _source(project, '<sp><speaker>Davus</speaker><p>Quid <stage>ridens</stage> agis?'
                                                         '</p></sp><stage>Exit.</stage>'))
    assert result.ok, result.error
    p = tree.find(".//t:sp/t:p", NS)
    assert _text(p) == "Quid (ridens) agis?" and p.find("t:stage", NS) is None
    assert [hi.text for hi in p.iterfind("t:hi[@rend='italic']", NS)] == ["ridens"]
    block = tree.find(".//t:div/t:stage", NS)
    assert _text(block) == "(Exit.)" and block.find("t:hi[@rend='italic']", NS).text == "Exit."


def test_the_reference_of_a_quotation_follows_the_common_rule(project):
    result, tree = _notes(project, "A", _source(project, '<p>Dixit <cit type="bible"><quote>In principio</quote>'
                                                         '<ref>Gn 1, 1</ref></cit> et <cit><quote>arma</quote>'
                                                         '<ref>Aen. 1, 1</ref></cit> finis.</p>'))
    assert result.ok, result.error
    p = tree.find(".//t:body//t:p", NS)
    outside = " ".join("".join(t for t in p.xpath(".//text()[not(ancestor::t:note)]", namespaces=NS)).split())
    assert outside == "Dixit In principio <Gn 1, 1> et arma finis."
    assert [(n.get("place"), _text(n)) for n in p.iterfind(".//t:note", NS)] == [("end", "Aen. 1, 1")]


def test_a_note_in_the_margin_becomes_an_endnote(project):
    result, tree = _notes(project, "A", _source(project, '<p>Lorem<note place="margin">Marg.</note> ipsum'
                                                         '<note place="foot">Foot.</note> dolor<note place="left">L.</note>'
                                                         ' sit<note place="inline">In.</note>.</p>'))
    assert result.ok, result.error
    assert [(n.get("place"), _text(n)) for n in tree.iterfind(".//t:body//t:note", NS)] == [
        ("end", "Marg."), ("foot", "Foot."), ("end", "L."), ("inline", "In.")]


def test_spaces_and_gaps_follow_the_common_rule(project):
    result, tree = _notes(project, "A", _source(project, '<p>Lorem <gap/> dolor <gap extent="3 words"/> sit'
                                                         '<space quantity="3" unit="chars"/>amet <graphic url="a.png"/>'
                                                         ' finis <ptr target="#x"/> est.</p>'))
    assert result.ok, result.error
    body = _body(tree)
    assert "Lorem [lacune] dolor [lacune : 3 words] sit amet " in body
    assert tree.find(".//t:body//t:gap", NS) is None and tree.find(".//t:body//t:space", NS) is None
    graphic = tree.find(".//t:body//t:graphic", NS)
    assert graphic.tail.startswith(" finis") and tree.find(".//t:body//t:ptr", NS).tail == " est."


def test_a_gap_in_a_reading_is_said_as_in_the_apparatus(project):
    result, tree = _notes(project, "A", _source(project, '<p>Lorem <app><lem wit="#A">ipsum</lem>'
                                                         '<rdg wit="#B"><gap reason="illegible"/></rdg>'
                                                         '<rdg wit="#C"><unclear>ips</unclear><gap extent="2 letters"/>'
                                                         '</rdg></app> dolor.</p>'))
    assert result.ok, result.error
    assert _apparatus(tree) == ["ipsum ] [lacune] B ; ips[lacune : 2 letters] C"]


def test_a_folio_of_the_chosen_witness_in_a_reading_not_kept_is_kept(project):
    source = _source(project, '<p>Lorem <app><lem wit="#B #C">ipsum dolor</lem><rdg wit="#A"><pb edRef="#A" n="3r"/>'
                              'ipsum <pb edRef="#A" n="2r"/>dolour</rdg></app> sit amet.</p>')
    result, tree = _notes(project, "A", source)
    assert result.ok, result.error
    p = tree.find(".//t:body//t:p", NS)
    marks = [("folio", seg.text) if seg.tag.endswith("seg") else ("note", None)
             for seg in p.iter(f"{{{NS['t']}}}seg", f"{{{NS['t']}}}note") if seg.get("type") in ("folio", "apparatus")]
    assert marks == [("folio", "⟨3r⟩"), ("note", None), ("folio", "⟨2r⟩")]
    _result, tree = _notes(project, "B", source)
    assert tree.find(".//t:body//t:seg[@type='folio']", NS) is None


def test_the_note_of_the_lemma_is_not_repeated_in_the_apparatus(project):
    result, tree = _notes(project, "A", _source(project, '<p>Lorem <app><lem wit="#A">ipsum<note>Nota lemmatis.</note>'
                                                         '</lem><rdg wit="#B">ipsam<note>Nota lectionis.</note></rdg>'
                                                         '<rdg wit="#C"><note>Omittit C.</note></rdg></app> dolor.</p>'))
    assert result.ok, result.error
    assert _apparatus(tree) == ["ipsum ] ipsam (Nota lectionis.) B ; om. (Omittit C.) C"]
    assert [_text(n) for n in tree.iterfind(".//t:body//t:note[@place='end']", NS)] == ["Nota lemmatis."]
