# -*- coding: utf-8 -*-
"""Documents XML du projet dans la fenêtre principale : l'édition et les
documents auxiliaires déclarés dans <documents> (fichier d'autorités, notes…).

Un seul document est affiché à la fois dans l'éditeur. Chacun possède sa
session (``DocumentSession``) : texte et historique d'annulation, état
« modifié », coloration, validation, position du curseur. Les témoins, la
synchronisation et l'aperçu ne concernent que l'édition.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QTextCursor, QTextDocument
from PySide6.QtWidgets import QMessageBox, QPlainTextDocumentLayout
from app_context import call_later, tr as _t
from code_editor import XMLHighlighter
from document_session import DocumentSession


class DocumentTabsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _init_documents(self):
        """Registre des documents, une fois l'édition chargée."""
        self.edition_session = self.document
        self.documents = [self.edition_session] + [
            DocumentSession.auxiliary(config) for config in self.project.documents
        ]

    def _edition_displayed(self):
        return self.document.is_edition

    def show_document(self, session):
        """Affiche ``session`` dans l'éditeur.

        Un document auxiliaire est lu à son premier affichage. Renvoie False
        si son fichier ne peut pas être lu ; le document affiché ne change
        alors pas.
        """
        if session is self.document:
            return True
        if session.text_document is None:
            try:
                text = Path(session.path).read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, _t("file.open.error.title"), str(exc))
                return False
            self._load_session_text(session, text)
        self._attach_document(session)
        return True

    def _load_session_text(self, session, text):
        """Crée le QTextDocument d'une session et y place ``text``, avant tout
        affichage : aucun signal n'atteint encore la fenêtre."""
        document = QTextDocument(self)
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        document.setPlainText(text)
        document.setModified(False)
        session.text_document = document
        session.highlighter = XMLHighlighter(document)
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
                             (old.contentsChanged, self._text_changed)):
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
        # Les numéros de révision sont propres à chaque document.
        self._folio_revision = None
        self.xpath_table.setRowCount(0)
        self.xpath_summary.setText("")
        self._set_title()
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
        revision = document.revision()
        if status is None:
            # Premier affichage : contrôle XML immédiat, RELAX NG juste après.
            self._reset_validation_state()
            self.schematron_status.setText("")
            self.schematron_status.setToolTip("")
            self.validate_text(False)
            call_later(120, self, lambda shown=session: self.document is shown and
                       self.validate_relaxng_document(show_panel=False, automatic=True))
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
