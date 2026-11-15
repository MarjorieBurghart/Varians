# -*- coding: utf-8 -*-
"""Varians — éditeur TEI/manuscrits générique — V0.9.4.7.

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
_LOCAL_MODULE_NAMES = {"project_config", "project_management", "project_dialogs", "project_widgets", "iiif_canvas_picker", "witness_edit_dialog", "witness_table", "i18n", "relaxng_validation", "schema_resolution", "rng_completion", "xpath_search", "save_io", "custom_completion", "image_sources", "iiif_manifest", "iiif_local", "iiif_selection", "iiif_download_manager", "iiif_page_selection", "alto_import", "tei_facsimile", "xml_tag_pairs", "tei_formatter", "selection_sync", "selection_quote", "mac_message_boxes", "error_log", "error_log_ui", "witness_resource_refresh", "resource_state", "witness_layout", "iiif_resolution", "folio_navigation", "xml_folding", "document_session", "app_context", "formatted_view", "preview_css", "preview_browser", "formatted_views", "fragment_editor", "preview_find", "element_wrap", "image_fetch", "manuscript_panel", "code_editor", "witness_sync", "project_actions", "main_menus", "help_dialogs", "witness_workspace", "document_io", "completion_ui", "validation_panel", "xpath_panel", "document_tabs", "document_display", "document_dialogs", "xml_references", "references_ui", "apparatus_xpath", "apparatus_ui", "relaxng_worker", "validation_worker", "busy_indicator", "xml_assembly", "pivot_lines", "text_alignments", "text_segments", "lacunae", "witness_route", "preview_sources", "segment_model", "xslt_engines", "transform_worker", "xslt_scenarios", "transform_runner", "transform_ui", "xslt_check_ui", "xslt_completion", "tei_stylesheets", "tei_stylesheets_ui", "schematron", "schematron_check", "schematron_check_ui", "schematron_completion", "xml_roots", "xml_model_edit", "schematron_rules_dialog", "xslt_packages", "text_search", "replace_bar", "help_search", "search_results", "fragment_units", "witness_rename", "witness_rename_plan", "witness_rename_ui", "source_selection", "pivot_line_index", "xml_health", "find_commands", "window_setup", "self_test", "large_files", "document_templates", "tei_templates", "tei_templates_ui", "view_files", "view_dialogs", "saxon_preview"}
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
# Processus d'une transformation XSLT (voir transform_runner), de même.
if __name__ == "__main__" and sys.argv[1:2] == ["--transform-worker"]:
    from transform_worker import serve
    raise SystemExit(serve())
# Processus d'aperçu des vues en XSLT 2.0 ou 3.0 (voir saxon_preview), de même ;
# il reste ouvert et reçoit en argument le fichier de sa sortie d'erreur.
if __name__ == "__main__" and sys.argv[1:2] == ["--preview-worker"]:
    from saxon_preview import serve
    raise SystemExit(serve(stderr_log=sys.argv[2] if len(sys.argv) > 2 else None))

from project_config import load_project
from project_management import create_portable_project, create_new_transcription_project
from project_dialogs import NewProjectDialog, run_pivot_scaffold_dialog
from i18n import I18nManager
from app_context import (
    apply_application_icon, apply_qt_language, call_later, error_message, set_i18n, tr, _settings, recent_project_paths, remember_recent_project,
    remove_recent_project, clear_recent_projects, last_open_project_path, remember_open_project,
    forget_open_project, startup_pending_project, mark_startup_pending, forget_startup_pending,
)
from large_files import confirm_large_files, large_project_files
from document_session import DocumentSession
from save_io import atomic_write_text_with_backup
from pivot_lines import pivot_lb_pattern
from xml_assembly import path_key
from code_editor import CodeEditor, XMLHighlighter
from replace_bar import ReplaceBarMixin
from search_results import SearchResultsMixin
from witness_resource_refresh import alignment_error_text
from witness_sync import WitnessSyncMixin
from project_actions import ProjectActionsMixin
from main_menus import MainMenusMixin, TEI_GUIDE_URL
from help_dialogs import (
    _build_varians_card, _open_external, _open_latin_dictionary, _show_about, _show_software_help,
)
from error_log_ui import open_log_folder
from witness_workspace import WitnessWorkspaceMixin
from document_io import DocumentIOMixin
from completion_ui import CompletionMixin
from validation_panel import ValidationPanelMixin
from xpath_panel import XPathPanelMixin
from document_tabs import DocumentTabsMixin
from text_segments import TextSegmentsMixin
from document_display import DocumentDisplayMixin
from document_dialogs import DocumentDialogsMixin
from references_ui import ReferencesMixin
from apparatus_ui import ApparatusDebugMixin
from source_selection import SourceSelectionMixin
from pivot_line_index import PivotLineIndexMixin
from xml_health import XmlHealthMixin
from find_commands import FindCommandsMixin
from window_setup import WindowSetupMixin
import error_log
import error_log_ui
import mac_message_boxes

# Sous macOS, le titre d'une boîte de message devient son message principal :
# Qt ne l'y affiche pas. Ailleurs, rien ne change (V0.9.4.6).
mac_message_boxes.install()
# Journal des erreurs (V0.9.4.6) : voir error_log.
_journal = error_log.logger("window")
from transform_ui import TransformScenariosMixin
from xslt_check_ui import StylesheetCheckMixin
from schematron_check_ui import SchematronCheckMixin
from schematron_rules_dialog import SchematronRulesMixin
from tei_stylesheets_ui import at_launch as tei_stylesheets_at_launch
from tei_templates_ui import at_launch as tei_templates_at_launch
from rng_completion import XmlContextCache
from tei_formatter import format_tei_xml

try:
    from PySide6.QtCore import Qt, QTimer, QThreadPool, QEvent, Slot
    from PySide6.QtGui import QTextCursor, QAction, QKeySequence
    from PySide6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QToolBar, QFileDialog, QMessageBox,
        QLabel, QSizePolicy, QVBoxLayout, QFrame,
        QDialog, QDialogButtonBox, QMenu, QToolButton,
    )
except ImportError:
    print("PySide6 n'est pas installé.")
    print("Installez-le avec : python -m pip install --user PySide6")
    raise

HERE = Path(__file__).resolve().parent
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

def _t(key, /, default=None, **values):
    return tr(key, default=default, **values)


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
        """Bouton « Enregistrer » : vérifie que le texte est du XML bien formé, de
        racine ``<customElements>``, puis l'écrit (écriture atomique, copie
        ``.bak``). True si le fichier est enregistré ; False après un message
        d'erreur. ``closeEvent`` l'appelle aussi avant de fermer la boîte."""
        text = self.editor.toPlainText()
        try:
            root = ET.fromstring(text)
            if root.tag != "customElements":
                raise ValueError(_t("ctrl_e.config.root_error", file=self.path))
        except Exception as exc:
            QMessageBox.warning(self, _t("ctrl_e.config.editor.invalid.title"), str(exc))
            return False
        try:
            atomic_write_text_with_backup(self.path, text)          # .bak, écriture atomique
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


class MainWindow(WindowSetupMixin, SourceSelectionMixin, PivotLineIndexMixin, XmlHealthMixin, FindCommandsMixin, WitnessSyncMixin, TextSegmentsMixin, ProjectActionsMixin, MainMenusMixin, WitnessWorkspaceMixin, DocumentIOMixin, CompletionMixin, ValidationPanelMixin, XPathPanelMixin, DocumentTabsMixin, DocumentDisplayMixin, DocumentDialogsMixin, ReferencesMixin, ApparatusDebugMixin, TransformScenariosMixin, StylesheetCheckMixin, SchematronCheckMixin, SchematronRulesMixin, ReplaceBarMixin, SearchResultsMixin, QMainWindow):
    """Fenêtre d'un projet : éditeur XML source, aperçu mis en forme, panneaux
    des témoins, menus et barres d'outils. Le constructeur lit ``project.xml``
    et les ressources des témoins (alignements, ALTO, images) ; les commandes
    sont réparties entre les classes mixtes (``*Mixin``) dont elle hérite. Les
    attributs déclarés en tête renvoient à l'état du document ouvert
    (``self.document``, voir ``document_session``)."""
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
    _last_synced_lacunae = _document_attribute("last_synced_lacunae")
    highlighter = _document_attribute("highlighter")
    # Schéma du document affiché (celui du projet pour l'édition).
    _schema_mode = _document_attribute("schema_mode")
    _schema_file = _document_attribute("schema_file")

    def __init__(self, project_path):
        super().__init__()
        # Document ouvert : doit exister avant toute affectation des attributs
        # de compatibilité ci-dessus.
        self.document = DocumentSession()
        # Changement de sigle interrompu (V0.9.4.0) : défait avant toute lecture.
        from witness_rename_ui import recover_interrupted_rename
        recover_interrupted_rename(project_path, None, _t)
        self.project = load_project(project_path)
        self.document.schema_mode = self.project.schema_mode
        self.document.schema_file = self.project.schema
        self._init_documents()
        remember_recent_project(self.project.path)
        global I18N
        I18N = I18nManager(self.project.translations_dir, self.project.language, self.project.fallback_language)
        set_i18n(I18N)
        apply_qt_language(I18N.language)
        app = QApplication.instance()
        if app is not None:
            app.setApplicationName(_t("app.name"))
        self.base_id = self.project.base_witness
        self.witness_configs = list(self.project.witnesses)
        self.witness_labels = {w.id: w.label for w in self.witness_configs}
        # Sigles montrés à l'écran (V0.9.2.8.2) ; le XML garde les identifiants.
        self.witness_sigla = {w.id: w.display_siglum for w in self.witness_configs}
        self.witness_titles = {w.id: w.display_title for w in self.witness_configs}
        self.lb_base_re = pivot_lb_pattern(self.base_id)
        # Segment des données des témoins : None pour l'édition, sinon un
        # texte synchronisé à part (V0.9.1.1, voir text_segments).
        self._active_segment = None

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

        # Étapes de la construction (window_setup, sauf la barre d'outils).
        self._load_witness_resources()
        self._build_document_views()
        self._build_witness_panels()
        self._build_main_layout()
        self._build_toolbar()
        self._build_status_bar()

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
        # Projet rouvert : le curseur et le document affiché d'avant.
        self._restore_cursor_places()
        remember_open_project(self.project.path)

    def _report_alignment_problems(self):
        texts = [_t("alignment.damaged", witness=self.witness_siglum(w.id), file=str(w.alignment),
                    detail=alignment_error_text(exc, _t)) for w, exc in self._alignment_problems]
        QMessageBox.warning(self, _t("alignment.damaged.title"), "\n\n".join(texts))

    def witness_siglum(self, witness_id):
        """Sigle du témoin ``witness_id`` pour l'affichage : le sigle saisi
        dans les paramètres du projet, sinon l'identifiant lui-même."""
        return getattr(self, "witness_sigla", {}).get(witness_id, witness_id)

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

        # Positions Python du texte formaté (red team, A2).
        qt = self.editor.positions(source)
        old_cursor = self.editor.textCursor()
        old_pos = qt.python(old_cursor.position())
        old_anchor = qt.python(old_cursor.anchor())
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
            # Du bas vers le haut : le texte qui précède chacun est intact.
            for repl in reversed(result.replacements):
                edit.setPosition(qt.qt(repl.start))
                edit.setPosition(qt.qt(repl.end), QTextCursor.MoveMode.KeepAnchor)
                edit.insertText(repl.text)
        finally:
            edit.endEditBlock()
            self.editor._pair_edit_guard = previous_guard
            self.editor._pair_previous_text = self.editor.toPlainText()

        formatted = self.editor.toPlainText()
        qt = self.editor.positions(formatted)
        restored = QTextCursor(self.editor.document())
        restored.setPosition(qt.qt(max(0, min(len(formatted), new_anchor))))
        restored.setPosition(
            qt.qt(max(0, min(len(formatted), new_pos))),
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

    def _remember_cursor_places_safely(self):
        """``remember_cursor_places``, sans jamais empêcher de fermer ou de
        recharger la fenêtre."""
        try:
            self.remember_cursor_places()
        except Exception:
            _journal.warning("Places du curseur non gardées", exc_info=True)

    def _replace_with_project(self, project_path):
        """Recharge l'application sur un autre project.xml après garde-fou de
        sauvegarde. Si un fichier de son édition dépasse le seuil de taille,
        Varians demande d'abord (``large_files``) ; sans accord, rien ne change."""
        if not confirm_large_files(self, large_project_files(project_path)):
            return False
        if not self.maybe_save():
            return False
        # Même projet rouvert : sa nouvelle fenêtre reprend la place du moment.
        self._remember_cursor_places_safely()
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

    def _set_title(self):
        name = self.current_path.name if self.current_path else _t("app.untitled"); mark = " *" if self.modified else ""
        self.setWindowTitle(_t("app.window.file", project=self.project.title, name=name, mark=mark))
        self._refresh_document_tab(self.document)

    def _cursor_changed(self):
        c=self.editor.textCursor(); self.cursor_status.setText(_t("status.cursor", line=c.blockNumber()+1, column=c.positionInBlock()+1))
        # Les témoins suivent le curseur de l'édition et de ses parties.
        if not self._sync_from_panel and self.document.in_edition: self.sync_timer.start()

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

    # Slot Qt d'un signal émis dans un autre fil (XmlHealthWorker) : défini
    # ici, dans MainWindow même, et non dans le mixin xml_health. PySide lie
    # alors la connexion à la fenêtre et l'oublie à sa destruction ; défini
    # dans un mixin, un résultat arrivé pendant la destruction serait livré
    # après, sur un éditeur détruit (test_gui_xml_health_teardown).
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

    def closeEvent(self,event):
        if self._force_close or self.confirm_close_application():
            self._remember_cursor_places_safely()
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
        self.action_tei_guide = self._make_action(_t("help.tei_guide"), "", lambda: _open_external(TEI_GUIDE_URL))
        self.action_software_help = self._make_action(
            _t("help.software"), "F1", lambda: _show_software_help(self)
        )
        self.action_error_log = self._make_action(
            _t("help.error_log"), "", lambda: open_log_folder(self), _t("help.error_log.tip")
        )
        self.action_about = self._make_action(
            _t("help.about"), "", lambda: _show_about(self)
        )
        self.help_menu.addAction(self.action_enigma)
        self.help_menu.addAction(self.action_latin_dictionary)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.action_tei_guide)
        self.help_menu.addSeparator()
        self.help_menu.addAction(self.action_software_help)
        self.help_menu.addAction(self.action_error_log)
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
        """Remplit le sous-menu « Réouvrir un projet récent… » : une entrée par
        projet (titre lu dans le fichier projet, sinon nom de son dossier), ou
        « Aucun projet récent », puis « Effacer la liste des projets récents »."""
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
        """« Effacer la liste des projets récents » : vide la liste enregistrée,
        puis le sous-menu."""
        clear_recent_projects()
        self.update_recent_projects_menu()

    def _open_project_path(self, project_path):
        """Ouvre le projet ``project_path`` dans une nouvelle fenêtre et ferme
        l'accueil ; un message s'il ne s'ouvre pas. Si un fichier de son
        édition dépasse le seuil de taille, Varians demande d'abord
        (``large_files``). Renvoie True si le projet est ouvert."""
        if not confirm_large_files(self, large_project_files(project_path)):
            return False
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
        """Fichier ▸ « Ouvrir un projet… » (Ctrl+O) : choisit un fichier projet, en
        partant du dossier du projet le plus récent (sinon du dossier personnel),
        et l'ouvre ; la fenêtre d'accueil se ferme si l'ouverture réussit."""
        recent = recent_project_paths()
        start = str(Path(recent[0]).parent if recent else Path.home())
        fn, _ = QFileDialog.getOpenFileName(
            self, _t("project.open.title"), start,
            f"{_t('project.open.filter')} (*.xml);;{_t('common.all_files')} (*)",
        )
        if fn:
            self._open_project_path(Path(fn))

    def open_recent_project(self, path):
        """Ouvre le projet ``path`` choisi dans les projets récents. Un fichier qui
        n'existe plus est retiré de la liste, avec un avertissement."""
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            remove_recent_project(path)
            self.update_recent_projects_menu()
            QMessageBox.warning(self, _t("project.recent.missing.title"), _t("project.recent.missing", path=path))
            return
        self._open_project_path(path)

    def new_project_dialog(self):
        """Fichier ▸ « Nouveau projet… » (Ctrl+N) : la boîte ``NewProjectDialog``,
        puis la création du projet (nouvelle transcription, ou copie d'une
        édition TEI existante), la « Préparation de la transcription du témoin
        pivot » si elle est demandée (nouvelle transcription seulement), et
        l'ouverture du projet. Si un témoin IIIF demande une copie locale, le
        gestionnaire des téléchargements IIIF démarre aussitôt."""
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


