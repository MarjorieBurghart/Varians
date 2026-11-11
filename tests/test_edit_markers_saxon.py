# -*- coding: utf-8 -*-
"""Crayons ✎ d'une vue en XSLT 2.0 ou 3.0 (V0.9.4.4), avec Saxon, sans Qt.

La feuille enveloppe d'une feuille 2.0 ou 3.0 est elle-même en 3.0 : elle
intercepte chaque élément modifiable dans tous les modes (``mode="#all"``),
puisque les feuilles 3.0 rendent souvent le texte dans un mode (« Édition
critique » : ``base`` et ``lecture``). Un élément rendu deux fois (le texte,
puis ses notes) n'a qu'un crayon, le premier de la page :
``place_edit_markers`` écarte les suivants, pour toute feuille."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from fragment_units import (
    TEI_UNIT_NAMES, chosen_units, edit_stylesheet, mark_units, place_edit_markers, stylesheet_needs_saxon,
)
from xslt_scenarios import saxon_available

ROOT = Path(__file__).resolve().parents[1]
TEI_NS = "http://www.tei-c.org/ns/1.0"
PERSONS = (f'<listPerson xmlns="{TEI_NS}"><person><persName>Bernardus</persName></person>'
           '<person><persName>Petrus</persName></person></listPerson>')

needs_saxon = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")


def _sheet(tmp_path, body, version="3.0", name="vue.xsl"):
    path = tmp_path / name
    path.write_text(f'<xsl:stylesheet version="{version}" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
                    f'xmlns:tei="{TEI_NS}" exclude-result-prefixes="tei"><xsl:output method="html"/>'
                    f'{body}</xsl:stylesheet>', encoding="utf-8")
    return path


def _render(xsl_path, xml_text, names, folder):
    """La feuille enveloppe importe la vue par son adresse absolue : elle
    peut être écrite ailleurs (ici, dans le dossier du test)."""
    from saxonche import PySaxonProcessor
    marked, _spans = mark_units(xml_text, names)
    wrapper = Path(folder) / "enveloppe.xsl"
    wrapper.write_text(edit_stylesheet(xsl_path, version="3.0"), encoding="utf-8")
    processor = PySaxonProcessor(license=False)
    executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(wrapper))
    source = Path(folder) / "source.xml"
    source.write_text(marked, encoding="utf-8")
    return place_edit_markers(executable.transform_to_string(source_file=str(source)), "✎")


def _indexes(html):
    return [int(n) for n in re.findall(r'href="tei-edit://p/(\d+)"', html)]


def test_the_version_of_a_stylesheet_chooses_its_engine(tmp_path):
    assert not stylesheet_needs_saxon(_sheet(tmp_path, "", "1.0", "un.xsl"))
    assert stylesheet_needs_saxon(_sheet(tmp_path, "", "2.0", "deux.xsl"))
    assert stylesheet_needs_saxon(_sheet(tmp_path, "", "3.0", "trois.xsl"))
    assert stylesheet_needs_saxon(ROOT / "rendering" / "edition-critique.xsl")
    assert not stylesheet_needs_saxon(ROOT / "rendering" / "tei-to-html.xsl")
    assert not stylesheet_needs_saxon(tmp_path / "absente.xsl")              # l'erreur viendra de lxml
    broken = tmp_path / "cassee.xsl"
    broken.write_text("<xsl:stylesheet", encoding="utf-8")
    assert not stylesheet_needs_saxon(broken)


def test_the_wrapper_of_a_3_0_stylesheet_is_3_0_and_reaches_every_mode(tmp_path):
    text = edit_stylesheet(_sheet(tmp_path, ""), version="3.0")
    assert 'version="3.0"' in text and 'mode="#all"' in text and "exsl:" not in text
    assert 'version="1.0"' in edit_stylesheet(_sheet(tmp_path, "", "1.0", "un.xsl"))


@needs_saxon
@pytest.mark.parametrize("body", [
    # Mode par défaut, comme en 1.0.
    '<xsl:template match="/"><html><body><xsl:apply-templates select="//tei:person"/></body></html></xsl:template>'
    '<xsl:template match="tei:person"><p><xsl:value-of select="tei:persName"/></p></xsl:template>',
    # Un mode nommé : en 3.0, les crayons y sont aussi.
    '<xsl:template match="/"><html><body><xsl:apply-templates select="//tei:person" mode="fiche"/></body></html>'
    '</xsl:template><xsl:template match="tei:person" mode="fiche"><p><xsl:value-of select="tei:persName"/></p>'
    '</xsl:template>',
])
def test_each_element_of_a_3_0_view_has_its_pencil(tmp_path, body):
    html, count = _render(_sheet(tmp_path, body), PERSONS, chosen_units(("person",)), tmp_path)
    assert count == 2 and _indexes(html) == [0, 1]
    assert re.search(r"<p>\s*<a [^>]*tei-edit://p/0[^>]*>✎</a> Bernardus</p>", html)


@needs_saxon
def test_an_element_rendered_twice_has_one_pencil_the_first(tmp_path):
    body = ('<xsl:template match="/"><html><body><xsl:apply-templates select="//tei:person"/>'
            '<hr/><xsl:apply-templates select="//tei:person" mode="notes"/></body></html></xsl:template>'
            '<xsl:template match="tei:person"><p class="texte"><xsl:value-of select="tei:persName"/></p></xsl:template>'
            '<xsl:template match="tei:person" mode="notes"><p class="note"><xsl:value-of select="tei:persName"/></p>'
            '</xsl:template>')
    html, count = _render(_sheet(tmp_path, body), PERSONS, chosen_units(("person",)), tmp_path)
    assert count == 2 and _indexes(html) == [0, 1]
    assert html.index("tei-edit://p/1") < html.index("<hr")                 # les crayons du texte
    assert re.search(r'<p class="note">Bernardus</p>', html)


@needs_saxon
@pytest.mark.parametrize("name", ["apparat-en-notes.xsl", "edition-critique.xsl", "tei-to-html.xsl"])
def test_the_bundled_stylesheets_get_one_pencil_per_element(tmp_path, name):
    text = (ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml").read_text(encoding="utf-8")
    total = len(mark_units(text)[1])
    assert total > 100
    html, count = _render(ROOT / "rendering" / name, text, TEI_UNIT_NAMES, tmp_path)
    assert count == total and sorted(_indexes(html)) == list(range(total))


def test_a_repeated_pencil_is_dropped_for_any_stylesheet():
    marker = '<a class="tei-edit-marker" href="tei-edit://p/{}">✎</a>'
    html = (f"<p>{marker.format(0)}Un</p><p>{marker.format(1)}Deux</p>"
            f"<div>{marker.format(0)}<p>Un, en note</p></div>")
    out, count = place_edit_markers(html, "")
    assert count == 2 and _indexes(out) == [0, 1]
    assert "<p>Un, en note</p>" in out and "✎" not in out[out.index("<div>"):]
