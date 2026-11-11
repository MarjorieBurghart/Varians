# -*- coding: utf-8 -*-
"""Repères de ligne de « Édition critique » dans l'aperçu (V0.9.4.4), avec
Saxon, sans Qt.

Choisie comme vue de l'édition, la feuille suit les témoins comme celle de
Varians : avec le paramètre ``reperes-lignes`` (que seul l'aperçu donne),
elle écrit un repère invisible par ``<lb>`` du témoin de base, tous, une
seule fois chacun, dans l'ordre du document. Un ``<lb>`` d'une leçon non
retenue, d'une autre forme d'un ``<choice>`` ou d'une note n'est pas rendu
dans le texte : son repère est écrit à la place de l'apparat ou de l'appel
de note. Une publication (sans le paramètre) n'a aucun repère."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from pivot_lines import pivot_lb_pattern
from xslt_scenarios import saxon_available

ROOT = Path(__file__).resolve().parents[1]
SHEET = ROOT / "rendering" / "edition-critique.xsl"
TEI_NS = "http://www.tei-c.org/ns/1.0"
MARKER = re.compile(r'<a class="tei-line-marker" href="tei-line://base/INDEX">⁠</a>')

pytestmark = pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")

BODY = ('<p><lb edRef="#A"/>unus <app><lem wit="#A">duo<lb edRef="#A"/>tres</lem>'
        '<rdg wit="#B">quattuor<lb edRef="#A"/>quinque</rdg></app> sex<note>nota<lb edRef="#A"/>septem</note>'
        ' octo <choice><sic>falsum<lb edRef="#A"/>verbum</sic><corr>rectum</corr></choice>'
        '<lb edRef="#B"/> nouem<lb edRef="#A"/>decem</p>')


def _edition(body):
    return (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>Essai</title></titleStmt>'
            '<publicationStmt><p>x</p></publicationStmt><sourceDesc><listWit><witness xml:id="A">A</witness>'
            '<witness xml:id="B">B</witness></listWit></sourceDesc></fileDesc></teiHeader>'
            f'<text><body><div>{body}</div></body></text></TEI>')


def _render(xml_text, **params):
    from saxonche import PySaxonProcessor
    processor = PySaxonProcessor(license=False)
    executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(SHEET))
    for name, value in params.items():
        executable.set_parameter(name, processor.make_atomic_value("untypedAtomic", value))
    return executable.transform_to_string(xdm_node=processor.parse_xml(xml_text=xml_text))


def _main(html):
    """Le texte établi, chaque repère noté « § »."""
    main = html[html.index('<main'):html.index('</main>')]
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", MARKER.sub("§", main)))


def test_a_publication_has_no_line_marker():
    html = _render(_edition(BODY), **{"temoin-de-base": "A"})
    assert "tei-line" not in html


def test_the_preview_gets_one_marker_per_pivot_line_in_order():
    xml_text = _edition(BODY)
    html = _render(xml_text, **{"temoin-de-base": "A", "reperes-lignes": "true"})
    pivot = len(list(pivot_lb_pattern("A").finditer(xml_text)))
    assert pivot == 6 and len(MARKER.findall(html)) == 6
    text = _main(html).replace(" ", "")
    # unus | duo tres (lb du lem) | leçon écartée, avant l'appel | note, après
    # son appel | autre forme du <choice>, avant la forme montrée | decem
    assert re.search(r"^§unusduo§tres§\w?sex\w?§octo§rectumnouem§decem", text), text


def test_the_apparatus_and_the_notes_have_no_marker():
    html = _render(_edition(BODY), **{"temoin-de-base": "A", "reperes-lignes": "true"})
    text = _main(html)
    apparatus = text.index("quattuor")
    assert "septem" in text[apparatus:] and "§" not in text[apparatus:]


def test_the_example_edition_has_as_many_markers_as_pivot_lines():
    xml_text = (ROOT / "tests" / "data" / "exemple" / "xml" / "edition.xml").read_text(encoding="utf-8")
    html = _render(xml_text, **{"temoin-de-base": "T1", "reperes-lignes": "true"})
    pivot = len(list(pivot_lb_pattern("T1").finditer(xml_text)))
    assert pivot > 1000 and len(MARKER.findall(html)) == pivot
