# -*- coding: utf-8 -*-
"""L'état du document ouvert est porté par MainWindow.document."""
from __future__ import annotations

from pathlib import Path

from document_session import DocumentSession


def test_window_state_lives_in_document_session(open_window, example_project):
    window = open_window(example_project)
    session = window.document
    assert isinstance(session, DocumentSession)
    assert session.text_document is window.editor.document()
    assert session.path == Path(example_project).parent / "xml" / "edition.xml"
    assert session.modified is False

    # Les anciens noms d'attributs lisent et écrivent dans la session.
    assert window.current_path is session.path
    assert window.lb_spans() is session.lb.spans
    assert not session.lb.dirty

    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(" ")
    assert session.modified is True
    assert session.last_rng_result is None and session.last_rng_revision == -1


def _type_at(window, position, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_plain_typing_shifts_lb_index_without_rescan(open_window, example_project):
    from document_session import LbIndex

    window = open_window(example_project)
    lb = window.document.lb
    spans_before = list(window.lb_spans())
    target = spans_before[10][0]
    _type_at(window, target, "abc")
    assert not lb.dirty                                   # pas de nouveau balayage
    assert lb.spans == LbIndex.scan(window.editor.toPlainText(), window.lb_base_re)
    assert lb.spans[10][0] == target + 3


def test_typing_markup_invalidates_lb_index(open_window, example_project):
    window = open_window(example_project)
    window.lb_spans()
    _type_at(window, window.lb_spans()[5][0], "<hi>")
    assert window.document.lb.dirty


# --- Un QTextDocument par document ouvert ------------------------------------

def test_session_owns_the_text_document_shown_by_the_editor(open_window, example_project):
    window = open_window(example_project)
    doc = window.document.text_document
    assert window.editor.document() is doc
    assert doc.parent() is window                       # détenu par la fenêtre, pas par l'éditeur
    assert window.highlighter.document() is doc
    assert doc.defaultFont() == window.editor.font()


def _code_editor(qtbot, editor_module, text):
    from PySide6.QtGui import QTextDocument

    editor = editor_module.CodeEditor()
    qtbot.addWidget(editor)
    first = QTextDocument(editor)
    editor.set_text_document(first)
    editor.setPlainText(text)
    return editor, first


def test_switching_documents_keeps_separate_undo_histories(qtbot, editor_module):
    from PySide6.QtGui import QTextDocument

    editor, first = _code_editor(qtbot, editor_module, "<a>premier</a>")
    tab_stop = editor.tabStopDistance()
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    editor.insertPlainText(" X")

    second = QTextDocument(editor)
    second.setPlainText("<b>second</b>")
    editor.set_text_document(second)
    assert editor.toPlainText() == "<b>second</b>"
    assert editor.tabStopDistance() == tab_stop
    assert second.defaultFont() == editor.font()
    editor.moveCursor(editor.textCursor().MoveOperation.End)
    editor.insertPlainText(" Y")
    editor.undo()
    assert editor.toPlainText() == "<b>second</b>"
    assert first.toPlainText() == "<a>premier</a> X"     # l'autre document est intact

    editor.set_text_document(first)
    editor.undo()
    assert editor.toPlainText() == "<a>premier</a>"


def test_a_new_document_does_not_receive_the_scroll_of_the_previous_one(qtbot, editor_module, monkeypatch):
    """V0.9.2.6 : la position de défilement du document quitté, appliquée
    un instant au nouveau document pendant ``setDocument``, pouvait faire
    osciller les barres de défilement sans fin (Varians figé en passant
    d'une partie modifiée de l'édition à un court fichier .sch). L'éditeur
    revient en haut avant de changer de document ; la position du document
    quitté est déjà gardée par la fenêtre (``_remember_document_view``)."""
    from PySide6.QtGui import QTextDocument

    editor, _first = _code_editor(qtbot, editor_module, "\n".join(f"<l n='{i}'>{'x' * 200}</l>" for i in range(300)))
    editor.resize(500, 300)
    editor.show()
    editor.verticalScrollBar().setValue(120)
    editor.horizontalScrollBar().setValue(80)
    real = editor_module.CodeEditor.setDocument

    def checked(self, document):
        # Sans la remise à zéro, l'appel réel ne rendrait pas la main.
        assert (self.verticalScrollBar().value(), self.horizontalScrollBar().value()) == (0, 0)
        real(self, document)

    monkeypatch.setattr(editor_module.CodeEditor, "setDocument", checked)
    second = QTextDocument(editor)
    second.setPlainText("<p>court</p>")
    editor.set_text_document(second)
    assert editor.toPlainText() == "<p>court</p>"


def test_document_signals_follow_the_displayed_document(qtbot, editor_module):
    from PySide6.QtGui import QTextCursor, QTextDocument

    editor, first = _code_editor(qtbot, editor_module, "<a>\n  <b/>\n</a>")
    second = QTextDocument(editor)
    second.setPlainText("<c>\n</c>")
    editor.set_text_document(second)

    sentinel = object()
    editor._fold_regions_cache = sentinel
    QTextCursor(first).insertText("<!-- ancien -->")     # document non affiché
    assert editor._fold_regions_cache is sentinel

    QTextCursor(second).insertText("<!-- affiché -->")
    assert editor._fold_regions_cache is None


def test_typing_inside_a_tag_that_becomes_a_pivot_lb(open_window, example_project):
    """edRef="#T" -> "#T1" : le nouveau <lb/> pivot est pris en compte aussitôt."""
    window = open_window(example_project)
    text = window.editor.toPlainText()
    position = text.index("<p>", text.index("<body>")) + len("<p>")
    _type_at(window, position, '<lb edRef="#T"/>')
    before = len(window.lb_spans())                       # index reconstruit
    _type_at(window, position + len('<lb edRef="#T'), "1")
    assert len(window.lb_spans()) == before + 1
    assert window.lb_spans() == _rescan(window)


def _rescan(window):
    from document_session import LbIndex

    return LbIndex.scan(window.editor.toPlainText(), window.lb_base_re)


# --- Schéma propre à chaque document ------------------------------------------

def test_edition_session_carries_the_project_schema_and_highlighter(open_window, example_project):
    window = open_window(example_project)
    session = window.document
    assert session.role == "edition"
    assert session.schema_mode == window.project.schema_mode
    assert session.schema_file == window.project.schema
    assert session.highlighter is window.highlighter
    assert session.highlighter.document() is session.text_document


def test_validation_follows_the_schema_of_the_displayed_document(open_window, example_project):
    # Un document auxiliaire peut être dispensé de validation alors que
    # l'édition est validée : le mode de schéma est celui du document.
    from app_context import tr

    window = open_window(example_project)
    window.validate_relaxng_document(show_panel=False)
    assert window.document.last_rng_result is not None      # test.rng (xml-model)

    window.document.schema_mode = "none"
    window.validate_relaxng_document(show_panel=False)
    assert window.document.last_rng_result is None
    assert window.validation_summary.text() == tr("rng.panel.disabled")


def test_completion_follows_the_schema_of_the_displayed_document(open_window, example_project):
    window = open_window(example_project)
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("<body>") + len("<body>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("<varianstest k")
    names, _context = window._auto_attribute_choices(window.editor)
    assert names == ("kind",)

    window.document.schema_mode = "none"
    names, _context = window._auto_attribute_choices(window.editor)
    assert names == ()