def startup_window(argv):
    """Fenêtre du démarrage, encore cachée.

    Le projet passé en argument (``argv[1]``), sinon celui qui était encore
    ouvert à la dernière fermeture (oublié, avec un avertissement, s'il ne se
    rouvre pas), sinon la fenêtre d'accueil. Avant d'ouvrir un projet dont un
    fichier dépasse le seuil de taille (``large_files``), Varians demande ;
    sans accord, la fenêtre d'accueil.

    Garde-fou : la réouverture automatique est notée avant de commencer
    (``mark_startup_pending``) et effacée une fois la fenêtre affichée
    (:func:`show_startup_window`). Si elle est encore notée au démarrage
    suivant, Varians a été fermé avant d'afficher sa fenêtre : ce projet
    n'est pas rouvert de nouveau, et l'accueil le dit. Une erreur
    d'ouverture du projet passé en argument est propagée."""
    if len(argv) > 1:
        project_path = Path(argv[1]).resolve()
        if not confirm_large_files(None, large_project_files(project_path)):
            return WelcomeWindow()
        return MainWindow(project_path)
    interrupted = startup_pending_project()
    if interrupted is not None:
        forget_startup_pending()
    # Rouvrir uniquement le projet qui était encore ouvert lors de la
    # précédente fermeture. « Fermer le projet » efface cette préférence.
    startup_project = last_open_project_path()
    if startup_project is None:
        # Le projet de démonstration reste livré, mais n'est jamais ouvert
        # automatiquement à la première utilisation.
        return WelcomeWindow()
    if interrupted is not None and path_key(interrupted) == path_key(startup_project):
        forget_open_project()
        win = WelcomeWindow()
        call_later(0, win, lambda: QMessageBox.warning(
            win, _t("startup.interrupted.title"), _t("startup.interrupted", path=startup_project)))
        return win
    if not confirm_large_files(None, large_project_files(startup_project)):
        forget_open_project()
        return WelcomeWindow()
    mark_startup_pending(startup_project)
    try:
        return MainWindow(startup_project)
    except Exception as exc:
        forget_startup_pending()
        forget_open_project()
        QMessageBox.warning(None, _t("project.reopen_error.title"),
                            _t("project.reopen_error", path=startup_project, error=error_message(exc)))
        return WelcomeWindow()


