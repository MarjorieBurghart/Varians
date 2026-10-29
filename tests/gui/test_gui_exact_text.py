# -*- coding: utf-8 -*-
"""Red team (intégrité et sécurité, A1, A2) : le fichier enregistré est le
texte de l'éditeur, caractère pour caractère, et ce que Varians écrit dans le
texte tombe à sa place.

- A1 : ``toPlainText`` de Qt change les espaces insécables (U+00A0) en
  espaces et les séparateurs de ligne (U+2028) en sauts de ligne : chaque
  enregistrement les perdait.
- A2 : Qt compte en UTF-16, Python en caractères. Après un caractère au-delà
  de U+FFFF (lettres gothiques 𝔄 𝔅, idéogrammes CJK rares…), ce que Varians
  calcule en Python (complétion, paires de balises, Formater, fragment,
  Marquer la page…) tombait un caractère trop tôt pour chacun d'eux, et la
  complétion lisait un autre endroit que celui du curseur.

Les deux lettres gothiques sont placées dans le <title> de l'en-tête : tout
le texte de l'édition est derrière elles."""
from __future__ import annotations

import re

import pytest
from PySide6.QtCore import Qt

from text_search import Utf16Positions

WIDE = "\U0001D504\U0001D505"                    # 𝔄𝔅 : quatre positions dans Qt, deux en Python
SPACED = "Commune\u00a0sanctorum\u2028"          # espace insécable, séparateur de ligne
PB = '<pb n="13v" edRef="#X" facs="#X-p0004"/>'


@pytest.fixture
def wide_project(example_project):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    text = text.replace("<title>Troyes.", f"<title>{WIDE} Troyes.", 1)
    text = text.replace("Commune sanctorum", SPACED, 1)
    edition.write_text(text, encoding="utf-8")
    return example_project


def _place(editor, index, end=None):
    """Curseur à l'indice Python ``index`` (sélection jusqu'à ``end``)."""
    positions = Utf16Positions(editor.toPlainText())
    cursor = editor.textCursor()
    cursor.setPosition(positions.qt(index))
    if end is not None:
        cursor.setPosition(positions.qt(end), cursor.MoveMode.KeepAnchor)
    editor.setTextCursor(cursor)


def _insert_in_body(window, markup, inside):
    """Insère ``markup`` au début du <body> et place le curseur après
    ``inside`` ; renvoie l'indice Python du début de ``markup``."""
    text = window.editor.toPlainText()
    start = text.index("<body>") + len("<body>")
    _place(window.editor, start)
    window.editor.insertPlainText(markup)
    _place(window.editor, start + markup.index(inside) + len(inside))
    window.editor.setFocus()
    return start


def _body(window, length):
    text = window.editor.toPlainText()
    start = text.index("<body>") + len("<body>")
    return text[start:start + length]


def _typed_at_cursor(window, qtbot, marker="§"):
    """Le curseur est-il là où on l'attend ? On y tape une marque."""
    qtbot.keyClicks(window.editor, marker)
    return window.editor.toPlainText()


def _without_layout(text):
    """Le texte sans les blancs de mise en forme (espaces, tabulations, sauts
    de ligne), seuls touchés par Formater."""
    return re.sub(r"[ \t\n]+", "", text)


def test_the_editor_keeps_non_breaking_spaces_and_line_separators(open_window, wide_project):
    window = open_window(wide_project)
    text = window.editor.toPlainText()
    assert SPACED in text and WIDE in text
    assert window.edition_session.text_document.toPlainText() == text


def test_saving_keeps_non_breaking_spaces_and_line_separators(open_window, wide_project):
    window = open_window(wide_project)
    _insert_in_body(window, "<!-- relu -->", "-->")
    assert window.save()
    saved = (wide_project.parent / "xml" / "edition.xml").read_text(encoding="utf-8")
    assert saved == window.editor.toPlainText()
    assert SPACED in saved and f"<title>{WIDE} Troyes." in saved


