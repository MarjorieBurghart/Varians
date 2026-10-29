# -*- coding: utf-8 -*-
"""Éléments modifiables comme fragment dans la Vue XSLT / CSS (V0.9.2.9).

Le crayon ✎ n'est plus réservé aux ``<p>`` : chaque bloc posé dans une
division (``model.divPart``, ``model.inter``, ``<head>``, ``<figure>``,
``<note>``, sauf à l'intérieur d'un autre) a le sien, quelle que soit la
feuille XSLT. F2, le fragment et les reports de sélection suivent la même
règle. Les classes viennent du schéma RELAX NG du projet, sinon de TEI P5.

Projet exemple, avec avant le premier paragraphe un titre, une strophe et
une note : éléments 0 (``<head>``), 1 (``<lg>``), 2 (``<note>``), puis les
``<p>`` à partir de 3."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app_context import tr
from fragment_units import unit_spans
from test_gui_pencil_selection import _click_pencil
from test_gui_selection_transfer import WJ, _select, _selection, _show_preview

VERSE = ("<head>Prologus</head>\n<lg><l>Uersus primus</l>\n<l>uersus secundus</l></lg>\n"
         "<note>Nota inter paragraphos</note>\n")


@pytest.fixture
def verse_project(example_project):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    anchor = '<div n="pr">\n'
    assert text.count(anchor) == 1
    edition.write_text(text.replace(anchor, anchor + VERSE), encoding="utf-8")
    return example_project


def _content(view, index):
    """Texte de l'aperçu qui suit le crayon de l'élément ``index``."""
    start, end = view.preview.paragraph_bounds(index)
    return view.preview.toPlainText()[start:end].replace(WJ, "")


def _preview_word(view, word, index):
    start, end = view.preview.paragraph_bounds(index)
    found = view.preview.toPlainText().find(word, start, end)
    assert found >= 0
    return found, found + len(word)


def test_head_verse_and_note_have_their_pencils(open_window, verse_project, qtbot):
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    total = len(unit_spans(window.editor.toPlainText()))
    assert [index for _marker, _content_pos, index in view.preview._paragraph_markers] == list(range(total))
    assert _content(view, 0).startswith("Prologus")
    assert _content(view, 1).startswith("Uersus primus")
    assert _content(view, 2).startswith("[Nota inter paragraphos]")
    assert "Commune sanctorum" in _content(view, 3)
    assert f"{total}/{total}" in view.info.text()


def test_the_pencil_of_a_verse_group_opens_it(open_window, verse_project, qtbot):
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    _click_pencil(qtbot, view, 1)
    qtbot.waitUntil(lambda: view.current_paragraph == 1, timeout=3000)
    assert view.fragment_editor.toPlainText() == "<lg><l>Uersus primus</l>\n<l>uersus secundus</l></lg>"
    total = len(unit_spans(window.editor.toPlainText()))
    assert view.frag_label.text() == tr("fragment.label", element="<lg>", index=2, total=total)
    assert view.frag_label.textFormat() == Qt.TextFormat.PlainText            # « <p> » n'est pas du HTML
    view.fragment_editor.setPlainText(view.fragment_editor.toPlainText().replace("primus", "prior"))
    assert view.apply_fragment()
    assert "<l>Uersus prior</l>" in window.editor.toPlainText()
    window.editor.undo()
    assert "<l>Uersus primus</l>" in window.editor.toPlainText()


def test_a_paragraph_after_the_new_elements_opens_as_before(open_window, verse_project, qtbot):
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    _click_pencil(qtbot, view, 3)
    qtbot.waitUntil(lambda: view.current_paragraph == 3, timeout=3000)
    fragment = view.fragment_editor.toPlainText()
    assert fragment.startswith("<p>") and fragment.endswith("</p>") and "Commune sanctorum" in fragment
    total = len(unit_spans(window.editor.toPlainText()))
    assert view.frag_label.text() == tr("fragment.label", element="<p>", index=4, total=total)


def test_f2_in_a_verse_opens_its_verse_group(open_window, verse_project, qtbot):
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    occurrence = _preview_word(view, "secundus", 1)
    window.activateWindow()
    view.preview.setFocus()
    _select(view.preview, *occurrence)
    QTest.keyClick(view.preview, Qt.Key.Key_F2)
    assert view.current_paragraph == 1
    fragment = view.fragment_editor.toPlainText()
    start = fragment.index("secundus")
    assert _selection(view.fragment_editor) == (start, start + len("secundus"))


def test_a_selection_in_a_verse_goes_to_the_source_and_back(open_window, verse_project, qtbot):
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    text = window.editor.toPlainText()
    expected = text.index("uersus secundus") + len("uersus "), text.index("uersus secundus") + len("uersus secundus")
    _select(view.preview, *_preview_word(view, "secundus", 1))
    window.left_tabs.setCurrentIndex(0)
    qtbot.waitUntil(lambda: window.editor.textCursor().hasSelection(), timeout=5000)
    assert _selection(window.editor) == expected
    start = text.index("Prologus")
    _select(window.editor, start, start + len("Prologus"))
    _show_preview(window, qtbot)
    qtbot.waitUntil(lambda: view.preview.textCursor().hasSelection(), timeout=5000)
    assert _selection(view.preview) == _preview_word(view, "Prologus", 0)


SCHEMA_CLASSES = """
  <define name="model.divPart"><choice><ref name="p"/><ref name="strophe"/></choice></define>
  <define name="model.inter"><notAllowed/></define>
  <define name="p"><element name="p"><ref name="any"/></element></define>
  <define name="strophe"><element name="strophe"><ref name="any"/></element></define>
