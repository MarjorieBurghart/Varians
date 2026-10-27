# -*- coding: utf-8 -*-
"""Boîte « Règles Schematron du document… » (V0.9.2.5).

Elle montre les déclarations Schematron (``<?xml-model?>``) du document
affiché, ou de l'édition quand une partie est affichée : pour chacune, le
fichier des règles et la phase vérifiée, choisie dans une liste (« phase par
défaut », ``#ALL``, puis les ``sch:phase`` du fichier). « Ajouter… » déclare
un fichier de règles, « Retirer » enlève une déclaration, « Ouvrir » affiche
le fichier. OK écrit les changements dans le texte du document
(``xml_model_edit``), en une seule modification annulable ; le document est
ensuite validé de nouveau. La déclaration reste standard, comme écrite à la
main.

On l'ouvre par un clic sur l'étiquette Schematron de la barre d'état
(``ClickableLabel``) ou par le bouton « Règles… » du panneau de validation.
"""
from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlparse

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QComboBox, QDialog, QDialogButtonBox, QFileDialog, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from app_context import tr as _t
from schema_resolution import _local_href_path, _url_cache_path, default_schema_cache_dir
from xml_model_edit import add_declaration, remove_declaration, schematron_declarations, set_phase

_GENERIC = ("", "#ALL")


class ClickableLabel(QLabel):
    """Étiquette qui signale un clic (``clicked``)."""

    clicked = Signal()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.text():
            self.clicked.emit()
        super().mouseReleaseEvent(event)


class SchematronRulesDialog(QDialog):
    """La boîte (voir le module). ``text`` : le texte du document, modifié
    au fil des choix ; ``phases_of(href)`` : les phases du fichier déclaré ;
    ``base`` : le dossier du document (adresses relatives)."""

    def __init__(self, parent, text, name, base, phases_of, start_dir):
        super().__init__(parent)
        self.text = text
        self.open_href = None
        self._base = Path(base)
        self._phases_of = phases_of
        self._start_dir = str(start_dir)
        self.setWindowTitle(_t("schematron.dialog.title"))
        self.resize(640, 320)
        layout = QVBoxLayout(self)
        intro = QLabel(_t("schematron.dialog.intro", name=name))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(intro)
        self.table = QTableWidget(0, 2, self)
        self.table.setHorizontalHeaderLabels([_t("schematron.dialog.file"), _t("schematron.dialog.phase")])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table, 1)
        self.empty = QLabel(_t("schematron.dialog.none"))
        layout.addWidget(self.empty)
        buttons = QHBoxLayout()
        self.add_button = QPushButton(_t("schematron.dialog.add"))
        self.remove_button = QPushButton(_t("schematron.dialog.remove"))
        self.open_button = QPushButton(_t("schematron.dialog.open"))
        self.add_button.clicked.connect(self.add)
        self.remove_button.clicked.connect(lambda: self.remove(self.table.currentRow()))
        self.open_button.clicked.connect(self._open_current)
        for button in (self.add_button, self.remove_button, self.open_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)
        box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        box.accepted.connect(self.accept)
        box.rejected.connect(self.reject)
        layout.addWidget(box)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        self._fill()

    # --- Lignes ---------------------------------------------------------------------

    def _fill(self):
        declarations = schematron_declarations(self.text)
        self.table.setRowCount(len(declarations))
        for row, declaration in enumerate(declarations):
            item = QTableWidgetItem(declaration.href)
            item.setToolTip(declaration.href)
            self.table.setItem(row, 0, item)
            combo = QComboBox(self.table)
            phases = list(_GENERIC) + [phase for phase in self._phases_of(declaration.href) if phase not in _GENERIC]
            unknown = declaration.phase not in phases and declaration.phase != "#DEFAULT"
            if declaration.phase not in phases:
                phases.append(declaration.phase)
            for phase in phases:
                combo.addItem(self._label(phase, not (unknown and phase == declaration.phase)), phase)
            combo.setCurrentIndex(phases.index(declaration.phase))
            combo.currentIndexChanged.connect(lambda _index, row=row, combo=combo:
                                              self.choose_phase(row, combo.currentData()))
            self.table.setCellWidget(row, 1, combo)
        self.empty.setVisible(not declarations)
        self._update_buttons()

    @staticmethod
    def _label(phase, known=True):
        if phase == "":
            return _t("schematron.dialog.default_phase")
        if phase == "#ALL":
            return _t("schematron.dialog.all_phases")
        return phase if known else _t("schematron.dialog.unknown_phase", phase=phase)

    def _update_buttons(self):
        selected = 0 <= self.table.currentRow() < self.table.rowCount()
        self.remove_button.setEnabled(selected)
        self.open_button.setEnabled(selected)

    def row_count(self):
        return self.table.rowCount()

    def href(self, row):
        return self.table.item(row, 0).text()

    def _combo(self, row):
        return self.table.cellWidget(row, 1)

    def phase_choices(self, row):
        combo = self._combo(row)
        return [combo.itemData(index) for index in range(combo.count())]

    def phase_label(self, row, phase):
        combo = self._combo(row)
        return combo.itemText(self.phase_choices(row).index(phase))

    def current_phase(self, row):
        return self._combo(row).currentData()

    # --- Changements ----------------------------------------------------------------

    def choose_phase(self, row, phase):
        """La déclaration de la ligne *row* demande la phase *phase*."""
        if schematron_declarations(self.text)[row].phase == phase:
            return
        self.text = set_phase(self.text, row, phase)
        combo = self._combo(row)
        if combo.currentData() != phase:
            combo.blockSignals(True)
            combo.setCurrentIndex(self.phase_choices(row).index(phase))
            combo.blockSignals(False)

    def add(self):
        """Choisit un fichier de règles et le déclare."""
        fn, _ = QFileDialog.getOpenFileName(
            self, _t("schematron.dialog.add.title"), self._start_dir,
            f"Schematron (*.sch);;RELAX NG (*.rng);;XML Schema (*.xsd);;{_t('common.all_files')} (*)")
        if fn:
            self.add_href(relative_href(fn, self._base))

    def add_href(self, href, phase=""):
        self.text = add_declaration(self.text, href, phase)
        self._fill()
        self.table.selectRow(self.table.rowCount() - 1)

    def remove(self, row):
        if 0 <= row < self.table.rowCount():
            self.text = remove_declaration(self.text, row)
            self._fill()

    def _open_current(self):
        row = self.table.currentRow()
        if 0 <= row < self.table.rowCount():
            self.open_href = self.href(row)
            self.accept()


