# -*- coding: utf-8 -*-
"""Panneau de validation RELAX NG et résolution du schéma du document."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout,
)
from app_context import tr as _t
from relaxng_validation import lxml_available, relaxng_schema_token, validate_relaxng
from schema_resolution import detect_xml_models, resolve_schema


class ValidationPanelMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _build_validation_panel(self):
        """Construit le panneau RELAX NG placé sous les vues XML/XSLT."""
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.validation_title = QLabel(_t("rng.panel.title"))
        title_font = self.validation_title.font(); title_font.setBold(True)
        self.validation_title.setFont(title_font)
        self.validation_summary = QLabel(_t("rng.panel.no_validation"))
        self.validation_summary.setWordWrap(True)
        self.validation_refresh = QToolButton(panel)
        self.validation_refresh.setText("↻")
        self.validation_refresh.setToolTip(_t("rng.panel.refresh"))
        self.validation_refresh.clicked.connect(self.refresh_schema_cache)
        self.validation_close = QToolButton(panel)
        self.validation_close.setText("×")
        self.validation_close.setToolTip(_t("rng.panel.close"))
        self.validation_close.clicked.connect(self.hide_validation_panel)
        head.addWidget(self.validation_title)
        head.addWidget(self.validation_summary, 1)
        head.addWidget(self.validation_refresh)
        head.addWidget(self.validation_close)
        root.addLayout(head)

        self.validation_table = QTableWidget(0, 4, panel)
        self.validation_table.setHorizontalHeaderLabels([
            _t("rng.column.level"), _t("rng.column.line"),
            _t("rng.column.column"), _t("rng.column.message"),
        ])
        header = self.validation_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.validation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.validation_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.validation_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setMouseTracking(True)
        self.validation_table.viewport().setMouseTracking(True)
        self.validation_table.cellDoubleClicked.connect(self.goto_validation_issue)
        root.addWidget(self.validation_table, 1)
        panel.setVisible(False)
        return panel

    def _reset_validation_state(self):
        """Vide tout diagnostic lié au document/projet précédent.

        Cette remise à zéro est volontairement appelée lors de chaque ouverture
        de fichier afin qu'aucune erreur RELAX NG antérieure ne reste visible
        pendant que la validation du nouveau document se prépare.
        """
        self.document.reset_validation()
        if hasattr(self, 'rng_refresh_timer'):
            self.rng_refresh_timer.stop()
        self._clear_validation_table()
        if hasattr(self, "validation_summary"):
            self.validation_summary.setText(_t("rng.panel.no_validation"))
        if hasattr(self, "rng_status"):
            self.rng_status.setText(_t("rng.status.none") if self.project.schema_mode == "none" else _t("rng.status.pending"))
            self.rng_status.setStyleSheet("color:#777" if self.project.schema_mode == "none" else "")

    def show_validation_panel(self):
        # Une hauteur modeste garde la vue d'édition utilisable sur petit écran.
        self._rng_watch_enabled = True
        self._show_bottom_panel(self.validation_panel, 180)
        # L'onglet XPath, le masquage du panneau ou la restauration d'une
        # fenêtre ne doivent pas faire réapparaître des erreurs anciennes.
        # F8 a déjà validé la révision courante : aucune passe redondante.
        if (self.project.schema_mode != 'none'
                and not getattr(self, '_rng_validation_in_progress', False)
                and self._last_rng_revision != self.editor.document().revision()):
            self.rng_refresh_timer.stop()
            self._auto_refresh_rng()

    def hide_validation_panel(self):
        self.validation_panel.setVisible(False)
        self.left_splitter.setSizes([max(300, self.left_splitter.height()), 0, 0])

    def _clear_validation_table(self):
        self.validation_table.setRowCount(0)

    def _populate_validation_issues(self, issues, *, jump_to_xml=True):
        self._clear_validation_table()
        for issue in issues:
            row = self.validation_table.rowCount()
            self.validation_table.insertRow(row)
            level_text = _t("rng.level.warning") if str(issue.level).upper() == "WARNING" else _t("rng.level.error")
            values = [
                level_text,
                str(issue.line or ""),
                str(issue.column or ""),
                issue.message,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.validation_table.setItem(row, col, item)
            # La donnée est attachée à la première cellule pour le double-clic.
            self.validation_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                (int(issue.line or 0), int(issue.column or 0), bool(jump_to_xml)),
            )

    def goto_validation_issue(self, row, _column=0):
        """Double-clic sur une erreur : place le curseur à la ligne XML."""
        item = self.validation_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        line, column, jump_to_xml = data
        if not jump_to_xml or line <= 0:
            return
        self.left_tabs.setCurrentIndex(0)
        block = self.editor.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        # Les colonnes libxml2 sont 1-based lorsqu'elles sont connues.
        offset = max(0, int(column or 1) - 1)
        offset = min(offset, max(0, block.length() - 1))
        cursor.setPosition(block.position() + offset)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    def _auto_refresh_rng(self):
        """A01: revalide l'état courant, même après masquage du panneau.

        Le délai de frappe est conservé, mais le rechargement du tableau ne
        dépend plus du fait que le widget soit visible à l'instant du signal.
        """
        if (not self._rng_watch_enabled or self.project.schema_mode == 'none'
                or getattr(self, '_loading_editor_document', False)):
            return
        revision = self.editor.document().revision()
        if revision == self._last_rng_revision and self._last_rng_result is not None:
            return
        self.validate_relaxng_document(show_panel=False, automatic=True,
                                       document_revision=revision)

    def validate_relaxng_manual(self):
        self.validate_relaxng_document(show_panel=True, show_success_message=True)

    def refresh_schema_cache(self):
        """Force le rechargement d'un RNG distant déclaré par xml-model."""
        self._completion_model = None
        self._completion_model_key = None
        self.validate_relaxng_document(show_panel=True, show_success_message=True, refresh_schema=True)

    def _update_schematron_status(self, resolution):
        count = len(getattr(resolution, "schematron", ()) or ()) if resolution is not None else 0
        if count:
            self.schematron_status.setText(_t("schematron.status.detected", count=count))
            self.schematron_status.setStyleSheet("color:#8b641d")
            self.schematron_status.setToolTip(_t("schematron.status.tooltip"))
        else:
            self.schematron_status.setText("")
            self.schematron_status.setToolTip("")

    def _schema_display_name(self, resolution):
        if resolution is None:
            return ""
        if resolution.href:
            try:
                return Path(resolution.href).name or resolution.href
            except Exception:
                return resolution.href
        return Path(resolution.schema_path).name if resolution.schema_path else ""

    def validate_relaxng_document(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False):
        """Valide la révision courante, sans revalidation récursive du panneau."""
        if getattr(self, '_rng_validation_in_progress', False):
            return None
        self._rng_validation_in_progress = True
        try:
            return self._validate_relaxng_document_impl(
                show_panel=show_panel, show_success_message=show_success_message,
                refresh_schema=refresh_schema, xml_text=xml_text,
                document_revision=document_revision, automatic=automatic,
            )
        finally:
            self._rng_validation_in_progress = False

    def _validate_relaxng_document_impl(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False):
        """Résout puis valide le RNG actif.

        ``xml_text`` permet à Ctrl+S de réutiliser son unique instantané du
        document. La compilation du RNG lui-même est mise en cache dans
        relaxng_validation.py depuis la V0.5.6.
        """
        text = self.editor.toPlainText() if xml_text is None else xml_text
        revision = self.editor.document().revision() if document_revision is None else int(document_revision)
        key = self._schema_resolution_cache_key(text)
        if not refresh_schema and self._completion_resolution_key == key and self._completion_resolution is not None:
            resolution = self._completion_resolution
        else:
            resolution = resolve_schema(
                mode=self.project.schema_mode,
                xml_text=text,
                xml_path=self.current_path or self.project.edition,
                project_schema=self.project.schema,
                force_refresh=refresh_schema,
            )
        # Le chargement/résolution du schéma peut être long (cache distant).
        # Si le document a changé entre-temps, ne jamais publier les anciennes
        # erreurs comme si elles concernaient la révision désormais affichée.
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        self._last_schema_resolution = resolution
        # La validation explicite vient de faire le travail de résolution : la
        # complétion peut réutiliser exactement ce résultat tant que xml-model
        # n'est pas modifié.
        self._completion_resolution_key = self._schema_resolution_cache_key(text)
        self._completion_resolution = resolution
        self._update_schematron_status(resolution)

        if self.project.schema_mode == "none":
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.disabled"))
            self.rng_status.setText(_t("rng.status.none"))
            self.rng_status.setStyleSheet("color:#777")
            if show_panel and not automatic:
                self.show_validation_panel()
            return None

        if resolution.error:
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.schema_resolution_error", error=resolution.error))
            self.rng_status.setText(_t("rng.status.schema_error"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            return None

        if resolution.schema_path is None:
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            if self.project.schema_mode == "auto":
                self.validation_summary.setText(_t("rng.panel.no_xml_model"))
                self.rng_status.setText(_t("rng.status.no_xml_model"))
            else:
                self.validation_summary.setText(_t("rng.panel.no_schema"))
                self.rng_status.setText(_t("rng.status.none"))
            self.rng_status.setStyleSheet("color:#777")
            if show_panel:
                self.show_validation_panel()
            if show_success_message:
                self.statusBar().showMessage(_t("rng.message.no_schema"), 4000)
            return None

        if not lxml_available():
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.lxml_missing"))
            self.rng_status.setText(_t("rng.status.unavailable"))
            self.rng_status.setStyleSheet("color:#a14b2f;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            if show_panel or show_success_message:
                QMessageBox.warning(self, _t("rng.lxml_missing.title"), _t("rng.lxml_missing.text"))
            return None

        schema = resolution.schema_path
        result = validate_relaxng(
            text, schema,
            base_url=self.current_path or self.project.edition,
        )
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        self._last_rng_result = result
        self._last_rng_revision = revision
        try:
            self._last_rng_schema_token = relaxng_schema_token(schema)
        except Exception:
            self._last_rng_schema_token = None
        schema_name = self._schema_display_name(resolution)

        if not result.schema_loaded:
            self._populate_validation_issues(result.issues, jump_to_xml=False)
            detail = result.error or _t("rng.schema.invalid.generic")
            self.validation_summary.setText(_t("rng.panel.schema_error", path=schema_name, error=detail))
            self.rng_status.setText(_t("rng.status.schema_error"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            return result

        if not result.well_formed:
            self._populate_validation_issues(result.issues, jump_to_xml=True)
            self.validation_summary.setText(_t("rng.panel.xml_invalid"))
            self.rng_status.setText(_t("rng.status.xml_invalid"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            self._set_document_health("malformed")
            if show_panel:
                self.show_validation_panel()
            return result

        if result.valid:
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.valid", schema=schema_name))
            self.rng_status.setText(_t("rng.status.valid"))
            self.rng_status.setStyleSheet("color:#376b3c")
            self._set_document_health("normal")
            if show_panel:
                self.show_validation_panel()
            if show_success_message:
                self.statusBar().showMessage(_t("rng.message.valid"), 3500)
            return result

        self._populate_validation_issues(result.issues, jump_to_xml=True)
        count = len(result.issues)
        self.validation_summary.setText(_t("rng.panel.invalid", count=count, schema=schema_name))
        self.rng_status.setText(_t("rng.status.invalid", count=count))
        self.rng_status.setStyleSheet("color:#a06a20;font-weight:600")
        self._set_document_health("rng_invalid")
        if not automatic:
            self.show_validation_panel()
        return result

    def _schema_resolution_cache_key(self, xml_text):
        """Clé légère : seules les déclarations xml-model influencent ce cache."""
        mode = (getattr(self.project, "schema_mode", "auto") or "auto").lower()
        project_schema = str(self.project.schema or "")
        xml_path = str((self.current_path or self.project.edition).resolve())
        declarations = detect_xml_models(xml_text) if mode in {"auto", "none"} else ()
        return (mode, project_schema, xml_path, declarations)
