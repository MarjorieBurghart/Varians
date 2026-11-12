# -*- coding: utf-8 -*-
"""Vue XSLT / CSS : aperçu mis en forme du document affiché (l'édition ou un
document XML du projet), synchronisé avec la source, et édition par
fragments. Chaque document a la vue du projet et ses vues nommées
(project.xml, ``<view>``), choisies dans une liste (V0.9.4.4)."""
from __future__ import annotations

import bisect
import hashlib
import html as html_lib
import json
import re
import shutil
import subprocess
import tempfile
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor

from pathlib import Path

from PySide6.QtCore import QRegularExpression, Qt, QTimer, Signal
from PySide6.QtGui import QAction, QColor, QKeySequence, QTextCursor
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QDialog, QHBoxLayout, QInputDialog, QLabel,
    QLineEdit, QMenu, QMessageBox, QPushButton, QSizePolicy, QSplitter, QTextBrowser, QTextEdit, QToolButton,
    QVBoxLayout, QWidget,
)
from app_context import _settings, call_later, tr as _t
from code_editor import CodeEditor, find_in_plain_editor
from completion_ui import CompletionDialog
from custom_completion import load_custom_completion
from selection_quote import plain_compact, quote as quote_selection, resolve as resolve_quote
from selection_sync import choose_occurrence, occurrence_index_for_position
from tei_facsimile import position_inside_xml_markup
from text_search import SearchError, Utf16Positions
from code_editor import replace_all_in_plain_editor, replace_in_plain_editor
from fragment_units import (
    chosen_units, edit_stylesheet, edit_stylesheet_url, mark_units, place_edit_markers, stylesheet_needs_saxon,
    unit_spans,
)
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


def xml_selection_structure(xml_text, selection_start, selection_end, units, words=3):
    """Repère structurel d'une sélection de la source (V0.9.3.0), pour
    l'aperçu, quand son texte n'y apparaît pas tel quel (élément entier choisi
    par une recherche XPath, leçons d'un apparat, note…). ``units`` : les
    éléments modifiables de la source, ``(rang dans l'aperçu, début, fin)``.

    Renvoie le premier et le dernier élément touchés (``first``, ``last``),
    si la sélection couvre le début du premier et la fin du dernier
    (``from_start``, ``to_end``), ses premiers et derniers mots visibles
    (``head``, ``tail``) et leur décalage visible dans leur élément
    (``head_relative``, ``tail_relative``) ; None si elle ne touche aucun
    élément modifiable ou n'a pas de texte."""
    start, end = int(selection_start), int(selection_end)
    touched = [(index, a, b) for index, a, b in units if a < end and b > start]
    visible = _selection_xml_to_visible_text(xml_text[start:end]).split()
    if not touched or not visible:
        return None
    first, fa, fb = touched[0]
    last, la, lb = touched[-1]
    return {
        "first": first, "last": last, "from_start": start <= fa, "to_end": end >= lb,
        "head": " ".join(visible[:words]), "tail": " ".join(visible[-words:]),
        "head_relative": len(_selection_xml_to_visible_text(xml_text[fa:max(fa, start)])),
        "tail_relative": len(_selection_xml_to_visible_text(xml_text[la:min(end, lb)])),
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


_ROOT_BLOCK = re.compile(r":root\s*\{(.*?)\}", re.I | re.S)
_CSS_DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)")
_CSS_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)")
_STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.I | re.S)


def resolve_css_variables(css_text):
    """Résout les variables CSS des blocs ``:root`` pour le moteur HTML
    simplifié de Qt, qui ne comprend pas ``var()`` : chaque ``var(--x)`` prend
    la valeur de ``--x`` ; une variable peut en citer une autre ; une
    variable inconnue prend sa valeur de repli (``var(--x, repli)``)."""
    blocks = list(_ROOT_BLOCK.finditer(css_text))
    if not blocks:
        return css_text
    variables = {}
    for block in blocks:
        variables.update((name, value.strip()) for name, value in _CSS_DECLARATION.findall(block.group(1)))
    out = _ROOT_BLOCK.sub("", css_text)

    def value(match):
        name, fallback = match.group(1), match.group(2)
        if name in variables:
            return variables[name]
        return fallback.strip() if fallback is not None else match.group(0)

    for _ in range(8):                       # variables qui en citent d'autres
        resolved = _CSS_VAR.sub(value, out)
        if resolved == out:
            break
        out = resolved
    return out


def resolve_style_variables(html_text):
    """Les variables CSS des ``<style>`` d'une page produite par une feuille
    XSLT, remplacées par leur valeur (V0.9.4.4) ; le reste de la page ne
    change pas."""
    return _STYLE_BLOCK.sub(lambda m: m.group(1) + resolve_css_variables(m.group(2)) + m.group(3), html_text)


def has_own_style(html_text):
    """La page produite par la feuille a son propre ``<style>`` (V0.9.4.4) :
    une vue sans fichier CSS laisse alors de côté la CSS du projet, sauf
    ``projectCss="always"``."""
    return _STYLE_BLOCK.search(html_text) is not None


