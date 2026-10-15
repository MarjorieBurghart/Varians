# -*- coding: utf-8 -*-
"""Varians — éditeur TEI/manuscrits générique — V0.8.5.26.2.

Refactorisation de la base V8o : le projet, le témoin de base, les témoins
secondaires, les alignements et les fichiers de rendu sont déclarés dans
``project.xml``. Aucun sigle de manuscrit n'est requis par la logique métier.

Dépendance externe obligatoire : PySide6.
XSLT : lxml si disponible, sinon moteur .NET/PowerShell sous Windows.
Installation : python -m pip install --user PySide6

Cette version affiche les sources d’images via un modèle générique (IIIF, fichier
local ou absence d’image) avec QGraphicsView. Les sources distantes sont
récupérées en Python (urllib). Elle ne contient aucun navigateur HTML embarqué.
"""
from __future__ import annotations

import bisect
import hashlib
import json
import os
import html as html_lib
from html.parser import HTMLParser
import re
import shutil
import sys
import subprocess
import tempfile
import urllib.request
import urllib.error
from urllib.parse import quote_plus
import threading
import time
import xml.etree.ElementTree as ET
from collections import defaultdict
from pathlib import Path

# ---------------------------------------------------------------------------
# Protection Spyder / IPython contre les imports mélangés entre installations.
#
# Spyder peut conserver dans sys.modules les modules d'une ancienne V0.4 alors
# que l'on exécute le nouveau editeur_tei.py via %runfile. Un simple ajout au
# sys.path ne suffit PAS : Python privilégie les modules déjà chargés.
# On donne priorité au dossier de CET exécutable puis on oublie uniquement les
# modules propres à l'application qui proviennent d'une autre installation.
# Aucun fichier projet ni module tiers n'est modifié.
# ---------------------------------------------------------------------------
_APPLICATION_DIR = Path(__file__).resolve().parent
_CURRENT_DIR = str(_APPLICATION_DIR)
sys.path[:] = [_CURRENT_DIR] + [
    _entry for _entry in sys.path
    if not _entry or Path(_entry).resolve() != _APPLICATION_DIR
]
_LOCAL_MODULE_NAMES = {"project_config", "project_management", "project_dialogs", "i18n", "relaxng_validation", "schema_resolution", "rng_completion", "xpath_search", "save_io", "custom_completion", "image_sources", "iiif_manifest", "iiif_local", "iiif_selection", "iiif_download_manager", "iiif_page_selection", "alto_import", "tei_facsimile", "xml_tag_pairs", "tei_formatter", "selection_sync", "witness_resource_refresh", "resource_state", "witness_layout", "iiif_resolution", "folio_navigation", "xml_folding", "document_session", "app_context", "image_fetch", "manuscript_panel", "code_editor", "witness_sync", "project_actions", "main_menus", "help_dialogs", "witness_workspace", "document_io", "completion_ui", "validation_panel", "xpath_panel"}
for _module_name, _module in tuple(sys.modules.items()):
    if _module_name not in _LOCAL_MODULE_NAMES and not (
        _module_name == "web_viewer" or _module_name.startswith("web_viewer.")
    ):
        continue
    _module_file = getattr(_module, "__file__", None)
    if _module_file is None:
        # Par exemple un package « namespace » provenant d'un ancien dossier.
        sys.modules.pop(_module_name, None)
    elif not Path(_module_file).resolve().is_relative_to(_APPLICATION_DIR):
        sys.modules.pop(_module_name, None)

from project_config import load_project, update_project_language, has_line_synchronization
from resource_state import primary_sync_line_count, secondary_sync_link_count
from witness_resource_refresh import (assemble_resources, RuntimeState, diagnostic_rows, changed_witnesses)
from project_management import create_portable_project, create_new_transcription_project, write_project_xml, create_local_xslt_if_needed, prepare_alignment_files_for_project, prepare_local_images_for_project, prepare_alto_files_for_project, prepare_iiif_manifests_for_project
from project_dialogs import NewProjectDialog, ProjectSettingsDialog, run_pivot_scaffold_dialog
from i18n import I18nManager
from relaxng_validation import validate_relaxng, lxml_available, relaxng_schema_token
from save_io import atomic_write_text_with_backup
from app_context import (
    APP_VERSION, set_i18n, tr, _settings, SETTINGS_ORGANIZATION, SETTINGS_APPLICATION, MAX_RECENT_PROJECTS,
    recent_project_paths, remember_recent_project, remove_recent_project, clear_recent_projects,
    last_open_project_path, remember_open_project, forget_open_project,
)
from document_session import DocumentSession, LbIndex
from manuscript_panel import ManuscriptPanel
from code_editor import CodeEditor, find_in_plain_editor, XMLHighlighter
from witness_sync import WitnessSyncMixin, flatten_primary, flatten_secondary
from image_fetch import DISK_CACHE, FetchSignals, FetchWorker
from project_actions import ProjectActionsMixin
from main_menus import MainMenusMixin
from help_dialogs import (
    _build_varians_card, _open_external, _open_latin_dictionary, _show_about, _show_software_help,
)
from witness_workspace import WitnessWorkspaceMixin
from document_io import DocumentIOMixin
from completion_ui import CompletionDialog, CompletionMixin
from validation_panel import ValidationPanelMixin
from xpath_panel import XPathPanelMixin
from schema_resolution import resolve_schema, detect_xml_models
from rng_completion import (
    load_completion_model, analyze_xml_context, XmlContextCache,
    adapt_pointer_list_value_context, format_pointer_list_insertion,
)
from custom_completion import load_custom_completion, merge_suggestion_sources
from xpath_search import search_xpath, XPathUnavailable, XPathQueryError
from image_sources import (
    page_image_source, page_image_dimensions, page_label as image_page_label,
    page_image_request as generic_image_request, full_page_target, image_scene_reference_crop,
    apply_witness_image_policy, image_only_items, page_navigation_items, display_window_indices,
    matched_line_center, valid_matched_indices, visible_line_frame_indices, effective_line_bbox,
)
from alto_import import apply_witness_alto_policy
from iiif_local import apply_working_copy, download_witness_copy
from folio_navigation import folios_for_witness, folio_at_position, split_surface_into_folios, scene_rect_for_folio, markable_part_for_line, inspect_surface_part_split, configure_surface_parts
from tei_facsimile import (
    facsimile_ref_at_position, upsert_pb_at_position, position_inside_xml_markup, project_facsimile_pages,
    sync_facsimile_file, sync_facsimile_text, previous_surface_labels,
    removable_generated_iiif_surfaces,
)
from xml_tag_pairs import (
    opening_pair_at_context, pair_at_context, exact_selected_opening_pair, closing_rename_mirror_for_change,
    opening_pair_for_name_change, opening_tag_at, closing_tag_suggestion,
)
from xml_folding import foldable_xml_regions, region_at_header, region_for_cursor
from tei_formatter import format_tei_xml
from selection_sync import containing_span_index, occurrence_index_for_position, choose_occurrence

try:
    from PySide6.QtCore import (
        Qt, QTimer, QObject, Signal, Slot, QRunnable, QThreadPool, QEvent,
        QRect, QRectF, QSize, QUrl, QPointF, QSettings, QRegularExpression, QBuffer, QByteArray, QIODevice, QStringListModel,
    )
    from PySide6.QtGui import (
        QColor, QFont, QPainter, QTextCharFormat, QTextCursor,
        QSyntaxHighlighter, QAction, QActionGroup, QKeySequence, QDesktopServices,
        QTextFormat, QTextDocument, QPixmap, QPen, QBrush, QImageReader, QPolygonF,
    )
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QPlainTextEdit, QPlainTextDocumentLayout, QWidget, QSplitter,
        QToolBar, QFileDialog, QMessageBox, QLabel, QLineEdit, QSizePolicy,
        QTextEdit, QVBoxLayout, QHBoxLayout, QPushButton, QCheckBox,
        QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsPolygonItem,
        QScrollArea, QFrame, QTabWidget, QTextBrowser, QInputDialog, QComboBox,
        QDialog, QDialogButtonBox, QProgressDialog, QFormLayout, QSpinBox, QDoubleSpinBox, QMenu, QToolButton, QCompleter, QTableWidget,
        QTableWidgetItem, QHeaderView, QAbstractItemView, QListWidget, QListWidgetItem,
    )
except ImportError:
    print("PySide6 n'est pas installé.")
    print("Installez-le avec : python -m pip install --user PySide6")
    raise

HERE = Path(__file__).resolve().parent
DEMO_PROJECT = HERE / "project.xml"
WELCOME_PROJECT_NAME = "Varians"

# Palette de sélection commune à toute l'application. Le bleu système Windows
# est souvent trop sombre avec certains thèmes ; Varians emploie partout la
# même nuance claire que le panneau XPath.
LIGHT_SELECTION_QSS = """
QAbstractItemView::item:selected { background-color: #d9ecff; color: #111111; }
QAbstractItemView::item:hover { background-color: #eef7ff; color: #111111; }
QMenu::item:selected { background-color: #d9ecff; color: #111111; }
QComboBox QAbstractItemView::item:selected { background-color: #d9ecff; color: #111111; }
"""

def _install_light_selection_palette(app):
    if app is None:
        return
    existing = app.styleSheet() or ""
    marker = "QAbstractItemView::item:selected { background-color: #d9ecff;"
    if marker not in existing:
        app.setStyleSheet((existing + "\n" + LIGHT_SELECTION_QSS).strip())
I18N = I18nManager(HERE / "i18n", "fr", "en")
set_i18n(I18N)

def _t(key, default=None, **values):
    return tr(key, default=default, **values)


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


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


class XmlHealthSignals(QObject):
    # revision QTextDocument, bien formé, ligne, colonne 0-based, message, spans lb
    finished = Signal(int, bool, int, int, str, object)


