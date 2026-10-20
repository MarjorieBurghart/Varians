# -*- coding: utf-8 -*-
"""Commande « Références » : vérification des pointeurs de tous les documents
du projet et panneau des références introuvables ou ambiguës."""
from __future__ import annotations

from PySide6.QtCore import Qt

from app_context import tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents
from xml_references import collect_references

LIEUX = '<listPlace>\n<place xml:id="petrus" corresp="#nulle"/>\n</listPlace>\n'
PROBLEMS = '<persName ref="#absent">A</persName> <persName ref="#petrus">P</persName>'


def _insert_in_body(window, markup):
    text = window.editor.toPlainText()
    position = text.index("<body>") + len("<body>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)


def _with_lieux(project):
    lieux = project.parent / "xml" / "lieux.xml"
    lieux.write_text(LIEUX, encoding="utf-8")
    documents = list(load_project(project).documents) + [DocumentConfig(lieux, "Lieux")]
    update_project_documents(project, documents)
    return project


def _rows(window):
    table = window.references_table
    return [tuple(table.item(row, column).text() for column in range(table.columnCount()))
            for row in range(table.rowCount())]


def _double_click(window, qtbot, row):
    table = window.references_table
    table.scrollToItem(table.item(row, 0))
    rect = table.visualItemRect(table.item(row, 3))
    # Un vrai double-clic : appui-relâche, puis double-clic sur la même cellule.
    qtbot.mouseClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
    qtbot.mouseDClick(table.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())


def test_toolbar_command_follows_xpath_and_reports_the_example_as_resolved(open_window, example_project):
    window = open_window(example_project)
    actions = window.main_toolbar.actions()
    index = actions.index(window.action_xpath_search)
    assert actions[index + 1] is window.action_check_references
    assert window.action_check_references.text() == tr("references.action")

    window.action_check_references.trigger()
    assert window.references_panel.isVisible()
    assert window.references_table.rowCount() == 0
    count = len(collect_references(window.editor.toPlainText()))
    assert window.references_summary.text() == tr("references.summary.ok", count=count)


def test_missing_and_ambiguous_references_of_every_document_are_listed(open_window, project_with_documents):
    window = open_window(_with_lieux(project_with_documents))
    _insert_in_body(window, PROBLEMS)
    window.check_references()
    text = window.editor.toPlainText()
    line = str(text[:text.index("#absent")].count("\n") + 1)
    assert _rows(window) == [
        ("edition.xml", line, "ref", "#absent", tr("references.problem.missing")),
        ("edition.xml", line, "ref", "#petrus",
         tr("references.problem.ambiguous", targets="personnes.xml, lieux.xml")),
        ("lieux.xml", "2", "corresp", "#nulle", tr("references.problem.missing")),
    ]
    total = len(collect_references(text)) + 1                   # + celle de lieux.xml
    assert window.references_summary.text() == tr("references.summary.problems", count=total, problems=3)


def test_double_click_goes_to_the_reference_even_in_another_document(open_window, project_with_documents, qtbot):
    window = open_window(_with_lieux(project_with_documents))
    _insert_in_body(window, PROBLEMS)
    window.check_references()

    _double_click(window, qtbot, 2)
    assert window.document is window.documents[2]
    assert window.editor.textCursor().selectedText() == "#nulle"
    assert window.references_table.rowCount() == 3               # résultats conservés

    _double_click(window, qtbot, 0)
    assert window.document is window.edition_session
    assert window.editor.textCursor().selectedText() == "#absent"


def test_edits_after_the_check_do_not_shift_the_selection(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    _insert_in_body(window, PROBLEMS)
    window.check_references()
    _insert_in_body(window, "<!-- ajout -->")
    _double_click(window, qtbot, 0)
    assert window.editor.textCursor().selectedText() == "#absent"


def test_check_again_after_a_correction(open_window, project_with_documents, qtbot):
    window = open_window(project_with_documents)
    _insert_in_body(window, '<persName ref="#absent">A</persName>')
    window.check_references()
    assert window.references_table.rowCount() == 1
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("#absent"))
    cursor.setPosition(text.index("#absent") + len("#absent"), cursor.MoveMode.KeepAnchor)
    cursor.insertText("#bernard")
    qtbot.mouseClick(window.references_recheck, Qt.MouseButton.LeftButton)
    assert window.references_table.rowCount() == 0
    count = len(collect_references(window.editor.toPlainText()))
    assert window.references_summary.text() == tr("references.summary.ok", count=count)


def test_problems_never_prevent_saving(open_window, project_with_documents):
    window = open_window(project_with_documents)
    aux = window.documents[1]
    assert window.show_document(aux)
    _insert_in_body_of_list(window, '\n  <person xml:id="x" corresp="#nulle"/>')
    window.check_references()
    assert window.references_table.rowCount() == 1
    assert window.save()
    assert 'corresp="#nulle"' in aux.path.read_text(encoding="utf-8")


def _insert_in_body_of_list(window, markup):
    text = window.editor.toPlainText()
    position = text.index("</listPerson>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)


def test_bottom_panels_remain_exclusive(open_window, example_project):
    window = open_window(example_project)
    window.check_references()
    assert window.references_panel.isVisible()
    window.focus_xpath_search()
    assert window.xpath_panel.isVisible() and not window.references_panel.isVisible()
    window.check_references()
    assert window.references_panel.isVisible() and not window.xpath_panel.isVisible()
    window.validate_relaxng_manual()
    assert window.validation_panel.isVisible() and not window.references_panel.isVisible()
    window.check_references()
    window.hide_references_panel()
    assert not any(panel.isVisible() for panel in (
        window.validation_panel, window.xpath_panel, window.references_panel))
    assert window.left_splitter.sizes()[1:] == [0, 0, 0]


def test_reference_commands_follow_the_interface_language(open_window, example_project):
    window = open_window(example_project)
    window._set_language_code("en")
    try:
        assert window.action_check_references.text() == tr("references.action")
        assert window.action_go_to_reference.text() == tr("references.goto") == "Go to target"
        assert window.references_table.horizontalHeaderItem(4).text() == tr("references.column.problem")
    finally:
        window._set_language_code("fr")
