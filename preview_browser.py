# -*- coding: utf-8 -*-
"""Le navigateur de l'aperçu de la vue XSLT / CSS (V0.9.4.7, extrait de
formatted_view) : ``ClickablePreview`` (repères de ligne et crayons
cliquables, sélection rapportée à la source) et ``find_in_rich_editor``
(recherche dans un texte enrichi)."""
from __future__ import annotations

import bisect
import re

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QTextBrowser, QTextEdit

from selection_quote import plain_compact, quote as quote_selection, resolve as resolve_quote
from text_search import Utf16Positions


def find_in_rich_editor(editor, query, backwards=False):
    """Recherche sûre dans le QTextBrowser de l’aperçu XSLT.

    - insensible à la casse ;
    - tolère les WORD JOINER U+2060 techniques entre les lettres ;
    - boucle en début/fin ;
    - surligne l’occurrence via ExtraSelection sans laisser de sélection active.

    Retourne (trouve, numero_occurrence, total_occurrences).
    """
    query = (query or "").strip()
    if not query:
        try:
            editor.clearSearchMatch()
        except Exception:
            pass
        return False, 0, 0

    doc = editor.document()
    visible_query = query.replace("\u2060", "")
    if not visible_query:
        return False, 0, 0
    pattern = "\u2060*".join(QRegularExpression.escape(char) for char in visible_query)
    expr = QRegularExpression(
        pattern,
        QRegularExpression.PatternOption.CaseInsensitiveOption,
    )

    # Recenser toutes les occurrences avec leurs positions réelles dans le
    # QTextDocument. Ces positions incluent les WORD JOINER invisibles.
    occurrences = []
    scan = QTextCursor(doc)
    scan.movePosition(QTextCursor.MoveOperation.Start)
    while True:
        hit = doc.find(expr, scan)
        if hit.isNull():
            break
        a, b = hit.selectionStart(), hit.selectionEnd()
        occurrences.append((a, b))
        scan = QTextCursor(doc)
        scan.setPosition(max(b, a + 1))

    if not occurrences:
        try:
            editor.clearSearchMatch()
        except Exception:
            pass
        return False, 0, 0

    needle = visible_query.casefold()
    last = getattr(editor, "_search_last", None)
    cur = editor.textCursor()
    same_hit = bool(last is not None and len(last) >= 3 and last[2] == needle)

    if backwards:
        anchor = last[0] if same_hit else cur.position()
        candidates = [i for i, (a, b) in enumerate(occurrences) if a < anchor]
        idx = candidates[-1] if candidates else len(occurrences) - 1
    else:
        anchor = last[1] if same_hit else cur.position()
        candidates = [i for i, (a, b) in enumerate(occurrences) if a >= anchor]
        idx = candidates[0] if candidates else 0

    a, b = occurrences[idx]
    # Le vrai curseur reste réduit à un point : aucune sélection active ne peut
    # capter une frappe. L’occurrence visible est une ExtraSelection jaune.
    out = QTextCursor(doc)
    out.setPosition(b)
    editor.setTextCursor(out)
    editor.ensureCursorVisible()
    if hasattr(editor, "setSearchMatch"):
        editor.setSearchMatch(a, b, visible_query)
    else:
        # Compatibilité avec les petits doubles de test hors Qt.
        editor._search_match = (a, b)
        editor._search_last = (a, b, visible_query.casefold())
    return True, idx + 1, len(occurrences)