class XmlHealthWorker(QRunnable):
    """Contrôle XML automatique hors du thread graphique.

    La validation explicite (sauvegarde/F8) reste synchrone ; seul le contrôle
    de bonne formation déclenché après la frappe est déplacé ici.
    """

    def __init__(self, revision, text, lb_pattern):
        super().__init__()
        self.revision = int(revision)
        self.text = text
        self.lb_pattern = lb_pattern
        self.signals = XmlHealthSignals()

    @Slot()
    def run(self):
        well_formed = True
        line = 0
        column = 0
        message = ""
        spans = None
        try:
            ET.fromstring(self.text)
            # Profiter du même instantané de texte pour reconstruire les repères
            # de lignes sans provoquer une seconde copie de QPlainTextEdit.
            spans = [(m.start(), m.end()) for m in self.lb_pattern.finditer(self.text)]
        except ET.ParseError as exc:
            well_formed = False
            line, column = getattr(exc, "position", (0, 0)) or (0, 0)
            message = str(exc)
        self.signals.finished.emit(
            self.revision, well_formed, int(line or 0), int(column or 0),
            message, spans,
        )


P_ELEMENT_RE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?p\b[^>]*>.*?</(?:[A-Za-z_][\w.-]*:)?p\s*>",
    re.IGNORECASE | re.DOTALL,
)


def paragraph_spans(xml_text):
    """Plages des <p> du tei:body uniquement, avec offsets absolus dans le XML source."""
    body_open = re.search(r"<(?:[A-Za-z_][\w.-]*:)?body\b[^>]*>", xml_text, re.I)
    body_close = re.search(r"</(?:[A-Za-z_][\w.-]*:)?body\s*>", xml_text, re.I)
    if not body_open or not body_close or body_close.start() <= body_open.end():
        return [(m.start(), m.end()) for m in P_ELEMENT_RE.finditer(xml_text)]
    start = body_open.end()
    chunk = xml_text[start:body_close.start()]
    return [(start + m.start(), start + m.end()) for m in P_ELEMENT_RE.finditer(chunk)]


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


def inject_edit_markers(html_text, max_paragraphs):
    """Ajoute un petit crayon au début des <p> de <main>, sans modifier la XSLT de l'utilisateur."""
    m = re.search(r"(<main\b[^>]*>)(.*?)(</main>)", html_text, re.I | re.S)
    if not m:
        return html_text, 0
    body = m.group(2)
    counter = 0

    def repl(pm):
        nonlocal counter
        attrs = pm.group(1) or ""
        if counter >= max_paragraphs:
            return pm.group(0)
        n = counter
        counter += 1
        marker = (
            f'<a href="tei-edit://p/{n}" class="tei-edit-marker" '
            f'title="{html_lib.escape(_t("preview.edit_paragraph"), quote=True)}">✎</a> '
        )
        return f"<p{attrs}>{marker}"

    body2 = re.sub(r"<p(\s[^>]*)?>", repl, body, flags=re.I)
    return html_text[:m.start(2)] + body2 + html_text[m.end(2):], counter