def show_startup_window(win):
    """Affiche la fenêtre du démarrage, maximisée (« plein écran » au sens
    bureau : sans masquer la barre des tâches ni les contrôles natifs de la
    fenêtre). Une fois la fenêtre affichée, le démarrage est terminé : le
    garde-fou de :func:`startup_window` est effacé."""
    win.showMaximized()
    call_later(0, win, forget_startup_pending)


def main():
    """Point d'entrée de l'interface : la fenêtre de :func:`startup_window`,
    affichée par :func:`show_startup_window` ; les TEI Stylesheets et les
    squelettes TEI sont vérifiés peu après (``tei_stylesheets_ui.at_launch``,
    ``tei_templates_ui.at_launch``). Renvoie le code
    de sortie de l'application, 2 si le projet passé en argument ne s'ouvre
    pas."""
    app = QApplication.instance() or QApplication(sys.argv)
    # Journal des erreurs (V0.9.4.6) : exceptions non rattrapées, erreurs
    # montrées, processus séparés en échec.
    error_log_ui.install_for_application()
    apply_application_icon(app)
    _install_light_selection_palette(app)
    startup_language = str(_settings().value("startupLanguage", "fr") or "fr")
    I18N.set_language(startup_language)
    apply_qt_language(I18N.language)
    app.setApplicationName(_t("app.name"))
    try:
        win = startup_window(sys.argv)
    except Exception as exc:
        QMessageBox.critical(None, _t("project.open_error"), error_message(exc))
        return 2
    show_startup_window(win)
    # TEI Stylesheets : anciennes versions supprimées, puis, au plus une fois
    # par mois, recherche d'une nouvelle version (sans bloquer la fenêtre).
    call_later(1500, win, lambda: tei_stylesheets_at_launch(win))
    call_later(2500, win, lambda: tei_templates_at_launch(win))
    return app.exec()

if __name__ == "__main__" and sys.argv[1:2] == ["--self-test"]:
    # Vérification d'une installation, version autonome comprise (self_test).
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from self_test import run as self_test
    raise SystemExit(self_test(sys.argv[2] if len(sys.argv) > 2 else None, window_class=MainWindow))

if __name__ == "__main__":
    raise SystemExit(main())
