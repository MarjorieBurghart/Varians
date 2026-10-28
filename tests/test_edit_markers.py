# -*- coding: utf-8 -*-
"""Crayons ✎ de la Vue XSLT / CSS (V0.9.2.9), sans Qt.

Varians place lui-même les crayons, quelle que soit la feuille XSLT de la
vue : chaque élément modifiable est numéroté dans le texte donné à la XSLT
(``mark_units``), une feuille enveloppe importe celle de la vue et écrit le
crayon devant ce qu'elle produit pour cet élément, puis le crayon est placé
au début du premier bloc qui le suit (``place_edit_markers``). Le crayon
porte le rang de l'élément : il ouvre le bon élément même si la feuille en
omet ou en déplace."""
from __future__ import annotations

import re
from pathlib import Path

from lxml import etree

from fragment_units import edit_stylesheet, edit_stylesheet_url, mark_units, place_edit_markers

ROOT = Path(__file__).resolve().parents[1]
BUILTIN = ROOT / "rendering" / "tei-to-html.xsl"
TEI_NS = "http://www.tei-c.org/ns/1.0"
TITLE = "Éditer cet élément TEI"


def _tei(body):
    return (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
            f'</fileDesc></teiHeader><text><body>{body}</body></text></TEI>')


def _render(xsl_path, body, **params):
    marked, _spans = mark_units(_tei(body))
    xslt = etree.XSLT(etree.fromstring(edit_stylesheet(xsl_path).encode("utf-8"),
                                       base_url=edit_stylesheet_url(xsl_path)))
    result = xslt(etree.fromstring(marked.encode("utf-8")),
                  **{name: etree.XSLT.strparam(value) for name, value in params.items()})
    return place_edit_markers(str(result), TITLE)


def _marker(index):
    return f'<a href="tei-edit://p/{index}" class="tei-edit-marker" title="{TITLE}">✎</a> '


def _indexes(html):
    return [int(n) for n in re.findall(r'href="tei-edit://p/(\d+)"', html)]


def _sheet(tmp_path, templates, name="feuille.xsl"):
    path = tmp_path / name
    path.write_text(
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
        f'xmlns:tei="{TEI_NS}" exclude-result-prefixes="tei"><xsl:output method="html"/>'
        '<xsl:template match="/"><html><body><main><xsl:apply-templates select="//tei:body"/></main>'
        f'</body></html></xsl:template>{templates}</xsl:stylesheet>', encoding="utf-8")
    return path


def test_the_varians_stylesheet_gets_a_pencil_per_editable_element():
    html, count = _render(BUILTIN, '<div xml:id="d1"><head>Titre</head>'
                                   '<p><lb edRef="#T1"/>Un <note>voir</note> mot.</p>'
                                   '<lg><l>vers un</l><l>vers deux</l></lg><note>entre</note><p>fin</p></div>',
                          baseWitness="T1")
    assert count == 5 and _indexes(html) == [0, 1, 2, 3, 4]
    assert re.search(re.escape(_marker(0)) + r"\s*Titre", html)
    assert "<p>" + _marker(1) in html
    assert re.search(re.escape(_marker(2)) + r"\s*vers un", html)
    assert "<p>" + _marker(4) + "fin" in html
    # Les paramètres de la vue passent : repères de ligne du pivot.
    assert 'href="tei-line://base/INDEX"' in html
    assert "urn:varians" not in html and "vx:" not in html


def test_a_paragraph_rendered_as_a_div_gets_its_pencil(tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="tei:p"><div class="para"><xsl:apply-templates/></div>'
                             '</xsl:template>', name="feuille personnelle é.xsl")
    html, count = _render(sheet, "<div><p>a</p><p>b</p></div>")
    assert count == 2
    assert '<div class="para">' + _marker(0) + "a</div>" in html
    assert '<div class="para">' + _marker(1) + "b</div>" in html


def test_an_element_the_stylesheet_hides_has_no_pencil(tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="tei:p"><p><xsl:apply-templates/></p></xsl:template>'
                             '<xsl:template match="tei:note"/>')
    html, count = _render(sheet, "<div><p>a</p><note>cachée</note><p>b</p></div>")
    assert (count, _indexes(html)) == (2, [0, 2])
    assert "<p>" + _marker(2) + "b</p>" in html


def test_the_stylesheet_templates_keep_their_priority(tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="tei:p"><p><xsl:apply-templates/></p></xsl:template>'
                             '<xsl:template match="tei:p[@rend=\'cit\']"><blockquote><xsl:apply-templates/>'
                             '</blockquote></xsl:template>')
    html, _count = _render(sheet, '<div><p rend="cit">a</p><p>b</p></div>')
    assert "<blockquote>" + _marker(0) + "a</blockquote>" in html
    assert "<p>" + _marker(1) + "b</p>" in html


def test_an_element_read_without_templates_leaves_the_other_ranks_exact(tmp_path):
    sheet = _sheet(tmp_path, '<xsl:template match="tei:div"><xsl:for-each select="tei:lg"><pre>'
                             '<xsl:value-of select="."/></pre></xsl:for-each>'
                             '<xsl:apply-templates select="tei:p"/></xsl:template>'
                             '<xsl:template match="tei:p"><p><xsl:apply-templates/></p></xsl:template>')
    html, count = _render(sheet, "<div><lg><l>v</l></lg><p>b</p></div>")
    assert (count, _indexes(html)) == (1, [1])
    assert "<pre>v</pre>" in html and "<p>" + _marker(1) + "b</p>" in html


def test_the_pencil_goes_into_the_first_block():
    raw = ('<main><a class="tei-edit-marker" href="tei-edit://p/3">✎</a>\n  <a name="s1"></a>'
           '<div class="section"><ul>\n<li>item</li></ul></div>'
           '<a class="tei-edit-marker" href="tei-edit://p/4">&#9998;</a><span>en ligne</span>'
           '<a href="tei-edit://p/5" class="tei-edit-marker">&#x270E;</a>\n<h3 class="head">Titre</h3></main>')
    html, count = place_edit_markers(raw, TITLE)
    assert count == 3
    assert html == ('<main>\n  <a name="s1"></a><div class="section"><ul>\n<li>' + _marker(3) + 'item</li></ul></div>'
                    + _marker(4) + '<span>en ligne</span>\n<h3 class="head">' + _marker(5) + 'Titre</h3></main>')


def test_the_title_is_escaped():
    html, _count = place_edit_markers('<a class="tei-edit-marker" href="tei-edit://p/0">✎</a>x', 'Ce « <p> » & co')
    assert 'title="Ce « &lt;p&gt; » &amp; co"' in html
