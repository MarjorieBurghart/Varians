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
_LOCAL_MODULE_NAMES = {"project_config", "project_management", "project_dialogs", "i18n", "relaxng_validation", "schema_resolution", "rng_completion", "xpath_search", "save_io", "custom_completion", "image_sources", "iiif_manifest", "iiif_local", "iiif_selection", "iiif_download_manager", "iiif_page_selection", "alto_import", "tei_facsimile", "xml_tag_pairs", "tei_formatter", "selection_sync", "witness_resource_refresh", "resource_state", "witness_layout", "iiif_resolution", "folio_navigation", "xml_folding"}
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
from document_session import DocumentSession, LbIndex
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
APP_VERSION = "0.8.5.26.2"
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

def _t(key, default=None, **values):
    return I18N.tr(key, default=default, **values)

DISK_CACHE = Path.home() / ".cache_tei_manuscript_editor"
DISK_CACHE.mkdir(parents=True, exist_ok=True)

SETTINGS_ORGANIZATION = "TEIManuscriptTools"
SETTINGS_APPLICATION = "GenericTEIManuscriptEditor"
MAX_RECENT_PROJECTS = 10

def _settings():
    # Identifiants stables et indépendants de la langue affichée.
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)

def recent_project_paths():
    value = _settings().value("recentProjects", [])
    if isinstance(value, str):
        value = [value]
    result = []
    seen = set()
    for raw in value or []:
        try:
            path = str(Path(raw).expanduser().resolve())
        except Exception:
            continue
        if path not in seen:
            seen.add(path); result.append(path)
    return result[:MAX_RECENT_PROJECTS]

def remember_recent_project(path):
    path = str(Path(path).expanduser().resolve())
    values = [p for p in recent_project_paths() if p != path]
    values.insert(0, path)
    _settings().setValue("recentProjects", values[:MAX_RECENT_PROJECTS])

def remove_recent_project(path):
    target = str(Path(path).expanduser().resolve())
    _settings().setValue("recentProjects", [p for p in recent_project_paths() if p != target])

def clear_recent_projects():
    _settings().remove("recentProjects")


def last_open_project_path():
    """Projet à rouvrir au démarrage s'il était encore ouvert à la fermeture.

    Cette préférence est volontairement distincte de la liste des récents :
    « Fermer le projet » l'efface, tandis que quitter l'application avec un
    projet ouvert la conserve.
    """
    raw = _settings().value("lastOpenProject", "")
    if not raw:
        return None
    try:
        path = Path(str(raw)).expanduser().resolve()
    except Exception:
        _settings().remove("lastOpenProject")
        return None
    if not path.is_file():
        _settings().remove("lastOpenProject")
        return None
    return path


def remember_open_project(path):
    _settings().setValue("lastOpenProject", str(Path(path).expanduser().resolve()))


def forget_open_project():
    _settings().remove("lastOpenProject")


def load_json(path: Path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def flatten_primary(cache):
    items = []
    by_key = {}
    for page in cache.get("pages", []):
        for line in page.get("lines", []):
            key = f"{page['id']}::{line.get('line')}"
            item = {"p": page, "l": line, "key": key}
            by_key[key] = len(items)
            items.append(item)
    return items, by_key


def flatten_secondary(cache):
    items = []
    for page in cache.get("pages", []):
        for line in page.get("lines", []):
            items.append({"p": page, "l": line, "key": f"{page['id']}::{line.get('alto_id') or line.get('line')}"})
    items.sort(key=lambda x: int(x["l"].get("order", 0)))
    by_816 = defaultdict(list)
    for i, item in enumerate(items):
        for k in (item["l"].get("base_keys") or item["l"].get("keys816") or []):
            by_816[k].append(i)
    return items, dict(by_816)


def scaled_bbox(item, project_root=None):
    p, l = item["p"], item["l"]
    # PAGE XML may provide only a polygon. Derive its bounding extents without
    # replacing the polygon used for drawing; never fabricate (0,0) geometry.
    b = effective_line_bbox(l)
    if b is None:
        return None
    # Include *every* PAGE polygon vertex even when a legacy bbox is smaller.
    polygon = l.get("polygon") or []
    if len(polygon) >= 3:
        try:
            from math import isfinite
            vertices = [(float(x), float(y)) for x, y in polygon]
            if all(isfinite(v) for point in vertices for v in point):
                x0 = min(b["hpos"], min(x for x, _ in vertices))
                y0 = min(b["vpos"], min(y for _, y in vertices))
                x1 = max(b["hpos"] + b["width"], max(x for x, _ in vertices))
                y1 = max(b["vpos"] + b["height"], max(y for _, y in vertices))
                b = {"hpos": x0, "vpos": y0, "width": x1-x0, "height": y1-y0}
        except (TypeError, ValueError, OverflowError):
            pass
    iw, ih = page_image_dimensions(p, project_root)
    aw = float(p.get("alto_width") or iw or 1)
    ah = float(p.get("alto_height") or ih or 1)
    sx, sy = iw / max(1, aw), ih / max(1, ah)
    return {
        "x": float(b.get("hpos", 0)) * sx,
        "y": float(b.get("vpos", 0)) * sy,
        "w": max(1.0, float(b.get("width", 1)) * sx),
        "h": max(1.0, float(b.get("height", 1)) * sy),
        "iw": iw,
        "ih": ih,
    }


def scaled_polygon(item, project_root=None):
    """Original polygon geometry in displayed image coordinates."""
    p, line = item['p'], item['l']
    polygon = line.get('polygon') or []
    if len(polygon) < 3:
        return []
    iw, ih = page_image_dimensions(p, project_root)
    aw = float(p.get('alto_width') or iw or 1)
    ah = float(p.get('alto_height') or ih or 1)
    return [(float(x) * iw / max(1, aw), float(y) * ih / max(1, ah))
            for x, y in polygon]


def crop_for_items(items, pad=24, project_root=None):
    if not items:
        return None
    boxes = [scaled_bbox(x, project_root) for x in items]
    # Missing/ambiguous coordinates: show the whole physical page instead of
    # a fictitious 1px crop at the top-left corner.
    if any(b is None for b in boxes):
        return None
    iw, ih = boxes[0]["iw"], boxes[0]["ih"]
    x0 = max(0, int(min(b["x"] for b in boxes) - pad))
    y0 = max(0, int(min(b["y"] for b in boxes) - pad))
    from math import ceil
    x1 = min(int(iw), ceil(max(b["x"] + b["w"] for b in boxes) + pad))
    y1 = min(int(ih), ceil(max(b["y"] + b["h"] for b in boxes) + pad))
    return {"x": x0, "y": y0, "w": max(1, x1-x0), "h": max(1, y1-y0)}


def iiif_image_request(page, crop, project_root=None):
    """Compatibilité API historique : délègue au modèle d'image V0.7.0."""
    return generic_image_request(page, crop, project_root)


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
                old_text, new_text, position, chars_removed, chars_added
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


class FetchSignals(QObject):
    # token, key, data, error, source_mode ("crop" ou "fallback")
    finished = Signal(int, str, bytes, str, str)


class FetchWorker(QRunnable):
    _gallica_lock = threading.Lock()

    def __init__(self, token, key, url, fallback_url=None):
        super().__init__(); self.token = token; self.key = key; self.url = url
        self.fallback_url = fallback_url
        self.signals = FetchSignals()

    @staticmethod
    def _cache_path(url):
        suffix = ".jpg"
        return DISK_CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix)

    def _cached_or_download(self, url):
        if str(url).lower().startswith("file://"):
            from urllib.parse import urlparse, unquote
            parsed = urlparse(url)
            raw_path = unquote(parsed.path or "")
            if parsed.netloc and not raw_path.startswith("/"):
                raw_path = "/" + raw_path
            # Sous Windows, file:///C:/... produit /C:/... ; Path accepte mieux C:/...
            if re.match(r"^/[A-Za-z]:/", raw_path):
                raw_path = raw_path[1:]
            return Path(raw_path).read_bytes()
        path = self._cache_path(url)
        if path.exists() and path.stat().st_size > 0:
            return path.read_bytes()
        old_url = self.url
        try:
            self.url = url
            data = self._download_once()
        finally:
            self.url = old_url
        if data:
            try:
                path.write_bytes(data)
            except OSError:
                pass
        return data

    def _download_once(self):
        req = urllib.request.Request(
            self.url,
            headers={
                # User-Agent de navigateur volontairement banal : certains
                # frontaux HTTP ferment les connexions de clients atypiques.
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "Referer": "https://gallica.bnf.fr/",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read()

    @Slot()
    def run(self):
        urls = [(self.url, "crop")]
        if self.fallback_url and self.fallback_url != self.url:
            urls.append((self.fallback_url, "fallback"))
        last_exc = None

        for candidate_url, mode in urls:
            is_gallica = "gallica.bnf.fr" in candidate_url.lower()
            attempts = 4 if is_gallica else 2
            lock = self._gallica_lock if is_gallica else None
            for attempt in range(attempts):
                try:
                    if lock:
                        with lock:
                            if attempt:
                                time.sleep(min(4.0, 0.8 * (2 ** (attempt - 1))))
                            data = self._cached_or_download(candidate_url)
                            time.sleep(0.35)
                    else:
                        data = self._cached_or_download(candidate_url)
                    if not data:
                        raise RuntimeError("réponse vide")
                    self.signals.finished.emit(self.token, self.key, data, "", mode)
                    return
                except Exception as exc:
                    last_exc = exc
                    if not is_gallica:
                        break
            # Si le recadrage IIIF Gallica échoue, on tente le fallback highres.

        msg = str(last_exc) if last_exc else "échec réseau"
        if "429" in msg or "Too Many Requests" in msg:
            msg = "Gallica limite temporairement les requêtes (HTTP 429)."
        elif "10054" in msg or "forcibly closed" in msg.lower() or "reset" in msg.lower():
            msg = "Gallica a réinitialisé la connexion (WinError 10054), même après plusieurs nouvelles tentatives."
        self.signals.finished.emit(self.token, self.key, b"", msg, "")


class ImageSceneView(QGraphicsView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setScene(QGraphicsScene(self))
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setResizeAnchor(QGraphicsView.ViewportAnchor.AnchorViewCenter)
        self.setBackgroundBrush(QBrush(QColor("#e8e3db")))
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.user_zoom = 1.0
        self._fit_pending = False
        self._fit_in_progress = False
        self.folio_focus_rect = None
        # À 100 %, l’image est ajustée à la largeur : une barre horizontale
        # n’est ni utile ni souhaitable. La masquer à ce niveau évite surtout
        # une boucle apparition/disparition des scrollbars qui pouvait faire
        # « vibrer » l’image lors des resizeEvent.
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        # Réserver en permanence la largeur de la barre verticale. Avec une
        # politique AsNeeded, son apparition change la largeur du viewport,
        # relance le fit à 100 %, puis peut la faire disparaître : c'est la
        # principale source du « tremblement » observé sur certaines images.
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.setMinimumHeight(160)

    def _schedule_fit(self):
        if self.user_zoom != 1.0 or self._fit_pending:
            return
        self._fit_pending = True

        def run():
            self._fit_pending = False
            if self.user_zoom == 1.0:
                self._apply_fit()

        QTimer.singleShot(0, run)

    def reset_zoom(self):
        self.user_zoom = 1.0
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self._apply_fit()

    def _apply_fit(self):
        if self._fit_in_progress:
            return
        rect = self.folio_focus_rect or self.scene().itemsBoundingRect()
        if rect.isEmpty():
            return
        self._fit_in_progress = True
        try:
            self.resetTransform()
            # Réserver d’emblée la largeur potentielle de la barre verticale.
            # Sans cette réserve, son apparition rétrécissait le viewport juste
            # après le fit, pouvait déclencher la barre horizontale, puis un
            # nouveau resizeEvent : deux tailles alternaient indéfiniment.
            # La barre verticale est AlwaysOn : sa largeur est déjà retirée
            # du viewport. Ne pas la soustraire une seconde fois.
            available = max(16.0, self.viewport().width() - 12.0)
            base = max(0.01, available / max(1.0, rect.width()))
            self.scale(base, base)
            self.centerOn(rect.center())
        finally:
            self._fit_in_progress = False

    def zoom_by(self, factor):
        if not self.scene().items(): return
        new = max(0.5, min(6.0, self.user_zoom * factor))
        factor2 = new / self.user_zoom; self.user_zoom = new
        # Dès que l’utilisateur quitte le fit 100 %, les scrollbars redeviennent
        # disponibles pour le panoramique. Elles seront à nouveau masquées au reset.
        if abs(self.user_zoom - 1.0) > 1e-9:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        else:
            self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scale(factor2, factor2)
        p = self.parent()
        while p is not None and not hasattr(p, "update_zoom_label"):
            p = p.parent()
        if p is not None: p.update_zoom_label()

    def wheelEvent(self, event):
        if event.angleDelta().y() > 0: self.zoom_by(1.15)
        else: self.zoom_by(1/1.15)
        event.accept()

    def mouseDoubleClickEvent(self, event):
        self.reset_zoom()
        p = self.parent()
        while p is not None and not hasattr(p, "update_zoom_label"):
            p = p.parent()
        if p is not None: p.update_zoom_label()
        event.accept()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        if self.user_zoom == 1.0:
            self._schedule_fit()



class SplitImagePreview(QWidget):
    """Whole-image thumbnail and movable vertical separator (physical pixels).

    No painting occurs in original image data. The widget always maps its
    displayed red line back into the full physical image width.
    """
    splitChanged = Signal(int)

    def __init__(self, image_width, image_height, parent=None):
        super().__init__(parent)
        self.image_width = max(2, int(image_width))
        self.image_height = max(2, int(image_height))
        self.split_px = round(self.image_width / 2)
        self.thumbnail = QPixmap()
        self._dragging = False
        self.status = _t('folio.split.loading')
        self.setMinimumSize(450, 245)
        self.setFixedHeight(305)
        self.setCursor(Qt.CursorShape.SizeHorCursor)
        self.setToolTip(_t('folio.split.drag_tip'))

    def set_split_px(self, px):
        self.split_px = max(1, min(self.image_width - 1, int(px)))
        self.update()

    def set_thumbnail(self, pixmap):
        if pixmap is not None and not pixmap.isNull():
            self.thumbnail = pixmap
            self.status = ''
        else:
            self.status = _t('folio.split.preview_failed')
        self.update()

    def _image_rect(self):
        available_w = max(1, self.width() - 24)
        available_h = max(1, self.height() - 24)
        aspect = (self.thumbnail.width() / max(1, self.thumbnail.height())
                  if not self.thumbnail.isNull()
                  else self.image_width / self.image_height)
        width = min(available_w, available_h * aspect)
        height = width / aspect
        return QRectF((self.width()-width)/2, (self.height()-height)/2, width, height)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor('#eeeae2'))
        rect = self._image_rect()
        if not self.thumbnail.isNull():
            painter.drawPixmap(rect.toRect(), self.thumbnail)
        else:
            painter.setPen(QColor('#625c55'))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.status)
        painter.setPen(QPen(QColor('#b4a99a'), 1))
        painter.drawRect(rect)
        xpos = rect.left() + rect.width() * self.split_px / self.image_width
        painter.setPen(QPen(QColor('#e32124'), 3))
        painter.drawLine(QPointF(xpos, rect.top()), QPointF(xpos, rect.bottom()))
        painter.end()

    def _set_from_mouse(self, event):
        rect = self._image_rect()
        xpos = max(rect.left(), min(rect.right(), event.position().x()))
        pixel = round((xpos - rect.left()) / max(1.0, rect.width()) * self.image_width)
        # Manual drag is intentionally restricted away from the outer edges.
        pixel = max(round(self.image_width * .01), min(round(self.image_width * .99), pixel))
        if pixel != self.split_px:
            self.set_split_px(pixel)
            self.splitChanged.emit(self.split_px)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._set_from_mouse(event)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event):
        if self._dragging:
            self._set_from_mouse(event)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if self._dragging and event.button() == Qt.MouseButton.LeftButton:
            self._set_from_mouse(event)
            self._dragging = False
            event.accept()
            return
        super().mouseReleaseEvent(event)


class SplitPreviewLoader(QObject):
    """Qt-owned receiver: image decoding and QWidget updates run in GUI thread."""

    def __init__(self, preview):
        super().__init__(preview)
        self.preview = preview

    @Slot(int, str, bytes, str, str)
    def finished(self, _token, _key, data, error, _mode):
        pix = QPixmap()
        if not error and data and pix.loadFromData(data):
            self.preview.set_thumbnail(pix.scaled(
                QSize(850, 480), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation))
        else:
            self.preview.set_thumbnail(None)


def _iiif_split_preview_request(page, project_root):
    """IIIF thumbnail URL independent of the line crop, never fullres if a service exists."""
    source = page_image_source(page, project_root)
    raw = source.raw or {}
    if source.kind == 'file' and isinstance(raw.get('remote_iiif'), dict):
        source = page_image_source({'image': raw['remote_iiif']}, project_root)
    if source.kind == 'iiif' and source.service:
        quality = 'native' if source.iiif_version == 1 else 'default'
        # IIIF Image API 2 and 3 accept a width-constrained size.
        url = f"{str(source.service).rstrip('/')}/full/800,/0/{quality}.jpg"
        return url, source.image_url
    request = generic_image_request(page, None, project_root)
    return (request.get('url'), request.get('fallback_url')) if request else (None, None)


def load_split_thumbnail(widget, page, project_root):
    """Local scaled decode, otherwise asynchronous low-resolution IIIF fetch."""
    source = page_image_source(page, project_root)
    if source.kind == 'file' and source.file_path and source.file_path.is_file():
        reader = QImageReader(str(source.file_path))
        reader.setAutoTransform(True)
        original = reader.size()
        if original.isValid():
            fit = original.scaled(QSize(850, 480), Qt.AspectRatioMode.KeepAspectRatio)
            reader.setScaledSize(fit)
        image = reader.read()
        if not image.isNull():
            widget.set_thumbnail(QPixmap.fromImage(image))
            return
    url, fallback = _iiif_split_preview_request(page, project_root)
    if not url:
        widget.set_thumbnail(None)
        return
    worker = FetchWorker(0, 'split_preview', url, fallback)
    loader = SplitPreviewLoader(widget)
    # QObject receiver ensures a queued signal from the download worker is
    # delivered on the GUI thread. A closed dialog destroys the receiver and
    # safely disconnects it rather than updating an invalid QWidget.
    widget._split_loader = loader
    worker.signals.finished.connect(loader.finished)
    QThreadPool.globalInstance().start(worker)


class WitnessHeader(QWidget):
    """En-tête léger d'un témoin ; double-clic = maximiser/restaurer le panneau."""
    doubleClicked = Signal()

    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        self.title = QLabel(label, self)
        self.title.setStyleSheet("font-weight:700;border:0")
        self.status = QLabel("—", self)
        self.status.setStyleSheet("color:#746b61;border:0")
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.status.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title)
        layout.addStretch(1)
        layout.addWidget(self.status)

    def mouseDoubleClickEvent(self, event):
        self.doubleClicked.emit()
        event.accept()


