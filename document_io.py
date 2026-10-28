# -*- coding: utf-8 -*-
"""Ouverture, enregistrement et fermeture du document XML de la fenêtre principale."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFileDialog, QMessageBox
from app_context import call_later, HERE, tr as _t
from save_io import atomic_write_text_with_backup
from xml_assembly import find_includes


class DocumentIOMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def open_path(self,path):
        # Un changement de document invalide immédiatement tous les diagnostics
        # précédents, avant même le parse/validation du nouveau texte.
        if hasattr(self, "validation_table"):
            self._reset_validation_state()
        try: text=Path(path).read_text(encoding="utf-8")
        except Exception as exc: QMessageBox.critical(self,_t("file.open.error.title"),str(exc)); return
        self._loading_editor_document = True
        try:
            self.editor.blockSignals(True)
            self.editor.setPlainText(text)
        finally:
            self.editor.blockSignals(False)
            self._loading_editor_document = False
        self.document.mark_loaded(Path(path), self.editor.document().revision())
        self.editor.document().setModified(False); self._set_title(); self.validate_text(False)
        self.editor.moveCursor(QTextCursor.MoveOperation.Start)
        if hasattr(self, "formatted_view"):
            self.formatted_view.current_paragraph = None
            self.formatted_view.fragment_original = ""
            self.formatted_view.fragment_session = None
            self.formatted_view.preview.active_line_ordinal = None
            self.formatted_view.preview_find_bar.setVisible(False)
            self.formatted_view.preview_find_status.setText("")
            self.formatted_view.apply_btn.setEnabled(False)
            self.formatted_view.reload_btn.setEnabled(False)
            self.formatted_view.frag_box.setVisible(False)
            self.formatted_view.dirty_preview = True
            self.formatted_view._last_preview_key = None
        call_later(50, self, lambda: self._edition_displayed() and self.sync_panels_to_cursor(True))
        # Même en mode RNG « aucun », on résout les xml-model pour détecter
        # à titre informatif une éventuelle déclaration Schematron.
        call_later(120, self, lambda: self.validate_relaxng_document(show_panel=False, show_success_message=False,
                                                                     background=True))

    def _confirm_save_warning(self, title, text):
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(title)
        box.setText(text)
        save_btn = box.addButton(_t("file.save_anyway"), QMessageBox.ButtonRole.AcceptRole)
        cancel_btn = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(cancel_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        return box.clickedButton() is save_btn

    def _write_to(self,path):
        # Un seul instantané du document pour toute la sauvegarde.
        text = self.editor.toPlainText()
        revision = self.editor.document().revision()

        # Le contrôle automatique asynchrone est réutilisé s'il porte exactement
        # sur cette révision ; sinon on effectue le parse synchrone nécessaire.
        well_formed = self.validate_text(False, text=text, revision=revision)
        rng_result = None
        if not well_formed:
            if not self._confirm_save_warning(
                _t("file.save_malformed.title"),
                _t("file.save_malformed.text"),
            ):
                return False
        else:
            # Si F8, l'ouverture ou une sauvegarde précédente a déjà validé
            # exactement cette révision avec le même schéma, réutiliser le
            # résultat. Sinon la validation repart du document courant mais
            # réutilise le RNG compilé en cache.
            rng_result = None
            if self._last_rng_revision == revision and self._last_rng_result is not None:
                resolution = self._resolve_completion_schema(text)
                if resolution.schema_path is not None or resolution.schematron_sources:
                    # Schéma et règles Schematron (V0.9.2.3) inchangés.
                    current_token = self._validation_token(resolution)
                    if current_token is not None and current_token == self._last_rng_schema_token:
                        rng_result = self._last_rng_result
            if rng_result is None:
                rng_result = self.validate_relaxng_document(
                    show_panel=False,
                    show_success_message=False,
                    xml_text=text,
                    document_revision=revision,
                )
            if rng_result is not None and rng_result.schema_loaded and rng_result.well_formed and not rng_result.valid:
                if self._displayed_stylesheet() is not None:      # feuille XSLT (xslt_check_ui)
                    errors = sum(1 for issue in rng_result.issues if issue.level != "WARNING")
                    title, message = _t("file.save_xslt_invalid.title"), _t("file.save_xslt_invalid.text", count=errors)
                elif self._displayed_schematron() is not None:    # règles Schematron (schematron_check_ui)
                    errors = sum(1 for issue in rng_result.issues if issue.level not in ("WARNING", "INFO"))
                    title = _t("file.save_schematron_invalid.title")
                    message = _t("file.save_schematron_invalid.text", count=errors)
                else:                                             # RELAX NG et Schematron
                    errors = sum(1 for issue in rng_result.issues if issue.level not in ("WARNING", "INFO"))
                    title = _t("file.save_rng_invalid.title")
                    message = _t("file.save_rng_invalid.text", count=errors)
                if not self._confirm_save_warning(title, message):
                    return False

        # Le nombre de <lb/> du témoin pivot concerne l'édition et ses parties ;
        # pour une édition en parties, il est compté dans l'édition assemblée.
        count = self._base_line_count() if self.document.in_edition else None
        if count is not None and self.expected_base_lines is not None and count != self.expected_base_lines:
            r=QMessageBox.warning(self,_t("file.structure.title", base=self.witness_siglum(self.base_id)),_t("file.structure.text", count=count, base=self.witness_siglum(self.base_id), expected=self.expected_base_lines),QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
            if r==QMessageBox.StandardButton.Cancel: return False
        try:
            path=Path(path)
            atomic_write_text_with_backup(path, text, encoding="utf-8")
        except Exception as exc:
            QMessageBox.critical(self,_t("file.save.error.title"),str(exc)); return False
        self.document.mark_saved(path)
        self.editor.document().setModified(False); self._set_title(); self.statusBar().showMessage(_t("status.saved", path=path),4000)
        # Si la validation n'a pas encore été faite (p.ex. XML mal formé),
        # l'état visuel calculé ci-dessus reste en place.
        if well_formed and rng_result is None and self._last_schema_resolution is None:
            self.validate_relaxng_document(show_panel=False, show_success_message=False, xml_text=text, document_revision=revision)
        # Les parties suivent les xi:include enregistrés.
        if self.document.in_edition:
            self._refresh_parts()
        return True

    def save_contextual(self):
        """Ctrl+S / Enregistrer : applique d’abord le fragment actif, puis écrit le fichier.

        Le fragment d'une partie de l'édition qui n'est pas affichée
        (V0.9.1.5) : le fichier de cette partie est enregistré, puis le
        document affiché s'il est modifié."""
        if (
            hasattr(self, "formatted_view")
            and self.formatted_view.frag_box.isVisible()
            and (
                self.formatted_view.focus_is_in_fragment()
                or self._last_save_context == "fragment"
            )
        ):
            if not self.formatted_view.apply_fragment():
                return False
            session = self.formatted_view.fragment_session
            if session is not None and session is not self.document and session in self.documents:
                if session.modified and not self._save_session(session):
                    return False
                if not self.modified:
                    return True
        return self.save()

    def save(self):
        if self.current_path is None: return self.save_as()
        return self._write_to(self.current_path)

    def save_as(self):
        start=str(self.current_path if self.current_path else HERE/"xml"/"edition.xml"); fn,_=QFileDialog.getSaveFileName(self,_t("file.save_as.title"),start,"XML (*.xml)")
        if not fn: return False
        if not self._confirm_parts_kept(Path(fn)): return False
        return self._write_to(Path(fn))

    def _confirm_parts_kept(self, target):
        """Avant d'enregistrer une édition qui a des parties dans un autre
        dossier : ses xi:include, relatifs, ne les trouveraient plus."""
        if not self.document.is_edition or self.current_path is None:
            return True
        if Path(target).resolve().parent == Path(self.current_path).resolve().parent:
            return True
        hrefs = [include.href for include in find_includes(self.editor.toPlainText()) if include.href]
        if not hrefs:
            return True
        return self._confirm_save_warning(
            _t("parts.save_as.title"),
            _t("parts.save_as.text", hrefs="\n".join("• " + href for href in hrefs)))

    def maybe_save(self):
        unsaved = self._unsaved_sessions()
        if not unsaved: return True
        # Plusieurs documents, ou un document auxiliaire : liste complète.
        if unsaved != [self.edition_session]:
            return self._confirm_unsaved_documents(unsaved)
        fragment_dirty = (
            hasattr(self, "formatted_view")
            and self.formatted_view.frag_box.isVisible()
            and self.formatted_view.fragment_has_unapplied_changes()
        )
        r=QMessageBox.question(self,_t("file.unsaved.title"),_t("file.unsaved.continue"),QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if r==QMessageBox.StandardButton.Cancel: return False
        if r==QMessageBox.StandardButton.Save:
            if fragment_dirty and not self.formatted_view.apply_fragment():
                return False
            return self._save_session(self.edition_session)
        return True

    def _has_unsaved_work(self):
        """Retourne True si la source ou le fragment contient du travail non sauvegardé."""
        fragment_dirty = (
            hasattr(self, "formatted_view")
            and self.formatted_view.frag_box.isVisible()
            and self.formatted_view.fragment_has_unapplied_changes()
        )
        return bool(self.modified or fragment_dirty)

    def confirm_close_application(self):
        """Garde-fou explicite avant de quitter l'application.

        Retourne True uniquement si la fermeture est autorisée. Les modifications
        du fragment ne sont appliquées que si l'utilisateur choisit d'enregistrer.
        """
        unsaved = self._unsaved_sessions()
        if not unsaved:
            return True
        if unsaved != [self.edition_session]:
            return self._confirm_unsaved_documents(unsaved, quitting=True)

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_t("file.unsaved.title"))
        box.setText(_t("file.unsaved.quit.text"))
        box.setInformativeText(
_t("file.unsaved.quit.info")
        )
        save_btn = box.addButton(_t("file.save_quit"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(_t("file.discard_quit"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_btn or clicked is None:
            return False
        if clicked is discard_btn:
            return True
        if clicked is save_btn:
            # Même comportement que Ctrl+S : si un fragment est ouvert et
            # modifié, il est d'abord réinjecté dans le XML, puis le fichier
            # complet est enregistré (avec la sauvegarde .bak habituelle).
            if (
                hasattr(self, "formatted_view")
                and self.formatted_view.frag_box.isVisible()
                and self.formatted_view.fragment_has_unapplied_changes()
            ):
                if not self.formatted_view.apply_fragment():
                    return False
            return self._save_session(self.edition_session)
        return False
