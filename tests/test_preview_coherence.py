# -*- coding: utf-8 -*-
"""Red team 2 (cohérence) : l'aperçu (Vue XSLT / CSS, Édition HTML,
rendering/tei-to-html.xsl) suit la règle commune.

- C11 : <front> et <back> étaient omis : ils sont rendus, titrés comme dans
  l'Édition critique (« Préliminaires », « Annexes », traduits).
- C12 : des <lb> contigus (de plusieurs témoins) sont une seule coupure,
  qui soude le mot si l'un porte break="no" ; des blancs entre eux n'y
  changent rien, ici comme dans l'Édition critique et le DOCX.
- C16 : apparat en ligne : un séparateur « | » entre deux leçons, et un
  seul (les blancs et les <rdgGrp> en ajoutaient ou en ôtaient) ; le
  @wit d'un <rdgGrp> vaut pour ses leçons ; une leçon sans témoin est
  « éd. » ; un vers qui suit un apparat de vers va à la ligne.
- C4 : une omission est « om. », une lacune « lacuna incipit » ou
  « lacuna desinit » (« -- » avant) ; une leçon faite d'une lacune
  matérielle (<gap/>) n'est pas une omission."""
from __future__ import annotations

from pathlib import Path

import pytest
from lxml import etree, html

from test_tei_to_html_rendering import BUILTIN, TEI_NS, _page, _texts

ROOT = Path(__file__).resolve().parents[1]


def _main(page):
    return " ".join(page.xpath("//main")[0].text_content().replace("⁠", "").split())


def _catalog(language):
    root = etree.parse(str(ROOT / "i18n" / f"{language}.xml")).getroot()
    return {string.get("key"): string.text for string in root.findall("string")}


@pytest.mark.parametrize("language", [None, "en"])
def test_front_and_back_matter_are_rendered_and_titled(language):
    params = {} if language is None else {"langue": language, "catalogues": (ROOT / "i18n").as_uri() + "/"}
    texts = _catalog(language or "fr")
    tei = (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>'
           '</teiHeader><text><front><div><head>Praefatio</head><p>Ante.</p></div></front>'
           '<body><div><head>Caput</head><p>Medium.</p></div></body>'
           '<back><div><head>Appendix</head><p>Post.</p></div></back></text></TEI>')
    transform = etree.XSLT(etree.parse(str(BUILTIN)))
    page = html.fromstring(str(transform(etree.fromstring(tei.encode("utf-8")),
                                         **{k: etree.XSLT.strparam(v) for k, v in params.items()})))
    assert _main(page).split() == (f"{texts['publication.critique.front_matter']} Praefatio Ante. Caput Medium. "
                                   f"{texts['publication.critique.back_matter']} Appendix Post.").split()
    assert _texts(page, '//nav//a') == ["Praefatio", "Caput", "Appendix"]


@pytest.mark.parametrize("body, expected", [
    ('<p>Lorem ip<lb edRef="#A" break="no"/><lb edRef="#B"/>sum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip<lb edRef="#B"/><lb edRef="#A" break="no"/>sum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip\n<lb edRef="#A" break="no"/>\n<lb edRef="#B"/>\nsum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip\n<lb edRef="#B"/>\n<lb edRef="#A" break="no"/>\nsum dolor.</p>', "Lorem ipsum dolor."),
    ('<p>Lorem ip<lb edRef="#A"/><lb edRef="#B"/>sum dolor.</p>', "Lorem ip sum dolor."),
])
def test_contiguous_line_breaks_are_one_break(body, expected):
    page = _page(f"<div>{body}</div>", params={"baseWitness": "A"})
    assert _main(page) == expected
    assert page.xpath('//a[@class="tei-line-marker"]')       # le repère du pivot reste
    paragraph = page.xpath("//main//p")[0].text_content().replace("⁠", "")
    assert "  " not in paragraph


