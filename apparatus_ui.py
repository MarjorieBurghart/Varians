# -*- coding: utf-8 -*-
"""Aide ▸ « Débugger l'apparat… » : requêtes XPath toutes prêtes pour repérer
les erreurs d'un apparat en parallel segmentation (voir apparatus_xpath), et
requêtes personnelles nommées, enregistrées dans project.xml.

La requête choisie est lancée dans le panneau XPath, sur le document
affiché : un clic sur un résultat mène à l'élément trouvé.
"""
from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QListWidget, QMessageBox, QPushButton, QRadioButton, QVBoxLayout,
)
from app_context import tr as _t
from apparatus_xpath import incomplete_app_xpath, part_witnesses, repeated_witness_xpath, witness_ids, witness_xpath
from project_config import XPathQuery
from project_management import update_project_xpath_queries
from xpath_search import TEI_NS, XML_NS


def _label(text, parent):
    """Étiquette en texte brut : « <app> » ne doit pas être pris pour du HTML."""
    label = QLabel(text, parent)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    return label


def xpath_error(expression):
    """Message de lxml si ``expression`` n'est pas une expression XPath 1.0
    valide (préfixes ``tei:`` et ``xml:`` connus), sinon None."""
    from lxml import etree
    try:
        etree.XPath(expression, namespaces={"tei": TEI_NS, "xml": XML_NS})
    except etree.XPathError as exc:
        return str(exc)
    return None


class XPathQueryDialog(QDialog):
    """Nom et expression d'une requête personnelle. Refuse une expression
    invalide ou un nom déjà pris (``taken``)."""

    def __init__(self, name="", expression="", taken=(), parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("apparatus.query.title"))
        self.resize(640, 140)
        self._taken = set(taken)
        form = QFormLayout(self)
        self.name_edit = QLineEdit(name, self)
        self.expression_edit = QLineEdit(expression, self)
        form.addRow(_t("apparatus.query.name"), self.name_edit)
        form.addRow(_t("apparatus.query.expression"), self.expression_edit)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                   parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        form.addRow(buttons)
        for edit in (self.name_edit, self.expression_edit):
            edit.textChanged.connect(self._update_ok_button)
        self._update_ok_button()

    def _update_ok_button(self, *_args):
        self.ok_button.setEnabled(bool(self.query().name and self.query().expression))

    def query(self):
        return XPathQuery(self.name_edit.text().strip(), self.expression_edit.text().strip())

    def accept(self):
        query = self.query()
        if query.name in self._taken:
            QMessageBox.warning(self, self.windowTitle(), _t("apparatus.query.duplicate", name=query.name))
            return
        error = xpath_error(query.expression)
        if error is not None:
            QMessageBox.warning(self, self.windowTitle(), _t("apparatus.query.invalid", error=error))
            return
        super().accept()


