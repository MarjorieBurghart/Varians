# -*- coding: utf-8 -*-
"""Panneau inférieur de recherche XPath de la fenêtre principale."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QPushButton,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
)
from app_context import tr as _t
from xpath_search import search_xpath, XPathQueryError, XPathUnavailable


class XPathPanelMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _build_xpath_panel(self):
        """Panneau inférieur de recherche XPath avec résultats navigables."""
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.xpath_title = QLabel(_t("xpath.panel.title"))
        title_font = self.xpath_title.font(); title_font.setBold(True)
        self.xpath_title.setFont(title_font)
        self.xpath_query = QLineEdit(panel)
        self.xpath_query.setClearButtonEnabled(True)
        self.xpath_query.setPlaceholderText(_t("xpath.placeholder"))
        self.xpath_query.returnPressed.connect(self.run_xpath_search)
        self.xpath_run_button = QPushButton(_t("xpath.run"), panel)
        self.xpath_run_button.clicked.connect(self.run_xpath_search)
        self.xpath_close = QToolButton(panel)
        self.xpath_close.setText("×")
        self.xpath_close.setToolTip(_t("xpath.close"))
        self.xpath_close.clicked.connect(self.hide_xpath_panel)
        head.addWidget(self.xpath_title)
        head.addWidget(self.xpath_query, 1)
        head.addWidget(self.xpath_run_button)
        head.addWidget(self.xpath_close)
        root.addLayout(head)

        self.xpath_summary = QLabel("")
        self.xpath_summary.setWordWrap(True)
        root.addWidget(self.xpath_summary)

        self.xpath_table = QTableWidget(0, 4, panel)
        self.xpath_table.setHorizontalHeaderLabels([
            _t("xpath.column.line"), _t("xpath.column.element"),
            _t("xpath.column.path"), _t("xpath.column.preview"),
        ])
        header = self.xpath_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.xpath_table.setColumnWidth(2, 300)
        self.xpath_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.xpath_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.xpath_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.xpath_table.setAlternatingRowColors(True)
        self.xpath_table.setMouseTracking(True)
        self.xpath_table.viewport().setMouseTracking(True)
        # La palette claire de sélection est installée globalement pour que
        # XPath, RELAX NG et les autres listes aient le même rendu lisible.
        # Un simple clic suffit, conformément au comportement demandé.
        self.xpath_table.cellClicked.connect(self.goto_xpath_result)
        root.addWidget(self.xpath_table, 1)
        panel.setVisible(False)
        return panel

    def show_xpath_panel(self):
        self._show_bottom_panel(self.xpath_panel, 250)

    def hide_xpath_panel(self):
        self._hide_bottom_panel(self.xpath_panel)

    def focus_xpath_search(self):
        self.left_tabs.setCurrentIndex(0)
        self.show_xpath_panel()
        selected = self.editor.textCursor().selectedText().strip()
        if selected and selected.startswith("//") and "\u2029" not in selected:
            self.xpath_query.setText(selected)
        self.xpath_query.setFocus()
        self.xpath_query.selectAll()

    def run_xpath_search(self):
        expression = self.xpath_query.text().strip()
        if not expression:
            self.xpath_query.setFocus()
            return
        text = self.editor.toPlainText()
        try:
            result = search_xpath(text, expression)
        except XPathUnavailable:
            self.xpath_table.setRowCount(0)
            self.xpath_summary.setText(_t("xpath.lxml_missing"))
            self.show_xpath_panel()
            return
        except XPathQueryError as exc:
            self.xpath_table.setRowCount(0)
            if str(exc) == "EMPTY_XPATH":
                self.xpath_summary.setText(_t("xpath.empty"))
            else:
                self.xpath_summary.setText(_t("xpath.error", error=exc))
            self.show_xpath_panel()
            return

        self.xpath_table.setRowCount(0)
        if result.scalar_value is not None:
            self.xpath_summary.setText(_t("xpath.scalar", value=result.scalar_value))
            self.show_xpath_panel()
            return

        for match in result.matches:
            row = self.xpath_table.rowCount()
            self.xpath_table.insertRow(row)
            values = [str(match.line or ""), match.tag, match.path, match.preview]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.xpath_table.setItem(row, col, item)
            self.xpath_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                (int(match.position), int(match.end_position), int(match.line or 0)),
            )

        if result.matches:
            if result.namespace_fallback_used:
                self.xpath_summary.setText(_t(
                    "xpath.found_tei_fallback", count=len(result.matches),
                    expression=result.effective_expression,
                ))
            else:
                self.xpath_summary.setText(_t("xpath.found", count=len(result.matches)))
        elif result.ignored_non_elements:
            self.xpath_summary.setText(_t("xpath.non_elements", count=result.ignored_non_elements))
        else:
            self.xpath_summary.setText(_t("xpath.none"))
        self.show_xpath_panel()

    def goto_xpath_result(self, row, _column=0):
        item = self.xpath_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        if len(data) >= 3:
            position, end_position, _line = data[:3]
        else:  # compatibilité défensive avec une ligne de résultat plus ancienne
            position, _line = data
            end_position = position
        self.left_tabs.setCurrentIndex(0)
        # Indices Python du résultat, positions Qt du curseur (red team, A2).
        text = self.editor.toPlainText()
        qt = self.editor.positions(text)
        cursor = self.editor.textCursor()
        start = max(0, min(int(position), len(text)))
        end = max(start, min(int(end_position), len(text)))
        cursor.setPosition(qt.qt(start))
        cursor.setPosition(qt.qt(end), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()
