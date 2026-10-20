# -*- coding: utf-8 -*-
"""Références entre les documents du projet dans la fenêtre principale :
identifiants proposés à la saisie d'un pointeur (« #bernard »), navigation
de la référence à sa cible (F12, Ctrl+clic, menu contextuel) et retour
(Alt+←), commande « Références » et son panneau des problèmes.

Le calcul est fait par ``xml_references`` ; ce module fournit les textes des
documents (le document affiché tel qu'il est dans l'éditeur, les autres en
mémoire ou sur le disque) et met en cache leurs identifiants.
"""
from __future__ import annotations

import html
import os
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFrame, QHBoxLayout, QHeaderView, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QToolButton, QVBoxLayout,
)

from app_context import call_later, tr as _t
from completion_ui import CompletionDialog
from xml_references import REFERENCE_ATTRIBUTES, Reference, ReferenceResolver, collect_ids, parse_pointer

_XML_ID_VALUES_RE = re.compile(r"""xml:id\s*=\s*["']([^"']*)""")
_STATUS_MSEC = 6000


def _same_path(first, second):
    return (os.path.normcase(str(Path(first).resolve()))
            == os.path.normcase(str(Path(second).resolve())))


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
            relative = None
            for ident, targets in index.items():
                target = targets[0]
                if elements is not None and target.element not in elements:
                    continue
                if session is current or (ident not in own and counts.get(ident) == 1):
                    value = f"#{ident}"
                else:
                    if relative is None:
                        relative = Path(os.path.relpath(Path(session.path).resolve(), current_dir)).as_posix()
                    value = f"{relative}#{ident}"
                label = target.label or target.element
                entries.append((value, f"{label} — {name}", target.element))
        return entries

    def _reference_documents(self):
        """``[(chemin, texte)]`` des documents du projet lisibles, l'édition d'abord."""
        documents = []
        for session in self.documents:
            text = self._session_text(session)
            if text is not None:
                documents.append((session.path, text))
        return documents

    def _session_for_path(self, path):
        return next((s for s in self.documents if _same_path(s.path, path)), None)

    # --- Navigation -------------------------------------------------------

    def _install_reference_actions(self):
        """F12 et Alt+← sur l'éditeur de la source, Ctrl+clic et menu contextuel."""
        self.action_go_to_reference = QAction(_t("references.goto"), self.editor)
        self.action_go_to_reference.setShortcut(QKeySequence("F12"))
        self.action_go_to_reference.triggered.connect(lambda: self.go_to_reference())
        self.action_reference_back = QAction(_t("references.back"), self.editor)
        self.action_reference_back.setShortcut(QKeySequence("Alt+Left"))
        self.action_reference_back.triggered.connect(lambda: self.go_back())
        for action in (self.action_go_to_reference, self.action_reference_back):
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            self.editor.addAction(action)
        self.editor.reference_click_provider = self.go_to_reference
        self.editor.context_menu_provider = self._reference_context_menu

    def _reference_under(self, position):
        """Référence (``Reference``) dont le jeton contient ``position`` dans
        la source, ou None."""
        text = self.editor.toPlainText()
        try:
            context = self._source_completion_context_cache.analyze(text, position)
        except Exception:
            return None
        attribute = context.current_attribute or ""
        if context.kind != "attribute_value" or attribute.rsplit(":", 1)[-1] not in REFERENCE_ATTRIBUTES:
            return None
        start, end = context.replace_start, context.replace_end
        for piece in re.finditer(r"\S+", text[start:end]):
            if start + piece.start() <= position <= start + piece.end():
                pointer = parse_pointer(html.unescape(piece.group(0)))
                if pointer is None:
                    return None
                line = text.count("\n", 0, start + piece.start()) + 1
                return Reference(attribute, context.current_element or "", piece.group(0),
                                 pointer[0], pointer[1], start + piece.start(),
                                 start + piece.end(), line)
        return None

    def go_to_reference(self, position=None):
        """Affiche la cible de la référence sous le curseur (ou à
        ``position``) ; renvoie True si elle est affichée. Une cible définie
        plusieurs fois est choisie dans une liste ; le point de départ est
        mémorisé pour Alt+←."""
        cursor = self.editor.textCursor()
        origin = (cursor.anchor(), cursor.position()) if position is None else (position, position)
        reference = self._reference_under(cursor.position() if position is None else int(position))
        if reference is None:
            self.statusBar().showMessage(_t("references.none_here"), _STATUS_MSEC)
            return False
        resolution = ReferenceResolver(self._reference_documents()).resolve(reference, self.document.path)
        if resolution.status == "no_file":
            self.statusBar().showMessage(_t("references.no_file", file=reference.file), _STATUS_MSEC)
            return False
        if resolution.status == "missing":
            self.statusBar().showMessage(_t("references.missing", token=reference.token), _STATUS_MSEC)
            return False
        target = resolution.targets[0]
        if resolution.status == "ambiguous":
            target = self._choose_reference_target(reference, resolution.targets)
            if target is None:
                return False
        path, id_target = target
        session = self._session_for_path(path)
        if session is None:
            self.statusBar().showMessage(_t("references.outside_project", file=Path(path).name),
                                         _STATUS_MSEC)
            return False
        departure = (self.document, *origin)
        if not self._show_location(session, id_target.start, id_target.end):
            return False
        self.__dict__.setdefault("_reference_history", []).append(departure)
        self.statusBar().showMessage(
            _t("references.jumped", file=Path(path).name, line=id_target.line), _STATUS_MSEC)
        return True

    def _choose_reference_target(self, reference, targets):
        entries = {}
        items = []
        for number, (path, target) in enumerate(targets, 1):
            value = f"{number}. " + _t("references.ambiguous.item", file=Path(path).name, line=target.line)
            entries[value] = (path, target)
            items.append((value, "", target.label or target.element))
        dialog = CompletionDialog(_t("references.ambiguous.title"),
                                  _t("references.ambiguous.label", token=reference.token),
                                  items, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return entries.get(dialog.selected_value)

    def _show_location(self, session, anchor, position):
        """Affiche ``session`` dans la source et sélectionne ``anchor``…
        ``position``, au centre de l'éditeur. False si l'affichage est refusé."""
        if not self.show_document(session):
            return False
        if self.left_tabs.currentIndex() != 0:
            self.left_tabs.setCurrentIndex(0)

        def select(shown=session):
            if self.document is not shown:
                return
            last = max(0, self.editor.document().characterCount() - 1)
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(min(anchor, last))
            cursor.setPosition(min(position, last), QTextCursor.MoveMode.KeepAnchor)
            self.editor.setTextCursor(cursor)
            self.editor.centerCursor()
            self.editor.setFocus()

        select()
        # Le défilement du document affiché est restauré juste après.
        call_later(0, self, select)
        return True

    def go_back(self):
        """Revient au dernier point de départ (Alt+←), même dans un autre
        document ; les documents retirés du projet sont sautés."""
        history = self.__dict__.setdefault("_reference_history", [])
        while history:
            session, anchor, position = history.pop()
            if session in self.documents:
                return self._show_location(session, anchor, position)
        self.statusBar().showMessage(_t("references.no_history"), _STATUS_MSEC)
        return False

    def _reference_context_menu(self, menu, position):
        """Menu du clic droit de la source : « Aller à la cible » en tête
        (actif sur une référence) et « Revenir » s'il y a où revenir."""
        first = menu.actions()[0] if menu.actions() else None
        goto = QAction(_t("references.goto"), menu)
        goto.setShortcut(QKeySequence("F12"))
        goto.setEnabled(self._reference_under(position) is not None)
        goto.triggered.connect(lambda: self.go_to_reference(position))
        menu.insertAction(first, goto)
        if self.__dict__.get("_reference_history"):
            back = QAction(_t("references.back"), menu)
            back.setShortcut(QKeySequence("Alt+Left"))
            back.triggered.connect(lambda: self.go_back())
            menu.insertAction(first, back)
        if first is not None:
            menu.insertSeparator(first)

    # --- Commande « Références » et panneau ----------------------------------

    def _build_references_panel(self):
        """Panneau inférieur des références introuvables ou ambiguës."""
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.references_title = QLabel(_t("references.action"))
        title_font = self.references_title.font(); title_font.setBold(True)
        self.references_title.setFont(title_font)
        self.references_summary = QLabel("")
        self.references_summary.setWordWrap(True)
        self.references_recheck = QPushButton(_t("references.recheck"), panel)
        self.references_recheck.clicked.connect(lambda: self.check_references())
        self.references_close = QToolButton(panel)
        self.references_close.setText("×")
        self.references_close.setToolTip(_t("references.close"))
        self.references_close.clicked.connect(self.hide_references_panel)
        head.addWidget(self.references_title)
        head.addWidget(self.references_summary, 1)
        head.addWidget(self.references_recheck)
        head.addWidget(self.references_close)
        root.addLayout(head)

        self.references_table = QTableWidget(0, 5, panel)
        self._set_references_headers()
        header = self.references_table.horizontalHeader()
        for column in range(4):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch)
        self.references_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.references_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.references_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.references_table.setAlternatingRowColors(True)
        self.references_table.cellDoubleClicked.connect(self.goto_reference_problem)
        root.addWidget(self.references_table, 1)
        self._reference_check = None            # (nombre de références, problèmes)
        panel.setVisible(False)
        return panel

    def _set_references_headers(self):
        self.references_table.setHorizontalHeaderLabels([
            _t("references.column.document"), _t("references.column.line"),
            _t("references.column.attribute"), _t("references.column.value"),
            _t("references.column.problem"),
        ])

    def hide_references_panel(self):
        self._hide_bottom_panel(self.references_panel)

    def check_references(self):
        """Vérifie les références de tous les documents du projet et liste
        celles qui sont introuvables ou ambiguës. N'empêche jamais rien :
        l'enregistrement ne dépend pas de ce résultat."""
        self._reference_check = ReferenceResolver(self._reference_documents()).check()
        self._show_reference_check()
        self._show_bottom_panel(self.references_panel, 220)

    def _show_reference_check(self):
        """Résumé et lignes du panneau, dans la langue de l'interface."""
        self.references_table.setRowCount(0)
        if self._reference_check is None:
            self.references_summary.setText("")
            return
        count, problems = self._reference_check
        if not count:
            self.references_summary.setText(_t("references.summary.none"))
        elif not problems:
            self.references_summary.setText(_t("references.summary.ok", count=count))
        else:
            self.references_summary.setText(
                _t("references.summary.problems", count=count, problems=len(problems)))
        for problem in problems:
            row = self.references_table.rowCount()
            self.references_table.insertRow(row)
            reference = problem.reference
            values = (Path(problem.path).name, str(reference.line), reference.attribute,
                      reference.token, self._reference_problem_text(problem.resolution))
            for column, value in enumerate(values):
                self.references_table.setItem(row, column, QTableWidgetItem(value))
            self.references_table.item(row, 0).setToolTip(str(problem.path))

    @staticmethod
    def _reference_problem_text(resolution):
        if resolution.status == "no_file":
            return _t("references.problem.no_file")
        if resolution.status == "missing":
            return _t("references.problem.missing")
        names = [Path(path).name for path, _target in resolution.targets]
        targets = ", ".join(name if names.count(name) == 1 else f"{name}:{target.line}"
                            for name, (_path, target) in zip(names, resolution.targets))
        return _t("references.problem.ambiguous", targets=targets)

    def goto_reference_problem(self, row, _column=0):
        """Double-clic : sélectionne la référence, même dans un autre document.
        Si le texte a changé depuis la vérification, l'occurrence du jeton la
        plus proche de sa position d'alors est retenue."""
        if self._reference_check is None or not 0 <= row < len(self._reference_check[1]):
            return False
        problem = self._reference_check[1][row]
        session = self._session_for_path(problem.path)
        if session is None:
            return False
        reference = problem.reference
        text = self._session_text(session) or ""
        start = reference.start
        if text[start:start + len(reference.token)] != reference.token:
            pattern = re.compile(r"(?<![^\s\"'])" + re.escape(reference.token) + r"(?![^\s\"'])")
            found = [m.start() for m in pattern.finditer(text)]
            if found:
                start = min(found, key=lambda position: abs(position - reference.start))
        return self._show_location(session, start, start + len(reference.token))

    def _retranslate_references(self):
        self.action_go_to_reference.setText(_t("references.goto"))
        self.action_reference_back.setText(_t("references.back"))
        self.action_check_references.setText(_t("references.action"))
        self.action_check_references.setToolTip(_t("references.action.tip"))
        self.references_title.setText(_t("references.action"))
        self.references_recheck.setText(_t("references.recheck"))
        self.references_close.setToolTip(_t("references.close"))
        self._set_references_headers()
        self._show_reference_check()
