# -*- coding: utf-8 -*-
"""Éditeur de fragment de la vue XSLT / CSS (V0.9.4.7, extrait de
formatted_view) : un élément modifiable de l'aperçu (crayon ✎, F2) ouvert
seul, rechargé, réinjecté dans sa source ; sélection reportée entre
l'aperçu et le fragment ; protection d'un fragment modifié."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QApplication, QMessageBox

from app_context import _settings, tr as _t
from selection_quote import quote as quote_selection, resolve as resolve_quote, xml_compact
from fragment_units import unit_spans


class FragmentEditorMixin:
    """Éditeur de fragment de ``FormattedEditionWidget`` (dont elle hérite)."""

    def _set_fragment_visual_wrap(self, enabled):
        """Retour à la ligne visuel du fragment, sans modifier le XML."""
        self.fragment_editor.set_visual_wrap(bool(enabled))
        _settings().setValue("fragmentVisualWrap", bool(enabled))

    def focus_is_in_fragment(self):
        """True si le focus clavier est dans l'éditeur de fragment ou dans ses lignes de recherche
        et de remplacement : Ctrl+F, Ctrl+H et F3 visent alors le fragment, et Ctrl+S l'applique
        avant d'enregistrer."""
        focus = QApplication.focusWidget()
        return bool(
            focus is self.fragment_editor
            or (focus is not None and self.fragment_editor.isAncestorOf(focus))
            or focus is self.fragment_find_box
            or (focus is not None and self.fragment_find_bar.isAncestorOf(focus))
            or (focus is not None and self.fragment_replace_row.isAncestorOf(focus))
        )

    def edit_selected_paragraph(self):
        """F2 : ouvre le paragraphe de la sélection, ou du curseur, de
        l'aperçu ; la sélection est reportée dans le fragment."""
        cursor = self.preview.textCursor()
        idx = self.preview.paragraph_for_position(cursor.selectionStart())
        if idx is None:
            return False
        selection = (cursor.selectionStart(), cursor.selectionEnd()) if cursor.hasSelection() else None
        return self._edit_paragraph(idx, selection, focus=True)

    def _edit_paragraph(self, idx, selection=None, focus=False):
        """Ouvre le paragraphe ``idx`` dans l'éditeur de fragment, puis y
        sélectionne ``selection`` (début, fin dans l'aperçu) si elle est dans
        ce paragraphe ; le fragment prend alors le focus, comme avec
        ``focus``. Le paragraphe déjà ouvert et modifié n'est pas rechargé :
        ses corrections non appliquées restent."""
        already_open = (idx == self.current_paragraph and not self.frag_box.isHidden()
                        and self.fragment_has_unapplied_changes())
        if not already_open and not self.load_fragment(idx):
            return False
        if selection is not None:
            cursor = QTextCursor(self.preview.document())
            cursor.setPosition(selection[0])
            cursor.setPosition(selection[1], QTextCursor.MoveMode.KeepAnchor)
            self.preview.setTextCursor(cursor)
            if self._preview_selection_to_fragment():
                return True
        if focus:
            self.fragment_editor.setFocus()
        return True

    def _confirm_fragment_switch(self, new_idx):
        """Protège un fragment modifié avant d'en ouvrir un autre.

        Retourne True si le changement de paragraphe peut continuer.
        """
        if (
            self.current_paragraph is None
            or new_idx == self.current_paragraph
            or not self.fragment_has_unapplied_changes()
        ):
            return True

        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Question)
        box.setWindowTitle(_t("fragment.unapplied.title"))
        box.setText(
            _t("fragment.unapplied.text")
        )
        box.setInformativeText(
            _t("fragment.unapplied.question")
        )
        apply_button = box.addButton(_t("fragment.apply_continue"), QMessageBox.ButtonRole.AcceptRole)
        discard_button = box.addButton(_t("fragment.ignore_continue"), QMessageBox.ButtonRole.DestructiveRole)
        cancel_button = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(apply_button)
        box.setEscapeButton(cancel_button)
        box.exec()

        clicked = box.clickedButton()
        if clicked is cancel_button or clicked is None:
            return False
        if clicked is apply_button:
            # apply_fragment() valide le XML, réinjecte le fragment et
            # recalcule les plages. Si l'application échoue, on reste sur
            # le fragment courant et le changement de paragraphe est annulé.
            return bool(self.apply_fragment())
        if clicked is discard_button:
            return True
        return False

    def _unit_names(self):
        return self.unit_names or self.view_unit_names()

    def _fragment_source(self, idx):
        """L'élément modifiable de rang ``idx`` de l'aperçu (V0.9.2.9 ;
        auparavant le ``<p>``) dans son fichier : ``(session, texte, début,
        fin, nombre d'éléments)``, ou None.

        Pour une édition en parties (V0.9.1.5), le fichier est celui qui
        contient l'élément, édition ou partie, lu au besoin sans être
        affiché ; sinon, c'est le document affiché."""
        main = self.main
        if not main._preview_shows_assembly():
            text = main.editor.toPlainText()
            spans = unit_spans(text, self._unit_names())
            if not 0 <= idx < len(spans):
                return None
            return (main.document, text, *spans[idx], len(spans))
        sources = main._assembled_preview_sources()
        if sources is None or not 0 <= idx < len(sources.paragraphs) or sources.paragraphs[idx] is None:
            return None
        span = sources.paragraphs[idx]
        session = main._edition_file_session(span.path, load=True)
        if session is None:
            return None
        return (session, session.text_document.toPlainText(), span.start, span.end, len(sources.paragraphs))

    def _update_fragment_label(self):
        if self.current_paragraph is None:
            self.frag_label.setText(_t("fragment.initial"))
            return
        # Nom de l'élément ouvert (V0.9.2.9), sans préfixe : « <lg> ».
        name = re.match(r"\s*<(?:[^\s/>:!?]+:)?([^\s/>:!?]+)", self.fragment_original or "")
        element = f"<{name.group(1)}>" if name else ""
        if self.main._preview_shows_assembly() and self.fragment_session is not None:
            self.frag_label.setText(_t("fragment.label.file", element=element, index=self.current_paragraph + 1,
                                       total=self._fragment_total, file=Path(self.fragment_session.path).name))
        else:
            self.frag_label.setText(_t("fragment.label", element=element, index=self.current_paragraph + 1,
                                       total=self._fragment_total))

    def load_fragment(self, idx):
        """Ouvre dans l'éditeur de fragment l'élément modifiable de rang ``idx`` de l'aperçu, pris
        dans son fichier (le document affiché ou, pour une édition en parties, le fichier qui le
        contient). Si un autre élément ouvert a des modifications non appliquées, l'utilisateur
        choisit d'abord « Appliquer et continuer », « Ignorer et continuer » ou « Annuler ».
        False si l'élément n'existe pas ou si l'utilisateur annule."""
        # Ne jamais remplacer silencieusement un fragment modifié par un
        # autre paragraphe. Le choix est explicite : appliquer, ignorer ou
        # annuler.
        if not self._confirm_fragment_switch(idx):
            return False

        # Recalculer les plages après une éventuelle application du fragment
        # courant : sa longueur a pu changer.
        source = self._fragment_source(idx)
        if source is None:
            return False
        session, text, start, end, total = source
        frag = text[start:end]
        self.current_paragraph = idx
        self.fragment_original = frag
        self.fragment_session = session
        self._fragment_total = total
        self.frag_box.setVisible(True)
        self.fragment_editor.blockSignals(True)
        self.fragment_editor.setPlainText(frag)
        self.fragment_editor.blockSignals(False)
        if hasattr(self, "fragment_find_status"):
            self.fragment_find_status.setText("")
        self._update_fragment_label()
        self.apply_btn.setEnabled(True)
        self.reload_btn.setEnabled(True)
        return True

    def reload_fragment(self):
        """« Recharger le fragment » : relit l'élément ouvert dans son fichier. Les modifications
        non appliquées du fragment sont perdues, sans question."""
        if self.current_paragraph is not None:
            self.load_fragment(self.current_paragraph)

    def fragment_has_unapplied_changes(self):
        """True si un élément a été ouvert et que le texte du fragment diffère de celui de son
        ouverture ou de sa dernière application. L'affichage de l'éditeur n'est pas vérifié :
        après « Fermer » sans appliquer, elle reste vraie (plusieurs appelants regardent aussi
        ``frag_box``)."""
        return (
            self.current_paragraph is not None
            and self.fragment_editor.toPlainText() != self.fragment_original
        )

    def _preview_selection_to_fragment(self):
        """Une sélection faite dans l'aperçu est aussi sélectionnée dans
        l'éditeur de fragment, qui prend le focus, si elle commence dans le
        paragraphe ouvert. Elle y est retrouvée par son texte et son contexte
        (V0.9.4.5), dans le texte actuel du fragment, même modifié."""
        if self.current_paragraph is None or self.frag_box.isHidden():
            return False
        context = self.preview.selection_context()
        if context is None or context.get("paragraph") != self.current_paragraph:
            return False
        fragment = self.fragment_editor.toPlainText()
        compact = xml_compact(fragment)
        found = resolve_quote(compact, context["quote"], hint=context.get("relative"))
        if found is None:
            return False
        start, end = compact.span(*found)
        qt = self.fragment_editor.positions(fragment)
        selection = QTextCursor(self.fragment_editor.document())
        selection.setPosition(qt.qt(start))
        selection.setPosition(qt.qt(end), QTextCursor.MoveMode.KeepAnchor)
        self.fragment_editor.setTextCursor(selection)
        # La sélection vient de l'aperçu : elle n'y est pas renvoyée.
        self._fragment_selection_timer.stop()
        self.fragment_editor.centerCursor()
        self.fragment_editor.setFocus()
        return True

    def _fragment_selection_to_preview(self):
        """Une sélection faite dans l'éditeur de fragment est aussi
        sélectionnée dans l'aperçu, qui défile jusqu'à elle ; le focus reste
        dans le fragment. Elle y est cherchée dans le seul élément ouvert,
        par son texte et son contexte (V0.9.4.5). Une sélection faite
        seulement de balises, ou un texte absent de l'aperçu (tapé, pas
        encore appliqué), n'y change rien."""
        if self.current_paragraph is None or self.frag_box.isHidden():
            return False
        cursor = self.fragment_editor.textCursor()
        if not cursor.hasSelection():
            return False
        fragment = self.fragment_editor.toPlainText()
        compact = xml_compact(fragment)
        qt = self.fragment_editor.positions(fragment)
        i, j = compact.range_of(qt.python(cursor.selectionStart()), qt.python(cursor.selectionEnd()))
        wanted = quote_selection(compact, i, j)
        if wanted is None:
            return False
        return self.preview.select_quote({"quote": wanted, "paragraph": self.current_paragraph, "relative": i},
                                         focus=False, anywhere=False)

    def close_fragment_editor(self):
        """Ferme l’éditeur de fragment sans perdre silencieusement une correction."""
        if self.fragment_has_unapplied_changes():
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Question)
            box.setWindowTitle(_t("fragment.close.title"))
            box.setText(_t("fragment.close.text"))
            apply_button = box.addButton(_t("common.apply"), QMessageBox.ButtonRole.AcceptRole)
            discard_button = box.addButton(_t("common.discard"), QMessageBox.ButtonRole.DestructiveRole)
            cancel_button = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
            box.setDefaultButton(apply_button)
            box.exec()
            clicked = box.clickedButton()
            if clicked is cancel_button or clicked is None:
                return False
            if clicked is apply_button:
                if not self.apply_fragment():
                    return False
            elif clicked is discard_button:
                # Rien à réinjecter : le XML source reste la référence.
                pass

        self.fragment_find_bar.setVisible(False)
        self.fragment_find_status.setText("")
        self.frag_box.setVisible(False)
        self.preview.setFocus()
        return True

    def apply_fragment(self):
        """Réinjecte le fragment dans le XML source : le fichier qui contient
        le paragraphe, affiché ou non. Retourne True en cas de succès."""
        if self.current_paragraph is None:
            return False
        idx = self.current_paragraph
        source = self._fragment_source(idx)
        # Le paragraphe de ce rang est désormais dans un autre fichier.
        if source is None or source[0] is not self.fragment_session:
            QMessageBox.warning(self, _t("fragment.moved.title"), _t("fragment.moved.text"))
            return False
        session, text, start, end, _total = source
        if text[start:end] != self.fragment_original:
            r = QMessageBox.question(
                self, _t("fragment.source_changed.title"),
                _t("fragment.source_changed.text"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                self.load_fragment(idx)
                return False
        frag = self.fragment_editor.toPlainText()

        # Si rien n’a changé, Ctrl+S doit tout de même pouvoir enregistrer le
        # document sans provoquer une retransformation XSLT inutile.
        if frag == self.fragment_original and text[start:end] == self.fragment_original:
            return True

        candidate = text[:start] + frag + text[end:]
        try:
            ET.fromstring(candidate)
        except ET.ParseError as exc:
            QMessageBox.warning(self, _t("fragment.invalid.title"), _t("fragment.invalid.text", error=exc))
            return False
        if session is self.main.document:
            qt = self.main.editor.positions(text)
            c = QTextCursor(self.main.editor.document())
            c.setPosition(qt.qt(start))
            c.setPosition(qt.qt(end), QTextCursor.MoveMode.KeepAnchor)
            c.insertText(frag)
            self.main.editor.setTextCursor(c)
            self.main.sync_panels_to_cursor(True)
        else:
            # Une partie, ou l'édition, non affichée : une seule étape
            # d'annulation, dans son propre document.
            self.main._write_session_text(session, text, candidate)
        self.fragment_original = frag
        self.dirty_preview = True
        self.refresh_preview()
        # Les plages ont pu changer ; recharge le même numéro ordinal si possible.
        total = (len(self.sources.paragraphs) if self.sources is not None
                 else len(unit_spans(self.main.editor.toPlainText(), self._unit_names())))
        self.load_fragment(min(idx, max(0, total - 1)))
        return True

    def dirty_fragment_session(self):
        """Le document dont vient le fragment ouvert, s'il est modifié et pas
        encore appliqué ; sinon None."""
        if self.frag_box.isVisible() and self.fragment_has_unapplied_changes():
            return self.fragment_session
        return None
