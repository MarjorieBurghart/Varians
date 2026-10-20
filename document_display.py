# -*- coding: utf-8 -*-
"""Onglets de documents affichés : lesquels, et dans quel ordre.

Le choix est mémorisé localement pour chaque projet (``documentTabs`` dans
les réglages de la vue) ; ``project.xml`` n'est pas modifié. Un document
masqué reste dans le projet : il garde ses modifications en mémoire et
Varians propose de les enregistrer avant de quitter.

- À la première ouverture, tous les onglets sont affichés ; un document
  ajouté plus tard l'est aussi, à la fin.
- Le document affiché a toujours son onglet : l'édition à l'ouverture, un
  document atteint par une référence (F12, panneau « Références »). Son
  onglet réapparaît alors durablement.
- Le dernier onglet visible ne peut pas être masqué.

Affichage ▸ « Choisir les documents affichés… » ouvre
``DocumentVisibilityDialog``, sur le modèle de la fenêtre des témoins.
"""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QDialogButtonBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QPushButton, QVBoxLayout,
)
from app_context import _settings, tr as _t
from project_management import portable_path

EDITION_KEY = "edition"
_SETTINGS_SUFFIX = "documentTabs"


def _keys(value):
    """Liste de clés lue dans les réglages ; tout autre contenu est ignoré."""
    if not isinstance(value, list):
        return []
    return [key for key in value if isinstance(key, str)]


class DocumentVisibilityDialog(QDialog):
    """Documents dont l'onglet est affiché, et ordre des onglets. OK reste
    inactif tant qu'aucun document n'est coché."""

    def __init__(self, entries, parent=None):
        """``entries`` : (clé, nom, info-bulle, visible), dans l'ordre des onglets."""
        super().__init__(parent)
        self.setWindowTitle(_t("documents.view.title"))
        self.resize(520, 400)
        root = QVBoxLayout(self)
        info = QLabel(_t("documents.view.hint"), self)
        info.setWordWrap(True)
        root.addWidget(info)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        for key, name, tip, visible in entries:
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, key)
            item.setToolTip(tip)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if visible else Qt.CheckState.Unchecked)
            self.list.addItem(item)
        root.addWidget(self.list, 1)

        controls = QHBoxLayout()
        self.all_btn = QPushButton(_t("documents.view.all"), self)
        self.none_btn = QPushButton(_t("documents.view.none"), self)
        self.up_btn = QPushButton(_t("documents.view.move_up"), self)
        self.down_btn = QPushButton(_t("documents.view.move_down"), self)
        self.all_btn.clicked.connect(lambda: self._check_all(Qt.CheckState.Checked))
        self.none_btn.clicked.connect(lambda: self._check_all(Qt.CheckState.Unchecked))
        self.up_btn.clicked.connect(lambda: self._move_current(-1))
        self.down_btn.clicked.connect(lambda: self._move_current(1))
        self.list.currentRowChanged.connect(self._update_move_buttons)
        controls.addWidget(self.all_btn)
        controls.addWidget(self.none_btn)
        controls.addStretch(1)
        controls.addWidget(self.up_btn)
        controls.addWidget(self.down_btn)
        root.addLayout(controls)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                   parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        root.addWidget(buttons)
        self.list.itemChanged.connect(self._update_ok_button)
        self.list.setCurrentRow(0)
        self._update_move_buttons()
        self._update_ok_button()

    def _update_move_buttons(self, *_args):
        row = self.list.currentRow()
        self.up_btn.setEnabled(row > 0)
        self.down_btn.setEnabled(0 <= row < self.list.count() - 1)

    def _update_ok_button(self, *_args):
        self.ok_button.setEnabled(bool(self.visible_keys()))

    def _move_current(self, direction):
        row = self.list.currentRow()
        target = row + direction
        if row < 0 or not 0 <= target < self.list.count():
            return
        self.list.insertItem(target, self.list.takeItem(row))
        self.list.setCurrentRow(target)

    def _check_all(self, state):
        for i in range(self.list.count()):
            self.list.item(i).setCheckState(state)

    def ordered_keys(self):
        """Tous les documents, cochés ou non, dans l'ordre choisi."""
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())]

    def visible_keys(self):
        return [self.list.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]

    def hidden_keys(self):
        visible = set(self.visible_keys())
        return [key for key in self.ordered_keys() if key not in visible]


class DocumentDisplayMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _document_key(self, session):
        """Clé mémorisée d'un document : ``edition`` pour l'édition (son chemin
        change avec « Enregistrer sous »), sinon son chemin dans le projet."""
        if session.is_edition:
            return EDITION_KEY
        return portable_path(self.project.root_dir, Path(session.path))

    def _document_tab_name(self, session):
        """Nom de l'onglet : « Édition », ou le label du document (à défaut,
        le nom de son fichier)."""
        return _t("documents.edition_tab") if session.is_edition else session.label

    def _load_document_tabs(self):
        """Ordre et onglets masqués mémorisés pour ce projet."""
        raw = _settings().value(self._view_settings_key(_SETTINGS_SUFFIX), "")
        try:
            saved = json.loads(raw) if isinstance(raw, str) and raw else {}
        except ValueError:
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        self._arrange_document_tabs(_keys(saved.get("order")), _keys(saved.get("hidden")))
        self._sync_document_tabs()

    def _save_document_tabs(self):
        keys = [(session, self._document_key(session)) for session in self._document_tab_order]
        _settings().setValue(self._view_settings_key(_SETTINGS_SUFFIX), json.dumps({
            "order": [key for _session, key in keys],
            "hidden": [key for session, key in keys if session in self._hidden_documents],
        }, ensure_ascii=False))

    def _arrange_document_tabs(self, order_keys, hidden_keys):
        """Ordre et documents masqués d'après leurs clés ; une clé inconnue
        est ignorée, un document absent de ``order_keys`` vient à la fin."""
        keys = {session: self._document_key(session) for session in self.documents}
        remaining = {key: session for session, key in keys.items()}
        order = [remaining.pop(key) for key in order_keys if key in remaining]
        order += remaining.values()
        hidden = set(hidden_keys)
        self._document_tab_order = order
        self._hidden_documents = {session for session in order if keys[session] in hidden}

    def _sync_document_tabs(self):
        """Suit les ajouts et retraits de documents (un nouveau document vient
        à la fin, visible), puis calcule les onglets visibles. Le document
        affiché garde son onglet."""
        present = set(self.documents)
        order = [session for session in self._document_tab_order if session in present]
        known = set(order)
        order += [session for session in self.documents if session not in known]
        self._document_tab_order = order
        self._hidden_documents &= present
        self._hidden_documents.discard(self.document)
        self._tab_sessions = [session for session in order if session not in self._hidden_documents]

    def _visible_document_sessions(self):
        """Documents qui ont un onglet, dans l'ordre des onglets."""
        return list(self._tab_sessions)

    def hide_document_tab(self, session):
        """Masque l'onglet de ``session`` ; le document reste dans le projet.

        Si c'est le document affiché, l'onglet suivant (sinon le précédent)
        est affiché à sa place. Renvoie False pour le dernier onglet visible,
        ou si l'affichage du voisin est refusé."""
        tabs = self._tab_sessions
        if session not in tabs or len(tabs) < 2:
            return False
        if session is self.document:
            index = tabs.index(session)
            neighbour = tabs[index + 1] if index + 1 < len(tabs) else tabs[index - 1]
            if not self.show_document(neighbour):
                return False
        self._hidden_documents.add(session)
        self._update_document_tabs()
        self._save_document_tabs()
        return True

    def show_document_tab(self, session):
        """Rend durablement son onglet à ``session``, à sa place dans l'ordre."""
        if session not in self._hidden_documents:
            return
        self._hidden_documents.discard(session)
        self._update_document_tabs()
        self._save_document_tabs()

    def set_document_tabs(self, order_keys, hidden_keys):
        """Ordre des onglets et documents masqués, par leurs clés (voir
        ``_document_key``), mémorisés pour le projet. Si le document affiché
        est masqué, le premier onglet visible le remplace ; si cet affichage
        est refusé, il garde son onglet."""
        self._arrange_document_tabs(order_keys, hidden_keys)
        if self.document in self._hidden_documents:
            visible = [s for s in self._document_tab_order if s not in self._hidden_documents]
            if visible:
                self.show_document(visible[0])
        self._update_document_tabs()
        self._save_document_tabs()

    def choose_displayed_documents(self):
        """Affichage ▸ « Choisir les documents affichés… ». True si le choix
        est validé."""
        entries = [(self._document_key(session), self._document_tab_name(session), str(session.path),
                    session not in self._hidden_documents)
                   for session in self._document_tab_order]
        dialog = DocumentVisibilityDialog(entries, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.set_document_tabs(dialog.ordered_keys(), dialog.hidden_keys())
        return True
