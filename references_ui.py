# -*- coding: utf-8 -*-
"""Références entre les documents du projet dans la fenêtre principale :
identifiants proposés à la saisie d'un pointeur (« #bernard »).

Le calcul est fait par ``xml_references`` ; ce module fournit les textes des
documents (le document affiché tel qu'il est dans l'éditeur, les autres en
mémoire ou sur le disque) et met en cache leurs identifiants.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

from xml_references import collect_ids

_XML_ID_VALUES_RE = re.compile(r"""xml:id\s*=\s*["']([^"']*)""")


class ReferencesMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _session_text(self, session):
        """Texte d'un document : l'éditeur pour le document affiché, sinon son
        texte en mémoire, sinon son fichier (None s'il est illisible)."""
        if session is self.document:
            return self.editor.toPlainText()
        if session.text_document is not None:
            return session.text_document.toPlainText()
        try:
            return Path(session.path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None

    def _session_ids(self, session, text):
        """Identifiants d'un document, recalculés seulement si la liste de ses
        ``xml:id`` a changé (les positions peuvent alors être périmées : la
        navigation recalcule les siennes)."""
        cache = self.__dict__.setdefault("_reference_ids_cache", {})
        signature = tuple(_XML_ID_VALUES_RE.findall(text))
        key = os.path.normcase(str(Path(session.path).resolve()))
        cached = cache.get(key)
        if cached is None or cached[0] != signature:
            cached = (signature, collect_ids(text))
            cache[key] = cached
        return cached[1]

    def _reference_id_entries(self, elements=None):
        """Identifiants proposés dans le document affiché : ``[(valeur,
        description, élément)]``, ceux des autres documents d'abord.

        ``elements`` limite aux éléments de ces noms locaux (None : tous). La
        valeur est ``#id``, ou ``fichier.xml#id`` lorsque la forme courte
        désignerait un autre élément (identifiant du document affiché, ou
        présent dans plusieurs autres documents).
        """
        current = self.document
        current_dir = Path(current.path).resolve().parent
        indexes = []
        for session in self.documents:
            text = self._session_text(session)
            if text is not None:
                indexes.append((session, self._session_ids(session, text)))
        own = next((index for session, index in indexes if session is current), {})
        others = [(s, index) for s, index in indexes if s is not current]
        counts = {}
        for _session, index in others:
            for ident in index:
                counts[ident] = counts.get(ident, 0) + 1
        entries = []
        for session, index in others + [(current, own)]:
            name = Path(session.path).name
            for ident, targets in index.items():
                target = targets[0]
                if elements is not None and target.element not in elements:
                    continue
                if session is current or (ident not in own and counts.get(ident) == 1):
                    value = f"#{ident}"
                else:
                    value = f"{Path(os.path.relpath(Path(session.path).resolve(), current_dir)).as_posix()}#{ident}"
                label = target.label or target.element
                entries.append((value, f"{label} — {name}", target.element))
        return entries
