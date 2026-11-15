# -*- coding: utf-8 -*-
"""Passage de l'onglet « XML source » à l'aperçu et retour (V0.9.4.7).

Mixin de ``MainWindow`` (editeur_tei.py) : la sélection de la source est
décrite par son texte et son contexte (``selection_quote``), puis retrouvée
dans l'aperçu, et inversement ; l'élément modifiable de l'aperçu et le
repère de ligne ne font que départager. Un aller-retour sans changement
rend la sélection de départ."""
from __future__ import annotations

from PySide6.QtGui import QTextCursor

from app_context import call_later, tr as _t
from formatted_view import xml_selection_structure
from selection_quote import quote as quote_selection, resolve as resolve_quote, xml_compact
from fragment_units import unit_spans
from xml_assembly import path_key
from selection_sync import containing_span_index


class SourceSelectionMixin:
    """Sélection reportée entre la source XML et l'aperçu (voir le module)."""

    def _source_compact(self):
        """Texte visible de la source (``selection_quote.xml_compact``),
        gardé tant que le texte ne change pas (V0.9.4.5) ; ``(texte, carte)``."""
        text = self.editor.toPlainText()
        cached = getattr(self, "_source_compact_cache", None)
        if cached is None or cached[0] is not text:
            cached = self._source_compact_cache = (text, xml_compact(text))
        return cached

    def _source_unit_spans(self, text=None):
        """``unit_spans`` de la source pour les éléments modifiables de
        l'aperçu, gardés tant que le texte et ces éléments ne changent pas
        (V0.9.4.5 : relevé coûteux sur un gros fichier)."""
        text = self.editor.toPlainText() if text is None else text
        names = self._preview_unit_names()
        key = (type(names), names)
        cached = getattr(self, "_source_units_cache", None)
        if cached is None or cached[0] is not text or cached[1] != key:
            cached = self._source_units_cache = (text, key, unit_spans(text, names))
        return cached[2]

    def _source_unit_at(self, position):
        """Élément modifiable de l'aperçu (V0.9.2.9) qui contient la position
        ``position`` de la source : ``(rang, début, fin)``, ou None. Pour une
        édition en parties (V0.9.1.5), le rang est celui de l'aperçu de
        toute l'édition."""
        sources = self._assembled_preview_sources()
        if sources is not None:
            pidx = sources.paragraph_at(self.document.path, position)
            if pidx is None:
                return None
            return pidx, sources.paragraphs[pidx].start, sources.paragraphs[pidx].end
        spans = self._source_unit_spans()
        pidx = containing_span_index(spans, position)
        return None if pidx is None else (pidx, *spans[pidx])

    def _source_unit_span(self, paragraph):
        """``(début, fin)`` dans la source de l'élément modifiable de rang
        ``paragraph`` de l'aperçu, ou None. Pour une édition en parties, le
        fichier qui le contient est d'abord affiché."""
        sources = self._assembled_preview_sources()
        try:
            if sources is not None:
                span = sources.paragraphs[int(paragraph)]
                if span is None or not self._show_file_position(span.path, span.start):
                    return None
                return span.start, span.end
            return self._source_unit_spans()[int(paragraph)]
        except (IndexError, TypeError, ValueError):
            return None

    def _source_selection_context(self, cursor):
        """La sélection de la source décrite pour l'aperçu (V0.9.4.5) :
        ``quote`` (citation et contexte), et pour départager ``paragraph``
        (élément modifiable) et ``relative`` (caractères visibles depuis son
        début) ; None si elle n'a pas de texte visible."""
        text, compact = self._source_compact()
        qt = self.editor.positions(text)
        start = qt.python(cursor.selectionStart())
        i, j = compact.range_of(start, qt.python(cursor.selectionEnd()))
        wanted = quote_selection(compact, i, j)
        if wanted is None:
            return None
        unit = self._source_unit_at(start)
        if unit is None:
            return {"quote": wanted, "paragraph": None, "relative": None}
        return {"quote": wanted, "paragraph": unit[0], "relative": i - compact.index_at(unit[1])}

    def _source_selection_structure(self, cursor):
        """Repère structurel de la sélection de la source pour l'aperçu
        (``xml_selection_structure``, V0.9.3.0) : éléments modifiables du
        document affiché, rangés comme dans l'aperçu."""
        source = self.editor.toPlainText()
        sources = self._assembled_preview_sources()
        if sources is not None:
            key = path_key(self.document.path)
            units = [(index, span.start, span.end) for index, span in enumerate(sources.paragraphs)
                     if span is not None and path_key(span.path) == key]
        else:
            units = [(index, a, b) for index, (a, b)
                     in enumerate(self._source_unit_spans(source))]
        qt = self.editor.positions(source)
        return xml_selection_structure(source, qt.python(cursor.selectionStart()), qt.python(cursor.selectionEnd()),
                                       units)

    def _select_source_quote(self, context, near_cursor=False):
        """Sélectionne dans la source ce que décrit ``context`` (voir
        ``ClickablePreview.selection_context``) : dans l'élément modifiable
        ``paragraph`` s'il y est, sinon dans tout le fichier, près du curseur
        avec ``near_cursor`` (placé sur le repère de ligne de la sélection),
        sinon à la même place relative. False si le texte n'y est pas
        (V0.9.4.5)."""
        wanted = (context or {}).get("quote")
        if wanted is None:
            return False
        found = None
        paragraph = context.get("paragraph")
        span = self._source_unit_span(paragraph) if paragraph is not None else None
        text, compact = self._source_compact()
        if span is not None:
            scope = compact.range_of(*span)
            relative = context.get("relative")
            found = resolve_quote(compact, wanted, scope=scope,
                                  hint=None if relative is None else scope[0] + int(relative))
        if found is None:
            hint = None
            if near_cursor:
                hint = compact.index_at(self.editor.positions(text).python(self.editor.textCursor().position()))
            found = resolve_quote(compact, wanted, hint=hint)
        if found is None:
            return False
        self._select_source_span(*compact.span(*found))
        return True

    def _select_source_span(self, start, end):
        """Sélectionne ``start``…``end`` (indices Python) dans la source."""
        qt = self.editor.positions()
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(qt.qt(start))
        cursor.setPosition(qt.qt(end), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    def _left_tab_changed(self, index):
        if not hasattr(self, "formatted_view"):
            return
        previous = getattr(self, "_previous_left_tab_index", 0)
        self._previous_left_tab_index = index
        # Édition en parties (V0.9.1.5) : l'aperçu montre toute l'édition ; ses
        # repères de ligne et ses paragraphes renvoient chacun à son fichier.
        # Un document auxiliaire (V0.9.4.4) : l'aperçu montre ce document.
        parts = self._preview_shows_assembly()

        if self.left_tabs.widget(index) is self.formatted_view:
            # XML -> XSLT : la sélection est retrouvée par son texte et son
            # contexte ("qui" peut apparaître plusieurs fois, V0.9.4.5).
            source_cursor = self.editor.textCursor()
            qt = self.editor.positions()
            source_pos = qt.python(source_cursor.selectionStart() if source_cursor.hasSelection()
                                   else source_cursor.position())
            if parts:
                sources = self._assembled_preview_sources()
                ordinal = sources.line_before(self.document.path, source_pos) if sources is not None else None
            else:
                ordinal = self.ordinal_at_position(source_pos)
            # Sélection décrite par son texte et son contexte (V0.9.4.5) :
            # l'élément modifiable et le repère de ligne ne font que départager.
            context = self._source_selection_context(source_cursor) if source_cursor.hasSelection() else None
            if context is not None:
                context["line"] = ordinal
            structure = self._source_selection_structure(source_cursor) if context is not None else None
            # Aller-retour (V0.9.3.0) : tant que la sélection faite dans
            # l'aperçu y reste, le retour à la source rend celle de départ.
            self._preview_round_trip = None
            round_trip = (self.document, self.editor.document().revision(),
                          qt.python(source_cursor.selectionStart()), qt.python(source_cursor.selectionEnd()))
            # Aller-retour dans l'autre sens (V0.9.4.5) : une sélection venue de
            # l'aperçu et inchangée y revient à sa place, même quand la feuille
            # affiche plusieurs fois ce texte de la source (index, résumé).
            back, self._source_round_trip = getattr(self, "_source_round_trip", None), None
            preview_back = None
            if (back and source_cursor.hasSelection() and back[0] is self.document
                    and back[1] == self.editor.document().revision()
                    and back[2:4] == (source_cursor.selectionStart(), source_cursor.selectionEnd())):
                preview_back = back[4:]
            self.formatted_view.became_visible()

            def restore_preview_context(n=ordinal, context=context, shape=structure, back=preview_back):
                preview = self.formatted_view.preview
                # Un élément entier (résultat XPath), un apparat, une note :
                # leur texte n'est pas celui de l'aperçu, d'où la structure.
                if ((back and preview.restore_selection(*back)) or (context and preview.select_quote(context))
                        or (shape and preview.select_structure(shape))):
                    cursor = preview.textCursor()
                    self._preview_round_trip = round_trip + (cursor.selectionStart(), cursor.selectionEnd())
                    return
                if context:
                    self.statusBar().showMessage(_t("selection.not_found.preview"), 6000)
                if n is not None:
                    self.formatted_view.scroll_to_t1_line(n)

            # Quand l'aperçu est prêt : une feuille 3.0 le rend plus tard,
            # hors du fil de la fenêtre (V0.9.4.4).
            self.formatted_view.when_ready(restore_preview_context)
            return

        if index == 0 and previous == 1:
            # XSLT -> XML : la sélection est retrouvée par son texte et son
            # contexte (V0.9.4.5).
            preview_cursor = self.formatted_view.preview.textCursor()
            has_selection = preview_cursor.hasSelection()
            trip, self._preview_round_trip = getattr(self, "_preview_round_trip", None), None
            if (trip and has_selection and trip[0] is self.document
                    and trip[1] == self.editor.document().revision()
                    and trip[4:] == (preview_cursor.selectionStart(), preview_cursor.selectionEnd())):
                call_later(0, self, lambda span=trip[2:4], shown=self.document:
                           self.document is shown and self._select_source_span(*span))
                return
            # Sélection décrite par son texte et son contexte (V0.9.4.5).
            context = self.formatted_view.preview.selection_context() if has_selection else None
            ordinal = context.get("line") if context is not None else None
            # Le curseur de la source, placé sur le repère de ligne de la
            # sélection, départage des passages semblables.
            near_cursor = ordinal is not None
            if ordinal is None:
                ordinal = self.formatted_view.current_preview_line()
            if ordinal is not None and parts:
                # Le repère de l'aperçu mène au fichier qui contient la ligne.
                self.navigate_to_preview_line(ordinal)
            elif ordinal is not None:
                self.navigate_to_base_ordinal(ordinal, move_xml_cursor=True)

            preview_back = (self.formatted_view.preview.document().characterCount(),
                            preview_cursor.selectionStart(), preview_cursor.selectionEnd())

            def restore_xml_context(context=context, near_cursor=near_cursor, shown=self.document, back=preview_back):
                if self.document is not shown:
                    return  # un autre document est affiché entre-temps
                if context and self._select_source_quote(context, near_cursor):
                    cursor = self.editor.textCursor()
                    self._source_round_trip = (self.document, self.editor.document().revision(),
                                               cursor.selectionStart(), cursor.selectionEnd()) + back
                    return
                if context:
                    self.statusBar().showMessage(_t("selection.not_found.source"), 6000)
                self.editor.setFocus()

            call_later(0, self, restore_xml_context)