class ManuscriptPanel(QFrame):
    primaryNavigate = Signal(int)   # nouveau centre du témoin de base
    markPageRequested = Signal(str, str, str)  # témoin, surface/zone xml:id, @n
    splitFolioRequested = Signal(str, str)  # témoin, surface xml:id
    maximizeRequested = Signal(str)
    detachRequested = Signal(str)

    _memory_cache = {}

    def __init__(self, siglum, label, items, map_base=None, is_base=False, base_label="base", project_root=None, sync_enabled=True, parent=None):
        super().__init__(parent)
        self.siglum = siglum; self.label = label; self.items = items; self.map_base = map_base or {}; self.is_base = bool(is_base); self.base_label = base_label; self.project_root = Path(project_root).resolve() if project_root else None
        self.sync_enabled = bool(sync_enabled)
        self.folios = []
        self._active_folio = None
        self._updating_folios = False
        self.center_index = 0; self.origin_center_index = 0
        self.match_indices = set(); self.primary_key = None
        self.show_frames = False; self.load_token = 0; self.pending = 0
        self.loaded_groups = {}; self.group_specs = []
        self.threadpool = QThreadPool.globalInstance()
        self.setFrameShape(QFrame.Shape.StyledPanel)
        self.setStyleSheet("QFrame {background:#fffdf9;border:1px solid #d8d0c5;border-radius:8px;} QPushButton{padding:3px 7px;}")

        root = QVBoxLayout(self); root.setContentsMargins(8, 6, 8, 8); root.setSpacing(5)
        self.header = WitnessHeader(label, self)
        self.status = self.header.status
        self.header.doubleClicked.connect(lambda: self.maximizeRequested.emit(self.siglum))
        self.detach_btn = QPushButton('↗', self.header)
        self.detach_btn.setToolTip(_t('workspace.detach.tip'))
        self.detach_btn.setFixedWidth(26)
        self.header.layout().addWidget(self.detach_btn)
        self.detach_btn.clicked.connect(lambda: self.detachRequested.emit(self.siglum))
        root.addWidget(self.header)

        bar = QHBoxLayout(); bar.setSpacing(4)
        self.prev_btn = QPushButton("←"); self.next_btn = QPushButton("→")
        self.home_btn = QPushButton("⤺"); self.home_btn.setToolTip(_t("manuscript.home.tip"))
        self.minus_btn = QPushButton("−"); self.reset_btn = QPushButton("↺"); self.plus_btn = QPushButton("+")
        self.zoom_label = QLabel("100 %"); self.zoom_label.setMinimumWidth(48); self.zoom_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.frames_btn = QPushButton(_t("common.frames")); self.frames_btn.setCheckable(True); self.frames_btn.setChecked(False)
        self.frames_btn.setToolTip(_t("manuscript.frames.tip"))
        # The toggle is *per witness*. Make this visually obvious even with a
        # platform theme that gives checked and unchecked buttons similar hues.
        self.frames_btn.setStyleSheet("QPushButton:checked { background-color: #ffe4d4; border: 2px solid #d45735; font-weight: bold; }")
        self.page_btn = QPushButton(_t("common.page"))
        self.mark_page_btn = QPushButton(_t("manuscript.mark_page"))
        self.mark_page_btn.setToolTip(_t("manuscript.mark_page.tip"))
        for b in [self.prev_btn, self.next_btn, self.home_btn, self.minus_btn, self.reset_btn, self.plus_btn, self.frames_btn, self.page_btn, self.mark_page_btn]:
            bar.addWidget(b)
        bar.insertWidget(6, self.zoom_label)
        # V0.8.5.20: the double-page command shares the EXISTING toolbar.
        # No second toolbar row. Arrows continue traversing logical parts in
        # page mode; a hidden combo maintains the existing navigation state.
        self.split_folio_btn = QPushButton(_t('folio.split.button'))
        self.split_folio_btn.setToolTip(_t('folio.split.tip'))
        bar.addWidget(self.split_folio_btn)
        bar.addStretch(1); root.addLayout(bar)
        self.folio_label = QLabel(_t('folio.navigator.label'), self)
        self.folio_combo = QComboBox(self)
        self.folio_label.hide()
        self.folio_combo.hide()
        self.folio_combo.currentIndexChanged.connect(self._folio_combo_changed)
        self.split_folio_btn.clicked.connect(self._request_split_folio)
        # Synchronized witnesses retain their physical-line navigator.
        self.folio_combo.setEnabled(not self.sync_enabled)
        # Décrire le fac-similé est indépendant des liens ligne-à-ligne.
        # V0.8.5.18 désactivait par erreur cette commande dès qu'un témoin
        # (par ex. L) devenait synchronisé avec le manuscrit pivot.
        self.split_folio_btn.setEnabled(bool(self.items))

        self.sync_issue = QLabel("")
        self.sync_issue.setWordWrap(True)
        self.sync_issue.setStyleSheet("color:#94512f;border:0;font-size:11px")
        self.sync_issue.hide()
        root.addWidget(self.sync_issue)
        self.view = ImageSceneView(self); root.addWidget(self.view, 1)
        self.message = QLabel(""); self.message.setWordWrap(True); self.message.setStyleSheet("color:#9b4636;border:0;font-size:11px")
        self.message.hide(); root.addWidget(self.message)

        self.prev_btn.clicked.connect(lambda: self.navigate(-1))
        self.next_btn.clicked.connect(lambda: self.navigate(1))
        self.home_btn.clicked.connect(self.go_home)
        self.minus_btn.clicked.connect(lambda: self._zoom(1/1.25))
        self.plus_btn.clicked.connect(lambda: self._zoom(1.25))
        self.reset_btn.clicked.connect(self._reset_zoom)
        self.frames_btn.toggled.connect(self._toggle_frames)
        self.page_btn.clicked.connect(self.open_page)
        self.mark_page_btn.clicked.connect(self._request_mark_page)
        self._surface_indices = {
            str((it.get("p") or {}).get("tei_surface_id")): i
            for i, it in enumerate(self.items)
            if (it.get("p") or {}).get("tei_surface_id")
        }
        if self.is_base: self.home_btn.hide()
        self._update_mark_page_button()

    def set_compact_toolbar(self, compact):
        """Keep two-column/grid layouts usable even on modest screen widths.

        Only presentation changes: the same QPushButton instances, shortcuts
        and connections remain live. Full descriptive tooltips remain.
        """
        self._compact_toolbar = bool(compact)
        compact_labels = (
            (self.frames_btn, '▣', _t('common.frames'), 36),
            (self.page_btn, '□', _t('common.page'), 30),
            (self.mark_page_btn, 'pb', _t('manuscript.mark_page'), 34),
            (self.split_folio_btn, '↔', _t('folio.split.button'), 34),
        )
        for btn, small, full, width in compact_labels:
            btn.setText(small if compact else full)
            btn.setToolTip((_t('manuscript.frames.tip') if btn is self.frames_btn
                            else _t('manuscript.mark_page.tip') if btn is self.mark_page_btn
                            else _t('folio.split.tip') if btn is self.split_folio_btn
                            else _t('common.page')))
            if compact:
                btn.setFixedWidth(width)
            else:
                btn.setMinimumWidth(0)
                btn.setMaximumWidth(16777215)
        for btn in (self.prev_btn, self.next_btn, self.home_btn,
                    self.minus_btn, self.reset_btn, self.plus_btn):
            if compact:
                btn.setFixedWidth(28)
            else:
                btn.setMinimumWidth(0)
                btn.setMaximumWidth(16777215)

    def retranslate_ui(self):
        self.detach_btn.setToolTip(_t('workspace.attach.tip' if getattr(self, '_detached', False) else 'workspace.detach.tip'))
        self.home_btn.setToolTip(_t("manuscript.home.tip"))
        self.frames_btn.setText(_t("common.frames"))
        self.frames_btn.setToolTip(_t("manuscript.frames.tip"))
        self.page_btn.setText(_t("common.page"))
        self.mark_page_btn.setText(_t("manuscript.mark_page"))
        self.mark_page_btn.setToolTip(_t("manuscript.mark_page.tip"))
        self.folio_label.setText(_t('folio.navigator.label'))
        self.split_folio_btn.setText(_t('folio.split.button'))
        self.split_folio_btn.setToolTip(_t('folio.split.tip'))
        self.set_compact_toolbar(getattr(self, '_compact_toolbar', False))
        # Update labels/status without refetching IIIF images.
        if not self.items:
            self.status.setText(_t("manuscript.no_line"))
            return
        if not self.is_base and self.primary_key is not None and not self.match_indices:
            self.status.setText(_t("manuscript.no_direct"))
            self.message.setText(_t("manuscript.no_match"))
            return
        center = self.current_item()
        if center:
            page_label = image_page_label(center["p"], self.project_root)
            line_no = center["l"].get("line")
            score = center["l"].get("score")
            if center["l"].get("_page_mode") or center["l"].get("_image_only"):
                self.status.setText(_t("manuscript.status.page_only_count", page=page_label, current=self.center_index + 1, total=len(self.items)))
            else:
                extra = _t("manuscript.score", score=f"{score:.0%}") if isinstance(score, (int, float)) and not self.is_base else ""
                self.status.setText(_t("manuscript.status", page=page_label, line=line_no, extra=extra))

    def update_zoom_label(self):
        self.zoom_label.setText(f"{round(self.view.user_zoom*100):d} %")

    def _zoom(self, factor):
        self.view.zoom_by(factor); self.update_zoom_label()

    def _reset_zoom(self):
        self.view.reset_zoom(); self.update_zoom_label()

    def _toggle_frames(self, checked):
        self.show_frames = bool(checked); self._redraw_scene()

    def set_primary(self, primary_index, primary_key):
        if not self.sync_enabled:
            return
        self.primary_key = primary_key
        if self.is_base:
            self.match_indices = {primary_index}
            self.center_index = max(0, min(len(self.items)-1, primary_index))
            self.origin_center_index = self.center_index
        else:
            matches = list(self.map_base.get(primary_key, []))
            center = matched_line_center(matches, self.center_index, len(self.items))
            if center is not None:
                # One base line may match several non-adjacent secondary lines.
                # Their numerical midpoint can designate an *unmatched* line,
                # and the window may even cross a column boundary. The current
                # window must always be anchored on a truly linked line.
                self.match_indices = valid_matched_indices(matches, len(self.items))
                self.center_index = center
                self.origin_center_index = center
            else:
                self.match_indices = set()
                self.status.setText(_t("manuscript.no_direct"))
                self.view.scene().clear()
                self.message.setText(_t("manuscript.no_match"))
                self.message.setStyleSheet("color:#746b61;border:0;font-size:11px")
                self.message.show()
                return
        self.reload()

    def navigate(self, step):
        if not self.items: return
        if not self.sync_enabled and self.folios:
            # Only logical folios, not the full-image previews, count as
            # pages when a surface is divided into several named folios.
            choices = [f for f in self.folios if f.region is not None or not any(
                x.region is not None and x.surface == f.surface for x in self.folios)]
            pos = next((i for i, f in enumerate(choices) if f.ref == self._active_folio), None)
            if pos is None:
                current = self._current_folio()
                pos = next((i for i, f in enumerate(choices) if current and f.surface == current.surface), 0)
            target = choices[max(0, min(len(choices)-1, pos + step))]
            self.set_folio(target.ref)
            return
        new = max(0, min(len(self.items)-1, self.center_index + step))
        if new == self.center_index: return
        self.center_index = new
        if self.is_base and self.sync_enabled:
            self.primaryNavigate.emit(new)
        else:
            self.reload()

    def go_home(self):
        if self.is_base: return
        self.center_index = self.origin_center_index; self.reload()

    def current_item(self):
        if not self.items: return None
        return self.items[max(0, min(len(self.items)-1, self.center_index))]

    def set_folios(self, targets):
        """Refresh folio choices without changing the displayed image needlessly."""
        self.folios = list(targets)
        self._updating_folios = True
        self.folio_combo.blockSignals(True)
        try:
            self.folio_combo.clear()
            for f in self.folios:
                prefix = _t('folio.full_image') + ' · ' if f.region is None and any(
                    c.region is not None and c.surface == f.surface for c in self.folios) else ''
                self.folio_combo.addItem(prefix + f.label, f.ref)
            if self._active_folio not in {f.ref for f in self.folios}:
                current = self.current_item()
                self._active_folio = str(((current or {}).get('p') or {}).get('tei_surface_id') or '')
            index = next((i for i, f in enumerate(self.folios) if f.ref == self._active_folio), -1)
            if index >= 0:
                self.folio_combo.setCurrentIndex(index)
        finally:
            self.folio_combo.blockSignals(False)
            self._updating_folios = False
        self._update_mark_page_button()

    def _folio_combo_changed(self, index):
        if self._updating_folios or self.sync_enabled or index < 0 or index >= len(self.folios):
            return
        self.set_folio(self.folios[index].ref)

    def _request_split_folio(self):
        """Ouvre la définition des folios, même si ce témoin suit les lignes.

        Si le lien surface/image manque, déléguer aussi au contrôleur afin
        d'afficher un diagnostic plutôt que de ne rien faire au clic.
        """
        item = self.current_item()
        if not item:
            return
        sid = str((item.get('p') or {}).get('tei_surface_id') or '').strip()
        self.splitFolioRequested.emit(self.siglum, sid)

    def set_folio(self, ref):
        target = next((f for f in self.folios if f.ref == str(ref)), None)
        if target is None:
            return False
        ix = self._surface_indices.get(target.surface)
        if ix is None:
            return False
        changed = self.center_index != ix or self._active_folio != target.ref
        self.center_index = ix
        self.origin_center_index = ix
        self._active_folio = target.ref
        self.folio_combo.blockSignals(True)
        try:
            index = next((i for i, f in enumerate(self.folios) if f.ref == target.ref), -1)
            if index >= 0:
                self.folio_combo.setCurrentIndex(index)
        finally:
            self.folio_combo.blockSignals(False)
        if changed:
            self.reload()
        return True

    def _current_folio(self):
        return next((f for f in self.folios if f.ref == self._active_folio), None)

    def _update_mark_page_button(self):
        item = self.current_item()
        sid = str(((item or {}).get("p") or {}).get("tei_surface_id") or "")
        self.mark_page_btn.setEnabled(bool(sid))
        self.split_folio_btn.setEnabled(bool(item))

    def _request_mark_page(self):
        item = self.current_item()
        if not item:
            return
        page = item.get("p") or {}
        sid = str(page.get("tei_surface_id") or "").strip()
        if not sid:
            return
        label = image_page_label(page, self.project_root) or str(page.get("label") or sid)
        parts = [f for f in self.folios if f.surface == sid and f.region is not None]
        if len(parts) == 2:
            target = None
            # An explicitly selected logical part is authoritative in page
            # mode; for synchronized lines, the geometry is authoritative.
            if self.sync_enabled:
                target = markable_part_for_line(item, self.folios, self.project_root)
            else:
                selected = self._current_folio()
                if selected is not None and selected.surface == sid and selected.region is not None:
                    target = selected
            if target is None:
                # Do NOT silently mark the entire physical image or guess a
                # side from navigation order / the name of the folio.
                options = [f'{_t("folio.split.left")} {parts[0].label}',
                           f'{_t("folio.split.right")} {parts[1].label}']
                choice, ok = QInputDialog.getItem(
                    self, _t('folio.mark.choose_title'),
                    _t('folio.mark.choose_prompt'), options, 0, False)
                if not ok:
                    return
                target = parts[options.index(choice)]
            sid, label = target.ref, target.label
        self.markPageRequested.emit(self.siglum, sid, label)

    def set_surface(self, surface_id):
        if not self.sync_enabled and self.set_folio(surface_id):
            return True
        index = self._surface_indices.get(str(surface_id or ""))
        if index is None:
            return False
        self.center_index = index
        self.origin_center_index = index
        self._active_folio = str(surface_id)
        self.reload()
        return True

    def open_page(self):
        item = self.current_item()
        if not item: return
        kind, target = full_page_target(item["p"], self.project_root)
        if kind == "file" and target is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))
        elif kind == "url" and target:
            QDesktopServices.openUrl(QUrl(str(target)))

    def _window_indices(self):
        return display_window_indices(self.items, self.center_index, 1)

    def reload(self):
        self.load_token += 1; token = self.load_token
        self.loaded_groups = {}; self.group_specs = []
        self.view.scene().clear(); self.message.hide(); self.message.setText("")
        inds = self._window_indices()
        if not inds:
            self.status.setText(_t("manuscript.no_line")); return
        groups = []
        for i in inds:
            item = self.items[i]
            pid = item["p"].get("id")
            if not groups or groups[-1][0] != pid:
                groups.append((pid, [i]))
            else:
                groups[-1][1].append(i)
        specs = []
        for gi, (pid, ginds) in enumerate(groups):
            gitems = [self.items[i] for i in ginds]
            page_mode = all(bool(x["l"].get("_page_mode")) for x in gitems)
            image_only = all(bool(x["l"].get("_image_only")) for x in gitems)
            crop = None if (page_mode or image_only) else crop_for_items(gitems, project_root=self.project_root)
            req = iiif_image_request(gitems[0]["p"], crop, self.project_root)
            url = req.get("url") if req else None
            specs.append({
                "key": f"g{gi}", "indices": ginds, "items": gitems, "crop": crop,
                "url": url,
                "local_crop": bool(req and req.get("local_crop")),
                "fallback_url": req.get("fallback_url") if req else None,
                "fallback_local_crop": bool(req and req.get("fallback_local_crop")),
                "source_type": req.get("source_type") if req else None,
                "image_only": image_only, "page_mode": page_mode,
            })
        self.group_specs = specs; self.pending = sum(1 for s in specs if s["url"])
        center = self.current_item(); page_label = image_page_label(center["p"], self.project_root)
        line_no = center["l"].get("line")
        score = center["l"].get("score")
        if center["l"].get("_page_mode") or center["l"].get("_image_only"):
            active = self._current_folio()
            if active:
                page_label = active.label
            self.status.setText(_t("manuscript.status.page_only_count", page=page_label, current=self.center_index + 1, total=len(self.items)))
        else:
            extra = _t("manuscript.score", score=f"{score:.0%}") if isinstance(score, (int,float)) and not self.is_base else ""
            self.status.setText(_t("manuscript.status", page=page_label, line=line_no, extra=extra))
        self._update_mark_page_button()
        if not self.pending:
            current = self.current_item()
            state = ((current or {}).get('p') or {}).get('iiif_resolution') or {}
            reason = state.get('status', '')
            detail = state.get('method', '')
            key = ('manuscript.no_image_reason.ambiguous' if reason == 'ambiguous' else
                   'manuscript.no_image_reason.canvas_not_found' if detail == 'canvas_not_found' else
                   'manuscript.no_image_reason.no_match' if reason == 'unresolved' else
                   'manuscript.no_image_source')
            self.message.setText(_t(key)); self.message.show(); return
        self.message.setText(_t("manuscript.loading")); self.message.setStyleSheet("color:#746b61;border:0;font-size:11px"); self.message.show()
        for spec in specs:
            url = spec["url"]
            if not url: continue
            if url in self._memory_cache:
                QTimer.singleShot(0, lambda s=spec, d=self._memory_cache[url], t=token: self._fetch_finished(t, s["key"], d, "", "crop"))
            else:
                w = FetchWorker(token, spec["key"], url, spec.get("fallback_url"))
                w.signals.finished.connect(self._fetch_finished)
                self.threadpool.start(w)

    @Slot(int, str, bytes, str, str)
    def _fetch_finished(self, token, key, data, error, source_mode):
        if token != self.load_token: return
        spec = next((s for s in self.group_specs if s["key"] == key), None)
        if not spec: return
        self.pending = max(0, self.pending - 1)
        if error:
            self.loaded_groups[key] = {"error": error, "pixmap": None}
        else:
            if spec.get("source_type") == "file":
                ba = QByteArray(data)
                buf = QBuffer(); buf.setData(ba); buf.open(QIODevice.OpenModeFlag.ReadOnly)
                reader = QImageReader(buf); reader.setAutoTransform(True)
                image = reader.read()
                pix = QPixmap.fromImage(image) if not image.isNull() else QPixmap()
                ok = not pix.isNull()
            else:
                pix = QPixmap(); ok = pix.loadFromData(data)
            if ok:
                if source_mode != "fallback":
                    self._memory_cache[spec["url"]] = data
                use_local_crop = spec.get("local_crop") if source_mode != "fallback" else spec.get("fallback_local_crop")
                if use_local_crop:
                    page = spec["items"][0]["p"]
                    iw0, ih0 = page_image_dimensions(page, self.project_root)
                    iw = float(iw0 or pix.width())
                    ih = float(ih0 or pix.height())
                    # Pour une image locale sans dimensions déclarées, les
                    # dimensions réelles du pixmap sont l'autorité.
                    src = page_image_source(page, self.project_root)
                    if src.kind == "file" and (src.width is None or src.height is None):
                        iw, ih = float(pix.width()), float(pix.height())
                    crop = spec.get("crop") or {"x": 0, "y": 0, "w": iw, "h": ih}
                    sx = pix.width() / max(1.0, iw)
                    sy = pix.height() / max(1.0, ih)
                    x = max(0, int(round(crop["x"] * sx)))
                    y = max(0, int(round(crop["y"] * sy)))
                    w = max(1, int(round(crop["w"] * sx)))
                    h = max(1, int(round(crop["h"] * sy)))
                    w = min(w, max(1, pix.width() - x))
                    h = min(h, max(1, pix.height() - y))
                    pix = pix.copy(x, y, w, h)
                note = " · repli highres" if source_mode == "fallback" else ""
                self.loaded_groups[key] = {"error": "", "pixmap": pix, "note": note}
            else:
                self.loaded_groups[key] = {"error": "format d'image non reconnu", "pixmap": None}
        if self.pending == 0:
            self._redraw_scene()

    def _redraw_scene(self):
        scene = self.view.scene(); scene.clear()
        focus_rect = None
        folio = self._current_folio() if not self.sync_enabled else None
        yoff = 0.0; errors = []; frame_count = 0; missing_frame_geometry = False
        divider_pen = QPen(QColor("#c8beb1")); divider_pen.setWidth(3)
        frame_pen = QPen(QColor("#d45735")); frame_pen.setWidth(3)
        current_pen = QPen(QColor("#3272a6")); current_pen.setWidth(3)
        for idx, spec in enumerate(self.group_specs):
            loaded = self.loaded_groups.get(spec["key"], {})
            pix = loaded.get("pixmap")
            if pix is None:
                if loaded.get("error"): errors.append(loaded["error"])
                continue
            item_pix = QGraphicsPixmapItem(pix); item_pix.setPos(0, yoff); scene.addItem(item_pix)
            # The displayed pixmap may be a IIIF derivative (or a low-res
            # offline copy) with pixels unlike the full Canvas dimensions.
            # Lines and polygons are expressed in the physical source space;
            # map them to the *actual* pixmap or frames can enlarge the entire
            # scene and make a double page look tiny even at 244 % zoom.
            crop = image_scene_reference_crop(
                spec["items"][0]["p"], pix.width(), pix.height(),
                spec["crop"], self.project_root)
            sx = pix.width() / max(1.0, crop["w"]); sy = pix.height() / max(1.0, crop["h"])
            if folio is not None and folio.region is not None and spec.get('page_mode'):
                if folio.surface == str(spec['items'][0]['p'].get('tei_surface_id') or ''):
                    focus_rect = QRectF(*scene_rect_for_folio(
                        folio.region, crop, pix.width(), pix.height(), yoff))
            if self.show_frames and not spec.get("image_only"):
                if spec.get("page_mode"):
                    # Sans synchronisation ligne-à-ligne, afficher tous les cadres
                    # ALTO de la page sans en privilégier un arbitrairement.
                    page = spec["items"][0]["p"]
                    frame_items = [{"p": page, "l": line} for line in (page.get("lines") or [])]
                    frame_iter = [(None, it) for it in frame_items]
                else:
                    # Always draw the current physical line. With the blue
                    # outline, a manually navigated line remains distinct from
                    # synchronized matches (orange). In particular, the user
                    # no longer sees an empty frame layer when the target was
                    # previously chosen by an arithmetic midpoint.
                    visible = visible_line_frame_indices(
                        spec["indices"], self.center_index, self.match_indices)
                    frame_iter = ((ix, it) for ix, it in zip(spec["indices"], spec["items"])
                                  if ix in visible)
                for physical_idx, line_item in frame_iter:
                    if not effective_line_bbox(line_item["l"]):
                        # Do not draw a misleading one-pixel box at 0,0 when a
                        # synchronization provides no geometric information.
                        missing_frame_geometry = True
                        continue
                    b = scaled_bbox(line_item, self.project_root)
                    x = (b["x"] - crop["x"]) * sx
                    y = yoff + (b["y"] - crop["y"]) * sy
                    w = b["w"] * sx; h = b["h"] * sy
                    points = scaled_polygon(line_item, self.project_root)
                    if len(points) >= 3:
                        vertices = QPolygonF([QPointF((px - crop['x']) * sx,
                                                       yoff + (py - crop['y']) * sy)
                                              for px, py in points])
                        shape = QGraphicsPolygonItem(vertices)
                    else:
                        shape = QGraphicsRectItem(x, y, w, h)
                    is_linked = spec.get("page_mode") or physical_idx in self.match_indices
                    shape.setPen(frame_pen if is_linked else current_pen)
                    shape.setBrush(QBrush(Qt.BrushStyle.NoBrush))
                    scene.addItem(shape)
                    frame_count += 1
            yoff += pix.height()
            if idx < len(self.group_specs)-1:
                scene.addLine(0, yoff+1, max(1, pix.width()), yoff+1, divider_pen); yoff += 4
        if not scene.items():
            self.message.setText(_t("manuscript.image_failed", detail=(" : " + " | ".join(errors[:2]) if errors else "")))
            self.message.setStyleSheet("color:#9b4636;border:0;font-size:11px"); self.message.show()
        elif self.show_frames and missing_frame_geometry and not frame_count:
            self.message.setText(_t("manuscript.frames.no_geometry"))
            self.message.setStyleSheet("color:#9b4636;border:0;font-size:11px")
            self.message.show()
        else:
            self.message.hide()
        self.view.folio_focus_rect = focus_rect
        self.view.reset_zoom(); self.update_zoom_label()


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



