# -*- coding: utf-8 -*-
"""Documents XML du projet dans la fenêtre principale : l'édition, ses
parties (V0.9.0.0 : fichiers inclus par ses xi:include) et les documents
auxiliaires déclarés dans <documents> (fichier d'autorités, notes…).

Un seul document est affiché à la fois dans l'éditeur. Chacun possède sa
session (``DocumentSession``) : texte et historique d'annulation, état
« modifié », coloration, validation, position du curseur. Les témoins, la
synchronisation et l'aperçu ne concernent que l'édition.

Les parties se déduisent des xi:include de l'édition enregistrée, sans
déclaration dans project.xml ; la liste est relue après chaque
enregistrement de l'édition ou d'une partie. Un fichier à la fois inclus et
déclaré dans <documents> est une partie : une seule session par fichier.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QTextCursor, QTextDocument
from PySide6.QtWidgets import QMessageBox, QPlainTextDocumentLayout, QTabBar, QVBoxLayout, QWidget
from app_context import call_later, current_i18n, tr as _t
from code_editor import XMLHighlighter
from document_session import DocumentSession
from project_management import update_project_documents
from lxml import etree
from xml_assembly import assemble, path_key


# Couleur du nom d'un document selon sa bonne formation (cf. _set_document_health).
_HEALTH_TAB_COLORS = {"malformed": "#a13d32", "rng_invalid": "#a06a20"}


class DocumentTabsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _init_documents(self):
        """Registre des documents, une fois le projet lu, avant le chargement
        du texte de l'édition : l'édition, ses parties dans l'ordre
        d'inclusion, puis les documents auxiliaires."""
        self.edition_session = self.document
        parts = self._edition_part_paths() or []
        included = {path_key(path) for path in parts}
        self.documents = [self.edition_session] + [self._new_part(path) for path in parts] + [
            DocumentSession.auxiliary(config) for config in self.project.documents
            if path_key(config.path) not in included
        ]
        self._load_document_tabs()

    def _new_part(self, path):
        """Session d'une partie ; son schéma est celui de l'édition."""
        return DocumentSession.part(path, self.project.schema_mode, self.project.schema)

    def _edition_part_paths(self):
        """Parties de l'édition enregistrée, dans l'ordre d'inclusion ; None
        si elle ne peut pas être lue ou si elle est mal formée."""
        path = self.edition_session.path or self.project.edition
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        assembly = assemble(text, path)
        return None if assembly.root is None else list(assembly.parts)

    def _refresh_parts(self):
        """Après l'enregistrement de l'édition ou d'une partie : les parties
        suivent les xi:include enregistrés. Une partie qui n'est plus incluse
        perd son onglet, sauf si elle a des modifications non enregistrées
        (elle le garde jusqu'à leur enregistrement) ; déclarée dans
        <documents>, elle redevient un document auxiliaire."""
        paths = self._edition_part_paths()
        if paths is None:
            return
        wanted = {path_key(path): path for path in paths}
        declared = {path_key(config.path): config for config in self.project.documents}
        sessions = {path_key(session.path): session for session in self.documents[1:]}
        changed = False
        for key, session in sessions.items():
            if not session.is_part or key in wanted or session.modified:
                continue
            changed = True
            config = declared.get(key)
            if config is not None:
                session.role, session.label = "auxiliary", config.display_label
                session.schema_mode, session.schema_file = config.schema_mode, config.schema
                continue
            if session is self.document:
                self.show_document(self.edition_session)
            self.documents.remove(session)
            self._hidden_documents.discard(session)
            if session.text_document is not None:
                session.text_document.deleteLater()
        for key, path in wanted.items():
            session = sessions.get(key)
            if session is not None and session.is_part:
                continue
            changed = True
            if session is not None:                          # document auxiliaire désormais inclus
                session.role, session.label = "part", Path(path).name
                session.schema_mode, session.schema_file = self.project.schema_mode, self.project.schema
            else:
                self.documents.append(self._new_part(path))
        if not changed:
            return
        position = {key: index for index, key in enumerate(wanted)}
        others = self.documents[1:]
        self.documents = ([self.edition_session]
                          + sorted((s for s in others if s.is_part and path_key(s.path) in position),
                                   key=lambda s: position[path_key(s.path)])
                          + [s for s in others if s.is_part and path_key(s.path) not in position]
                          + [s for s in others if not s.is_part])
        self._update_document_tabs()
        self._save_document_tabs()
        # La synchronisation peut avoir été suspendue ou rétablie.
        if self.document.is_edition:
            self._rebuild_lb_cache()

    def _edition_displayed(self):
        return self.document.is_edition

    def _edition_has_parts(self):
        """L'édition inclut des parties (XInclude) : elle est validée
        assemblée."""
        return any(session.is_part for session in self.documents)

    def _assembled_preview_text(self, edition_text):
        """Texte de l'édition assemblée, parties comprises (texte non enregistré
        des parties modifiées), pour la Vue XSLT / CSS ; None si l'édition
        n'est pas affichée, n'a pas de parties ou est mal formée. L'aperçu est
        alors en lecture seule : ses paragraphes ne sont plus ceux de la
        source."""
        if not self.document.is_edition or not self._edition_has_parts():
            return None
        parts = {str(s.path): s.text_document.toPlainText() for s in self.documents
                 if s.is_part and s.text_document is not None and s.modified}
        assembly = assemble(edition_text, self.edition_session.path or self.project.edition, parts)
        if assembly.root is None:
            return None
        return etree.tostring(assembly.root, encoding="unicode")

    def _witness_sync_suspended(self):
        """Synchronisation des témoins suspendue (V0.9.0.0) : l'édition a des
        parties, et la synchronisation à travers les parties n'est pas encore
        réalisée. Les témoins restent consultables en navigation libre."""
        return self._edition_has_parts()

    def _build_document_area(self, views):
        """Rangée d'onglets des documents au-dessus de ``views`` (source et
        aperçu), un par document visible (voir document_display). Elle reste
        masquée tant que le projet ne compte que l'édition."""
        bar = QTabBar(self)
        bar.setDocumentMode(True)
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        self.document_tab_bar = bar
        self._normal_tab_color = bar.tabTextColor(0)
        for session in self._tab_sessions:
            bar.addTab("")
            self._refresh_document_tab(session)
        # L'onglet de l'édition n'est pas forcément le premier.
        self._select_document_tab()
        bar.setVisible(len(self.documents) > 1)
        bar.currentChanged.connect(self._document_tab_changed)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._document_tab_context_menu)
        area = QWidget(self)
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(bar)
        layout.addWidget(views, 1)
        return area

    def _register_document(self, config):
        """Déclare ``config`` dans project.xml, l'ajoute aux onglets et l'affiche."""
        documents = list(self.project.documents) + [config]
        try:
            update_project_documents(self.project.path, documents)
        except Exception as exc:
            QMessageBox.critical(self, _t("documents.error.title"), str(exc))
            return False
        self.project = replace(self.project, documents=tuple(documents))
        session = DocumentSession.auxiliary(config)
        self.documents.append(session)
        self._update_document_tabs()
        self._save_document_tabs()
        return self.show_document(session)

    def _unregister_document(self, session):
        """Retire ``session`` de project.xml et des onglets ; le fichier reste."""
        documents = [config for config in self.project.documents
                     if Path(config.path).resolve() != Path(session.path).resolve()]
        try:
            update_project_documents(self.project.path, documents)
        except Exception as exc:
            QMessageBox.critical(self, _t("documents.error.title"), str(exc))
            return False
        self.project = replace(self.project, documents=tuple(documents))
        if session is self.document:
            self.show_document(self.edition_session)
        self.documents.remove(session)
        self._update_document_tabs()
        self._save_document_tabs()
        if session.text_document is not None:
            session.text_document.deleteLater()
        return True

    def _update_document_tabs(self):
        """Un onglet par document visible (après un ajout, un retrait, un
        onglet masqué ou rendu, un nouvel ordre)."""
        self._sync_document_tabs()
        bar = self.document_tab_bar
        bar.blockSignals(True)
        try:
            while bar.count() > len(self._tab_sessions):
                bar.removeTab(bar.count() - 1)
            while bar.count() < len(self._tab_sessions):
                bar.addTab("")
        finally:
            bar.blockSignals(False)
        for session in self._tab_sessions:
            self._refresh_document_tab(session)
        bar.setVisible(len(self.documents) > 1)
        self.action_choose_documents.setEnabled(len(self.documents) > 1)
        self._select_document_tab()

    def _document_tab_changed(self, index):
        if 0 <= index < len(self._tab_sessions) and not self.show_document(self._tab_sessions[index]):
            self._select_document_tab()

    def _select_document_tab(self):
        """Onglet courant = document affiché, sans redéclencher l'affichage.
        Un document masqué affiché le temps de l'enregistrer n'a pas d'onglet."""
        bar = getattr(self, "document_tab_bar", None)
        if bar is None or self.document not in self._tab_sessions:
            return
        bar.blockSignals(True)
        try:
            bar.setCurrentIndex(self._tab_sessions.index(self.document))
        finally:
            bar.blockSignals(False)

    def _refresh_document_tab(self, session):
        """Nom, « * » si modifié, couleur et info-bulle selon l'état XML
        (rien pour un document masqué)."""
        bar = getattr(self, "document_tab_bar", None)
        if bar is None or session not in self._tab_sessions:
            return
        index = self._tab_sessions.index(session)
        bar.setTabText(index, self._document_tab_name(session) + (" *" if session.modified else ""))
        color = _HEALTH_TAB_COLORS.get(session.health)
        bar.setTabTextColor(index, QColor(color) if color else self._normal_tab_color)
        tip = str(session.path)
        if session.health == "malformed":
            tip += "\n" + _t("xml.health.malformed.tooltip")
        elif session.health == "rng_invalid":
            tip += "\n" + _t("xml.health.rng_invalid.tooltip")
        bar.setTabToolTip(index, tip)

    def show_document(self, session):
        """Affiche ``session`` dans l'éditeur.

        Un document auxiliaire est lu à son premier affichage. Renvoie False
        si son fichier ne peut pas être lu ; le document affiché ne change
        alors pas.
        """
        if session is self.document:
            return True
        text = None
        if session.text_document is None:
            try:
                text = Path(session.path).read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, _t("file.open.error.title"), str(exc))
                return False
        if self._edition_displayed() and not self._leave_edition_view():
            return False
        if text is not None:
            self._load_session_text(session, text)
        self._attach_document(session)
        return True

    def _leave_edition_view(self):
        """Avant d'afficher un autre document que l'édition : un fragment
        modifié dans l'aperçu est appliqué ou abandonné (ou la demande est
        annulée), puis l'onglet de la source est affiché."""
        view = self.formatted_view
        if not view.frag_box.isHidden() and not view.close_fragment_editor():
            return False
        self.left_tabs.setCurrentIndex(0)
        return True

    def _load_session_text(self, session, text):
        """Crée le QTextDocument d'une session et y place ``text``, avant tout
        affichage : aucun signal n'atteint encore la fenêtre."""
        document = QTextDocument(self)
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        # Coloration attachée AVANT le texte : attachée à un document déjà
        # rempli, sa passe différée incrémenterait la révision, que la fenêtre
        # prendrait pour une modification.
        session.highlighter = XMLHighlighter(document)
        document.setPlainText(text)
        document.setModified(False)
        session.text_document = document
        session.mark_loaded(session.path, document.revision())

    def _attach_document(self, session):
        """Remplace le document affiché par ``session``."""
        previous = self.document
        # Minuteries du document quitté ; l'aperçu lit toujours le texte affiché.
        for timer in (self.sync_timer, self.validate_timer, self.rng_refresh_timer,
                      self.formatted_view.preview_timer):
            timer.stop()
        self._remember_document_view(previous)
        old = previous.text_document
        for signal, slot in ((old.contentsChange, self._source_contents_changed),
                             (old.contentsChanged, self._text_changed),
                             (old.contentsChanged, self._assembly_changed)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        # La session doit être courante AVANT que l'éditeur n'affiche son texte :
        # les signaux émis pendant le changement (curseur, texte) la concernent.
        self.document = session
        self.editor.set_text_document(session.text_document)
        session.text_document.contentsChange.connect(self._source_contents_changed)
        session.text_document.contentsChanged.connect(self._text_changed)
        session.text_document.contentsChanged.connect(self._assembly_changed)
        # Les numéros de révision sont propres à chaque document.
        self._folio_revision = None
        self.xpath_table.setRowCount(0)
        self.xpath_summary.setText("")
        self._set_title()
        self._select_document_tab()
        self._apply_edition_ui()
        self._restore_document_view(session)

    def _remember_document_view(self, session):
        cursor = self.editor.textCursor()
        session.view_state = {
            "cursor": (cursor.anchor(), cursor.position()),
            "scroll": (self.editor.verticalScrollBar().value(),
                       self.editor.horizontalScrollBar().value()),
            "status": (self.xml_status.text(), self.xml_status.styleSheet(),
                       self.rng_status.text(), self.rng_status.styleSheet(),
                       self.schematron_status.text(), self.schematron_status.toolTip(),
                       self.validation_summary.text()),
            # Les textes d'état ci-dessus sont dans la langue de l'interface.
            "language": current_i18n().language,
        }

    def _restore_document_view(self, session):
        """Curseur, défilement, état XML/RELAX NG du document affiché."""
        state = session.view_state or {}
        document = session.text_document
        last = max(0, document.characterCount() - 1)
        anchor, position = state.get("cursor", (0, 0))
        cursor = QTextCursor(document)
        cursor.setPosition(min(anchor, last))
        cursor.setPosition(min(position, last), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        vertical, horizontal = state.get("scroll", (0, 0))

        def restore_scroll(shown=session):
            if self.document is shown:
                self.editor.verticalScrollBar().setValue(vertical)
                self.editor.horizontalScrollBar().setValue(horizontal)

        call_later(0, self, restore_scroll)
        self._set_document_health(session.health)
        status = state.get("status")
        if state.get("language") != current_i18n().language:
            status = None
        revision = document.revision()
        if status is None:
            # Premier affichage (ou langue changée entre-temps) : contrôle XML
            # immédiat, RELAX NG juste après.
            self._reset_validation_state()
            self.schematron_status.setText("")
            self.schematron_status.setToolTip("")
            session.last_xml_health_revision = -1   # afficher le résultat
            self.validate_text(False)
            call_later(120, self, lambda shown=session: self.document is shown and
                       self.validate_relaxng_document(show_panel=False, automatic=True, background=True))
            return
        (xml_text, xml_style, rng_text, rng_style,
         schematron_text, schematron_tip, summary) = status
        self.xml_status.setText(xml_text)
        self.xml_status.setStyleSheet(xml_style)
        self.rng_status.setText(rng_text)
        self.rng_status.setStyleSheet(rng_style)
        self.schematron_status.setText(schematron_text)
        self.schematron_status.setToolTip(schematron_tip)
        self.validation_summary.setText(summary)
        result = session.last_rng_result
        if result is not None and session.last_rng_revision == revision and result.issues:
            self._populate_validation_issues(result.issues, jump_to_xml=result.schema_loaded)
        else:
            self._clear_validation_table()
        # Contrôles interrompus par le changement de document.
        if session.last_xml_health_revision != revision:
            self.validate_timer.start()
        if (self._rng_watch_enabled and self._schema_mode != "none"
                and session.last_rng_revision != revision):
            self.rng_refresh_timer.start()

    # --- Enregistrement de plusieurs documents --------------------------------

    def _unsaved_sessions(self):
        """Documents dont des modifications ne sont pas enregistrées. Pour le
        document affiché, un fragment modifié dans l'aperçu compte aussi."""
        return [session for session in self.documents
                if (self._has_unsaved_work() if session is self.document else session.modified)]

    def _document_display_name(self, session):
        return f"{self._document_tab_name(session)} ({Path(session.path).name})"

    def _save_session(self, session):
        """Enregistre ``session``. Un document non affiché l'est le temps de
        l'enregistrement : les avertissements (XML mal formé…) le montrent.
        En cas d'échec, il reste affiché, avec son onglet s'il était masqué."""
        if session is self.document:
            return bool(self.save())
        previous = self.document
        if not self.show_document(session) or not self.save():
            if self.document is session:
                self.show_document_tab(session)
            return False
        # L'enregistrement a pu retirer une partie qui n'est plus incluse.
        self.show_document(previous if previous in self.documents else self.edition_session)
        return True

    def _confirm_unsaved_documents(self, sessions, *, quitting=False):
        """Plusieurs documents (ou un document auxiliaire) à enregistrer :
        Tout enregistrer / Ignorer / Annuler. Renvoie True si l'on peut
        continuer."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_t("file.unsaved.title"))
        box.setText(_t("documents.unsaved.text") + "\n\n" + "\n".join(
            "• " + self._document_display_name(session) for session in sessions))
        save_btn = box.addButton(_t("documents.save_all"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(_t("file.discard_quit") if quitting else _t("common.discard"),
                                    QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is discard_btn:
            return True
        if clicked is not save_btn:
            return False
        view = self.formatted_view
        if (self._edition_displayed() and view.frag_box.isVisible()
                and view.fragment_has_unapplied_changes() and not view.apply_fragment()):
            return False
        return all(self._save_session(session) for session in sessions)

    # --- Interface réservée à l'édition ---------------------------------------

    def _edition_only_actions(self):
        return [self.action_preview, self.action_save_as, self.action_reload_images,
                self.action_choose_witnesses, self.workspace_layout_menu.menuAction(),
                self.action_diagnose_witnesses, self.action_refresh_synchronizations]

    def _apply_edition_ui(self):
        """Aperçu, témoins (y compris détachés), état de structure et commandes
        associées : masqués quand un document auxiliaire est affiché, puis
        rétablis à l'identique au retour sur l'édition."""
        edition = self._edition_displayed()
        hidden = getattr(self, "_edition_ui_hidden", None)
        preview = self.left_tabs.indexOf(self.formatted_view)
        if edition and hidden is not None:
            self._edition_ui_hidden = None
            for action, enabled in hidden["actions"]:
                action.setEnabled(enabled)
            self.left_tabs.setTabEnabled(preview, True)
            self.structure_status.setVisible(hidden["structure"])
            self.witness_scroll.setVisible(hidden["witnesses"])
            self.main_splitter.setSizes(hidden["sizes"])
            for window in hidden["detached"]:
                window.show()
        elif not edition and hidden is None:
            self._edition_ui_hidden = hidden = {
                "actions": [(action, action.isEnabled()) for action in self._edition_only_actions()],
                "structure": not self.structure_status.isHidden(),
                "witnesses": not self.witness_scroll.isHidden(),
                "sizes": self.main_splitter.sizes(),
                # Masquées, non fermées : fermer une fenêtre la rattacherait.
                "detached": [w for w in self._detached_windows.values() if w.isVisible()],
            }
            for action, _enabled in hidden["actions"]:
                action.setEnabled(False)
            self.left_tabs.setTabEnabled(preview, False)
            self.structure_status.hide()
            self.witness_scroll.hide()
            for window in hidden["detached"]:
                window.hide()
        self.action_save.setText(_t("menu.save_edition" if edition else "menu.save_document"))
        # Retirer un document réécrit <documents> : une partie n'y figure pas.
        self.action_remove_document.setEnabled(self.document.is_auxiliary)

    # --- Garde-fous : commandes réservées à l'édition -------------------------

    def _edition_write(self, method):
        """Commande d'un panneau de témoin qui écrit dans l'édition : refusée,
        avec un message, si un autre document est affiché (elle s'appliquerait
        à un endroit que l'utilisateur ne voit pas)."""
        def guarded(*args):
            if not self._edition_displayed():
                QMessageBox.information(
                    self, _t("documents.edition_required.title"),
                    _t("documents.edition_required.text", name=self.edition_session.path.name))
                return None
            return method(*args)
        return guarded

    def _edition_navigation(self, method):
        """Navigation depuis un témoin : sans effet hors de l'édition."""
        def guarded(*args):
            if self._edition_displayed():
                return method(*args)
            return None
        return guarded
