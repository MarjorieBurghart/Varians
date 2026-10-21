# -*- coding: utf-8 -*-
"""Varians — éditeur TEI/manuscrits générique — V0.9.0.0.

Refactorisation de la base V8o : le projet, le témoin pivot, les témoins
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

import json
import re
import shutil
import sys
import xml.etree.ElementTree as ET
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
_LOCAL_MODULE_NAMES = {"project_config", "project_management", "project_dialogs", "i18n", "relaxng_validation", "schema_resolution", "rng_completion", "xpath_search", "save_io", "custom_completion", "image_sources", "iiif_manifest", "iiif_local", "iiif_selection", "iiif_download_manager", "iiif_page_selection", "alto_import", "tei_facsimile", "xml_tag_pairs", "tei_formatter", "selection_sync", "witness_resource_refresh", "resource_state", "witness_layout", "iiif_resolution", "folio_navigation", "xml_folding", "document_session", "app_context", "formatted_view", "image_fetch", "manuscript_panel", "code_editor", "witness_sync", "project_actions", "main_menus", "help_dialogs", "witness_workspace", "document_io", "completion_ui", "validation_panel", "xpath_panel", "document_tabs", "document_display", "document_dialogs", "xml_references", "references_ui", "apparatus_xpath", "apparatus_ui", "relaxng_worker", "validation_worker", "busy_indicator", "xml_assembly"}
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

# Processus de validation RELAX NG (voir validation_worker) : Varians relancé
# avec cette option ne charge que lxml, ni PySide6 ni fenêtre. Placé avant
# tout import de l'interface, et valable aussi dans une version autonome.
if __name__ == "__main__" and sys.argv[1:2] == ["--relaxng-worker"]:
    from relaxng_worker import serve
    raise SystemExit(serve())

from project_config import load_project, has_line_synchronization
from resource_state import primary_sync_line_count, secondary_sync_link_count
from project_management import create_portable_project, create_new_transcription_project
from project_dialogs import NewProjectDialog, run_pivot_scaffold_dialog
from i18n import I18nManager
from app_context import (
    call_later, error_message, set_i18n, tr, _settings, recent_project_paths, remember_recent_project,
    remove_recent_project, clear_recent_projects, last_open_project_path, remember_open_project,
    forget_open_project,
)
from document_session import DocumentSession, LB_EDIT_LOOKBACK, LbIndex
from formatted_view import (
    _selection_xml_to_visible_text, _xml_selection_pattern, FormattedEditionWidget, paragraph_spans,
)
from manuscript_panel import ManuscriptPanel
from code_editor import CodeEditor, find_in_plain_editor, XMLHighlighter
from witness_sync import WitnessSyncMixin, flatten_primary, flatten_secondary
from project_actions import ProjectActionsMixin
from main_menus import MainMenusMixin
from help_dialogs import (
    _build_varians_card, _open_external, _open_latin_dictionary, _show_about, _show_software_help,
)
from witness_workspace import WitnessWorkspaceMixin
from document_io import DocumentIOMixin
from completion_ui import CompletionMixin
from validation_panel import ValidationPanelMixin
from xpath_panel import XPathPanelMixin
from document_tabs import DocumentTabsMixin
from document_display import DocumentDisplayMixin
from document_dialogs import DocumentDialogsMixin
from references_ui import ReferencesMixin
from apparatus_ui import ApparatusDebugMixin
from busy_indicator import BusyIndicator
from validation_worker import worker_client
from rng_completion import XmlContextCache
from image_sources import (
    page_image_source, apply_witness_image_policy, image_only_items, page_navigation_items,
)
from alto_import import apply_witness_alto_policy
from iiif_local import apply_working_copy
from tei_facsimile import position_inside_xml_markup
from tei_formatter import format_tei_xml
from selection_sync import containing_span_index, occurrence_index_for_position, choose_occurrence

try:
    from PySide6.QtCore import Qt, QTimer, QObject, Signal, Slot, QRunnable, QThreadPool, QEvent
    from PySide6.QtGui import QTextCursor, QAction, QKeySequence, QTextDocument
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QSplitter, QToolBar, QFileDialog, QMessageBox,
        QLabel, QSizePolicy, QVBoxLayout, QHBoxLayout, QCheckBox, QScrollArea, QFrame,
        QTabWidget, QDialog, QDialogButtonBox, QMenu, QToolButton,
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


class MainWindow(WitnessSyncMixin, ProjectActionsMixin, MainMenusMixin, WitnessWorkspaceMixin, DocumentIOMixin, CompletionMixin, ValidationPanelMixin, XPathPanelMixin, DocumentTabsMixin, DocumentDisplayMixin, DocumentDialogsMixin, ReferencesMixin, ApparatusDebugMixin, QMainWindow):
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
    highlighter = _document_attribute("highlighter")
    # Schéma du document affiché (celui du projet pour l'édition).
    _schema_mode = _document_attribute("schema_mode")
    _schema_file = _document_attribute("schema_file")

    def __init__(self, project_path=None):
        super().__init__()
        # Document ouvert : doit exister avant toute affectation des attributs
        # de compatibilité ci-dessus.
        self.document = DocumentSession()
        self.project = load_project(project_path or DEMO_PROJECT)
        self.document.schema_mode = self.project.schema_mode
        self.document.schema_file = self.project.schema
        self._init_documents()
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
        self._xml_health_session = None
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
        self.editor.value_completion_provider = self._auto_value_choices
        self.formatted_view.fragment_editor.value_completion_provider = self._auto_value_choices
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
        self._install_reference_actions()

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
            # Ces commandes écrivent dans l'édition : refusées si un autre
            # document est affiché.
            panel.markPageRequested.connect(self._edition_write(self._mark_page_in_tei))
            panel.splitFolioRequested.connect(self._edition_write(self._split_double_folio))
            panel.maximizeRequested.connect(self._toggle_witness_panel_maximize)
            panel.detachRequested.connect(self._toggle_detached_witness)
            if w.is_base:
                # Connect once, even if synchronization becomes active later.
                panel.primaryNavigate.connect(self._edition_navigation(self._primary_panel_navigate))
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
        self.references_panel = self._build_references_panel()
        self._bottom_panels = [self.validation_panel, self.xpath_panel, self.references_panel]
        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.left_splitter.addWidget(self._build_document_area(self.left_tabs))
        self.left_splitter.setStretchFactor(0, 1)
        for index, panel in enumerate(self._bottom_panels, 1):
            self.left_splitter.addWidget(panel)
            self.left_splitter.setStretchFactor(index, 0)
        self.left_splitter.setSizes([760] + [0] * len(self._bottom_panels))
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
        self.rng_status = QLabel(_t("rng.status.none") if self._schema_mode == "none" else _t("rng.status.pending"))
        # Lueur qui tourne pendant une validation dans le processus séparé.
        self.rng_busy = BusyIndicator(self)
        self.rng_busy.setToolTip(_t("rng.status.running.tip"))
        worker = worker_client()
        worker.busyChanged.connect(self._rng_busy_changed)
        self._rng_busy_changed(worker.busy)
        self.schematron_status = QLabel("")
        self.statusBar().addWidget(self.xml_status,1)
        self.statusBar().addPermanentWidget(self.rng_busy)
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
        # Édition assemblée : un changement invalide le résultat partagé.
        self.editor.document().contentsChanged.connect(self._assembly_changed)
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
        for other in self._bottom_panels:
            if other is not panel:
                other.setVisible(False)
        panel.setVisible(True)
        total = max(450, self.left_splitter.height())
        bottom = min(max(150, int(height)), max(150, total // 2))
        sizes = [max(240, total - bottom)] + [0] * len(self._bottom_panels)
        index = self.left_splitter.indexOf(panel)
        if 0 <= index < len(sizes):
            sizes[index] = bottom
        self.left_splitter.setSizes(sizes)

    def _hide_bottom_panel(self, panel):
        panel.setVisible(False)
        self.left_splitter.setSizes([max(300, self.left_splitter.height())] + [0] * len(self._bottom_panels))

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
            if (self._schema_mode != "none" and not resolution.error
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
            QMessageBox.critical(self, _t("project.open_error"), error_message(exc))
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
        self._refresh_document_tab(self.document)

    def _set_title(self):
        name = self.current_path.name if self.current_path else _t("app.untitled"); mark = " *" if self.modified else ""
        self.setWindowTitle(_t("app.window.file", project=self.project.title, name=name, mark=mark))
        self._refresh_document_tab(self.document)

    @Slot(int, int, int)
    def _source_contents_changed(self, position, chars_removed, chars_added):
        """Invalide seulement ce que l'édition rend réellement obsolète."""
        self._source_completion_context_cache.invalidate_from(position)
        lb = self.document.lb
        if lb.dirty:
            return
        start = max(0, int(position))
        cursor = QTextCursor(self.editor.document())
        inserted = ""
        if chars_added:
            cursor.setPosition(start)
            cursor.setPosition(start + max(0, int(chars_added)), QTextCursor.MoveMode.KeepAnchor)
            inserted = cursor.selectedText()
        # Texte qui précède la modification : permet de savoir si elle a lieu
        # à l'intérieur d'une balise.
        cursor.setPosition(max(0, start - LB_EDIT_LOOKBACK))
        cursor.setPosition(start, QTextCursor.MoveMode.KeepAnchor)
        lb.apply_edit(position, chars_removed, chars_added, inserted, cursor.selectedText())

    def _set_lb_spans(self, spans):
        self.document.lb.set(spans)
        if not self.document.is_edition:
            return  # l'état de structure est celui de l'édition
        n = len(self.document.lb.spans)
        self.structure_status.setToolTip("")
        if self._witness_sync_suspended():
            self.structure_status.setText(_t("status.structure.suspended", base=self.base_id))
            self.structure_status.setToolTip(_t("status.structure.suspended.tip"))
            self.structure_status.setStyleSheet("color:#746b61")
        elif self.expected_base_lines is None:
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
        # Les témoins ne suivent que le curseur de l'édition.
        if not self._sync_from_panel and self._edition_displayed(): self.sync_timer.start()

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
        if self._schema_mode != 'none' and hasattr(self, 'rng_status'):
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

        # Édition en parties : l'aperçu montre l'édition assemblée ; ses
        # paragraphes ne correspondent pas à ceux de la source (pas de report
        # de la position d'une vue à l'autre).
        if self._edition_has_parts():
            if self.left_tabs.widget(index) is self.formatted_view:
                self.formatted_view.became_visible()
            return

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

            call_later(20, self, restore_preview_context)
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

            def restore_xml_context(selected=selected_visible, n=ordinal, desc=descriptor, shown=self.document):
                if self.document is not shown:
                    return  # un autre document est affiché entre-temps
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
            and self._rng_invalid_for(self.document, self._last_rng_result)
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
        self._xml_health_session = self.document
        worker = XmlHealthWorker(revision, text, self.lb_base_re)
        self._xml_health_worker = worker
        worker.signals.finished.connect(self._async_xml_health_finished)
        self._xml_health_pool.start(worker)

    @Slot(int, bool, int, int, str, object)
    def _async_xml_health_finished(self, revision, well_formed, line, column, error, spans):
        self._xml_health_running = False
        self._xml_health_worker = None
        # Le résultat ne vaut que pour le document contrôlé : un autre a pu
        # être affiché entre-temps (les révisions sont propres à chaque document).
        checked = self._xml_health_session
        self._xml_health_session = None
        same_document = checked is None or checked is self.document
        current_revision = self.editor.document().revision()
        if same_document and revision == current_revision:
            self._last_xml_health_revision = revision
            self._last_xml_health_well_formed = bool(well_formed)
            self._apply_xml_health_result(well_formed, line, column, error, spans, False)
        # Si le document a changé pendant un contrôle exceptionnellement long
        # et que le timer a déjà expiré, programmer une nouvelle passe courte.
        if (self._xml_health_pending or not same_document or revision != current_revision) and not self.validate_timer.isActive():
            self._xml_health_pending = False
            call_later(180, self, self.validate_editor)

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
            QMessageBox.critical(self, _t("project.open_error"), error_message(exc))
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
                                        _t("project.reopen_error", path=startup_project, error=error_message(exc)))
                    win = WelcomeWindow()
            else:
                # Le projet de démonstration reste livré, mais n'est jamais ouvert
                # automatiquement à la première utilisation.
                win = WelcomeWindow()
    except Exception as exc:
        QMessageBox.critical(None, _t("project.open_error"), error_message(exc))
        return 2
    # « Plein écran » au sens bureau : fenêtre maximisée, sans masquer la barre
    # des tâches ni les contrôles natifs de la fenêtre.
    win.showMaximized()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
