# -*- coding: utf-8 -*-
"""Éditeur de la source XML : coloration syntaxique, numéros de ligne, repliage, paires de balises, complétion des fermetures et des attributs, recherche."""
from __future__ import annotations

import re

from PySide6.QtCore import QRect, QSize, QStringListModel, Qt
from PySide6.QtGui import (
    QColor, QFont, QPainter, QStandardItem, QStandardItemModel, QSyntaxHighlighter,
    QTextCharFormat, QTextCursor, QTextFormat,
)
from PySide6.QtWidgets import (
    QCompleter, QPlainTextDocumentLayout, QPlainTextEdit, QTextEdit, QWidget,
)
from rng_completion import format_pointer_list_insertion
from xml_folding import foldable_xml_regions, region_at_header, region_for_cursor
from xml_tag_pairs import (
    closing_rename_mirror_for_change, closing_tag_suggestion, exact_selected_opening_pair,
    opening_pair_for_name_change, opening_tag_at, pair_at_context,
)


class XMLHighlighter(QSyntaxHighlighter):
    def __init__(self, document):
        super().__init__(document)
        self.tag_fmt = QTextCharFormat(); self.tag_fmt.setForeground(QColor("#315a8a"))
        self.attr_fmt = QTextCharFormat(); self.attr_fmt.setForeground(QColor("#73559a"))
        self.value_fmt = QTextCharFormat(); self.value_fmt.setForeground(QColor("#9a5537"))
        self.comment_fmt = QTextCharFormat(); self.comment_fmt.setForeground(QColor("#6b7d63"))
        self.entity_fmt = QTextCharFormat(); self.entity_fmt.setForeground(QColor("#327f79"))

    def highlightBlock(self, text):
        for m in re.finditer(r"<!--.*?-->", text):
            self.setFormat(m.start(), m.end()-m.start(), self.comment_fmt)
        for m in re.finditer(r"</?[A-Za-z_][\w:.-]*(?:\s+[^<>]*?)?/?>", text):
            self.setFormat(m.start(), m.end()-m.start(), self.tag_fmt)
            chunk = m.group(0)
            for a in re.finditer(r"\b[A-Za-z_][\w:.-]*(?=\s*=)", chunk):
                self.setFormat(m.start()+a.start(), a.end()-a.start(), self.attr_fmt)
            for q in re.finditer(r"(['\"]).*?\1", chunk):
                self.setFormat(m.start()+q.start(), q.end()-q.start(), self.value_fmt)
        for m in re.finditer(r"&(?:#\d+|#x[0-9A-Fa-f]+|[A-Za-z][\w.-]*);", text):
            self.setFormat(m.start(), m.end()-m.start(), self.entity_fmt)


class LineNumberArea(QWidget):
    def __init__(self, editor):
        super().__init__(editor); self.editor = editor
    def sizeHint(self):
        return QSize(self.editor.lineNumberAreaWidth(), 0)
    def paintEvent(self, event):
        self.editor.lineNumberAreaPaintEvent(event)
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton and self.editor.toggle_fold_at_gutter(event.position().toPoint()):
            event.accept()
            return
        super().mousePressEvent(event)


