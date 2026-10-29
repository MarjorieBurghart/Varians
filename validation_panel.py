# -*- coding: utf-8 -*-
"""Panneau de validation RELAX NG et résolution du schéma du document.

La validation elle-même se fait dans un processus séparé (validation_worker) :
la validation automatique (ouverture, changement de document, modification)
n'attend pas sa réponse, la fenêtre reste utilisable pendant la compilation
d'un gros schéma ; la validation demandée (F8, enregistrement) l'attend en
laissant la fenêtre se redessiner.

Édition assemblée par XInclude (V0.9.0.0) : l'édition et chacune de ses
parties font valider l'édition assemblée, avec le schéma de l'édition et le
texte non enregistré des parties ouvertes. Le résultat est rangé sur
l'édition et sur ses parties ; une colonne Document indique le fichier de
chaque erreur, et l'onglet de chaque partie prend la couleur de ses propres
erreurs.

Règles Schematron (V0.9.2.3) : celles des sources de la résolution
(``SchemaResolution.schematron_sources``) sont appliquées dans le même
passage ; une colonne Origine distingue leurs messages (XML, RELAX NG,
XInclude, Schematron). Une erreur Schematron rend le document invalide comme
une erreur RELAX NG (onglet orange, question avant d'enregistrer) ; un
avertissement ou une information non. L'étiquette Schematron de la barre
d'état résume leur résultat ; son info-bulle donne les sources des règles et
le détail d'une règle incorrecte.

Phases et règles incorrectes (V0.9.2.4) : l'info-bulle nomme la phase de
chaque source ; une règle incorrecte (domaine SCHEMATRON_RULES) a sa ligne
dans le panneau, après les messages du document, sans le rendre invalide ;
le double-clic mène au fichier des règles, à la ligne de la règle (Varians
propose d'ajouter aux documents un fichier du dossier du projet qui n'en est
pas un). Un résultat dont le schéma ou les règles ont changé depuis est
périmé : il est validé de nouveau à l'affichage du document.

Règles non enregistrées (V0.9.2.5) : un fichier de règles ouvert et modifié
est appliqué avec son texte non enregistré (``_rules_texts``) ; le jeton
compte la révision de ce texte, et l'info-bulle le signale. De même
(V0.9.2.6) pour un fichier qu'il inclut (``_unsaved_rules_texts``,
``schematron.rules_files``) ; l'info-bulle nomme alors les fichiers non
enregistrés de la source.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QFrame, QHBoxLayout, QHeaderView, QLabel, QMessageBox, QTableWidget,
    QTableWidgetItem, QToolButton, QVBoxLayout,
)
from app_context import call_later, remember_rules_choice, rules_choice, tr as _t
from project_config import DocumentConfig
from relaxng_validation import ValidationIssue, lxml_available, relaxng_schema_token
from schema_resolution import detect_xml_models, resolve_schema, rules_outside
from text_search import Utf16Positions
from validation_worker import worker_client
from xml_assembly import path_key

# Colonnes du panneau : Niveau, Origine, Ligne, Colonne, Message, Document ;
# la colonne Document n'est affichée que pour une édition qui a des parties.
_MESSAGE_COLUMN = 4
_DOCUMENT_COLUMN = 5
_LEVELS = {"WARNING": "rng.level.warning", "INFO": "rng.level.info"}
RULES_DOMAIN = "SCHEMATRON_RULES"
_ORIGINS = {"SCHEMATRON": "rng.origin.schematron", "XINCLUDE": "rng.origin.xinclude", "XSLT": "rng.origin.xslt",
            RULES_DOMAIN: "rng.origin.schematron_rules"}
# Codes des règles incorrectes (schematron.SchematronReport.errors) ;
# « declaration » : une déclaration Schematron que la résolution n'a pas pu
# suivre ; « assembly » et, pour la structure, « element », « attribute »,
# « required » : à la vérification d'un fichier .sch (schematron_check).
_RULES_CODES = ("missing", "malformed", "xpath", "compile", "runtime", "declaration", "assembly")
# Codes dont le message est « nom, tabulation, parent ».
_STRUCTURE_CODES = ("element", "attribute", "required")


def _is_error(issue):
    """Vrai pour une erreur du document, faux pour un avertissement, une
    information ou une règle incorrecte."""
    return str(issue.level).upper() not in _LEVELS and issue.domain != RULES_DOMAIN


def _rules_message(issue):
    """Le message d'une règle incorrecte, dans la langue de l'interface."""
    if issue.type_name == "phase":
        phase, _tab, phases = issue.message.partition("\t")
        return _t("schematron.rules.phase", phase=phase, phases=phases or "—")
    if issue.type_name in _STRUCTURE_CODES:
        name, _tab, parent = issue.message.partition("\t")
        return _t(f"schematron.rules.{issue.type_name}", name=name, parent=parent)
    code = issue.type_name if issue.type_name in _RULES_CODES else "compile"
    return _t(f"schematron.rules.{code}", detail=issue.message or issue.file)


def _rules_located(issue):
    """« fichier:ligne: message » d'une règle incorrecte."""
    name = Path(issue.file).name if issue.file else ""
    place = f"{name}:{issue.line}: " if issue.line else (f"{name}: " if name else "")
    return place + _rules_message(issue)