def test_a_pointer_from_the_list_lands_in_its_attribute(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    _insert_in_body(window, '<app><rdg wit=""></rdg></app>', 'wit="')
    qtbot.keyClicks(window.editor, "#")
    model = window.editor._value_completer.completionModel()
    assert [model.index(row, 0).data(Qt.ItemDataRole.UserRole) for row in range(model.rowCount())] == [
        "#T1", "#T2", "#P"]
    qtbot.keyClick(window.editor, Qt.Key.Key_Tab)
    assert '<body><app><rdg wit="#T1§"></rdg></app>' in _typed_at_cursor(window, qtbot)


def test_an_attribute_name_from_the_list_lands_in_its_tag(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    _insert_in_body(window, "<varianstest ></varianstest>", "<varianstest ")
    qtbot.keyClicks(window.editor, "k")
    assert window.editor._attribute_completer.popup().isVisible()
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert '<body><varianstest kind="§"></varianstest>' in _typed_at_cursor(window, qtbot)


def test_the_closing_tag_from_the_list_closes_its_element(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    _insert_in_body(window, "<hi>x", "x")
    qtbot.keyClicks(window.editor, "</")
    assert window.editor._closing_completer.popup().isVisible()
    qtbot.keyClick(window.editor, Qt.Key.Key_Return)
    assert "<body><hi>x</hi>§" in _typed_at_cursor(window, qtbot)


def test_renaming_an_opening_tag_renames_its_closing_tag(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    start = _insert_in_body(window, "<hi>x</hi>", "<hi")
    _place(window.editor, start + 1, start + 3)                     # « hi » de l'ouverture
    qtbot.keyClicks(window.editor, "seg")
    assert _body(window, 12) == "<seg>x</seg>"


def test_deleting_an_opening_tag_deletes_its_closing_tag(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    start = _insert_in_body(window, "<hi>x</hi>y", "y")
    _place(window.editor, start, start + 4)                         # « <hi> »
    qtbot.keyClick(window.editor, Qt.Key.Key_Delete)
    assert _body(window, 3) == "xy\n"


def test_an_element_from_ctrl_space_lands_at_the_cursor(open_window, wide_project, dialogs, qtbot):
    window = open_window(wide_project)
    _insert_in_body(window, "<p></p>", "<p>")
    chosen = []

    def choose_first(dialog):
        dialog.list_widget.setCurrentRow(0)
        chosen.append(dialog.list_widget.item(0).data(0x0100))
        dialog._accept_current()
        return dialog.result()

    dialogs.expect("dialog", choose_first)
    window.show_rng_completion(window.editor)
    name = chosen[0]
    assert f"<body><p><{name}>§</{name}></p>" in _typed_at_cursor(window, qtbot)


class _ElementOnly:
    """Schéma vu par Formater : <TEI>, <text>, <body> et <div> sans texte,
    donc indentés ; le reste intact."""

    def allows_text(self, name):
        return name.rsplit(":", 1)[-1] not in {"TEI", "text", "body", "div"}


def test_format_xml_keeps_the_text_and_the_cursor(open_window, wide_project, editor_module, monkeypatch, qtbot):
    from tei_formatter import format_tei_xml

    monkeypatch.setattr(editor_module, "format_tei_xml",
                        lambda source, **_options: format_tei_xml(source, rng_model=_ElementOnly()))
    window = open_window(wide_project)
    _insert_in_body(window, "<div><p>alpha</p><p>beta</p></div>", "be")
    before = window.editor.toPlainText()
    window.format_xml_source()
    after = window.editor.toPlainText()
    assert "<div>\n" in after[after.index("<body>"):] and after != before
    assert _without_layout(after) == _without_layout(before)
    assert SPACED in after
    assert "be§ta" in _typed_at_cursor(window, qtbot)


def test_a_fragment_is_written_in_its_place(open_window, wide_project):
    window = open_window(wide_project)
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    index = 0
    while not (view.load_fragment(index) and "permansistis" in view.fragment_original):
        index += 1
    original = view.fragment_original
    edited = original.replace("permansistis", "PERMANSISTIS", 1)
    view.fragment_editor.setPlainText(edited)
    before = window.editor.toPlainText()
    assert view.apply_fragment()
    assert window.editor.toPlainText() == before.replace(original, edited, 1)


def test_mark_page_inserts_the_pb_at_the_cursor(open_window, example_with_text):
    from corpus_data import add_text_pages

    add_text_pages(example_with_text)
    part = example_with_text.parent / "xml" / "rls185.xml"
    text = part.read_text(encoding="utf-8")
    part.write_text(text.replace("?>", f"?>\n<!-- {WIDE} -->", 1), encoding="utf-8")
    window = open_window(example_with_text)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    position = window.lb_spans()[30][1]
    _place(window.editor, position)
    before = window.editor.toPlainText()
    window._edition_write(window._mark_page_in_tei)("X", "X-p0004", "13v")
    assert window.editor.toPlainText() == before[:position] + PB + before[position:]


def test_the_line_of_the_cursor_after_typing(open_window, wide_project, qtbot):
    window = open_window(wide_project)
    spans = window.lb_spans()
    _place(window.editor, spans[2][1])
    qtbot.keyClicks(window.editor, "ab")                             # index des <lb/> décalé, sans relecture
    spans = window.lb_spans()
    text = window.editor.toPlainText()
    assert text[spans[3][0]:spans[3][1]].startswith("<lb ")
    _place(window.editor, spans[3][0])
    assert window.ordinal_at_cursor() == 3
    _place(window.editor, spans[3][0] - 1)
    assert window.ordinal_at_cursor() == 2


def test_a_fragment_of_a_part_not_displayed_is_written_in_its_place(open_window, sermons_project):
    part = sermons_project.parent / "xml" / "sermons" / "s03.xml"
    text = part.read_text(encoding="utf-8")
    part.write_text(text.replace("?>", f"?>\n<!-- {WIDE} {SPACED} -->", 1), encoding="utf-8")
    window = open_window(sermons_project)
    s03 = next(s for s in window.documents if s.path.name == "s03.xml")
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    assert view.load_fragment(9) and view.fragment_session is s03          # premier <p> de s03
    original = view.fragment_original
    edited = original.replace("Surrexit Dominus", "SURREXIT Dominus", 1)
    assert edited != original
    view.fragment_editor.setPlainText(edited)
    before = s03.text_document.toPlainText()
    assert view.apply_fragment()
    assert window.document is not s03
    assert s03.text_document.toPlainText() == before.replace(original, edited, 1)
    assert SPACED in s03.text_document.toPlainText()


def test_f12_selects_the_target_and_alt_left_comes_back(open_window, wide_project):
    window = open_window(wide_project)
    start = _insert_in_body(window, '<app><rdg wit="#T1">x</rdg></app>', 'wit="#T1')     # fin du jeton
    window.action_go_to_reference.trigger()
    assert window.editor.textCursor().selectedText() == '<witness xml:id="T1">'
    window.action_reference_back.trigger()
    positions = Utf16Positions(window.editor.toPlainText())
    assert positions.python(window.editor.textCursor().position()) == start + len('<app><rdg wit="#T1')


def test_ctrl_e_keeps_a_line_separator_of_the_selection(open_window, wide_project, dialogs):
    window = open_window(wide_project)
    text = window.editor.toPlainText()
    start = text.index(SPACED) + len("Commune ")
    _place(window.editor, start, start + len("sanctorum "))

    def typed_hi(dialog):
        dialog.filter_box.setText("hi")
        dialog._accept_current()
        return dialog.result()

    dialogs.expect("dialog", typed_hi)
    window.source_wrap_element_action.trigger()
    assert "Commune <hi>sanctorum </hi>" in window.editor.toPlainText()
    assert window.editor.textCursor().selectedText() == "sanctorum "