def _rich_selection_pattern(text):
    """Regex Qt pour retrouver du texte visible malgré les WORD JOINER."""
    clean = (text or "").replace("\u2060", "")
    clean = clean.replace("\u2029", " ").replace("\u2028", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""
    parts = []
    for i, ch in enumerate(clean):
        if ch.isspace():
            parts.append(r"(?:\s|\x{2060})+")
        else:
            parts.append(QRegularExpression.escape(ch))
            if i + 1 < len(clean) and not clean[i + 1].isspace():
                parts.append(r"\x{2060}*")
    return "".join(parts)


class ClickablePreview(QTextBrowser):
    """Aperçu HTML dont le texte est cliquable sans être rendu comme un hyperlien."""

    lineActivated = Signal(int)
    # Sélection faite à la souris (glisser, double-clic), hors des liens.
    textSelected = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._marker_positions = []
        self._marker_lines = []
        self._line_to_position = {}
        self._paragraph_markers = []
        self._paragraph_content_by_index = {}
        self.active_line_ordinal = None
        # Recherche dans l’aperçu : le résultat est mis en évidence via
        # ExtraSelection, sans devenir la sélection active du QTextCursor.
        # Cela garde le focus clavier dans le champ de recherche et évite tout
        # comportement différent de la source XML / de l’éditeur de fragment.
        self._search_match = None
        self._search_last = None
        # Sélection en cours au moment d'un clic sur le crayon ✎, que le clic
        # efface : (début, fin), reprise par take_selection_before_pencil().
        self._selection_before_pencil = None

    def setSearchMatch(self, start, end, query):
        """Surligne en jaune l'occurrence ``start``–``end`` d'une recherche de ``query``
        (``ExtraSelection``) sans la sélectionner ; ``find_in_rich_editor`` repart de là. Tout
        autre surlignage de l'aperçu est remplacé."""
        self._search_match = (int(start), int(end))
        self._search_last = (int(start), int(end), (query or "").casefold())
        sel = QTextEdit.ExtraSelection()
        sel.format.setBackground(QColor("#fff000"))
        sel.format.setForeground(QColor("#17120b"))
        sel.cursor = QTextCursor(self.document())
        sel.cursor.setPosition(int(start))
        sel.cursor.setPosition(int(end), QTextCursor.MoveMode.KeepAnchor)
        self.setExtraSelections([sel])

    def clearSearchMatch(self):
        """Efface le surlignage de recherche et oublie la dernière occurrence."""
        self._search_match = None
        self._search_last = None
        self.setExtraSelections([])

    @staticmethod
    def _line_from_href(href):
        m = re.match(r"tei-line://base/(\d+)$", href or "", re.I)
        return int(m.group(1)) if m else None

    @staticmethod
    def _paragraph_from_href(href):
        m = re.match(r"tei-edit://p/(\d+)$", href or "", re.I)
        return int(m.group(1)) if m else None

    def rebuild_line_markers(self):
        """Relève les liens du document affiché : repères de ligne ``tei-line://base/N`` (place de
        chacun) et crayons ``tei-edit://p/N`` (début du texte de chaque élément modifiable, après
        le crayon et son espace). À appeler après chaque ``setHtml`` : les méthodes de position
        de l'aperçu s'y fient."""
        self._compact_cache = None
        marks = []
        paragraphs = []
        block = self.document().begin()
        while block.isValid():
            it = block.begin()
            while not it.atEnd():
                frag = it.fragment()
                if frag.isValid():
                    fmt = frag.charFormat()
                    if fmt.isAnchor():
                        href = fmt.anchorHref()
                        n = self._line_from_href(href)
                        if n is not None:
                            marks.append((frag.position(), n))
                        pidx = self._paragraph_from_href(href)
                        if pidx is not None:
                            paragraphs.append((frag.position(), frag.position() + frag.length(), pidx))
                it += 1
            block = block.next()
        marks.sort()
        self._marker_positions = [p for p, _ in marks]
        self._marker_lines = [n for _, n in marks]
        self._line_to_position = {}
        for p, n in marks:
            self._line_to_position.setdefault(n, p)

        plain = self.toPlainText()
        normalized = []
        for marker_pos, after_anchor, pidx in sorted(paragraphs):
            content_pos = int(after_anchor)
            # place_edit_markers ajoute exactement un espace après le crayon.
            if 0 <= content_pos < len(plain) and plain[content_pos].isspace():
                content_pos += 1
            normalized.append((marker_pos, content_pos, pidx))
        self._paragraph_markers = normalized
        self._paragraph_content_by_index = {pidx: content for _, content, pidx in normalized}

    def paragraph_for_position(self, char_pos):
        """Rang de l'élément modifiable où se trouve la position ``char_pos`` de l'aperçu : celui du
        dernier crayon ✎ placé avant elle ; None avant le premier crayon ou s'il n'y en a pas."""
        if not self._paragraph_markers:
            return None
        positions = [x[0] for x in self._paragraph_markers]
        i = bisect.bisect_right(positions, int(char_pos)) - 1
        return self._paragraph_markers[i][2] if i >= 0 else None

    def paragraph_bounds(self, paragraph_index):
        """``(début, fin)`` dans l'aperçu de l'élément modifiable de rang ``paragraph_index`` : du
        texte qui suit son crayon jusqu'au crayon suivant, ou jusqu'à la fin du document ; None
        si ce rang n'a pas de crayon."""
        for i, (marker_pos, content_pos, pidx) in enumerate(self._paragraph_markers):
            if pidx == int(paragraph_index):
                end = self._paragraph_markers[i + 1][0] if i + 1 < len(self._paragraph_markers) else max(0, self.document().characterCount() - 1)
                return content_pos, end
        return None

    def _compact(self):
        """Texte de l'aperçu sans blancs (``selection_quote.plain_compact``)
        et positions Qt ↔ Python, gardés jusqu'au rendu suivant (V0.9.4.5)."""
        count = self.document().characterCount()
        cached = getattr(self, "_compact_cache", None)
        if cached is None or cached[0] != count:
            plain = self.toPlainText()
            cached = self._compact_cache = (count, plain_compact(plain), Utf16Positions(plain))
        return cached[1], cached[2]

    def selection_context(self):
        """La sélection de l'aperçu décrite pour une autre vue (V0.9.4.5) :
        ``quote`` (citation et contexte, ``selection_quote``), et pour
        départager ``paragraph`` (élément modifiable), ``relative`` (caractères
        visibles depuis son début) et ``line`` (repère de ligne du pivot) ;
        None sans texte sélectionné."""
        cursor = self.textCursor()
        if not cursor.hasSelection():
            return None
        compact, positions = self._compact()
        start = cursor.selectionStart()
        i, j = compact.range_of(positions.python(start), positions.python(cursor.selectionEnd()))
        wanted = quote_selection(compact, i, j)
        if wanted is None:
            return None
        paragraph = self.paragraph_for_position(start)
        bounds = self.paragraph_bounds(paragraph) if paragraph is not None else None
        relative = i - compact.index_at(positions.python(bounds[0])) if bounds else None
        return {"quote": wanted, "paragraph": paragraph, "relative": relative, "line": self.line_for_position(start)}

    def select_quote(self, context, focus=True, anywhere=True):
        """Sélectionne dans l'aperçu ce que décrit ``context`` (voir
        ``selection_context``) : dans l'élément modifiable ``paragraph`` s'il
        y est, sinon (``anywhere``) dans toute la page, près du repère
        ``line`` en cas de doute. False si le texte n'y est pas (V0.9.4.5)."""
        wanted = (context or {}).get("quote")
        if wanted is None:
            return False
        compact, positions = self._compact()
        found = None
        paragraph = context.get("paragraph")
        bounds = self.paragraph_bounds(paragraph) if paragraph is not None else None
        if bounds:
            scope = compact.range_of(positions.python(bounds[0]), positions.python(bounds[1]))
            relative = context.get("relative")
            found = resolve_quote(compact, wanted, scope=scope,
                                  hint=None if relative is None else scope[0] + int(relative))
        if found is None and (anywhere or not bounds):
            line = context.get("line")
            position = self._line_to_position.get(int(line)) if line is not None else None
            found = resolve_quote(compact, wanted,
                                  hint=None if position is None else compact.index_at(positions.python(position)))
        if found is None:
            return False
        self._select_range(*(positions.qt(index) for index in compact.span(*found)), focus=focus)
        return True

    def restore_selection(self, size, start, end):
        """Rend la sélection ``start``–``end`` de l'aperçu (aller-retour,
        V0.9.4.5), s'il n'a pas changé depuis (``size`` : son nombre de
        caractères). False sinon."""
        if self.document().characterCount() != size or not 0 <= start < end < size:
            return False
        self._select_range(start, end)
        return True

    def _select_range(self, start, end, focus=True):
        self.clearSearchMatch()
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        if focus:
            self.setFocus()
        line = self.line_for_position(start)
        if line is not None:
            self.active_line_ordinal = line

    def _words_in(self, words, start, end, target, at_end):
        """Position des mots ``words`` (les plus nombreux qu'on trouve, en
        partant de tous) entre ``start`` et ``end``, l'occurrence la plus
        proche de ``target`` : son début, ou sa fin avec ``at_end``."""
        words = words.split()
        for count in range(len(words), 0, -1):
            part = " ".join(words[-count:] if at_end else words[:count])
            pattern = _rich_selection_pattern(part)
            if not pattern:
                continue
            expr = QRegularExpression(pattern)
            found = []
            scan = QTextCursor(self.document())
            scan.setPosition(start)
            while True:
                hit = self.document().find(expr, scan)
                if hit.isNull() or hit.selectionStart() >= end:
                    break
                if hit.selectionEnd() <= end:
                    found.append((hit.selectionStart(), hit.selectionEnd()))
                scan = QTextCursor(self.document())
                scan.setPosition(max(hit.selectionEnd(), hit.selectionStart() + 1))
            if found:
                a, b = min(found, key=lambda ab: abs((ab[1] if at_end else ab[0]) - target))
                return b if at_end else a
        return None

    def select_structure(self, structure):
        """Sélectionne dans l'aperçu une sélection de la source décrite par
        ``xml_selection_structure`` (V0.9.3.0) : de l'élément modifiable
        ``first`` à ``last``, entiers s'ils sont couverts, sinon de leurs
        premiers à leurs derniers mots. False si ces mots n'y sont pas."""
        if not structure:
            return False
        first = self.paragraph_bounds(structure["first"])
        last = self.paragraph_bounds(structure["last"])
        if not first or not last:
            return False
        if structure["from_start"]:
            start = first[0]
        else:
            start = self._words_in(structure["head"], first[0], first[1],
                                   first[0] + int(structure["head_relative"]), at_end=False)
        if start is None:
            return False
        if structure["to_end"]:
            end = last[1]
            text = self.toPlainText()
            while end > start and (text[end - 1].isspace() or text[end - 1] == "\u2060"):
                end -= 1
        else:
            end = self._words_in(structure["tail"], start, last[1],
                                 last[0] + int(structure["tail_relative"]), at_end=True)
        if end is None or end <= start:
            return False
        self.clearSearchMatch()
        cursor = QTextCursor(self.document())
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.setFocus()
        line = self.line_for_position(start)
        if line is not None:
            self.active_line_ordinal = line
        return True

    def line_for_position(self, char_pos):
        """Rang du dernier repère de ligne du témoin pivot placé avant la position ``char_pos`` de
        l'aperçu (ou à cette position) ; None avant le premier repère ou s'il n'y en a pas."""
        if not self._marker_positions:
            return None
        i = bisect.bisect_right(self._marker_positions, int(char_pos)) - 1
        return self._marker_lines[i] if i >= 0 else None

    def line_at_viewport_center(self):
        """Rang du repère de ligne du témoin pivot au centre de la zone visible, qui devient la
        ligne active (``active_line_ordinal``) ; None s'il n'y en a pas."""
        pos = self.cursorForPosition(self.viewport().rect().center()).position()
        line = self.line_for_position(pos)
        if line is not None:
            self.active_line_ordinal = line
        return line

    def scroll_to_line(self, ordinal, center=True):
        """Place le curseur sur le repère de ligne ``ordinal`` et fait défiler l'aperçu jusqu'à lui,
        centré dans la fenêtre avec ``center`` ; la ligne devient active. False si l'aperçu n'a
        pas ce repère."""
        pos = self._line_to_position.get(int(ordinal))
        if pos is None:
            return False
        c = QTextCursor(self.document())
        c.setPosition(pos)
        self.setTextCursor(c)
        self.ensureCursorVisible()
        self.active_line_ordinal = int(ordinal)
        if center:
            # Une fois le curseur rendu visible, recentrer approximativement le
            # passage dans la fenêtre pour garder du contexte au-dessus et dessous.
            rect = self.cursorRect(c)
            bar = self.verticalScrollBar()
            target = bar.value() + rect.center().y() - self.viewport().height() // 2
            bar.setValue(max(bar.minimum(), min(bar.maximum(), target)))
        return True

    def mousePressEvent(self, event):
        cursor = self.textCursor()
        on_pencil = self._paragraph_from_href(self.anchorAt(event.position().toPoint())) is not None
        self._selection_before_pencil = (
            (cursor.selectionStart(), cursor.selectionEnd()) if on_pencil and cursor.hasSelection() else None)
        super().mousePressEvent(event)

    def take_selection_before_pencil(self):
        """Sélection effacée par le dernier clic sur un crayon, ou None."""
        selection, self._selection_before_pencil = self._selection_before_pencil, None
        return selection

    def mouseReleaseEvent(self, event):
        # Les vrais liens de l'aperçu (notamment le crayon ✎) gardent leur
        # comportement normal. Un clic sur le texte ordinaire est associé au
        # dernier marqueur du témoin pivot placé avant la position du curseur.
        pos = event.position().toPoint()
        href = self.anchorAt(pos)
        super().mouseReleaseEvent(event)
        if href:
            return
        if self._marker_positions:
            char_pos = self.cursorForPosition(pos).position()
            line = self.line_for_position(char_pos)
            if line is not None:
                self.active_line_ordinal = line
                self.lineActivated.emit(line)
        if self.textCursor().hasSelection():
            self.textSelected.emit()