LINE_MARKER_RE = re.compile(
    r'(<a\b(?=[^>]*\bclass=["\'][^"\']*\btei-line-marker\b[^"\']*["\'])'
    r'(?=[^>]*\bhref=["\']tei-line://base/(\d+)["\'])[^>]*>)\s*</a>',
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
            # inject_edit_markers ajoute exactement un espace après le crayon.
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

    def select_visible_text_in_paragraph(self, text, descriptor):
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

    def mouseReleaseEvent(self, event):
        # Les vrais liens de l'aperçu (notamment le crayon ✎) gardent leur
        # comportement normal. Un clic sur le texte ordinaire est associé au
        # dernier marqueur du témoin de base placé avant la position du curseur.
        pos = event.position().toPoint()
        href = self.anchorAt(pos)
        super().mouseReleaseEvent(event)
        if href:
            return
        if not self._marker_positions:
            return
        char_pos = self.cursorForPosition(pos).position()
        line = self.line_for_position(char_pos)
        if line is not None:
            self.active_line_ordinal = line
            self.lineActivated.emit(line)


_LXML_TRANSFORM_CACHE = {}

def lxml_available():
    try:
        import lxml.etree  # noqa: F401
        return True
    except Exception:
        return False


def transform_with_xslt(xml_text, xsl_path, params=None):
    """Transformation XSLT 1.0 optimisée.

    Avec lxml, la feuille XSLT compilée est mise en cache tant que le fichier
    n'a pas changé. Sans lxml, on conserve le moteur .NET/PowerShell de secours.
    """
    first_error = None
    try:
        from lxml import etree as LET
        parser = LET.XMLParser(resolve_entities=False, no_network=True, recover=False)
        xml_doc = LET.fromstring(xml_text.encode("utf-8"), parser=parser)
        xp = Path(xsl_path).resolve()
        st = xp.stat()
        cache_key = (str(xp), st.st_mtime_ns, st.st_size)
        transform = _LXML_TRANSFORM_CACHE.get(cache_key)
        if transform is None:
            # Une seule version compilée par chemin suffit ; jeter les anciennes
            # entrées si la feuille a été modifiée sur disque.
            for k in list(_LXML_TRANSFORM_CACHE):
                if k[0] == str(xp):
                    _LXML_TRANSFORM_CACHE.pop(k, None)
            xsl_doc = LET.parse(str(xp), parser=parser)
            transform = LET.XSLT(xsl_doc)
            _LXML_TRANSFORM_CACHE[cache_key] = transform
        xslt_params = {str(k): LET.XSLT.strparam(str(v)) for k, v in (params or {}).items()}
        return str(transform(xml_doc, **xslt_params)), "lxml (XSLT en cache)"
    except Exception as exc:
        first_error = exc

    ps = shutil.which("powershell.exe") or shutil.which("powershell") or shutil.which("pwsh")
    if ps:
        try:
            with tempfile.TemporaryDirectory(prefix="tei_xslt_") as td:
                td = Path(td)
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
        self.dirty_preview = True
        self._last_preview_key = None
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

        frag_box = QWidget()
        self.frag_box = frag_box
        frag_layout = QVBoxLayout(frag_box)
        frag_layout.setContentsMargins(0, 4, 0, 0)
        frag_head = QHBoxLayout()
        self.frag_label = QLabel(_t("fragment.initial"))
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
        frag_head.addWidget(self.fragment_visual_wrap)
        frag_head.addStretch(1)
        frag_head.addWidget(self.reload_btn)
        frag_head.addWidget(self.apply_btn)
        frag_head.addWidget(self.close_fragment_btn)
        frag_layout.addLayout(frag_head)

        # Barre de recherche locale au fragment. Elle apparaît avec Ctrl+F
        # lorsque le focus est dans l’éditeur de paragraphe.
        self.fragment_find_bar = QWidget()
        ff = QHBoxLayout(self.fragment_find_bar)
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
        self.fragment_editor.setPlaceholderText(_t("fragment.placeholder"))
        self.fragment_visual_wrap.setText(_t("source.visual_wrap"))
        self.wrap_element_action.setText(_t("fragment.wrap"))
        self.fragment_completion_action.setText(_t("completion.action"))
        if self.current_paragraph is None:
            self.frag_label.setText(_t("fragment.initial"))
        else:
            spans = paragraph_spans(self.main.editor.toPlainText())
            self.frag_label.setText(_t("fragment.label", index=self.current_paragraph + 1, total=len(spans)))
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
                self.main.navigate_to_base_ordinal(line, move_xml_cursor=True)
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
        QTimer.singleShot(0, lambda n=int(ordinal): self.preview.scroll_to_line(n, center=True))

    def focus_is_in_fragment(self):
        focus = QApplication.focusWidget()
        return bool(
            focus is self.fragment_editor
            or (focus is not None and self.fragment_editor.isAncestorOf(focus))
            or focus is self.fragment_find_box
            or (focus is not None and self.fragment_find_bar.isAncestorOf(focus))
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

    def show_fragment_find(self):
        self.fragment_find_bar.setVisible(True)
        # Si du texte est sélectionné, il devient naturellement la recherche.
        selected = self.fragment_editor.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.fragment_find_box.setText(selected)
        self.fragment_find_box.setFocus()
        self.fragment_find_box.selectAll()

    def hide_fragment_find(self):
        self.fragment_find_bar.setVisible(False)
        self.fragment_find_status.setText("")
        self.fragment_editor.setFocus()

    def _find_fragment(self, backwards=False):
        q = self.fragment_find_box.text()
        if not q:
            self.show_fragment_find()
            return
        found, n, total = find_in_plain_editor(self.fragment_editor, q, backwards=backwards)
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
            QTimer.singleShot(0, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

    def _reset_preview_zoom(self):
        anchor_line = self.current_preview_line()
        self.preview_zoom_steps = 0
        self._apply_preview_zoom_state()
        if anchor_line is not None:
            QTimer.singleShot(0, lambda n=int(anchor_line): self.preview.scroll_to_line(n, center=True))

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
            css = resolve_css_variables(self.css_path.read_text(encoding="utf-8"))
            css += (
                "\n.tei-edit-marker { color:#8a8177; text-decoration:none; font-family:sans-serif; font-size:0.75em; padding-right:0.35em; }"
                "\na.tei-line-marker { color: transparent; text-decoration:none; font-size:0; line-height:0; margin:0; padding:0; white-space:nowrap; }"
            )
            self._cached_css_key = key
            self._cached_css_text = css
        return self._cached_css_text

    def refresh_preview(self, force=False):
        xml_text = self.main.editor.toPlainText()
        if not self.xsl_path.exists() or not self.css_path.exists():
            self.info.setText(_t("preview.files_missing"))
            self.info.setStyleSheet("color:#a14b2f")
            return

        # Empreinte légère : évite de reconstruire le gros QTextDocument quand
        # rien n'a changé (clic sur Actualiser, changement d'onglet, etc.).
        xml_digest = hashlib.blake2b(xml_text.encode("utf-8"), digest_size=12).hexdigest()
        preview_key = (xml_digest, self._file_signature(self.xsl_path), self._file_signature(self.css_path))
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
            html_text, engine = transform_with_xslt(xml_text, self.xsl_path, {"baseWitness": self.main.base_id, "tocTitle": _t("preview.toc")})
            spans = paragraph_spans(xml_text)
            html_text, clickable_lines, text_links = make_line_segments_clickable(html_text)
            html_text, marked = inject_edit_markers(html_text, len(spans))
            css = self._resolved_css_cached()

            # setHtml() et zoomIn()/zoomOut() n’ont pas des sémantiques identiques
            # selon la nature des tailles CSS. Remettre explicitement le widget à
            # sa base avant reconstruction rend le résultat déterministe.
            self._normalize_preview_zoom_before_reload()
            self.preview.document().setDefaultStyleSheet(css)
            self.preview.setHtml(html_text)
            self.preview.rebuild_line_markers()
            self._preview_applied_zoom_steps = 0
            self._reapply_preview_zoom()

            def restore_preview_position(line=old_anchor_line, ratio=old_ratio):
                if line is not None and self.preview.scroll_to_line(int(line), center=True):
                    return
                bar = self.preview.verticalScrollBar()
                if bar.maximum() > 0:
                    bar.setValue(int(round(ratio * bar.maximum())))

            QTimer.singleShot(0, restore_preview_position)
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

    def _line_clicked(self, idx):
        self.preview.active_line_ordinal = int(idx)
        self.main.navigate_to_base_ordinal(idx, move_xml_cursor=True)
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
                    self.main.navigate_to_base_ordinal(int(line), move_xml_cursor=False)
            QTimer.singleShot(0, sync_after_toc)
            return
        if url.scheme() != "tei-edit":
            return
        try:
            idx = int(url.path().strip("/"))
        except Exception:
            return
        self.load_fragment(idx, move_source=True)

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

    def load_fragment(self, idx, move_source=False):
        # Ne jamais remplacer silencieusement un fragment modifié par un
        # autre paragraphe. Le choix est explicite : appliquer, ignorer ou
        # annuler.
        if not self._confirm_fragment_switch(idx):
            return False

        # Recalculer les plages après une éventuelle application du fragment
        # courant : sa longueur a pu changer.
        text = self.main.editor.toPlainText()
        spans = paragraph_spans(text)
        if not (0 <= idx < len(spans)):
            return False
        start, end = spans[idx]
        frag = text[start:end]
        self.current_paragraph = idx
        self.fragment_original = frag
        self.frag_box.setVisible(True)
        self.fragment_editor.blockSignals(True)
        self.fragment_editor.setPlainText(frag)
        self.fragment_editor.blockSignals(False)
        if hasattr(self, "fragment_find_status"):
            self.fragment_find_status.setText("")
        self.frag_label.setText(_t("fragment.label", index=idx+1, total=len(spans)))
        self.apply_btn.setEnabled(True)
        self.reload_btn.setEnabled(True)
        if move_source:
            c = self.main.editor.textCursor()
            c.setPosition(start)
            self.main.editor.setTextCursor(c)
            self.main.sync_panels_to_cursor(True)
        return True

    def reload_fragment(self):
        if self.current_paragraph is not None:
            self.load_fragment(self.current_paragraph, move_source=False)

    def fragment_has_unapplied_changes(self):
        return (
            self.current_paragraph is not None
            and self.fragment_editor.toPlainText() != self.fragment_original
        )

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
        """Réinjecte le fragment dans le XML source. Retourne True en cas de succès."""
        if self.current_paragraph is None:
            return False
        text = self.main.editor.toPlainText()
        spans = paragraph_spans(text)
        idx = self.current_paragraph
        if not (0 <= idx < len(spans)):
            QMessageBox.warning(self, _t("fragment.moved.title"), _t("fragment.moved.text"))
            return False
        start, end = spans[idx]
        if text[start:end] != self.fragment_original:
            r = QMessageBox.question(
                self, _t("fragment.source_changed.title"),
                _t("fragment.source_changed.text"),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if r != QMessageBox.StandardButton.Yes:
                self.load_fragment(idx, move_source=False)
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
        c = QTextCursor(self.main.editor.document())
        c.setPosition(start)
        c.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(frag)
        self.fragment_original = frag
        self.main.editor.setTextCursor(c)
        self.main.sync_panels_to_cursor(True)
        self.dirty_preview = True
        self.refresh_preview()
        # Les plages ont pu changer ; recharge le même numéro ordinal si possible.
        self.load_fragment(min(idx, max(0, len(paragraph_spans(self.main.editor.toPlainText()))-1)), move_source=False)
        return True



class CtrlEConfigDialog(QDialog):
    """Petit éditeur interne pour custom-elements.xml.

    Il évite de déléguer l'ouverture du XML à l'application système par défaut.
    Le fichier est validé comme XML et sa racine doit être <customElements>.
    """
    def __init__(self, path: Path, parent=None):
        super().__init__(parent)
        self.path = Path(path)
        self.setWindowTitle(_t("ctrl_e.config.editor.title"))
        self.resize(760, 560)
        layout = QVBoxLayout(self)
        info = QLabel(_t("ctrl_e.config.editor.path", path=self.path))
        info.setWordWrap(True)
        layout.addWidget(info)
        self.editor = CodeEditor(self)
        self.highlighter = XMLHighlighter(self.editor.document())
        self.editor.setPlainText(self.path.read_text(encoding="utf-8"))
        self.editor.document().setModified(False)
        layout.addWidget(self.editor, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Save).setText(_t("common.save"))
        buttons.button(QDialogButtonBox.StandardButton.Close).setText(_t("common.close"))
        buttons.button(QDialogButtonBox.StandardButton.Save).clicked.connect(self.save_config)
        buttons.rejected.connect(self.close)
        layout.addWidget(buttons)

    def save_config(self):
        text = self.editor.toPlainText()
        try:
            root = ET.fromstring(text)
            if root.tag != "customElements":
                raise ValueError(_t("ctrl_e.config.root_error", file=self.path))
        except Exception as exc:
            QMessageBox.warning(self, _t("ctrl_e.config.editor.invalid.title"), str(exc))
            return False
        try:
            if self.path.exists():
                shutil.copy2(self.path, self.path.with_suffix(self.path.suffix + ".bak"))
            self.path.write_text(text, encoding="utf-8")
            self.editor.document().setModified(False)
            QMessageBox.information(self, _t("ctrl_e.config.editor.saved.title"), _t("ctrl_e.config.editor.saved", path=self.path))
            return True
        except Exception as exc:
            QMessageBox.critical(self, _t("file.save.error.title"), str(exc))
            return False

    def closeEvent(self, event):
        if not self.editor.document().isModified():
            event.accept(); return
        r = QMessageBox.question(
            self, _t("file.unsaved.title"), _t("ctrl_e.config.editor.unsaved"),
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Save,
        )
        if r == QMessageBox.StandardButton.Cancel:
            event.ignore(); return
        if r == QMessageBox.StandardButton.Save and not self.save_config():
            event.ignore(); return
        event.accept()


def _document_attribute(path):
    """Ancien attribut de MainWindow redirigé vers ``self.document``.

    ``path`` est le chemin pointé de l'attribut dans ``DocumentSession``
    (p. ex. ``"lb.spans"``). Ces propriétés assurent la compatibilité pendant
    la restructuration : le code existant continue d'utiliser les anciens noms.
    """
    *parents, leaf = path.split(".")

    def _owner(self):
        obj = self.document
        for name in parents:
            obj = getattr(obj, name)
        return obj

    return property(
        lambda self: getattr(_owner(self), leaf),
        lambda self, value: setattr(_owner(self), leaf, value),
        doc=f"Compatibilité : self.document.{path}",
    )


class MainWindow(WitnessSyncMixin, ProjectActionsMixin, MainMenusMixin, WitnessWorkspaceMixin, DocumentIOMixin, CompletionMixin, ValidationPanelMixin, XPathPanelMixin, QMainWindow):
    # --- État du document ouvert (voir document_session.DocumentSession) ---
    current_path = _document_attribute("path")
    modified = _document_attribute("modified")
    _last_processed_edit_revision = _document_attribute("last_processed_edit_revision")
    _loading_editor_document = _document_attribute("loading")
    _lb_spans = _document_attribute("lb.spans")
    _lb_cache_dirty = _document_attribute("lb.dirty")
    _document_health = _document_attribute("health")
    _last_xml_health_revision = _document_attribute("last_xml_health_revision")
    _last_xml_health_well_formed = _document_attribute("last_xml_health_well_formed")
    _last_rng_result = _document_attribute("last_rng_result")
    _last_rng_revision = _document_attribute("last_rng_revision")
    _last_rng_schema_token = _document_attribute("last_rng_schema_token")
    _last_schema_resolution = _document_attribute("last_schema_resolution")
    _completion_model = _document_attribute("completion_model")
    _completion_model_key = _document_attribute("completion_model_key")
    _completion_resolution = _document_attribute("completion_resolution")
    _completion_resolution_key = _document_attribute("completion_resolution_key")
    _source_completion_context_cache = _document_attribute("completion_context_cache")
    _last_synced_ordinal = _document_attribute("last_synced_ordinal")
    _last_synced_surface = _document_attribute("last_synced_surface")

    def __init__(self, project_path=None):
        super().__init__()
        # Document ouvert : doit exister avant toute affectation des attributs
        # de compatibilité ci-dessus.
        self.document = DocumentSession()
        self.project = load_project(project_path or DEMO_PROJECT)
        remember_recent_project(self.project.path)
        global I18N
        I18N = I18nManager(self.project.translations_dir, self.project.language, self.project.fallback_language)
        set_i18n(I18N)
        app = QApplication.instance()
        if app is not None:
            app.setApplicationName(_t("app.name"))
        self.base_id = self.project.base_witness
        self.witness_configs = list(self.project.witnesses)
        self.witness_labels = {w.id: w.label for w in self.witness_configs}
        escaped_base = re.escape(self.base_id)
        self.lb_base_re = re.compile(
            rf"<(?:[A-Za-z_][\w.-]*:)?lb\b(?=[^>]*\bedRef\s*=\s*(['\"])#{escaped_base}\1)[^>]*?/?>",
            re.IGNORECASE | re.DOTALL,
        )

        self.setWindowTitle(_t("app.window.project", title=self.project.title))
        self.resize(1650, 980)
        self.current_path = None; self.modified = False; self._lb_spans = []; self._lb_cache_dirty = True
        self._sync_from_panel = False; self._last_synced_ordinal = None
        self._force_close = False
        self._replacement_window = None
        self._document_health = "normal"
        self._last_rng_result = None
        self._last_rng_revision = -1
        self._last_rng_schema_token = None
        self._last_schema_resolution = None
        # Suivi des révisions indépendant de la visibilité du panneau.
        # Dès que F8 a été utilisé, les éditions successives déclenchent
        # toujours une nouvelle validation après le délai de frappe.
        self._rng_watch_enabled = False
        self._last_processed_edit_revision = -1
        self._loading_editor_document = False
        self._completion_model = None
        self._completion_model_key = None
        self._completion_resolution = None
        self._completion_resolution_key = None
        self._source_completion_context_cache = XmlContextCache()
        self._fragment_completion_context_cache = XmlContextCache()
        self._xml_health_pool = QThreadPool(self)
        self._xml_health_pool.setMaxThreadCount(1)
        self._xml_health_running = False
        self._xml_health_pending = False
        self._xml_health_worker = None
        self._last_xml_health_revision = -1
        self._last_xml_health_well_formed = None

        # V0.7.0 : les ressources d'un témoin sont facultatives. Un témoin
        # sans fichier d'alignement reste un témoin parfaitement valide ; son
        # panneau existe mais la synchronisation ALTO/base_keys est inactive.
        self.alignment_caches = {}
        self._raw_alignment_caches = {}
        self.witness_items = {}
        self.base_maps = {}
        self.base_by_key = {}
        # Le nombre de lignes attendu par la TEI vient exclusivement du JSON
        # de synchronisation du témoin de base. Un ALTO indépendant n'est pas
        # une synchronisation et ne doit jamais imposer ce nombre.
        self._base_sync_line_count = None
        self._secondary_sync_link_counts = {}
        for w in self.witness_configs:
            alignment_available = has_line_synchronization(w)
            if alignment_available:
                cache = load_json(w.alignment)
                if w.is_base:
                    self._base_sync_line_count = primary_sync_line_count(cache)
                else:
                    self._secondary_sync_link_counts[w.id] = secondary_sync_link_count(cache)
            else:
                cache = {"meta": {"witness": w.id, "role": w.role}, "pages": []}
                if not w.is_base:
                    self._secondary_sync_link_counts[w.id] = 0
            self._raw_alignment_caches[w.id] = cache
            cache = apply_witness_alto_policy(
                cache, getattr(w, "alto_source_type", "auto"),
                [x.path for x in getattr(w, "alto_files", ())], self.project.root_dir,
                w.id, w.role,
                strict_no_ordinal=(getattr(w, 'image_source_type', '') == 'iiif'),
            )
            cache = apply_witness_image_policy(
                cache, getattr(w, "image_source_type", "auto"),
                getattr(w, "image_source_value", None), self.project.root_dir,
                getattr(w, "image_files", ()), w.id,
                getattr(w, 'iiif_selection_mode', 'all'),
                getattr(w, 'iiif_selected_canvases', ()),
                getattr(w, 'iiif_ocr_links', ()),
                getattr(w, 'iiif_page_links', ()),
            )
            if getattr(w, 'iiif_local_copy', False) and w.image_source_type == 'iiif':
                cache = apply_working_copy(cache, self.project.root_dir, w.id)
            self.alignment_caches[w.id] = cache
            if w.is_base:
                items, by_key = flatten_primary(cache)
                self.witness_items[w.id] = items
                self.base_by_key = by_key
            else:
                items, by_base = flatten_secondary(cache)
                self.witness_items[w.id] = items
                self.base_maps[w.id] = by_base
        self.base_items = self.witness_items.get(self.base_id, [])
        base_cfg = self.project.witness_by_id[self.base_id]
        # V0.8.4 : un fichier JSON vide/provisoire n'active pas le mode ligne.
        # Le nombre est mesuré avant toute superposition ALTO, afin qu'un ALTO
        # indépendant ne puisse jamais être pris pour une synchronisation TEI.
        self.base_alignment_available = bool(
            has_line_synchronization(base_cfg) and (self._base_sync_line_count or 0) > 0
        )

        # V0.7.9.1 : sans synchronisation ligne-à-ligne, la page — et non une
        # pseudo-ligne ALTO — est l'unité de navigation. L'ALTO reste disponible
        # pour dessiner tous les cadres de la page, mais ne détermine pas un crop.
        self.witness_display_items = {}
        for w in self.witness_configs:
            cache = self.alignment_caches.get(w.id, {})
            line_sync = self.base_alignment_available and (
                w.is_base or self._secondary_sync_link_counts.get(w.id, 0) > 0
            )
            if line_sync:
                display = self.witness_items.get(w.id, [])
            else:
                display = page_navigation_items(cache, self.project.root_dir)
                if not display:
                    display = self.witness_items.get(w.id, []) or image_only_items(cache, self.project.root_dir)
            self.witness_display_items[w.id] = display

        # La colonne manuscrits n'a aucune raison d'occuper la moitié de l'écran
        # lorsqu'aucune page d'aucun témoin ne possède réellement de source
        # d'image. ALTO et synchronisation peuvent parfaitement exister seuls.
        self.has_any_images = any(
            page_image_source(page, self.project.root_dir).available
            for cache in self.alignment_caches.values()
            for page in (cache.get("pages", []) or [])
        )
        self.expected_base_lines = self._base_sync_line_count if self.base_alignment_available else None
        self._last_synced_surface = None

        self.editor = CodeEditor()
        # Le QTextDocument appartient au document ouvert, non à l'éditeur.
        self.document.text_document = QTextDocument(self)
        self.editor.set_text_document(self.document.text_document)
        self.highlighter = XMLHighlighter(self.editor.document())
        self.formatted_view = FormattedEditionWidget(self)
        self.editor.attribute_completion_provider = self._auto_attribute_choices
        self.formatted_view.fragment_editor.attribute_completion_provider = self._auto_attribute_choices
        # Invalidation incrémentale : les points lexicaux antérieurs à l'édition
        # restent valides et accélèrent les Ctrl+Espace suivants.
        self.editor.document().contentsChange.connect(self._source_contents_changed)
        self.formatted_view.fragment_editor.document().contentsChange.connect(
            lambda position, _removed, _added: self._fragment_completion_context_cache.invalidate_from(position)
        )

        self.source_wrap_element_action = QAction(_t("fragment.wrap"), self.editor)
        self.source_wrap_element_action.setShortcut(QKeySequence("Ctrl+E"))
        self.source_wrap_element_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.source_wrap_element_action.triggered.connect(
            lambda: self.formatted_view.wrap_selection_with_element(self.editor, _t("ctrl_e.where.source"))
        )
        self.editor.addAction(self.source_wrap_element_action)

        self.source_completion_action = QAction(_t("completion.action"), self.editor)
        self.source_completion_action.setShortcut(QKeySequence("Ctrl+Space"))
        self.source_completion_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self.source_completion_action.triggered.connect(lambda: self.show_rng_completion(self.editor))
        self.editor.addAction(self.source_completion_action)

        self.left_tabs = QTabWidget()

        # Vue XML source : la case n'agit que sur l'affichage. Elle ne modifie
        # ni le texte, ni les numéros de lignes, ni les offsets utilisés par les
        # synchronisations et validations.
        self.source_tab = QWidget()
        source_layout = QVBoxLayout(self.source_tab)
        source_layout.setContentsMargins(0, 0, 0, 0)
        source_layout.setSpacing(2)
        source_options = QHBoxLayout()
        source_options.setContentsMargins(4, 2, 4, 0)
        self.source_visual_wrap = QCheckBox(_t("source.visual_wrap"), self.source_tab)
        wrap_setting = _settings().value("sourceVisualWrap", False)
        if isinstance(wrap_setting, str):
            wrap_setting = wrap_setting.strip().lower() in {"1", "true", "yes", "on"}
        self.source_visual_wrap.setChecked(bool(wrap_setting))
        self.editor.set_visual_wrap(bool(wrap_setting))
        self.source_visual_wrap.toggled.connect(self._set_source_visual_wrap)
        source_options.addWidget(self.source_visual_wrap)
        source_options.addStretch(1)
        source_layout.addLayout(source_options)
        source_layout.addWidget(self.editor, 1)

        self.left_tabs.addTab(self.source_tab, _t("tab.xml_source"))
        self.left_tabs.addTab(self.formatted_view, _t("tab.preview"))
        self._previous_left_tab_index = 0
        self.left_tabs.currentChanged.connect(self._left_tab_changed)
        self._last_save_context = "source"
        QApplication.instance().focusChanged.connect(self._track_edit_focus)

        # Each witness retains an independently resizable panel inside a scroll
        # area.  A naked vertical splitter used to squeeze the 4th manuscript
        # into an unusable sliver as the window height stayed fixed.
        self.panels = {}
        self._witness_image_available = {}
        self.witness_splitter = QSplitter(Qt.Orientation.Vertical)
        self.witness_splitter.setChildrenCollapsible(True)
        # The former fixed 560-px minimum prevented shrinking the manuscript
        # side and therefore constrained the editor/manuscript balance.
        self.witness_splitter.setMinimumWidth(0)
        self.witness_horizontal_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.witness_grid_splitter = QSplitter(Qt.Orientation.Vertical)
        self._grid_rows = [QSplitter(Qt.Orientation.Horizontal), QSplitter(Qt.Orientation.Horizontal)]
        for row in self._grid_rows:
            self.witness_grid_splitter.addWidget(row)
        self.workspace_root = QWidget(self)
        workspace_layout = QVBoxLayout(self.workspace_root)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)
        for view in (self.witness_splitter, self.witness_horizontal_splitter,
                     self.witness_grid_splitter):
            workspace_layout.addWidget(view, 1)
        self.witness_horizontal_splitter.hide()
        self.witness_grid_splitter.hide()
        self.witness_scroll = QScrollArea(self)
        self.witness_scroll.setWidgetResizable(True)
        self.witness_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.witness_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.witness_scroll.setMinimumWidth(0)
        self.witness_scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.witness_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        # Stable viewport widget: changing orientation never calls
        # QScrollArea.setWidget() again (which would DELETE the old widget).
        self.witness_scroll.setWidget(self.workspace_root)
        for w in self.witness_configs:
            panel = ManuscriptPanel(
                w.id,
                w.label,
                self.witness_display_items[w.id],
                self.base_maps.get(w.id),
                is_base=w.is_base,
                base_label=self.witness_labels[self.base_id],
                project_root=self.project.root_dir,
                sync_enabled=((self.base_alignment_available and bool(self.base_items)) if w.is_base
                              else bool(self.base_alignment_available and self._secondary_sync_link_counts.get(w.id, 0) > 0)),
            )
            self.panels[w.id] = panel
            if not w.is_base and has_line_synchronization(w) and self.base_alignment_available:
                # A configured JSON is not necessarily a line synchronization.
                # Make the fallback visible instead of letting the user infer
                # from colored ALTO frames that line alignment is operational.
                links = self._secondary_sync_link_counts.get(w.id, 0)
                if links == 0:
                    problem = _t('manuscript.sync.no_base_keys')
                elif not set(self.base_maps.get(w.id) or {}).intersection(self.base_by_key):
                    problem = _t('manuscript.sync.unmatched_base_keys')
                else:
                    problem = ''
                if problem:
                    panel.sync_issue.setText(problem)
                    panel.sync_issue.setToolTip(problem)
                    panel.sync_issue.show()
            cache = self.alignment_caches.get(w.id, {})
            unmatched_layout = int((cache.get('meta') or {}).get('iiif_unassociated_layout_count') or 0)
            if unmatched_layout:
                # Optional OCR geometry must never hide the corresponding
                # IIIF manuscript. Explain why its frames are not yet drawn.
                message = _t('manuscript.iiif_unassociated_layout.tip', count=unmatched_layout)
                panel.header.setToolTip(message)
                panel.status.setToolTip(message)
            self._witness_image_available[w.id] = any(
                page_image_source(page, self.project.root_dir).available
                for page in (cache.get("pages", []) or [])
            )
            self.witness_splitter.addWidget(panel)
            panel.markPageRequested.connect(self._mark_page_in_tei)
            panel.splitFolioRequested.connect(self._split_double_folio)
            panel.maximizeRequested.connect(self._toggle_witness_panel_maximize)
            panel.detachRequested.connect(self._toggle_detached_witness)
            if w.is_base:
                # Connect once, even if synchronization becomes active later.
                panel.primaryNavigate.connect(self._primary_panel_navigate)
            if panel.items and not panel.sync_enabled:
                QTimer.singleShot(0, panel.reload)
        self.base_panel = self.panels[self.base_id]
        self.witness_splitter.splitterMoved.connect(self._remember_witness_splitter_sizes)
        self._witness_maximized_id = None
        self._witness_sizes_before_maximize = None
        self._witness_display_order = self._load_witness_display_order()
        self._reordering_witness_panels = False
        self._changing_workspace = False
        self._closing_workspace = False
        self._workspace_before_maximize = None
        self._detached_windows = {}
        self._workspace_mode = self._load_workspace_mode()
        self._visible_witness_ids = self._load_visible_witness_ids()
        self.witness_horizontal_splitter.splitterMoved.connect(self._remember_workspace_sizes)
        self.witness_grid_splitter.splitterMoved.connect(self._remember_workspace_sizes)
        for row in self._grid_rows:
            row.splitterMoved.connect(self._remember_workspace_sizes)

        # Colonne gauche : les deux vues de l'édition + panneau de validation
        # RELAX NG rétractable. Le panneau reste fermé tant qu'il n'est pas
        # utile, afin de ne pas pénaliser les petits écrans.
        self.validation_panel = self._build_validation_panel()
        self.xpath_panel = self._build_xpath_panel()
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.addWidget(self.left_tabs)
        self.left_splitter.addWidget(self.validation_panel)
        self.left_splitter.addWidget(self.xpath_panel)
        self.left_splitter.setStretchFactor(0, 1)
        self.left_splitter.setStretchFactor(1, 0)
        self.left_splitter.setStretchFactor(2, 0)
        self.left_splitter.setSizes([760, 0, 0])
        # Do not let sizeHint/minimums from the XML widgets force a 50:50
        # layout. The splitter handle may be dragged down to ~20% editor width.
        self.left_splitter.setMinimumWidth(140)
        self.left_tabs.setMinimumWidth(0)

        # ``witness_splitter`` stays available to the sizing/maximize logic;
        # ``manuscript_scroll`` now points to the actual scroll container.
        self.manuscript_scroll = self.witness_scroll
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.left_splitter)
        splitter.addWidget(self.witness_scroll)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        splitter.setChildrenCollapsible(False)
        splitter.setHandleWidth(6)
        self.main_splitter = splitter
        self._restoring_main_splitter_ratio = False
        splitter.splitterMoved.connect(self._remember_main_splitter_ratio)
        self._main_splitter_last_visible_sizes = [780, 870]
        self.setCentralWidget(splitter)
        self._apply_witness_visibility(initial=True)
        QTimer.singleShot(0, self._restore_main_splitter_ratio)
        QTimer.singleShot(0, self._restore_detached_witnesses)

        self._build_toolbar()
        self.xml_status = QLabel(_t("status.xml.initial")); self.cursor_status = QLabel(_t("status.cursor", line=1, column=1))
        self.structure_status = QLabel(
            _t("status.structure.expected", base=self.base_id, count=self.expected_base_lines)
            if self.expected_base_lines is not None
            else _t("status.structure.no_alignment", base=self.base_id)
        )
        self.rng_status = QLabel(_t("rng.status.none") if self.project.schema_mode == "none" else _t("rng.status.pending"))
        self.schematron_status = QLabel("")
        self.statusBar().addWidget(self.xml_status,1)
        self.statusBar().addPermanentWidget(self.rng_status)
        self.statusBar().addPermanentWidget(self.schematron_status)
        self.statusBar().addPermanentWidget(self.structure_status)
        self.statusBar().addPermanentWidget(self.cursor_status)
        self._set_document_health("normal")

        self.sync_timer = QTimer(self); self.sync_timer.setSingleShot(True); self.sync_timer.setInterval(55); self.sync_timer.timeout.connect(self.sync_panels_to_cursor)
        # Le contrôle automatique reste systématique après une courte pause,
        # mais son parse XML est exécuté hors du thread graphique (V0.5.5).
        self.validate_timer = QTimer(self); self.validate_timer.setSingleShot(True); self.validate_timer.setInterval(650); self.validate_timer.timeout.connect(self.validate_editor)
        self.rng_refresh_timer = QTimer(self)
        self.rng_refresh_timer.setSingleShot(True)
        self.rng_refresh_timer.setInterval(1250)
        self.rng_refresh_timer.timeout.connect(self._auto_refresh_rng)
        self.editor.cursorPositionChanged.connect(self._cursor_changed)
        # Une opération Qt qui modifie le QTextDocument directement (édition
        # de fragment, QTextCursor, undo/redo) doit invalider le RNG aussi.
        # Le garde de révision dans _text_changed évite un double traitement.
        self.editor.textChanged.connect(self._text_changed)
        self.editor.document().contentsChanged.connect(self._text_changed)
        self.open_path(self.project.edition)
        remember_open_project(self.project.path)

    def _track_edit_focus(self, old, new):
        if new is None:
            return
        if (
            new is self.formatted_view.fragment_editor
            or self.formatted_view.fragment_editor.isAncestorOf(new)
            or new is self.formatted_view.fragment_find_box
            or self.formatted_view.fragment_find_bar.isAncestorOf(new)
        ):
            self._last_save_context = "fragment"
        elif new is self.editor or self.editor.isAncestorOf(new):
            self._last_save_context = "source"
        elif (
            new is self.formatted_view.preview
            or self.formatted_view.preview.isAncestorOf(new)
            or new is self.formatted_view.preview_find_box
            or self.formatted_view.preview_find_bar.isAncestorOf(new)
        ):
            self._last_save_context = "preview"

    def _make_action(self, text, shortcut, slot, tip=""):
        a = QAction(text, self)
        if shortcut:
            a.setShortcut(QKeySequence(shortcut))
        a.triggered.connect(slot)
        if tip:
            a.setToolTip(tip)
        return a

    def _set_source_visual_wrap(self, enabled):
        self.editor.set_visual_wrap(bool(enabled))
        _settings().setValue("sourceVisualWrap", bool(enabled))

    def _show_bottom_panel(self, panel, height=230):
        """N'affiche qu'un panneau inférieur à la fois."""
        other = self.xpath_panel if panel is self.validation_panel else self.validation_panel
        other.setVisible(False)
        panel.setVisible(True)
        total = max(450, self.left_splitter.height())
        bottom = min(max(150, int(height)), max(150, total // 2))
        sizes = [max(240, total - bottom), 0, 0]
        index = self.left_splitter.indexOf(panel)
        if 0 <= index < len(sizes):
            sizes[index] = bottom
        self.left_splitter.setSizes(sizes)

    def format_xml_source(self):
        """Indente les seules zones XML/TEI dont la mise en forme est sûre.

        Le formateur travaille sur les blancs structurels uniquement. Les zones
        mixtes, ``xml:space=preserve`` et tout contexte direct contenant ``<lb/>``
        sont protégés. Une règle ``formatting`` de custom-elements.xml peut
        raffiner la classification, sans contourner ces protections absolues.
        """
        source = self.editor.toPlainText()
        if not source.strip():
            return

        custom = self._custom_completion_config()
        model = None
        try:
            resolution = self._resolve_completion_schema(source)
            if (self.project.schema_mode != "none" and not resolution.error
                    and resolution.schema_path is not None):
                model = self._completion_model_for_schema(resolution.schema_path)
        except Exception:
            # Le formateur reste utilisable avec les seules règles projet, mais
            # il s'abstiendra sur toute zone dont la structure reste ambiguë.
            model = None

        result = format_tei_xml(source, rng_model=model, custom_config=custom)
        if result.error:
            self.statusBar().showMessage(
                _t("format_xml.invalid", error=result.error), 6000
            )
            return
        if not result.changed:
            self.statusBar().showMessage(_t("format_xml.no_change"), 3500)
            return

        old_cursor = self.editor.textCursor()
        old_pos = old_cursor.position()
        old_anchor = old_cursor.anchor()
        new_pos = result.map_position(old_pos)
        new_anchor = result.map_position(old_anchor)

        # Les remplacements sont appliqués du bas vers le haut dans un seul bloc
        # Undo. Le moteur de paires est suspendu : aucun QName n'est touché et
        # une réinterprétation de dizaines de changements de blancs serait à la
        # fois inutile et risquée.
        previous_guard = self.editor._pair_edit_guard
        self.editor._pair_edit_guard = True
        edit = QTextCursor(self.editor.document())
        edit.beginEditBlock()
        try:
            for repl in reversed(result.replacements):
                edit.setPosition(repl.start)
                edit.setPosition(repl.end, QTextCursor.MoveMode.KeepAnchor)
                edit.insertText(repl.text)
        finally:
            edit.endEditBlock()
            self.editor._pair_edit_guard = previous_guard
            self.editor._pair_previous_text = self.editor.toPlainText()

        restored = QTextCursor(self.editor.document())
        restored.setPosition(max(0, min(self.editor.document().characterCount() - 1, new_anchor)))
        restored.setPosition(
            max(0, min(self.editor.document().characterCount() - 1, new_pos)),
            QTextCursor.MoveMode.KeepAnchor if new_pos != new_anchor else QTextCursor.MoveMode.MoveAnchor,
        )
        self.editor.setTextCursor(restored)
        self.editor.ensureCursorVisible()
        self.statusBar().showMessage(
            _t("format_xml.done", count=result.formatted_elements), 3500
        )

    def close_project(self):
        """Ferme le projet courant sans quitter Varians.

        Le projet reste dans les récents mais ne sera plus rouvert au prochain
        démarrage, ce qui distingue explicitement « fermer le projet » de
        « quitter l'application ».
        """
        if not self.maybe_save():
            return False
        forget_open_project()
        new_window = WelcomeWindow()
        self._replacement_window = new_window
        new_window.showMaximized()
        self._force_close = True
        self.close()
        return True

    def _replace_with_project(self, project_path):
        """Recharge l'application sur un autre project.xml après garde-fou de sauvegarde."""
        if not self.maybe_save():
            return False
        try:
            new_window = MainWindow(Path(project_path))
        except Exception as exc:
            QMessageBox.critical(self, _t("project.open_error"), str(exc))
            return False
        self._replacement_window = new_window
        new_window.showMaximized()
        self._force_close = True
        self.close()
        return True

    def open_ctrl_e_config(self):
        """Édite en interne le fichier custom-elements.xml réellement utilisé.

        Ne dépend pas de l'association système des fichiers .xml (qui ouvre
        fréquemment un navigateur sous Windows).
        """
        custom_file = self.project.custom_elements
        if not custom_file.exists():
            try:
                custom_file.parent.mkdir(parents=True, exist_ok=True)
                custom_file.write_text(
                    '<?xml version="1.0" encoding="UTF-8"?>\n'
                    '<customElements>\n'
                    '  <element name="rdg">\n'
                    '    <attribute name="wit"/>\n'
                    '  </element>\n'
                    '</customElements>\n',
                    encoding="utf-8",
                )
            except Exception as exc:
                QMessageBox.warning(self, _t("ctrl_e.config.create_error.title"), _t("ctrl_e.config.create_error", error=exc))
                return
        dlg = CtrlEConfigDialog(custom_file, self)
        dlg.exec()
        self.statusBar().showMessage(_t("status.ctrl_e.config", path=custom_file), 6000)

    def _set_document_health(self, state):
        """Signale visuellement la santé XML dans les deux onglets.

        malformed = rouge pâle ; rng_invalid = orange pâle ; normal = thème Qt.
        Le rouge est prioritaire : un XML mal formé n'est pas validable en RNG.
        """
        state = state if state in {"normal", "malformed", "rng_invalid"} else "normal"
        self._document_health = state
        tabbar = self.left_tabs.tabBar()
        if state == "malformed":
            tabbar.setStyleSheet(
                "QTabBar::tab { background:#f6d2d2; } "
                "QTabBar::tab:selected { background:#efbcbc; }"
            )
            tip = _t("xml.health.malformed.tooltip")
        elif state == "rng_invalid":
            tabbar.setStyleSheet(
                "QTabBar::tab { background:#f8e3bd; } "
                "QTabBar::tab:selected { background:#f2d59f; }"
            )
            tip = _t("xml.health.rng_invalid.tooltip")
        else:
            tabbar.setStyleSheet("")
            tip = ""
        for i in range(self.left_tabs.count()):
            self.left_tabs.setTabToolTip(i, tip)

    def _set_title(self):
        name = self.current_path.name if self.current_path else _t("app.untitled"); mark = " *" if self.modified else ""
        self.setWindowTitle(_t("app.window.file", project=self.project.title, name=name, mark=mark))

    @Slot(int, int, int)
    def _source_contents_changed(self, position, chars_removed, chars_added):
        """Invalide seulement ce que l'édition rend réellement obsolète."""
        self._source_completion_context_cache.invalidate_from(position)
        lb = self.document.lb
        if lb.dirty:
            return
        inserted = ""
        if chars_added:
            start = max(0, int(position))
            cursor = QTextCursor(self.editor.document())
            cursor.setPosition(start)
            cursor.setPosition(start + max(0, int(chars_added)), QTextCursor.MoveMode.KeepAnchor)
            inserted = cursor.selectedText()
        lb.apply_edit(position, chars_removed, chars_added, inserted)

    def _set_lb_spans(self, spans):
        self.document.lb.set(spans)
        n = len(self.document.lb.spans)
        if self.expected_base_lines is None:
            self.structure_status.setText(_t("status.structure.free", base=self.base_id, count=n))
            self.structure_status.setStyleSheet("color:#746b61")
        elif n == self.expected_base_lines:
            self.structure_status.setText(_t("status.structure.ok", base=self.base_id, count=n)); self.structure_status.setStyleSheet("color:#376b3c")
        else:
            self.structure_status.setText(_t("status.structure.changed", base=self.base_id, count=n, expected=self.expected_base_lines)); self.structure_status.setStyleSheet("color:#a14b2f;font-weight:600")

    def _rebuild_lb_cache(self, text=None):
        if text is None:
            text = self.editor.toPlainText()
        self._set_lb_spans(LbIndex.scan(text, self.lb_base_re))

    def lb_spans(self):
        if self.document.lb.dirty:
            self._rebuild_lb_cache()
        return self.document.lb.spans

    def ordinal_at_position(self, position):
        self.lb_spans()
        return self.document.lb.ordinal_at(position)

    def ordinal_at_cursor(self):
        return self.ordinal_at_position(self.editor.textCursor().position())

    def _xml_occurrences_in_paragraph(self, text, paragraph_index):
        pattern = _xml_selection_pattern(text)
        if not pattern:
            return []
        source = self.editor.toPlainText()
        spans = paragraph_spans(source)
        try:
            start, end = spans[int(paragraph_index)]
        except (IndexError, TypeError, ValueError):
            return []
        try:
            matches = list(re.finditer(pattern, source[start:end], flags=re.DOTALL))
        except re.error:
            return []
        result = []
        for match in matches:
            a, b = start + match.start(), start + match.end()
            # Écarter les occurrences qui ne sont visibles que dans un nom de
            # balise ou une valeur d'attribut. Une sélection traversant un lb
            # break=no reste admise car son premier caractère est du texte.
            if position_inside_xml_markup(source, a):
                continue
            result.append((a, b))
        return result

    def _source_selection_descriptor(self, text, selection_start):
        source = self.editor.toPlainText()
        spans = paragraph_spans(source)
        pidx = containing_span_index(spans, selection_start)
        if pidx is None:
            return None
        occurrences = self._xml_occurrences_in_paragraph(text, pidx)
        occ = occurrence_index_for_position(occurrences, selection_start)
        start, _end = spans[pidx]
        # Offset visible approximatif, utilisé uniquement comme repli si la
        # transformation XSLT a modifié le nombre d'occurrences.
        rel = len(_selection_xml_to_visible_text(source[start:int(selection_start)]))
        return {"paragraph": pidx, "occurrence": occ, "relative": rel}

    def _select_xml_text_in_paragraph(self, text, descriptor):
        if not descriptor:
            return False
        pidx = descriptor.get("paragraph")
        occurrences = self._xml_occurrences_in_paragraph(text, pidx)
        source = self.editor.toPlainText()
        spans = paragraph_spans(source)
        target = None
        try:
            pstart, pend = spans[int(pidx)]
        except (IndexError, TypeError, ValueError):
            return False
        # Pour le repli positionnel, on approxime l'offset visible en balayant
        # les occurrences candidates ; l'index d'occurrence reste prioritaire.
        if descriptor.get("relative") is not None and occurrences:
            wanted = int(descriptor.get("relative") or 0)
            target = min(
                occurrences,
                key=lambda ab: abs(len(_selection_xml_to_visible_text(source[pstart:ab[0]])) - wanted),
            )[0]
        chosen = choose_occurrence(occurrences, descriptor.get("occurrence"), target)
        if not chosen:
            return False
        a, b = chosen
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(a)
        cursor.setPosition(b, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()
        return True

    def _select_xml_text_near_ordinal(self, text, ordinal=None):
        """Projette une sélection de l'aperçu dans la source XML.

        Si le texte traverse un lb break=no, la sélection XML inclut la balise
        et les blancs de mise en forme intermédiaires : un QTextCursor ne peut
        pas sélectionner deux fragments disjoints.
        """
        pattern = _xml_selection_pattern(text)
        if not pattern:
            return False
        source = self.editor.toPlainText()
        try:
            matches = list(re.finditer(pattern, source, flags=re.DOTALL))
        except re.error:
            return False
        if not matches:
            return False
        anchor = self.editor.textCursor().position()
        spans = self.lb_spans()
        if ordinal is not None and spans:
            n = max(0, min(len(spans) - 1, int(ordinal)))
            anchor = spans[n][0]
        match = min(matches, key=lambda m: abs(m.start() - anchor))
        cursor = QTextCursor(self.editor.document())
        cursor.setPosition(match.start())
        cursor.setPosition(match.end(), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()
        return True

    def _cursor_changed(self):
        c=self.editor.textCursor(); self.cursor_status.setText(_t("status.cursor", line=c.blockNumber()+1, column=c.positionInBlock()+1))
        if not self._sync_from_panel: self.sync_timer.start()

    def _text_changed(self):
        """Invalide tout diagnostic antérieur, quel que soit le panneau actif.

        Le document Qt notifie aussi les modifications par QTextCursor et les
        undo/redo. Une révision n'est traitée qu'une fois, même si les deux
        signaux Qt (document et widget) arrivent pour la même modification.
        """
        if getattr(self, '_loading_editor_document', False):
            return
        revision = self.editor.document().revision()
        if revision == self._last_processed_edit_revision:
            return
        self._last_processed_edit_revision = revision
        self.modified = True
        self._set_title()
        self.validate_timer.start()
        self._last_rng_result = None
        self._last_rng_revision = -1
        self._last_rng_schema_token = None
        if getattr(self.project, 'schema_mode', 'auto') != 'none' and hasattr(self, 'rng_status'):
            self.rng_status.setText(_t('rng.status.modified'))
            self.rng_status.setStyleSheet('color:#a06a20')
            if hasattr(self, 'validation_table'):
                self._clear_validation_table()
                self.validation_summary.setText(_t('rng.panel.stale'))
            # Le panneau a déjà été ouvert : continuer à recalculer même
            # lorsqu'un autre panneau/onglet est actuellement affiché.
            if self._rng_watch_enabled and hasattr(self, 'rng_refresh_timer'):
                self.rng_refresh_timer.start()
        if hasattr(self, 'formatted_view'):
            self.formatted_view.source_changed()

    def _left_tab_changed(self, index):
        if not hasattr(self, "formatted_view"):
            return
        previous = getattr(self, "_previous_left_tab_index", 0)
        self._previous_left_tab_index = index

        if self.left_tabs.widget(index) is self.formatted_view:
            # XML -> XSLT : la chaîne seule ne suffit pas ("qui" peut apparaître
            # plusieurs fois). On transporte aussi le paragraphe et le rang de
            # l'occurrence à l'intérieur de ce paragraphe.
            source_cursor = self.editor.textCursor()
            source_pos = source_cursor.selectionStart() if source_cursor.hasSelection() else source_cursor.position()
            ordinal = self.ordinal_at_position(source_pos)
            selected_visible = (
                _selection_xml_to_visible_text(source_cursor.selectedText())
                if source_cursor.hasSelection() else ""
            )
            descriptor = (
                self._source_selection_descriptor(selected_visible, source_pos)
                if selected_visible else None
            )
            self.formatted_view.became_visible()

            def restore_preview_context(n=ordinal, selected=selected_visible, desc=descriptor):
                if selected and desc and self.formatted_view.preview.select_visible_text_in_paragraph(selected, desc):
                    return
                if selected and self.formatted_view.preview.select_visible_text_near_line(selected, n):
                    return
                if n is not None:
                    self.formatted_view.scroll_to_t1_line(n)

            QTimer.singleShot(20, restore_preview_context)
            return

        if index == 0 and previous == 1:
            # XSLT -> XML : même descripteur positionnel dans l'autre sens.
            preview_cursor = self.formatted_view.preview.textCursor()
            has_selection = preview_cursor.hasSelection()
            selected_visible = (
                preview_cursor.selectedText().replace("\u2060", "")
                if has_selection else ""
            )
            descriptor = (
                self.formatted_view.preview.selection_descriptor(selected_visible, preview_cursor.selectionStart())
                if has_selection and selected_visible else None
            )
            ordinal = None
            if has_selection:
                ordinal = self.formatted_view.preview.line_for_position(preview_cursor.selectionStart())
            if ordinal is None:
                ordinal = self.formatted_view.current_preview_line()
            if ordinal is not None:
                self.navigate_to_base_ordinal(ordinal, move_xml_cursor=True)

            def restore_xml_context(selected=selected_visible, n=ordinal, desc=descriptor):
                if selected and desc and self._select_xml_text_in_paragraph(selected, desc):
                    return
                if selected and self._select_xml_text_near_ordinal(selected, n):
                    return
                self.editor.setFocus()

            QTimer.singleShot(0, restore_xml_context)

    def _apply_xml_health_result(self, well_formed, line=0, column=0, error="", spans=None, show_message=False):
        if not well_formed:
            where = f" — ligne {line}, colonne {column + 1}" if line else ""
            msg = _t("xml.invalid", where=where, error=error)
            self.xml_status.setText(msg); self.xml_status.setStyleSheet("color:#a13d32")
            self._set_document_health("malformed")
            if show_message:
                QMessageBox.warning(self, _t("xml.invalid.title"), msg)
            return False
        self.xml_status.setText(_t("xml.valid")); self.xml_status.setStyleSheet("color:#376b3c")
        if spans is not None:
            self._set_lb_spans(spans)
        current_revision = self.editor.document().revision()
        if (
            self._last_rng_revision == current_revision
            and self._last_rng_result is not None
            and self._last_rng_result.well_formed
            and not self._last_rng_result.valid
        ):
            self._set_document_health("rng_invalid")
        else:
            self._set_document_health("normal")
        return True

    def validate_text(self, show_message=False, *, text=None, revision=None):
        """Contrôle synchrone pour les opérations exigeant une réponse immédiate.

        V0.5.6 accepte un instantané déjà extrait de l'éditeur afin que Ctrl+S ne
        recopie pas plusieurs fois un gros document. Si le contrôle automatique a
        déjà validé exactement la révision courante, la sauvegarde peut réutiliser
        directement ce résultat sans reparsing XML.
        """
        revision = self.editor.document().revision() if revision is None else int(revision)
        if revision == self._last_xml_health_revision and self._last_xml_health_well_formed is not None:
            return bool(self._last_xml_health_well_formed)
        text = self.editor.toPlainText() if text is None else text
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            line, col = getattr(exc, "position", (0, 0)) or (0, 0)
            self._last_xml_health_revision = revision
            self._last_xml_health_well_formed = False
            return self._apply_xml_health_result(False, line, col, str(exc), None, show_message)
        spans = [(m.start(), m.end()) for m in self.lb_base_re.finditer(text)]
        self._last_xml_health_revision = revision
        self._last_xml_health_well_formed = True
        return self._apply_xml_health_result(True, spans=spans, show_message=show_message)

    def validate_editor(self):
        """Contrôle automatique asynchrone après une pause de saisie."""
        revision = self.editor.document().revision()
        if revision == self._last_xml_health_revision:
            return
        if self._xml_health_running:
            self._xml_health_pending = True
            return
        text = self.editor.toPlainText()
        self._xml_health_running = True
        self._xml_health_pending = False
        worker = XmlHealthWorker(revision, text, self.lb_base_re)
        self._xml_health_worker = worker
        worker.signals.finished.connect(self._async_xml_health_finished)
        self._xml_health_pool.start(worker)

    @Slot(int, bool, int, int, str, object)
    def _async_xml_health_finished(self, revision, well_formed, line, column, error, spans):
        self._xml_health_running = False
        self._xml_health_worker = None
        current_revision = self.editor.document().revision()
        if revision == current_revision:
            self._last_xml_health_revision = revision
            self._last_xml_health_well_formed = bool(well_formed)
            self._apply_xml_health_result(well_formed, line, column, error, spans, False)
        # Si le document a changé pendant un contrôle exceptionnellement long
        # et que le timer a déjà expiré, programmer une nouvelle passe courte.
        if (self._xml_health_pending or revision != current_revision) and not self.validate_timer.isActive():
            self._xml_health_pending = False
            QTimer.singleShot(180, self.validate_editor)

    def _focus_inside(self, widget):
        focus = QApplication.focusWidget()
        return bool(focus is widget or (focus is not None and widget.isAncestorOf(focus)))

    def focus_find(self):
        # Ctrl+F est contextuel aux trois espaces d'édition/lecture.
        if self.formatted_view.focus_is_in_fragment():
            self.formatted_view.show_fragment_find()
            return
        if self.left_tabs.currentWidget() is self.formatted_view:
            self.formatted_view.show_preview_find()
            return
        selected = self.editor.textCursor().selectedText().strip()
        if selected and "\u2029" not in selected and len(selected) <= 120:
            self.find_box.setText(selected)
        self.find_box.setFocus()
        self.find_box.selectAll()

    def _find_source(self, backwards=False):
        q = self.find_box.text()
        if not q:
            self.find_box.setFocus()
            return
        found, n, total = find_in_plain_editor(self.editor, q, backwards=backwards)
        if found:
            self.left_tabs.setCurrentIndex(0)
            self.statusBar().showMessage(_t("status.search.xml.found", n=n, total=total, query=q), 2500)
        else:
            self.statusBar().showMessage(_t("status.search.xml.none", query=q), 3000)
        # Entrée reste associée à la recherche suivante, jamais à l'édition XML.
        # La mise en évidence fluo demeure visible dans l'éditeur sans focus.
        self.find_box.setFocus()

    def find_source_next(self):
        self._find_source(False)

    def find_source_previous(self):
        self._find_source(True)

    def find_next(self):
        if self.formatted_view.fragment_find_bar.isVisible() and self.formatted_view.focus_is_in_fragment():
            self.formatted_view.find_fragment_next()
        elif self.left_tabs.currentWidget() is self.formatted_view:
            if not self.formatted_view.preview_find_bar.isVisible():
                self.formatted_view.show_preview_find()
            else:
                self.formatted_view.find_preview_next()
        else:
            self._find_source(False)

    def find_previous(self):
        if self.formatted_view.fragment_find_bar.isVisible() and self.formatted_view.focus_is_in_fragment():
            self.formatted_view.find_fragment_previous()
        elif self.left_tabs.currentWidget() is self.formatted_view:
            if not self.formatted_view.preview_find_bar.isVisible():
                self.formatted_view.show_preview_find()
            else:
                self.formatted_view.find_preview_previous()
        else:
            self._find_source(True)

    def closeEvent(self,event):
        if self._force_close or self.confirm_close_application():
            self._closing_workspace = True
            for win in list(self._detached_windows.values()):
                win.close()
            manager = getattr(self, '_iiif_download_dialog', None)
            if manager is not None:
                manager.shutdown()
            event.accept()
        else:
            event.ignore()


class WelcomeWindow(QMainWindow):
    """Fenêtre légère de démarrage : aucun projet n'est chargé par défaut."""

    def __init__(self):
        super().__init__()
        self._replacement_window = None
        self._welcome_visible = True
        self.setWindowTitle(_t("welcome.window"))
        self.resize(1400, 900)
        self._build_toolbar()
        self._build_welcome()
        app = QApplication.instance()
        if app is not None:
            app.installEventFilter(self)

    def _make_action(self, text, shortcut, slot, tip=""):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(slot)
        if tip:
            action.setToolTip(tip)
        return action

    def _build_toolbar(self):
        tb = QToolBar(_t("toolbar.title"), self)
        tb.setMovable(False)
        self.addToolBar(tb)

        self.file_menu = QMenu(_t("menu.file"), self)
        self.action_new_project = self._make_action(_t("menu.new_project"), "Ctrl+N", self.new_project_dialog)
        self.action_open_project = self._make_action(_t("menu.open_project"), "Ctrl+O", self.open_project_dialog)
        self.recent_menu = self.file_menu.addMenu(_t("menu.recent_projects"))
        self.action_quit = self._make_action(_t("menu.quit"), "Ctrl+Q", self.close)
        self.file_menu.insertAction(self.recent_menu.menuAction(), self.action_new_project)
        self.file_menu.insertAction(self.recent_menu.menuAction(), self.action_open_project)
        self.file_menu.addSeparator()
        self.file_menu.addAction(self.action_quit)
        for action in (self.action_new_project, self.action_open_project, self.action_quit):
            self.addAction(action)
        self.update_recent_projects_menu()

        file_button = QToolButton(self)
        file_button.setText(_t("menu.file"))
        file_button.setMenu(self.file_menu)
        file_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        file_button.setAutoRaise(True)
        tb.addWidget(file_button)
        self.file_menu_button = file_button

        self.help_menu = QMenu(_t("menu.help"), self)
        self.action_enigma = self._make_action(
            _t("help.enigma"), "", lambda: _open_external("https://enigma.huma-num.fr")
        )
        self.action_latin_dictionary = self._make_action(
            _t("help.latin_dictionary"), "", lambda: _open_latin_dictionary(self)
        )
        self.action_latin_dictionary.setShortcuts([QKeySequence("Ctrl+?")])
        self.action_software_help = self._make_action(
            _t("help.software"), "F1", lambda: _show_software_help(self)
        )
        self.action_about = self._make_action(
            _t("help.about"), "", lambda: _show_about(self)
        )
        self.help_menu.addAction(self.action_enigma)
        self.help_menu.addAction(self.action_latin_dictionary)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.action_software_help)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.action_about)
        self.addAction(self.action_latin_dictionary)
        self.addAction(self.action_software_help)

        help_button = QToolButton(self)
        help_button.setText(_t("menu.help"))
        help_button.setMenu(self.help_menu)
        help_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        help_button.setAutoRaise(True)
        tb.addWidget(help_button)
        self.help_menu_button = help_button

    def _build_welcome(self):
        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(36, 30, 36, 30)
        root.addStretch(1)
        self.welcome_panel = _build_varians_card(central, True)
        root.addWidget(self.welcome_panel, 0, Qt.AlignmentFlag.AlignCenter)

        # État vide affiché après fermeture de la carte d’accueil.
        # Le QLabel seul pouvait recevoir, sous Windows/Qt, une hauteur calculée
        # sur une seule ligne alors que le texte était ensuite wrappé, ce qui
        # rognait les glyphes en haut et en bas. Un conteneur de hauteur minimale
        # donne au texte une géométrie stable, quelle que soit la DPI/police.
        self.idle_panel = QFrame(central)
        self.idle_panel.setObjectName("emptyProjectPanel")
        self.idle_panel.setMinimumWidth(720)
        self.idle_panel.setMaximumWidth(820)
        self.idle_panel.setMinimumHeight(96)
        self.idle_panel.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        self.idle_panel.setStyleSheet(
            "QFrame#emptyProjectPanel {"
            " background: #f8fafc; border: 1px solid #dbe3eb;"
            " border-radius: 8px; }"
        )
        idle_layout = QVBoxLayout(self.idle_panel)
        idle_layout.setContentsMargins(24, 18, 24, 18)
        idle_layout.setSpacing(0)

        self.idle_label = QLabel(_t("welcome.no_project"), self.idle_panel)
        self.idle_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.idle_label.setWordWrap(True)
        self.idle_label.setMinimumHeight(58)
        self.idle_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        idle_layout.addWidget(self.idle_label)

        self.idle_panel.hide()
        root.addWidget(self.idle_panel, 0, Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)
        self.setCentralWidget(central)

    def _dismiss_welcome(self):
        if not self._welcome_visible:
            return
        self._welcome_visible = False
        self.welcome_panel.hide()
        self.idle_panel.show()
        self.idle_panel.updateGeometry()
        self.idle_label.updateGeometry()

    def eventFilter(self, obj, event):
        if self._welcome_visible and event.type() == QEvent.Type.MouseButtonPress:
            self._dismiss_welcome()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        app = QApplication.instance()
        if app is not None:
            app.removeEventFilter(self)
        event.accept()

    def update_recent_projects_menu(self):
        self.recent_menu.clear()
        paths = recent_project_paths()
        if not paths:
            empty = QAction(_t("menu.recent_empty"), self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
        else:
            for raw in paths:
                path = Path(raw)
                try:
                    title = load_project(path).title if path.is_file() else path.parent.name
                except Exception:
                    title = path.parent.name or path.stem
                action = QAction(_t("menu.recent_item", title=title, path=path), self)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, p=path: self.open_recent_project(p))
                self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction(_t("menu.recent_clear"), self)
        clear_action.triggered.connect(self.clear_recent_projects_action)
        self.recent_menu.addAction(clear_action)

    def clear_recent_projects_action(self):
        clear_recent_projects()
        self.update_recent_projects_menu()

    def _open_project_path(self, project_path):
        try:
            new_window = MainWindow(Path(project_path))
        except Exception as exc:
            QMessageBox.critical(self, _t("project.open_error"), str(exc))
            return False
        self._replacement_window = new_window
        new_window.showMaximized()
        self.close()
        return True

    def open_project_dialog(self):
        recent = recent_project_paths()
        start = str(Path(recent[0]).parent if recent else Path.home())
        fn, _ = QFileDialog.getOpenFileName(
            self, _t("project.open.title"), start,
            f"{_t('project.open.filter')} (*.xml);;{_t('common.all_files')} (*)",
        )
        if fn:
            self._open_project_path(Path(fn))

    def open_recent_project(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            remove_recent_project(path)
            self.update_recent_projects_menu()
            QMessageBox.warning(self, _t("project.recent.missing.title"), _t("project.recent.missing", path=path))
            return
        self._open_project_path(path)

    def new_project_dialog(self):
        languages = [(info.code, info.label) for info in I18N.available_languages()]
        dlg = NewProjectDialog(_t, languages, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        try:
            creator = (create_new_transcription_project
                       if values.get("creation_mode") == "blank" else create_portable_project)
            if values.get("creation_mode") == "blank":
                project_path = creator(
                    values["target_dir"], values["title"],
                    values["witnesses"], values["base_witness"], HERE,
                    values["language"], "en",
                    xslt_mode=values["xslt_mode"],
                    schema_source=values.get("schema"),
                    schema_mode=values.get("schema_mode", "auto"),
                )
            else:
                project_path = creator(
                    values["target_dir"], values["title"], values["edition"],
                    values["witnesses"], values["base_witness"], HERE,
                    values["language"], "en",
                    xslt_mode=values["xslt_mode"],
                    schema_source=values.get("schema"),
                    schema_mode=values.get("schema_mode", "auto"),
                )
        except Exception as exc:
            message = _t("project.new.error.target_not_empty") if str(exc) == "TARGET_NOT_EMPTY" else str(exc)
            QMessageBox.critical(self, _t("project.new.error.title"), message)
            return
        if values.get('prepare_pivot') and values.get('creation_mode') == 'blank':
            from project_config import load_project as _load_pivot_project
            created = _load_pivot_project(project_path)
            run_pivot_scaffold_dialog(_t, self, created.witnesses, created.base_witness,
                                      created.root_dir, created.edition,
                                      include_lb=values.get('pivot_lines', True))
        remember_recent_project(project_path)
        QMessageBox.information(self, _t("project.new.done.title"), _t("project.new.done", path=project_path))
        if self._open_project_path(project_path):
            new_window = self._replacement_window
            if any(w.image_source_type == 'iiif' and (
                w.iiif_local_copy or w.iiif_web_local_copy) for w in values['witnesses']):
                QTimer.singleShot(0, lambda: new_window.open_iiif_download_manager(auto_start=True))


def main():
    app = QApplication.instance() or QApplication(sys.argv)
    _install_light_selection_palette(app)
    startup_language = str(_settings().value("startupLanguage", "fr") or "fr")
    I18N.set_language(startup_language)
    app.setApplicationName(_t("app.name"))
    try:
        if len(sys.argv) > 1:
            win = MainWindow(Path(sys.argv[1]).resolve())
        else:
            # Rouvrir uniquement le projet qui était encore ouvert lors de la
            # précédente fermeture. « Fermer le projet » efface cette préférence.
            startup_project = last_open_project_path()
            if startup_project is not None:
                try:
                    win = MainWindow(startup_project)
                except Exception as exc:
                    forget_open_project()
                    QMessageBox.warning(None, _t("project.reopen_error.title"),
                                        _t("project.reopen_error", path=startup_project, error=exc))
                    win = WelcomeWindow()
            else:
                # Le projet de démonstration reste livré, mais n'est jamais ouvert
                # automatiquement à la première utilisation.
                win = WelcomeWindow()
    except Exception as exc:
        QMessageBox.critical(None, _t("project.open_error"), str(exc))
        return 2
    # « Plein écran » au sens bureau : fenêtre maximisée, sans masquer la barre
    # des tâches ni les contrôles natifs de la fenêtre.
    win.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
