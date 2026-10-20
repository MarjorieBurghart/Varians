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
"""
from __future__ import annotations

import json
from pathlib import Path

from app_context import _settings
from project_management import portable_path

EDITION_KEY = "edition"
_SETTINGS_SUFFIX = "documentTabs"


def _keys(value):
    """Liste de clés lue dans les réglages ; tout autre contenu est ignoré."""
    if not isinstance(value, list):
        return []
    return [key for key in value if isinstance(key, str)]


class DocumentDisplayMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _document_key(self, session):
        """Clé mémorisée d'un document : ``edition`` pour l'édition (son chemin
        change avec « Enregistrer sous »), sinon son chemin dans le projet."""
        if session.is_edition:
            return EDITION_KEY
        return portable_path(self.project.root_dir, Path(session.path))

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