def _is_schematron(issue):
    return issue.domain == "SCHEMATRON"


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
        # Déclarations Schematron du document (V0.9.2.5).
        self.validation_rules = QToolButton(panel)
        self.validation_rules.setText(_t("schematron.panel.rules_button"))
        self.validation_rules.setToolTip(_t("schematron.panel.rules_button.tip"))
        self.validation_rules.clicked.connect(self.schematron_rules_dialog)
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
        head.addWidget(self.validation_rules)
        head.addWidget(self.validation_refresh)
        head.addWidget(self.validation_close)
        root.addLayout(head)

        self.validation_table = QTableWidget(0, 6, panel)
        self.validation_table.setHorizontalHeaderLabels([
            _t("rng.column.level"), _t("rng.column.origin"), _t("rng.column.line"),
            _t("rng.column.column"), _t("rng.column.message"), _t("rng.column.document"),
        ])
        header = self.validation_table.horizontalHeader()
        for column in range(6):
            header.setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(_MESSAGE_COLUMN, QHeaderView.ResizeMode.Stretch)
        self.validation_table.setColumnHidden(_DOCUMENT_COLUMN, True)
        self.validation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.validation_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.validation_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setMouseTracking(True)
        self.validation_table.viewport().setMouseTracking(True)
        self.validation_table.cellDoubleClicked.connect(self.goto_validation_issue)
        root.addWidget(self.validation_table, 1)
        panel.setVisible(False)
        worker_client().fellBack.connect(self._rng_worker_fell_back)
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
            self.rng_status.setText(_t("rng.status.none") if self._schema_mode == "none" else _t("rng.status.pending"))
            self.rng_status.setStyleSheet("color:#777" if self._schema_mode == "none" else "")
        if hasattr(self, "schematron_status"):
            self._set_schematron_label()

    def show_validation_panel(self):
        # Une hauteur modeste garde la vue d'édition utilisable sur petit écran.
        self._rng_watch_enabled = True
        self._show_bottom_panel(self.validation_panel, 180)
        # L'onglet XPath, le masquage du panneau ou la restauration d'une
        # fenêtre ne doivent pas faire réapparaître des erreurs anciennes.
        # F8 a déjà validé la révision courante : aucune passe redondante.
        if (self._schema_mode != 'none'
                and not getattr(self, '_rng_validation_in_progress', False)
                and self._last_rng_revision != self.editor.document().revision()):
            self.rng_refresh_timer.stop()
            self._auto_refresh_rng()

    def hide_validation_panel(self):
        self._hide_bottom_panel(self.validation_panel)

    def _clear_validation_table(self):
        self.validation_table.setRowCount(0)

    def _populate_validation_issues(self, issues, *, jump_to_xml=True):
        self._clear_validation_table()
        # Colonne Document : pour une édition assemblée, ou des erreurs dans
        # d'autres fichiers (feuille importée par une feuille XSLT).
        assembled = self._assembly_context() is not None or any(self._foreign_issue(i) for i in issues)
        self.validation_table.setColumnHidden(_DOCUMENT_COLUMN, not assembled)
        for issue in issues:
            row = self.validation_table.rowCount()
            self.validation_table.insertRow(row)
            values = [
                _t(_LEVELS.get(str(issue.level).upper(), "rng.level.error")),
                self._issue_origin(issue),
                str(issue.line or ""),
                str(issue.column or ""),
                self._issue_message(issue),
                self._issue_document_name(issue) if assembled else "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.validation_table.setItem(row, col, item)
            # La donnée est attachée à la première cellule pour le double-clic.
            self.validation_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                (int(issue.line or 0), int(issue.column or 0), bool(jump_to_xml), issue.file, issue.domain),
            )

    @staticmethod
    def _issue_origin(issue):
        """Colonne Origine : XML (bonne formation), RELAX NG, XInclude,
        Schematron, ou XSLT (vérification d'une feuille)."""
        domain = str(issue.domain or "").upper()
        if domain in _ORIGINS:
            return _t(_ORIGINS[domain])
        return _t("rng.origin.relaxng") if domain.startswith("RELAXNG") else _t("rng.origin.xml")

    @staticmethod
    def _issue_message(issue):
        """Message d'une erreur ; un problème d'inclusion est mis en forme
        dans la langue de l'interface (voir validate_assembled)."""
        if issue.domain == "XINCLUDE":
            return _t(f"rng.xinclude.{issue.type_name}", detail=issue.message)
        if issue.domain == RULES_DOMAIN:
            return _rules_message(issue)
        return issue.message

    def _issue_session(self, file):
        """Document d'une erreur de l'édition assemblée : l'édition pour un
        fichier vide, sinon la partie de ce chemin (None si inconnue)."""
        if not file:
            return self.edition_session
        key = path_key(file)
        return next((session for session in self.documents
                     if session.path is not None and path_key(session.path) == key), None)

    def _foreign_issue(self, issue):
        """Vrai pour une erreur d'un autre fichier que le document affiché,
        hors édition assemblée."""
        return bool(issue.file and self.document.path is not None and self._assembly_context() is None
                    and path_key(issue.file) != path_key(self.document.path))

    def _issue_document_name(self, issue):
        session = self._issue_session(issue.file)
        return self._document_tab_name(session) if session is not None else Path(issue.file).name

    def goto_validation_issue(self, row, _column=0):
        """Double-clic sur une erreur : place le curseur à la ligne XML, dans
        le document de l'erreur pour une édition assemblée."""
        item = self.validation_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        line, column, jump_to_xml, file, domain = data
        if domain == RULES_DOMAIN:
            self._open_rules_file(file, line)
            return
        if not jump_to_xml or line <= 0:
            return
        target = self._issue_session(file) if self._assembly_context() is not None else self.document
        if file and self._assembly_context() is None and self.document.path is not None \
                and path_key(file) != path_key(self.document.path):
            target = self._issue_session(file)                 # une feuille importée, si elle est au projet
        if target is None:
            return
        if target is not self.document:
            if not self.show_document(target):
                return
            self.show_document_tab(target)
            # Le défilement du document affiché est restauré juste après.
            call_later(0, self, lambda: self.document is target and self._goto_line(line, column))
        self._goto_line(line, column)

    def _open_rules_file(self, file, line):
        """Double-clic sur une règle incorrecte : affiche son fichier, à sa
        ligne (au début si elle est inconnue). Un fichier du dossier du
        projet qui n'est pas un document du projet peut y être ajouté ; un
        fichier hors du projet ne s'ouvre pas."""
        path = Path(file) if file else None
        if path is None or not path.is_file():
            return
        target = self._issue_session(str(path))
        if target is None:
            path = path.resolve()
            if not path.is_relative_to(Path(self.project.root_dir).resolve()):
                self.statusBar().showMessage(_t("schematron.rules.outside", name=path.name, path=str(path)), 10000)
                return
            answer = QMessageBox.question(
                self, _t("schematron.rules.add.title"), _t("schematron.rules.add.text", name=path.name),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.Yes)
            if answer != QMessageBox.StandardButton.Yes or not self._register_document(DocumentConfig(path)):
                return
            target = self._issue_session(str(path))
            if target is None:
                return
        line = max(1, int(line or 0))
        if target is not self.document:
            if not self.show_document(target):
                return
            self.show_document_tab(target)
        # Le défilement du document affiché est restauré juste après.
        call_later(0, self, lambda: self.document is target and self._goto_line(line, 1))
        self._goto_line(line, 1)

    def _goto_line(self, line, column):
        self.left_tabs.setCurrentIndex(0)
        block = self.editor.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        # Les colonnes libxml2 sont 1-based lorsqu'elles sont connues ; elles
        # comptent des caractères, Qt des unités UTF-16 (red team, A2).
        line_text = block.text()
        offset = min(max(0, int(column or 1) - 1), len(line_text))
        cursor.setPosition(block.position() + Utf16Positions(line_text).qt(offset))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    # --- Édition assemblée ----------------------------------------------------

    def _assembly_context(self):
        """L'édition, si le document affiché en fait partie (l'édition ou
        l'une de ses parties) et qu'elle a des parties : la validation porte
        alors sur l'édition assemblée. Sinon None."""
        if self.document.in_edition and self._edition_has_parts():
            return self.edition_session
        return None

    def _assembly_texts(self, displayed_text):
        """Texte de l'édition et ``{chemin: texte}`` des parties à valider
        autrement que sur le disque : le document affiché (``displayed_text``,
        instantané) et les parties modifiées."""
        def text_of(session):
            return displayed_text if session is self.document else session.text_document.toPlainText()

        parts = {str(session.path): text_of(session) for session in self.documents
                 if session.is_part and session.text_document is not None
                 and (session is self.document or session.modified)}
        return text_of(self.edition_session), parts

    def _open_unsaved_texts(self):
        """``{chemin: texte}`` des documents ouverts et modifiés hors de
        l'édition (fichiers de règles, feuilles XSLT…). Une modification
        défaite jusqu'à l'état enregistré n'en est plus une
        (``QTextDocument.isModified``)."""
        return {str(session.path): session.text_document.toPlainText() for session in self.documents
                if session.path is not None and session.text_document is not None and not session.in_edition
                and session.text_document.isModified()}

    def _unsaved_rules_texts(self, paths, texts=None):
        """``{chemin: texte}`` des documents ouverts et modifiés qui sont l'un
        des fichiers de règles *paths* (V0.9.2.5) ou (V0.9.2.6) un fichier
        qu'ils incluent ; *texts* : ceux de ``_open_unsaved_texts``, s'ils
        sont déjà connus."""
        texts = self._open_unsaved_texts() if texts is None else texts
        if not texts:
            return {}
        from schematron import rules_files
        keys = {path_key(file) for path in paths for file in rules_files(path, texts)}
        return {path: text for path, text in texts.items() if path_key(path) in keys}

    def _rules_texts(self, resolution):
        """``{chemin: texte}`` des fichiers de règles de *resolution*, et des
        fichiers qu'ils incluent, ouverts dans Varians et modifiés : leur
        texte non enregistré est appliqué à la place du disque."""
        return self._unsaved_rules_texts(tuple(getattr(resolution, "schematron_sources", ()) or ()))

    def _source_tip_name(self, name, path, texts):
        """*name*, le nom de la source *path* dans l'info-bulle, avec ses
        fichiers non enregistrés (*texts*, ``{chemin: texte}``) : la source
        seule (V0.9.2.5), ou (V0.9.2.6) les fichiers qu'elle inclut."""
        from schematron import rules_files
        unsaved = {path_key(file) for file in texts}
        if not unsaved:
            return name
        files = [file for file in rules_files(path, texts) if path_key(file) in unsaved]
        if any(path_key(file) != path_key(path) for file in files):
            return _t("schematron.tip.unsaved_included", name=name, files=", ".join(file.name for file in files))
        return _t("schematron.tip.unsaved", name=name) if files else name

    def _rng_invalid_for(self, session, result):
        """True si ``result`` signale une erreur dans ``session`` : toute
        erreur hors d'une édition assemblée, sinon celles de son fichier (un
        avertissement ne compte pas)."""
        if result is None or result.valid:
            return False
        if not (session.in_edition and self._edition_has_parts()):
            return True
        return any(_is_error(issue) and self._issue_session(issue.file) is session for issue in result.issues)

    def _share_assembled_result(self, result):
        """Résultat de l'édition assemblée, obtenu pour le document affiché :
        rangé aussi sur l'édition et sur ses parties chargées, avec l'état RNG
        affiché ; l'onglet de chacune prend la couleur de ses propres erreurs."""
        rng = (self.rng_status.text(), self.rng_status.styleSheet(), self.schematron_status.text(),
               self.schematron_status.styleSheet(), self.schematron_status.toolTip(), self.validation_summary.text())
        for session in self.documents:
            if session is self.document or not session.in_edition:
                continue
            if session.text_document is not None:
                session.last_rng_result = result
                session.last_rng_revision = session.text_document.revision()
                session.last_rng_schema_token = self._last_rng_schema_token
                status = (session.view_state or {}).get("status")
                if status:
                    session.view_state["status"] = status[:2] + rng
            if session.health != "malformed":
                session.health = "rng_invalid" if self._rng_invalid_for(session, result) else "normal"
            self._refresh_document_tab(session)

    def _assembly_changed(self):
        """Le document affiché, édition ou partie, vient de changer : le
        résultat partagé de l'édition assemblée n'est plus valable pour les
        autres documents ; ils seront validés à nouveau à leur affichage."""
        if getattr(self, "_loading_editor_document", False) or self._assembly_context() is None:
            return
        # L'aperçu de l'édition assemblée contient aussi le texte des parties.
        self.formatted_view.dirty_preview = True
        for session in self.documents:
            if session is self.document or not session.in_edition or session.last_rng_result is None:
                continue
            session.invalidate_rng()
            if session.view_state:
                session.view_state["status"] = None
            if session.health == "rng_invalid":
                session.health = "normal"
                self._refresh_document_tab(session)

    def _auto_refresh_rng(self):
        """A01: revalide l'état courant, même après masquage du panneau.

        Le délai de frappe est conservé, mais le rechargement du tableau ne
        dépend plus du fait que le widget soit visible à l'instant du signal.
        """
        if (not self._rng_watch_enabled or self._schema_mode == 'none'
                or getattr(self, '_loading_editor_document', False)):
            return
        revision = self.editor.document().revision()
        if revision == self._last_rng_revision and self._last_rng_result is not None:
            return
        self.validate_relaxng_document(show_panel=False, automatic=True,
                                       document_revision=revision, background=True)

    def validate_relaxng_manual(self):
        self.validate_relaxng_document(show_panel=True, show_success_message=True, ask_rules=True)

    def refresh_schema_cache(self):
        """Force le rechargement d'un RNG distant déclaré par xml-model."""
        self._completion_model = None
        self._completion_model_key = None
        self.validate_relaxng_document(show_panel=True, show_success_message=True, refresh_schema=True,
                                       ask_rules=True)

    def _set_schematron_label(self, text="", style="", tip=""):
        """L'étiquette Schematron de la barre d'état ; un clic ouvre la boîte
        des règles (V0.9.2.5), que l'info-bulle annonce."""
        if text:
            tip = "\n".join(part for part in (tip, _t("schematron.tip.click")) if part)
        self.schematron_status.setText(text)
        self.schematron_status.setStyleSheet(style)
        self.schematron_status.setToolTip(tip)

    # --- Règles hors du projet (red team, B2) --------------------------------

    def _rules_to_confirm(self, resolution):
        """Les sources de règles de *resolution* à confirmer : hors du
        projet (``schema_resolution.rules_outside``)."""
        sources = tuple(getattr(resolution, "schematron_sources", ()) or ())
        trusted = (self._schema_file,) if self._schema_file else ()
        return rules_outside(sources, self.project.root_dir, trusted=trusted) if sources else ()

    def _allowed_rules(self, resolution):
        """*resolution* sans les sources hors du projet que l'utilisatrice
        n'a pas acceptées, rangées dans ``schematron_refused`` (sans
        question)."""
        refused = tuple(source for source in self._rules_to_confirm(resolution) if rules_choice(source) is not True)
        if not refused:
            return resolution
        keys = {path_key(source) for source in refused}
        return replace(resolution, schematron_refused=tuple(resolution.schematron_refused) + refused,
                       schematron_sources=tuple(source for source in resolution.schematron_sources
                                                if path_key(source) not in keys))

    def _approved_rules(self, resolution, *, ask_refused=False):
        """Demande s'il faut appliquer chaque source hors du projet sans
        réponse mémorisée, ou (*ask_refused* : F8) refusée ; renvoie
        *resolution* sans celles qui restent refusées."""
        for source in self._rules_to_confirm(resolution):
            choice = rules_choice(source)
            if choice is None or (ask_refused and choice is False):
                remember_rules_choice(source, self._ask_rules(source))
        return self._allowed_rules(resolution)

    def _ask_rules(self, source):
        """La question pour la source *source* : True pour l'appliquer."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setTextFormat(Qt.TextFormat.PlainText)
        box.setWindowTitle(_t("schematron.outside.title"))
        box.setText(_t("schematron.outside.text", path=str(Path(source)), command=_t("toolbar.validate_rng")))
        apply_button = box.addButton(_t("schematron.outside.apply"), QMessageBox.ButtonRole.AcceptRole)
        skip_button = box.addButton(_t("schematron.outside.skip"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(skip_button)
        box.setEscapeButton(skip_button)
        box.exec()
        return box.clickedButton() is apply_button

    def _update_schematron_status(self, resolution):
        """Avant la validation : l'étiquette Schematron quand aucune règle ne
        sera vérifiée (validation désactivée, ou aucune source) ; sinon elle
        attend le résultat (``_show_schematron_result``)."""
        if self._schema_mode == "none":
            declared = bool(getattr(resolution, "schematron", ()) if resolution is not None else ())
            self._set_schematron_label(_t("schematron.status.disabled") if declared else "", "color:#777",
                                       _t("schematron.tip.disabled") if declared else "")
        elif resolution is None or not (resolution.schematron_sources or resolution.schematron_errors):
            self._set_schematron_label()

    @staticmethod
    def _resolution_rules_errors(resolution):
        """Les déclarations Schematron que la résolution n'a pas pu suivre,
        comme des règles incorrectes (code ``declaration``)."""
        return tuple(ValidationIssue(0, 0, "ERROR", str(error), RULES_DOMAIN, "declaration", str(href))
                     for href, error in (getattr(resolution, "schematron_errors", ()) or ()))

    def _schematron_problems(self, resolution, result):
        """Les règles incorrectes, pour l'info-bulle et le résumé : celles du
        résultat (qui reprend déjà celles de la résolution), sinon celles de
        la résolution."""
        return tuple(result.schematron_errors if result is not None
                     else self._resolution_rules_errors(resolution))

    def _show_schematron_result(self, resolution, result):
        """Étiquette Schematron d'après le résultat (None : règles non
        appliquées, document mal formé ou schéma impossible à charger)."""
        problems = self._schematron_problems(resolution, result)
        sources = tuple(getattr(resolution, "schematron_sources", ()) or ())
        applied = tuple(result.schematron_rules) if result is not None else ()
        tips = [_rules_located(issue) for issue in problems]
        if applied:
            phases = {path_key(source): getattr(source, "phase", "") for source in sources}
            texts = self._rules_texts(resolution)
            names = [_t("schematron.tip.phase", name=Path(path).name, phase=phases[path_key(path)])
                     if phases.get(path_key(path)) else Path(path).name for path in applied]
            names = [self._source_tip_name(name, path, texts) for name, path in zip(names, applied)]
            tips.insert(0, _t("schematron.tip.sources", sources=", ".join(names)))
        refused = tuple(getattr(resolution, "schematron_refused", ()) or ())
        if refused:
            tips.append(_t("schematron.tip.refused", files=", ".join(str(Path(path)) for path in refused)))
        messages = [issue for issue in (result.issues if result is not None else ()) if _is_schematron(issue)]
        errors = sum(1 for issue in messages if _is_error(issue))
        if result is not None and result.schematron_error == "saxon_missing":
            self._set_schematron_label(_t("schematron.status.saxon_missing"), "color:#a14b2f",
                                       _t("schematron.tip.saxon_missing"))
        elif problems:
            self._set_schematron_label(_t("schematron.status.rules_error"), "color:#a13d32;font-weight:600",
                                       "\n".join(tips))
        elif refused and not applied:
            self._set_schematron_label(_t("schematron.status.refused"), "color:#a14b2f", "\n".join(tips))
        elif result is None or not (result.well_formed and result.schema_loaded):
            self._set_schematron_label()
        elif errors:
            self._set_schematron_label(_t("schematron.status.errors", count=errors),
                                       "color:#a06a20;font-weight:600", "\n".join(tips))
        elif messages:
            self._set_schematron_label(_t("schematron.status.messages", count=len(messages)), "color:#8b641d",
                                       "\n".join(tips))
        elif applied:
            self._set_schematron_label(_t("schematron.status.valid"), "color:#376b3c", "\n".join(tips))
        elif sources and getattr(resolution, "schematron", ()):
            self._set_schematron_label(_t("schematron.status.no_rules"), "color:#777", _t(
                "schematron.tip.no_rules", sources=", ".join(Path(path).name for path in sources)))
        else:
            self._set_schematron_label()

    def _schematron_summary(self, resolution, result):
        """Phrases ajoutées au résumé du panneau : règles incorrectes, Saxon
        absent."""
        notes = [_t("schematron.panel.rules_error", source=Path(issue.file).name, detail=_rules_located(issue))
                 for issue in self._schematron_problems(resolution, result)]
        if result is not None and result.schematron_error == "saxon_missing":
            notes.append(_t("schematron.panel.saxon_missing"))
        return "".join(" " + note for note in notes)

    def _validation_outdated(self, session):
        """Vrai si le schéma ou les règles du document affiché (*session*)
        ont changé depuis son dernier résultat : un fichier de règles
        enregistré entre-temps, par exemple."""
        token = session.last_rng_schema_token
        if session.last_rng_result is None or self._schema_mode == "none" or not token:
            return False
        # Fichier Schematron (V0.9.2.6) : un fichier qu'il inclut a changé.
        if token[0] == "schematron":
            try:
                return (self._displayed_schematron() is not None
                        and self._schematron_inclusions(session)[1] != token)
            except Exception:
                return False
        if token[0] == "xslt" or self._displayed_stylesheet() is not None or self._displayed_schematron() is not None:
            return False
        try:
            current = self._validation_token(self._resolve_completion_schema())
        except Exception:
            return False
        return current is not None and current != token

    def _validation_token(self, resolution):
        """Jeton du schéma et des sources des règles : il change si l'un de
        ces fichiers ou de ceux qu'ils incluent change (None : inconnu), ou
        (V0.9.2.5) le texte non enregistré d'un fichier de règles ouvert."""
        if resolution is None:
            return None
        resolution = self._allowed_rules(resolution)
        paths = [Path(resolution.schema_path)] if resolution.schema_path is not None else []
        paths += [Path(source) for source in resolution.schematron_sources if Path(source) not in paths]
        unsaved = {path_key(path) for path in self._rules_texts(resolution)}
        revisions = tuple(("unsaved", path_key(session.path), session.text_document.revision())
                          for session in self.documents
                          if session.path is not None and path_key(session.path) in unsaved)
        try:
            return tuple(relaxng_schema_token(path) for path in paths) + revisions
        except Exception:
            return None

    def _schema_display_name(self, resolution):
        if resolution is None:
            return ""
        if resolution.href:
            try:
                return Path(resolution.href).name or resolution.href
            except Exception:
                return resolution.href
        if resolution.schema_path:
            return Path(resolution.schema_path).name
        # Des règles Schematron sans RELAX NG.
        return ", ".join(Path(path).name for path in resolution.schematron_sources)

    def validate_relaxng_document(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False, background=False, ask_rules=False):
        """Valide la révision courante, sans revalidation récursive du panneau.

        ``background`` : sans attendre la réponse (validation automatique) ;
        renvoie alors None, le résultat est affiché à son arrivée.
        ``ask_rules`` (F8) : redemander pour les règles hors du projet
        refusées (``_approved_rules``)."""
        if getattr(self, '_rng_validation_in_progress', False):
            return None
        self._rng_validation_in_progress = True
        try:
            return self._validate_relaxng_document_impl(
                show_panel=show_panel, show_success_message=show_success_message,
                refresh_schema=refresh_schema, xml_text=xml_text,
                document_revision=document_revision, automatic=automatic, background=background,
                ask_rules=ask_rules,
            )
        finally:
            self._rng_validation_in_progress = False

    def _validate_relaxng_document_impl(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False, background=False, ask_rules=False):
        """Résout puis valide le RNG actif.

        ``xml_text`` permet à Ctrl+S de réutiliser son unique instantané du
        document. La compilation du RNG lui-même est mise en cache dans
        relaxng_validation.py depuis la V0.5.6.
        """
        text = self.editor.toPlainText() if xml_text is None else xml_text
        revision = self.editor.document().revision() if document_revision is None else int(document_revision)
        # Une feuille XSLT est vérifiée par sa compilation (xslt_check_ui).
        if self._displayed_stylesheet() is not None:
            return self._check_stylesheet(text, revision, show_panel=show_panel,
                                          show_success_message=show_success_message,
                                          automatic=automatic, background=background)
        # Un fichier Schematron est vérifié à part (schematron_check_ui).
        if self._displayed_schematron() is not None:
            return self._check_schematron(text, revision, show_panel=show_panel,
                                          show_success_message=show_success_message,
                                          automatic=automatic, background=background)
        # Édition assemblée : le schéma est celui de l'édition, même quand une
        # partie est affichée.
        edition = self._assembly_context()
        schema_text, schema_xml_path = text, self.current_path or self.project.edition
        if edition is not None and edition is not self.document:
            schema_text = edition.text_document.toPlainText()
            schema_xml_path = edition.path or self.project.edition
        key = self._schema_resolution_cache_key(schema_text)
        if not refresh_schema and self._completion_resolution_key == key and self._completion_resolution is not None:
            resolution = self._completion_resolution
        else:
            resolution = resolve_schema(
                mode=self._schema_mode,
                xml_text=schema_text,
                xml_path=schema_xml_path,
                project_schema=self._schema_file,
                force_refresh=refresh_schema,
            )
        # Le chargement/résolution du schéma peut être long (cache distant).
        # Si le document a changé entre-temps, ne jamais publier les anciennes
        # erreurs comme si elles concernaient la révision désormais affichée.
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        # La validation explicite vient de faire le travail de résolution : la
        # complétion peut réutiliser exactement ce résultat tant que xml-model
        # n'est pas modifié.
        self._completion_resolution_key = self._schema_resolution_cache_key(schema_text)
        self._completion_resolution = resolution
        # Règles hors du projet : appliquées seulement si l'utilisatrice les
        # accepte (red team, B2).
        resolution = self._approved_rules(resolution, ask_refused=ask_rules)
        self._last_schema_resolution = resolution
        self._update_schematron_status(resolution)

        if self._schema_mode == "none":
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
            self._show_schematron_result(resolution, None)
            self.validation_summary.setText(_t("rng.panel.schema_resolution_error", error=resolution.error))
            self.rng_status.setText(_t("rng.status.schema_error"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            return None

        if resolution.schema_path is None and not resolution.schematron_sources:
            self._show_schematron_result(resolution, None)
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            if self._schema_mode == "auto":
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
        sources = resolution.schematron_sources
        rules = self._rules_texts(resolution)
        base_url = self.current_path or self.project.edition
        parts = None
        if edition is not None:
            text, parts = self._assembly_texts(text)
            base_url = edition.path or self.project.edition
        options = dict(revision=revision, schema=schema, resolution=resolution, show_panel=show_panel,
                       show_success_message=show_success_message, automatic=automatic)
        self.rng_status.setText(_t("rng.status.running"))
        self.rng_status.setStyleSheet("color:#777")
        if background:
            self._validate_in_background(text, schema, base_url, options, parts, sources, rules)
            return None
        return self._apply_rng_result(
            worker_client().validate(text, schema, base_url, parts=parts, schematron=sources, rules=rules), **options)

    def _validate_in_background(self, text, schema, base_url, options, parts=None, sources=(), rules=None):
        """Validation automatique : la fenêtre reste utilisable. Le résultat est
        affiché à son arrivée s'il concerne encore le document affiché ; un
        document quitté entre-temps sera validé à nouveau à son retour."""
        session = self.document
        pending = self.__dict__.setdefault("_rng_background_pending", set())
        key = (session, options["revision"])
        if key in pending:                                  # déjà demandée
            return

        def arrived(result):
            pending.discard(key)
            if self.document is session:
                self._apply_rng_result(result, **options)
            elif session.view_state:
                session.view_state["status"] = None

        pending.add(key)
        worker_client().validate_async(text, schema, base_url, self, arrived, parts=parts, schematron=sources,
                                       rules=rules)

    def _rng_busy_changed(self, busy):
        """Lueur de la barre d'état pendant une validation en cours."""
        if busy:
            self.rng_busy.start()
        else:
            self.rng_busy.stop()

    def _rng_worker_fell_back(self, reason):
        """Le processus de validation est indisponible (signalé une fois)."""
        self.statusBar().showMessage(_t("rng.worker.fallback", reason=reason), 10000)

    def _apply_rng_result(self, result, *, revision, schema, resolution, show_panel, show_success_message, automatic):
        """Affiche le résultat de la validation de la révision ``revision`` ;
        rien si le document a changé depuis (une nouvelle validation suit)."""
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        # Les déclarations introuvables rejoignent les règles incorrectes.
        result = replace(result, schematron_errors=self._resolution_rules_errors(resolution)
                         + tuple(result.schematron_errors))
        self._last_rng_result = result
        self._last_rng_revision = revision
        self._last_rng_schema_token = self._validation_token(resolution)
        schema_name = self._schema_display_name(resolution)
        notes = self._schematron_summary(resolution, result)
        self._show_schematron_result(resolution, result)
        # Sans RELAX NG (des règles Schematron seules), l'étiquette RNG le dit.
        if schema is None:
            rng_valid = (_t("rng.status.no_xml_model"), "color:#777")
        else:
            rng_valid = (_t("rng.status.valid"), "color:#376b3c")

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
            if self._assembly_context() in (None, self.document):
                self._set_document_health("malformed")
            else:                                           # l'édition est mal formée, pas la partie
                self.edition_session.health = "malformed"
                self._refresh_document_tab(self.edition_session)
            if show_panel:
                self.show_validation_panel()
            return result

        if result.valid:
            # Des avertissements ou informations Schematron restent listés.
            messages = sum(1 for issue in result.issues if _is_schematron(issue))
            rows = tuple(result.issues) + tuple(result.schematron_errors)
            if rows:
                self._populate_validation_issues(rows, jump_to_xml=True)
            else:
                self._clear_validation_table()
            summary = (_t("rng.panel.valid.messages", schema=schema_name, count=messages) if messages
                       else _t("rng.panel.valid", schema=schema_name))
            self.validation_summary.setText(summary + notes)
            self.rng_status.setText(rng_valid[0])
            self.rng_status.setStyleSheet(rng_valid[1])
            self._set_document_health("normal")
            if self._assembly_context() is not None:
                self._share_assembled_result(result)
            if show_panel:
                self.show_validation_panel()
            if show_success_message:
                self.statusBar().showMessage(_t("rng.message.valid"), 3500)
            return result

        self._populate_validation_issues(tuple(result.issues) + tuple(result.schematron_errors), jump_to_xml=True)
        errors = [issue for issue in result.issues if _is_error(issue)]
        schematron = sum(1 for issue in errors if _is_schematron(issue))
        rng = len(errors) - schematron
        if schematron:
            summary = _t("rng.panel.invalid.schematron", count=len(errors), schema=schema_name,
                         rng=rng, schematron=schematron)
        else:
            summary = _t("rng.panel.invalid", count=len(errors), schema=schema_name)
        self.validation_summary.setText(summary + notes)
        if rng:
            self.rng_status.setText(_t("rng.status.invalid", count=rng))
            self.rng_status.setStyleSheet("color:#a06a20;font-weight:600")
        else:                                               # erreurs Schematron seulement
            self.rng_status.setText(rng_valid[0])
            self.rng_status.setStyleSheet(rng_valid[1])
        # Édition assemblée : chaque document prend la couleur de ses erreurs.
        self._set_document_health("rng_invalid" if self._rng_invalid_for(self.document, result) else "normal")
        if self._assembly_context() is not None:
            self._share_assembled_result(result)
        if not automatic:
            self.show_validation_panel()
        return result

    def _schema_resolution_cache_key(self, xml_text):
        """Clé légère : seules les déclarations xml-model influencent ce cache."""
        mode = (self._schema_mode or "auto").lower()
        project_schema = str(self._schema_file or "")
        xml_path = str((self.current_path or self.project.edition).resolve())
        declarations = detect_xml_models(xml_text) if mode in {"auto", "none"} else ()
        return (mode, project_schema, xml_path, declarations)