# Règles de base de l'aperçu (V0.9.3.0), placées avant la CSS du projet, qui
# les remplace si elle en a : une strophe de la feuille livrée (un seul bloc,
# vers séparés par des <br/>) en retrait, même avec la CSS d'un projet créé
# par une version antérieure. Qt ignore toute règle placée après un @media :
# celles du crayon ✎ et des repères de ligne, autrefois ajoutées à la fin,
# n'étaient pas appliquées (le crayon était un lien bleu souligné).
PREVIEW_BASE_CSS = (
    ".lg { margin-top: 0.5em; margin-bottom: 1em; margin-left: 2em; line-height: 150%; }\n"
    ".ref { color: #8a8177; }\n"
    ".rature { text-decoration: line-through; }\n"
    ".ajout { text-decoration: underline; }\n"
    ".sic { font-style: italic; }\n"
    ".lacune { color: #8a8177; }\n"
    ".petites-capitales { font-variant: small-caps; }\n"
    ".speaker { font-variant: small-caps; font-weight: 600; letter-spacing: 0.04em; margin-top: 0.6em; }\n"
    ".stage { font-style: italic; color: #5d554c; }\n"
    "div.stage { margin-left: 1.6em; margin-bottom: 0.4em; }\n"
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
    """Numérote puis préserve les repères du témoin pivot invisibles en temps linéaire.

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
        """Décrit une sélection de l'aperçu qui montre ``text`` et commence à ``selection_start`` :
        ``paragraph`` (rang de l'élément modifiable), ``occurrence`` (rang de ``text`` parmi ses
        occurrences dans cet élément) et ``relative`` (décalage depuis le début de l'élément) ;
        None hors de tout élément. Sert à retrouver la même occurrence dans la source ou le
        fragment."""
        pidx = self.paragraph_for_position(selection_start)
        if pidx is None:
            return None
        occurrences = self._visible_occurrences_in_paragraph(text, pidx)
        occ = occurrence_index_for_position(occurrences, selection_start)
        bounds = self.paragraph_bounds(pidx)
        rel = max(0, int(selection_start) - int(bounds[0])) if bounds else None
        return {"paragraph": pidx, "occurrence": occ, "relative": rel}

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

    def select_quote(self, context, focus=True):
        """Sélectionne dans l'aperçu ce que décrit ``context`` (voir
        ``selection_context``) : dans l'élément modifiable ``paragraph`` s'il
        y est, sinon dans toute la page, près du repère ``line`` en cas de
        doute. False si le texte n'y est pas (V0.9.4.5)."""
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
        if found is None:
            line = context.get("line")
            position = self._line_to_position.get(int(line)) if line is not None else None
            found = resolve_quote(compact, wanted,
                                  hint=None if position is None else compact.index_at(positions.python(position)))
        if found is None:
            return False
        a, b = (positions.qt(index) for index in compact.span(*found))
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

    def select_visible_text_near_line(self, text, ordinal=None):
        """Sélectionne réellement ``text`` près d'une ligne du témoin pivot.

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


_LXML_TRANSFORM_CACHE = {}

def lxml_available():
    """True si lxml s'importe. Sans lui, l'aperçu passe par PowerShell/.NET
    (``_transform_without_lxml``) et l'actualisation automatique attend plus longtemps."""
    try:
        import lxml.etree  # noqa: F401
        return True
    except Exception:
        return False


def publication_params():
    """Langue de l'interface et catalogues i18n, où la feuille de Varians
    lit ses textes (V0.9.3.1)."""
    from app_context import current_i18n
    from xslt_scenarios import catalogs_uri
    i18n = current_i18n()
    language = i18n.language if i18n is not None else "fr"
    return {"langue": language, "catalogues": catalogs_uri(language)}


def transform_with_xslt(xml_text, xsl_path, params=None, edit_markers=False, cache=None):
    """Transformation XSLT 1.0 optimisée.

    Avec lxml, la feuille XSLT compilée est mise en cache tant que le fichier
    n'a pas changé ; une erreur de la feuille ou de la transformation est
    signalée telle quelle. Le moteur .NET/PowerShell ne sert que de secours si
    lxml n'est pas installé.

    Avec ``edit_markers`` (V0.9.2.9), la feuille est importée par l'enveloppe
    de ``fragment_units.edit_stylesheet`` : les éléments numérotés par
    ``mark_units`` reçoivent leur crayon ✎, quelle que soit la feuille.

    *cache* : les feuilles compilées, propres à un fil (red team 2, A8) ; par
    défaut, celles du fil de la fenêtre. Un document très imbriqué est lu
    (huge_tree, red team 2, A10).
    """
    cache = _LXML_TRANSFORM_CACHE if cache is None else cache
    try:
        from lxml import etree as LET
    except ImportError as exc:
        return _transform_without_lxml(xml_text, xsl_path, params, exc, edit_markers)
    try:
        parser = LET.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)
        xml_doc = LET.fromstring(xml_text.encode("utf-8"), parser=parser)
        xp = Path(xsl_path).resolve()
        st = xp.stat()
        cache_key = (str(xp), st.st_mtime_ns, st.st_size, bool(edit_markers))
        transform = cache.get(cache_key)
        if transform is None:
            # Une seule version compilée par chemin (avec ou sans crayons)
            # suffit ; jeter les anciennes si la feuille a été modifiée sur
            # disque.
            for k in list(cache):
                if k[0] == str(xp) and k[3] == cache_key[3]:
                    cache.pop(k, None)
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
            cache[cache_key] = transform
        xslt_params = {str(k): LET.XSLT.strparam(str(v)) for k, v in (params or {}).items()}
        return str(transform(xml_doc, **xslt_params)), "lxml"
    except Exception as exc:
        # Seules les erreurs XSLT ont un journal propre à la transformation ;
        # celui d'une erreur de syntaxe XML est global et contient aussi les
        # erreurs antérieures.
        log = exc.error_log if isinstance(exc, LET.XSLTError) else ()
        raise RuntimeError(_xslt_error_text(exc, xsl_path, log)) from exc