def relative_href(path, base) -> str:
    """Adresse de *path* relative au dossier *base*, en barres obliques ;
    une adresse ``file:`` si aucun chemin relatif n'existe (autre lecteur)."""
    path = Path(path).expanduser().resolve()
    try:
        return Path(os.path.relpath(path, Path(base).expanduser().resolve())).as_posix()
    except ValueError:
        return path.as_uri()


def is_remote(href) -> bool:
    return urlparse(href).scheme in ("http", "https")


def replace_text(text_document, old, new):
    """Remplace *old* par *new* dans *text_document* en une seule
    modification annulable, limitée à la partie qui change."""
    start = 0
    limit = min(len(old), len(new))
    while start < limit and old[start] == new[start]:
        start += 1
    end_old, end_new = len(old), len(new)
    while end_old > start and end_new > start and old[end_old - 1] == new[end_new - 1]:
        end_old -= 1
        end_new -= 1
    cursor = QTextCursor(text_document)
    cursor.beginEditBlock()
    cursor.setPosition(start)
    cursor.setPosition(end_old, QTextCursor.MoveMode.KeepAnchor)
    cursor.insertText(new[start:end_new])
    cursor.endEditBlock()


class SchematronRulesMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _rules_target(self):
        """Le document dont les déclarations sont montrées : l'édition quand
        une de ses parties est affichée, sinon le document affiché."""
        edition = self._assembly_context()
        return edition if edition is not None else self.document

    def _declaration_path(self, href, session):
        """Fichier d'une déclaration de *session* (la copie du cache pour
        une adresse distante), ou None."""
        if is_remote(href):
            path = _url_cache_path(href, default_schema_cache_dir())
            return path if path.is_file() else None
        if session.path is None:
            return None
        return _local_href_path(href, Path(session.path))

    def _declared_phases(self, href, session):
        """Phases du fichier déclaré par *href* et des fichiers qu'il inclut
        (leur texte non enregistré s'ils sont ouverts et modifiés dans
        Varians)."""
        from schematron import _phases
        path = self._declaration_path(href, session)
        if path is None or not path.is_file():
            return ()
        try:
            return tuple(_phases(path, texts=self._unsaved_rules_texts([path])))
        except Exception:
            return ()

    def schematron_rules_dialog(self):
        """Ouvre la boîte (voir le module) ; vrai si le document a changé
        ou qu'un fichier de règles a été ouvert."""
        session = self._rules_target()
        if session is None or session.text_document is None:
            return False
        text = session.text_document.toPlainText()
        base = Path(session.path).parent if session.path is not None else Path(self.project.root_dir)
        dialog = SchematronRulesDialog(self, text, self._document_tab_name(session), base,
                                       lambda href: self._declared_phases(href, session),
                                       Path(self.project.root_dir) / "xml")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        changed = dialog.text != text
        if changed:
            replace_text(session.text_document, text, dialog.text)
            session.modified = True
            self.validate_relaxng_document(show_panel=False, automatic=True, background=True)
        if dialog.open_href:
            path = self._declaration_path(dialog.open_href, session)
            if path is not None:
                self._open_rules_file(str(path), 1)
                return True
        return changed
