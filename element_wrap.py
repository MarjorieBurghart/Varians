# -*- coding: utf-8 -*-
"""Ctrl+E dans le fragment de la vue XSLT / CSS (V0.9.4.7, extrait de
formatted_view) : entourer la sélection d'un élément, ou l'insérer au point
d'insertion, avec les attributs configurés dans custom-elements.xml."""
from __future__ import annotations

import html as html_lib
import re

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QDialog, QInputDialog, QLineEdit, QMessageBox

from app_context import tr as _t
from completion_ui import CompletionDialog
from custom_completion import load_custom_completion


class ElementWrapMixin:
    """Ctrl+E de ``FormattedEditionWidget`` (dont elle hérite)."""

    @staticmethod
    def _is_simple_xml_qname(name):
        """Valide le sous-ensemble de QName accepté par Ctrl+E/configuration."""
        name_part = r"[A-Za-z_][A-Za-z0-9_.-]*"
        return bool(name and re.fullmatch(rf"{name_part}(?::{name_part})?", name))

    def _custom_attributes_for_element(self, element):
        """Relit custom-elements.xml et renvoie les attributs configurés.

        Le fichier est volontairement relu à chaque Ctrl+E afin qu'une
        modification prenne effet sans redémarrage. La configuration décrit
        une aide de saisie : elle n'altère jamais la validation RELAX NG.
        """
        custom_file = self.main.project.custom_elements
        if not custom_file.exists():
            return []
        try:
            config = load_custom_completion(custom_file)
        except Exception as exc:
            if str(exc) == "ROOT_NOT_CUSTOM_ELEMENTS":
                raise ValueError(_t("ctrl_e.config.root_error", file=custom_file.name)) from exc
            raise ValueError(
                _t("ctrl_e.config.read_error", file=custom_file.name, error=exc)
            ) from exc

        attrs = []
        for attr in config.attributes_for(element):
            if not self._is_simple_xml_qname(attr.name):
                raise ValueError(
                    _t("ctrl_e.config.attr_error", file=custom_file.name, name=repr(attr.name))
                )
            attrs.append((attr.name, attr.default_value, attr.has_default))
        return attrs

    def wrap_selection_with_element(self, target_editor=None, editor_label="fragment TEI"):
        """Ctrl+E : entourer la sélection ou insérer un élément au point d'insertion.

        Avec sélection, seul le CONTENU d'origine demeure sélectionné, sans
        les balises ajoutées : Ctrl+E répété insère donc le deuxième élément
        à l'intérieur du premier (comportement de type Oxygen).
        Sans sélection, on crée une paire de balises avec le curseur à
        l'intérieur. Le suffixe « / » (ex. « lb/ ») crée une balise vide.
        Si un attribut de custom-elements.xml n'a pas de defaultValue,
        le point d'insertion sans sélection reste dans le premier attribut vide.
        La commande est commune à la source XML et à l'éditeur de fragment.
        """
        target_editor = target_editor or self.fragment_editor
        cursor = target_editor.textCursor()
        has_selection = cursor.hasSelection()

        # V0.6.0 : Ctrl+E fusionne le contexte RNG et les aides du projet ;
        # d'abord les éléments réellement admissibles à cette position. Le champ
        # reste éditable : la personnalisation de saisie et les documents en cours
        # de correction ne sont donc pas bloqués par le sélecteur.
        suggestion_pos = target_editor.positions().python(cursor.selectionStart() if has_selection
                                                          else cursor.position())
        suggestion_provider = getattr(self.main, "rng_element_suggestions", None)
        suggestions = (
            suggestion_provider(target_editor, suggestion_pos)
            if callable(suggestion_provider) else ()
        )
        if suggestions:
            dlg = CompletionDialog(
                _t("ctrl_e.dialog.title"),
                _t("ctrl_e.suggestions.label"),
                suggestions,
                "",
                self,
                allow_custom=True,
            )
            try:
                point = target_editor.viewport().mapToGlobal(target_editor.cursorRect().bottomLeft())
                dlg.move(point)
            except Exception:
                pass
            if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_value:
                return
            element = dlg.selected_value.strip()
        else:
            element, ok = QInputDialog.getText(
                self,
                _t("ctrl_e.dialog.title"),
                _t("ctrl_e.dialog.label"),
                QLineEdit.EchoMode.Normal,
                "",
            )
            if not ok:
                return
            element = element.strip()
        self_closing = element.endswith("/")
        if self_closing:
            element = element[:-1].strip()

        if not self._is_simple_xml_qname(element):
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_element.title"),
                _t("ctrl_e.invalid_element.text"),
            )
            return
        if self_closing and has_selection:
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_element.title"),
                _t("ctrl_e.self_closing_requires_empty"),
            )
            return

        try:
            custom_attrs = self._custom_attributes_for_element(element)
        except ValueError as exc:
            QMessageBox.warning(
                self,
                _t("ctrl_e.invalid_config.title"),
                str(exc) + _t("ctrl_e.invalid_config.suffix"),
            )
            return

        # Le QTextCursor capture la sélection avant l'ouverture du dialogue.
        # Qt y sépare les lignes par U+2029 : les restituer en LF conserve
        # exactement le XML multiligne sélectionné. Un U+2028 du texte reste
        # tel quel (red team, A1).
        selected = cursor.selectedText().replace("\u2029", "\n")
        selection_start = cursor.selectionStart()
        # Préserver aussi le sens de la sélection : Qt place position() à
        # gauche pour une sélection faite de droite à gauche.
        selection_reversed = has_selection and cursor.position() == selection_start

        opening_tag = f"<{element}"
        empty_attr_cursor_offset = None
        for name, value, has_default in custom_attrs:
            opening_tag += f' {name}="'
            if not has_default and empty_attr_cursor_offset is None:
                empty_attr_cursor_offset = len(opening_tag)
            opening_tag += html_lib.escape(str(value), quote=True) + '"'
        opening_tag += "/>" if self_closing else ">"

        replacement = (opening_tag if self_closing
                       else opening_tag + selected + f"</{element}>")
        cursor.beginEditBlock()
        cursor.insertText(replacement)
        cursor.endEditBlock()

        new_cursor = QTextCursor(target_editor.document())
        # QTextCursor utilise des offsets UTF-16 et non la longueur Python :
        # des caractères non-BMP (emoji, etc.) doivent compter pour 2 unités.
        utf16_length = lambda text: len(text.encode("utf-16-le")) // 2
        if has_selection:
            # Garder précisément le texte initial sélectionné, PAS les balises.
            # Exemple : <app>[uerbum]</app> puis Ctrl+E « rdg » produit
            # <app><rdg>[uerbum]</rdg></app>, dans le bon ordre d'imbrication.
            content_start = selection_start + utf16_length(opening_tag)
            content_end = content_start + utf16_length(selected)
            if selection_reversed:
                new_cursor.setPosition(content_end)
                new_cursor.setPosition(content_start, QTextCursor.MoveMode.KeepAnchor)
            else:
                new_cursor.setPosition(content_start)
                new_cursor.setPosition(content_end, QTextCursor.MoveMode.KeepAnchor)
        elif empty_attr_cursor_offset is not None:
            # Aucun texte sélectionné : compléter d'abord le 1er attribut vide.
            new_cursor.setPosition(selection_start + utf16_length(opening_tag[:empty_attr_cursor_offset]))
        elif self_closing:
            # <lb/> : point d'insertion immédiatement après la balise vide.
            new_cursor.setPosition(selection_start + utf16_length(replacement))
        else:
            # <note>|</note> : prêt à saisir le contenu de l'élément.
            new_cursor.setPosition(selection_start + utf16_length(opening_tag))
        target_editor.setTextCursor(new_cursor)
        target_editor.setFocus()

        if custom_attrs:
            attrs_msg = ", ".join(name for name, _, _ in custom_attrs)
            msg = _t("ctrl_e.inserted_attrs", element=element, attrs=attrs_msg, file=self.main.project.custom_elements.name)
        elif self_closing:
            msg = _t("ctrl_e.inserted_self_closing", element=element)
        elif not has_selection:
            msg = _t("ctrl_e.inserted_empty", element=element)
        else:
            msg = _t("ctrl_e.inserted", element=element)
        self.main.statusBar().showMessage(msg, 2600)
