# -*- coding: utf-8 -*-
"""Étapes de la construction de la fenêtre principale (V0.9.4.7).

Mixin de ``MainWindow`` (editeur_tei.py). Chaque méthode est un bloc de
l'ancien constructeur, recopié tel quel, que ``MainWindow.__init__`` appelle
à la même place : ressources des témoins, éditeur et aperçu, panneaux des
témoins, disposition de la fenêtre, barre d'état. Aucune variable locale ne
passait d'un bloc à l'autre ; ce qu'une étape prépare pour la suivante est
un attribut de la fenêtre."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QFrame, QHBoxLayout, QLabel, QScrollArea, QSizePolicy, QSplitter,
    QTabWidget, QVBoxLayout, QWidget,
)

from project_config import has_line_synchronization
from resource_state import primary_sync_line_count, secondary_sync_link_count
from app_context import _settings, call_later, tr as _t
from formatted_view import FormattedEditionWidget
from manuscript_panel import ManuscriptPanel
from code_editor import CodeEditor, TextDocument, XMLHighlighter
from witness_resource_refresh import AlignmentError, read_alignment_json
from witness_sync import flatten_primary, flatten_secondary
from text_segments import TEXT_ABSENT
from schematron_rules_dialog import ClickableLabel
from busy_indicator import BusyIndicator
from validation_worker import worker_client
from image_sources import (
    apply_witness_image_policy, image_only_items, page_image_source, page_navigation_items,
)
from alto_import import apply_witness_alto_policy
from iiif_local import apply_working_copy


class WindowSetupMixin:
    """Étapes de ``MainWindow.__init__`` (voir le module)."""

    def _load_witness_resources(self):
        """Ressources des témoins, lues à l'ouverture du projet : alignements
        (JSON), ALTO, images, copie IIIF de travail ; nombre de lignes attendu
        du pivot, unités de navigation de chaque panneau, présence d'images.
        Un fichier d'alignement abîmé est signalé sans empêcher l'ouverture."""
        # V0.7.0 : les ressources d'un témoin sont facultatives. Un témoin
        # sans fichier d'alignement reste un témoin parfaitement valide ; son
        # panneau existe mais la synchronisation ALTO/base_keys est inactive.
        self.alignment_caches = {}
        self._raw_alignment_caches = {}
        self.witness_items = {}
        self.base_maps = {}
        self.base_by_key = {}
        # Le nombre de lignes attendu par la TEI vient exclusivement du JSON
        # de synchronisation du témoin pivot. Un ALTO indépendant n'est pas
        # une synchronisation et ne doit jamais imposer ce nombre.
        self._base_sync_line_count = None
        self._secondary_sync_link_counts = {}
        # Un fichier d'alignement abîmé (red team 2, B5) : le projet s'ouvre,
        # sans synchroniser ce seul témoin, et c'est dit.
        self._alignment_problems = []
        for w in self.witness_configs:
            cache = None
            if has_line_synchronization(w):
                try:
                    cache = read_alignment_json(w.alignment)
                except AlignmentError as exc:
                    self._alignment_problems.append((w, exc))
            if cache is not None:
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
        if self._alignment_problems:
            call_later(0, self, self._report_alignment_problems)
        # Projet sans témoin : pas de pivot, rien à synchroniser.
        base_cfg = self.project.witness_by_id.get(self.base_id)
        # V0.8.4 : un fichier JSON vide/provisoire n'active pas le mode ligne.
        # Le nombre est mesuré avant toute superposition ALTO, afin qu'un ALTO
        # indépendant ne puisse jamais être pris pour une synchronisation TEI.
        self.base_alignment_available = bool(
            base_cfg is not None and has_line_synchronization(base_cfg) and (self._base_sync_line_count or 0) > 0
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

    def _build_document_views(self):
        """Éditeur de la source XML et aperçu XSLT / CSS, leurs raccourcis
        (Ctrl+E, Ctrl+Espace, références) ; onglets « XML source » et
        « Aperçu », case du retour à la ligne visuel, barre de remplacement."""
        self.editor = CodeEditor()
        # Le QTextDocument appartient au document ouvert, non à l'éditeur.
        self.document.text_document = TextDocument(self)
        self.editor.set_text_document(self.document.text_document)
        self.highlighter = XMLHighlighter(self.editor.document())
        self.formatted_view = FormattedEditionWidget(self)
        self.editor.attribute_completion_provider = self._auto_attribute_choices
        self.formatted_view.fragment_editor.attribute_completion_provider = self._auto_attribute_choices
        self.editor.value_completion_provider = self._auto_value_choices
        self.formatted_view.fragment_editor.value_completion_provider = self._auto_value_choices
        # Invalidation incrémentale : les points lexicaux antérieurs à l'édition
        # restent valides et accélèrent les Ctrl+Espace suivants. Les
        # modifications arrivent en indices Python (red team, A2).
        self.editor.text_change_listener = self._source_contents_changed
        self.formatted_view.fragment_editor.text_change_listener = (
            lambda position, _removed, _added, _text: self._fragment_completion_context_cache.invalidate_from(position)
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
        # Chercher et remplacer (Ctrl+H, V0.9.2.8) : sous l'éditeur, fermée au départ.
        source_layout.addWidget(self._build_replace_bar())

        self.left_tabs.addTab(self.source_tab, _t("tab.xml_source"))
        self.left_tabs.addTab(self.formatted_view, _t("tab.preview"))
        self._previous_left_tab_index = 0
        self.left_tabs.currentChanged.connect(self._left_tab_changed)
        self._last_save_context = "source"
        QApplication.instance().focusChanged.connect(self._track_edit_focus)

    def _build_witness_panels(self):
        """Panneaux des témoins (``ManuscriptPanel``) dans leurs dispositions
        (verticale, horizontale, grille) et leur zone défilante ; signaux de
        chaque panneau, réglages de disposition retenus pour le projet."""
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
        leading = self._load_leading_witnesses()
        for w in self.witness_configs:
            panel = ManuscriptPanel(
                w.id,
                w.display_title,
                self.witness_display_items[w.id],
                self.base_maps.get(w.id),
                is_base=w.is_base,
                base_label=self.witness_titles[self.base_id],
                project_root=self.project.root_dir,
                sync_enabled=((self.base_alignment_available and bool(self.base_items)) if w.is_base
                              else bool(self.base_alignment_available and self._secondary_sync_link_counts.get(w.id, 0) > 0)),
            )
            self.panels[w.id] = panel
            # Les flèches de ce manuscrit mènent-elles l'édition (V0.9.2.8.1) ?
            # Retenu pour le projet ; par défaut, celles du pivot seulement.
            panel.set_leads_edition(leading.get(w.id, w.is_base))
            panel.leadsEditionChanged.connect(self._witness_lead_changed)
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
            # Un témoin qui n'a de JSON que pour des textes synchronisés à
            # part (V0.9.1.1) garde son panneau, sauf s'il est déclaré sans image.
            self._witness_image_available[w.id] = any(
                page_image_source(page, self.project.root_dir).available
                for page in (cache.get("pages", []) or [])
            ) or (w.id in self._text_witness_ids() and getattr(w, "image_source_type", "auto") != "none")
            # Sans donnée pour l'édition, dans un projet à textes à part : le
            # panneau le dit, comme le viewer web (red team 2, D5).
            if not self.witness_display_items[w.id] and self._text_witness_ids():
                panel.set_absent(TEXT_ABSENT)
            self.witness_splitter.addWidget(panel)
            # Ces commandes écrivent dans l'édition : refusées si un autre
            # document est affiché.
            panel.markPageRequested.connect(self._edition_write(self._mark_page_in_tei))
            panel.splitFolioRequested.connect(self._edition_write(self._split_double_folio))
            panel.maximizeRequested.connect(self._toggle_witness_panel_maximize)
            panel.detachRequested.connect(self._toggle_detached_witness)
            # Connect once, even if synchronization becomes active later. Le
            # pivot peut changer avec le texte affiché : seul le panneau du
            # pivot du moment émet ce signal.
            panel.primaryNavigate.connect(self._edition_navigation(self._primary_panel_navigate))
            # Les flèches de tout panneau mènent l'édition (V0.9.1.4).
            panel.witnessNavigate.connect(self._witness_panel_navigate)
            if panel.items and not panel.sync_enabled:
                call_later(0, panel, panel.reload)
        self.base_panel = self.panels.get(self.base_id)          # None sans témoin
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

    def _build_main_layout(self):
        """Panneaux inférieurs (validation, XPath, références, résultats de
        recherche), colonne de gauche et séparateur principal entre les
        documents et les témoins."""
        # Colonne gauche : les deux vues de l'édition + panneau de validation
        # RELAX NG rétractable. Le panneau reste fermé tant qu'il n'est pas
        # utile, afin de ne pas pénaliser les petits écrans.
        self.validation_panel = self._build_validation_panel()
        self.xpath_panel = self._build_xpath_panel()
        self.references_panel = self._build_references_panel()
        self.search_results_panel = self._build_search_results_panel()
        self._bottom_panels = [self.validation_panel, self.xpath_panel, self.references_panel,
                               self.search_results_panel]
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
        call_later(0, self, self._restore_main_splitter_ratio)
        call_later(0, self, self._restore_detached_witnesses)

    def _build_status_bar(self):
        """Barre d'état : bonne formation, curseur, structure (lignes du pivot),
        validation RELAX NG et sa lueur, règles Schematron."""
        self.xml_status = QLabel(_t("status.xml.initial")); self.cursor_status = QLabel(_t("status.cursor", line=1, column=1))
        self.structure_status = QLabel(
            _t("status.structure.no_witness") if not self.base_id
            else _t("status.structure.expected", base=self.witness_siglum(self.base_id), count=self.expected_base_lines)
            if self.expected_base_lines is not None
            else _t("status.structure.no_alignment", base=self.witness_siglum(self.base_id))
        )
        self.rng_status = QLabel(_t("rng.status.none") if self._schema_mode == "none" else _t("rng.status.pending"))
        # Lueur qui tourne pendant une validation dans le processus séparé.
        self.rng_busy = BusyIndicator(self)
        self.rng_busy.setToolTip(_t("rng.status.running.tip"))
        worker = worker_client()
        worker.busyChanged.connect(self._rng_busy_changed)
        self._rng_busy_changed(worker.busy)
        # Un clic ouvre « Règles Schematron du document… » (V0.9.2.5).
        self.schematron_status = ClickableLabel("")
        self.schematron_status.setCursor(Qt.CursorShape.PointingHandCursor)
        self.schematron_status.clicked.connect(self.schematron_rules_dialog)
        self.statusBar().addWidget(self.xml_status,1)
        self.statusBar().addPermanentWidget(self.rng_busy)
        self.statusBar().addPermanentWidget(self.rng_status)
        self.statusBar().addPermanentWidget(self.schematron_status)
        self.statusBar().addPermanentWidget(self.structure_status)
        self.statusBar().addPermanentWidget(self.cursor_status)
        self._set_document_health("normal")