def render_preview(xml_text, xsl_path, params, marker_title, cache=None, check=False, base=""):
    """La partie lourde de l'aperçu, sans Qt ni état de la fenêtre :
    ``(html, lignes cliquables, crayons, moteur)``. Avec *check*, le XML est
    d'abord vérifié (ET.ParseError). Peut se faire hors du fil de la
    fenêtre, avec son propre *cache* de feuilles compilées (red team 2, A8).

    Une feuille 2.0 ou 3.0 (V0.9.4.4) est confiée au processus d'aperçu
    Saxon (``saxon_preview``) : appel bloquant, à faire hors du fil de la
    fenêtre ; ``base`` est l'adresse du document, pour un ``doc()``
    relatif. Une erreur de Saxon lève ``saxon_preview.PreviewError``."""
    if check:
        ET.fromstring(xml_text)
    if stylesheet_needs_saxon(xsl_path):
        import saxon_preview
        result = saxon_preview.client().transform(xml_text, xsl_path, params, base=base,
                                                 timeout=saxon_preview.PREVIEW_TIMEOUT_SEC)
        html_text, engine = result.html, result.engine
    else:
        html_text, engine = transform_with_xslt(xml_text, xsl_path, params, edit_markers=True, cache=cache)
    html_text, clickable_lines, _text_links = make_line_segments_clickable(html_text)
    html_text, marked = place_edit_markers(html_text, marker_title)
    return resolve_style_variables(html_text), clickable_lines, marked, engine


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

    # Résultat d'une actualisation faite dans un autre fil (red team 2, A8),
    # reçu dans celui de la fenêtre.
    preview_job_done = Signal(object)

    def __init__(self, main_window):
        super().__init__(main_window)
        self.main = main_window
        # Vue choisie (V0.9.4.4) : None pour la vue du projet (feuille et CSS
        # de <rendering>), sinon une vue nommée (ViewConfig) du document
        # affiché. _view_key : le document dont la liste montre les vues
        # (l'édition, pour elle et ses parties) ; _views : ses vues nommées.
        self._current_view = None
        self._view_key = None
        self._views = ()
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
        # Liste des vues du document affiché : la vue du projet, puis ses
        # vues nommées. Elle remplace les boutons « XSLT… » et « CSS… », dont
        # le choix ne valait que pour la session.
        self.view_combo = QComboBox()
        self.view_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.view_combo.setMinimumContentsLength(12)
        # Menu « Vues » : créer, modifier, retirer une vue nommée du document
        # affiché, ouvrir sa feuille XSLT.
        self.views_button = QToolButton()
        self.views_button.setText(_t("views.menu"))
        self.views_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        views_menu = QMenu(self.views_button)
        self.new_view_action = views_menu.addAction(_t("views.new"))
        self.edit_view_action = views_menu.addAction(_t("views.edit"))
        self.remove_view_action = views_menu.addAction(_t("views.remove"))
        views_menu.addSeparator()
        self.open_view_stylesheet_action = views_menu.addAction(_t("views.open_xslt"))
        self.views_button.setMenu(views_menu)
        self.new_view_action.triggered.connect(self.new_view)
        self.edit_view_action.triggered.connect(self.edit_view)
        self.remove_view_action.triggered.connect(self.remove_view)
        self.open_view_stylesheet_action.triggered.connect(self.open_view_stylesheet)
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
        top.addWidget(self.view_combo)
        top.addWidget(self.views_button)
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
        self.fragment_visual_wrap.setToolTip(_t("source.visual_wrap"))     # texte entier, la case pouvant être réduite
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
        self.preview_timer.timeout.connect(self._refresh_preview_in_background)
        # Actualisation automatique hors du fil de la fenêtre (red team 2, A8).
        self._preview_generation = 0
        # Génération de l'aperçu en cours dans un autre fil (None : aucun), et
        # ce qui attend qu'il soit affiché (when_ready, V0.9.4.4).
        self._pending_job = None
        self._ready_callbacks = []
        self._preview_executor = None
        self._background_xslt_cache = {}
        self.preview_job_done.connect(self._background_preview_done)
        self.view_combo.currentIndexChanged.connect(self._view_chosen)
        self.context_changed()
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

    # -- Vues (V0.9.4.4) ----------------------------------------------------------

    @property
    def current_view(self):
        """Vue choisie : None pour la vue du projet, sinon une vue nommée
        (``ViewConfig``) du document affiché."""
        return self._current_view

    @property
    def xsl_path(self):
        """Feuille XSLT de la vue choisie : celle de la vue nommée (chemin
        relatif au projet, ou ``${varians}/…``), sinon celle du projet."""
        view = self._current_view
        if view is not None:
            path = self._view_file(view.xslt)
            if path is not None:
                return path
        return self.main.project.xslt

    def _css_mode(self):
        """CSS de l'aperçu (V0.9.4.4) : ``file`` (fichier de la vue),
        ``project`` (vue du projet, ou ``projectCss="always"``), ``never``
        (aucune) ou ``auto`` (celle du projet, sauf si la feuille produit son
        propre ``<style>``)."""
        view = self._current_view
        if view is None:
            return "project"
        if view.css.strip():
            return "file"
        return {"always": "project", "never": "never"}.get(view.project_css, "auto")

    def _preview_css(self, html_text):
        """CSS donnée à l'aperçu pour ``html_text`` : les règles de Varians
        (crayons, repères), puis, selon ``_css_mode``, le fichier CSS de la
        vue ou celui du projet."""
        mode = self._css_mode()
        if mode == "never" or (mode == "auto" and has_own_style(html_text)):
            return PREVIEW_BASE_CSS
        return self._resolved_css_cached()

    @property
    def css_path(self):
        """Fichier CSS de la vue choisie ; une vue nommée sans fichier CSS
        renvoie à celui du projet (``_css_mode`` dit s'il sert)."""
        view = self._current_view
        if view is not None:
            path = self._view_file(view.css)
            if path is not None:
                return path
        return self.main.project.css

    def _view_file(self, raw):
        from xslt_scenarios import resolve_path
        return resolve_path(self.main.project, raw)

    def _view_context(self):
        """``(clé, vues nommées)`` du document affiché : pour l'édition et
        ses parties, celles de l'édition (``<edition>``) ; pour un document
        auxiliaire, celles de son ``<document>``. La clé (chemin relatif au
        projet) retient la vue choisie dans les réglages du projet."""
        main = self.main
        session = getattr(main, "document", None)
        if session is None or session.in_edition or session.path is None:
            edition = getattr(main, "edition_session", None)
            path = getattr(edition, "path", None) or main.project.edition
            return "edition:" + main._place_key(path), tuple(main.project.edition_views)
        config = main.document_config(session)
        return main._place_key(session.path), tuple(config.views) if config is not None else ()

    def _remembered_views(self):
        try:
            data = json.loads(_settings().value(self.main._view_settings_key("previewViews"), "") or "{}")
        except (TypeError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _remember_view(self):
        if self._view_key is None:
            return
        data = self._remembered_views()
        if self._current_view is None:
            data.pop(self._view_key, None)
        else:
            data[self._view_key] = self._current_view.name
        _settings().setValue(self.main._view_settings_key("previewViews"), json.dumps(data, ensure_ascii=False))

    def context_changed(self):
        """Document affiché changé, ou ses vues : la liste montre celles du
        nouveau document, et la vue qui y avait été choisie la dernière fois.
        Passer de l'édition à l'une de ses parties ne change rien : l'aperçu
        reste celui de l'édition assemblée."""
        key, views = self._view_context()
        if key == self._view_key and views == self._views:
            return
        self._view_key, self._views = key, views
        name = self._remembered_views().get(key)
        self._current_view = next((view for view in views if view.name == name), None)
        self._fill_view_combo()
        self._reset_preview(clear=True)

    def _fill_view_combo(self):
        combo = self.view_combo
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem(_t("preview.view.project"), None)
            for view in self._views:
                combo.addItem(view.name, view.name)
            index = combo.findData(self._current_view.name) if self._current_view is not None else 0
            combo.setCurrentIndex(max(0, index))
        finally:
            combo.blockSignals(False)
        self._update_view_tip()
        self._update_view_actions()

    def _update_view_actions(self):
        """La vue du projet ne se modifie ni ne se retire ici (Paramètres du
        projet…) ; seule une feuille du projet s'ouvre dans un onglet."""
        named = self._current_view is not None
        self.edit_view_action.setEnabled(named)
        self.remove_view_action.setEnabled(named)
        self.open_view_stylesheet_action.setEnabled(named and self._project_stylesheet() is not None)

    def _project_stylesheet(self):
        """Feuille XSLT de la vue nommée choisie, si elle est un fichier du
        projet ; sinon None (feuille de Varians, fichier absent…)."""
        if self._current_view is None:
            return None
        path = self.xsl_path
        try:
            path.relative_to(Path(self.main.project.root_dir).resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def _views_may_change(self):
        """Avant d'écrire les vues : un fragment ouvert est appliqué ou
        abandonné (ses éléments modifiables peuvent changer) ; False si
        l'utilisateur annule."""
        return self.frag_box.isHidden() or self.close_fragment_editor()

    def _store_views(self, views, chosen):
        """Écrit les vues nommées du document affiché dans project.xml, puis
        montre ``chosen`` (None : la vue du projet). False si l'écriture
        échoue (message déjà affiché)."""
        if not self.main.set_preview_views(views):
            return False
        data = self._remembered_views()
        if chosen is None:
            data.pop(self._view_key, None)
        else:
            data[self._view_key] = chosen.name
        _settings().setValue(self.main._view_settings_key("previewViews"), json.dumps(data, ensure_ascii=False))
        self._views = None                       # liste à refaire
        self.context_changed()
        if self.isVisible():
            self.refresh_preview(force=True)
        return True

    def _view_dialog(self, view=None, units=()):
        from view_dialogs import ViewDialog
        taken = [v.name for v in self._views if v is not view]
        dialog = ViewDialog(self, self.main.project, view=view, taken=taken, units=units)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_view is None:
            return None
        return dialog.result_view

    def new_view(self):
        """« Nouvelle vue… » : vue nommée du document affiché, avec au choix
        une feuille XSLT 1.0 et une CSS de départ ; pour un document
        auxiliaire, les entrées de sa première liste sont proposées comme
        éléments modifiables. La nouvelle vue est choisie."""
        from view_files import suggested_units
        if not self._views_may_change():
            return False
        session = self.main.document
        units = () if session is None or session.in_edition else suggested_units(self.main.editor.toPlainText())
        view = self._view_dialog(units=units)
        if view is None:
            return False
        return self._store_views(tuple(self._views) + (view,), view)

    def edit_view(self):
        """« Modifier la vue… » : nom, feuille, CSS et éléments modifiables de
        la vue choisie ; ses anciens fichiers restent."""
        current = self._current_view
        if current is None or not self._views_may_change():
            return False
        view = self._view_dialog(current)
        if view is None:
            return False
        return self._store_views(tuple(view if v == current else v for v in self._views), view)

    def remove_view(self):
        """« Retirer la vue » : après confirmation, la vue choisie quitte
        project.xml ; ses fichiers restent. La vue du projet est alors
        choisie."""
        current = self._current_view
        if current is None:
            return False
        answer = QMessageBox.question(
            self, _t("views.remove.title"), _t("views.remove.question", name=current.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes or not self._views_may_change():
            return False
        return self._store_views(tuple(v for v in self._views if v != current), None)

    def open_view_stylesheet(self):
        """« Ouvrir la feuille XSLT » : la feuille de la vue choisie, si elle
        est dans le projet, s'affiche dans son onglet (ajoutée aux documents
        du projet au besoin) ; F8 la vérifie."""
        path = self._project_stylesheet()
        return path is not None and self.main.open_project_file(path)

    def _update_view_tip(self):
        view = self._current_view
        lines = []
        if view is None:
            lines.append(_t("project.xslt.mode.builtin" if self.main.project.xslt_mode == "builtin"
                            else "project.xslt.mode.file"))
        mode = self._css_mode()
        css = (_t("preview.view.css.none") if mode == "never"
               else _t("preview.view.css.auto", css=self.css_path) if mode == "auto" else self.css_path)
        lines.append(_t("preview.view.files.tip", xslt=self.xsl_path, css=css))
        if view is not None and view.units:
            lines.append(_t("preview.view.units.tip", units=", ".join(view.units)))
        self.view_combo.setToolTip("\n".join(lines))

    def select_view(self, name):
        """Choisit la vue ``name`` du document affiché (None : la vue du
        projet), comme dans la liste. False si elle n'existe pas ou si le
        changement est annulé (fragment modifié)."""
        index = 0 if name is None else self.view_combo.findData(name)
        if index < 0:
            return False
        if index != self.view_combo.currentIndex():
            self.view_combo.setCurrentIndex(index)
        current = self._current_view
        return (current.name if current is not None else None) == name

    def _view_chosen(self, index):
        """Choix dans la liste des vues : un fragment ouvert est d'abord
        appliqué ou abandonné (sinon le choix est annulé), puis l'aperçu est
        refait avec la feuille, la CSS et les éléments modifiables de la
        vue."""
        name = self.view_combo.itemData(index)
        view = next((v for v in self._views if v.name == name), None)
        if view == self._current_view:
            return
        if not self.frag_box.isHidden() and not self.close_fragment_editor():
            previous = self.view_combo.findData(self._current_view.name) if self._current_view is not None else 0
            self.view_combo.blockSignals(True)
            self.view_combo.setCurrentIndex(max(0, previous))
            self.view_combo.blockSignals(False)
            return
        self._current_view = view
        self._remember_view()
        self._update_view_tip()
        self._update_view_actions()
        self._reset_preview(clear=False)
        if self.isVisible():
            self.refresh_preview(force=True)

    def _reset_preview(self, clear):
        """L'aperçu est à refaire (autre vue, autre document) : ses éléments
        modifiables seront relevés à nouveau. Avec ``clear``, il est vidé : il
        montrait un autre document."""
        self.preview_timer.stop()
        self._preview_generation += 1           # un aperçu en cours est dépassé
        self._pending_job = None
        self._ready_callbacks = []              # ils visaient l'aperçu d'avant
        self.unit_names = None
        self.sources = None
        self.dirty_preview = True
        self._last_preview_key = None
        if clear:
            self.preview.clear()
            self.preview.rebuild_line_markers()

    def view_unit_names(self):
        """Éléments modifiables de la vue choisie : ceux qu'elle nomme
        (``units``, comptés partout dans le document), sinon la règle de
        l'édition (schéma du document, sinon TEI P5)."""
        view = self._current_view
        if view is not None and view.units:
            return chosen_units(view.units)
        return self.main.fragment_unit_names()

    def retranslate_ui(self):
        """Remet les textes de la vue dans la langue de l'interface, puis retransforme l'aperçu
        (``force=True``) : la feuille XSLT y écrit aussi des textes traduits (titre de la table
        des matières…)."""
        self.view_combo.setItemText(0, _t("preview.view.project"))
        self._update_view_tip()
        self.views_button.setText(_t("views.menu"))
        self.new_view_action.setText(_t("views.new"))
        self.edit_view_action.setText(_t("views.edit"))
        self.remove_view_action.setText(_t("views.remove"))
        self.open_view_stylesheet_action.setText(_t("views.open_xslt"))
        self.edit_paragraph_action.setText(_t("preview.edit_paragraph"))
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
        """True si le focus clavier est dans l'aperçu ou dans sa barre de recherche."""
        focus = QApplication.focusWidget()
        return bool(
            focus is self.preview
            or (focus is not None and self.preview.isAncestorOf(focus))
            or focus is self.preview_find_box
            or (focus is not None and self.preview_find_bar.isAncestorOf(focus))
        )

    def show_preview_find(self):
        """Montre la barre « Rechercher dans l’aperçu : » et y met le focus (Ctrl+F dans l'onglet
        de l'aperçu). Une sélection courte de l'aperçu (une ligne, 120 caractères au plus)
        devient le texte cherché."""
        self.preview_find_bar.setVisible(True)
        selected = self.preview.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.preview_find_box.setText(selected)
        self.preview_find_box.setFocus()
        self.preview_find_box.selectAll()

    def hide_preview_find(self):
        """Bouton « ✕ » : cache la barre de recherche de l'aperçu, efface le surlignage de
        l'occurrence et rend le focus à l'aperçu."""
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
        """Occurrence suivante dans l'aperçu (Entrée, « ▶ », F3) : la source et les témoins vont à
        sa ligne, l'onglet de l'aperçu restant affiché. Sans texte cherché, montre la barre."""
        self._find_preview(False)

    def find_preview_previous(self):
        """Comme ``find_preview_next``, vers l'arrière (« ◀ », Maj+F3)."""
        self._find_preview(True)

    def current_preview_line(self):
        """Ligne du témoin pivot où en est la lecture de l'aperçu : le repère au centre de la zone
        visible, sinon la dernière ligne active ; None si l'aperçu n'en a pas. Sert au retour
        vers la source et à garder la place quand la taille du texte change."""
        # Pour une transition d'onglet, la ligne au centre de la fenêtre reflète
        # mieux la position de lecture qu'une ancienne sélection.
        line = self.preview.line_at_viewport_center()
        return line if line is not None else self.preview.active_line_ordinal

    def scroll_to_t1_line(self, ordinal):
        """Fait défiler l'aperçu jusqu'au repère de ligne ``ordinal`` du témoin pivot, centré.
        L'aperçu est d'abord actualisé s'il est en retard sur la source ; le défilement attend
        le tour suivant de la boucle d'événements. Rien si ``ordinal`` est None."""
        if ordinal is None:
            return
        if self.dirty_preview:
            self.refresh_preview()
        call_later(0, self, lambda n=int(ordinal): self.preview.scroll_to_line(n, center=True))

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

    def show_fragment_find(self, replace=False):
        """Montre la ligne « Rechercher dans le fragment : » (Ctrl+F) et, avec ``replace``
        (Ctrl+H), la ligne « Remplacer par : », cachée sinon. Une sélection courte du fragment
        (une ligne, 120 caractères au plus) devient le texte cherché ; le focus va à la
        recherche."""
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
        """Bouton « × » : cache la recherche et le remplacement du fragment et rend le focus à
        l'éditeur de fragment. Le surlignage de l'occurrence trouvée, lui, reste affiché."""
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
        """Occurrence suivante dans le fragment (Entrée, « ▶ », F3), avec les options de recherche
        de la fenêtre (« Aa », « .* ») ; sans texte cherché, montre la barre. Quand la ligne
        « Remplacer par : » est visible, le texte cherché garde ses blancs du début et de la fin."""
        self._find_fragment(False)

    def replace_fragment_next(self):
        """« Remplacer » : remplace dans le fragment l'occurrence surlignée par le texte de
        « Remplacer par : », si elle correspond toujours à la recherche, puis cherche la
        suivante. Seul l'éditeur de fragment change : le XML attend « Appliquer au XML »."""
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
        """« Tout remplacer » dans le fragment, en une seule étape d'annulation ; le nombre de
        remplacements s'affiche dans la barre d'état. Le XML attend « Appliquer au XML »."""
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
        """Comme ``find_fragment_next``, vers l'arrière (« ◀ », Maj+F3)."""
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
        """À chaque modification de la source : l'aperçu est marqué en retard et une actualisation
        en cours dans un autre fil est rendue caduque. Avec « Aperçu auto » et la vue affichée,
        l'actualisation est reportée à la fin d'une pause de la frappe (``preview_timer``)."""
        self.dirty_preview = True
        # Un aperçu en cours dans un autre fil ne montre plus le texte.
        self._preview_generation += 1
        # start() redémarre le timer : une saisie continue ne déclenche donc pas
        # de transformation intermédiaire. On attend une vraie pause de frappe.
        if self.auto_check.isChecked() and self.isVisible():
            self.preview_timer.start()

    def became_visible(self):
        """À l'affichage de l'onglet de l'aperçu : l'actualise s'il est en retard sur la source."""
        if self.dirty_preview:
            self.refresh_preview()

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

    def _preview_inputs(self):
        """Ce que l'aperçu transforme : ``(sources, texte, plages, noms)``.
        Édition en parties (XInclude) : l'édition assemblée, quel que soit le
        document affiché ; ses éléments modifiables et ses lignes restent
        rattachés à leur fichier (V0.9.1.5). Chaque élément modifiable porte
        son rang (vx:edit), celui de son crayon ✎. Un document auxiliaire,
        ou une édition sans parties : le document affiché."""
        names = self.view_unit_names()
        if self.main._preview_shows_assembly():
            sources = self.main._assembled_preview_sources(names)
            xml_text = (sources.text if sources is not None
                        else self.main.edition_session.text_document.toPlainText())
            spans = sources.paragraphs if sources is not None else ()
        else:
            sources = None
            xml_text, spans = mark_units(self.main.editor.toPlainText(), names)
        return sources, xml_text, spans, names

    def _preview_files_missing(self):
        if self.xsl_path.exists() and (self._css_mode() == "never" or self.css_path.exists()):
            return False
        self.info.setText(_t("preview.files_missing"))
        self.info.setStyleSheet("color:#a14b2f")
        return True

    def _preview_key(self, xml_text, names):
        # Empreinte légère : évite de reconstruire le gros QTextDocument quand
        # rien n'a changé (clic sur Actualiser, changement d'onglet, etc.).
        xml_digest = hashlib.blake2b(xml_text.encode("utf-8"), digest_size=12).hexdigest()
        return (xml_digest, self._file_signature(self.xsl_path), self._file_signature(self.css_path), names)

    def _preview_up_to_date(self):
        self.dirty_preview = False
        engine = self._last_preview_engine or "cache"
        self.info.setText(_t("preview.up_to_date", engine=engine))
        self.info.setStyleSheet("color:#376b3c")

    def _preview_params(self):
        """Paramètres de la feuille de l'aperçu : le témoin pivot
        (``baseWitness`` pour la feuille de Varians, ``temoin-de-base`` pour
        « Édition critique »), le titre du sommaire, la langue et les
        catalogues ; ``reperes-lignes`` (V0.9.4.4) demande à « Édition
        critique » les repères de ligne, qu'une publication n'a pas. Une
        feuille ignore ceux qu'elle ne déclare pas."""
        return {"baseWitness": self.main.base_id, "temoin-de-base": self.main.base_id, "reperes-lignes": "true",
                "tocTitle": _t("preview.toc"), **publication_params()}

    def _preview_base(self):
        """Adresse du document transformé (pour un ``doc()`` relatif d'une
        feuille 3.0) : l'édition quand l'aperçu la montre assemblée, sinon
        le document affiché."""
        main = self.main
        if main._preview_shows_assembly():
            return str(getattr(main.edition_session, "path", "") or main.project.edition)
        return str(getattr(main.document, "path", "") or "")

    def _expected_line_count(self):
        """Nombre de lignes du témoin pivot auxquelles vont les repères de
        l'aperçu de l'édition (V0.9.4.4) : celles de l'édition assemblée,
        sinon les <lb/> du pivot du document affiché ; None hors de
        l'édition ou sans pivot."""
        main = self.main
        document = getattr(main, "document", None)
        if document is None or not document.in_edition or not getattr(main, "base_id", ""):
            return None
        if self.sources is not None:
            return len(self.sources.lines)
        return len(main.lb_spans())

    def _preview_error_text(self, exc):
        """Texte d'un échec de l'aperçu : délai dépassé, Saxon absent ou
        arrêté (V0.9.4.4), sinon l'erreur de la feuille, avec son lieu."""
        from saxon_preview import PreviewError
        if isinstance(exc, PreviewError):
            if exc.code == "timeout":
                return _t("preview.saxon.timeout", seconds=exc.detail)
            if exc.code == "saxon_missing":
                return _t("preview.saxon.missing")
            if exc.code == "worker_failed":
                return _t("preview.saxon.failed", error=exc.detail)
            return _t("preview.transform_error", error=exc.detail or exc.code)
        return _t("preview.transform_error", error=exc)

    def refresh_preview(self, force=False):
        """Transforme la source par la feuille XSLT, dans le fil de la fenêtre, et affiche le
        résultat avec la CSS ; pour une édition en parties, c'est l'édition assemblée qui est
        transformée. Sans ``force`` (bouton « Actualiser »), rien n'est refait si le texte, les
        feuilles et les éléments modifiables n'ont pas changé. Un XML mal formé ou une erreur de
        transformation est signalé sous l'aperçu, qui garde son contenu."""
        sources, xml_text, spans, names = self._preview_inputs()
        self.sources = sources
        if self._preview_files_missing():
            return
        preview_key = self._preview_key(xml_text, names)
        if not force and preview_key == self._last_preview_key:
            self._preview_up_to_date()
            return
        # Un aperçu en cours dans un autre fil est dépassé.
        self._preview_generation += 1
        try:
            ET.fromstring(xml_text)
        except ET.ParseError as exc:
            self.info.setText(_t("preview.xml_invalid", error=exc))
            self.info.setStyleSheet("color:#a14b2f")
            return
        if stylesheet_needs_saxon(self.xsl_path):
            # Saxon (V0.9.4.4) : hors du fil de la fenêtre, même à la demande.
            self.info.setText(_t("preview.refreshing"))
            self.info.setStyleSheet("color:#746b61")
            self._refresh_preview_in_background(force=True)
            return
        started = time.perf_counter()
        try:
            rendered = render_preview(xml_text, self.xsl_path, self._preview_params(), _t("preview.edit_paragraph"),
                                      base=self._preview_base())
            self._show_preview(rendered, preview_key, names, spans, started)
        except Exception as exc:
            self.info.setText(self._preview_error_text(exc))
            self.info.setStyleSheet("color:#a13d32")

    def _refresh_preview_in_background(self, force=False):
        """Actualisation automatique, après une pause de la frappe (red team
        2, A8) : la transformation (0,85 s par Mo) se fait hors du fil de la
        fenêtre, qui reste libre ; seul l'affichage du résultat s'y fait. Un
        résultat dépassé (le texte a changé depuis, ou l'aperçu a été
        actualisé autrement) est jeté. Avec ``force``, l'aperçu est refait
        même s'il semble à jour (actualisation demandée, feuille 3.0)."""
        sources, xml_text, spans, names = self._preview_inputs()
        if self._preview_files_missing():
            return
        preview_key = self._preview_key(xml_text, names)
        if not force and preview_key == self._last_preview_key:
            self._preview_up_to_date()
            return
        self._preview_generation += 1
        generation = self._preview_generation
        xsl_path, params, title = self.xsl_path, self._preview_params(), _t("preview.edit_paragraph")
        base = self._preview_base()
        started = time.perf_counter()
        cache = self._background_xslt_cache

        def job():
            try:
                return "ok", render_preview(xml_text, xsl_path, params, title, cache=cache, check=True, base=base)
            except ET.ParseError as exc:
                return "xml", exc
            except Exception as exc:
                return "error", exc

        def finished(future):
            try:
                self.preview_job_done.emit((generation, future.result(), sources, spans, names, preview_key, started))
            except RuntimeError:
                pass        # la vue a été fermée entre-temps

        if self._preview_executor is None:
            self._preview_executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="varians-preview")
        self._pending_job = generation
        self._preview_executor.submit(job).add_done_callback(finished)

    def when_ready(self, callback):
        """Appelle ``callback`` quand l'aperçu affiché est à jour : tout de
        suite (au tour suivant de la boucle d'événements) s'il l'est, sinon
        après l'affichage de l'aperçu en cours dans un autre fil (feuille
        3.0, V0.9.4.4). Sert à y reporter la sélection de la source. Rien
        n'est appelé si cet aperçu échoue."""
        if self._pending_job is not None and self._pending_job == self._preview_generation:
            self._ready_callbacks.append(callback)
        else:
            call_later(20, self, callback)

    def _run_ready_callbacks(self, shown):
        callbacks, self._ready_callbacks = self._ready_callbacks, []
        if shown:
            for callback in callbacks:
                call_later(20, self, callback)

    def _background_preview_done(self, payload):
        generation, (status, value), sources, spans, names, preview_key, started = payload
        if generation != self._preview_generation:
            return
        self._pending_job = None
        if status == "xml":
            self.info.setText(_t("preview.xml_invalid", error=value))
            self.info.setStyleSheet("color:#a14b2f")
            self._run_ready_callbacks(False)
        elif status == "error":
            self.info.setText(self._preview_error_text(value))
            self.info.setStyleSheet("color:#a13d32")
            self._run_ready_callbacks(False)
        else:
            self.sources = sources
            try:
                self._show_preview(value, preview_key, names, spans, started)
            except Exception as exc:
                self.info.setText(_t("preview.transform_error", error=exc))
                self.info.setStyleSheet("color:#a13d32")
                self._run_ready_callbacks(False)

    def _show_preview(self, rendered, preview_key, names, spans, started):
        """Affiche le résultat de ``render_preview``, à la même place."""
        html_text, clickable_lines, marked, engine = rendered
        # Conserver une ancre sémantique plutôt qu’une simple valeur de scrollbar.
        # Une modification de fragment peut changer la hauteur/recomposition du HTML :
        # restaurer le même nombre de pixels ne ramène alors plus au même passage.
        old_anchor_line = self.preview.line_at_viewport_center()
        if old_anchor_line is None:
            old_anchor_line = self.preview.active_line_ordinal
        old_bar = self.preview.verticalScrollBar()
        old_ratio = (old_bar.value() / old_bar.maximum()) if old_bar.maximum() > 0 else 0.0
        css = self._preview_css(html_text)

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
        elapsed = time.perf_counter() - started
        document = getattr(self.main, "document", None)
        if document is not None and not document.in_edition:
            # Un document sans témoin (V0.9.4.4) : rien à dire des lignes du pivot.
            self.info.setText(_t("preview.updated.timed.document", elapsed=f"{elapsed:.2f}", engine=engine,
                                 marked=marked, paragraphs=len(spans)))
            self.info.setStyleSheet("color:#376b3c")
        elif clickable_lines:
            text = _t("preview.updated.timed.lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked,
                      paragraphs=len(spans), lines=clickable_lines)
            expected = self._expected_line_count()
            if expected is not None and expected != clickable_lines:
                # V0.9.4.4 : le n-ième repère va à la n-ième ligne du pivot ;
                # un repère omis ou répété décale tout ce qui suit.
                self.info.setText(text + " " + _t("preview.lines_mismatch", lines=clickable_lines, expected=expected))
                self.info.setStyleSheet("color:#9a6a2f")
            else:
                self.info.setText(text)
                self.info.setStyleSheet("color:#376b3c")
        else:
            self.info.setText(_t("preview.updated.timed.no_lines", elapsed=f"{elapsed:.2f}", engine=engine, marked=marked, paragraphs=len(spans)))
            self.info.setStyleSheet("color:#9a6a2f")
        self._run_ready_callbacks(True)

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
            # ligne du témoin pivot située au centre du passage atteint, sans quitter l’aperçu.
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
        fragment = self.fragment_editor.toPlainText()
        chosen = pick_xml_occurrence(fragment, text, descriptor)
        if not chosen:
            return False
        qt = self.fragment_editor.positions(fragment)
        selection = QTextCursor(self.fragment_editor.document())
        selection.setPosition(qt.qt(chosen[0]))
        selection.setPosition(qt.qt(chosen[1]), QTextCursor.MoveMode.KeepAnchor)
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
        fragment = self.fragment_editor.toPlainText()
        descriptor = xml_selection_descriptor(fragment, text,
                                              self.fragment_editor.positions(fragment).python(cursor.selectionStart()))
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

