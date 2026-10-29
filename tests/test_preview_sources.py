# -*- coding: utf-8 -*-
"""Sources de l'aperçu d'une édition assemblée (V0.9.1.5), sans Qt.

La Vue XSLT / CSS d'une édition en parties rend le document assemblé. Pour y
éditer un élément, y cliquer une ligne ou y reporter une sélection, chaque
élément modifiable (``fragment_units``, V0.9.2.9) et chaque repère de ligne
(``<lb edRef="#pivot"/>``) de l'aperçu doit être rattaché à son fichier et à
sa place dans ce fichier.

Jeu « sermons » (tests/data/sermons) : s01 est un fragment ; s02 un document
TEI complet inclus par identifiant ; s03 un document TEI complet inclus par
``element()`` ; s04 inclut lui-même l'exemplum.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

from fragment_units import EDIT_NS
from preview_sources import preview_sources
from xml_assembly import path_key

DATA = Path(__file__).resolve().parent / "data" / "sermons" / "xml"
EDITION = DATA / "edition.xml"
SERMONS = DATA / "sermons"
TEI = "{http://www.tei-c.org/ns/1.0}"


def _read(path):
    return Path(path).read_text(encoding="utf-8")


def _sources(**texts):
    changed = {SERMONS / f"{name}.xml": text for name, text in texts.items()}
    return preview_sources(_read(EDITION), EDITION, changed, "A")


def _text_of(xml):
    return " ".join("".join(etree.fromstring(xml).itertext()).split())


def _file_text(path, **texts):
    return texts.get(Path(path).stem, None) or _read(path)


def _tag(xml):
    return xml[1:].split(">", 1)[0].split()[0]


def test_each_editable_element_of_the_preview_comes_from_its_file():
    """V0.9.2.9 : les éléments modifiables (fragment_units) de l'édition
    assemblée, ici le <head> et les <p> de chaque sermon ; chacun porte son
    rang (vx:edit) dans le texte de l'aperçu."""
    sources = _sources()
    root = etree.fromstring(sources.text.encode("utf-8"))
    numbered = [e for e in root.iter() if e.get(f"{{{EDIT_NS}}}edit") is not None]
    assert [int(e.get(f"{{{EDIT_NS}}}edit")) for e in numbered] == list(range(len(sources.paragraphs)))
    files = [Path(span.path).name for span in sources.paragraphs]
    # Le <p> de la préface (<front>) et ceux des en-têtes de s02 et s03
    # ne sont pas dans le <body> assemblé.
    assert files == ["s01.xml"] * 4 + ["s02.xml"] * 4 + ["s03.xml"] * 4 + ["s04.xml"] * 3 + ["s04_exemplum.xml"]
    tags = [_tag(_read(span.path)[span.start:span.end]) for span in sources.paragraphs]
    assert tags == (["head"] + ["p"] * 3) * 3 + ["head", "p", "p", "p"]
    for element, span in zip(numbered, sources.paragraphs):
        xml = _read(span.path)[span.start:span.end]
        name = _tag(xml)
        assert etree.QName(element).localname == name and xml.endswith(f"</{name}>")
        assert _text_of(xml.replace(f"<{name}", f'<{name} xmlns="http://www.tei-c.org/ns/1.0"', 1)) == \
            " ".join("".join(element.itertext()).split())


def test_the_names_of_the_editable_elements_can_be_given():
    paragraphs = preview_sources(_read(EDITION), EDITION, {}, "A", names=frozenset({"p"})).paragraphs
    assert [_tag(_read(span.path)[span.start:span.end]) for span in paragraphs] == ["p"] * 12


def test_a_verse_group_of_a_part_is_one_editable_element():
    s01 = _read(SERMONS / "s01.xml")
    tag = '<p xml:id="s01_p1">'
    s01 = s01.replace(tag, "<lg><l>Uersus primus</l>\n<l>uersus secundus</l></lg>" + tag, 1)
    sources = _sources(s01=s01)
    span = sources.paragraphs[1]
    assert s01[span.start:span.end] == "<lg><l>Uersus primus</l>\n<l>uersus secundus</l></lg>"
    assert s01[sources.paragraphs[2].start:].startswith(tag)


def test_each_line_marker_of_the_preview_comes_from_its_file():
    sources = _sources()
    # 10 lignes de A dans s01, aucune dans s02 (son pivot est B), 9 dans s03,
    # 5 dans s04 et 3 dans l'exemplum.
    assert len(sources.lines) == 27
    names = [Path(path).name for path, _end in sources.lines]
    assert names.count("s01.xml") == 10 and names.count("s03.xml") == 9 and names.count("s04_exemplum.xml") == 3
    for path, end in sources.lines:
        assert _read(path)[:end].endswith('edRef="#A"/>')
    assert names.index("s04_exemplum.xml") > names.index("s04.xml")       # l'exemplum est dans s04


def test_the_unsaved_text_of_a_part_is_used():
    """Texte non enregistré d'une partie ; un <p> en commentaire, sur la même
    ligne, ne compte pas."""
    tag = '<p xml:id="s01_p1">'
    s01 = _read(SERMONS / "s01.xml").replace(tag, "<!-- <p>vetus</p> -->" + tag + "Additum. ", 1)
    sources = _sources(s01=s01)
    span = sources.paragraphs[1]                                        # après le <head>
    assert s01[span.start:span.end].startswith(tag + "Additum. ")
    assert "Additum." in sources.text


def test_from_a_place_of_a_file_to_the_preview():
    sources = _sources()
    span = sources.paragraphs[6]                                        # le second <p> de s02
    assert sources.paragraph_at(span.path, span.start + 5) == 6
    assert sources.paragraph_at(span.path, span.end + 1) is None or sources.paragraph_at(span.path, span.end + 1) != 6
    assert sources.paragraph_at(SERMONS / "inconnu.xml", 10) is None
    path, end = sources.lines[12]
    assert sources.line_before(path, end + 3) == 12
    # Avant la première ligne de l'exemplum : la dernière ligne de s04 qui la précède.
    first = next(i for i, (p, _e) in enumerate(sources.lines) if Path(p).name == "s04_exemplum.xml")
    assert sources.line_before(sources.lines[first][0], 0) == first - 1


def test_a_malformed_edition_has_no_sources():
    assert preview_sources("<TEI><mal", EDITION, {}, "A") is None
    assert path_key(_sources().paragraphs[0].path) == path_key(SERMONS / "s01.xml")