class CodeEditor(QPlainTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.lineNumberArea = LineNumberArea(self)
        self._fold_regions_cache = None
        self._folded_opening_lines = set()
        self._fold_relayouting = False
        self.document().contentsChange.connect(self._folding_document_changed)
        self.cursorPositionChanged.connect(self._unfold_for_hidden_cursor)
        self.blockCountChanged.connect(self.updateLineNumberAreaWidth)
        self.updateRequest.connect(self.updateLineNumberArea)
        # Un résultat de recherche doit rester visible même sans focus dans
        # l'éditeur, mais ne doit JAMAIS être une sélection de texte éditable.
        self._search_match = None
        self._search_last = None
        self._pair_edit_guard = False
        self._pair_previous_text = self.toPlainText()
        self._pending_pair_rename = None
        self.cursorPositionChanged.connect(self.highlightCurrentLine)
        self.document().contentsChange.connect(self._pair_document_contents_changed)
        self.textChanged.connect(self.clearSearchMatch)
        self.textChanged.connect(self.highlightCurrentLine)
        self.updateLineNumberAreaWidth(0); self.highlightCurrentLine()
        self.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        # Par défaut, conserver le comportement historique. L'utilisateur peut
        # activer un retour à la ligne purement VISUEL dans la vue XML source.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        font = QFont("Consolas"); font.setStyleHint(QFont.StyleHint.Monospace); font.setPointSize(10)
        self.setFont(font)
        self.setTabStopDistance(self.fontMetrics().horizontalAdvance(" ") * 4)

        # V0.8.5.13 : complétion immédiate des fermetures structurelles.
        # Un seul QName lexicalement attendu, sans dépendance au RELAX NG.
        self._closing_completer = QCompleter(self)
        self._closing_completer.setWidget(self)
        self._closing_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._closing_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseSensitive)
        self._closing_completer.setModel(QStringListModel([], self._closing_completer))
        self._closing_completer.activated[str].connect(self._accept_closing_completion)
        self.cursorPositionChanged.connect(self._check_closing_completion_cursor)
        # A02: noms d'attributs RNG à la frappe, indépendamment de Ctrl+Espace.
        self.attribute_completion_provider = None
        self._attribute_completer = QCompleter(self)
        self._attribute_completer.setWidget(self)
        self._attribute_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._attribute_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._attribute_completer.activated[str].connect(self._accept_attribute_completion)
        self.cursorPositionChanged.connect(self._check_attribute_completion_cursor)
        # Pointeurs (#id) à la frappe de « # » dans la valeur d'un attribut :
        # le fournisseur renvoie des couples (valeur, description) et le
        # contexte réduit au jeton courant. La valeur est portée par UserRole,
        # le texte affiché ajoute la description.
        self.value_completion_provider = None
        self._value_completer = QCompleter(self)
        self._value_completer.setWidget(self)
        self._value_completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
        self._value_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._value_completer.setCompletionRole(Qt.ItemDataRole.UserRole)
        # « #mo » doit aussi trouver « personnes.xml#molesme » (identifiant ambigu).
        self._value_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._value_completer.activated[str].connect(self._accept_value_completion)
        self.cursorPositionChanged.connect(self._check_value_completion_cursor)
        # Rappels facultatifs de la fenêtre : Ctrl+clic (``position`` -> True
        # si le clic est traité) et menu du clic droit (``menu, position``).
        self.reference_click_provider = None
        self.context_menu_provider = None

    def mousePressEvent(self, event):
        if (event.button() == Qt.MouseButton.LeftButton
                and event.modifiers() & Qt.KeyboardModifier.ControlModifier
                and callable(self.reference_click_provider)):
            position = self.cursorForPosition(event.position().toPoint()).position()
            if self.reference_click_provider(position):
                event.accept()
                return
        super().mousePressEvent(event)

    def contextMenuEvent(self, event):
        if not callable(self.context_menu_provider):
            super().contextMenuEvent(event)
            return
        # Comme QPlainTextEdit lui-même : menu non bloquant, détruit à sa fermeture.
        menu = self.createStandardContextMenu(event.pos())
        menu.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.context_menu_provider(menu, self.cursorForPosition(event.pos()).position())
        menu.popup(event.globalPos())

    def _value_proposals(self):
        if self.textCursor().hasSelection() or not callable(self.value_completion_provider):
            return (), None
        try:
            items, context = self.value_completion_provider(self)
            if (context is None or context.kind != "attribute_value"
                    or not (context.prefix or "").startswith("#")):
                return (), None
            return tuple(items), context
        except Exception:
            return (), None

    def _check_value_completion_cursor(self):
        popup = self._value_completer.popup()
        if popup.isVisible():
            items, context = self._value_proposals()
            if context is None or not items:
                popup.hide()

    def show_value_completion(self):
        items, context = self._value_proposals()
        popup = self._value_completer.popup()
        if not items:
            popup.hide()
            return False
        self._closing_completer.popup().hide()
        self._attribute_completer.popup().hide()
        model = QStandardItemModel(self._value_completer)
        texts = []
        for value, description in items:
            text = f"{value} — {description}" if description else str(value)
            item = QStandardItem(text)
            item.setData(str(value), Qt.ItemDataRole.UserRole)
            item.setEditable(False)
            model.appendRow(item)
            texts.append(text)
        self._value_completer.setModel(model)
        self._value_completer.setCompletionPrefix(context.prefix)
        self._value_completer.setCurrentRow(0)
        rect = self.cursorRect()
        rect.setWidth(min(640, max(160, max(self.fontMetrics().horizontalAdvance(x) for x in texts) + 40)))
        self._value_completer.complete(rect)
        return True

    def _accept_value_completion(self, value):
        items, context = self._value_proposals()  # Recontrôle après édition/curseur.
        if context is None or str(value) not in {str(v) for v, _description in items}:
            self._value_completer.popup().hide()
            return
        start, end = int(context.replace_start), int(context.replace_end)
        replacement, final_pos = format_pointer_list_insertion(self.toPlainText(), start, end, str(value))
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        cursor.endEditBlock()
        cursor.setPosition(final_pos)
        self.setTextCursor(cursor)
        self._value_completer.popup().hide()
        self.ensureCursorVisible()

    def _check_attribute_completion_cursor(self):
        popup = self._attribute_completer.popup()
        if popup.isVisible():
            items, ctx = self._attribute_proposals()
            if ctx is None or not items:
                popup.hide()

    def _attribute_proposals(self):
        if self.textCursor().hasSelection() or not callable(self.attribute_completion_provider):
            return (), None
        try:
            items, context = self.attribute_completion_provider(self)
            if context is None or context.kind != "attribute" or not context.prefix:
                return (), None
            return tuple(items), context
        except Exception:
            # Aucune complétion trompeuse si le RNG ou l'analyse est indisponible.
            return (), None

    def show_attribute_completion(self):
        items, context = self._attribute_proposals()
        popup = self._attribute_completer.popup()
        if not items:
            popup.hide()
            return False
        self._closing_completer.popup().hide()
        self._attribute_completer.setModel(QStringListModel(list(items), self._attribute_completer))
        self._attribute_completer.setCompletionPrefix(context.prefix)
        self._attribute_completer.setCurrentRow(0)
        rect = self.cursorRect()
        rect.setWidth(max(140, max(self.fontMetrics().horizontalAdvance(x) for x in items) + 40))
        self._attribute_completer.complete(rect)
        return True

    def _accept_attribute_completion(self, displayed):
        items, context = self._attribute_proposals()  # Recontrôle après édition/cursor.
        if context is None or str(displayed) not in items:
            self._attribute_completer.popup().hide()
            return
        text = self.toPlainText()
        start, end = context.replace_start, context.replace_end
        before = text[start-1:start] if start else ""
        after = text[end:]
        lead = "" if not before or before.isspace() else " "
        # Respecter un = déjà présent : ne pas dupliquer l'attribut.
        has_value = bool(re.match(r"\s*=", after))
        replacement = lead + str(displayed) + ("" if has_value else '=""')
        cursor = self.textCursor()
        cursor.beginEditBlock()
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        cursor.insertText(replacement)
        cursor.endEditBlock()
        if not has_value:
            cursor.setPosition(start + len(lead) + len(str(displayed)) + 2)
        self.setTextCursor(cursor)
        self._attribute_completer.popup().hide()
        self.ensureCursorVisible()

    def _check_closing_completion_cursor(self):
        popup = self._closing_completer.popup()
        if not popup.isVisible():
            return
        c = self.textCursor()
        if c.hasSelection() or closing_tag_suggestion(self.toPlainText(), c.position()) is None:
            popup.hide()

    def show_closing_tag_completion(self, force=False):
        """Propose ``div>`` après ``</`` ; Entrée complète la balise.

        Le popup est non modal ; la complétion reste facultative et la saisie
        manuelle continue si l'utilisateur l'ignore ou presse Échap.
        """
        c = self.textCursor()
        suggestion = None if c.hasSelection() else closing_tag_suggestion(
            self.toPlainText(), c.position()
        )
        popup = self._closing_completer.popup()
        if suggestion is None:
            popup.hide()
            return False
        if not force and self.hasFocus() is False:
            return False
        self._closing_completer.setModel(
            QStringListModel([suggestion.label], self._closing_completer)
        )
        self._closing_completer.setCompletionPrefix(suggestion.typed_prefix)
        self._closing_completer.setCurrentRow(0)
        rect = self.cursorRect()
        rect.setWidth(max(110, self.fontMetrics().horizontalAdvance(suggestion.label) + 35))
        self._closing_completer.complete(rect)
        return True

    def _accept_closing_completion(self, displayed):
        """Recontrôle le contexte avant insertion (pas de suggestion périmée)."""
        c = self.textCursor()
        text = self.toPlainText()
        suggestion = closing_tag_suggestion(text, c.position())
        if suggestion is None or str(displayed) != suggestion.label:
            self._closing_completer.popup().hide()
            return
        suffix = "" if text[c.position():c.position()+1] == ">" else ">"
        c.beginEditBlock()
        c.setPosition(suggestion.replace_start)
        c.setPosition(suggestion.replace_end, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(suggestion.name + suffix)
        c.endEditBlock()
        self.setTextCursor(c)
        self._closing_completer.popup().hide()

    def keyPressEvent(self, event):
        vpopup = self._value_completer.popup()
        if vpopup.isVisible() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self._accept_value_completion(self._value_completer.currentCompletion())
            event.accept()
            return
        if vpopup.isVisible() and event.key() == Qt.Key.Key_Escape:
            vpopup.hide()
            event.accept()
            return
        apopup = self._attribute_completer.popup()
        if apopup.isVisible() and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab):
            self._accept_attribute_completion(self._attribute_completer.currentCompletion())
            event.accept()
            return
        if apopup.isVisible() and event.key() == Qt.Key.Key_Escape:
            apopup.hide()
            event.accept()
            return
        popup = self._closing_completer.popup()
        if popup.isVisible() and event.key() in (
            Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Tab
        ):
            self._accept_closing_completion(self._closing_completer.currentCompletion())
            event.accept()
            return
        if popup.isVisible() and event.key() == Qt.Key.Key_Escape:
            popup.hide()
            event.accept()
            return
        super().keyPressEvent(event)
        ch = event.text() or ""
        if (ch == "#" or (vpopup.isVisible() and ch and (ch.isalnum() or ch in "_.:-"))
                or (event.key() == Qt.Key.Key_Backspace and vpopup.isVisible())):
            self.show_value_completion()
        elif vpopup.isVisible():
            vpopup.hide()
        if ((ch and (ch.isalpha() or (apopup.isVisible() and (ch.isalnum() or ch in "_.:-"))))
                or (event.key() == Qt.Key.Key_Backspace and apopup.isVisible())):
            self.show_attribute_completion()
        elif apopup.isVisible():
            apopup.hide()
        if ch == "/":
            self.show_closing_tag_completion()
        elif popup.isVisible() and (ch and (ch.isalnum() or ch in "_.:-")):
            self.show_closing_tag_completion()
        elif event.key() == Qt.Key.Key_Backspace and popup.isVisible():
            self.show_closing_tag_completion()
        elif popup.isVisible():
            popup.hide()

    def set_text_document(self, document):
        """Affiche ``document`` (texte et historique annuler/refaire).

        Chaque document ouvert possède son propre QTextDocument. Les
        connexions propres au document (repliage, renommage des paires de
        balises) sont déplacées vers le nouveau document, et les réglages
        d'affichage de l'éditeur (police, tabulations) lui sont appliqués.
        L'état visuel lié à l'ancien document (repliage, résultat de
        recherche) est réinitialisé.
        """
        old = self.document()
        if document is old:
            return
        for slot in (self._folding_document_changed, self._pair_document_contents_changed):
            try:
                old.contentsChange.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        if not isinstance(document.documentLayout(), QPlainTextDocumentLayout):
            document.setDocumentLayout(QPlainTextDocumentLayout(document))
        document.setDefaultFont(self.font())
        tab_stop = self.tabStopDistance()
        self.setDocument(document)
        self.setTabStopDistance(tab_stop)
        document.contentsChange.connect(self._folding_document_changed)
        document.contentsChange.connect(self._pair_document_contents_changed)
        self._fold_regions_cache = None
        self._folded_opening_lines = set()
        self._search_match = None
        self._search_last = None
        self._pending_pair_rename = None
        self._pair_previous_text = self.toPlainText()
        self.updateLineNumberAreaWidth(0)
        self.highlightCurrentLine()

    def set_visual_wrap(self, enabled: bool):
        """Active/désactive le retour à la ligne visuel sans toucher au XML.

        QPlainTextEdit conserve un QTextBlock par vraie ligne du document : les
        segments visuellement repliés ne deviennent donc pas de nouvelles lignes
        logiques et la numérotation reste celle du fichier source.
        """
        enabled = bool(enabled)
        self.setLineWrapMode(
            QPlainTextEdit.LineWrapMode.WidgetWidth if enabled
            else QPlainTextEdit.LineWrapMode.NoWrap
        )
        self.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff if enabled
            else Qt.ScrollBarPolicy.ScrollBarAlwaysOn
        )
        self.viewport().update()
        self.lineNumberArea.update()

    # V0.8.5.22 : repliage structurel sans aucune altération du texte.
    # QTextBlock.setVisible ne participe ni à l'undo stack, ni aux offsets TEI.
    def _fold_regions(self):
        if self._fold_regions_cache is None:
            self._fold_regions_cache = foldable_xml_regions(self.toPlainText())
        return self._fold_regions_cache

    def _folding_document_changed(self, _position, _removed, _added):
        if self._fold_relayouting:
            return
        self._fold_regions_cache = None
        if self._folded_opening_lines:
            # Une édition ou un formatage peut déplacer les blocs : toujours
            # révéler le texte, jamais conserver des lignes cachées obsolètes.
            self.unfold_all_xml()
        self.lineNumberArea.update()

    def _unfold_for_hidden_cursor(self):
        if self._fold_relayouting or not self._folded_opening_lines:
            return
        block = self.textCursor().block()
        if block.isValid() and not block.isVisible():
            # Navigation depuis XPath, recherche, synchronisation des manuscrits
            # ou lien TEI : il faut retrouver le curseur dans le texte visible.
            self.unfold_all_xml()

    def _apply_xml_fold_visibility(self):
        if self._fold_relayouting:
            return
        self._fold_relayouting = True
        try:
            hidden = set()
            for region in self._fold_regions():
                if region.opening_line in self._folded_opening_lines:
                    hidden.update(range(region.first_hidden_line, region.closing_line + 1))
            block = self.document().firstBlock()
            while block.isValid():
                show = block.blockNumber() not in hidden
                if block.isVisible() != show:
                    block.setVisible(show)
                    block.setLineCount(max(1, block.layout().lineCount()) if show else 0)
                    self.document().markContentsDirty(block.position(), block.length())
                block = block.next()
            self.viewport().update()
            self.lineNumberArea.update()
            self.updateLineNumberAreaWidth(0)
        finally:
            self._fold_relayouting = False

    def toggle_xml_fold(self, line_number=None):
        regions = self._fold_regions()
        if line_number is None:
            region = region_for_cursor(regions, self.textCursor().blockNumber())
        else:
            region = region_at_header(regions, int(line_number))
        if region is None:
            return False
        line = region.opening_line
        if line not in self._folded_opening_lines:
            # Placer le curseur sur la balise qui reste visible. Sinon,
            # la sélection active pourrait rester dans un bloc masqué.
            cursor = self.textCursor()
            if region.first_hidden_line <= cursor.blockNumber() <= region.closing_line:
                cursor.setPosition(region.opening_offset)
                self.setTextCursor(cursor)
        if line in self._folded_opening_lines:
            self._folded_opening_lines.remove(line)
        else:
            # Child folds remain recorded, but are ignored while an ancestor
            # hides them; they reappear once the ancestor is reopened.
            self._folded_opening_lines.add(line)
        self._apply_xml_fold_visibility()
        return True

    def unfold_all_xml(self):
        if not self._folded_opening_lines:
            return
        self._folded_opening_lines.clear()
        self._apply_xml_fold_visibility()

    def fold_all_xml(self):
        # Les conteneurs de document (<TEI>, <text>, <body>) restent
        # consultables. Replier les premiers éléments *éditoriaux* qui les
        # composent, plutôt que masquer d'un coup tout le manuscrit.
        regions = self._fold_regions()
        wrappers = {'TEI', 'teiCorpus', 'text', 'body', 'front', 'back'}
        eligible = [r for r in regions if r.name.rsplit(':', 1)[-1] not in wrappers]
        top = []
        for region in eligible:
            if not any(parent.opening_line < region.opening_line and
                       parent.closing_line >= region.closing_line for parent in eligible):
                top.append(region.opening_line)
        if top:
            cursor = self.textCursor()
            first_region = next((r for r in regions if r.opening_line == top[0]), None)
            if first_region is not None:
                cursor.setPosition(first_region.opening_offset)
                self.setTextCursor(cursor)
        self._folded_opening_lines = set(top)
        self._apply_xml_fold_visibility()

    def toggle_fold_at_gutter(self, point):
        if point.x() >= 17:
            return False
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        while block.isValid():
            height = round(self.blockBoundingRect(block).height()) if block.isVisible() else 0
            if block.isVisible() and top <= point.y() < top + height:
                return self.toggle_xml_fold(block.blockNumber())
            top += height
            if top > point.y():
                break
            block = block.next()
        return False

    def lineNumberAreaWidth(self):
        digits = max(3, len(str(max(1, self.blockCount()))))
        return 24 + self.fontMetrics().horizontalAdvance("9") * digits

    def updateLineNumberAreaWidth(self, _):
        self.setViewportMargins(self.lineNumberAreaWidth(), 0, 0, 0)

    def updateLineNumberArea(self, rect, dy):
        if dy: self.lineNumberArea.scroll(0, dy)
        else: self.lineNumberArea.update(0, rect.y(), self.lineNumberArea.width(), rect.height())
        if rect.contains(self.viewport().rect()): self.updateLineNumberAreaWidth(0)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        cr = self.contentsRect()
        self.lineNumberArea.setGeometry(QRect(cr.left(), cr.top(), self.lineNumberAreaWidth(), cr.height()))

    def lineNumberAreaPaintEvent(self, event):
        painter = QPainter(self.lineNumberArea)
        painter.fillRect(event.rect(), QColor("#f2f0ec"))
        block = self.firstVisibleBlock()
        top = round(self.blockBoundingGeometry(block).translated(self.contentOffset()).top())
        # Qt peut conserver une métrique mise en cache sur un bloc invisible.
        # Seules les hauteurs des blocs vraiment visibles font progresser y.
        regions_by_header = {r.opening_line: r for r in self._fold_regions()}
        while block.isValid() and top <= event.rect().bottom():
            visible = block.isVisible()
            height = round(self.blockBoundingRect(block).height()) if visible else 0
            n = block.blockNumber()
            if visible and top + height >= event.rect().top():
                painter.setPen(QColor("#8a8177"))
                if n in regions_by_header:
                    painter.setPen(QColor("#315a8a"))
                    painter.drawText(QRect(1, top, 17, self.fontMetrics().height()),
                                     Qt.AlignmentFlag.AlignCenter,
                                     "▸" if n in self._folded_opening_lines else "▾")
                    painter.setPen(QColor("#8a8177"))
                painter.drawText(17, top, self.lineNumberArea.width()-22,
                                 self.fontMetrics().height(),
                                 Qt.AlignmentFlag.AlignRight, str(n+1))
            top += height
            block = block.next()

    def highlightCurrentLine(self):
        line = QTextEdit.ExtraSelection()
        line.format.setBackground(QColor("#fff8df"))
        line.format.setProperty(QTextFormat.Property.FullWidthSelection, True)
        line.cursor = self.textCursor()
        line.cursor.clearSelection()
        selections = [line]

        # V0.8.5.23 : mettre en évidence les DEUX balises de la paire sûre,
        # que le curseur soit dans l'ouverture ou la fermeture. QTextCursor
        # d'édition et historique d'annulation sont totalement inchangés.
        cursor = self.textCursor()
        pair = pair_at_context(
            self.toPlainText(), cursor.position(),
            cursor.selectionStart(), cursor.selectionEnd(),
        )
        if pair is not None:
            for token in (pair.opening, pair.closing):
                matching = QTextEdit.ExtraSelection()
                matching.format.setBackground(QColor("#d9ecff"))
                matching.format.setForeground(QColor("#111111"))
                matching.cursor = QTextCursor(self.document())
                matching.cursor.setPosition(token.start)
                matching.cursor.setPosition(token.end, QTextCursor.MoveMode.KeepAnchor)
                selections.append(matching)

        if self._search_match is not None:
            start, end = self._search_match
            if 0 <= start < end <= self.document().characterCount() - 1:
                # ExtraSelection surligne l'occurrence SANS sélectionner du texte
                # dans le QTextCursor d'édition (Entrée ne peut pas la remplacer).
                match = QTextEdit.ExtraSelection()
                match.format.setBackground(QColor("#fff000"))  # jaune vif
                match.format.setForeground(QColor("#17120b"))
                match.cursor = QTextCursor(self.document())
                match.cursor.setPosition(start)
                match.cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
                selections.append(match)
        self.setExtraSelections(selections)

    def setSearchMatch(self, start, end, query):
        self._search_match = (start, end)
        self._search_last = (start, end, query.casefold())
        self.highlightCurrentLine()

    def clearSearchMatch(self):
        if self._search_match is None and self._search_last is None:
            return
        self._search_match = None
        self._search_last = None
        self.highlightCurrentLine()

    def _remove_pair_after_opening_deletion(self, old_text, new_text, position, chars_removed, chars_added):
        """Complète une suppression exacte d'ouverture par celle de sa fermeture.

        Cette routine est appelée depuis QTextDocument.contentsChange : elle
        couvre donc Suppr/Retour arrière, Couper et la commande Supprimer du menu
        contextuel, sans dépendre de la manière dont l'édition a été déclenchée.
        """
        if int(chars_removed) <= 0 or int(chars_added) != 0:
            return False
        a = int(position)
        b = a + int(chars_removed)
        pair = exact_selected_opening_pair(old_text, a, b)
        if pair is None:
            return False
        delta = int(chars_added) - int(chars_removed)
        close_start = pair.closing.start + delta
        close_end = pair.closing.end + delta
        expected = old_text[pair.closing.start:pair.closing.end]
        if not (0 <= close_start <= close_end <= len(new_text)):
            return False
        if new_text[close_start:close_end] != expected:
            return False

        edit = QTextCursor(self.document())
        edit.joinPreviousEditBlock()
        edit.setPosition(close_start)
        edit.setPosition(close_end, QTextCursor.MoveMode.KeepAnchor)
        edit.removeSelectedText()
        edit.endEditBlock()
        return True

    def _pair_document_contents_changed(self, position, chars_removed, chars_added):
        """Applique les automatismes de paire à toute modification du document.

        Le signal Qt fournit directement la zone modifiée : aucune comparaison
        O(n) de tout le document n'est nécessaire à chaque frappe. Un petit état
        transitoire conserve aussi la paire si l'utilisateur efface entièrement
        le QName puis commence à en retaper un autre.
        """
        new_text = self.toPlainText()
        if self._pair_edit_guard:
            self._pair_previous_text = new_text
            return
        old_text = self._pair_previous_text
        if old_text is None:
            self._pair_previous_text = new_text
            return

        self._pair_edit_guard = True
        try:
            if self._remove_pair_after_opening_deletion(
                old_text, new_text, position, chars_removed, chars_added
            ):
                self._pending_pair_rename = None
                self._pair_previous_text = self.toPlainText()
                return

            # Si le QName avait été entièrement effacé au signal précédent,
            # conserver la fermeture connue jusqu'à ce qu'un nouveau QName
            # redevienne lexicalement valide.
            pending = self._pending_pair_rename
            if pending is not None:
                delta = int(chars_added) - int(chars_removed)
                close_start = int(pending["close_start"])
                close_end = int(pending["close_end"])
                change_start = int(position)
                change_end = change_start + int(chars_removed)
                tag_end = old_text.find(">", int(pending["open_start"]))
                edit_still_in_opening = (
                    tag_end >= 0
                    and int(pending["open_start"]) < change_start <= tag_end
                    and change_end <= tag_end
                )
                if change_end <= close_start:
                    close_start += delta
                    close_end += delta
                if not edit_still_in_opening:
                    self._pending_pair_rename = None
                else:
                    pending["close_start"] = close_start
                    pending["close_end"] = close_end
                    opening = opening_tag_at(new_text, int(pending["open_start"]))
                    if opening is not None:
                        old_close_name = str(pending["close_name"])
                        if new_text[close_start:close_end] == old_close_name:
                            edit = QTextCursor(self.document())
                            edit.joinPreviousEditBlock()
                            edit.setPosition(close_start)
                            edit.setPosition(close_end, QTextCursor.MoveMode.KeepAnchor)
                            edit.insertText(opening.name)
                            edit.endEditBlock()
                        self._pending_pair_rename = None
                        self._pair_previous_text = self.toPlainText()
                        return
                    self._pair_previous_text = new_text
                    return

            pair_before = opening_pair_for_name_change(
                old_text, position, chars_removed
            )
            mirror = closing_rename_mirror_for_change(
                old_text, new_text, position, chars_removed, chars_added,
                pair=pair_before,
            )
            if mirror is not None:
                edit = QTextCursor(self.document())
                # Le QName fermant appartient à la même intention d'édition :
                # Ctrl+Z restaure les deux côtés de la paire simultanément.
                edit.joinPreviousEditBlock()
                edit.setPosition(mirror.start)
                edit.setPosition(mirror.end, QTextCursor.MoveMode.KeepAnchor)
                edit.insertText(mirror.new_name)
                edit.endEditBlock()
                self._pending_pair_rename = None
            elif pair_before is not None:
                # Le changement touchait bien le QName d'une paire connue, mais
                # le nouveau tag n'est momentanément plus lexicalement valide
                # (cas classique : sélectionner le nom, Suppr, puis retaper).
                opening_now = opening_tag_at(new_text, pair_before.opening.start)
                if opening_now is None:
                    delta = int(chars_added) - int(chars_removed)
                    cs = pair_before.closing.name_start + delta
                    ce = pair_before.closing.name_end + delta
                    if 0 <= cs <= ce <= len(new_text) and new_text[cs:ce] == pair_before.closing.name:
                        self._pending_pair_rename = {
                            "open_start": pair_before.opening.start,
                            "close_start": cs,
                            "close_end": ce,
                            "close_name": pair_before.closing.name,
                        }
        finally:
            self._pair_edit_guard = False
            self._pair_previous_text = self.toPlainText()
        self.highlightCurrentLine()


