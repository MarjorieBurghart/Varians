# -*- coding: utf-8 -*-
"""Édition par fragment dans l'aperçu d'une édition assemblée (V0.9.1.5) :
le ✎ d'un paragraphe ouvre ce paragraphe dans le fichier qui le contient, et
le fragment appliqué y est écrit, que ce fichier soit affiché ou non, et même
s'il n'a jamais été ouvert.

Jeu « sermons » (tests/data/sermons) : les ✎ de l'aperçu sont, dans l'ordre,
le titre (<head>, V0.9.2.9) et trois paragraphes de s01, de s02 et de s03, le
titre et deux paragraphes de s04, et le paragraphe de l'exemplum (inclus par
s04)."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app_context import tr

S03_FIRST = 9
EXEMPLUM = 15


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _preview(window):
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    return view


def _text(session):
    return session.text_document.toPlainText()


def _edit_fragment(view, old, new):
    text = view.fragment_editor.toPlainText()
    assert old in text
    view.fragment_editor.setPlainText(text.replace(old, new, 1))


def test_the_pencil_opens_the_paragraph_in_its_part(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)
    assert view.load_fragment(S03_FIRST)
    assert view.fragment_editor.toPlainText().startswith('<p xml:id="s03_p1">')
    assert view.fragment_editor.toPlainText().endswith("</p>")
    assert view.fragment_session is _doc(window, "s03.xml")
    assert view.frag_label.text() == tr("fragment.label.file", index=S03_FIRST + 1, total=16, file="s03.xml")
    assert window.document is window.edition_session                 # le ✎ ne déplace pas la source


def test_a_fragment_is_written_into_its_part_not_displayed(open_window, sermons_project):
    window = open_window(sermons_project)
    s03 = _doc(window, "s03.xml")
    on_disk = s03.path.read_text(encoding="utf-8")
    edition_text = _text(window.edition_session)
    view = _preview(window)
    view.load_fragment(S03_FIRST)
    _edit_fragment(view, "Surrexit Dominus", "SURREXIT Dominus")
    assert view.apply_fragment()
    assert "SURREXIT Dominus" in _text(s03) and s03.modified
    bar = window.document_tab_bar
    assert bar.tabText(window._tab_sessions.index(s03)).endswith(" *")
    assert _text(window.edition_session) == edition_text and not window.edition_session.modified
    assert s03.path.read_text(encoding="utf-8") == on_disk
    assert window.document is window.edition_session
    assert "SURREXIT Dominus" in view.preview.toPlainText()
    assert view.current_paragraph == S03_FIRST and "SURREXIT" in view.fragment_original
    # Une seule étape d'annulation, dans la partie.
    window.show_document(s03)
    window.editor.undo()
    assert s03.path.read_text(encoding="utf-8") == window.editor.toPlainText() == on_disk


def test_a_fragment_is_written_into_the_displayed_part(open_window, sermons_project):
    window = open_window(sermons_project)
    s03 = _doc(window, "s03.xml")
    window.show_document(s03)
    view = _preview(window)
    view.load_fragment(S03_FIRST + 1)
    old = view.fragment_original
    _edit_fragment(view, "</p>", " Additum.</p>")
    assert view.apply_fragment()
    assert old[:-4] + " Additum.</p>" in window.editor.toPlainText()
    assert window.document is s03 and s03.modified
    assert not window.edition_session.modified


def test_a_part_never_opened_is_loaded_then_saved_with_ctrl_s(open_window, sermons_project):
    window = open_window(sermons_project)
    exemplum = _doc(window, "s04_exemplum.xml")
    assert exemplum.text_document is None
    view = _preview(window)
    assert view.load_fragment(EXEMPLUM)
    assert view.fragment_session is exemplum and exemplum.text_document is not None
    _edit_fragment(view, "</p>", " Additum.</p>")
    window._last_save_context = "fragment"
    assert window.save_contextual()
    assert " Additum.</p>" in exemplum.path.read_text(encoding="utf-8")
    assert not exemplum.modified
    assert window.document is window.edition_session and not window.edition_session.modified
    assert window.left_tabs.currentWidget() is view


def test_a_fragment_that_would_break_its_part_is_refused(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)
    s03 = _doc(window, "s03.xml")
    view = _preview(window)
    view.load_fragment(S03_FIRST)
    _edit_fragment(view, "</p>", "")
    dialogs.expect("warning")
    assert not view.apply_fragment()
    assert dialogs.seen[-1][1] == tr("fragment.invalid.title")
    assert not s03.modified


def test_a_paragraph_changed_in_its_part_meanwhile(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)
    s03 = _doc(window, "s03.xml")
    view = _preview(window)
    view.load_fragment(S03_FIRST)
    window.show_document(s03)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("Surrexit Dominus"))
    cursor.insertText("Alleluia. ")
    window.show_document(window.edition_session)
    _edit_fragment(view, "</p>", " Additum.</p>")
    dialogs.expect("question", QMessageBox.StandardButton.No)
    assert not view.apply_fragment()
    assert dialogs.seen[-1][1] == tr("fragment.source_changed.title")
    assert "Alleluia. Surrexit" in view.fragment_editor.toPlainText()        # rechargé
    assert "Additum." not in _text(s03)


def test_an_unapplied_fragment_counts_for_its_part(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)
    view.load_fragment(S03_FIRST)
    _edit_fragment(view, "</p>", " Additum.</p>")
    assert window._unsaved_sessions() == [_doc(window, "s03.xml")]