class ApparatusDebugDialog(QDialog):
    """Choix d'un contrôle de l'apparat ou d'une requête personnelle.

    ``save(queries)`` enregistre la liste des requêtes personnelles après
    chaque ajout, modification ou suppression ; elle renvoie False en cas
    d'échec (la liste affichée n'est alors pas modifiée)."""

    # Origine de la liste des témoins (apparatus_xpath.part_witnesses).
    _WITNESS_SOURCES = {"document": "apparatus.witnesses", "part": "apparatus.witnesses.part",
                        "locus": "apparatus.witnesses.locus", "wit": "apparatus.witnesses.wit"}

    def __init__(self, ids, queries, proposed_expression, save, parent=None, source="document"):
        """``source`` : d'où vient la liste ``ids`` (« document » : le
        ``<listWit>`` du document affiché ; pour une partie d'une édition
        assemblée, voir ``part_witnesses``)."""
        super().__init__(parent)
        self.setWindowTitle(_t("apparatus.title"))
        self.resize(640, 520)
        self._ids = list(ids)
        self._queries = list(queries)
        self._proposed = proposed_expression
        self._save = save
        root = QVBoxLayout(self)
        root.addWidget(_label(_t("apparatus.hint"), self))
        self.witnesses_label = _label(_t(self._WITNESS_SOURCES[source], ids=", ".join(self._ids)) if self._ids
                                      else _t("apparatus.no_witness"), self)
        root.addWidget(self.witnesses_label)

        self.choices = QButtonGroup(self)
        self.repeated_radio = QRadioButton(_t("apparatus.check.repeated"), self)
        self.incomplete_radio = QRadioButton(_t("apparatus.check.incomplete"), self)
        self.witness_radio = QRadioButton(_t("apparatus.check.witness"), self)
        self.query_radio = QRadioButton(_t("apparatus.check.query"), self)
        for button in (self.repeated_radio, self.incomplete_radio, self.witness_radio, self.query_radio):
            self.choices.addButton(button)
            button.toggled.connect(self._update_search_button)
        root.addWidget(self.repeated_radio)
        root.addWidget(self.incomplete_radio)

        witness_row = QHBoxLayout()
        self.witness_combo = QComboBox(self)
        self.witness_combo.addItems(self._ids)
        self.presence_combo = QComboBox(self)
        self.presence_combo.addItems([_t("apparatus.present"), _t("apparatus.absent")])
        self.scope_combo = QComboBox(self)
        self.scope_combo.addItems([_t("apparatus.scope.all"), _t("apparatus.scope.rdg")])
        witness_row.addWidget(self.witness_radio)
        for combo in (self.witness_combo, self.presence_combo, self.scope_combo):
            witness_row.addWidget(combo)
            combo.activated.connect(lambda _index: self.witness_radio.setChecked(True))
        witness_row.addStretch(1)
        root.addLayout(witness_row)

        root.addWidget(self.query_radio)
        self.queries_list = QListWidget(self)
        self.queries_list.currentRowChanged.connect(self._query_row_changed)
        self.queries_list.itemDoubleClicked.connect(lambda _item: self.edit_query())
        root.addWidget(self.queries_list, 1)
        query_buttons = QHBoxLayout()
        self.add_btn = QPushButton(_t("apparatus.query.add"), self)
        self.edit_btn = QPushButton(_t("apparatus.query.edit"), self)
        self.remove_btn = QPushButton(_t("apparatus.query.remove"), self)
        self.add_btn.clicked.connect(self.add_query)
        self.edit_btn.clicked.connect(self.edit_query)
        self.remove_btn.clicked.connect(self.remove_query)
        for button in (self.add_btn, self.edit_btn, self.remove_btn):
            query_buttons.addWidget(button)
        query_buttons.addStretch(1)
        root.addLayout(query_buttons)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.search_btn = buttons.addButton(_t("apparatus.search"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

        # Sans <listWit>, seules les requêtes personnelles restent utilisables.
        for widget in (self.repeated_radio, self.incomplete_radio, self.witness_radio,
                       self.witness_combo, self.presence_combo, self.scope_combo):
            widget.setEnabled(bool(self._ids))
        (self.repeated_radio if self._ids else self.query_radio).setChecked(True)
        self._refresh_queries()

    # --- Requête choisie --------------------------------------------------------

    def selected_expression(self):
        """Expression XPath du choix courant, ou None."""
        if self.query_radio.isChecked():
            row = self.queries_list.currentRow()
            return self._queries[row].expression if 0 <= row < len(self._queries) else None
        if not self._ids:
            return None
        if self.repeated_radio.isChecked():
            return repeated_witness_xpath(self._ids)
        if self.incomplete_radio.isChecked():
            return incomplete_app_xpath(self._ids)
        return witness_xpath(self.witness_combo.currentText(), present=self.presence_combo.currentIndex() == 0,
                             rdg_only=self.scope_combo.currentIndex() == 1)

    def _update_search_button(self, *_args):
        self.search_btn.setEnabled(self.selected_expression() is not None)

    def _query_row_changed(self, row):
        if row >= 0:
            self.query_radio.setChecked(True)
        selected = 0 <= row < len(self._queries)
        self.edit_btn.setEnabled(selected)
        self.remove_btn.setEnabled(selected)
        self._update_search_button()

    # --- Requêtes personnelles ------------------------------------------------

    def _refresh_queries(self, current=-1):
        self.queries_list.blockSignals(True)
        self.queries_list.clear()
        for query in self._queries:
            self.queries_list.addItem(query.name)
            self.queries_list.item(self.queries_list.count() - 1).setToolTip(query.expression)
        self.queries_list.setCurrentRow(current)
        self.queries_list.blockSignals(False)
        self._query_row_changed(current)

    def _store(self, queries, current):
        if not self._save(queries):
            return False
        self._queries = list(queries)
        self._refresh_queries(current)
        return True

    def add_query(self):
        """« Ajouter… » : propose la requête en cours du panneau XPath."""
        dialog = XPathQueryDialog("", self._proposed, [q.name for q in self._queries], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return self._store(self._queries + [dialog.query()], len(self._queries))

    def edit_query(self):
        row = self.queries_list.currentRow()
        if not 0 <= row < len(self._queries):
            return False
        query = self._queries[row]
        taken = [q.name for q in self._queries if q is not query]
        dialog = XPathQueryDialog(query.name, query.expression, taken, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        queries = list(self._queries)
        queries[row] = dialog.query()
        return self._store(queries, row)

    def remove_query(self):
        row = self.queries_list.currentRow()
        if not 0 <= row < len(self._queries):
            return False
        answer = QMessageBox.question(
            self, self.windowTitle(), _t("apparatus.query.remove.question", name=self._queries[row].name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return False
        return self._store(self._queries[:row] + self._queries[row + 1:], -1)


class ApparatusDebugMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def debug_apparatus(self):
        """Aide ▸ « Débugger l'apparat… ». True si une requête a été lancée."""
        text = self.editor.toPlainText()
        # Partie d'une édition assemblée : ses propres témoins (son <listWit>,
        # les <locus target> de l'édition, sinon ses @wit).
        if self.document.is_part:
            ids, source = part_witnesses(text, self.edition_session.text_document.toPlainText())
        else:
            ids, source = witness_ids(text), "document"
        dialog = ApparatusDebugDialog(ids, self.project.xpath_queries, self.xpath_query.text().strip(),
                                      self._save_xpath_queries, self, source=source)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        expression = dialog.selected_expression()
        if expression is None:
            return False
        self.xpath_query.setText(expression)
        self.run_xpath_search()
        return True

    def _save_xpath_queries(self, queries):
        """Enregistre les requêtes personnelles dans project.xml."""
        try:
            update_project_xpath_queries(self.project.path, queries)
        except Exception as exc:
            QMessageBox.critical(self, _t("apparatus.title"), str(exc))
            return False
        self.project = replace(self.project, xpath_queries=tuple(queries))
        return True
