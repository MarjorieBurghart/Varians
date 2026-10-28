# -*- coding: utf-8 -*-
"""Chercher et remplacer dans le XML (V0.9.2.8, Ctrl+H) : une barre sous
l'éditeur de l'onglet « XML source ».

Son champ « Rechercher » partage son texte avec celui de la barre
d'outils ; les options (casse, expressions régulières) sont celles du menu
Rechercher. « Remplacer » change l'occurrence surlignée puis passe à la
suivante ; « Tout remplacer » s'annule d'un seul Ctrl+Z. Le fragment a sa
propre ligne « Remplacer par » (formatted_view)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QToolButton, QWidget

from app_context import tr as _t
from code_editor import replace_all_in_plain_editor, replace_in_plain_editor
from text_search import SearchError


def search_error_text(error: SearchError) -> str:
    """Le message d'une expression ou d'un texte de remplacement incorrect."""
    key = "replace.error.template" if error.code == "template_invalid" else "search.error.pattern"
    return _t(key, detail=error.detail)


class ReplaceBarMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _build_replace_bar(self):
        bar = QWidget(self)
        grid = QGridLayout(bar)
        grid.setContentsMargins(4, 2, 4, 2)
        grid.setHorizontalSpacing(5)
        grid.setVerticalSpacing(2)
        self.replace_find_label = QLabel(_t("replace.find.label"), bar)
        self.replace_find_box = QLineEdit(bar)
        self.replace_find_box.setClearButtonEnabled(True)
        self.replace_find_box.returnPressed.connect(lambda: self._find_source(False, self.replace_find_box))
        # « Aa » et « .* » : ajoutés avec la barre d'outils (connect_replace_bar).
        self.replace_options = QHBoxLayout()
        self.replace_options.setSpacing(2)
        self.replace_prev_button = QPushButton("◀", bar)
        self.replace_next_button = QPushButton("▶", bar)
        self.replace_prev_button.clicked.connect(lambda: self._find_source(True, self.replace_find_box))
        self.replace_next_button.clicked.connect(lambda: self._find_source(False, self.replace_find_box))
        self.replace_status = QLabel("", bar)
        self.replace_status.setMinimumWidth(54)
        self.replace_close_button = QPushButton("×", bar)
        self.replace_close_button.clicked.connect(self.hide_replace)
        self.replace_with_label = QLabel(_t("replace.with.label"), bar)
        self.replace_box = QLineEdit(bar)
        self.replace_box.setClearButtonEnabled(True)
        self.replace_box.returnPressed.connect(self.replace_source_next)
        self.replace_one_button = QPushButton(_t("replace.one"), bar)
        self.replace_all_button = QPushButton(_t("replace.all"), bar)
        self.replace_one_button.clicked.connect(self.replace_source_next)
        self.replace_all_button.clicked.connect(self.replace_source_all)

        grid.addWidget(self.replace_find_label, 0, 0)
        grid.addWidget(self.replace_find_box, 0, 1)
        grid.addLayout(self.replace_options, 0, 2)
        grid.addWidget(self.replace_prev_button, 0, 3)
        grid.addWidget(self.replace_next_button, 0, 4)
        grid.addWidget(self.replace_status, 0, 5)
        grid.addWidget(self.replace_close_button, 0, 6)
        grid.addWidget(self.replace_with_label, 1, 0)
        grid.addWidget(self.replace_box, 1, 1)
        buttons = QHBoxLayout()
        buttons.addWidget(self.replace_one_button)
        buttons.addWidget(self.replace_all_button)
        buttons.addStretch(1)
        grid.addLayout(buttons, 1, 2, 1, 5)
        grid.setColumnStretch(1, 1)
        QShortcut(QKeySequence(Qt.Key.Key_Escape), bar, self.hide_replace,
                  context=Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._retranslate_replace_bar()
        bar.setVisible(False)
        self.replace_bar = bar
        return bar

    def connect_replace_bar(self, find_box, options):
        """Avec la barre d'outils : boutons des options et texte partagé avec
        son champ de recherche."""
        for action in options:
            button = QToolButton(self.replace_bar)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            self.replace_options.addWidget(button)
        find_box.textChanged.connect(
            lambda text: self.replace_find_box.text() != text and self.replace_find_box.setText(text))
        self.replace_find_box.textChanged.connect(
            lambda text: find_box.text() != text and find_box.setText(text))

    def _retranslate_replace_bar(self):
        self.replace_find_label.setText(_t("replace.find.label"))
        self.replace_with_label.setText(_t("replace.with.label"))
        self.replace_one_button.setText(_t("replace.one"))
        self.replace_all_button.setText(_t("replace.all"))
        self.replace_prev_button.setToolTip(_t("fragment.search.prev.tip"))
        self.replace_next_button.setToolTip(_t("fragment.search.next.tip"))
        self.replace_close_button.setToolTip(_t("replace.close.tip"))

    def show_replace(self):
        """Ctrl+H : la barre de remplacement du XML, ou la ligne « Remplacer
        par » du fragment si le focus y est."""
        if self.formatted_view.focus_is_in_fragment():
            self.formatted_view.show_fragment_find(replace=True)
            return
        self.left_tabs.setCurrentIndex(0)
        selected = self.editor.textCursor().selectedText().strip()
        if selected and " " not in selected and len(selected) <= 120:
            self.replace_find_box.setText(selected)
        self.replace_status.setText("")
        self.replace_bar.setVisible(True)
        self.replace_find_box.setFocus()
        self.replace_find_box.selectAll()

    def hide_replace(self):
        self.replace_bar.setVisible(False)
        self.replace_status.setText("")
        self.editor.setFocus()

    def replace_source_next(self):
        query = self.replace_find_box.text()
        if not query:
            self.replace_find_box.setFocus()
            return
        try:
            _replaced, (found, n, total) = replace_in_plain_editor(
                self.editor, query, self.replace_box.text(), self.search_options())
        except SearchError as error:
            self._show_replace_error(error)
            return
        self.replace_status.setText(f"{n}/{total}" if found else "0/0")

    def replace_source_all(self):
        query = self.replace_find_box.text()
        if not query:
            self.replace_find_box.setFocus()
            return
        try:
            count = replace_all_in_plain_editor(self.editor, query, self.replace_box.text(), self.search_options())
        except SearchError as error:
            self._show_replace_error(error)
            return
        self.replace_status.setText("")
        self.statusBar().showMessage(_t("replace.done", count=count), 5000)

    def _show_replace_error(self, error):
        self.replace_status.setText("!")
        self.statusBar().showMessage(search_error_text(error), 5000)