class CompletionDialog(QDialog):
    """Petit sélecteur filtrable pour Ctrl+Espace.

    Le dialogue est volontairement générique : le calcul du contexte et les
    modifications XML restent dans MainWindow, ce qui facilite les tests du
    moteur RELAX NG sans Qt.
    """

    def __init__(self, title, label, items, prefix="", parent=None, allow_custom=False):
        super().__init__(parent)
        # Chaque entrée peut être une simple chaîne (compatibilité historique)
        # ou un couple (valeur, provenance) où provenance vaut rng/custom/both.
        # La provenance n'est qu'une information d'interface : elle ne change
        # jamais la validité du document.
        self._all_items = []
        for item in items:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                value, source = str(item[0]), str(item[1])
                source_key = {
                    "rng": "completion.source.rng",
                    "custom": "completion.source.custom",
                    "both": "completion.source.both",
                }.get(source)
                display = (f"{value}    [{_t(source_key)}]" if source_key else value)
            else:
                value = str(item)
                display = value
            self._all_items.append((value, display))
        self._selected = None
        self._allow_custom = bool(allow_custom)
        self.setWindowTitle(title)
        self.resize(360, 330)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        self.label = QLabel(label)
        self.label.setWordWrap(True)
        root.addWidget(self.label)
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText(_t("completion.filter.placeholder"))
        root.addWidget(self.filter_box)
        self.list_widget = QListWidget()
        root.addWidget(self.list_widget, 1)
        self.filter_box.textChanged.connect(self._refilter)
        self.filter_box.returnPressed.connect(self._accept_current)
        self.list_widget.itemActivated.connect(lambda _item: self._accept_current())
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_current())
        self.filter_box.setText(prefix or "")
        self._refilter(prefix or "")
        self.filter_box.setFocus()
        self.filter_box.setCursorPosition(len(prefix or ""))

    @property
    def selected_value(self):
        return self._selected

    def _refilter(self, text):
        needle = (text or "").casefold()
        starts = [x for x in self._all_items if x[0].casefold().startswith(needle)]
        contains = [x for x in self._all_items
                    if needle in x[0].casefold() and x not in starts]
        values = starts + contains
        self.list_widget.clear()
        for value, display in values:
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _accept_current(self):
        typed = self.filter_box.text().strip()
        raw_values = {value for value, _display in self._all_items}
        if self._allow_custom and typed and typed not in raw_values:
            # En mode Ctrl+E, le champ reste réellement éditable : une saisie
            # manuelle ne doit pas être remplacée par le premier résultat dont
            # elle n'est qu'un préfixe.
            self._selected = typed
            self.accept()
            return
        item = self.list_widget.currentItem()
        if item is not None:
            self._selected = item.data(Qt.ItemDataRole.UserRole) or item.text()
            self.accept()
            return
        if self._allow_custom and typed:
            self._selected = typed
            self.accept()


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


class SoftwareHelpDialog(QDialog):
    """Aide intégrée, localisée, sans navigateur embarqué pour les ressources externes."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("help.software"))
        self.resize(900, 720)
        layout = QVBoxLayout(self)
        browser = QTextBrowser(self)
        language = I18N.language
        path = HERE / "help" / f"{language}.html"
        if not path.is_file():
            fallback = I18N.fallback if (HERE / "help" / f"{I18N.fallback}.html").is_file() else "fr"
            path = HERE / "help" / f"{fallback}.html"
        try:
            browser.setHtml(path.read_text(encoding="utf-8"))
        except Exception as exc:
            browser.setPlainText(str(exc))
        browser.setOpenExternalLinks(True)
        layout.addWidget(browser, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)


def _selected_text_for_dictionary(window) -> str:
    """Retourne la sélection textuelle active, ou le mot sous le curseur."""
    widget = QApplication.focusWidget()
    candidates = []
    while widget is not None:
        candidates.append(widget)
        widget = widget.parentWidget() if hasattr(widget, "parentWidget") else None
    for name in ("editor",):
        candidate = getattr(window, name, None)
        if candidate is not None:
            candidates.append(candidate)
    formatted = getattr(window, "formatted_view", None)
    if formatted is not None:
        for name in ("fragment_editor", "preview"):
            candidate = getattr(formatted, name, None)
            if candidate is not None:
                candidates.append(candidate)
    seen = set()
    for candidate in candidates:
        if id(candidate) in seen or not hasattr(candidate, "textCursor"):
            continue
        seen.add(id(candidate))
        try:
            cursor = candidate.textCursor()
            text = cursor.selectedText()
            if not text:
                probe = QTextCursor(cursor)
                probe.select(QTextCursor.SelectionType.WordUnderCursor)
                text = probe.selectedText()
            text = re.sub(r"\s+", " ", (text or "").replace("\u2029", " ")).strip()
            if text:
                return text
        except Exception:
            continue
    return ""


def _open_external(url: str) -> None:
    QDesktopServices.openUrl(QUrl(url))


def _open_latin_dictionary(window) -> None:
    query = _selected_text_for_dictionary(window)
    url = "https://www.vocabula.lat/?q=" + quote_plus(query)
    _open_external(url)


def _show_software_help(window) -> None:
    SoftwareHelpDialog(window).exec()


def _varians_font(point_size: int) -> QFont:
    """Police de marque : Cormorant Garamond SemiBold si disponible.

    Qt choisit automatiquement une police de repli si la famille n'est pas
    installée ; aucun fichier de police n'est embarqué dans Varians.
    """
    font = QFont("Cormorant Garamond", int(point_size))
    font.setStyleName("SemiBold")
    font.setWeight(QFont.Weight.DemiBold)
    return font


def _scaled_logo_label(parent, filename: str, max_w: int, max_h: int) -> QLabel:
    label = QLabel(parent)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    pix = QPixmap(str(HERE / "resources" / filename))
    if not pix.isNull():
        label.setPixmap(pix.scaled(
            max_w, max_h, Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        ))
    return label


def _build_varians_card(parent, include_dismiss_hint=False) -> QFrame:
    """Carte de marque commune à l'accueil et à « À propos… »."""
    frame = QFrame(parent)
    frame.setObjectName("variansWelcomeCard")
    frame.setFrameShape(QFrame.Shape.StyledPanel)
    frame.setStyleSheet(
        "QFrame#variansWelcomeCard { background: palette(base); "
        "border: 1px solid palette(mid); border-radius: 10px; }"
    )
    frame.setMaximumWidth(760)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(42, 32, 42, 32)
    layout.setSpacing(13)

    # Logo propre à Varians, au-dessus du nom.
    layout.addWidget(_scaled_logo_label(frame, "varians_logo.png", 300, 145),
                     0, Qt.AlignmentFlag.AlignHCenter)

    title = QLabel("Varians", frame)
    title.setFont(_varians_font(38))
    title.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(title)

    subtitle = QLabel(_t("welcome.subtitle"), frame)
    f = subtitle.font(); f.setPointSize(15); subtitle.setFont(f)
    subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
    subtitle.setWordWrap(True)
    layout.addWidget(subtitle)

    pi = QLabel(_t("welcome.pi"), frame)
    f = pi.font(); f.setPointSize(12); pi.setFont(f)
    pi.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(pi)

    version = QLabel(_t("welcome.version", version=APP_VERSION), frame)
    f = version.font(); f.setPointSize(11); version.setFont(f)
    version.setAlignment(Qt.AlignmentFlag.AlignCenter)
    layout.addWidget(version)

    institutions = QHBoxLayout()
    institutions.setSpacing(32)
    institutions.addStretch(1)
    institutions.addWidget(_scaled_logo_label(frame, "ciham.png", 190, 95))
    institutions.addWidget(_scaled_logo_label(frame, "cnrs.png", 90, 90))
    institutions.addStretch(1)
    layout.addLayout(institutions)

    if include_dismiss_hint:
        hint = QLabel(_t("welcome.dismiss"), frame)
        f = hint.font(); f.setItalic(True); f.setPointSize(9); hint.setFont(f)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(hint)
    return frame


class AboutDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("help.about"))
        self.resize(790, 650)
        root = QVBoxLayout(self)
        root.setContentsMargins(18, 18, 18, 18)
        root.addStretch(1)
        root.addWidget(_build_varians_card(self, False), 0, Qt.AlignmentFlag.AlignCenter)
        root.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        root.addWidget(buttons)


def _show_about(window) -> None:
    AboutDialog(window).exec()


class DetachedWitnessWindow(QWidget):
    """Independent native window owning the ORIGINAL ManuscriptPanel.

    A regular close docks its panel. Closing the main editor sets
    ``_closing_workspace`` first, so a project cannot outlive its owner.
    """

    def __init__(self, main, witness_id, panel, always_on_top=False):
        super().__init__(None, Qt.WindowType.Window)
        self.main = main
        self.witness_id = str(witness_id)
        self.panel = panel
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
        self.setWindowTitle(_t('workspace.detached.title', witness=self.witness_id))
        root = QVBoxLayout(self)
        root.setContentsMargins(5, 5, 5, 5)
        root.setSpacing(3)
        controls = QHBoxLayout()
        self.always_on_top = QCheckBox(_t('workspace.always_on_top'), self)
        self.always_on_top.setChecked(bool(always_on_top))
        self.dock_button = QPushButton(_t('workspace.attach'), self)
        self.dock_button.clicked.connect(self.close)
        self.always_on_top.toggled.connect(self._set_always_on_top)
        controls.addWidget(self.always_on_top)
        controls.addStretch(1)
        controls.addWidget(self.dock_button)
        root.addLayout(controls)
        root.addWidget(panel, 1)
        panel._detached = True
        panel.retranslate_ui()
        panel.set_compact_toolbar(False)
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(always_on_top))
        self.resize(800, 620)

    def _set_always_on_top(self, enabled):
        if not self.main._closing_workspace:
            _settings().setValue(self.main._view_settings_key(
                f'floatingAlwaysOnTop/{self.witness_id}'), bool(enabled))
        # Changing native window flags hides the HWND on Windows; restore it
        # explicitly, retaining position, size and focus as far as possible.
        geometry = self.saveGeometry()
        self.setWindowFlag(Qt.WindowType.WindowStaysOnTopHint, bool(enabled))
        self.show()
        self.restoreGeometry(geometry)
        self.raise_()

    def retranslate_ui(self):
        self.setWindowTitle(_t('workspace.detached.title', witness=self.witness_id))
        self.always_on_top.setText(_t('workspace.always_on_top'))
        self.dock_button.setText(_t('workspace.attach'))

    def closeEvent(self, event):
        _settings().setValue(self.main._view_settings_key(
            f'floatingGeometry/{self.witness_id}'), self.saveGeometry())
        if not self.main._closing_workspace:
            self.main._dock_witness(self.witness_id, from_window=True)
        event.accept()