</grammar>"""


def test_the_classes_come_from_the_project_schema(open_window, verse_project, qtbot):
    """Un schéma qui range « strophe » dans model.divPart, et pas <lg> : la
    strophe a son crayon, le groupe de vers non (ses vers ne sont dans aucun
    élément modifiable)."""
    root = verse_project.parent
    schema = root / "xml" / "test.rng"
    schema.write_text(schema.read_text(encoding="utf-8").replace("</grammar>", SCHEMA_CLASSES), encoding="utf-8")
    edition = root / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace(
        "<head>Prologus</head>", "<head>Prologus</head>\n<strophe>Strophe nova</strophe>"), encoding="utf-8")
    window = open_window(verse_project)
    resolution = window.edition_session.last_schema_resolution
    assert resolution is not None and resolution.schema_path.name == "test.rng"
    assert "strophe" in window.fragment_unit_names() and "lg" not in window.fragment_unit_names()
    view = _show_preview(window, qtbot)
    markers = view.preview._paragraph_markers
    assert len(markers) == len(unit_spans(window.editor.toPlainText(), window.fragment_unit_names()))
    assert _content(view, 0).startswith("Prologus")
    assert _content(view, 1).startswith("Strophe nova")
    assert not any(_content(view, i).startswith("Uersus primus") for i in range(len(markers)))
    _click_pencil(qtbot, view, 1)
    qtbot.waitUntil(lambda: view.current_paragraph == 1, timeout=3000)
    assert view.fragment_editor.toPlainText() == "<strophe>Strophe nova</strophe>"


OLD_CSS = ("body { line-height: 1.8; }\np { margin: 0 0 1em; }\n"
           "@media (max-width: 600px) { body { font-size: 0.97rem; } }\n")


@pytest.mark.parametrize("old_stylesheet", [False, True])
def test_a_stanza_is_one_indented_block(open_window, verse_project, qtbot, old_stylesheet):
    """V0.9.3.0 : les vers d'un <lg> forment un seul bloc de l'aperçu, en
    retrait, même avec la CSS d'un projet créé par une version antérieure
    (sans règle pour .lg, et finie par un @media, après lequel Qt ignore
    toute règle) : Varians place ses règles de base avant celle du projet."""
    if old_stylesheet:
        (verse_project.parent / "rendering" / "tei.css").write_text(OLD_CSS, encoding="utf-8")
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    text = view.preview.toPlainText()
    block = view.preview.document().findBlock(text.index("Uersus primus"))
    assert "uersus secundus" in block.text()
    assert block.blockFormat().leftMargin() > 0
    paragraph = view.preview.document().findBlock(text.index("Commune sanctorum"))
    assert paragraph.blockFormat().leftMargin() == 0



def test_the_pencil_is_a_small_grey_mark_not_a_blue_underlined_link(open_window, verse_project, qtbot):
    """V0.9.3.0 : les règles de Varians pour le crayon (et les repères de
    ligne) sont placées avant la CSS du projet ; ajoutées après elle, Qt les
    ignorait (règles après un @media) et le crayon était un lien bleu
    souligné."""
    from PySide6.QtGui import QTextCursor
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    marker = view.preview._paragraph_markers[0][0]
    cursor = QTextCursor(view.preview.document())
    cursor.setPosition(marker + 1)
    assert view.preview.toPlainText()[marker] == "✎"
    fmt = cursor.charFormat()
    assert fmt.isAnchor() and not fmt.fontUnderline()
    assert fmt.foreground().color().name() == "#8a8177"


@pytest.mark.parametrize("old_stylesheet", [False, True])
def test_the_reference_of_a_quotation_is_grey_in_angle_brackets(open_window, verse_project, qtbot, old_stylesheet):
    """V0.9.3.0 : « <Lc. 22:28> » suit sa citation, grisé, même avec la CSS
    d'un projet créé par une version antérieure (sans règle .ref)."""
    from PySide6.QtGui import QTextCursor
    if old_stylesheet:
        (verse_project.parent / "rendering" / "tei.css").write_text(OLD_CSS, encoding="utf-8")
    window = open_window(verse_project)
    view = _show_preview(window, qtbot)
    text = view.preview.toPlainText()
    at = text.index("<Lc. 22:28>")
    cursor = QTextCursor(view.preview.document())
    cursor.setPosition(at + 2)
    grey = cursor.charFormat().foreground().color()
    cursor.setPosition(text.index("Commune sanctorum") + 2)
    assert grey.name() != cursor.charFormat().foreground().color().name()
    if old_stylesheet:
        assert grey.name() == "#8a8177"

