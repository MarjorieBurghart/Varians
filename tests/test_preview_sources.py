# -*- coding: utf-8 -*-
"""Sources de l'aperçu d'une édition assemblée (V0.9.1.5), sans Qt.

La Vue XSLT / CSS d'une édition en parties rend le document assemblé. Pour y
éditer un paragraphe, y cliquer une ligne ou y reporter une sélection, chaque
``<p>`` et chaque repère de ligne (``<lb edRef="#pivot"/>``) de l'aperçu doit
être rattaché à son fichier et à sa place dans ce fichier.

Jeu « sermons » (tests/data/sermons) : s01 est un fragment ; s02 un document
TEI complet inclus par identifiant ; s03 un document TEI complet inclus par
``element()`` ; s04 inclut lui-même l'exemplum.
"""
from __future__ import annotations

from pathlib import Path

from lxml import etree

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


def test_each_paragraph_of_the_preview_comes_from_its_file():
    sources = _sources()
    root = etree.fromstring(sources.text.encode("utf-8"))
    paragraphs = [p for p in root.iter(f"{TEI}p") if any(a.tag == f"{TEI}body" for a in p.iterancestors())]
    assert len(sources.paragraphs) == len(paragraphs)
    files = [Path(span.path).name for span in sources.paragraphs]
    # Le <p> de la préface (<front>) et ceux des en-têtes de s02 et s03
    # ne sont pas dans le <body> assemblé.
    assert files == ["s01.xml"] * 3 + ["s02.xml"] * 3 + ["s03.xml"] * 3 + ["s04.xml"] * 2 + ["s04_exemplum.xml"]
    for element, span in zip(paragraphs, sources.paragraphs):
        xml = _read(span.path)[span.start:span.end]
        assert xml.startswith("<p") and xml.endswith("</p>")
        assert _text_of(xml.replace("<p", '<p xmlns="http://www.tei-c.org/ns/1.0"', 1)) == \
            " ".join("".join(element.itertext()).split())


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
    span = sources.paragraphs[0]
    assert s01[span.start:span.end].startswith(tag + "Additum. ")
    assert "Additum." in sources.text


def test_from_a_place_of_a_file_to_the_preview():
    sources = _sources()
    span = sources.paragraphs[4]                                        # le second <p> de s02
    assert sources.paragraph_at(span.path, span.start + 5) == 4
    assert sources.paragraph_at(span.path, span.end + 1) is None or sources.paragraph_at(span.path, span.end + 1) != 4
    assert sources.paragraph_at(SERMONS / "inconnu.xml", 10) is None
    path, end = sources.lines[12]
    assert sources.line_before(path, end + 3) == 12
    # Avant la première ligne de l'exemplum : la dernière ligne de s04 qui la précède.
    first = next(i for i, (p, _e) in enumerate(sources.lines) if Path(p).name == "s04_exemplum.xml")
    assert sources.line_before(sources.lines[first][0], 0) == first - 1


def test_a_malformed_edition_has_no_sources():
    assert preview_sources("<TEI><mal", EDITION, {}, "A") is None
    assert path_key(_sources().paragraphs[0].path) == path_key(SERMONS / "s01.xml")