def find_in_plain_editor(editor, query, backwards=False):
    """Recherche robuste (insensible à la casse) dans un QPlainTextEdit.

    La recherche avance à partir du résultat précédent et boucle en début/fin.
    Le résultat est mis en évidence sans devenir une sélection éditable.
    Retourne (trouve, numero_occurrence, total_occurrences).
    """
    query = (query or "").strip()
    if not query:
        return False, 0, 0

    text = editor.toPlainText()
    hay = text.casefold()
    needle = query.casefold()
    if not needle:
        return False, 0, 0

    # Liste des occurrences, y compris celles qui se chevauchent : utile pour
    # des recherches éditoriales très courtes.
    positions = []
    start = 0
    while True:
        pos = hay.find(needle, start)
        if pos < 0:
            break
        positions.append(pos)
        start = pos + 1
    if not positions:
        editor.clearSearchMatch()
        return False, 0, 0

    c = editor.textCursor()
    last = editor._search_last
    # Mémoriser le résultat précédent permet notamment à « Précédent »
    # d'éviter de revenir sur le résultat actuel (qui n'est plus sélectionné).
    same_hit = (last is not None and last[2] == needle
                and c.position() == last[1])
    if backwards:
        anchor = last[0] if same_hit else (c.selectionStart() if c.hasSelection() else c.position())
        candidates = [i for i, pos in enumerate(positions) if pos < anchor]
        idx = candidates[-1] if candidates else len(positions) - 1
    else:
        anchor = last[1] if same_hit else (c.selectionEnd() if c.hasSelection() else c.position())
        candidates = [i for i, pos in enumerate(positions) if pos >= anchor]
        idx = candidates[0] if candidates else 0

    pos = positions[idx]
    # Le vrai curseur XML n'a PAS de sélection. Seule l'ExtraSelection jaune
    # représente l'occurrence trouvée, même si le focus se déplace.
    out = QTextCursor(editor.document())
    out.setPosition(pos + len(query))
    editor.setTextCursor(out)
    editor.centerCursor()
    editor.setSearchMatch(pos, pos + len(query), query)
    return True, idx + 1, len(positions)