@pytest.mark.parametrize("app, expected", [
    ('<app>\n  <rdg wit="#A">ipsum</rdg>\n  <rdg wit="#B #C">ipsam</rdg>\n</app>', "[ipsum (A) | ipsam (B C) ]"),
    ('<app><lem wit="#A">ipsum</lem><rdgGrp type="orth"><rdg wit="#B">ypsum</rdg><rdg wit="#C">hipsum</rdg></rdgGrp></app>',
     "[ipsum (A) | ypsum (B) | hipsum (C) ]"),
    ('<app><rdg wit="#B">ipsam</rdg><rdgGrp wit="#A #C"><rdg>ipsum</rdg></rdgGrp></app>', "[ipsam (B) | ipsum (A C) ]"),
    ('<app><lem wit="#A #B"/><rdg wit="#C"><lacunaStart/></rdg></app>', "[om. (A B) | lacuna incipit (C) ]"),
    ('<app><lem wit="#A #B"/><rdg wit="#C"><lacunaEnd/></rdg></app>', "[om. (A B) | lacuna desinit (C) ]"),
    ('<app><lem wit="#A">ipsum</lem><rdg wit="#B"><gap reason="illegible"/></rdg><rdg wit="#C"><note>Omittit.</note></rdg></app>',
     "[ipsum (A) | [lacune] (B) | om.[Omittit.] (C) ]"),
    ('<app><lem>sit</lem><rdg wit="#A">set</rdg></app>', "[sit (éd.) | set (A) ]"),
])
def test_the_inline_apparatus_follows_the_common_rule(app, expected):
    page = _page(f"<div><p>Lorem {app} dolor.</p></div>")
    assert _main(page) == f"Lorem {expected} dolor."
    words = [e.text_content() for e in page.xpath('//span[@class="apparatus"]//em[@class="editeur"]')]
    assert words == [w for w in ("om.", "lacuna incipit", "lacuna desinit") if w in expected]


def test_a_line_after_an_apparatus_of_lines_starts_a_new_line():
    page = _page('<div><lg><l n="1">Arma uirumque cano</l><app><lem wit="#A"><l n="2">Troiae qui primus</l></lem>'
                 '<rdg wit="#B"><l n="2">Troiae qui prior</l></rdg></app><l n="3">Italiam fato</l></lg></div>')
    lg = page.xpath('//div[@class="lg"]')[0]
    last = lg.xpath('span[@class="l"]')[-1]
    assert last.text_content() == "Italiam fato"
    assert last.getprevious().tag == "br" and last.getprevious().getprevious().get("class") == "apparatus"


# --- Les mêmes <lb> dans l'Édition critique et le DOCX ------------------------------------------

saxon = pytest.importorskip("xslt_scenarios")


@pytest.mark.skipif(not saxon.saxon_available(), reason="Saxon (saxonche) n'est pas installé")
@pytest.mark.parametrize("body", [
    '<div><p>Lorem fu\n<lb edRef="#A" break="no"/>\n<lb edRef="#B"/>\nit dolor.</p></div>',
    '<div><p>Lorem fu\n<lb edRef="#B"/>\n<lb edRef="#A" break="no"/>\nit dolor.</p></div>',
])
def test_blanks_between_contiguous_line_breaks_change_nothing_in_the_critical_edition(body, tmp_path):
    import shutil

    from project_config import load_project
    from test_apparatus_notes_saxon import _notes
    from test_edition_critique_saxon import TESTS, _edition, _main as _critique_main, _write
    root = tmp_path / "sermons"
    shutil.copytree(TESTS / "sermons", root)
    project = load_project(root / "project.xml")
    name = _write(project, "lb.xml", body)
    result, tree = _edition(project, name, "A")
    assert result.ok, result.error
    assert _critique_main(tree) == ["Lorem fuit dolor."]
    result, notes = _notes(project, "A", f"xml/{name}")
    assert result.ok, result.error
    p = notes.find(".//{%s}body//{%s}p" % (TEI_NS, TEI_NS))
    assert " ".join("".join(p.itertext()).split()) == "Lorem fuit dolor."
