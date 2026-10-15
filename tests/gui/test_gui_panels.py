# -*- coding: utf-8 -*-
"""Panneaux de la vraie fenêtre : validation RELAX NG, XPath, synchronisation
des témoins et aperçu XSLT. Tests de caractérisation (V0.8.5.26.2)."""
from __future__ import annotations

from PySide6.QtCore import Qt


def _insert_after(window, marker, text):
    source = window.editor.toPlainText()
    pos = source.index(marker) + len(marker)
    cursor = window.editor.textCursor()
    cursor.setPosition(pos)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def _line_of(window, needle):
    return window.editor.toPlainText()[: window.editor.toPlainText().index(needle)].count("\n") + 1


# --- Validation RELAX NG ----------------------------------------------------

def test_valid_document_has_no_rng_issue(open_window, example_project):
    window = open_window(example_project)
    window.validate_relaxng_manual()               # aucune boîte de dialogue
    assert window.validation_panel.isVisible()
    assert window.validation_table.rowCount() == 0
    assert window._last_rng_result is not None and window._last_rng_result.valid


def test_rng_error_is_listed_and_navigable(open_window, example_project):
    window = open_window(example_project)
    _insert_after(window, "<body>", "\n<forbidden/>")

    window.validate_relaxng_manual()

    assert window.validation_panel.isVisible()
    assert window.validation_table.rowCount() >= 1
    assert window._last_rng_result is not None and not window._last_rng_result.valid
    # La ligne affichée est celle que libxml2 rapporte ; le double-clic y mène.
    reported_line = int(window.validation_table.item(0, 1).text())
    assert reported_line > 0
    window.left_tabs.setCurrentWidget(window.formatted_view)
    window.editor.moveCursor(window.editor.textCursor().MoveOperation.End)
    window.goto_validation_issue(0)
    assert window.left_tabs.currentIndex() == 0
    assert window.editor.textCursor().blockNumber() + 1 == reported_line


def test_editing_invalidates_previous_rng_issues(open_window, example_project):
    window = open_window(example_project)
    _insert_after(window, "<body>", "\n<forbidden/>")
    window.validate_relaxng_manual()
    assert window.validation_table.rowCount() >= 1

    _insert_after(window, "<body>", " ")
    assert window._last_rng_result is None
    assert window.validation_table.rowCount() == 0


# --- XPath --------------------------------------------------------------------

def test_xpath_search_lists_matches_and_selects_them(open_window, example_project):
    window = open_window(example_project)
    window.xpath_query.setText("//tei:body")
    window.run_xpath_search()

    assert window.xpath_panel.isVisible()
    assert window.xpath_table.rowCount() == 1
    window.goto_xpath_result(0)
    assert window.left_tabs.currentIndex() == 0
    assert window.editor.textCursor().selectedText().startswith("<body")


def test_xpath_count_returns_scalar(open_window, example_project):
    window = open_window(example_project)
    window.xpath_query.setText("count(//tei:body)")
    window.run_xpath_search()
    assert window.xpath_table.rowCount() == 0
    assert "1" in window.xpath_summary.text()


def test_xpath_syntax_error_is_reported(open_window, example_project):
    window = open_window(example_project)
    window.xpath_query.setText("//[")
    window.run_xpath_search()
    assert window.xpath_table.rowCount() == 0
    assert window.xpath_summary.text()


# --- Synchronisation XML -> témoins ------------------------------------------

def test_cursor_on_lb_synchronizes_witness_panels(open_window, example_project):
    window = open_window(example_project)
    assert window.base_alignment_available
    spans = window.lb_spans()
    assert len(spans) > 20

    target = 15
    cursor = window.editor.textCursor()
    cursor.setPosition(spans[target][1])
    window.editor.setTextCursor(cursor)
    window.sync_panels_to_cursor(force=True)

    assert window.ordinal_at_cursor() == target
    base_panel = window.panels[window.base_id]
    assert base_panel.center_index == target
    assert base_panel.primary_key == window.base_items[target]["key"]
    for panel in window.panels.values():
        if panel.sync_enabled:
            assert panel.primary_key == window.base_items[target]["key"]


def test_navigate_to_base_ordinal_moves_xml_cursor(open_window, example_project, qtbot):
    window = open_window(example_project)
    spans = window.lb_spans()
    window.navigate_to_base_ordinal(30)
    assert window.editor.textCursor().position() == spans[30][1]
    assert window.panels[window.base_id].center_index == 30
    qtbot.wait(150)                                  # libération du verrou de synchro


# --- Aperçu XSLT ----------------------------------------------------------------

def test_preview_tab_renders_xslt_output(open_window, example_project, qtbot):
    window = open_window(example_project)
    window.left_tabs.setCurrentWidget(window.formatted_view)
    qtbot.waitUntil(lambda: len(window.formatted_view.preview.toPlainText()) > 1000, timeout=15000)
    rendered = window.formatted_view.preview.toPlainText()
    assert "Troyes" in rendered or "Sermo" in rendered or len(rendered) > 1000


def test_preview_follows_source_changes(open_window, example_project, qtbot):
    window = open_window(example_project)
    window.left_tabs.setCurrentWidget(window.formatted_view)
    qtbot.waitUntil(lambda: len(window.formatted_view.preview.toPlainText()) > 1000, timeout=15000)

    window.left_tabs.setCurrentIndex(0)
    marker = "MARQUEURDETEST"
    source = window.editor.toPlainText()
    pos = source.index("<lb", source.index("<body>"))
    cursor = window.editor.textCursor()
    cursor.setPosition(pos)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(marker + " ")

    window.left_tabs.setCurrentWidget(window.formatted_view)
    qtbot.waitUntil(lambda: marker in window.formatted_view.preview.toPlainText(), timeout=15000)


def test_xpath_panel_selection_role_data(open_window, example_project):
    """Les résultats XPath portent leurs positions dans UserRole."""
    window = open_window(example_project)
    window.xpath_query.setText("//tei:body")
    window.run_xpath_search()
    data = window.xpath_table.item(0, 0).data(Qt.ItemDataRole.UserRole)
    start, end, line = data
    assert window.editor.toPlainText()[start:end].startswith("<body")
    assert line == _line_of(window, "<body")
