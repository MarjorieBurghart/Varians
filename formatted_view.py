# -*- coding: utf-8 -*-
"""Vue XSLT / CSS : aperçu mis en forme de l'édition, synchronisé avec la source, et édition par fragments."""
from __future__ import annotations

import bisect
import hashlib
import html as html_lib
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET

from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QDialog, QFileDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMessageBox, QPushButton, QSizePolicy, QSplitter, QTextBrowser, QTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)
from app_context import _settings, call_later, tr as _t
from code_editor import CodeEditor, find_in_plain_editor
from completion_ui import CompletionDialog
from custom_completion import load_custom_completion
from selection_sync import choose_occurrence, occurrence_index_for_position
from tei_facsimile import position_inside_xml_markup
from text_search import SearchError
from code_editor import replace_all_in_plain_editor, replace_in_plain_editor
from fragment_units import edit_stylesheet, edit_stylesheet_url, mark_units, place_edit_markers, unit_spans
from replace_bar import search_error_text
from xslt_engines import xslt_error_text as _xslt_error_text


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


def _selection_xml_to_visible_text(fragment):
    """Convertit une sélection brute de la source XML en texte visible approché.

    Cette fonction sert uniquement au transfert de sélection XML -> aperçu.
    Les ``lb break="no"`` ne produisent aucun espace ; les autres ``lb``
    produisent un espace, comme dans la XSLT de l'éditeur. Les autres balises
    sont retirées.
    """
    text = (fragment or "").replace("\u2029", "\n").replace("\u2028", "\n")
    lb = r"<(?:[A-Za-z_][\w.-]*:)?lb\b[^>]*?/?>"
    break_no = r"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bbreak\s*=\s*[\"']no[\"'])[^>]*?/?>"
    # Un saut de ligne d'indentation autour d'un break=no ne doit pas devenir
    # un espace visible. On absorbe donc le blanc immédiatement adjacent.
    text = re.sub(r"\s*" + break_no + r"\s*", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"\s*" + lb + r"\s*", " ", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<[^>]+>", "", text, flags=re.DOTALL)
    text = html_lib.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


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


def _xml_selection_pattern(text):
    """Regex Python pour retrouver un texte visible dans la source XML.

    Entre deux caractères d'un même mot, un ``lb break="no"`` accompagné de
    ses retours à la ligne est autorisé. Une sélection issue de l'aperçu peut
    ainsi devenir, dans la source, une sélection continue incluant la balise lb.
    """
    clean = (text or "").replace("\u2060", "")
    clean = clean.replace("\u2029", " ").replace("\u2028", " ")
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""
    lb_no = r"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bbreak\s*=\s*[\"']no[\"'])[^>]*?/?>"
    lb_break = r"<(?:[A-Za-z_][\w.-]*:)?lb\b(?![^>]*\bbreak\s*=\s*[\"']no[\"'])[^>]*?/?>"
    no_break_sep = r"(?:\s*" + lb_no + r"\s*)*"
    visible_space = r"(?:\s+|\s*" + lb_break + r"\s*)+"
    parts = []
    for i, ch in enumerate(clean):
        if ch.isspace():
            parts.append(visible_space)
        else:
            parts.append(re.escape(ch))
            if i + 1 < len(clean) and not clean[i + 1].isspace():
                parts.append(no_break_sep)
    return "".join(parts)


def xml_occurrences(xml_text, visible, start=0, end=None):
    """Plages où le texte visible ``visible`` apparaît dans ``xml_text[start:end]``.

    Sert à la source XML comme au fragment ouvert. Une occurrence visible
    seulement dans un nom de balise ou une valeur d'attribut est écartée ; une
    sélection traversant un lb break=no reste admise, car son premier
    caractère est du texte.
    """
    pattern = _xml_selection_pattern(visible)
    if not pattern:
        return []
    end = len(xml_text) if end is None else int(end)
    try:
        matches = list(re.finditer(pattern, xml_text[start:end], flags=re.DOTALL))
    except re.error:
        return []
    return [(start + m.start(), start + m.end()) for m in matches
            if not position_inside_xml_markup(xml_text, start + m.start())]


def xml_selection_descriptor(xml_text, visible, selection_start, start=0, end=None):
    """Rang de la sélection parmi les occurrences de ``visible`` dans
    ``xml_text[start:end]``, et longueur du texte visible qui la précède
    depuis ``start``. Ce décalage approximatif sert seulement de repli si la
    transformation XSLT a modifié le nombre d'occurrences."""
    occurrences = xml_occurrences(xml_text, visible, start, end)
    return {
        "occurrence": occurrence_index_for_position(occurrences, selection_start),
        "relative": len(_selection_xml_to_visible_text(xml_text[start:int(selection_start)])),
    }


def pick_xml_occurrence(xml_text, visible, descriptor, start=0, end=None):
    """Occurrence de ``visible`` décrite par ``descriptor`` (rang, sinon
    décalage visible depuis ``start``), ou None."""
    occurrences = xml_occurrences(xml_text, visible, start, end)
    target = None
    # Pour le repli positionnel, on approxime l'offset visible en balayant
    # les occurrences candidates ; l'index d'occurrence reste prioritaire.
    if descriptor.get("relative") is not None and occurrences:
        wanted = int(descriptor.get("relative") or 0)
        target = min(
            occurrences,
            key=lambda ab: abs(len(_selection_xml_to_visible_text(xml_text[start:ab[0]])) - wanted),
        )[0]
    return choose_occurrence(occurrences, descriptor.get("occurrence"), target)


def resolve_css_variables(css_text):
    """Résout les variables CSS :root pour le moteur HTML simplifié de Qt."""
    m = re.search(r":root\s*\{(.*?)\}", css_text, re.I | re.S)
    if not m:
        return css_text
    variables = dict(re.findall(r"(--[\w-]+)\s*:\s*([^;]+);", m.group(1)))
    out = css_text[:m.start()] + css_text[m.end():]
    for name, value in variables.items():
        out = out.replace(f"var({name})", value.strip())
    return out


# Règles de base de l'aperçu (V0.9.3.0), placées avant la CSS du projet, qui
# les remplace si elle en a : une strophe de la feuille livrée (un seul bloc,
# vers séparés par des <br/>) en retrait, même avec la CSS d'un projet créé
# par une version antérieure. Qt ignore toute règle placée après un @media :
# celles du crayon ✎ et des repères de ligne, autrefois ajoutées à la fin,
# n'étaient pas appliquées (le crayon était un lien bleu souligné).
PREVIEW_BASE_CSS = (
    ".lg { margin-top: 0.5em; margin-bottom: 1em; margin-left: 2em; line-height: 150%; }\n"
    ".ref { color: #8a8177; }\n"
    "a.tei-edit-marker { color:#8a8177; text-decoration:none; font-family:sans-serif; font-size:0.75em;"
    " padding-right:0.35em; }\n"
    "a.tei-line-marker { color: transparent; text-decoration:none; font-size:0; line-height:0; margin:0;"
    " padding:0; white-space:nowrap; }\n"
)


LINE_MARKER_RE = re.compile(
    r'(<a\b(?=[^>]*\bclass=["\'][^"\']*\btei-line-marker\b[^"\']*["\'])'
    r'(?=[^>]*\bhref=["\']tei-line://base/(\d+)["\'])[^>]*>)(?:\s|\u2060|&#8288;)*</a>',
    re.IGNORECASE,
)


def make_line_segments_clickable(html_text):
    """Numérote puis préserve les repères du témoin de base invisibles en temps linéaire.

    La XSLT écrit volontairement ``tei-line://base/INDEX`` au lieu de calculer
    ``count(preceding::tei:lb...)`` pour chaque ligne. Ce dernier calcul rendait
    la transformation presque quadratique. Ici, Python numérote les marqueurs
    0,1,2... en un seul passage, puis le QTextDocument les utilise comme repères
    invisibles pour les clics et la synchronisation des trois manuscrits.
    """
    counter = 0

    def number_placeholder(m):
        nonlocal counter
        n = counter
        counter += 1
        quote = m.group(1)
        return f'href={quote}tei-line://base/{n}{quote}'

    html_text = re.sub(
        r'href=(["\'])tei-line://base/INDEX\1',
        number_placeholder,
        html_text,
        flags=re.IGNORECASE,
    )

    lines = set()

    def repl(m):
        lines.add(int(m.group(2)))
        return m.group(1) + '&#8288;</a>'

    out = LINE_MARKER_RE.sub(repl, html_text)
    return out, len(lines), 0


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
        if not self._paragraph_markers:
            return None
        positions = [x[0] for x in self._paragraph_markers]
        i = bisect.bisect_right(positions, int(char_pos)) - 1
        return self._paragraph_markers[i][2] if i >= 0 else None

    def paragraph_bounds(self, paragraph_index):
        for i, (marker_pos, content_pos, pidx) in enumerate(self._paragraph_markers):
            if pidx == int(paragraph_index):
                end = self._paragraph_markers[i + 1][0] if i + 1 < len(self._paragraph_markers) else max(0, self.document().characterCount() - 1)
                return content_pos, end
        return None

    def _visible_occurrences_in_paragraph(self, text, paragraph_index):
        bounds = self.paragraph_bounds(paragraph_index)
        pattern = _rich_selection_pattern(text)
        if not bounds or not pattern:
            return []
        start, end = bounds
        expr = QRegularExpression(pattern)
        occurrences = []
        scan = QTextCursor(self.document())
        scan.setPosition(start)
        while True:
            hit = self.document().find(expr, scan)
            if hit.isNull():
                break
            a, b = hit.selectionStart(), hit.selectionEnd()
            if a >= end:
                break
            if a >= start and b <= end:
                occurrences.append((a, b))
            scan = QTextCursor(self.document())
            scan.setPosition(max(b, a + 1))
        return occurrences

    def selection_descriptor(self, text, selection_start):
        pidx = self.paragraph_for_position(selection_start)
        if pidx is None:
            return None
        occurrences = self._visible_occurrences_in_paragraph(text, pidx)
        occ = occurrence_index_for_position(occurrences, selection_start)
        bounds = self.paragraph_bounds(pidx)
        rel = max(0, int(selection_start) - int(bounds[0])) if bounds else None
        return {"paragraph": pidx, "occurrence": occ, "relative": rel}

    def select_visible_text_in_paragraph(self, text, descriptor, focus=True):
        """Sélectionne ``text`` dans un paragraphe de l'aperçu, à l'occurrence
        décrite par ``descriptor``. ``focus=False`` : le focus reste où il est
        (sélection venue de l'éditeur de fragment)."""
        if not descriptor:
            return False
        pidx = descriptor.get("paragraph")
        occurrences = self._visible_occurrences_in_paragraph(text, pidx)
        bounds = self.paragraph_bounds(pidx)
        target = None
        if bounds and descriptor.get("relative") is not None:
            target = int(bounds[0]) + int(descriptor.get("relative") or 0)
        chosen = choose_occurrence(occurrences, descriptor.get("occurrence"), target)
        if not chosen:
            return False
        a, b = chosen
        self.clearSearchMatch()
        cursor = QTextCursor(self.document())
        cursor.setPosition(a)
        cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        if focus:
            self.setFocus()
        line = self.line_for_position(a)
        if line is not None:
            self.active_line_ordinal = line
        return True

    def line_for_position(self, char_pos):
        if not self._marker_positions:
            return None
        i = bisect.bisect_right(self._marker_positions, int(char_pos)) - 1
        return self._marker_lines[i] if i >= 0 else None

    def line_at_viewport_center(self):
        pos = self.cursorForPosition(self.viewport().rect().center()).position()
        line = self.line_for_position(pos)
        if line is not None:
            self.active_line_ordinal = line
        return line

    def scroll_to_line(self, ordinal, center=True):
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

    def select_visible_text_near_line(self, text, ordinal=None):
        """Sélectionne réellement ``text`` près d'une ligne du témoin de base.

        Contrairement au surlignage de recherche, il s'agit ici d'une sélection
        volontaire de l'utilisateur transférée depuis l'autre onglet. Elle doit
        donc rester une vraie sélection QTextCursor.
        """
        pattern = _rich_selection_pattern(text)
        if not pattern:
            return False
        expr = QRegularExpression(pattern)
        occurrences = []
        scan = QTextCursor(self.document())
        scan.movePosition(QTextCursor.MoveOperation.Start)
        while True:
            hit = self.document().find(expr, scan)
            if hit.isNull():
                break
            a, b = hit.selectionStart(), hit.selectionEnd()
            occurrences.append((a, b))
            scan = QTextCursor(self.document())
            scan.setPosition(max(b, a + 1))
        if not occurrences:
            return False
        target = self.textCursor().position()
        if ordinal is not None:
            target = self._line_to_position.get(int(ordinal), target)
        a, b = min(occurrences, key=lambda ab: abs(ab[0] - target))
        self.clearSearchMatch()
        cursor = QTextCursor(self.document())
        cursor.setPosition(a)
        cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()
        self.setFocus()
        line = self.line_for_position(a)
        if line is not None:
            self.active_line_ordinal = line
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
        # dernier marqueur du témoin de base placé avant la position du curseur.
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


_LXML_TRANSFORM_CACHE = {}

def lxml_available():
    try:
        import lxml.etree  # noqa: F401
        return True
    except Exception:
        return False


def transform_with_xslt(xml_text, xsl_path, params=None, edit_markers=False):
    """Transformation XSLT 1.0 optimisée.

    Avec lxml, la feuille XSLT compilée est mise en cache tant que le fichier
    n'a pas changé ; une erreur de la feuille ou de la transformation est
    signalée telle quelle. Le moteur .NET/PowerShell ne sert que de secours si
    lxml n'est pas installé.

    Avec ``edit_markers`` (V0.9.2.9), la feuille est importée par l'enveloppe
    de ``fragment_units.edit_stylesheet`` : les éléments numérotés par
    ``mark_units`` reçoivent leur crayon ✎, quelle que soit la feuille.
    """
    try:
        from lxml import etree as LET
    except ImportError as exc:
        return _transform_without_lxml(xml_text, xsl_path, params, exc, edit_markers)
    try:
        parser = LET.XMLParser(resolve_entities=False, no_network=True, recover=False)
        xml_doc = LET.fromstring(xml_text.encode("utf-8"), parser=parser)
        xp = Path(xsl_path).resolve()
        st = xp.stat()
        cache_key = (str(xp), st.st_mtime_ns, st.st_size, bool(edit_markers))
        transform = _LXML_TRANSFORM_CACHE.get(cache_key)
        if transform is None:
            # Une seule version compilée par chemin (avec ou sans crayons)
            # suffit ; jeter les anciennes si la feuille a été modifiée sur
            # disque.
            for k in list(_LXML_TRANSFORM_CACHE):
                if k[0] == str(xp) and k[3] == cache_key[3]:
                    _LXML_TRANSFORM_CACHE.pop(k, None)
            if edit_markers:
                xsl_doc = LET.fromstring(edit_stylesheet(xp).encode("utf-8"), parser=parser,
                                         base_url=edit_stylesheet_url(xp))
            else:
                xsl_doc = LET.parse(str(xp), parser=parser)
            # Une feuille peut lire des fichiers locaux (document(), import),
            # mais jamais écrire de fichier, créer de dossier ni accéder au
            # réseau.
            access = LET.XSLTAccessControl(
                read_file=True, write_file=False, create_dir=False,
                read_network=False, write_network=False,
            )
            transform = LET.XSLT(xsl_doc, access_control=access)
            _LXML_TRANSFORM_CACHE[cache_key] = transform
        xslt_params = {str(k): LET.XSLT.strparam(str(v)) for k, v in (params or {}).items()}
        return str(transform(xml_doc, **xslt_params)), "lxml (XSLT en cache)"
    except Exception as exc:
        # Seules les erreurs XSLT ont un journal propre à la transformation ;
        # celui d'une erreur de syntaxe XML est global et contient aussi les
        # erreurs antérieures.
        log = exc.error_log if isinstance(exc, LET.XSLTError) else ()
        raise RuntimeError(_xslt_error_text(exc, xsl_path, log)) from exc


def _transform_without_lxml(xml_text, xsl_path, params, first_error, edit_markers=False):
    """Secours sans lxml : moteur .NET via PowerShell (Windows)."""
    ps = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if ps:
        try:
            with tempfile.TemporaryDirectory(prefix="tei_xslt_") as td:
                td = Path(td)
                if edit_markers:
                    wrapper = td / "varians-edit.xsl"
                    wrapper.write_text(edit_stylesheet(xsl_path), encoding="utf-8")
                    xsl_path = wrapper
                xmlf = td / "edition.xml"
                outf = td / "edition.html"
                psf = td / "transform.ps1"
                xmlf.write_text(xml_text, encoding="utf-8")
                psf.write_text(
                    'param([string]$xml,[string]$xsl,[string]$out,[string]$baseWitness,[string]$tocTitle)\n'
                    '$tr = New-Object System.Xml.Xsl.XslCompiledTransform\n'
                    '$settings = New-Object System.Xml.Xsl.XsltSettings($false,$false)\n'
                    '$resolver = New-Object System.Xml.XmlUrlResolver\n'
                    '$tr.Load($xsl,$settings,$resolver)\n'
                    '$args = New-Object System.Xml.Xsl.XsltArgumentList\n'
                    'if ($baseWitness) { $args.AddParam("baseWitness", "", $baseWitness) }\n'
                    'if ($tocTitle) { $args.AddParam("tocTitle", "", $tocTitle) }\n'
                    '$writer = [System.Xml.XmlWriter]::Create($out, $tr.OutputSettings)\n'
                    'try { $tr.Transform($xml,$args,$writer,$resolver) } finally { $writer.Close() }\n',
                    encoding="utf-8",
                )
                proc = subprocess.run(
                    [ps, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(psf),
                     str(xmlf), str(xsl_path), str(outf), str((params or {}).get("baseWitness", "")), str((params or {}).get("tocTitle", ""))],
                    capture_output=True, text=True, timeout=30,
                )
                if proc.returncode != 0 or not outf.exists():
                    raise RuntimeError((proc.stderr or proc.stdout or _t("xslt.error.powershell")).strip())
                return outf.read_text(encoding="utf-8", errors="replace"), "PowerShell/.NET"
        except Exception as exc:
            raise RuntimeError(
                _t("xslt.error.generic", lxml=first_error, powershell=exc)
            ) from exc

    raise RuntimeError(
        _t("xslt.error.install", error=first_error)
    )


class FormattedEditionWidget(QWidget):
    """Vue XSLT/CSS + édition sûre du fragment TEI correspondant au paragraphe choisi."""

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main = main_window
        self.xsl_path = self.main.project.xslt
        self.css_path = self.main.project.css
        self.current_paragraph = None
        self.fragment_original = ""
        # Document (édition ou partie) dont vient le fragment ouvert, et
        # nombre de paragraphes de l'aperçu à son ouverture.
        self.fragment_session = None
        self._fragment_total = 0
        self.dirty_preview = True
        self._last_preview_key = None
        # Édition en parties (V0.9.1.5) : fichier et place de chaque
        # paragraphe et repère de ligne de l'aperçu (preview_sources).
        self.sources = None
        # Noms des éléments modifiables de l'aperçu affiché (V0.9.2.9),
        # relevés à son actualisation : le crayon, F2, le fragment et les
        # reports de sélection s'y tiennent jusqu'à la suivante.
        self.unit_names = None
        self._cached_css_key = None
        self._cached_css_text = None
        self._last_preview_engine = None

        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(5)

        top = QHBoxLayout()
        self.xsl_label = QLabel(self.xsl_path.name)
        self.xsl_label.setToolTip(
            _t("project.xslt.mode.builtin" if self.main.project.xslt_mode == "builtin"
               else "project.xslt.mode.file") + "\n" + str(self.xsl_path)
        )
        self.css_label = QLabel(self.css_path.name)
        self.xsl_btn = QPushButton("XSLT…")
        self.css_btn = QPushButton("CSS…")
        self.refresh_btn = QPushButton(_t("preview.refresh"))
        self.auto_check = QCheckBox(_t("preview.auto"))
        self.auto_check.setChecked(True)
        self.font_minus_btn = QPushButton("A−")
        self.font_reset_btn = QPushButton("100 %")
        self.font_plus_btn = QPushButton("A+")
        self.font_minus_btn.setToolTip(_t("preview.font_minus.tip"))
        self.font_reset_btn.setToolTip(_t("preview.font_reset.tip"))
        self.font_plus_btn.setToolTip(_t("preview.font_plus.tip"))
        self.formatting_label = QLabel(_t("preview.formatting"))
        top.addWidget(self.formatting_label)
        top.addWidget(self.xsl_label)
        top.addWidget(self.xsl_btn)
        top.addWidget(QLabel("+"))
        top.addWidget(self.css_label)
        top.addWidget(self.css_btn)
        top.addWidget(self.refresh_btn)
        top.addWidget(self.auto_check)
        top.addSpacing(8)
        self.preview_size_label = QLabel(_t("preview.size"))
        top.addWidget(self.preview_size_label)
        top.addWidget(self.font_minus_btn)
        top.addWidget(self.font_reset_btn)
        top.addWidget(self.font_plus_btn)
        top.addStretch(1)
        root.addLayout(top)

        # Recherche contextuelle dans l'aperçu XSLT/CSS. Ctrl+F depuis cet
        # onglet ouvre cette barre au lieu de basculer vers la source XML.
        self.preview_find_bar = QWidget()
        pf = QHBoxLayout(self.preview_find_bar)
        pf.setContentsMargins(0, 0, 0, 2)
        pf.setSpacing(5)
        self.preview_find_label = QLabel(_t("preview.search.label"))
        pf.addWidget(self.preview_find_label)
        self.preview_find_box = QLineEdit()
        self.preview_find_box.setClearButtonEnabled(True)
        self.preview_find_box.setPlaceholderText(_t("preview.search.placeholder"))
        self.preview_find_status = QLabel("")
        self.preview_find_status.setMinimumWidth(54)
        self.preview_find_prev_btn = QPushButton("◀")
        self.preview_find_next_btn = QPushButton("▶")
        self.preview_find_close_btn = QPushButton("✕")
        self.preview_find_prev_btn.clicked.connect(self.find_preview_previous)
        self.preview_find_next_btn.clicked.connect(self.find_preview_next)
        self.preview_find_close_btn.clicked.connect(self.hide_preview_find)
        self.preview_find_box.returnPressed.connect(self.find_preview_next)
        pf.addWidget(self.preview_find_box, 1)
        pf.addWidget(self.preview_find_status)
        pf.addWidget(self.preview_find_prev_btn)
        pf.addWidget(self.preview_find_next_btn)
        pf.addWidget(self.preview_find_close_btn)
        self.preview_find_bar.setVisible(False)
        root.addWidget(self.preview_find_bar)

        # preview_zoom_steps = taille souhaitée par l’utilisateur ;
        # _preview_applied_zoom_steps = zoom effectivement appliqué au QTextBrowser.
        # Les séparer évite les doubles applications lors d’un setHtml().
        self.preview_zoom_steps = 0
        self._preview_applied_zoom_steps = 0
        self.preview = ClickablePreview()
        self.preview.setOpenLinks(False)
        self.preview.setOpenExternalLinks(False)
        self.preview.setMinimumHeight(300)
        self.preview.anchorClicked.connect(self._anchor_clicked)
        self.preview.lineActivated.connect(self._line_clicked)
        self.preview.textSelected.connect(self._preview_selection_to_fragment)
        # F2 : ouvre dans l'éditeur de fragment le paragraphe de la sélection
        # (ou du curseur) de l'aperçu, la sélection reportée.
        self.edit_paragraph_action = QAction(_t("preview.edit_paragraph"), self.preview)
        self.edit_paragraph_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
        self.edit_paragraph_action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        self.edit_paragraph_action.triggered.connect(self.edit_selected_paragraph)
        self.preview.addAction(self.edit_paragraph_action)

        frag_box = QWidget()
        self.frag_box = frag_box
        frag_layout = QVBoxLayout(frag_box)
        frag_layout.setContentsMargins(0, 4, 0, 0)
        frag_head = QHBoxLayout()
        self.frag_label = QLabel(_t("fragment.initial"))
        # L'étiquette nomme l'élément ouvert (« <p> ») : jamais du HTML.
        self.frag_label.setTextFormat(Qt.TextFormat.PlainText)
        self.fragment_visual_wrap = QCheckBox(_t("source.visual_wrap"), frag_box)
        _fragment_wrap_setting = _settings().value(
            "fragmentVisualWrap", _settings().value("sourceVisualWrap", False)
        )
        if isinstance(_fragment_wrap_setting, str):
            _fragment_wrap_setting = _fragment_wrap_setting.strip().lower() in {"1", "true", "yes", "on"}
        self.fragment_visual_wrap.setChecked(bool(_fragment_wrap_setting))
        self.apply_btn = QPushButton(_t("fragment.apply_xml"))
        self.reload_btn = QPushButton(_t("fragment.reload"))
        self.close_fragment_btn = QPushButton(_t("fragment.close"))
        self.close_fragment_btn.setToolTip(_t("fragment.close.tip"))
        self.apply_btn.setEnabled(False)
        self.reload_btn.setEnabled(False)
        frag_head.addWidget(self.frag_label)
        frag_head.addSpacing(12)
        # Faute de place, la case cède la sienne : l'étiquette du fragment
        # (paragraphe, fichier d'une partie) reste lisible en entier.
        self.fragment_visual_wrap.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.fragment_visual_wrap.setMinimumWidth(24)
        frag_head.addWidget(self.fragment_visual_wrap, 1)
        frag_head.addWidget(self.reload_btn)
        frag_head.addWidget(self.apply_btn)
        frag_head.addWidget(self.close_fragment_btn)
        frag_layout.addLayout(frag_head)

        # Barre de recherche locale au fragment. Elle apparaît avec Ctrl+F
        # lorsque le focus est dans l’éditeur de paragraphe.
        self.fragment_find_bar = QWidget()
        ff = QHBoxLayout(self.fragment_find_bar)
        self._fragment_find_layout = ff
        ff.setContentsMargins(0, 0, 0, 2)
        ff.setSpacing(5)
        self.fragment_find_label = QLabel(_t("fragment.search.label"))
        ff.addWidget(self.fragment_find_label)
        self.fragment_find_box = QLineEdit()
        self.fragment_find_box.setClearButtonEnabled(True)
        self.fragment_find_box.setPlaceholderText(_t("fragment.search.placeholder"))
        self.fragment_find_box.returnPressed.connect(self.find_fragment_next)
        self.fragment_find_prev_btn = QPushButton("◀")
        self.fragment_find_next_btn = QPushButton("▶")
        self.fragment_find_close_btn = QPushButton("×")
        self.fragment_find_prev_btn.setToolTip(_t("fragment.search.prev.tip"))
        self.fragment_find_next_btn.setToolTip(_t("fragment.search.next.tip"))
        self.fragment_find_close_btn.setToolTip(_t("fragment.search.close.tip"))
        self.fragment_find_prev_btn.clicked.connect(self.find_fragment_previous)
        self.fragment_find_next_btn.clicked.connect(self.find_fragment_next)
        self.fragment_find_close_btn.clicked.connect(self.hide_fragment_find)
        self.fragment_find_status = QLabel("")
        self.fragment_find_status.setMinimumWidth(54)
        ff.addWidget(self.fragment_find_box, 1)
        ff.addWidget(self.fragment_find_status)
        ff.addWidget(self.fragment_find_prev_btn)
        ff.addWidget(self.fragment_find_next_btn)
        ff.addWidget(self.fragment_find_close_btn)
        self.fragment_find_bar.setVisible(False)
        frag_layout.addWidget(self.fragment_find_bar)
        # Ligne « Remplacer par » (Ctrl+H, V0.9.2.8), sous la recherche.
        self.fragment_replace_row = QWidget()
        fr = QHBoxLayout(self.fragment_replace_row)
        fr.setContentsMargins(0, 0, 0, 2)
        fr.setSpacing(5)
        self.fragment_replace_label = QLabel(_t("replace.with.label"))
        self.fragment_replace_box = QLineEdit()
        self.fragment_replace_box.setClearButtonEnabled(True)
        self.fragment_replace_box.returnPressed.connect(self.replace_fragment_next)
        self.fragment_replace_one_button = QPushButton(_t("replace.one"))
        self.fragment_replace_all_button = QPushButton(_t("replace.all"))
        self.fragment_replace_one_button.clicked.connect(self.replace_fragment_next)
        self.fragment_replace_all_button.clicked.connect(self.replace_fragment_all)
        fr.addWidget(self.fragment_replace_label)
        fr.addWidget(self.fragment_replace_box, 1)
        fr.addWidget(self.fragment_replace_one_button)
        fr.addWidget(self.fragment_replace_all_button)
        self.fragment_replace_row.setVisible(False)
        frag_layout.addWidget(self.fragment_replace_row)

        self.fragment_editor = CodeEditor()
        self.fragment_editor.setMaximumHeight(235)
        self.fragment_editor.setPlaceholderText(_t("fragment.placeholder"))
        # Même retour à la ligne purement visuel que dans XML source. Le choix
        # du fragment est mémorisé séparément ; lors de la première utilisation,
        # il hérite de la préférence de la source XML.
        self.fragment_editor.set_visual_wrap(bool(_fragment_wrap_setting))
        self.fragment_visual_wrap.toggled.connect(self._set_fragment_visual_wrap)

        # Ctrl+E entoure la sélection (en la conservant) ou insère un élément
        # vide si aucune sélection n'est active. Le raccourci est attaché
        # uniquement à l'éditeur de fragment pour ne pas interférer avec les
        # autres vues de l'application.
        self.wrap_element_action = QAction(_t("fragment.wrap"), self.fragment_editor)
        self.wrap_element_action.setShortcut(QKeySequence("Ctrl+E"))
        self.wrap_element_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.wrap_element_action.triggered.connect(lambda: self.wrap_selection_with_element(self.fragment_editor, _t("ctrl_e.where.fragment")))
        self.fragment_editor.addAction(self.wrap_element_action)

        # Ctrl+Espace : complétion contextuelle pilotée par le RNG actif.
        self.fragment_completion_action = QAction(_t("completion.action"), self.fragment_editor)
        self.fragment_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.fragment_completion_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.fragment_completion_action.triggered.connect(
            lambda: self.main.show_rng_completion(self.fragment_editor)
        )
        self.fragment_editor.addAction(self.fragment_completion_action)

        # Une sélection faite dans le fragment est aussi sélectionnée dans
        # l'aperçu, après une courte pause (pas à chaque pas d'un glisser).
        self._fragment_selection_timer = QTimer(self)
        self._fragment_selection_timer.setSingleShot(True)
        self._fragment_selection_timer.setInterval(150)
        self._fragment_selection_timer.timeout.connect(self._fragment_selection_to_preview)
        self.fragment_editor.selectionChanged.connect(self._fragment_selection_timer.start)

        frag_layout.addWidget(self.fragment_editor)

        # L’éditeur de fragment reste masqué tant qu’aucun paragraphe n’est ouvert.
        frag_box.setVisible(False)

        split = QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.preview)
        split.addWidget(frag_box)
        split.setSizes([620, 260])
        root.addWidget(split, 1)

        self.info = QLabel(_t("preview.info.default"))
        self.info.setWordWrap(True)
        self.info.setStyleSheet("color:#746b61")
        root.addWidget(self.info)

        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        # Évite une retransformation de toute l'édition après chaque petite pause
        # de frappe. Le moteur PowerShell de secours est plus coûteux que lxml.
        self.preview_timer.setInterval(1800 if lxml_available() else 3200)
        self.preview_timer.timeout.connect(self.refresh_preview)
        self.xsl_btn.clicked.connect(self.choose_xslt)
        self.css_btn.clicked.connect(self.choose_css)
        self.refresh_btn.clicked.connect(self.refresh_preview)
        self.apply_btn.clicked.connect(self.apply_fragment)
        self.reload_btn.clicked.connect(self.reload_fragment)
        self.close_fragment_btn.clicked.connect(self.close_fragment_editor)
        self.auto_check.toggled.connect(self._auto_toggled)
        self.font_minus_btn.clicked.connect(lambda: self._change_preview_zoom(-1))
        self.font_reset_btn.clicked.connect(self._reset_preview_zoom)
        self.font_plus_btn.clicked.connect(lambda: self._change_preview_zoom(1))

    def _set_fragment_visual_wrap(self, enabled):
        """Retour à la ligne visuel du fragment, sans modifier le XML."""
        self.fragment_editor.set_visual_wrap(bool(enabled))
        _settings().setValue("fragmentVisualWrap", bool(enabled))

    def retranslate_ui(self):
        self.refresh_btn.setText(_t("preview.refresh"))
        self.auto_check.setText(_t("preview.auto"))
        self.font_minus_btn.setToolTip(_t("preview.font_minus.tip"))
        self.font_reset_btn.setToolTip(_t("preview.font_reset.tip"))
        self.font_plus_btn.setToolTip(_t("preview.font_plus.tip"))
        self.formatting_label.setText(_t("preview.formatting"))
        self.preview_size_label.setText(_t("preview.size"))
        self.preview_find_label.setText(_t("preview.search.label"))
        self.preview_find_box.setPlaceholderText(_t("preview.search.placeholder"))
        self.apply_btn.setText(_t("fragment.apply_xml"))
        self.reload_btn.setText(_t("fragment.reload"))
        self.close_fragment_btn.setText(_t("fragment.close"))
        self.close_fragment_btn.setToolTip(_t("fragment.close.tip"))
        self.fragment_find_label.setText(_t("fragment.search.label"))
        self.fragment_find_box.setPlaceholderText(_t("fragment.search.placeholder"))
        self.fragment_find_prev_btn.setToolTip(_t("fragment.search.prev.tip"))
        self.fragment_find_next_btn.setToolTip(_t("fragment.search.next.tip"))
        self.fragment_find_close_btn.setToolTip(_t("fragment.search.close.tip"))
        self.fragment_replace_label.setText(_t("replace.with.label"))
        self.fragment_replace_one_button.setText(_t("replace.one"))
        self.fragment_replace_all_button.setText(_t("replace.all"))
        self.fragment_editor.setPlaceholderText(_t("fragment.placeholder"))
        self.fragment_visual_wrap.setText(_t("source.visual_wrap"))
        self.fragment_visual_wrap.setToolTip(_t("source.visual_wrap"))
        self.wrap_element_action.setText(_t("fragment.wrap"))
        self.fragment_completion_action.setText(_t("completion.action"))
        self._update_fragment_label()
        self.info.setText(_t("preview.info.default"))
        # The transformed preview contains localized XSLT chrome (e.g. Contents).
        self.dirty_preview = True
        self._last_preview_key = None
        self.refresh_preview(force=True)

    def focus_is_in_preview(self):
        focus = QApplication.focusWidget()
        return bool(
            focus is self.preview
            or (focus is not None and self.preview.isAncestorOf(focus))
            or focus is self.preview_find_box
            or (focus is not None and self.preview_find_bar.isAncestorOf(focus))
        )

    def show_preview_find(self):
        self.preview_find_bar.setVisible(True)
        selected = self.preview.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.preview_find_box.setText(selected)
        self.preview_find_box.setFocus()
        self.preview_find_box.selectAll()

    def hide_preview_find(self):
        self.preview_find_bar.setVisible(False)
        self.preview_find_status.setText("")
        self.preview.clearSearchMatch()
        self.preview.setFocus()

    def _find_preview(self, backwards=False):
        q = self.preview_find_box.text()
        if not q:
            self.show_preview_find()
            return
        found, n, total = find_in_rich_editor(self.preview, q, backwards=backwards)
        if found:
            self.preview_find_status.setText(f"{n}/{total}")
            self.preview_find_status.setStyleSheet("color:#5f574f")
            match = getattr(self.preview, "_search_match", None)
            pos = match[0] if match else self.preview.textCursor().position()
            line = self.preview.line_for_position(pos)
            if line is not None:
                self.preview.active_line_ordinal = line
                # Rester dans l'onglet XSLT tout en synchronisant XML et images.
                self._activate_line(line, move_xml_cursor=True)
            self.info.setText(_t("preview.search.found", n=n, total=total, query=q))
            self.info.setStyleSheet("color:#376b3c")
        else:
            self.preview_find_status.setText("0/0")
            self.preview_find_status.setStyleSheet("color:#a13d32;font-weight:600")
            self.info.setText(_t("preview.search.none", query=q))
            self.info.setStyleSheet("color:#a13d32")
        # Éviter que le bouton Suivant/Précédent conserve le focus clavier.
        self.preview_find_box.setFocus()

    def find_preview_next(self):
        self._find_preview(False)

    def find_preview_previous(self):
        self._find_preview(True)

    def current_preview_line(self):
        # Pour une transition d'onglet, la ligne au centre de la fenêtre reflète
        # mieux la position de lecture qu'une ancienne sélection.
        line = self.preview.line_at_viewport_center()
        return line if line is not None else self.preview.active_line_ordinal

    def scroll_to_t1_line(self, ordinal):
        if ordinal is None:
            return
        if self.dirty_preview:
            self.refresh_preview()
        call_later(0, self, lambda n=int(ordinal): self.preview.scroll_to_line(n, center=True))

    def focus_is_in_fragment(self):
        focus = QApplication.focusWidget()
        return bool(
            focus is self.fragment_editor
            or (focus is not None and self.fragment_editor.isAncestorOf(focus))
            or focus is self.fragment_find_box
            or (focus is not None and self.fragment_find_bar.isAncestorOf(focus))
            or (focus is not None and self.fragment_replace_row.isAncestorOf(focus))
        )

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
        suggestion_pos = cursor.selectionStart() if has_selection else cursor.position()
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
        # Qt représente les fins de paragraphes par U+2029/U+2028 : les
        # restituer en LF conserve exactement le XML multiligne sélectionné.
        selected = cursor.selectedText().replace("\u2029", "\n").replace("\u2028", "\n")
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

    def show_fragment_find(self, replace=False):
        # Ctrl+F : la recherche seule ; Ctrl+H (replace) : avec « Remplacer par ».
        self.fragment_find_bar.setVisible(True)
        self.fragment_replace_row.setVisible(bool(replace))
        # Si du texte est sélectionné, il devient naturellement la recherche.
        selected = self.fragment_editor.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.fragment_find_box.setText(selected)
        self.fragment_find_box.setFocus()
        self.fragment_find_box.selectAll()

    def add_fragment_find_options(self, actions):
        """Boutons des options de recherche de la fenêtre (« Aa », « .* »),
        après le champ de recherche du fragment (V0.9.2.8)."""
        layout = self._fragment_find_layout
        index = layout.indexOf(self.fragment_find_box) + 1
        for offset, action in enumerate(actions):
            button = QToolButton(self.fragment_find_bar)
            button.setDefaultAction(action)
            button.setAutoRaise(True)
            layout.insertWidget(index + offset, button)

    def hide_fragment_find(self):
        self.fragment_find_bar.setVisible(False)
        self.fragment_replace_row.setVisible(False)
        self.fragment_find_status.setText("")
        self.fragment_editor.setFocus()

    def _find_fragment(self, backwards=False):
        q = self.fragment_find_box.text()
        if not q:
            self.show_fragment_find()
            return
        try:
            # Avec la ligne « Remplacer par », le texte cherché est pris tel quel.
            found, n, total = find_in_plain_editor(self.fragment_editor, q, backwards=backwards,
                                                   options=self.main.search_options(),
                                                   exact=not self.fragment_replace_row.isHidden())
        except SearchError as error:
            self._fragment_search_error(error)
            self.fragment_find_box.setFocus()
            return
        if found:
            self.fragment_find_status.setText(f"{n}/{total}")
            self.fragment_find_status.setStyleSheet("color:#5f574f")
        else:
            self.fragment_find_status.setText("0/0")
            self.fragment_find_status.setStyleSheet("color:#a13d32;font-weight:600")
        # Même protection pour l'éditeur de fragment (il est lui aussi éditable).
        self.fragment_find_box.setFocus()

    def find_fragment_next(self):
        self._find_fragment(False)

    def replace_fragment_next(self):
        query = self.fragment_find_box.text()
        if not query:
            self.fragment_find_box.setFocus()
            return
        try:
            _replaced, (found, n, total) = replace_in_plain_editor(
                self.fragment_editor, query, self.fragment_replace_box.text(), self.main.search_options())
        except SearchError as error:
            self._fragment_search_error(error)
            return
        self.fragment_find_status.setText(f"{n}/{total}" if found else "0/0")

    def replace_fragment_all(self):
        query = self.fragment_find_box.text()
        if not query:
            self.fragment_find_box.setFocus()
            return
        try:
            count = replace_all_in_plain_editor(
                self.fragment_editor, query, self.fragment_replace_box.text(), self.main.search_options())
        except SearchError as error:
            self._fragment_search_error(error)
            return
        self.fragment_find_status.setText("")
        self.main.statusBar().showMessage(_t("replace.done", count=count), 5000)

    def _fragment_search_error(self, error):
        self.fragment_find_status.setText("!")
        self.fragment_find_status.setStyleSheet("color:#a13d32;font-weight:600")
        self.main.statusBar().showMessage(search_error_text(error), 5000)

    def find_fragment_previous(self):
        self._find_fragment(True)

    def _preview_zoom_label(self):
        # L’API Qt travaille en crans typographiques, pas en vrais pourcentages.
        # On conserve une échelle utilisateur simple de 10 % par cran, mais l’état
        # appliqué est désormais absolu et non cumulatif.
        return f"{100 + self.preview_zoom_steps * 10} %"

    def _apply_preview_zoom_state(self):
        """Applique uniquement l’écart entre le zoom désiré et le zoom réel."""
        diff = self.preview_zoom_steps - self._preview_applied_zoom_steps
        if diff > 0:
            self.preview.zoomIn(diff)
        elif diff < 0:
            self.preview.zoomOut(-diff)
        self._preview_applied_zoom_steps = self.preview_zoom_steps
        self.font_reset_btn.setText(self._preview_zoom_label())

    def _normalize_preview_zoom_before_reload(self):
        """Ramène réellement le QTextBrowser à sa base avant de remplacer son HTML."""
        applied = self._preview_applied_zoom_steps
        if applied > 0:
            self.preview.zoomOut(applied)
        elif applied < 0:
            self.preview.zoomIn(-applied)
        self._preview_applied_zoom_steps = 0

    def _change_preview_zoom(self, delta):
        anchor_line = self.current_preview_line()
        self.preview_zoom_steps = max(-6, min(12, self.preview_zoom_steps + delta))
        self._apply_preview_zoom_state()
        if anchor_line is not None:
            call_later(0, self, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

    def _reset_preview_zoom(self):
        anchor_line = self.current_preview_line()
        self.preview_zoom_steps = 0
        self._apply_preview_zoom_state()
        if anchor_line is not None:
            call_later(0, self, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

    def _reapply_preview_zoom(self):
        self._apply_preview_zoom_state()

    def _auto_toggled(self, checked):
        if checked and self.dirty_preview:
            self.preview_timer.start()

    def source_changed(self):
        self.dirty_preview = True
        # start() redémarre le timer : une saisie continue ne déclenche donc pas
        # de transformation intermédiaire. On attend une vraie pause de frappe.
        if self.auto_check.isChecked() and self.isVisible():
            self.preview_timer.start()

    def became_visible(self):
        if self.dirty_preview:
            self.refresh_preview()

    def choose_xslt(self):
        fn, _ = QFileDialog.getOpenFileName(self, _t("preview.choose_xslt"), str(self.xsl_path.parent), f"XSLT (*.xsl *.xslt);;{_t('common.all_files')} (*)")
        if fn:
            self.xsl_path = Path(fn)
            self.xsl_label.setText(self.xsl_path.name)
            self.dirty_preview = True
            self.refresh_preview(force=True)

    def choose_css(self):
        fn, _ = QFileDialog.getOpenFileName(self, _t("preview.choose_css"), str(self.css_path.parent), f"CSS (*.css);;{_t('common.all_files')} (*)")
        if fn:
            self.css_path = Path(fn)
            self.css_label.setText(self.css_path.name)
            self.dirty_preview = True
            self.refresh_preview(force=True)

    def _file_signature(self, path):
        try:
            st = Path(path).stat()
            return (str(Path(path).resolve()), st.st_mtime_ns, st.st_size)
        except OSError:
            return (str(path), None, None)

    def _resolved_css_cached(self):
        key = self._file_signature(self.css_path)
        if key != self._cached_css_key or self._cached_css_text is None:
            css = PREVIEW_BASE_CSS + resolve_css_variables(self.css_path.read_text(encoding="utf-8"))
            self._cached_css_key = key
            self._cached_css_text = css
        return self._cached_css_text

    def refresh_preview(self, force=False):
        # Édition en parties (XInclude) : l'aperçu montre l'édition assemblée,
        # quel que soit le document affiché ; ses éléments modifiables et ses
        # lignes restent rattachés à leur fichier (V0.9.1.5). Chaque élément
        # modifiable porte son rang (vx:edit), celui de son crayon ✎.
        names = self.main.fragment_unit_names()
        if self.main._edition_has_parts():
            self.sources = self.main._assembled_preview_sources(names)
            xml_text = (self.sources.text if self.sources is not None
                        else self.main.edition_session.text_document.toPlainText())
            spans = self.sources.paragraphs if self.sources is not None else ()
        else:
            self.sources = None
            xml_text, spans = mark_units(self.main.editor.toPlainText(), names)
        if not self.xsl_path.exists() or not self.css_path.exists():
            self.info.setText(_t("preview.files_missing"))
            self.info.setStyleSheet("color:#a14b2f")
            return

        # Empreinte légère : évite de reconstruire le gros QTextDocument quand
        # rien n'a changé (clic sur Actualiser, changement d'onglet, etc.).
        xml_digest = hashlib.blake2b(xml_text.encode("utf-8"), digest_size=12).hexdigest()
        preview_key = (xml_digest, self._file_signature(self.xsl_path), self._file_signature(self.css_path), names)
        if not force and preview_key == self._last_preview_key:
            self.dirty_preview = False
            engine = self._last_preview_engine or "cache"
            self.info.setText(_t("preview.up_to_date", engine=engine))
            self.info.setStyleSheet("color:#376b3c")
            return

        try:
            ET.fromstring(xml_text)
        except ET.ParseError as exc:
            self.info.setText(_t("preview.xml_invalid", error=exc))
            self.info.setStyleSheet("color:#a14b2f")
            return

        # Conserver une ancre sémantique plutôt qu’une simple valeur de scrollbar.
        # Une modification de fragment peut changer la hauteur/recomposition du HTML :
        # restaurer le même nombre de pixels ne ramène alors plus au même passage.
        old_anchor_line = self.preview.line_at_viewport_center()
        if old_anchor_line is None:
            old_anchor_line = self.preview.active_line_ordinal
        old_bar = self.preview.verticalScrollBar()
        old_ratio = (old_bar.value() / old_bar.maximum()) if old_bar.maximum() > 0 else 0.0
        t0 = time.perf_counter()
        try:
            html_text, engine = transform_with_xslt(
                xml_text, self.xsl_path, {"baseWitness": self.main.base_id, "tocTitle": _t("preview.toc")},
                edit_markers=True)
            html_text, clickable_lines, text_links = make_line_segments_clickable(html_text)
            html_text, marked = place_edit_markers(html_text, _t("preview.edit_paragraph"))
            css = self._resolved_css_cached()

            # setHtml() et zoomIn()/zoomOut() n’ont pas des sémantiques identiques
            # selon la nature des tailles CSS. Remettre explicitement le widget à
            # sa base avant reconstruction rend le résultat déterministe.
            self._normalize_preview_zoom_before_reload()
            self.preview.document().setDefaultStyleSheet(css)
            self.preview.setHtml(html_text)
            self.preview.rebuild_line_markers()
            self.unit_names = names
            self._preview_applied_zoom_steps = 0
            self._reapply_preview_zoom()

            def restore_preview_position(line=old_anchor_line, ratio=old_ratio):
                if line is not None and self.preview.scroll_to_line(int(line), center=True):
                    return
                bar = self.preview.verticalScrollBar()
                if bar.maximum() > 0:
                    bar.setValue(int(round(ratio * bar.maximum())))

            call_later(0, self, restore_preview_position)
            self.dirty_preview = False
            self._last_preview_key = preview_key
            self._last_preview_engine = engine
            elapsed = time.perf_counter() - t0
            if clickable_lines:
                self.info.setText(_t("preview.updated.timed.lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked, paragraphs=len(spans), lines=clickable_lines))
                self.info.setStyleSheet("color:#376b3c")
            else:
                self.info.setText(_t("preview.updated.timed.no_lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked, paragraphs=len(spans)))
                self.info.setStyleSheet("color:#9a6a2f")
        except Exception as exc:
            self.info.setText(_t("preview.transform_error", error=exc))
            self.info.setStyleSheet("color:#a13d32")

    def _activate_line(self, idx, move_xml_cursor=True):
        """Repère de ligne ``idx`` de l'aperçu : le curseur de la source et les
        témoins y vont. Dans une édition assemblée, par la place de ce
        repère dans son fichier (V0.9.1.5) : la numérotation des textes
        synchronisés à part est ainsi respectée."""
        if self.sources is not None:
            self.main.navigate_to_preview_line(int(idx))
        else:
            self.main.navigate_to_base_ordinal(idx, move_xml_cursor=move_xml_cursor)

    def _line_clicked(self, idx):
        self.preview.active_line_ordinal = int(idx)
        self._activate_line(idx, move_xml_cursor=True)
        self.info.setText(_t("preview.base_selected", line=idx+1))
        self.info.setStyleSheet("color:#376b3c")

    def _anchor_clicked(self, url):
        if url.scheme() == "tei-line":
            try:
                idx = int(url.path().strip("/"))
            except Exception:
                return
            self._line_clicked(idx)
            return
        if url.scheme() == "tei-toc":
            anchor = url.path().strip("/") or url.host()
            if not anchor:
                return
            self.preview.scrollToAnchor(anchor)

            # Après le saut, synchroniser aussi les trois manuscrits sur la
            # ligne du témoin de base située au centre du passage atteint, sans quitter l’aperçu.
            def sync_after_toc():
                line = self.preview.line_at_viewport_center()
                if line is not None:
                    self.preview.active_line_ordinal = int(line)
                    self._activate_line(int(line), move_xml_cursor=False)
            call_later(0, self, sync_after_toc)
            return
        if url.scheme() != "tei-edit":
            return
        try:
            idx = int(url.path().strip("/"))
        except Exception:
            return
        # Le crayon ouvre seulement le paragraphe : la source et les témoins
        # restent où ils sont (seul un clic sur le texte les déplace). La
        # sélection en cours, effacée par le clic, est rétablie.
        self._edit_paragraph(idx, self.preview.take_selection_before_pencil())

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
        return self.unit_names or self.main.fragment_unit_names()

    def _fragment_source(self, idx):
        """L'élément modifiable de rang ``idx`` de l'aperçu (V0.9.2.9 ;
        auparavant le ``<p>``) dans son fichier : ``(session, texte, début,
        fin, nombre d'éléments)``, ou None.

        Pour une édition en parties (V0.9.1.5), le fichier est celui qui
        contient l'élément, édition ou partie, lu au besoin sans être
        affiché ; sinon, c'est le document affiché."""
        main = self.main
        if not main._edition_has_parts():
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
        if self.main._edition_has_parts() and self.fragment_session is not None:
            self.frag_label.setText(_t("fragment.label.file", element=element, index=self.current_paragraph + 1,
                                       total=self._fragment_total, file=Path(self.fragment_session.path).name))
        else:
            self.frag_label.setText(_t("fragment.label", element=element, index=self.current_paragraph + 1,
                                       total=self._fragment_total))

    def load_fragment(self, idx):
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
        if self.current_paragraph is not None:
            self.load_fragment(self.current_paragraph)

    def fragment_has_unapplied_changes(self):
        return (
            self.current_paragraph is not None
            and self.fragment_editor.toPlainText() != self.fragment_original
        )

    def _preview_selection_to_fragment(self):
        """Une sélection faite dans l'aperçu est aussi sélectionnée dans
        l'éditeur de fragment, qui prend le focus, si elle commence dans le
        paragraphe ouvert. La même occurrence est cherchée dans le texte
        actuel du fragment, même modifié."""
        if self.current_paragraph is None or self.frag_box.isHidden():
            return False
        cursor = self.preview.textCursor()
        text = cursor.selectedText().replace("⁠", "")
        if not text.strip():
            return False
        descriptor = self.preview.selection_descriptor(text, cursor.selectionStart())
        if not descriptor or descriptor.get("paragraph") != self.current_paragraph:
            return False
        chosen = pick_xml_occurrence(self.fragment_editor.toPlainText(), text, descriptor)
        if not chosen:
            return False
        selection = QTextCursor(self.fragment_editor.document())
        selection.setPosition(chosen[0])
        selection.setPosition(chosen[1], QTextCursor.MoveMode.KeepAnchor)
        self.fragment_editor.setTextCursor(selection)
        # La sélection vient de l'aperçu : elle n'y est pas renvoyée.
        self._fragment_selection_timer.stop()
        self.fragment_editor.centerCursor()
        self.fragment_editor.setFocus()
        return True

    def _fragment_selection_to_preview(self):
        """Une sélection faite dans l'éditeur de fragment est aussi
        sélectionnée dans l'aperçu, qui défile jusqu'à elle ; le focus reste
        dans le fragment. Une sélection faite seulement de balises, ou un
        texte absent de l'aperçu (tapé, pas encore appliqué), n'y change rien."""
        if self.current_paragraph is None or self.frag_box.isHidden():
            return False
        cursor = self.fragment_editor.textCursor()
        if not cursor.hasSelection():
            return False
        text = _selection_xml_to_visible_text(cursor.selectedText())
        if not text:
            return False
        descriptor = xml_selection_descriptor(self.fragment_editor.toPlainText(), text, cursor.selectionStart())
        descriptor["paragraph"] = self.current_paragraph
        return self.preview.select_visible_text_in_paragraph(text, descriptor, focus=False)

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
            c = QTextCursor(self.main.editor.document())
            c.setPosition(start)
            c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
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