class WitnessVisibilityDialog(QDialog):
    """Per-project local preferences: checked witnesses AND panel order."""

    def __init__(self, witnesses, available_ids, selected_ids, order_ids, parent=None):
        super().__init__(parent)
        from witness_layout import normalized_witness_order
        self.setWindowTitle(_t("view.witnesses.title"))
        self.resize(600, 460)
        root = QVBoxLayout(self)
        info = QLabel(_t("view.witnesses.hint"), self)
        info.setWordWrap(True)
        root.addWidget(info)

        self.list = QListWidget(self)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        available_ids = set(available_ids or ())
        selected_ids = set(selected_ids or ())
        by_id = {str(w.id): w for w in witnesses}
        for wid in normalized_witness_order(by_id, order_ids):
            w = by_id[wid]
            label = f"{w.id} — {w.label}" if getattr(w, "label", "") else str(w.id)
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, wid)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            if wid in available_ids:
                item.setCheckState(Qt.CheckState.Checked if wid in selected_ids else Qt.CheckState.Unchecked)
            else:
                item.setCheckState(Qt.CheckState.Unchecked)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
                item.setToolTip(_t("view.witnesses.no_image"))
            self.list.addItem(item)
        root.addWidget(self.list, 1)

        controls = QHBoxLayout()
        self.all_btn = QPushButton(_t("view.witnesses.all"), self)
        self.none_btn = QPushButton(_t("view.witnesses.none"), self)
        self.up_btn = QPushButton(_t("view.witnesses.move_up"), self)
        self.down_btn = QPushButton(_t("view.witnesses.move_down"), self)
        self.all_btn.clicked.connect(self._select_all)
        self.none_btn.clicked.connect(self._select_none)
        self.up_btn.clicked.connect(lambda: self._move_selected(-1))
        self.down_btn.clicked.connect(lambda: self._move_selected(1))
        self.list.currentRowChanged.connect(self._update_move_buttons)
        controls.addWidget(self.all_btn)
        controls.addWidget(self.none_btn)
        controls.addStretch(1)
        controls.addWidget(self.up_btn)
        controls.addWidget(self.down_btn)
        root.addLayout(controls)
        self.list.setCurrentRow(0)
        self._update_move_buttons()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _update_move_buttons(self, *_args):
        row = self.list.currentRow()
        self.up_btn.setEnabled(row > 0)
        self.down_btn.setEnabled(0 <= row < self.list.count() - 1)

    def _move_selected(self, direction):
        row = self.list.currentRow()
        target = row + int(direction)
        if row < 0 or target < 0 or target >= self.list.count():
            return
        item = self.list.takeItem(row)
        self.list.insertItem(target, item)
        self.list.setCurrentRow(target)
        self._update_move_buttons()

    def _select_all(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(Qt.CheckState.Checked)

    def _select_none(self):
        for i in range(self.list.count()):
            item = self.list.item(i)
            if item.flags() & Qt.ItemFlag.ItemIsEnabled:
                item.setCheckState(Qt.CheckState.Unchecked)

    def ordered_ids(self):
        """All witnesses, including unchecked ones (their position is kept)."""
        return [str(self.list.item(i).data(Qt.ItemDataRole.UserRole))
                for i in range(self.list.count())]

    def selected_ids(self):
        return [str(self.list.item(i).data(Qt.ItemDataRole.UserRole))
                for i in range(self.list.count())
                if self.list.item(i).checkState() == Qt.CheckState.Checked]


class WitnessDiagnosticDialog(QDialog):
    """Read-only audit of witness resources (no OCR or TEI text is exposed)."""

    def __init__(self, rows, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t('diagnostics.title'))
        self.resize(1040, 520)
        self._rows = tuple(rows)
        root = QVBoxLayout(self)
        self.intro = QLabel(_t('diagnostics.intro'))
        self.intro.setWordWrap(True)
        root.addWidget(self.intro)
        self.table = QTableWidget(len(rows), 7, self)
        self.table.setHorizontalHeaderLabels([
            _t('diagnostics.column.witness'), _t('diagnostics.column.mode'),
            _t('diagnostics.column.pages'), _t('diagnostics.column.images'),
            _t('diagnostics.column.geometry'), _t('diagnostics.column.links'),
            _t('diagnostics.column.issues'),
        ])
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        for i, row in enumerate(rows):
            issue_text = self._issue_text(row)
            status = (_t('diagnostics.mode.active') if row.active
                      else _t('diagnostics.mode.page'))
            cells = (f'{row.id} — {row.label}', status, str(row.pages), str(row.images),
                     str(row.geometry_lines),
                     str(row.usable_links) if not row.is_base else '—',
                     issue_text or _t('diagnostics.no_issues'))
            for j, value in enumerate(cells):
                item = QTableWidgetItem(value)
                item.setToolTip(issue_text)
                self.table.setItem(i, j, item)
        root.addWidget(self.table, 1)
        explanation = QLabel(_t('diagnostics.footer'))
        explanation.setWordWrap(True)
        root.addWidget(explanation)
        buttons = QHBoxLayout()
        copy_btn = QPushButton(_t('diagnostics.copy'), self)
        copy_btn.clicked.connect(self.copy_report)
        buttons.addWidget(copy_btn)
        refresh_btn = QPushButton(_t('diagnostics.refresh'), self)
        refresh_btn.clicked.connect(self.refresh_and_reopen)
        buttons.addWidget(refresh_btn)
        buttons.addStretch(1)
        close = QPushButton(_t('common.close'), self)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        root.addLayout(buttons)

    @staticmethod
    def _issue_text(row):
        if not row.issue_codes:
            return ''
        return '; '.join(_t('diagnostics.issue.' + code) for code in row.issue_codes)

    def copy_report(self):
        lines = [_t('diagnostics.title')]
        for row in self._rows:
            lines.append(f'{row.id} — {row.label}: '
                         f'{row.pages} {_t("diagnostics.column.pages")}; '
                         f'{row.images} {_t("diagnostics.column.images")}; '
                         f'{row.geometry_lines} {_t("diagnostics.column.geometry")}; '
                         f'{row.usable_links} {_t("diagnostics.column.links")}; '
                         f'{self._issue_text(row) or _t("diagnostics.no_issues")}')
        QApplication.clipboard().setText('\n'.join(lines))

    def refresh_and_reopen(self):
        main = self.parent()
        self.accept()
        if main is not None and main.refresh_witness_synchronizations():
            QTimer.singleShot(0, main.show_witness_diagnostics)


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


class MainWindow(QMainWindow):
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

    def _build_xpath_panel(self):
        """Panneau inférieur de recherche XPath avec résultats navigables."""
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.xpath_title = QLabel(_t("xpath.panel.title"))
        title_font = self.xpath_title.font(); title_font.setBold(True)
        self.xpath_title.setFont(title_font)
        self.xpath_query = QLineEdit(panel)
        self.xpath_query.setClearButtonEnabled(True)
        self.xpath_query.setPlaceholderText(_t("xpath.placeholder"))
        self.xpath_query.returnPressed.connect(self.run_xpath_search)
        self.xpath_run_button = QPushButton(_t("xpath.run"), panel)
        self.xpath_run_button.clicked.connect(self.run_xpath_search)
        self.xpath_close = QToolButton(panel)
        self.xpath_close.setText("×")
        self.xpath_close.setToolTip(_t("xpath.close"))
        self.xpath_close.clicked.connect(self.hide_xpath_panel)
        head.addWidget(self.xpath_title)
        head.addWidget(self.xpath_query, 1)
        head.addWidget(self.xpath_run_button)
        head.addWidget(self.xpath_close)
        root.addLayout(head)

        self.xpath_summary = QLabel("")
        self.xpath_summary.setWordWrap(True)
        root.addWidget(self.xpath_summary)

        self.xpath_table = QTableWidget(0, 4, panel)
        self.xpath_table.setHorizontalHeaderLabels([
            _t("xpath.column.line"), _t("xpath.column.element"),
            _t("xpath.column.path"), _t("xpath.column.preview"),
        ])
        header = self.xpath_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Interactive)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.xpath_table.setColumnWidth(2, 300)
        self.xpath_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.xpath_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.xpath_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.xpath_table.setAlternatingRowColors(True)
        self.xpath_table.setMouseTracking(True)
        self.xpath_table.viewport().setMouseTracking(True)
        # La palette claire de sélection est installée globalement pour que
        # XPath, RELAX NG et les autres listes aient le même rendu lisible.
        # Un simple clic suffit, conformément au comportement demandé.
        self.xpath_table.cellClicked.connect(self.goto_xpath_result)
        root.addWidget(self.xpath_table, 1)
        panel.setVisible(False)
        return panel

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

    def show_xpath_panel(self):
        self._show_bottom_panel(self.xpath_panel, 250)

    def hide_xpath_panel(self):
        self.xpath_panel.setVisible(False)
        self.left_splitter.setSizes([max(300, self.left_splitter.height()), 0, 0])

    def focus_xpath_search(self):
        self.left_tabs.setCurrentIndex(0)
        self.show_xpath_panel()
        selected = self.editor.textCursor().selectedText().strip()
        if selected and selected.startswith("//") and "\u2029" not in selected:
            self.xpath_query.setText(selected)
        self.xpath_query.setFocus()
        self.xpath_query.selectAll()

    def run_xpath_search(self):
        expression = self.xpath_query.text().strip()
        if not expression:
            self.xpath_query.setFocus()
            return
        text = self.editor.toPlainText()
        try:
            result = search_xpath(text, expression)
        except XPathUnavailable:
            self.xpath_table.setRowCount(0)
            self.xpath_summary.setText(_t("xpath.lxml_missing"))
            self.show_xpath_panel()
            return
        except XPathQueryError as exc:
            self.xpath_table.setRowCount(0)
            if str(exc) == "EMPTY_XPATH":
                self.xpath_summary.setText(_t("xpath.empty"))
            else:
                self.xpath_summary.setText(_t("xpath.error", error=exc))
            self.show_xpath_panel()
            return

        self.xpath_table.setRowCount(0)
        if result.scalar_value is not None:
            self.xpath_summary.setText(_t("xpath.scalar", value=result.scalar_value))
            self.show_xpath_panel()
            return

        for match in result.matches:
            row = self.xpath_table.rowCount()
            self.xpath_table.insertRow(row)
            values = [str(match.line or ""), match.tag, match.path, match.preview]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.xpath_table.setItem(row, col, item)
            self.xpath_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                (int(match.position), int(match.end_position), int(match.line or 0)),
            )

        if result.matches:
            if result.namespace_fallback_used:
                self.xpath_summary.setText(_t(
                    "xpath.found_tei_fallback", count=len(result.matches),
                    expression=result.effective_expression,
                ))
            else:
                self.xpath_summary.setText(_t("xpath.found", count=len(result.matches)))
        elif result.ignored_non_elements:
            self.xpath_summary.setText(_t("xpath.non_elements", count=result.ignored_non_elements))
        else:
            self.xpath_summary.setText(_t("xpath.none"))
        self.show_xpath_panel()

    def goto_xpath_result(self, row, _column=0):
        item = self.xpath_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        if len(data) >= 3:
            position, end_position, _line = data[:3]
        else:  # compatibilité défensive avec une ligne de résultat plus ancienne
            position, _line = data
            end_position = position
        self.left_tabs.setCurrentIndex(0)
        cursor = self.editor.textCursor()
        doc_last = max(0, self.editor.document().characterCount() - 1)
        start = max(0, min(int(position), doc_last))
        end = max(start, min(int(end_position), doc_last))
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    def _build_validation_panel(self):
        """Construit le panneau RELAX NG placé sous les vues XML/XSLT."""
        panel = QFrame(self)
        panel.setFrameShape(QFrame.Shape.StyledPanel)
        root = QVBoxLayout(panel)
        root.setContentsMargins(6, 4, 6, 6)
        root.setSpacing(4)

        head = QHBoxLayout()
        self.validation_title = QLabel(_t("rng.panel.title"))
        title_font = self.validation_title.font(); title_font.setBold(True)
        self.validation_title.setFont(title_font)
        self.validation_summary = QLabel(_t("rng.panel.no_validation"))
        self.validation_summary.setWordWrap(True)
        self.validation_refresh = QToolButton(panel)
        self.validation_refresh.setText("↻")
        self.validation_refresh.setToolTip(_t("rng.panel.refresh"))
        self.validation_refresh.clicked.connect(self.refresh_schema_cache)
        self.validation_close = QToolButton(panel)
        self.validation_close.setText("×")
        self.validation_close.setToolTip(_t("rng.panel.close"))
        self.validation_close.clicked.connect(self.hide_validation_panel)
        head.addWidget(self.validation_title)
        head.addWidget(self.validation_summary, 1)
        head.addWidget(self.validation_refresh)
        head.addWidget(self.validation_close)
        root.addLayout(head)

        self.validation_table = QTableWidget(0, 4, panel)
        self.validation_table.setHorizontalHeaderLabels([
            _t("rng.column.level"), _t("rng.column.line"),
            _t("rng.column.column"), _t("rng.column.message"),
        ])
        header = self.validation_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        self.validation_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.validation_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.validation_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.validation_table.setAlternatingRowColors(True)
        self.validation_table.setMouseTracking(True)
        self.validation_table.viewport().setMouseTracking(True)
        self.validation_table.cellDoubleClicked.connect(self.goto_validation_issue)
        root.addWidget(self.validation_table, 1)
        panel.setVisible(False)
        return panel

    def _reset_validation_state(self):
        """Vide tout diagnostic lié au document/projet précédent.

        Cette remise à zéro est volontairement appelée lors de chaque ouverture
        de fichier afin qu'aucune erreur RELAX NG antérieure ne reste visible
        pendant que la validation du nouveau document se prépare.
        """
        self.document.reset_validation()
        if hasattr(self, 'rng_refresh_timer'):
            self.rng_refresh_timer.stop()
        self._clear_validation_table()
        if hasattr(self, "validation_summary"):
            self.validation_summary.setText(_t("rng.panel.no_validation"))
        if hasattr(self, "rng_status"):
            self.rng_status.setText(_t("rng.status.none") if self.project.schema_mode == "none" else _t("rng.status.pending"))
            self.rng_status.setStyleSheet("color:#777" if self.project.schema_mode == "none" else "")

    def show_validation_panel(self):
        # Une hauteur modeste garde la vue d'édition utilisable sur petit écran.
        self._rng_watch_enabled = True
        self._show_bottom_panel(self.validation_panel, 180)
        # L'onglet XPath, le masquage du panneau ou la restauration d'une
        # fenêtre ne doivent pas faire réapparaître des erreurs anciennes.
        # F8 a déjà validé la révision courante : aucune passe redondante.
        if (self.project.schema_mode != 'none'
                and not getattr(self, '_rng_validation_in_progress', False)
                and self._last_rng_revision != self.editor.document().revision()):
            self.rng_refresh_timer.stop()
            self._auto_refresh_rng()

    def hide_validation_panel(self):
        self.validation_panel.setVisible(False)
        self.left_splitter.setSizes([max(300, self.left_splitter.height()), 0, 0])

    def _clear_validation_table(self):
        self.validation_table.setRowCount(0)

    def _populate_validation_issues(self, issues, *, jump_to_xml=True):
        self._clear_validation_table()
        for issue in issues:
            row = self.validation_table.rowCount()
            self.validation_table.insertRow(row)
            level_text = _t("rng.level.warning") if str(issue.level).upper() == "WARNING" else _t("rng.level.error")
            values = [
                level_text,
                str(issue.line or ""),
                str(issue.column or ""),
                issue.message,
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                self.validation_table.setItem(row, col, item)
            # La donnée est attachée à la première cellule pour le double-clic.
            self.validation_table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                (int(issue.line or 0), int(issue.column or 0), bool(jump_to_xml)),
            )

    def goto_validation_issue(self, row, _column=0):
        """Double-clic sur une erreur : place le curseur à la ligne XML."""
        item = self.validation_table.item(row, 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        if not data:
            return
        line, column, jump_to_xml = data
        if not jump_to_xml or line <= 0:
            return
        self.left_tabs.setCurrentIndex(0)
        block = self.editor.document().findBlockByNumber(max(0, line - 1))
        if not block.isValid():
            return
        cursor = QTextCursor(block)
        # Les colonnes libxml2 sont 1-based lorsqu'elles sont connues.
        offset = max(0, int(column or 1) - 1)
        offset = min(offset, max(0, block.length() - 1))
        cursor.setPosition(block.position() + offset)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        self.editor.setFocus()

    def _auto_refresh_rng(self):
        """A01: revalide l'état courant, même après masquage du panneau.

        Le délai de frappe est conservé, mais le rechargement du tableau ne
        dépend plus du fait que le widget soit visible à l'instant du signal.
        """
        if (not self._rng_watch_enabled or self.project.schema_mode == 'none'
                or getattr(self, '_loading_editor_document', False)):
            return
        revision = self.editor.document().revision()
        if revision == self._last_rng_revision and self._last_rng_result is not None:
            return
        self.validate_relaxng_document(show_panel=False, automatic=True,
                                       document_revision=revision)

    def validate_relaxng_manual(self):
        self.validate_relaxng_document(show_panel=True, show_success_message=True)

    def refresh_schema_cache(self):
        """Force le rechargement d'un RNG distant déclaré par xml-model."""
        self._completion_model = None
        self._completion_model_key = None
        self.validate_relaxng_document(show_panel=True, show_success_message=True, refresh_schema=True)

    def _update_schematron_status(self, resolution):
        count = len(getattr(resolution, "schematron", ()) or ()) if resolution is not None else 0
        if count:
            self.schematron_status.setText(_t("schematron.status.detected", count=count))
            self.schematron_status.setStyleSheet("color:#8b641d")
            self.schematron_status.setToolTip(_t("schematron.status.tooltip"))
        else:
            self.schematron_status.setText("")
            self.schematron_status.setToolTip("")

    def _schema_display_name(self, resolution):
        if resolution is None:
            return ""
        if resolution.href:
            try:
                return Path(resolution.href).name or resolution.href
            except Exception:
                return resolution.href
        return Path(resolution.schema_path).name if resolution.schema_path else ""

    def validate_relaxng_document(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False):
        """Valide la révision courante, sans revalidation récursive du panneau."""
        if getattr(self, '_rng_validation_in_progress', False):
            return None
        self._rng_validation_in_progress = True
        try:
            return self._validate_relaxng_document_impl(
                show_panel=show_panel, show_success_message=show_success_message,
                refresh_schema=refresh_schema, xml_text=xml_text,
                document_revision=document_revision, automatic=automatic,
            )
        finally:
            self._rng_validation_in_progress = False

    def _validate_relaxng_document_impl(self, *, show_panel=False, show_success_message=False, refresh_schema=False, xml_text=None, document_revision=None, automatic=False):
        """Résout puis valide le RNG actif.

        ``xml_text`` permet à Ctrl+S de réutiliser son unique instantané du
        document. La compilation du RNG lui-même est mise en cache dans
        relaxng_validation.py depuis la V0.5.6.
        """
        text = self.editor.toPlainText() if xml_text is None else xml_text
        revision = self.editor.document().revision() if document_revision is None else int(document_revision)
        key = self._schema_resolution_cache_key(text)
        if not refresh_schema and self._completion_resolution_key == key and self._completion_resolution is not None:
            resolution = self._completion_resolution
        else:
            resolution = resolve_schema(
                mode=self.project.schema_mode,
                xml_text=text,
                xml_path=self.current_path or self.project.edition,
                project_schema=self.project.schema,
                force_refresh=refresh_schema,
            )
        # Le chargement/résolution du schéma peut être long (cache distant).
        # Si le document a changé entre-temps, ne jamais publier les anciennes
        # erreurs comme si elles concernaient la révision désormais affichée.
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        self._last_schema_resolution = resolution
        # La validation explicite vient de faire le travail de résolution : la
        # complétion peut réutiliser exactement ce résultat tant que xml-model
        # n'est pas modifié.
        self._completion_resolution_key = self._schema_resolution_cache_key(text)
        self._completion_resolution = resolution
        self._update_schematron_status(resolution)

        if self.project.schema_mode == "none":
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.disabled"))
            self.rng_status.setText(_t("rng.status.none"))
            self.rng_status.setStyleSheet("color:#777")
            if show_panel and not automatic:
                self.show_validation_panel()
            return None

        if resolution.error:
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.schema_resolution_error", error=resolution.error))
            self.rng_status.setText(_t("rng.status.schema_error"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            return None

        if resolution.schema_path is None:
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            if self.project.schema_mode == "auto":
                self.validation_summary.setText(_t("rng.panel.no_xml_model"))
                self.rng_status.setText(_t("rng.status.no_xml_model"))
            else:
                self.validation_summary.setText(_t("rng.panel.no_schema"))
                self.rng_status.setText(_t("rng.status.none"))
            self.rng_status.setStyleSheet("color:#777")
            if show_panel:
                self.show_validation_panel()
            if show_success_message:
                self.statusBar().showMessage(_t("rng.message.no_schema"), 4000)
            return None

        if not lxml_available():
            self._last_rng_result = None
            self._last_rng_revision = revision
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.lxml_missing"))
            self.rng_status.setText(_t("rng.status.unavailable"))
            self.rng_status.setStyleSheet("color:#a14b2f;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            if show_panel or show_success_message:
                QMessageBox.warning(self, _t("rng.lxml_missing.title"), _t("rng.lxml_missing.text"))
            return None

        schema = resolution.schema_path
        result = validate_relaxng(
            text, schema,
            base_url=self.current_path or self.project.edition,
        )
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        self._last_rng_result = result
        self._last_rng_revision = revision
        try:
            self._last_rng_schema_token = relaxng_schema_token(schema)
        except Exception:
            self._last_rng_schema_token = None
        schema_name = self._schema_display_name(resolution)

        if not result.schema_loaded:
            self._populate_validation_issues(result.issues, jump_to_xml=False)
            detail = result.error or _t("rng.schema.invalid.generic")
            self.validation_summary.setText(_t("rng.panel.schema_error", path=schema_name, error=detail))
            self.rng_status.setText(_t("rng.status.schema_error"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            if show_panel:
                self.show_validation_panel()
            return result

        if not result.well_formed:
            self._populate_validation_issues(result.issues, jump_to_xml=True)
            self.validation_summary.setText(_t("rng.panel.xml_invalid"))
            self.rng_status.setText(_t("rng.status.xml_invalid"))
            self.rng_status.setStyleSheet("color:#a13d32;font-weight:600")
            self._set_document_health("malformed")
            if show_panel:
                self.show_validation_panel()
            return result

        if result.valid:
            self._clear_validation_table()
            self.validation_summary.setText(_t("rng.panel.valid", schema=schema_name))
            self.rng_status.setText(_t("rng.status.valid"))
            self.rng_status.setStyleSheet("color:#376b3c")
            self._set_document_health("normal")
            if show_panel:
                self.show_validation_panel()
            if show_success_message:
                self.statusBar().showMessage(_t("rng.message.valid"), 3500)
            return result

        self._populate_validation_issues(result.issues, jump_to_xml=True)
        count = len(result.issues)
        self.validation_summary.setText(_t("rng.panel.invalid", count=count, schema=schema_name))
        self.rng_status.setText(_t("rng.status.invalid", count=count))
        self.rng_status.setStyleSheet("color:#a06a20;font-weight:600")
        self._set_document_health("rng_invalid")
        if not automatic:
            self.show_validation_panel()
        return result

    def _schema_resolution_cache_key(self, xml_text):
        """Clé légère : seules les déclarations xml-model influencent ce cache."""
        mode = (getattr(self.project, "schema_mode", "auto") or "auto").lower()
        project_schema = str(self.project.schema or "")
        xml_path = str((self.current_path or self.project.edition).resolve())
        declarations = detect_xml_models(xml_text) if mode in {"auto", "none"} else ()
        return (mode, project_schema, xml_path, declarations)

    def _resolve_completion_schema(self, xml_text=None):
        """Résout le RNG actif en réutilisant la résolution tant que le prologue
        ``xml-model`` n'a pas changé.

        Cela évite notamment de reconsulter un RNG distant/cache réseau à chaque
        Ctrl+Espace lorsque l'utilisateur ne modifie que le corps de la TEI.
        """
        text = self.editor.toPlainText() if xml_text is None else xml_text
        key = self._schema_resolution_cache_key(text)
        if self._completion_resolution_key == key and self._completion_resolution is not None:
            resolution = self._completion_resolution
            if resolution.schema_path is None or Path(resolution.schema_path).is_file():
                return resolution
        resolution = resolve_schema(
            mode=self.project.schema_mode,
            xml_text=text,
            xml_path=self.current_path or self.project.edition,
            project_schema=self.project.schema,
            force_refresh=False,
        )
        self._completion_resolution_key = key
        self._completion_resolution = resolution
        return resolution

    def _completion_model_for_schema(self, schema_path):
        path = Path(schema_path).expanduser().resolve()
        stat = path.stat()
        key = (str(path), int(stat.st_mtime_ns), int(stat.st_size))
        if self._completion_model is None or self._completion_model_key != key:
            self.statusBar().showMessage(_t("completion.status.loading"), 2000)
            self._completion_model = load_completion_model(path)
            self._completion_model_key = key
        return self._completion_model

    def _custom_completion_config(self):
        """Relit la configuration projet de saisie personnalisée.

        Le fichier est petit et volontairement relu à chaque invocation pour
        que l'éditeur interne de custom-elements.xml prenne effet immédiatement.
        Une erreur est signalée à l'utilisateur, puis la complétion RNG reste
        utilisable sans cette couche de commodité.
        """
        try:
            return load_custom_completion(self.project.custom_elements)
        except Exception as exc:
            detail = (_t("ctrl_e.config.root_error", file=self.project.custom_elements.name)
                      if str(exc) == "ROOT_NOT_CUSTOM_ELEMENTS"
                      else _t("ctrl_e.config.read_error",
                              file=self.project.custom_elements.name, error=exc))
            self.statusBar().showMessage(detail, 6500)
            return None

    def _custom_witness_ids(self):
        return tuple(w.id for w in getattr(self.project, "witnesses", ()) if getattr(w, "id", ""))

    @staticmethod
    def _filter_existing_attributes(values, existing_attributes):
        existing = set(existing_attributes or ())
        existing_local = {x.split(":", 1)[-1] for x in existing}
        return tuple(
            x for x in values
            if x not in existing and x.split(":", 1)[-1] not in existing_local
        )

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

    def rng_element_suggestions(self, editor, position=None):
        """Suggestions de Ctrl+E, enrichies par custom-elements.xml.

        Le résultat conserve la provenance de chaque entrée (RNG / Projet /
        les deux). Les suggestions projet sont une aide de saisie uniquement :
        elles ne rendent jamais un élément valide si le RNG l'interdit.
        """
        source_text = self.editor.toPlainText()
        text = source_text if editor is self.editor else editor.toPlainText()
        cursor = editor.textCursor()
        pos = cursor.position() if position is None else int(position)
        cache = (
            self._source_completion_context_cache
            if editor is self.editor
            else self._fragment_completion_context_cache
        )
        try:
            context = cache.analyze(text, pos)
        except Exception:
            return ()
        if context.kind != "element":
            return ()

        custom = self._custom_completion_config()
        custom_items = custom.element_names() if custom is not None else ()
        rng_items = ()
        try:
            resolution = self._resolve_completion_schema(source_text)
            if (self.project.schema_mode != "none" and not resolution.error
                    and resolution.schema_path is not None):
                model = self._completion_model_for_schema(resolution.schema_path)
                rng_items = model.child_elements_at(
                    context.parent_element,
                    context.preceding_siblings,
                    context.following_siblings,
                )
        except Exception:
            # Ctrl+E reste disponible pendant une correction ou une panne du RNG.
            rng_items = ()
        return tuple(merge_suggestion_sources(rng_items, custom_items, "append"))

    def _auto_attribute_choices(self, editor):
        """A02: filtrage RNG strict sans dialogue ni auto-ajout de valeurs libres."""
        text = editor.toPlainText()
        cursor = editor.textCursor()
        cache = (self._source_completion_context_cache if editor is self.editor
                 else self._fragment_completion_context_cache)
        context = cache.analyze(text, cursor.position())
        if context.kind != "attribute" or not context.prefix:
            return (), context
        model = None
        resolution = self._resolve_completion_schema(self.editor.toPlainText())
        if self.project.schema_mode != "none" and not resolution.error and resolution.schema_path:
            model = self._completion_model_for_schema(resolution.schema_path)
        # La complétion automatique est strictement limitée aux noms démontrés
        # par le RELAX NG. Les suggestions libres du projet restent accessibles
        # par Ctrl+Espace et ne sont pas présentées comme autorisées par le RNG.
        rng_names = model.allowed_attributes(context.current_element) if model else ()
        names = self._filter_existing_attributes(rng_names, context.existing_attributes)
        prefix = context.prefix.casefold()
        return tuple(dict.fromkeys(n for n in names if n.casefold().startswith(prefix))), context

    def show_rng_completion(self, editor):
        """Ctrl+Espace : fermeture XML prioritaire, sinon RNG / aides projet."""
        if editor.show_closing_tag_completion(force=True):
            return
        source_text = self.editor.toPlainText()
        model = None
        resolution = self._resolve_completion_schema(source_text)
        if self.project.schema_mode != "none":
            if resolution.error:
                QMessageBox.warning(
                    self, _t("completion.error.title"),
                    _t("completion.schema_error", error=resolution.error)
                )
            elif resolution.schema_path is not None:
                try:
                    model = self._completion_model_for_schema(resolution.schema_path)
                except Exception as exc:
                    QMessageBox.warning(
                        self, _t("completion.error.title"),
                        _t("completion.analysis_error", error=exc)
                    )

        custom = self._custom_completion_config()
        text = source_text if editor is self.editor else editor.toPlainText()
        cursor = editor.textCursor()
        position = cursor.position()
        cache = (
            self._source_completion_context_cache
            if editor is self.editor
            else self._fragment_completion_context_cache
        )
        context = cache.analyze(text, position)
        has_project_suggestions = False

        if context.kind == "element":
            rng_values = (model.child_elements_at(
                context.parent_element,
                context.preceding_siblings,
                context.following_siblings,
            ) if model is not None else ())
            custom_values = custom.element_names() if custom is not None else ()
            items = merge_suggestion_sources(rng_values, custom_values, "append")
            has_project_suggestions = bool(custom_values)
            title = _t("completion.elements.title")
            parent = context.parent_element or _t("completion.document_root")
            label = _t("completion.elements.label", parent=parent)

        elif context.kind == "attribute":
            rng_values = (model.allowed_attributes(context.current_element)
                          if model is not None else ())
            custom_values = (custom.attribute_names(context.current_element)
                             if custom is not None else ())
            rng_values = self._filter_existing_attributes(rng_values, context.existing_attributes)
            custom_values = self._filter_existing_attributes(custom_values, context.existing_attributes)
            items = merge_suggestion_sources(rng_values, custom_values, "append")
            has_project_suggestions = bool(custom_values)
            title = _t("completion.attributes.title")
            label = _t("completion.attributes.label", element=context.current_element or "?")

        elif context.kind == "attribute_value":
            rng_values = (model.allowed_attribute_values(
                context.current_element, context.current_attribute
            ) if model is not None else ())
            custom_values, custom_mode = (
                custom.attribute_values(
                    context.current_element,
                    context.current_attribute,
                    self._custom_witness_ids(),
                ) if custom is not None else ((), "append")
            )
            items = merge_suggestion_sources(rng_values, custom_values, custom_mode)
            # Les listes de pointeurs TEI (valeurs commençant par #) peuvent
            # contenir plusieurs tokens séparés par des espaces. Adapte alors
            # le contexte au token courant et retire les pointeurs déjà saisis.
            context, remaining_pointer_values = adapt_pointer_list_value_context(
                context, text, position, [value for value, _source in items]
            )
            if remaining_pointer_values != tuple(value for value, _source in items):
                remaining_set = set(remaining_pointer_values)
                items = [item for item in items if item[0] in remaining_set]
            has_project_suggestions = bool(custom_values)
            title = _t("completion.values.title")
            label = _t(
                "completion.values.label",
                attribute=context.current_attribute or "?",
                element=context.current_element or "?",
            )
            if custom_values and custom_mode == "replace":
                label += "\n" + _t("completion.custom.replace_notice")
        else:
            self.statusBar().showMessage(_t("completion.unavailable_here"), 4000)
            return

        if has_project_suggestions and not (
            context.kind == "attribute_value" and custom_values and custom_mode == "replace"
        ):
            label += "\n" + _t("completion.custom.notice")

        # Filtrage par le fragment déjà saisi. Les tuples conservent la source.
        prefix = (context.prefix or "").casefold()
        if prefix:
            filtered = [item for item in items if item[0].casefold().startswith(prefix)]
            if filtered:
                items = filtered
        # Dédupliquer sans perdre l'ordre RNG d'abord, Projet ensuite.
        dedup = []
        seen = set()
        for value, source in items:
            if value in seen:
                continue
            seen.add(value)
            dedup.append((value, source))
        items = dedup
        if not items:
            if model is None and custom is None:
                self.statusBar().showMessage(_t("completion.no_schema"), 4500)
            else:
                self.statusBar().showMessage(_t("completion.no_suggestions"), 4500)
            return

        dlg = CompletionDialog(title, label, items, context.prefix, self)
        try:
            point = editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft())
            dlg.move(point)
        except Exception:
            pass
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_value:
            return
        self._apply_rng_completion(editor, context, dlg.selected_value)

    def _apply_rng_completion(self, editor, context, value):
        """Insère la suggestion sans remplacer une sélection éditoriale existante."""
        doc = editor.document()
        cursor = QTextCursor(doc)
        start = max(0, int(context.replace_start))
        end = max(start, int(context.replace_end))
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        if context.kind == "element":
            if context.typed_lt:
                replacement = f"{value}></{value}>"
                inner_pos = start + len(value) + 1
            else:
                replacement = f"<{value}></{value}>"
                inner_pos = start + len(value) + 2
            cursor.insertText(replacement)
            out = QTextCursor(doc)
            out.setPosition(inner_pos)
            editor.setTextCursor(out)
        elif context.kind == "attribute_value":
            replacement, final_pos = format_pointer_list_insertion(
                editor.toPlainText(), start, end, value
            )
            cursor.insertText(replacement)
            out = QTextCursor(doc)
            out.setPosition(final_pos)
            editor.setTextCursor(out)
        else:
            before = editor.toPlainText()[max(0, start - 1):start]
            lead = "" if (before.isspace() or before in {"<", ""}) else " "
            replacement = f'{lead}{value}=""'
            cursor.insertText(replacement)
            quote_pos = start + len(lead) + len(value) + 2
            out = QTextCursor(doc)
            out.setPosition(quote_pos)
            editor.setTextCursor(out)
        editor.ensureCursorVisible()
        editor.setFocus()

    def _view_settings_key(self, suffix):
        try:
            identity = str(Path(self.project.path).resolve())
        except Exception:
            identity = str(getattr(self.project, "path", "project"))
        digest = hashlib.sha1(identity.encode("utf-8", errors="replace")).hexdigest()[:20]
        return f"projectView/{digest}/{suffix}"

    def _load_witness_display_order(self):
        """Read the visual-only, project-local order; append new witnesses."""
        from witness_layout import normalized_witness_order
        saved = _settings().value(self._view_settings_key("witnessOrder"), "")
        try:
            saved = json.loads(saved) if isinstance(saved, str) and saved else saved
        except (TypeError, ValueError):
            saved = []
        if not isinstance(saved, (list, tuple)):
            saved = []
        return normalized_witness_order([w.id for w in self.witness_configs], saved)

    def _save_witness_display_order(self):
        _settings().setValue(
            self._view_settings_key("witnessOrder"),
            json.dumps(self._witness_display_order, ensure_ascii=False),
        )

    def _apply_witness_panel_order(self):
        """Reparent existing panels; never reinstantiate images or synchronizations."""
        from witness_layout import normalized_witness_order
        from workspace_layout import workspace_slots
        self._witness_display_order = normalized_witness_order(
            [w.id for w in self.witness_configs], self._witness_display_order
        )
        mode = getattr(self, '_workspace_mode', 'vertical')
        detached = set(getattr(self, '_detached_windows', {}))
        docked = [wid for wid in self._witness_display_order if wid not in detached]
        self._reordering_witness_panels = True
        try:
            if mode == 'vertical':
                for index, wid in enumerate(docked):
                    panel = self.panels[wid]
                    if self.witness_splitter.indexOf(panel) != index:
                        self.witness_splitter.insertWidget(index, panel)
            elif mode == 'horizontal':
                for index, wid in enumerate(docked):
                    panel = self.panels[wid]
                    if self.witness_horizontal_splitter.indexOf(panel) != index:
                        self.witness_horizontal_splitter.insertWidget(index, panel)
            else:
                slots = workspace_slots(docked, columns=2)
                while len(self._grid_rows) < len(slots):
                    row = QSplitter(Qt.Orientation.Horizontal)
                    row.splitterMoved.connect(self._remember_workspace_sizes)
                    self._grid_rows.append(row)
                    self.witness_grid_splitter.addWidget(row)
                for row_index, ids in enumerate(slots):
                    row = self._grid_rows[row_index]
                    for index, wid in enumerate(ids):
                        panel = self.panels[wid]
                        if row.indexOf(panel) != index:
                            row.insertWidget(index, panel)
                for row_index, row in enumerate(self._grid_rows):
                    row.setVisible(row_index < len(slots))
        finally:
            self._reordering_witness_panels = False
        for wid in docked:
            panel = self.panels[wid]
            panel.set_compact_toolbar(mode != 'vertical')
            # Reparenting to a previously hidden splitter may leave a Qt
            # widget explicitly hidden; restore the user's checked visibility.
            panel.setVisible(wid in getattr(self, '_visible_witness_ids', docked))
        if hasattr(self, 'workspace_root'):
            self.witness_splitter.setVisible(mode == 'vertical')
            self.witness_horizontal_splitter.setVisible(mode == 'horizontal')
            self.witness_grid_splitter.setVisible(mode == 'grid')

    def _load_workspace_mode(self):
        from workspace_layout import normalize_workspace_mode
        return normalize_workspace_mode(_settings().value(
            self._view_settings_key('workspaceMode'), 'vertical'))

    def _set_workspace_mode(self, mode, *, persist=True):
        from workspace_layout import normalize_workspace_mode
        mode = normalize_workspace_mode(mode)
        if mode == self._workspace_mode:
            return
        self._remember_workspace_sizes()
        self._changing_workspace = True
        try:
            self._workspace_mode = mode
            self._witness_maximized_id = None
            self._witness_sizes_before_maximize = None
            self._apply_witness_panel_order()
            self._update_witness_scroll_extent()
            if hasattr(self, 'workspace_mode_actions'):
                for key, action in self.workspace_mode_actions.items():
                    action.setChecked(key == mode)
        finally:
            self._changing_workspace = False
        if persist:
            _settings().setValue(self._view_settings_key('workspaceMode'), mode)
        QTimer.singleShot(0, self._restore_workspace_sizes)

    def _remember_workspace_sizes(self, *_args):
        if getattr(self, '_changing_workspace', False) or getattr(self, '_reordering_witness_panels', False):
            return
        mode = getattr(self, '_workspace_mode', 'vertical')
        if mode == 'vertical':
            self._remember_witness_splitter_sizes()
            return
        saved = {}
        if mode == 'horizontal':
            for i in range(self.witness_horizontal_splitter.count()):
                panel = self.witness_horizontal_splitter.widget(i)
                sizes = self.witness_horizontal_splitter.sizes()
                if panel is not None and panel.isVisible() and i < len(sizes) and sizes[i] > 0:
                    saved[panel.siglum] = sizes[i]
        else:
            rows = self.witness_grid_splitter.sizes()
            saved['rows'] = rows
            for row in self._grid_rows:
                sizes = row.sizes()
                for i in range(row.count()):
                    panel = row.widget(i)
                    if panel is not None and panel.isVisible() and i < len(sizes) and sizes[i] > 0:
                        saved[panel.siglum] = sizes[i]
        if saved:
            key = 'horizontalSizes' if mode == 'horizontal' else 'gridSizes'
            old = _settings().value(self._view_settings_key(key), '')
            try:
                old = json.loads(str(old)) if old else {}
            except (ValueError, TypeError):
                old = {}
            if isinstance(old, dict):
                old.update(saved)
                saved = old
            _settings().setValue(self._view_settings_key(key), json.dumps(saved))

    def _restore_workspace_sizes(self):
        if self._workspace_mode == 'vertical':
            self._restore_witness_splitter_sizes()
            return
        key = 'horizontalSizes' if self._workspace_mode == 'horizontal' else 'gridSizes'
        raw = _settings().value(self._view_settings_key(key), '')
        try:
            saved = json.loads(str(raw)) if raw else {}
        except (TypeError, ValueError):
            saved = {}
        if not isinstance(saved, dict):
            saved = {}
        self._changing_workspace = True
        try:
            if self._workspace_mode == 'horizontal':
                splitter = self.witness_horizontal_splitter
                if splitter.count():
                    splitter.setSizes([int(saved.get(splitter.widget(i).siglum, 450))
                                       for i in range(splitter.count())])
            else:
                for row in self._grid_rows:
                    if row.count():
                        row.setSizes([int(saved.get(row.widget(i).siglum, 400))
                                      for i in range(row.count())])
                if isinstance(saved.get('rows'), list) and len(saved['rows']) == self.witness_grid_splitter.count():
                    self.witness_grid_splitter.setSizes([int(n) for n in saved['rows']])
        finally:
            self._changing_workspace = False

    def _remember_main_splitter_ratio(self, *_args):
        if getattr(self, '_restoring_main_splitter_ratio', False):
            return
        sizes = self.main_splitter.sizes()
        if len(sizes) >= 2 and min(sizes) > 0:
            _settings().setValue(self._view_settings_key('xmlColumnRatio'),
                                 round(sizes[0] / sum(sizes), 5))

    def _restore_main_splitter_ratio(self):
        raw = _settings().value(self._view_settings_key('xmlColumnRatio'), '')
        try:
            ratio = float(raw)
        except (TypeError, ValueError):
            ratio = 0.48
        ratio = max(0.15, min(.85, ratio))
        if self.witness_scroll.isHidden():
            return
        total = max(600, self.main_splitter.width())
        self._restoring_main_splitter_ratio = True
        try:
            self.main_splitter.setSizes([round(total * ratio), round(total * (1.0 - ratio))])
        finally:
            self._restoring_main_splitter_ratio = False

    def _toggle_detached_witness(self, witness_id):
        witness_id = str(witness_id)
        if witness_id in self._detached_windows:
            self._detached_windows[witness_id].close()
        else:
            self._detach_witness(witness_id)

    def _detach_witness(self, witness_id, *, persist=True):
        witness_id = str(witness_id)
        if (witness_id in self._detached_windows or witness_id not in self.panels
                or witness_id not in self._visible_witness_ids):
            return False
        self._remember_workspace_sizes()
        panel = self.panels[witness_id]
        # Reparenting the original widget maintains the live scene and zoom.
        panel.setParent(None)
        always = _settings().value(self._view_settings_key(
            f'floatingAlwaysOnTop/{witness_id}'), False)
        if isinstance(always, str):
            always = always.strip().lower() in ('true', '1', 'yes', 'on')
        win = DetachedWitnessWindow(self, witness_id, panel, bool(always))
        self._detached_windows[witness_id] = win
        geom = _settings().value(self._view_settings_key(f'floatingGeometry/{witness_id}'))
        if geom:
            try:
                win.restoreGeometry(geom)
            except (TypeError, ValueError):
                pass  # Corrupted/stale preferences must never prevent detaching.
        win.show()
        panel.show()  # QWidget.setParent(None) can leave it explicitly hidden.
        if persist:
            self._save_detached_witness_ids()
        self._apply_witness_panel_order()
        self._refresh_workspace_visibility()
        QTimer.singleShot(0, self._restore_workspace_sizes)
        self._refresh_detach_actions()
        return True

    def _dock_witness(self, witness_id, *, from_window=False):
        witness_id = str(witness_id)
        win = self._detached_windows.pop(witness_id, None)
        if win is None:
            return False
        panel = self.panels[witness_id]
        panel._detached = False
        panel.retranslate_ui()
        panel.setParent(None)
        self._apply_witness_panel_order()
        panel.setVisible(witness_id in self._visible_witness_ids)
        self._refresh_workspace_visibility()
        self._save_detached_witness_ids()
        self._refresh_detach_actions()
        if not from_window:
            win.close()
        win.deleteLater()
        QTimer.singleShot(0, self._restore_workspace_sizes)
        return True

    def _save_detached_witness_ids(self):
        ids = [wid for wid in self._witness_display_order if wid in self._detached_windows]
        _settings().setValue(self._view_settings_key('detachedWitnesses'), json.dumps(ids))

    def _restore_detached_witnesses(self):
        from workspace_layout import normalized_detached_witnesses
        raw = _settings().value(self._view_settings_key('detachedWitnesses'), '')
        try:
            raw = json.loads(str(raw)) if raw else []
        except (TypeError, ValueError):
            raw = []
        for wid in normalized_detached_witnesses(raw, self._visible_witness_ids):
            self._detach_witness(wid, persist=False)
        self._refresh_detach_actions()

    def _refresh_detach_actions(self):
        actions = getattr(self, '_detach_actions', {})
        for wid, action in actions.items():
            action.setChecked(wid in self._detached_windows)
            action.setEnabled(wid in self._visible_witness_ids)
        if hasattr(self, 'action_attach_all'):
            self.action_attach_all.setEnabled(bool(self._detached_windows))

    def _dock_all_witnesses(self):
        for wid in list(self._detached_windows):
            self._detached_windows[wid].close()

    def _refresh_workspace_visibility(self):
        docked = [wid for wid in self._visible_witness_ids
                  if wid not in self._detached_windows]
        self.witness_scroll.setVisible(bool(docked))
        self._update_witness_scroll_extent()
        if not docked:
            self.main_splitter.setSizes([1650, 0])
        elif self.main_splitter.sizes()[1] == 0:
            self._restore_main_splitter_ratio()

    def _available_image_witness_ids(self):
        return [w.id for w in self.witness_configs if self._witness_image_available.get(w.id, False)]

    def _load_visible_witness_ids(self):
        settings = _settings()
        key = self._view_settings_key("visibleWitnesses")
        available = set(self._available_image_witness_ids())
        if not settings.contains(key):
            # Première ouverture : montrer toutes les ressources d'image déjà
            # présentes. Un témoin ajouté plus tard n'est pas coché de force,
            # puisque la préférence existe alors déjà.
            return [w.id for w in self.witness_configs if w.id in available]
        raw = settings.value(key, [])
        if isinstance(raw, str):
            try:
                decoded = json.loads(raw)
                raw = decoded if isinstance(decoded, list) else [raw]
            except Exception:
                raw = [raw] if raw else []
        from witness_layout import ordered_visible_witnesses
        return ordered_visible_witnesses(self._witness_display_order, raw, available)

    def _save_visible_witness_ids(self):
        _settings().setValue(
            self._view_settings_key("visibleWitnesses"),
            json.dumps(list(self._visible_witness_ids), ensure_ascii=False),
        )

    def _load_witness_size_map(self):
        raw = _settings().value(self._view_settings_key("witnessHeights"), "")
        if not raw:
            return {}
        try:
            data = json.loads(str(raw))
        except Exception:
            return {}
        result = {}
        if isinstance(data, dict):
            for key, value in data.items():
                try:
                    result[str(key)] = max(0, int(value))
                except Exception:
                    pass
        return result

    def _remember_witness_splitter_sizes(self, *_args):
        if (self._witness_maximized_id is not None or self._reordering_witness_panels
                or getattr(self, '_workspace_mode', 'vertical') != 'vertical'):
            return
        sizes = self.witness_splitter.sizes()
        # Preserve heights belonging to witnesses currently hidden.
        data = self._load_witness_size_map()
        for i, wid in enumerate(self._witness_display_order):
            if i < len(sizes) and self.panels[wid].isVisible():
                data[wid] = max(1, int(sizes[i]))
        if data:
            _settings().setValue(
                self._view_settings_key("witnessHeights"),
                json.dumps(data, ensure_ascii=False),
            )

    def _update_witness_scroll_extent(self):
        """Reserve enough vertical space for all visible image panels.

        A scrollable QSplitter must have a content minimum greater than the
        viewport height; otherwise Qt simply shrinks the bottom panels.  This
        minimum is based on *visible* panels, and drops to one panel while a
        witness is maximized.  Pane heights remain draggable and persisted.
        """
        from witness_layout import minimum_witness_stack_height
        visible_count = sum(
            w.id not in getattr(self, '_detached_windows', {}) and not self.panels[w.id].isHidden()
            for w in self.witness_configs
        )
        mode = getattr(self, '_workspace_mode', 'vertical')
        rows = (visible_count + 1) // 2 if mode == 'grid' else (1 if mode == 'horizontal' and visible_count else visible_count)
        self.witness_splitter.setMinimumHeight(
            minimum_witness_stack_height(
                visible_count, maximized=self._witness_maximized_id is not None
            ) if mode == 'vertical' else 0
        )
        if hasattr(self, 'witness_horizontal_splitter'):
            self.witness_horizontal_splitter.setMinimumHeight(290 if mode == 'horizontal' and visible_count else 0)
            self.witness_grid_splitter.setMinimumHeight(
                minimum_witness_stack_height(rows, panel_height=290) if mode == 'grid' else 0)

    def _restore_witness_splitter_sizes(self):
        visible = set(self._visible_witness_ids)
        stored = self._load_witness_size_map()
        sizes = []
        for wid in self._witness_display_order:
            sizes.append(stored.get(wid, 320) if wid in visible else 0)
        if any(sizes) and getattr(self, '_workspace_mode', 'vertical') == 'vertical':
            self.witness_splitter.setSizes(sizes)

    def _apply_witness_visibility(self, initial=False):
        # Changing visible witnesses exits temporary maximized mode before
        # recomputing the scroll extent for the newly visible collection.
        if not initial:
            self._witness_maximized_id = None
            self._witness_sizes_before_maximize = None
            previous = getattr(self, '_workspace_before_maximize', None)
            if previous:
                self._workspace_before_maximize = None
                self._set_workspace_mode(previous, persist=False)
        from witness_layout import ordered_visible_witnesses
        self._apply_witness_panel_order()
        available = set(self._available_image_witness_ids())
        visible = ordered_visible_witnesses(
            self._witness_display_order, self._visible_witness_ids, available
        )
        self._visible_witness_ids = visible
        visible_set = set(visible)
        was_explicitly_visible = not self.witness_scroll.isHidden()
        if hasattr(self, "main_splitter") and was_explicitly_visible:
            current_main_sizes = self.main_splitter.sizes()
            if len(current_main_sizes) >= 2 and current_main_sizes[1] > 0:
                self._main_splitter_last_visible_sizes = current_main_sizes[:2]
        for w in self.witness_configs:
            self.panels[w.id].setVisible(w.id in visible_set)
            if w.id in getattr(self, '_detached_windows', {}) and w.id not in visible_set:
                self._detached_windows[w.id].close()
        docked = [wid for wid in visible if wid not in getattr(self, '_detached_windows', {})]
        has_visible = bool(docked)
        self.witness_scroll.setVisible(has_visible)
        self._update_witness_scroll_extent()
        if hasattr(self, "main_splitter"):
            if has_visible:
                if initial or not was_explicitly_visible:
                    self.main_splitter.setSizes(list(self._main_splitter_last_visible_sizes))
                QTimer.singleShot(0, self._restore_workspace_sizes)
            else:
                self.main_splitter.setSizes([1650, 0])
        if not initial:
            self._save_visible_witness_ids()
        self._refresh_detach_actions()

    def choose_visible_witnesses(self):
        dlg = WitnessVisibilityDialog(
            self.witness_configs,
            self._available_image_witness_ids(),
            self._visible_witness_ids,
            self._witness_display_order,
            self,
        )
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        self._witness_display_order = dlg.ordered_ids()
        self._visible_witness_ids = dlg.selected_ids()
        self._save_witness_display_order()
        self._apply_witness_visibility(initial=False)

    def _toggle_witness_panel_maximize(self, witness_id):
        witness_id = str(witness_id)
        detached = getattr(self, '_detached_windows', {})
        if witness_id in detached:
            window = detached[witness_id]
            window.showNormal() if window.isMaximized() else window.showMaximized()
            return
        if getattr(self, '_workspace_mode', 'vertical') != 'vertical':
            self._workspace_before_maximize = self._workspace_mode
            self._set_workspace_mode('vertical', persist=False)
        visible = [w.id for w in self.witness_configs if self.panels[w.id].isVisible()
                   and w.id not in detached]
        if witness_id not in visible:
            return
        if self._witness_maximized_id == witness_id:
            sizes = self._witness_sizes_before_maximize
            self._witness_maximized_id = None
            self._witness_sizes_before_maximize = None
            self._update_witness_scroll_extent()
            if sizes:
                self.witness_splitter.setSizes(sizes)
            else:
                self._restore_witness_splitter_sizes()
            self._remember_witness_splitter_sizes()
            previous = getattr(self, '_workspace_before_maximize', None)
            if previous:
                self._workspace_before_maximize = None
                self._set_workspace_mode(previous, persist=False)
            return
        if self._witness_maximized_id is None:
            self._witness_sizes_before_maximize = self.witness_splitter.sizes()
        self._witness_maximized_id = witness_id
        self._update_witness_scroll_extent()
        total = max(600, sum(max(0, x) for x in self.witness_splitter.sizes()))
        sizes = [total if wid == witness_id and self.panels[wid].isVisible() else 0
                 for wid in self._witness_display_order]
        self.witness_splitter.setSizes(sizes)
        # Bring a lower panel into view even when the scrollbar was elsewhere.
        self.witness_scroll.verticalScrollBar().setValue(0)

    def _build_toolbar(self):
        # V0.8.3 : menus à gauche, commandes XML regroupées, recherche à droite.
        self._build_file_menu()
        self._build_display_menu()
        self._build_help_menu()

        tb = QToolBar(_t("toolbar.title"), self)
        self.main_toolbar = tb
        tb.setMovable(False)
        self.addToolBar(tb)

        self.file_menu_button = QToolButton(self)
        self.file_menu_button.setText(_t("menu.file"))
        self.file_menu_button.setMenu(self.file_menu)
        self.file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.file_menu_button.setAutoRaise(True)
        tb.addWidget(self.file_menu_button)

        self.display_menu_button = QToolButton(self)
        self.display_menu_button.setText(_t("menu.display"))
        self.display_menu_button.setMenu(self.display_menu)
        self.display_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.display_menu_button.setAutoRaise(True)
        tb.addWidget(self.display_menu_button)

        self.help_menu_button = QToolButton(self)
        self.help_menu_button.setText(_t("menu.help"))
        self.help_menu_button.setMenu(self.help_menu)
        self.help_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.help_menu_button.setAutoRaise(True)
        tb.addWidget(self.help_menu_button)
        menu_gap = QWidget()
        menu_gap.setFixedWidth(14)
        tb.addWidget(menu_gap)

        self.action_generate_web = self._make_action(
            _t("toolbar.generate_web"), "", self.generate_web_viewer, _t("toolbar.generate_web.tip")
        )
        tb.addAction(self.action_generate_web)
        tool_gap = QWidget()
        tool_gap.setFixedWidth(12)
        tb.addWidget(tool_gap)

        # Bloc XML : conserver ces trois commandes côte à côte.
        self.action_validate_rng = self._make_action(
            _t("toolbar.validate_rng"), "F8", self.validate_relaxng_manual, _t("toolbar.validate_rng.tip")
        )
        self.action_format_xml = self._make_action(
            _t("toolbar.format_xml"), "", self.format_xml_source, _t("toolbar.format_xml.tip")
        )
        self.action_xpath_search = self._make_action(
            _t("xpath.action"), "Ctrl+Shift+F", self.focus_xpath_search
        )
        tb.addAction(self.action_validate_rng)
        tb.addAction(self.action_format_xml)
        tb.addAction(self.action_xpath_search)
        xml_gap = QWidget()
        xml_gap.setFixedWidth(12)
        tb.addWidget(xml_gap)

        # Ctrl+1 / Ctrl+2 restent disponibles comme raccourcis, mais les boutons
        # redondants ont été supprimés : les onglets sont l'interface principale.
        self.action_xml_source = self._make_action(_t("toolbar.xml_source"), "Ctrl+1", lambda: self.left_tabs.setCurrentIndex(0))
        self.action_preview = self._make_action(_t("toolbar.preview"), "Ctrl+2", lambda: self.left_tabs.setCurrentIndex(1))
        self.addAction(self.action_xml_source)
        self.addAction(self.action_preview)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Recherche source alignée à droite.
        self.search_source_label = QLabel(" " + _t("toolbar.search_source") + " ")
        tb.addWidget(self.search_source_label)
        self.find_box = QLineEdit()
        self.find_box.setClearButtonEnabled(True)
        self.find_box.setMaximumWidth(260)
        self.find_box.setPlaceholderText("Ctrl+F")
        self.find_box.returnPressed.connect(self.find_source_next)
        tb.addWidget(self.find_box)
        self.action_search = self._make_action(_t("toolbar.search"), "Ctrl+F", self.focus_find)
        self.action_find_prev = self._make_action(_t("toolbar.previous"), "Shift+F3", self.find_previous)
        self.action_find_next = self._make_action(_t("toolbar.next"), "F3", self.find_next)
        tb.addAction(self.action_search)
        tb.addAction(self.action_find_prev)
        tb.addAction(self.action_find_next)

    def _build_file_menu(self):
        # QMenu autonome : contrairement à menuBar().addMenu(), aucun bandeau
        # supplémentaire n'est créé au-dessus de la barre d'outils.
        menu = QMenu(_t("menu.file"), self)
        self.file_menu = menu

        self.action_new_project = self._make_action(_t("menu.new_project"), "Ctrl+N", self.new_project_dialog)
        self.action_open_project = self._make_action(_t("menu.open_project"), "Ctrl+O", self.open_project_dialog)
        self.recent_menu = menu.addMenu(_t("menu.recent_projects"))
        self.action_project_settings = self._make_action(_t("menu.project_settings"), "", self.project_settings_dialog)
        self.action_close_project = self._make_action(_t("menu.close_project"), "Ctrl+W", self.close_project)
        self.action_save = self._make_action(_t("menu.save_edition"), "Ctrl+S", self.save_contextual)
        self.action_save_as = self._make_action(_t("menu.save_edition_as"), "Ctrl+Shift+S", self.save_as)
        self.action_ctrl_e_config = self._make_action(
            _t("menu.ctrl_e_config"), "", self.open_ctrl_e_config, _t("toolbar.ctrl_e_config.tip", path=self.project.custom_elements)
        )
        self.action_generate_web_menu = self._make_action(
            _t("menu.generate_web"), "", self.generate_web_viewer, _t("toolbar.generate_web.tip")
        )
        self.action_quit = self._make_action(_t("menu.quit"), "Ctrl+Q", self.close)

        menu.insertAction(self.recent_menu.menuAction(), self.action_new_project)
        menu.insertAction(self.recent_menu.menuAction(), self.action_open_project)
        menu.addAction(self.action_project_settings)
        self.action_iiif_manager = self._make_action(_t('iiif.manager.menu'), '', self.open_iiif_download_manager)
        menu.addAction(self.action_iiif_manager)
        menu.addAction(self.action_close_project)
        menu.addSeparator()
        menu.addAction(self.action_save)
        menu.addAction(self.action_save_as)
        menu.addSeparator()
        menu.addAction(self.action_ctrl_e_config)
        menu.addSeparator()
        menu.addAction(self.action_generate_web_menu)
        menu.addSeparator()
        menu.addAction(self.action_quit)
        # Dans un QMenu attaché à un QToolButton, les raccourcis doivent aussi
        # être enregistrés auprès de la fenêtre pour rester actifs menu fermé.
        for action in (
            self.action_new_project, self.action_open_project, self.action_close_project,
            self.action_save, self.action_save_as, self.action_quit,
        ):
            self.addAction(action)
        self.update_recent_projects_menu()

    def _build_display_menu(self):
        menu = QMenu(_t("menu.display"), self)
        self.display_menu = menu

        self.action_reload_images = self._make_action(_t("toolbar.reload_images"), "F5", self.reload_images)
        self.action_reload_images.setEnabled(bool(getattr(self, "has_any_images", True)))
        self.action_choose_witnesses = self._make_action(
            _t("view.witnesses.choose"), "", self.choose_visible_witnesses, _t("view.witnesses.choose.tip")
        )
        self.action_choose_witnesses.setEnabled(bool(getattr(self, "has_any_images", True)))
        menu.addAction(self.action_reload_images)
        menu.addAction(self.action_choose_witnesses)
        self.workspace_layout_menu = menu.addMenu(_t('workspace.menu'))
        self.workspace_mode_group = QActionGroup(self)
        self.workspace_mode_group.setExclusive(True)
        self.workspace_mode_actions = {}
        for mode, key in (('vertical', 'workspace.vertical'),
                          ('horizontal', 'workspace.horizontal'),
                          ('grid', 'workspace.grid')):
            action = QAction(_t(key), self)
            action.setCheckable(True)
            action.setChecked(mode == self._workspace_mode)
            action.triggered.connect(lambda checked=False, m=mode:
                                     self._set_workspace_mode(m) if checked else None)
            self.workspace_mode_group.addAction(action)
            self.workspace_layout_menu.addAction(action)
            self.workspace_mode_actions[mode] = action
        self.workspace_layout_menu.addSeparator()
        self.detach_witness_menu = self.workspace_layout_menu.addMenu(_t('workspace.detach.menu'))
        self._detach_actions = {}
        for w in self.witness_configs:
            action = QAction(f'{w.id} — {w.label}' if w.label else str(w.id), self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, wid=w.id:
                                     self._toggle_detached_witness(wid))
            self.detach_witness_menu.addAction(action)
            self._detach_actions[w.id] = action
        self.action_attach_all = QAction(_t('workspace.attach_all'), self)
        self.action_attach_all.triggered.connect(self._dock_all_witnesses)
        self.workspace_layout_menu.addAction(self.action_attach_all)
        self._refresh_detach_actions()
        menu.addSeparator()
        self.xml_folding_menu = menu.addMenu(_t('fold.menu'))
        self.action_fold_current = self._make_action(
            _t('fold.current'), 'Ctrl+Alt+F', lambda checked=False: self.editor.toggle_xml_fold())
        self.action_fold_all = self._make_action(
            _t('fold.all'), '', lambda checked=False: self.editor.fold_all_xml())
        self.action_unfold_all = self._make_action(
            _t('fold.none'), 'Ctrl+Alt+Shift+F', lambda checked=False: self.editor.unfold_all_xml())
        for action in (self.action_fold_current, self.action_fold_all, self.action_unfold_all):
            self.xml_folding_menu.addAction(action)
            self.addAction(action)
        menu.addSeparator()
        self.action_diagnose_witnesses = self._make_action(
            _t('diagnostics.menu'), '', self.show_witness_diagnostics)
        self.action_refresh_synchronizations = self._make_action(
            _t('diagnostics.refresh'), 'Ctrl+Shift+R', self.refresh_witness_synchronizations)
        self.action_refresh_synchronizations.setToolTip(_t('diagnostics.refresh.tip'))
        menu.addAction(self.action_diagnose_witnesses)
        menu.addAction(self.action_refresh_synchronizations)
        self.addAction(self.action_refresh_synchronizations)
        menu.addSeparator()

        self.language_menu = menu.addMenu(_t("common.language"))
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)
        self.language_actions = {}
        for info in I18N.available_languages():
            action = QAction(info.label, self)
            action.setCheckable(True)
            action.setChecked(info.code == I18N.language)
            action.triggered.connect(lambda checked=False, code=info.code: self._set_language_code(code) if checked else None)
            self.language_action_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[info.code] = action

    def _build_help_menu(self):
        menu = QMenu(_t("menu.help"), self)
        self.help_menu = menu
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
        # Les ressources en ligne sont volontairement placées en premier.
        menu.addAction(self.action_enigma)
        menu.addAction(self.action_latin_dictionary)
        menu.addSeparator()
        menu.addAction(self.action_software_help)
        menu.addSeparator()
        menu.addAction(self.action_about)
        self.addAction(self.action_latin_dictionary)
        self.addAction(self.action_software_help)

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
                label = _t("menu.recent_item", title=title, path=path)
                action = QAction(label, self)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, p=path: self.open_recent_project(p))
                self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction(_t("menu.recent_clear"), self)
        clear_action.triggered.connect(self.clear_recent_projects_action)
        self.recent_menu.addAction(clear_action)

    def clear_recent_projects_action(self):
        clear_recent_projects()
        remember_recent_project(self.project.path)
        self.update_recent_projects_menu()

    def _set_language_code(self, code):
        code = str(code or "")
        if not code or code == I18N.language:
            return
        if not I18N.set_language(code):
            return
        _settings().setValue("startupLanguage", code)
        try:
            update_project_language(self.project.path, code)
        except Exception as exc:
            # Language still changes for the current session even if project.xml
            # is read-only. The status bar is deliberately non-blocking here.
            self.statusBar().showMessage(str(exc), 5000)
        self.retranslate_ui()

    def _language_changed(self, index):
        """Compatibilité avec d'anciens appels internes de la combo supprimée en V0.8.3."""
        if hasattr(self, "language_combo"):
            self._set_language_code(self.language_combo.itemData(index))

    def retranslate_ui(self):
        app = QApplication.instance()
        if app is not None:
            app.setApplicationName(_t("app.name"))
        self.main_toolbar.setWindowTitle(_t("toolbar.title"))
        self.file_menu.setTitle(_t("menu.file"))
        self.file_menu_button.setText(_t("menu.file"))
        self.display_menu.setTitle(_t("menu.display"))
        self.display_menu_button.setText(_t("menu.display"))
        self.help_menu.setTitle(_t("menu.help"))
        self.help_menu_button.setText(_t("menu.help"))
        self.action_enigma.setText(_t("help.enigma"))
        self.action_latin_dictionary.setText(_t("help.latin_dictionary"))
        self.action_software_help.setText(_t("help.software"))
        self.action_about.setText(_t("help.about"))
        self.action_new_project.setText(_t("menu.new_project"))
        self.action_open_project.setText(_t("menu.open_project"))
        self.recent_menu.setTitle(_t("menu.recent_projects"))
        self.action_project_settings.setText(_t("menu.project_settings"))
        self.action_iiif_manager.setText(_t('iiif.manager.menu'))
        self.action_close_project.setText(_t("menu.close_project"))
        self.action_save.setText(_t("menu.save_edition"))
        self.action_save_as.setText(_t("menu.save_edition_as"))
        self.action_ctrl_e_config.setText(_t("menu.ctrl_e_config"))
        self.action_ctrl_e_config.setToolTip(_t("toolbar.ctrl_e_config.tip", path=self.project.custom_elements))
        self.action_generate_web_menu.setText(_t("menu.generate_web"))
        self.action_quit.setText(_t("menu.quit"))
        self.action_generate_web.setText(_t("toolbar.generate_web"))
        self.action_generate_web.setToolTip(_t("toolbar.generate_web.tip"))
        self.action_xml_source.setText(_t("toolbar.xml_source"))
        self.action_preview.setText(_t("toolbar.preview"))
        self.action_reload_images.setText(_t("toolbar.reload_images"))
        self.action_choose_witnesses.setText(_t("view.witnesses.choose"))
        self.action_choose_witnesses.setToolTip(_t("view.witnesses.choose.tip"))
        self.workspace_layout_menu.setTitle(_t('workspace.menu'))
        self.detach_witness_menu.setTitle(_t('workspace.detach.menu'))
        for mode, key in (('vertical', 'workspace.vertical'), ('horizontal', 'workspace.horizontal'), ('grid', 'workspace.grid')):
            self.workspace_mode_actions[mode].setText(_t(key))
        self.action_attach_all.setText(_t('workspace.attach_all'))
        self.xml_folding_menu.setTitle(_t('fold.menu'))
        self.action_fold_current.setText(_t('fold.current'))
        self.action_fold_all.setText(_t('fold.all'))
        self.action_unfold_all.setText(_t('fold.none'))
        for win in self._detached_windows.values():
            win.retranslate_ui()
        self.action_diagnose_witnesses.setText(_t('diagnostics.menu'))
        self.action_refresh_synchronizations.setText(_t('diagnostics.refresh'))
        self.action_refresh_synchronizations.setToolTip(_t('diagnostics.refresh.tip'))
        self.language_menu.setTitle(_t("common.language"))
        language_labels = {info.code: info.label for info in I18N.available_languages()}
        for code, action in self.language_actions.items():
            action.setText(language_labels.get(code, code))
            action.setChecked(code == I18N.language)
        self.action_validate_rng.setText(_t("toolbar.validate_rng"))
        self.action_validate_rng.setToolTip(_t("toolbar.validate_rng.tip"))
        self.action_format_xml.setText(_t("toolbar.format_xml"))
        self.action_format_xml.setToolTip(_t("toolbar.format_xml.tip"))
        self.search_source_label.setText(" " + _t("toolbar.search_source") + " ")
        self.action_search.setText(_t("toolbar.search"))
        self.action_find_prev.setText(_t("toolbar.previous"))
        self.action_find_next.setText(_t("toolbar.next"))
        self.action_xpath_search.setText(_t("xpath.action"))
        self.source_visual_wrap.setText(_t("source.visual_wrap"))
        self.xpath_title.setText(_t("xpath.panel.title"))
        self.xpath_query.setPlaceholderText(_t("xpath.placeholder"))
        self.xpath_run_button.setText(_t("xpath.run"))
        self.xpath_close.setToolTip(_t("xpath.close"))
        self.xpath_table.setHorizontalHeaderLabels([
            _t("xpath.column.line"), _t("xpath.column.element"),
            _t("xpath.column.path"), _t("xpath.column.preview"),
        ])
        self.left_tabs.setTabText(0, _t("tab.xml_source"))
        self.left_tabs.setTabText(1, _t("tab.preview"))
        self.validation_title.setText(_t("rng.panel.title"))
        self.validation_refresh.setToolTip(_t("rng.panel.refresh"))
        self.validation_close.setToolTip(_t("rng.panel.close"))
        self.validation_table.setHorizontalHeaderLabels([
            _t("rng.column.level"), _t("rng.column.line"),
            _t("rng.column.column"), _t("rng.column.message"),
        ])
        self.source_wrap_element_action.setText(_t("fragment.wrap"))
        self.source_completion_action.setText(_t("completion.action"))
        self.formatted_view.retranslate_ui()
        for panel in self.panels.values():
            panel.retranslate_ui()
        self.update_recent_projects_menu()
        self._set_title()
        self._rebuild_lb_cache()
        self._cursor_changed()
        self.validate_text(False)
        self.validate_relaxng_document(show_panel=self.validation_panel.isVisible(), show_success_message=False)
        self._set_document_health(self._document_health)

    def generate_web_viewer(self):
        """Sauvegarde l'édition du projet puis lance le générateur web générique."""
        if self.current_path is None:
            return
        if self.current_path.resolve() != self.project.edition.resolve():
            QMessageBox.warning(
                self, _t("webgen.wrong_file.title"), _t("webgen.wrong_file.text")
            )
            return
        if self._has_unsaved_work() and not self.save_contextual():
            return
        try:
            from web_viewer.generator import generate
            # Presentation preferences belong to QSettings, NOT project.xml.
            # Export their *current* effective state, including detached panels.
            # The generator keeps the pivot as a technical source when hidden.
            visible = set(self._visible_witness_ids)
            display_ids = [wid for wid in self._witness_display_order if wid in visible]
            output, missing, data = generate(
                self.project.path, display_witness_ids=display_ids)
        except Exception as exc:
            QMessageBox.critical(self, _t("webgen.error.title"), str(exc))
            return
        msg = _t("webgen.done.text", output=output, witnesses=len(data.get("witnesses", [])), lines=data.get("meta", {}).get("lines", 0))
        if missing:
            msg += _t("webgen.missing", pages=", ".join(missing))
        box = QMessageBox(self)
        box.setWindowTitle(_t("webgen.done.title"))
        box.setText(msg)
        open_btn = box.addButton(_t("common.open"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_t("common.close"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

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

    def open_project_dialog(self):
        """Sélectionne un project.xml puis recharge l'application sur ce projet."""
        fn, _ = QFileDialog.getOpenFileName(
            self,
            _t("project.open.title"),
            str(self.project.path.parent),
            f"{_t('project.open.filter')} (*.xml);;{_t('common.all_files')} (*)",
        )
        if fn:
            self._replace_with_project(Path(fn))

    def open_recent_project(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            remove_recent_project(path)
            self.update_recent_projects_menu()
            QMessageBox.warning(self, _t("project.recent.missing.title"), _t("project.recent.missing", path=path))
            return
        self._replace_with_project(path)

    def new_project_dialog(self):
        """Crée un projet depuis une TEI existante ou une nouvelle transcription."""
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
                    values["language"], self.project.fallback_language,
                    xslt_mode=values["xslt_mode"],
                    schema_source=values.get("schema"),
                    schema_mode=values.get("schema_mode", "auto"),
                )
            else:
                project_path = creator(
                    values["target_dir"], values["title"], values["edition"],
                    values["witnesses"], values["base_witness"], HERE,
                    values["language"], self.project.fallback_language,
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
        if self._replace_with_project(project_path):
            new_window = self._replacement_window
            if any(w.image_source_type == 'iiif' and (
                w.iiif_local_copy or w.iiif_web_local_copy) for w in values['witnesses']):
                QTimer.singleShot(0, lambda: new_window.open_iiif_download_manager(auto_start=True))

    def open_iiif_download_manager(self, auto_start=False):
        """Open the non-modal IIIF manager; one job at a time per project."""
        from iiif_download_manager import IIIFDownloadManager
        manager = getattr(self, '_iiif_download_dialog', None)
        if manager is not None:
            manager.show()
            manager.raise_()
            manager.activateWindow()
            return
        manager = IIIFDownloadManager(_t, self.project, self, auto_start=auto_start)
        self._iiif_download_dialog = manager
        manager.show()

    def project_settings_dialog(self):
        """Modifie graphiquement project.xml puis recharge le projet."""
        if not self.maybe_save():
            return
        languages = [(info.code, info.label) for info in I18N.available_languages()]
        dlg = ProjectSettingsDialog(_t, self.project, languages, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            draft = dlg.draft()
            draft.witnesses = prepare_alignment_files_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_local_images_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_alto_files_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_iiif_manifests_for_project(self.project.root_dir, draft.witnesses)
            # Le gestionnaire est lancé après la sauvegarde, hors du thread UI.
            start_iiif = any(w.image_source_type == 'iiif' and (
                w.iiif_local_copy or w.iiif_web_local_copy) for w in draft.witnesses)

            # La couche page↔image conserve l'autorité TEI sans altérer les zones.
            facsimile_pages = project_facsimile_pages(draft.witnesses, self.project.root_dir, draft.edition)
            facsimile_report = sync_facsimile_file(
                draft.edition, facsimile_pages, previous_surface_labels(self.project.witnesses)
            ) if facsimile_pages else None
            # En passant du mode « XSLT application » au mode « personnalisée »,
            # initialiser une copie locale si elle n'existe pas, sans jamais
            # remplacer un fichier personnalisé déjà présent.
            create_local_xslt_if_needed(self.project.path.parent, draft)
            if self.project.path.exists():
                shutil.copy2(self.project.path, self.project.path.with_suffix(self.project.path.suffix + ".bak"))
            write_project_xml(self.project.path, draft)
            # Existing TEI surfaces belong to the edition. They are never
            # silently deleted when a new IIIF page selection excludes them.
            # Only strictly unchanged and unreferenced Varians-generated
            # surfaces may be offered for explicit removal, with a backup.
            for w in draft.witnesses:
                if (w.image_source_type != 'iiif' or
                    getattr(w, 'iiif_selection_mode', 'all') != 'selected'):
                    continue
                previous_witness = self.project.witness_by_id.get(w.id)
                if (previous_witness is not None and
                    getattr(previous_witness, 'iiif_selection_mode', 'all') == 'selected' and
                    tuple(getattr(previous_witness, 'iiif_selected_canvases', ())) ==
                    tuple(getattr(w, 'iiif_selected_canvases', ()))):
                    # Don't repeatedly prompt a scholar who has chosen to
                    # retain existing TEI surfaces on a previous save.
                    continue
                from iiif_manifest import cache_path, read_cache
                manifest = read_cache(cache_path(self.project.root_dir, w.id), w.image_source_value)
                if manifest is None:
                    continue
                xml_text = Path(draft.edition).read_text(encoding='utf-8-sig')
                try:
                    updated, candidates = removable_generated_iiif_surfaces(
                        xml_text, manifest, w.id, getattr(w, 'iiif_selected_canvases', ()))
                except ET.ParseError:
                    # Optional cleanup must not prevent valid project setting
                    # changes if an in-progress TEI cannot be parsed here.
                    continue
                if not candidates:
                    continue
                choice = QMessageBox.question(
                    self, _t('iiif.prune.title'),
                    _t('iiif.prune.question', witness=w.label, count=len(candidates),
                       ids=', '.join(candidates[:8]) + ('…' if len(candidates) > 8 else '')),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    continue
                path = Path(draft.edition)
                # Unique dated backup, never overwrite an existing backup.
                from datetime import datetime
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                backup = path.with_name(path.name + '.pre-iiif-cleanup-' + stamp + '.bak')
                shutil.copy2(path, backup)
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                                 prefix='.varians-iiif-', suffix='.tmp',
                                                 delete=False) as output:
                    output.write(updated)
                    temp_name = output.name
                try:
                    os.replace(temp_name, path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            if dlg.pivot_prepare.isChecked():
                run_pivot_scaffold_dialog(_t, self, draft.witnesses, draft.base_witness,
                                          self.project.root_dir, draft.edition,
                                          include_lb=dlg.pivot_lines.isChecked())
            remember_recent_project(self.project.path)
        except Exception as exc:
            QMessageBox.critical(self, _t("project.settings.error.title"), str(exc))
            return
        if facsimile_report is not None and facsimile_report.conflicts:
            QMessageBox.warning(
                self, _t("facsimile.warning.title"),
                _t("facsimile.warning.preserved") + "\n\n" + "\n".join(facsimile_report.conflicts),
            )
        QMessageBox.information(self, _t("project.settings.saved.title"), _t("project.settings.saved"))
        # maybe_save() a déjà été exécuté ; on recharge immédiatement les chemins,
        # témoins et ressources qui viennent d'être modifiés.
        try:
            new_window = MainWindow(self.project.path)
        except Exception as exc:
            QMessageBox.critical(self, _t("project.open_error"), str(exc))
            return
        self._replacement_window = new_window
        new_window.showMaximized()
        if start_iiif:
            QTimer.singleShot(0, lambda: new_window.open_iiif_download_manager(auto_start=True))
        self._force_close = True
        self.close()

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

    def _refresh_folio_navigation(self, text=None, force=False):
        if not hasattr(self, 'panels'):
            return
        if text is None:
            text = self.editor.toPlainText()
        revision = self.editor.document().revision()
        if not force and getattr(self, '_folio_revision', None) == revision:
            return
        for wid, panel in self.panels.items():
            ids = list(panel._surface_indices)
            labels = {str(it['p']['tei_surface_id']): image_page_label(it['p'], self.project.root_dir)
                      for it in panel.items if it.get('p', {}).get('tei_surface_id')}
            panel.set_folios(folios_for_witness(text, wid, ids, labels))
        self._folio_revision = revision

    def _sync_page_panels_to_cursor(self, force=False):
        """Synchronise chaque témoin avec son dernier ``pb/@edRef`` précédent.

        Depuis V0.8.3, une position de texte peut correspondre à des pages
        différentes selon le témoin. Les anciens ``pb`` sans ``@edRef`` restent
        reconnus lorsque leur ``@facs`` pointe sans ambiguïté vers une surface
        connue du panneau concerné.
        """
        if not self.has_any_images:
            return
        cursor = self.editor.textCursor()
        text = self.editor.toPlainText()
        pos = cursor.position()
        if hasattr(self, '_refresh_folio_navigation'):
            self._refresh_folio_navigation(text)
        refs = {}
        for witness_id, panel in self.panels.items():
            # V0.8.5.11 : le choix page/ligne est propre à chaque témoin.
            # Un témoin relié par base_keys doit continuer à suivre ses lignes,
            # même lorsque des pb de ce même témoin figurent dans la TEI.
            if panel.sync_enabled:
                continue
            if hasattr(panel, 'folios') and panel.folios:
                target = folio_at_position(text, pos, witness_id, panel.folios)
                if target:
                    refs[witness_id] = target.ref
            else:
                # Compatible with legacy/simple page-only panels, including
                # sessions without any folio zones or older unit-test stubs.
                surface = facsimile_ref_at_position(
                    text, pos, witness_id=witness_id,
                    surface_ids=panel._surface_indices.keys(),
                    surface_labels={
                        str(it['p']['tei_surface_id']): image_page_label(it['p'], self.project.root_dir)
                        for it in panel.items if it.get('p', {}).get('tei_surface_id')
                    },
                )
                if surface:
                    refs[witness_id] = surface
        signature = tuple(sorted(refs.items()))
        if not force and signature == self._last_synced_surface:
            return
        matched = False
        for witness_id, surface in refs.items():
            panel = self.panels.get(witness_id)
            if panel is not None and panel.set_surface(surface):
                matched = True
        if matched:
            self._last_synced_surface = signature

    def _replace_editor_text_minimally(self, old_text, new_text, target_position=None):
        """Applique un patch textuel minimal afin de conserver Undo et le contexte."""
        if old_text == new_text:
            return
        prefix = 0
        limit = min(len(old_text), len(new_text))
        while prefix < limit and old_text[prefix] == new_text[prefix]:
            prefix += 1
        suffix = 0
        max_suffix = min(len(old_text) - prefix, len(new_text) - prefix)
        while suffix < max_suffix and old_text[len(old_text)-1-suffix] == new_text[len(new_text)-1-suffix]:
            suffix += 1
        old_end = len(old_text) - suffix
        new_end = len(new_text) - suffix
        c = QTextCursor(self.editor.document())
        c.beginEditBlock()
        c.setPosition(prefix)
        c.setPosition(old_end, QTextCursor.MoveMode.KeepAnchor)
        c.insertText(new_text[prefix:new_end])
        c.endEditBlock()
        if target_position is not None:
            c.setPosition(max(0, min(self.editor.document().characterCount()-1, int(target_position))))
        self.editor.setTextCursor(c)
        self.editor.centerCursor()

    @Slot(str, str)
    def _split_double_folio(self, witness_id, surface_id):
        """Crée deux zones TEI sans dupliquer l'image ni réécrire la surface."""
        panel = self.panels.get(witness_id)
        if panel is None:
            return
        if not surface_id:
            QMessageBox.warning(self, _t('folio.split.title'), _t('folio.split.no_surface_ref'))
            return
        current = next((it for it in panel.items
                        if str(it.get('p', {}).get('tei_surface_id') or '') == surface_id), None)
        if current is None:
            QMessageBox.warning(self, _t('folio.split.title'), _t('folio.split.page_not_found'))
            return
        # Vérifier l'existence de la surface dans le XML de l'éditeur AVANT
        # d'ouvrir un dialogue que l'utilisateur remplirait pour rien.
        old = self.editor.toPlainText()
        try:
            tei_root = ET.fromstring(old)
        except ET.ParseError as exc:
            QMessageBox.warning(self, _t('folio.split.title'),
                                _t('folio.split.xml_invalid') + '\n' + str(exc))
            return
        surface_matches = [el for el in tei_root.iter()
                           if el.tag.rsplit('}', 1)[-1].rsplit(':', 1)[-1] == 'surface'
                           and el.get('{http://www.w3.org/XML/1998/namespace}id') == surface_id]
        if len(surface_matches) != 1:
            QMessageBox.warning(self, _t('folio.split.title'),
                                _t('folio.split.missing_surface', surface=surface_id))
            return
        iw, ih = page_image_dimensions(current['p'], self.project.root_dir)
        if not iw or not ih or iw <= 1 or ih <= 1:
            QMessageBox.warning(self, _t('folio.split.title'), _t('folio.split.no_dimensions'))
            return
        try:
            existing = inspect_surface_part_split(old, surface_id, int(iw), int(ih))
        except ValueError as exc:
            QMessageBox.warning(self, _t('folio.split.title'),
                                _t('folio.split.existing_zones') + '\n' + str(exc))
            return
        dialog = QDialog(self)
        dialog.setWindowTitle(_t('folio.split.title'))
        layout = QVBoxLayout(dialog)
        explanation = QLabel(_t('folio.split.explanation'))
        explanation.setWordWrap(True)
        layout.addWidget(explanation)
        dialog.setMinimumWidth(570)
        # Use a dedicated full-image thumbnail, never the cropped image of the
        # currently synchronized physical line. Remote IIIF previews load via
        # a background worker; local images use scaled QImageReader decoding.
        preview = SplitImagePreview(int(iw), int(ih), dialog)
        if existing:
            preview.set_split_px(existing['split_pixel'])
        layout.addWidget(preview)
        load_split_thumbnail(preview, current['p'], self.project.root_dir)
        fields = QFormLayout()
        left, right = QLineEdit(), QLineEdit()
        if existing:
            left.setText(existing['left']); right.setText(existing['right'])
        ratio = QDoubleSpinBox()
        ratio.setDecimals(2); ratio.setRange(1.0, 99.0)
        ratio.setValue(100.0 * preview.split_px / int(iw)); ratio.setSuffix(' %')
        ratio.valueChanged.connect(lambda v: preview.set_split_px(round(int(iw) * v / 100)))
        def on_preview_moved(px):
            ratio.blockSignals(True)
            ratio.setValue(100.0 * px / int(iw))
            ratio.blockSignals(False)
        preview.splitChanged.connect(on_preview_moved)
        fields.addRow(_t('folio.split.left'), left)
        fields.addRow(_t('folio.split.right'), right)
        fields.addRow(_t('folio.split.position'), ratio)
        layout.addLayout(fields)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(dialog.accept); buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        # Le texte ne doit pas être réécrit avant acceptation. En mode
        # synchronisé, ne pas changer le centre du panneau : seules les zones
        # de folio TEI sont créées, les base_keys restent prépondérants.
        old = self.editor.toPlainText()
        try:
            updated, (lref, rref) = configure_surface_parts(
                old, surface_id, left.text(), right.text(), int(iw), int(ih),
                split_pixel=preview.split_px)
        except ValueError as exc:
            QMessageBox.warning(self, _t('folio.split.title'), str(exc))
            return
        self._replace_editor_text_minimally(old, updated)
        self._refresh_folio_navigation(updated, force=True)
        if not panel.sync_enabled and existing is None:
            panel.set_folio(lref)
        # Revising an existing division leaves the user's selected logical
        # part untouched. Line-sync always retains its current physical line.
        self._last_synced_surface = None
        message_key = ('folio.split.created_synced' if panel.sync_enabled
                       else 'folio.split.created')
        QMessageBox.information(self, _t('folio.split.title'), _t(message_key))

    @Slot(str, str, str)
    def _mark_page_in_tei(self, witness_id, surface_id, label):
        """Crée/complète le facsimile puis insère un <pb n facs> en position sûre."""
        old = self.editor.toPlainText()
        original_pos = self.editor.textCursor().position()
        # Règle conservatrice : « Marquer la page » n'édite jamais une balise
        # existante. S'il est dans du markup XML, le curseur est probablement là
        # par erreur ; surtout, ne pas créer non plus <facsimile> avant de sortir.
        if position_inside_xml_markup(old, original_pos):
            self.statusBar().showMessage(_t("manuscript.mark_page.inside_tag"), 3200)
            return
        # When marking one region of a spread, validate the target BEFORE
        # changing the source, even if an older in-memory list is stale.
        panel = self.panels.get(witness_id)
        if panel is not None and surface_id not in getattr(panel, '_surface_indices', {}):
            ids = list(getattr(panel, '_surface_indices', {}).keys())
            actual = folios_for_witness(old, witness_id, ids)
            target = next((f for f in actual if f.ref == surface_id and f.region is not None), None)
            if target is None:
                QMessageBox.warning(self, _t('folio.mark.choose_title'), _t('folio.mark.stale_target'))
                return
            if target.label != label:
                QMessageBox.warning(self, _t('folio.mark.choose_title'), _t('folio.mark.stale_target'))
                return
        # Avant de créer un pointeur, garantir que sa cible existe. La fusion est
        # incrémentale : aucune surface ou zone existante n'est supprimée.
        pages = project_facsimile_pages(self.witness_configs, self.project.root_dir, self.project.edition)
        with_facsimile, report = sync_facsimile_text(old, pages, previous_surface_labels(self.witness_configs))
        fatal_conflicts = [
            c for c in report.conflicts
            if c.startswith("XML non bien formé") or c.startswith(f"{surface_id}:")
            or c.startswith("Aucun élément <text>")
        ]
        if fatal_conflicts:
            QMessageBox.warning(self, _t("facsimile.warning.title"), "\n".join(fatal_conflicts))
            return
        # Le curseur d'origine doit être translaté si <facsimile> vient d'être
        # inséré avant <text>. Rechercher la portion commune permet de conserver
        # approximativement le même point dans la transcription.
        if with_facsimile != old:
            text_marker = old[:original_pos]
            if text_marker:
                # La fin du préfixe original se retrouve normalement telle quelle.
                probe = text_marker[-min(160, len(text_marker)):]
                found = with_facsimile.find(probe)
                if found >= 0:
                    original_pos = found + len(probe)
                else:
                    original_pos += max(0, len(with_facsimile) - len(old))
        updated, new_pos, mode = upsert_pb_at_position(
            with_facsimile, original_pos, label, surface_id, witness_id=witness_id
        )
        if mode == "blocked":
            # Double garde-fou : ne devrait pas arriver après le test ci-dessus,
            # sauf si une future transformation déplace le curseur dans du markup.
            self.statusBar().showMessage(_t("manuscript.mark_page.inside_tag"), 3200)
            return
        self._replace_editor_text_minimally(old, updated, new_pos)
        self._last_synced_surface = None
        self._sync_page_panels_to_cursor(True)
        self.statusBar().showMessage(
            _t("manuscript.mark_page.inserted", page=label),
            2200,
        )

    def sync_panels_to_cursor(self, force=False):
        # En mode mixte, mettre à jour les folios indépendants sur la foi des
        # pb/edRef/facs, même si le pivot possède une synchronisation de lignes.
        self._sync_page_panels_to_cursor(force)
        if not self.base_alignment_available:
            return
        ordinal=self.ordinal_at_cursor()
        if ordinal is None or not self.base_items: return
        ordinal=max(0,min(len(self.base_items)-1,ordinal))
        if not force and ordinal == self._last_synced_ordinal:
            return
        self._last_synced_ordinal = ordinal
        key=self.base_items[ordinal]["key"]
        for panel in self.panels.values():
            if panel.sync_enabled:
                panel.set_primary(ordinal, key)
        self.statusBar().showMessage(_t("status.base_line", base=self.base_id, line=ordinal+1, total=len(self.base_items)),1500)

    def navigate_to_base_ordinal(self, ordinal, move_xml_cursor=True):
        """Synchronise tous les témoins sur un segment cliqué dans la vue mise en forme."""
        if not self.base_alignment_available or not self.base_items:
            return
        ordinal = max(0, min(len(self.base_items)-1, int(ordinal)))
        spans = self.lb_spans()
        if move_xml_cursor and spans:
            i = max(0, min(len(spans)-1, ordinal))
            self._sync_from_panel = True
            try:
                c = self.editor.textCursor()
                c.setPosition(spans[i][1])
                self.editor.setTextCursor(c)
                self.editor.centerCursor()
            finally:
                QTimer.singleShot(90, self._release_panel_sync)
        self._last_synced_ordinal = ordinal
        key = self.base_items[ordinal]["key"]
        for panel in self.panels.values():
            if panel.sync_enabled:
                panel.set_primary(ordinal, key)
        # Le déplacement dans la vue mise en forme peut inhiber temporairement
        # le timer du curseur : actualiser également les témoins en mode page.
        self._sync_page_panels_to_cursor(force=True)
        self.statusBar().showMessage(_t("status.base_line", base=self.base_id, line=ordinal+1, total=len(self.base_items)), 1500)

    def refresh_local_iiif_cache(self):
        """Make newly downloaded full-canvas copies usable without reopening TEI.

        The editor's TEI, cursor, undo stack and synchronization remain intact.
        Rebuild only the image-bearing navigation objects for affected witnesses.
        """
        for w in self.witness_configs:
            if w.image_source_type != 'iiif' or not w.iiif_local_copy:
                continue
            current = self.alignment_caches.get(w.id)
            if current is None:
                continue
            updated = apply_working_copy(current, self.project.root_dir, w.id)
            self.alignment_caches[w.id] = updated
            if w.is_base:
                lines, by_key = flatten_primary(updated)
                self.witness_items[w.id], self.base_by_key = lines, by_key
                self.base_items = lines
            else:
                lines, by_base = flatten_secondary(updated)
                self.witness_items[w.id], self.base_maps[w.id] = lines, by_base
            line_sync = self.base_alignment_available and (
                w.is_base or self._secondary_sync_link_counts.get(w.id, 0) > 0)
            if line_sync:
                display = self.witness_items[w.id]
            else:
                display = page_navigation_items(updated, self.project.root_dir)
                if not display:
                    display = self.witness_items[w.id] or image_only_items(updated, self.project.root_dir)
            self.witness_display_items[w.id] = display
            self._folio_revision = None
            panel = self.panels.get(w.id)
            if panel is not None:
                panel.items = display
                panel.map_base = self.base_maps.get(w.id) or {}
                panel.center_index = min(panel.center_index, max(0, len(display) - 1))
                panel._surface_indices = {
                    str(it['p'].get('tei_surface_id')): i
                    for i, it in enumerate(display) if it['p'].get('tei_surface_id')
                }
                if display:
                    panel.reload()

    def _witness_resource_snapshot(self):
        """Describe the resources *currently displayed*, without reparsing files."""
        return RuntimeState(
            self._raw_alignment_caches, self.alignment_caches,
            self.witness_items, self.witness_display_items, self.base_by_key,
            self.base_maps, self.base_items, self._base_sync_line_count,
            self.base_alignment_available, self._secondary_sync_link_counts,
            self._witness_image_available,
        )

    def show_witness_diagnostics(self):
        rows = diagnostic_rows(self.project, self._witness_resource_snapshot())
        WitnessDiagnosticDialog(rows, self).exec()

    def refresh_witness_synchronizations(self):
        """Reload the alignments and OCR without replacing the editor widget.

        The entire new state is staged before commit: a broken/partial JSON
        cannot destroy the current display. A confirmation shows changes to
        scientific line keys (even if the line counts happen to be equal).
        No modifications to TEI, project.xml, image sources or external files.
        """
        old_rows = diagnostic_rows(self.project, self._witness_resource_snapshot())
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            staged = assemble_resources(self.project)
            new_rows = diagnostic_rows(self.project, staged)
        except Exception as exc:
            refresh_error = str(exc)
        else:
            refresh_error = None
        finally:
            QApplication.restoreOverrideCursor()
        if refresh_error is not None:
            QMessageBox.warning(self, _t('diagnostics.refresh.error.title'),
                                _t('diagnostics.refresh.error', error=refresh_error))
            return False
        changed = changed_witnesses(old_rows, new_rows)
        if changed:
            before = {r.id: r for r in old_rows}
            after = {r.id: r for r in new_rows}
            lines = []
            for wid in changed:
                a, b = before.get(wid), after[wid]
                if a:
                    annotation = (_t('diagnostics.refresh.mapping_changed')
                                  if a.fingerprint != b.fingerprint else '')
                    lines.append(f'{wid}: {a.geometry_lines} → {b.geometry_lines} '
                                 f'{_t("diagnostics.column.geometry")}; '
                                 f'{a.usable_links} → {b.usable_links} '
                                 f'{_t("diagnostics.column.links")} {annotation}')
                else:
                    lines.append(wid)
            result = QMessageBox.question(
                self, _t('diagnostics.refresh.title'),
                _t('diagnostics.refresh.confirm', changes='\n'.join(lines)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if result != QMessageBox.StandardButton.Yes:
                return False
        # Commit; from this point on, all expensive and error-prone disk reads
        # have completed. Preserve each existing panel, zoom and frame toggle.
        self._raw_alignment_caches = staged.raw
        self.alignment_caches = staged.caches
        self.witness_items = staged.witness_items
        self.witness_display_items = staged.display_items
        self.base_by_key = staged.base_by_key
        self.base_maps = staged.base_maps
        self.base_items = staged.base_items
        self._base_sync_line_count = staged.base_sync_count
        self.base_alignment_available = staged.base_active
        self._secondary_sync_link_counts = staged.secondary_links
        self._witness_image_available = staged.images_available
        self.has_any_images = any(staged.images_available.values())
        self.expected_base_lines = staged.base_sync_count if staged.base_active else None
        self.action_reload_images.setEnabled(self.has_any_images)
        self.action_choose_witnesses.setEnabled(self.has_any_images)
        valid_pivot_keys = set(staged.base_by_key)
        for w in self.witness_configs:
            panel = self.panels[w.id]
            old = panel.current_item()
            old_page_id = str((old or {}).get('p', {}).get('id', ''))
            old_line_id = str((old or {}).get('l', {}).get('alto_id') or (old or {}).get('l', {}).get('line'))
            new_items = staged.display_items[w.id]
            panel.items = new_items
            panel.map_base = staged.base_maps.get(w.id) or {}
            panel.sync_enabled = bool(staged.base_active and (
                w.is_base or staged.secondary_links.get(w.id, 0) > 0))
            # The same witness may switch from page-only to synchronized after
            # a Varians-Synchro JSON refresh; folio controls follow its mode.
            if hasattr(panel, 'folio_combo'):
                panel.folio_combo.setEnabled(not panel.sync_enabled)
            if hasattr(panel, 'split_folio_btn'):
                panel.split_folio_btn.setEnabled(bool(panel.items))
            panel._surface_indices = {
                str(it['p'].get('tei_surface_id')): i
                for i, it in enumerate(new_items) if it['p'].get('tei_surface_id')
            }
            chosen = next((i for i, it in enumerate(new_items)
                           if str(it['p'].get('id', '')) == old_page_id
                           and str(it['l'].get('alto_id') or it['l'].get('line')) == old_line_id), None)
            if chosen is None:
                chosen = next((i for i, it in enumerate(new_items)
                               if str(it['p'].get('id', '')) == old_page_id), None)
            panel.center_index = (chosen if chosen is not None else
                                  min(panel.center_index, max(0, len(new_items) - 1)))
            panel.origin_center_index = panel.center_index
            panel.match_indices = set()
            panel.primary_key = None
            panel.sync_issue.hide()
            panel.sync_issue.setText('')
            if not w.is_base and w.alignment and staged.base_active:
                keys = panel.map_base
                if not staged.secondary_links.get(w.id, 0):
                    reason = _t('manuscript.sync.no_base_keys')
                elif not set(keys).intersection(valid_pivot_keys):
                    reason = _t('manuscript.sync.unmatched_base_keys')
                else:
                    reason = ''
                if reason:
                    panel.sync_issue.setText(reason)
                    panel.sync_issue.setToolTip(reason)
                    panel.sync_issue.show()
            unmatched = int((staged.caches[w.id].get('meta') or {}).get('iiif_unassociated_layout_count') or 0)
            tip = (_t('manuscript.iiif_unassociated_layout.tip', count=unmatched)
                   if unmatched else '')
            panel.header.setToolTip(tip)
            panel.status.setToolTip(tip)
            panel.reload()
        self._last_synced_ordinal = None
        self._last_synced_surface = None
        self._folio_revision = None
        self._set_lb_spans(self.lb_spans())
        # Do not undo an active single-panel maximization. The ordinary
        # visibility routine schedules size restoration on the next Qt tick.
        maximized = getattr(self, '_witness_maximized_id', None)
        if maximized and staged.images_available.get(maximized, False):
            self._update_witness_scroll_extent()
        else:
            self._apply_witness_visibility(initial=True)
        self.sync_panels_to_cursor(True)
        self.statusBar().showMessage(_t('diagnostics.refresh.done', count=len(changed)), 6500)
        return True

    def reload_images(self):
        self.refresh_local_iiif_cache()
        self.sync_panels_to_cursor(True)

    @Slot(int)
    def _primary_panel_navigate(self, ordinal):
        spans=self.lb_spans()
        if not spans: return
        ordinal=max(0,min(len(spans)-1,int(ordinal)))
        self._sync_from_panel=True
        try:
            c=self.editor.textCursor(); c.setPosition(spans[ordinal][1]); self.editor.setTextCursor(c); self.editor.centerCursor()
            self._last_synced_ordinal = ordinal
            key=self.base_items[ordinal]["key"]
            # Le témoin de base vient déjà de naviguer ; on actualise tous les panneaux.
            self.base_panel.match_indices={ordinal}; self.base_panel.origin_center_index=ordinal; self.base_panel.reload()
            for wid, panel in self.panels.items():
                if wid != self.base_id and panel.sync_enabled:
                    panel.set_primary(ordinal, key)
            self._sync_page_panels_to_cursor(force=True)
        finally:
            QTimer.singleShot(90,self._release_panel_sync)

    def _release_panel_sync(self): self._sync_from_panel=False

    def goto_xml_from_base(self):
        spans=self.lb_spans()
        if not spans: return
        i=max(0,min(len(spans)-1,self.base_panel.center_index)); c=self.editor.textCursor(); c.setPosition(spans[i][1]); self.editor.setTextCursor(c); self.editor.centerCursor(); self.editor.setFocus()

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
            self.formatted_view.preview.active_line_ordinal = None
            self.formatted_view.preview_find_bar.setVisible(False)
            self.formatted_view.preview_find_status.setText("")
            self.formatted_view.apply_btn.setEnabled(False)
            self.formatted_view.reload_btn.setEnabled(False)
            self.formatted_view.frag_box.setVisible(False)
            self.formatted_view.dirty_preview = True
            self.formatted_view._last_preview_key = None
        QTimer.singleShot(50,lambda: self.sync_panels_to_cursor(True))
        # Même en mode RNG « aucun », on résout les xml-model pour détecter
        # à titre informatif une éventuelle déclaration Schematron.
        QTimer.singleShot(120, lambda: self.validate_relaxng_document(show_panel=False, show_success_message=False))

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
                if resolution.schema_path is not None:
                    try:
                        current_token = relaxng_schema_token(resolution.schema_path)
                    except Exception:
                        current_token = None
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
                if not self._confirm_save_warning(
                    _t("file.save_rng_invalid.title"),
                    _t("file.save_rng_invalid.text", count=len(rng_result.issues)),
                ):
                    return False

        if self.expected_base_lines is not None and len(self.lb_spans()) != self.expected_base_lines:
            r=QMessageBox.warning(self,_t("file.structure.title", base=self.base_id),_t("file.structure.text", count=len(self.lb_spans()), base=self.base_id, expected=self.expected_base_lines),QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Cancel)
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
        return True

    def save_contextual(self):
        """Ctrl+S / Enregistrer : applique d’abord le fragment actif, puis écrit le fichier."""
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
        return self.save()

    def save(self):
        if self.current_path is None: return self.save_as()
        return self._write_to(self.current_path)

    def save_as(self):
        start=str(self.current_path if self.current_path else HERE/"xml"/"edition.xml"); fn,_=QFileDialog.getSaveFileName(self,_t("file.save_as.title"),start,"XML (*.xml)")
        if not fn: return False
        return self._write_to(Path(fn))

    def maybe_save(self):
        fragment_dirty = (
            hasattr(self, "formatted_view")
            and self.formatted_view.frag_box.isVisible()
            and self.formatted_view.fragment_has_unapplied_changes()
        )
        if not self.modified and not fragment_dirty: return True
        r=QMessageBox.question(self,_t("file.unsaved.title"),_t("file.unsaved.continue"),QMessageBox.StandardButton.Save|QMessageBox.StandardButton.Discard|QMessageBox.StandardButton.Cancel,QMessageBox.StandardButton.Save)
        if r==QMessageBox.StandardButton.Cancel: return False
        if r==QMessageBox.StandardButton.Save:
            if fragment_dirty and not self.formatted_view.apply_fragment():
                return False
            return bool(self.save())
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
        if not self._has_unsaved_work():
            return True

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
            return bool(self.save())
        return False

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
