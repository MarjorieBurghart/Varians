# -*- coding: utf-8 -*-
"""Panneau des résultats de la recherche XML (V0.9.2.8).

« Tout lister » (bouton près du champ de recherche, Rechercher ▸ Lister
toutes les occurrences, Ctrl+Maj+L) liste chaque occurrence de la
recherche de la barre d'outils, avec ses options (casse, expressions
régulières) : sa ligne et son contexte, le résultat surligné et centré
(KWIC, ``text_search.kwic``). Le document affiché, ou, case « Tout le
projet » cochée, tous les documents du projet, avec une colonne Document.
Un clic mène à l'occurrence (en affichant son document). Le panneau
ouvert suit les recherches, les options et le texte du document affiché.
"""
from __future__ import annotations

import re

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QFrame, QHBoxLayout, QHeaderView, QLabel, QTableWidget, QTableWidgetItem,
    QToolButton, QVBoxLayout,
)

from app_context import tr as _t
from code_editor import _search_query
from replace_bar import search_error_text
from text_search import SearchError, Utf16Positions, find_spans, kwic

# Au-delà, le panneau n'affiche que les premières occurrences.
MAX_RESULTS = 2000
_BLANKS = re.compile(r"\s+")


class SearchResultsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _build_search_results_panel(self):
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.search_results_title = QLabel(_t("results.title"), panel)
        title_font = self.search_results_title.font()
        title_font.setBold(True)
        self.search_results_title.setFont(title_font)
        self.search_results_summary = QLabel("", panel)
        self.search_results_project = QCheckBox(_t("results.all_project"), panel)
        self.search_results_project.toggled.connect(lambda _checked: self.refresh_search_results())
        self.search_results_close = QToolButton(panel)
        self.search_results_close.setText("×")
        self.search_results_close.setToolTip(_t("results.close"))
        self.search_results_close.clicked.connect(lambda: self._hide_bottom_panel(self.search_results_panel))
        head.addWidget(self.search_results_title)
        head.addWidget(self.search_results_summary, 1)
        head.addWidget(self.search_results_project)
        head.addWidget(self.search_results_close)
        root.addLayout(head)

        table = QTableWidget(0, 5, panel)
        self.search_results_table = table
        header = table.horizontalHeader()
        for column, mode in enumerate((QHeaderView.ResizeMode.ResizeToContents, QHeaderView.ResizeMode.ResizeToContents,
                                       QHeaderView.ResizeMode.Stretch, QHeaderView.ResizeMode.ResizeToContents,
                                       QHeaderView.ResizeMode.Stretch)):
            header.setSectionResizeMode(column, mode)
        table.verticalHeader().setVisible(False)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        # Le contexte avant, aligné à droite, est coupé à gauche ; le contexte
        # après, à droite : le résultat reste au centre.
        table.setTextElideMode(Qt.TextElideMode.ElideNone)
        table.setWordWrap(False)
        table.setColumnHidden(0, True)
        table.cellClicked.connect(self.goto_search_result)
        root.addWidget(table, 1)
        self._retranslate_search_results()

        self._search_results = []
        self._search_results_query = ""
        self._search_results_timer = QTimer(self)
        self._search_results_timer.setSingleShot(True)
        self._search_results_timer.setInterval(400)
        self._search_results_timer.timeout.connect(self._refresh_visible_search_results)
        panel.setVisible(False)
        return panel

    def connect_search_results(self):
        """Avec la barre d'outils et l'éditeur : le panneau ouvert suit les
        options de recherche et le texte du document affiché."""
        for action in (self.action_search_case, self.action_search_regex):
            action.toggled.connect(lambda _checked: self._refresh_visible_search_results())
        self.editor.textChanged.connect(self._search_results_text_changed)

    def _retranslate_search_results(self):
        self.search_results_title.setText(_t("results.title"))
        self.search_results_project.setText(_t("results.all_project"))
        self.search_results_close.setToolTip(_t("results.close"))
        self.search_results_table.setHorizontalHeaderLabels([
            _t("results.column.document"), _t("results.column.line"), _t("results.column.before"),
            _t("results.column.match"), _t("results.column.after"),
        ])

    def list_search_results(self):
        """« Tout lister » : ouvre le panneau avec toutes les occurrences."""
        if not self.find_box.text():
            self.find_box.setFocus()
            return
        self._show_bottom_panel(self.search_results_panel, 260)
        self.refresh_search_results()

    def _refresh_visible_search_results(self):
        if self.search_results_panel.isVisible():
            self.refresh_search_results()

    def _search_results_text_changed(self):
        if self.search_results_panel.isVisible():
            self._search_results_timer.start()

    def search_results_document_changed(self):
        """Un autre document affiché : la liste du document affiché le suit."""
        if not self.search_results_project.isChecked():
            self._refresh_visible_search_results()

    def search_results_follow(self):
        """Une nouvelle recherche dans la barre d'outils : le panneau ouvert la suit."""
        if self.search_results_panel.isVisible() and self.find_box.text() != self._search_results_query:
            self.refresh_search_results()

    def refresh_search_results(self):
        self._search_results_timer.stop()
        options = self.search_options()
        query = _search_query(self.find_box.text(), options)
        self._search_results_query = self.find_box.text()
        project = self.search_results_project.isChecked()
        sessions = list(self.documents) if project else [self.document]
        results, error, documents = [], None, 0
        if query:
            for session in sessions:
                text = self._session_text(session)
                if text is None:
                    continue
                try:
                    rows = kwic(text, find_spans(text, query, options))
                except SearchError as exc:
                    error = exc
                    results = []
                    break
                documents += bool(rows)
                results.extend((session, row) for row in rows)
        self._search_results = results
        table = self.search_results_table
        table.setColumnHidden(0, not project)
        shown = results[:MAX_RESULTS]
        table.setRowCount(len(shown))
        mono = QFont(self.editor.font())
        bold = QFont(mono)
        bold.setBold(True)
        for index, (session, row) in enumerate(shown):
            cells = (
                (self._document_tab_name(session), None, Qt.AlignmentFlag.AlignLeft),
                (str(row.line), None, Qt.AlignmentFlag.AlignRight),
                (row.before, mono, Qt.AlignmentFlag.AlignRight),
                (row.match, bold, Qt.AlignmentFlag.AlignCenter),
                (row.after, mono, Qt.AlignmentFlag.AlignLeft),
            )
            for column, (text, font, alignment) in enumerate(cells):
                item = QTableWidgetItem(text)
                item.setTextAlignment(alignment | Qt.AlignmentFlag.AlignVCenter)
                if font is not None:
                    item.setFont(font)
                if column == 3:
                    item.setBackground(QColor("#fff000"))
                    item.setForeground(QColor("#17120b"))
                table.setItem(index, column, item)
        if error is not None:
            summary = search_error_text(error)
        elif project:
            summary = _t("results.summary.project", count=len(results), query=query, documents=documents)
        else:
            summary = _t("results.summary", count=len(results), query=query)
        if len(results) > len(shown):
            summary += " — " + _t("results.truncated", shown=len(shown))
        self.search_results_summary.setText(summary)

    def goto_search_result(self, row, _column=0):
        if not 0 <= row < len(self._search_results):
            return
        session, result = self._search_results[row]
        if session is not self.document and not self.show_document(session):
            return
        self.left_tabs.setCurrentIndex(0)
        text = self.editor.toPlainText()
        if _BLANKS.sub(" ", text[result.start:result.end]) != result.match:
            # Le texte a changé depuis : la liste est refaite.
            self.refresh_search_results()
            return
        positions = Utf16Positions(text)
        start, end = positions.qt(result.start), positions.qt(result.end)
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(end)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setSearchMatch(start, end, self.find_box.text())
