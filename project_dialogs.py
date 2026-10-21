# -*- coding: utf-8 -*-
"""Dialogues de création et modification des projets Varians V0.8.5.10."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGridLayout, QGroupBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QScrollArea, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QWidget,
)

from project_management import ProjectDraft, WitnessDraft, LocalImageDraft, AltoFileDraft
from iiif_manifest import fetch_manifest, parse_manifest
from tei_facsimile import default_surface_id, valid_xml_id
from iiif_page_selection import canvas_key, natural_key, propose_exact_ocr_links


class PathRow(QWidget):
    def __init__(self, value="", parent=None, mode="file", caption="", file_filter="Tous les fichiers (*)"):
        super().__init__(parent)
        self.mode = mode
        self.caption = caption
        self.file_filter = file_filter
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(str(value or ""))
        self.button = QPushButton("…")
        self.button.setMaximumWidth(34)
        self.button.clicked.connect(self.browse)
        lay.addWidget(self.edit, 1); lay.addWidget(self.button)

    def browse(self):
        start = self.edit.text().strip() or str(Path.home())
        if self.mode == "dir":
            value = QFileDialog.getExistingDirectory(self, self.caption, start)
        else:
            value, _ = QFileDialog.getOpenFileName(self, self.caption, start, self.file_filter)
        if value:
            self.edit.setText(value)

    def text(self):
        return self.edit.text().strip()


class IIIFCanvasPicker(QDialog):
    """Pick actual editorial canvases, associate each with at most one local OCR.

    No network activity occurs in the picker: its manifest has already been
    fetched/cached on a deliberate user action. Manifest order is immutable.
    """
    def __init__(self, tr, manifest, layouts, selected=(), links=(), parent=None,
                 *, sync_pages=(), page_links=(), project_root=None, witness_id='W', use_local=False):
        super().__init__(parent)
        self.tr = tr
        self.manifest = manifest
        self.setWindowTitle(tr('iiif.picker.title'))
        self.resize(1320, 720)
        root = QVBoxLayout(self)
        info = QLabel(tr('iiif.picker.hint'))
        info.setWordWrap(True)
        root.addWidget(info)
        filter_row = QHBoxLayout()
        filter_row.addWidget(QLabel(tr('iiif.picker.filter')))
        self.search = QLineEdit()
        filter_row.addWidget(self.search, 1)
        self.selected_count = QLabel()
        filter_row.addWidget(self.selected_count)
        root.addLayout(filter_row)
        self.table = QTableWidget(len(manifest.pages), 7)
        self.table.setHorizontalHeaderLabels([
            tr('iiif.picker.keep'), tr('iiif.picker.order'),
            tr('iiif.picker.canvas'), tr('iiif.picker.ocr'),
            tr('iiif.picker.sync_page'), tr('iiif.picker.local'), tr('iiif.picker.state'),
        ])
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(3, 190)
        self.table.setColumnWidth(4, 160)
        self.sync_pages = list(sync_pages or ())
        from iiif_resolution import resolve_pages
        self._page_links = list(page_links or ())
        valid_canvas_ids = {canvas_key(page) for page in manifest.pages}
        valid_explicit = [(pid, canvas) for pid, canvas in self._page_links
                          if canvas in valid_canvas_ids]
        self._sync_auto = resolve_pages(self.sync_pages, manifest, explicit_links=valid_explicit) if self.sync_pages else {}
        self._auto_sync_by_canvas = {
            match.key: str(self.sync_pages[i]['id'])
            for i, match in self._sync_auto.items() if match.key
        }
        self._sync_selected_initial = {str(canvas): str(page_id) for page_id, canvas in self._page_links}
        self._sync_auto_initial = dict(self._auto_sync_by_canvas)
        selected_set = set(selected or ())
        links_by_canvas = {str(canvas): str(path) for path, canvas in links or ()}
        self.layout_choices = [(str(Path(item.path).expanduser().resolve()),
                                f'{getattr(item, "label", "") or Path(item.path).stem} — {Path(item.path).name}')
                               for item in layouts or ()]
        self._proposed_links, self._auto_problems = propose_exact_ocr_links(
            manifest, layouts, links)
        # For a brand-new selection, suggestions appear immediately. For an
        # already selected canvas deliberately saved without OCR, do not
        # overwrite that choice when the dialog is reopened.
        self._auto_initial_keys = set(self._proposed_links).difference(selected_set)
        for i, page in enumerate(manifest.pages):
            key = canvas_key(page)
            keep = QTableWidgetItem('')
            keep.setFlags((keep.flags() | Qt.ItemFlag.ItemIsUserCheckable) & ~Qt.ItemFlag.ItemIsEditable)
            keep.setCheckState(Qt.CheckState.Checked if key in selected_set else Qt.CheckState.Unchecked)
            keep.setData(Qt.ItemDataRole.UserRole, key)
            self.table.setItem(i, 0, keep)
            rank = QTableWidgetItem(str(i + 1))
            rank.setFlags(rank.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 1, rank)
            label = page.get('label') or page.get('id') or key
            text = QTableWidgetItem(str(label) + ' — ' + key)
            text.setFlags(text.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 2, text)
            combo = QComboBox()
            combo.addItem(tr('iiif.picker.no_ocr'), '')
            for path, title in self.layout_choices:
                combo.addItem(title, path)
            preferred = links_by_canvas.get(key, '')
            if preferred:
                idx = combo.findData(str(Path(preferred).expanduser().resolve()))
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            elif key in self._auto_initial_keys:
                idx = combo.findData(self._proposed_links[key])
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            self.table.setCellWidget(i, 3, combo)
            sync_combo = QComboBox()
            sync_combo.addItem(tr('iiif.picker.no_sync'), '')
            for sync_page in self.sync_pages:
                sid = str(sync_page.get('id') or '')
                sync_combo.addItem(f"{sync_page.get('label') or sid} — {sid}", sid)
            sync_id = self._sync_selected_initial.get(key) or self._auto_sync_by_canvas.get(key)
            if sync_id:
                slot = sync_combo.findData(sync_id)
                if slot >= 0:
                    sync_combo.setCurrentIndex(slot)
            sync_combo.setToolTip(tr('iiif.picker.sync.tip'))
            self.table.setCellWidget(i, 4, sync_combo)
            local_file = None
            if project_root is not None:
                from iiif_local import local_image_path
                local_file = local_image_path(project_root, witness_id, page.get('image') or {})
            local_text = tr('iiif.picker.local.yes') if local_file else tr('iiif.picker.local.no')
            local_item = QTableWidgetItem(local_text)
            local_item.setFlags(local_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            if local_file:
                local_item.setToolTip(str(local_file))
            self.table.setItem(i, 5, local_item)
            state = tr('iiif.picker.status.unlinked')
            if sync_id:
                if key in self._sync_selected_initial:
                    state = tr('iiif.picker.status.manual')
                else:
                    state = tr('iiif.picker.status.auto', method=next(
                        (r.method for r in self._sync_auto.values() if r.key == key), 'canvas'))
                state += ' · ' + (tr('iiif.picker.source.local') if local_file and use_local
                                  else tr('iiif.picker.source.iiif'))
            elif any(key in r.candidates for r in self._sync_auto.values() if r.status == 'ambiguous'):
                state = tr('iiif.picker.status.ambiguous')
            state_item = QTableWidgetItem(state)
            state_item.setFlags(state_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 6, state_item)
        root.addWidget(self.table, 1)
        buttons = QHBoxLayout()
        self.select_visible = QPushButton(tr('iiif.picker.select_visible'))
        self.clear_visible = QPushButton(tr('iiif.picker.clear_visible'))
        self.preview = QPushButton(tr('iiif.picker.preview'))
        self.auto_link = QPushButton(tr('iiif.picker.auto'))
        buttons.addWidget(self.select_visible)
        buttons.addWidget(self.clear_visible)
        buttons.addWidget(self.preview)
        buttons.addWidget(self.auto_link)
        buttons.addStretch(1)
        root.addLayout(buttons)
        self.auto_status = QLabel(tr('iiif.picker.auto.summary',
            matches=len(self._proposed_links), ambiguous=len(self._auto_problems)))
        self.auto_status.setWordWrap(True)
        root.addWidget(self.auto_status)
        actions = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        root.addWidget(actions)
        actions.accepted.connect(self._accept)
        actions.rejected.connect(self.reject)
        self.search.textChanged.connect(self._filter)
        self.select_visible.clicked.connect(lambda: self._mark_visible(True))
        self.clear_visible.clicked.connect(lambda: self._mark_visible(False))
        self.preview.clicked.connect(self._open_preview)
        self.auto_link.clicked.connect(self._apply_auto_links)
        self.table.itemChanged.connect(lambda *_: self._count())
        unresolved = sum(r.status != 'resolved' for r in self._sync_auto.values())
        if unresolved:
            diagnostic = QLabel(tr('iiif.picker.sync.unresolved', count=unresolved))
            diagnostic.setWordWrap(True)
            root.addWidget(diagnostic)
        self._count()

    def _count(self):
        chosen = sum(self.table.item(i, 0).checkState() == Qt.CheckState.Checked
                     for i in range(self.table.rowCount()))
        self.selected_count.setText(self.tr('iiif.picker.count', selected=chosen, total=self.table.rowCount()))

    def _filter(self, query):
        search = query.casefold().strip()
        for i in range(self.table.rowCount()):
            self.table.setRowHidden(i, bool(search) and search not in self.table.item(i, 2).text().casefold())

    def _mark_visible(self, chosen):
        for i in range(self.table.rowCount()):
            if not self.table.isRowHidden(i):
                self.table.item(i, 0).setCheckState(Qt.CheckState.Checked if chosen else Qt.CheckState.Unchecked)

    def _apply_auto_links(self):
        """Apply safe proposals to empty slots only; preserve manual choices."""
        changed = 0
        for i in range(self.table.rowCount()):
            key = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            path = self._proposed_links.get(key)
            combo = self.table.cellWidget(i, 3)
            if not path or combo.currentData():
                continue
            idx = combo.findData(path)
            if idx >= 0:
                combo.setCurrentIndex(idx)
                changed += 1
        self.auto_status.setText(self.tr('iiif.picker.auto.applied',
            matches=changed, ambiguous=len(self._auto_problems)))

    def _open_preview(self):
        index = self.table.currentRow()
        if index < 0:
            return
        image = self.manifest.pages[index].get('image') or {}
        url = image.get('image') or image.get('service')
        if url and str(url).startswith(('https://', 'http://')):
            QDesktopServices.openUrl(QUrl(str(url)))

    def selection(self):
        selected, links = [], []
        for i in range(self.table.rowCount()):
            if self.table.item(i, 0).checkState() != Qt.CheckState.Checked:
                continue
            key = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            selected.append(key)
            source = self.table.cellWidget(i, 3).currentData()
            if source:
                links.append((source, key))
        return selected, links

    def sync_selection(self):
        """Preserve explicit mappings; save newly chosen overrides only."""
        entries = []
        for i in range(self.table.rowCount()):
            key = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
            if self.table.item(i, 0).checkState() != Qt.CheckState.Checked:
                continue
            pid = str(self.table.cellWidget(i, 4).currentData() or '')
            if pid and (key in self._sync_selected_initial or
                        pid != self._sync_auto_initial.get(key)):
                entries.append((pid, key))
        return entries

    def _accept(self):
        selected, links = self.selection()
        explicit_sync = self.sync_selection()
        ids = [pid for pid, _ in explicit_sync]
        chosen_ids = [self.table.cellWidget(i, 4).currentData()
                      for i in range(self.table.rowCount())
                      if self.table.item(i, 0).checkState() == Qt.CheckState.Checked]
        chosen_ids = [pid for pid in chosen_ids if pid]
        if len(set(chosen_ids)) != len(chosen_ids):
            QMessageBox.warning(self, self.tr('project.validation.title'),
                                self.tr('iiif.picker.sync.duplicate'))
            return
        paths = [path for path, _ in links]
        if len(set(paths)) != len(paths):
            QMessageBox.warning(self, self.tr('project.validation.title'), self.tr('iiif.picker.duplicate'))
            return
        # One OCR file can describe multiple PAGE/ALTO pages. Explicit link is
        # only safe when exactly one page is present; otherwise do not assume.
        from alto_import import parse_layout_file
        for path in paths:
            try:
                number = len(parse_layout_file(path).pages)
            except Exception as exc:
                QMessageBox.warning(self, self.tr('project.validation.title'), str(exc))
                return
            if number != 1:
                QMessageBox.warning(self, self.tr('project.validation.title'),
                                    self.tr('iiif.picker.multipage', name=Path(path).name))
                return
        self.accept()


class WitnessEditDialog(QDialog):
    IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp)"

    def __init__(self, tr, witness=None, parent=None, project_root=None):
        super().__init__(parent)
        self.tr = tr
        self.project_root = Path(project_root).resolve() if project_root else None
        self.setWindowTitle(tr("project.witness.edit.title"))
        self.resize(900, 820)
        self._original_alignment = None
        if witness is not None and getattr(witness, "alignment", None):
            try:
                self._original_alignment = Path(witness.alignment).expanduser().resolve()
            except Exception:
                self._original_alignment = Path(witness.alignment).expanduser()
        root = QVBoxLayout(self)
        form = QFormLayout()
        self.id_edit = QLineEdit(getattr(witness, "id", ""))
        self.label_edit = QLineEdit(getattr(witness, "label", ""))
        self.image_source = QComboBox()
        self.image_source.addItem(tr("project.witness.images.none"), "none")
        self.image_source.addItem(tr("project.witness.images.files"), "files")
        self.image_source.addItem(tr("project.witness.images.iiif"), "iiif")
        self.image_source.addItem(tr("project.witness.images.auto"), "auto")
        image_type = getattr(witness, "image_source_type", None)
        if image_type not in {"none", "auto", "files", "iiif"}:
            image_type = "auto" if witness is not None else "none"
        idx = self.image_source.findData(image_type or ("auto" if witness is not None else "none"))
        self.image_source.setCurrentIndex(max(0, idx))
        self.alignment = PathRow(
            getattr(witness, "alignment", ""), self, "file",
            tr("project.witness.alignment.choose"), f"JSON (*.json);;{tr('common.all_files')} (*)"
        )
        form.addRow(tr("project.witness.id"), self.id_edit)
        form.addRow(tr("project.witness.label"), self.label_edit)
        form.addRow(tr("project.witness.images"), self.image_source)
        form.addRow(tr("project.witness.alignment"), self.alignment)
        self.copy_alignment = QCheckBox(tr("project.witness.alignment.copy"))
        self.copy_alignment.setToolTip(tr("project.witness.alignment.copy.tip"))
        alignment_inside_project = False
        if self._original_alignment is not None and self.project_root is not None:
            try:
                self._original_alignment.relative_to(self.project_root)
                alignment_inside_project = True
            except ValueError:
                alignment_inside_project = False
        self._alignment_copy_default = alignment_inside_project if witness is not None else True
        self.copy_alignment.setChecked(self._alignment_copy_default)
        form.addRow("", self.copy_alignment)
        alignment_hint = QLabel(tr("project.witness.alignment.hint")); alignment_hint.setWordWrap(True)
        form.addRow("", alignment_hint)
        root.addLayout(form)

        self.local_group = QGroupBox(tr("project.witness.local_images"))
        lg = QVBoxLayout(self.local_group)
        self.local_table = QTableWidget(0, 3)
        self.local_table.setHorizontalHeaderLabels([
            tr("project.witness.local_images.label"), tr("project.witness.local_images.surface"),
            tr("project.witness.local_images.file")
        ])
        self.local_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)
        self.local_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.local_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.local_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        lg.addWidget(self.local_table, 1)
        buttons_row = QHBoxLayout()
        self.add_images_btn = QPushButton(tr("project.witness.local_images.add"))
        self.remove_image_btn = QPushButton(tr("project.witness.local_images.remove"))
        self.up_image_btn = QPushButton("↑")
        self.down_image_btn = QPushButton("↓")
        self.sort_image_btn = QPushButton(tr("project.witness.sort_natural"))
        buttons_row.addWidget(self.add_images_btn)
        buttons_row.addWidget(self.remove_image_btn)
        buttons_row.addWidget(self.up_image_btn)
        buttons_row.addWidget(self.down_image_btn)
        buttons_row.addWidget(self.sort_image_btn)
        buttons_row.addStretch(1)
        lg.addLayout(buttons_row)
        self.copy_images = QCheckBox(tr("project.witness.local_images.copy"))
        self.copy_images.setChecked(True)
        self.copy_images.setToolTip(tr("project.witness.local_images.copy.tip"))
        lg.addWidget(self.copy_images)
        hint = QLabel(tr("project.witness.local_images.hint")); hint.setWordWrap(True); lg.addWidget(hint)
        root.addWidget(self.local_group, 1)

        self.iiif_group = QGroupBox(tr("project.witness.iiif"))
        ig = QVBoxLayout(self.iiif_group)
        iiif_row = QHBoxLayout()
        self.iiif_manifest = QLineEdit(getattr(witness, "image_source_value", "") if image_type == "iiif" else "")
        self.iiif_load_btn = QPushButton(tr("project.witness.iiif.load"))
        iiif_row.addWidget(self.iiif_manifest, 1); iiif_row.addWidget(self.iiif_load_btn)
        ig.addLayout(iiif_row)
        self.iiif_status = QLabel(tr("project.witness.iiif.hint")); self.iiif_status.setWordWrap(True); ig.addWidget(self.iiif_status)
        self._iiif_manifest_data = None
        self._iiif_manifest_loaded_source = None
        self.iiif_manifest.textChanged.connect(self._manifest_source_changed)
        self._iiif_selection_mode = getattr(witness, 'iiif_selection_mode', 'selected')
        self._iiif_selected_canvases = list(getattr(witness, 'iiif_selected_canvases', ()) or ())
        self._iiif_page_links = list(getattr(witness, 'iiif_page_links', ()) or ())
        self._iiif_ocr_links = list(getattr(witness, 'iiif_ocr_links', ()) or ())
        selection_row = QHBoxLayout()
        self.iiif_selection_mode = QComboBox()
        self.iiif_selection_mode.addItem(tr('iiif.picker.mode.all'), 'all')
        self.iiif_selection_mode.addItem(tr('iiif.picker.mode.selected'), 'selected')
        self.iiif_selection_mode.setCurrentIndex(max(0, self.iiif_selection_mode.findData(self._iiif_selection_mode)))
        selection_row.addWidget(self.iiif_selection_mode, 1)
        self.iiif_pick = QPushButton(tr('iiif.picker.open'))
        selection_row.addWidget(self.iiif_pick)
        ig.addLayout(selection_row)
        self.iiif_pick.clicked.connect(self._pick_iiif_canvases)
        self.iiif_load_btn.clicked.connect(self._load_iiif_manifest)
        self.iiif_local_copy = QCheckBox(tr('project.witness.iiif.local_copy'))
        self.iiif_local_copy.setChecked(bool(getattr(witness, 'iiif_local_copy', False)))
        self.iiif_local_copy.setToolTip(tr('project.witness.iiif.local_copy.tip'))
        ig.addWidget(self.iiif_local_copy)
        self.iiif_web_local_copy = QCheckBox(tr('project.witness.iiif.web_local_copy'))
        self.iiif_web_local_copy.setChecked(bool(getattr(witness, 'iiif_web_local_copy', False)))
        self.iiif_web_local_copy.setToolTip(tr('project.witness.iiif.web_local_copy.tip'))
        ig.addWidget(self.iiif_web_local_copy)
        scope_row = QHBoxLayout()
        scope_row.addWidget(QLabel(tr('project.witness.iiif.scope.label')))
        self.iiif_download_scope = QComboBox()
        self.iiif_download_scope.addItem(tr('project.witness.iiif.scope.all'), 'all')
        self.iiif_download_scope.addItem(tr('project.witness.iiif.scope.ocr'), 'ocr')
        scope = getattr(witness, 'iiif_download_scope', 'all')
        self.iiif_download_scope.setCurrentIndex(max(0, self.iiif_download_scope.findData(scope)))
        self.iiif_download_scope.setToolTip(tr('project.witness.iiif.scope.tip'))
        scope_row.addWidget(self.iiif_download_scope, 1)
        ig.addLayout(scope_row)
        hint_offline = QLabel(tr('project.witness.iiif.copy_hint'))
        hint_offline.setWordWrap(True)
        ig.addWidget(hint_offline)
        root.addWidget(self.iiif_group)

        # V0.7.5 : ALTO est indépendant des images et de la synchronisation.
        self.alto_group = QGroupBox(tr("project.witness.layout"))
        ag = QVBoxLayout(self.alto_group)
        alto_mode_row = QHBoxLayout()
        self.alto_source = QComboBox()
        self.alto_source.addItem(tr("project.witness.alto.auto"), "auto")
        self.alto_source.addItem(tr("project.witness.alto.files"), "files")
        alto_type = getattr(witness, "alto_source_type", "auto") if witness is not None else "auto"
        if alto_type not in {"auto", "files"}:
            alto_type = "auto"
        self.alto_source.setCurrentIndex(max(0, self.alto_source.findData(alto_type)))
        alto_mode_row.addWidget(QLabel(tr("project.witness.alto.source")))
        alto_mode_row.addWidget(self.alto_source, 1)
        ag.addLayout(alto_mode_row)
        self.alto_table = QTableWidget(0, 2)
        self.alto_table.setHorizontalHeaderLabels([
            tr("project.witness.alto.label"), tr("project.witness.alto.file")
        ])
        self.alto_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.alto_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.alto_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.alto_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        ag.addWidget(self.alto_table, 1)
        alto_buttons = QHBoxLayout()
        self.add_alto_btn = QPushButton(tr("project.witness.alto.add"))
        self.remove_alto_btn = QPushButton(tr("project.witness.alto.remove"))
        self.up_alto_btn = QPushButton("↑")
        self.down_alto_btn = QPushButton("↓")
        self.sort_alto_btn = QPushButton(tr("project.witness.sort_natural"))
        for btn in (self.add_alto_btn, self.remove_alto_btn, self.up_alto_btn, self.down_alto_btn, self.sort_alto_btn):
            alto_buttons.addWidget(btn)
        alto_buttons.addStretch(1)
        ag.addLayout(alto_buttons)
        self.copy_alto = QCheckBox(tr("project.witness.alto.copy"))
        self.copy_alto.setChecked(True)
        self.copy_alto.setToolTip(tr("project.witness.alto.copy.tip"))
        ag.addWidget(self.copy_alto)
        alto_hint = QLabel(tr("project.witness.alto.hint")); alto_hint.setWordWrap(True); ag.addWidget(alto_hint)
        root.addWidget(self.alto_group, 1)

        existing_alto = list(getattr(witness, "alto_files", ()) or ())
        for alto in existing_alto:
            self._append_alto(Path(alto.path), getattr(alto, "label", "") or Path(alto.path).stem)
        if witness is not None and alto_type == "files" and self.project_root is not None:
            existing = [Path(x.path).resolve() for x in existing_alto]
            self.copy_alto.setChecked(bool(existing) and all(self._is_inside_project(x) for x in existing))
        self.add_alto_btn.clicked.connect(self._add_alto)
        self.remove_alto_btn.clicked.connect(self._remove_alto)
        self.up_alto_btn.clicked.connect(lambda: self._move_alto(-1))
        self.down_alto_btn.clicked.connect(lambda: self._move_alto(1))
        self.sort_alto_btn.clicked.connect(lambda: self._sort_table(self.alto_table, 1))
        self.alto_source.currentIndexChanged.connect(self._alto_source_changed)
        self._alto_source_changed()

        existing_images = list(getattr(witness, "image_files", ()) or ())
        if not existing_images and witness is not None and image_type == "files":
            folder = getattr(witness, "image_source_value", None)
            if folder and Path(folder).is_dir():
                allowed = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp"}
                existing_images = [LocalImageDraft(x, x.stem) for x in sorted(Path(folder).iterdir(), key=lambda p: natural_key(p.name)) if x.is_file() and x.suffix.lower() in allowed]
        for image in existing_images:
            self._append_local_image(
                Path(image.path), getattr(image, "label", "") or Path(image.path).stem,
                getattr(image, "width", None), getattr(image, "height", None),
                getattr(image, "surface_id", ""),
            )
        if witness is not None and image_type == "files" and self.project_root is not None:
            existing = [Path(x.path).resolve() for x in getattr(witness, "image_files", ()) or ()]
            # Les images déjà dans le projet sont naturellement conservées sur place.
            if existing and all(self._is_inside_project(x) for x in existing):
                self.copy_images.setChecked(True)
            else:
                self.copy_images.setChecked(False)

        self.add_images_btn.clicked.connect(self._add_images)
        self.remove_image_btn.clicked.connect(self._remove_image)
        self.up_image_btn.clicked.connect(lambda: self._move_image(-1))
        self.down_image_btn.clicked.connect(lambda: self._move_image(1))
        self.sort_image_btn.clicked.connect(lambda: self._sort_table(self.local_table, 2))
        self.image_source.currentIndexChanged.connect(self._image_source_changed)
        self._image_source_changed()

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _is_inside_project(self, path):
        if self.project_root is None:
            return False
        try:
            Path(path).resolve().relative_to(self.project_root)
            return True
        except ValueError:
            return False

    def _append_local_image(self, path, label=None, width=None, height=None, surface_id=""):
        path = Path(path).expanduser().resolve()
        row = self.local_table.rowCount(); self.local_table.insertRow(row)
        label_item = QTableWidgetItem(label or path.stem)
        # L'identifiant est stable : une fois enregistré dans project.xml, il
        # n'est jamais recalculé à partir du foliotage ou du nom de fichier.
        sid = str(surface_id or default_surface_id(self.id_edit.text().strip() or "W", row + 1))
        surface_item = QTableWidgetItem(sid)
        path_item = QTableWidgetItem(str(path))
        path_item.setFlags(path_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        path_item.setData(Qt.ItemDataRole.UserRole, width)
        path_item.setData(Qt.ItemDataRole.UserRole + 1, height)
        self.local_table.setItem(row, 0, label_item)
        self.local_table.setItem(row, 1, surface_item)
        self.local_table.setItem(row, 2, path_item)

    def _add_images(self):
        start = str(Path.home())
        if self.local_table.rowCount():
            start = str(Path(self.local_table.item(self.local_table.rowCount()-1, 2).text()).parent)
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("project.witness.local_images.choose"), start,
            f"{self.IMAGE_FILTER};;{self.tr('common.all_files')} (*)"
        )
        existing = {self.local_table.item(r, 2).text() for r in range(self.local_table.rowCount())}
        for fn in sorted(files, key=natural_key):
            path = str(Path(fn).expanduser().resolve())
            if path not in existing:
                self._append_local_image(path)
                existing.add(path)

    def _remove_image(self):
        row = self.local_table.currentRow()
        if row >= 0:
            self.local_table.removeRow(row)

    def _move_image(self, delta):
        row = self.local_table.currentRow()
        dest = row + delta
        if row < 0 or dest < 0 or dest >= self.local_table.rowCount():
            return
        values = []
        for c in range(3):
            item = self.local_table.takeItem(row, c)
            values.append(item)
        self.local_table.removeRow(row)
        self.local_table.insertRow(dest)
        for c, item in enumerate(values):
            self.local_table.setItem(dest, c, item)
        self.local_table.selectRow(dest)

    def _sort_table(self, table, path_column):
        # Moving complete item objects retains surface IDs and metadata.
        rows = [[table.takeItem(r, c) for c in range(table.columnCount())]
                for r in range(table.rowCount())]
        rows.sort(key=lambda cells: natural_key(cells[path_column].text()))
        for r, cells in enumerate(rows):
            for c, cell in enumerate(cells):
                table.setItem(r, c, cell)

    def _append_alto(self, path, label=None):
        path = Path(path).expanduser().resolve()
        row = self.alto_table.rowCount(); self.alto_table.insertRow(row)
        self.alto_table.setItem(row, 0, QTableWidgetItem(label or path.stem))
        item = QTableWidgetItem(str(path)); item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
        self.alto_table.setItem(row, 1, item)

    def _add_alto(self):
        start = str(Path.home())
        if self.alto_table.rowCount():
            start = str(Path(self.alto_table.item(self.alto_table.rowCount()-1, 1).text()).parent)
        files, _ = QFileDialog.getOpenFileNames(
            self, self.tr("project.witness.alto.choose"), start,
            f"ALTO / PAGE XML (*.xml *.alto *.page);;{self.tr('common.all_files')} (*)"
        )
        existing = {self.alto_table.item(r, 1).text() for r in range(self.alto_table.rowCount())}
        for fn in sorted(files, key=natural_key):
            path = str(Path(fn).expanduser().resolve())
            if path not in existing:
                self._append_alto(path)
                existing.add(path)

    def _remove_alto(self):
        row = self.alto_table.currentRow()
        if row >= 0:
            self.alto_table.removeRow(row)

    def _move_alto(self, delta):
        row = self.alto_table.currentRow(); dest = row + delta
        if row < 0 or dest < 0 or dest >= self.alto_table.rowCount():
            return
        values = [self.alto_table.takeItem(row, c) for c in range(2)]
        self.alto_table.removeRow(row); self.alto_table.insertRow(dest)
        for c, item in enumerate(values): self.alto_table.setItem(dest, c, item)
        self.alto_table.selectRow(dest)

    def _alto_source_changed(self, *_):
        enabled = self.alto_source.currentData() == "files"
        for widget in (self.alto_table, self.add_alto_btn, self.remove_alto_btn, self.up_alto_btn, self.down_alto_btn, self.sort_alto_btn, self.copy_alto):
            widget.setEnabled(enabled)

    def _alto_files(self):
        out = []
        for r in range(self.alto_table.rowCount()):
            pitem = self.alto_table.item(r, 1)
            out.append(AltoFileDraft(
                Path(pitem.text()).expanduser().resolve(),
                self.alto_table.item(r, 0).text().strip() or Path(pitem.text()).stem,
            ))
        return out

    def _manifest_source_changed(self, source):
        if source.strip() != self._iiif_manifest_loaded_source:
            # Cached raw JSON belongs to its original URL; never silently
            # attach an old manuscript manifest to a newly typed IIIF URL.
            self._iiif_manifest_data = None

    def _load_iiif_manifest(self):
        source = self.iiif_manifest.text().strip()
        if not source:
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.iiif_manifest_required"))
            return
        try:
            raw = fetch_manifest(source)
            parsed = parse_manifest(raw, source)
        except Exception as exc:
            QMessageBox.warning(self, self.tr("project.witness.iiif.error.title"), str(exc))
            return
        self._iiif_manifest_data = raw
        self._iiif_manifest_loaded_source = source
        self.iiif_status.setText(self.tr("project.witness.iiif.loaded", count=len(parsed.pages), version=parsed.presentation_version))

    def _pick_iiif_canvases(self):
        source = self.iiif_manifest.text().strip()
        if not source:
            QMessageBox.warning(self, self.tr('project.validation.title'), self.tr('project.validation.iiif_manifest_required'))
            return
        try:
            if self._iiif_manifest_data is not None:
                manifest = parse_manifest(self._iiif_manifest_data, source)
            else:
                from iiif_manifest import read_cache, cache_path
                wid = self.id_edit.text().strip()
                manifest = (read_cache(cache_path(self.project_root, wid), source)
                            if self.project_root and wid else None)
                if manifest is None:
                    self._load_iiif_manifest()
                    if self._iiif_manifest_data is None:
                        return
                    manifest = parse_manifest(self._iiif_manifest_data, source)
        except Exception as exc:
            QMessageBox.warning(self, self.tr('project.witness.iiif.error.title'), str(exc))
            return
        # A new selection starts empty: users with 500 folios rarely want 500.
        sync_pages = []
        sync_path = self.alignment.text().strip()
        if sync_path:
            try:
                import json
                with open(Path(sync_path).expanduser(), encoding='utf-8') as stream:
                    raw_sync = json.load(stream)
                sync_pages = list(raw_sync.get('pages') or ())
            except (OSError, ValueError, AttributeError) as exc:
                QMessageBox.warning(self, self.tr('project.validation.title'), str(exc))
                return
        dlg = IIIFCanvasPicker(self.tr, manifest, self._alto_files(),
                 self._iiif_selected_canvases, self._iiif_ocr_links, self,
                 sync_pages=sync_pages, page_links=self._iiif_page_links,
                 project_root=self.project_root, witness_id=self.id_edit.text().strip(),
                 use_local=self.iiif_local_copy.isChecked())
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._iiif_selected_canvases, self._iiif_ocr_links = dlg.selection()
            self._iiif_page_links = dlg.sync_selection()
            self.iiif_selection_mode.setCurrentIndex(self.iiif_selection_mode.findData('selected'))
            self.iiif_status.setText(self.tr('iiif.picker.count',
                selected=len(self._iiif_selected_canvases), total=len(manifest.pages)))

    def _image_source_changed(self, *_):
        kind = self.image_source.currentData()
        self.local_group.setVisible(kind == "files")
        self.iiif_group.setVisible(kind == "iiif")

    def _accept(self):
        wid = self.id_edit.text().strip()
        if not wid or any(c.isspace() for c in wid) or wid.startswith("#"):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.witness_id"))
            return
        raw = self.alignment.text().strip()
        if raw:
            path = Path(raw).expanduser()
            if not path.is_file():
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.alignment_missing", path=path))
                return
        if self.image_source.currentData() == "iiif" and not self.iiif_manifest.text().strip():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.iiif_manifest_required"))
            return
        if self.image_source.currentData() == 'iiif' and self.iiif_selection_mode.currentData() == 'selected':
            source = self.iiif_manifest.text().strip()
            try:
                if self._iiif_manifest_data is not None:
                    current_manifest = parse_manifest(self._iiif_manifest_data, source)
                else:
                    from iiif_manifest import cache_path, read_cache
                    current_manifest = (read_cache(cache_path(self.project_root, wid), source)
                                        if self.project_root else None)
                if current_manifest is None:
                    raise ValueError(self.tr('iiif.picker.validate_reload'))
                from iiif_page_selection import selected_manifest_pages
                selected_manifest_pages(current_manifest, self._iiif_selected_canvases, 'selected')
                selected_keys = set(self._iiif_selected_canvases)
                if any(canvas not in selected_keys for _, canvas in self._iiif_page_links):
                    raise ValueError(self.tr('iiif.picker.sync.bad_canvas'))
                if self._iiif_page_links:
                    from iiif_resolution import resolve_pages
                    import json
                    sync_path = self.alignment.text().strip()
                    if not sync_path:
                        raise ValueError(self.tr('iiif.picker.sync.no_json'))
                    with open(Path(sync_path).expanduser(), encoding='utf-8') as stream:
                        sync_cache = json.load(stream)
                    resolve_pages(sync_cache.get('pages') or [], current_manifest,
                                  selected_keys, self._iiif_page_links)
                valid_ocr = {str(Path(item.path).expanduser().resolve()) for item in self._alto_files()}
                if self._iiif_ocr_links and self.alto_source.currentData() != 'files':
                    raise ValueError(self.tr('iiif.picker.validate_ocr'))
                if any(str(Path(path).expanduser().resolve()) not in valid_ocr
                       for path, _ in self._iiif_ocr_links):
                    raise ValueError(self.tr('iiif.picker.validate_ocr'))
            except Exception as exc:
                QMessageBox.warning(self, self.tr('project.validation.title'), str(exc))
                return
        if self.image_source.currentData() == "files":
            if self.local_table.rowCount() == 0:
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.local_images_required"))
                return
            for r in range(self.local_table.rowCount()):
                path = Path(self.local_table.item(r, 2).text())
                if not path.is_file():
                    QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.local_image_missing", path=path))
                    return
            surface_ids = []
            for r in range(self.local_table.rowCount()):
                sid = self.local_table.item(r, 1).text().strip()
                if not valid_xml_id(sid):
                    QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.surface_id", id=sid))
                    return
                surface_ids.append(sid)
            if len(surface_ids) != len(set(surface_ids)):
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.surface_duplicate"))
                return
        if self.alto_source.currentData() == "files":
            if self.alto_table.rowCount() == 0:
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.alto_required"))
                return
            for r in range(self.alto_table.rowCount()):
                path = Path(self.alto_table.item(r, 1).text())
                if not path.is_file():
                    QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.alto_missing", path=path))
                    return
        self.accept()

    def _local_images(self):
        out = []
        for r in range(self.local_table.rowCount()):
            pitem = self.local_table.item(r, 2)
            out.append(LocalImageDraft(
                Path(pitem.text()).expanduser().resolve(),
                self.local_table.item(r, 0).text().strip() or Path(pitem.text()).stem,
                pitem.data(Qt.ItemDataRole.UserRole),
                pitem.data(Qt.ItemDataRole.UserRole + 1),
                self.local_table.item(r, 1).text().strip(),
            ))
        return out

    def witness(self):
        raw = self.alignment.text().strip()
        image_type = self.image_source.currentData() or "none"
        alignment_path = Path(raw).expanduser().resolve() if raw else None
        alignment_mode = "keep"
        if alignment_path is not None:
            same_as_original = self._original_alignment is not None and alignment_path == self._original_alignment
            copy_changed = self.copy_alignment.isChecked() != self._alignment_copy_default
            if not same_as_original or copy_changed or self._original_alignment is None:
                alignment_mode = "copy" if self.copy_alignment.isChecked() else "reference"
        return WitnessDraft(
            self.id_edit.text().strip(),
            self.label_edit.text().strip() or self.id_edit.text().strip(),
            alignment_path,
            "secondary",
            image_type,
            self.iiif_manifest.text().strip() if image_type == "iiif" else None,
            self._local_images() if image_type == "files" else [],
            ("copy" if self.copy_images.isChecked() else "reference") if image_type == "files" else "keep",
            self._iiif_manifest_data if image_type == "iiif" else None,
            self.alto_source.currentData() or "auto",
            self._alto_files() if self.alto_source.currentData() == "files" else [],
            ("copy" if self.copy_alto.isChecked() else "reference") if self.alto_source.currentData() == "files" else "keep",
            alignment_mode,
            self.iiif_local_copy.isChecked() if image_type == 'iiif' else False,
            self.iiif_web_local_copy.isChecked() if image_type == 'iiif' else False,
            self.iiif_download_scope.currentData() if image_type == 'iiif' else 'all',
            self.iiif_selection_mode.currentData() if image_type == 'iiif' else 'all',
            list(self._iiif_selected_canvases) if image_type == 'iiif' else [],
            list(self._iiif_ocr_links) if image_type == 'iiif' else [],
            list(self._iiif_page_links) if image_type == 'iiif' else [],
        )


class WitnessTable(QWidget):
    def __init__(self, tr, witnesses=None, base_witness="", parent=None, project_root=None):
        super().__init__(parent)
        self.tr = tr
        self.project_root = Path(project_root).resolve() if project_root else None
        lay = QVBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.table = QTableWidget(0, 6)
        self.table.setHorizontalHeaderLabels([
            tr("project.witness.id"), tr("project.witness.label"),
            tr("project.witness.role"), tr("project.witness.images"),
            tr("project.witness.alto.column"), tr("project.witness.alignment"),
        ])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(5, QHeaderView.ResizeMode.Stretch)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        lay.addWidget(self.table)
        row = QHBoxLayout()
        self.add_btn = QPushButton(tr("project.witness.add"))
        self.edit_btn = QPushButton(tr("project.witness.edit"))
        self.remove_btn = QPushButton(tr("project.witness.remove"))
        self.base_btn = QPushButton(tr("project.witness.set_base"))
        self.base_btn.setToolTip(tr("project.witness.pivot_tip"))
        row.addWidget(self.add_btn); row.addWidget(self.edit_btn); row.addWidget(self.remove_btn); row.addWidget(self.base_btn); row.addStretch(1)
        lay.addLayout(row)
        self.add_btn.clicked.connect(self.add_witness)
        self.edit_btn.clicked.connect(self.edit_witness)
        self.remove_btn.clicked.connect(self.remove_witness)
        self.base_btn.clicked.connect(self.set_base)
        self.table.doubleClicked.connect(lambda *_: self.edit_witness())
        for w in witnesses or []:
            self._append(w, w.id == base_witness or getattr(w, "role", "") == "base")

    def _image_source_label(self, image_type, count=0):
        if image_type == "files":
            return self.tr("project.witness.images.files.count", count=count)
        if image_type == "iiif":
            return self.tr("project.witness.images.iiif")
        return self.tr("project.witness.images.auto" if image_type == "auto" else "project.witness.images.none")

    def _alto_source_label(self, alto_type, count=0):
        if alto_type == "files":
            return self.tr("project.witness.alto.files.count", count=count)
        return self.tr("project.witness.alto.auto.short")

    def _append(self, w, is_base=False):
        r = self.table.rowCount(); self.table.insertRow(r)
        image_type = getattr(w, "image_source_type", "auto") or "auto"
        if image_type not in {"auto", "none", "files", "iiif"}:
            image_type = "auto"
        image_files = list(getattr(w, "image_files", ()) or ())
        alto_type = getattr(w, "alto_source_type", "auto") or "auto"
        alto_files = list(getattr(w, "alto_files", ()) or ())
        vals = [
            w.id, w.label,
            self.tr("project.witness.base") if is_base else self.tr("project.witness.secondary"),
            self._image_source_label(image_type, len(image_files)),
            self._alto_source_label(alto_type, len(alto_files)),
            str(w.alignment) if w.alignment else self.tr("common.none"),
        ]
        for c, value in enumerate(vals):
            item = QTableWidgetItem(value)
            item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(r, c, item)
        self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, bool(is_base))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole, image_type)
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 1, image_files)
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 2, getattr(w, "image_import_mode", "keep"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 3, getattr(w, "image_source_value", None))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 4, getattr(w, "iiif_manifest_data", None))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 5, getattr(w, "alto_source_type", "auto"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 6, list(getattr(w, "alto_files", ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 7, getattr(w, "alto_import_mode", "keep"))
        self.table.item(r, 5).setData(Qt.ItemDataRole.UserRole, getattr(w, "alignment_import_mode", "keep"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 8, getattr(w, 'iiif_local_copy', False))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 9, getattr(w, 'iiif_web_local_copy', False))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 10, getattr(w, 'iiif_download_scope', 'all'))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 11, getattr(w, 'iiif_selection_mode', 'all'))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 12, list(getattr(w, 'iiif_selected_canvases', ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 13, list(getattr(w, 'iiif_ocr_links', ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 14, list(getattr(w, 'iiif_page_links', ()) or ()))

    def add_witness(self):
        dlg = WitnessEditDialog(self.tr, parent=self, project_root=self.project_root)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            w = dlg.witness()
            if w.id in {x.id for x in self.witnesses()}:
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.duplicate_witness", id=w.id))
                return
            self._append(w, self.table.rowCount() == 0)

    def edit_witness(self):
        r = self.table.currentRow()
        if r < 0: return
        old = self.witness_at(r)
        dlg = WitnessEditDialog(self.tr, old, self, project_root=self.project_root)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        new = dlg.witness()
        existing = {self.table.item(i, 0).text() for i in range(self.table.rowCount()) if i != r}
        if new.id in existing:
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.duplicate_witness", id=new.id))
            return
        is_base = bool(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))
        self.table.item(r, 0).setText(new.id); self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, is_base)
        self.table.item(r, 1).setText(new.label)
        image_type = getattr(new, "image_source_type", "none") or "none"
        images = list(getattr(new, "image_files", []) or [])
        self.table.item(r, 3).setText(self._image_source_label(image_type, len(images)))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole, image_type)
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 1, images)
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 2, getattr(new, "image_import_mode", "keep"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 3, getattr(new, "image_source_value", None))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 4, getattr(new, "iiif_manifest_data", None))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 5, getattr(new, "alto_source_type", "auto"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 6, list(getattr(new, "alto_files", ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 7, getattr(new, "alto_import_mode", "keep"))
        alto_type = getattr(new, "alto_source_type", "auto") or "auto"
        alto_files = list(getattr(new, "alto_files", ()) or ())
        self.table.item(r, 4).setText(self._alto_source_label(alto_type, len(alto_files)))
        self.table.item(r, 5).setText(str(new.alignment) if new.alignment else self.tr("common.none"))
        self.table.item(r, 5).setData(Qt.ItemDataRole.UserRole, getattr(new, "alignment_import_mode", "keep"))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 8, getattr(new, 'iiif_local_copy', False))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 9, getattr(new, 'iiif_web_local_copy', False))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 10, getattr(new, 'iiif_download_scope', 'all'))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 11, getattr(new, 'iiif_selection_mode', 'all'))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 12, list(getattr(new, 'iiif_selected_canvases', ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 13, list(getattr(new, 'iiif_ocr_links', ()) or ()))
        self.table.item(r, 3).setData(Qt.ItemDataRole.UserRole + 14, list(getattr(new, 'iiif_page_links', ()) or ()))

    def remove_witness(self):
        r = self.table.currentRow()
        if r < 0: return
        was_base = bool(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))
        self.table.removeRow(r)
        if was_base and self.table.rowCount():
            self._mark_base(0)

    def set_base(self):
        r = self.table.currentRow()
        if r >= 0: self._mark_base(r)

    def _mark_base(self, base_row):
        for r in range(self.table.rowCount()):
            is_base = r == base_row
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, is_base)
            self.table.item(r, 2).setText(self.tr("project.witness.base") if is_base else self.tr("project.witness.secondary"))

    def witness_at(self, r):
        raw_alignment = self.table.item(r, 5).text().strip()
        alignment = None if raw_alignment in {"", self.tr("common.none")} else Path(raw_alignment)
        image_type = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole) or "auto"
        raw_images = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 1) or []
        images = [LocalImageDraft(Path(x.path), getattr(x, "label", ""), getattr(x, "width", None), getattr(x, "height", None), getattr(x, "surface_id", "")) for x in raw_images]
        import_mode = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 2) or "keep"
        image_value = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 3)
        manifest_data = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 4)
        alto_type = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 5) or "auto"
        raw_alto = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 6) or []
        alto_files = [AltoFileDraft(Path(x.path), getattr(x, "label", "")) for x in raw_alto]
        alto_mode = self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 7) or "keep"
        alignment_mode = self.table.item(r, 5).data(Qt.ItemDataRole.UserRole) or "keep"
        return WitnessDraft(
            self.table.item(r, 0).text(), self.table.item(r, 1).text(),
            alignment,
            "base" if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole) else "secondary",
            image_type, image_value, images, import_mode, manifest_data,
            alto_type, alto_files, alto_mode, alignment_mode,
            bool(self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 8)),
            bool(self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 9)),
            self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 10) or 'all',
            self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 11) or 'all',
            self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 12) or [],
            self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 13) or [],
            self.table.item(r, 3).data(Qt.ItemDataRole.UserRole + 14) or [],
        )

    def witnesses(self):
        return [self.witness_at(r) for r in range(self.table.rowCount())]

    def base_witness(self):
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole):
                return self.table.item(r, 0).text()
        return ""


def run_pivot_scaffold_dialog(tr, parent, witnesses, base_witness, project_root,
                              edition_path, *, include_lb=True):
    """Preview and explicitly authorize the only permitted blank-TEI mutation."""
    from tei_pivot_scaffold import (build_pivot_plan, scaffold_is_empty,
                                   write_pivot_scaffold)
    try:
        source = Path(edition_path).read_text(encoding='utf-8-sig')
        if not scaffold_is_empty(source):
            QMessageBox.warning(parent, tr('pivot.title'), tr('pivot.not_empty'))
            return False
        plan = build_pivot_plan(witnesses, base_witness, project_root, edition_path)
        if not plan.pages:
            QMessageBox.warning(parent, tr('pivot.title'), tr('pivot.no_pages'))
            return False
    except Exception as exc:
        QMessageBox.warning(parent, tr('pivot.title'), str(exc))
        return False
    message = QMessageBox(parent)
    message.setWindowTitle(tr('pivot.preview.title'))
    message.setIcon(QMessageBox.Icon.Question)
    message.setText(tr('pivot.preview.summary', witness=plan.witness_id,
                       pages=len(plan.pages), lines=plan.line_count if include_lb else 0))
    overview = '\n'.join(f'{x.label} → #{x.surface_id} : {x.line_count if include_lb else 0} lb ({x.evidence})'
                         for x in plan.pages)
    if plan.warnings:
        overview += '\n\n' + tr('pivot.preview.warnings') + '\n' + '\n'.join(plan.warnings)
    message.setDetailedText(overview)
    message.setInformativeText(tr('pivot.preview.confirm'))
    message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    message.setDefaultButton(QMessageBox.StandardButton.No)
    if message.exec() != QMessageBox.StandardButton.Yes:
        return False
    try:
        backup = write_pivot_scaffold(edition_path, plan, include_lb=include_lb)
    except Exception as exc:
        QMessageBox.critical(parent, tr('pivot.title'), str(exc))
        return False
    QMessageBox.information(parent, tr('pivot.title'),
                            tr('pivot.done', backup=backup or ''))
    return True


class NewProjectDialog(QDialog):
    def __init__(self, tr, languages, parent=None):
        super().__init__(parent)
        self.tr = tr
        # The version in the title helps identify a stale Spyder/module session.
        self.setWindowTitle(f'{tr("project.new.title")} — Varians 0.8.5.10')
        self.resize(950, 690)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        form = QFormLayout()
        self.folder = PathRow("", self, "dir", tr("project.new.folder.choose"))
        self.title_edit = QLineEdit()
        self.creation_mode = QComboBox()
        self.creation_mode.addItem(tr("project.new.mode.existing"), "existing")
        self.creation_mode.addItem(tr("project.new.mode.blank"), "blank")
        self.creation_mode.currentIndexChanged.connect(self._creation_mode_changed)
        # Keep the TEI preparation choices next to "Starting point", not below
        # the large, resizable witnesses table where they can be clipped.
        self.pivot_section = QGroupBox(tr('pivot.title'))
        pivot_box = QVBoxLayout(self.pivot_section)
        self.pivot_prepare = QCheckBox(tr('pivot.option.pb'))
        self.pivot_lines = QCheckBox(tr('pivot.option.lb'))
        self.pivot_lines.setChecked(True)
        self.pivot_prepare.toggled.connect(self.pivot_lines.setEnabled)
        self.pivot_prepare.toggled.connect(self._pivot_enabled)
        self.pivot_prepare.setChecked(False)
        self.pivot_lines.setEnabled(False)
        pivot_box.addWidget(self.pivot_prepare)
        pivot_box.addWidget(self.pivot_lines)
        self.edition = PathRow("", self, "file", tr("project.edition.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_mode = QComboBox()
        self.schema_mode.addItem(tr("project.schema.mode.auto"), "auto")
        self.schema_mode.addItem(tr("project.schema.mode.file"), "file")
        self.schema_mode.addItem(tr("project.schema.mode.none"), "none")
        self.schema = PathRow("", self, "file", tr("project.schema.choose"), f"RELAX NG (*.rng);;XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_hint = QLabel(tr("project.schema.hint.auto")); self.schema_hint.setWordWrap(True)
        self.schema_mode.currentIndexChanged.connect(self._schema_mode_changed)
        self.language = QComboBox()
        for code, label in languages: self.language.addItem(label, code)
        self.xslt_mode = QComboBox()
        self.xslt_mode.addItem(tr("project.xslt.mode.builtin"), "builtin")
        self.xslt_mode.addItem(tr("project.xslt.mode.file"), "file")
        form.addRow(tr("project.new.folder"), self.folder)
        form.addRow(tr("project.title"), self.title_edit)
        form.addRow(tr("project.new.mode"), self.creation_mode)
        form.addRow('', self.pivot_section)
        form.addRow(tr("project.edition"), self.edition)
        form.addRow(tr("project.schema.mode"), self.schema_mode)
        form.addRow(tr("project.schema.file"), self.schema)
        form.addRow("", self.schema_hint)
        form.addRow(tr("common.language"), self.language)
        form.addRow(tr("project.xslt.mode"), self.xslt_mode)
        self._schema_mode_changed()
        self._creation_mode_changed()
        root.addLayout(form)
        group = QGroupBox(tr("project.witnesses")); gl = QVBoxLayout(group)
        self.witnesses_table = WitnessTable(tr, parent=self); gl.addWidget(self.witnesses_table)
        root.addWidget(group, 1)
        self.info = QLabel(tr("project.new.info")); self.info.setWordWrap(True); root.addWidget(self.info)
        self._creation_mode_changed()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); outer.addWidget(buttons)

    def _accept(self):
        folder = Path(self.folder.text()).expanduser()
        edition = Path(self.edition.text()).expanduser() if self.edition.text() else None
        witnesses = self.witnesses_table.witnesses()
        if not self.folder.text():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.folder_required")); return
        if folder.exists() and any(folder.iterdir()):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.folder_not_empty")); return
        if self.creation_mode.currentData() == "existing" and (edition is None or not edition.is_file()):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.edition_missing", path=edition or "")); return
        if self.schema_mode.currentData() == "file" and not Path(self.schema.text()).expanduser().is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.schema_missing", path=self.schema.text())); return
        if not witnesses:
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_witness")); return
        if not self.witnesses_table.base_witness():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_base")); return
        self.accept()

    def _creation_mode_changed(self, *_):
        mode = self.creation_mode.currentData() or "existing"
        self.edition.setEnabled(mode == "existing")
        if hasattr(self, 'pivot_prepare'):
            self.pivot_prepare.setEnabled(mode == 'blank')
            self.pivot_lines.setEnabled(mode == 'blank' and self.pivot_prepare.isChecked())
        if hasattr(self, "info"):
            self.info.setText(self.tr("project.new.info.blank" if mode == "blank" else "project.new.info"))

    def _pivot_enabled(self, *_):
        self.pivot_lines.setEnabled(self.pivot_prepare.isChecked() and
                                    self.creation_mode.currentData() == 'blank')

    def _schema_mode_changed(self, *_):
        mode = self.schema_mode.currentData() or "auto"
        self.schema.setEnabled(mode == "file")
        self.schema_hint.setText(self.tr(f"project.schema.hint.{mode}"))

    def values(self):
        return {
            "target_dir": Path(self.folder.text()).expanduser().resolve(),
            "title": self.title_edit.text().strip() or Path(self.folder.text()).name,
            "creation_mode": self.creation_mode.currentData() or "existing",
            "edition": (Path(self.edition.text()).expanduser().resolve()
                        if self.creation_mode.currentData() == "existing" and self.edition.text() else None),
            "schema_mode": self.schema_mode.currentData() or "auto",
            "schema": Path(self.schema.text()).expanduser().resolve() if self.schema_mode.currentData() == "file" and self.schema.text() else None,
            "language": self.language.currentData() or "fr",
            "xslt_mode": self.xslt_mode.currentData() or "builtin",
            "witnesses": self.witnesses_table.witnesses(),
            "base_witness": self.witnesses_table.base_witness(),
            "prepare_pivot": self.pivot_prepare.isChecked() and self.creation_mode.currentData() == 'blank',
            "pivot_lines": self.pivot_lines.isChecked(),
        }


class ProjectSettingsDialog(QDialog):
    def __init__(self, tr, project, languages, parent=None):
        super().__init__(parent)
        self.tr = tr; self.project = project
        self.setWindowTitle(f'{tr("project.settings.title")} — Varians 0.8.5.10')
        self.resize(980, 740)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        form = QFormLayout()
        self.title_edit = QLineEdit(project.title)
        self.edition = PathRow(project.edition, self, "file", tr("project.edition.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_mode = QComboBox()
        self.schema_mode.addItem(tr("project.schema.mode.auto"), "auto")
        self.schema_mode.addItem(tr("project.schema.mode.file"), "file")
        self.schema_mode.addItem(tr("project.schema.mode.none"), "none")
        sm_idx = self.schema_mode.findData(getattr(project, "schema_mode", "auto"))
        self.schema_mode.setCurrentIndex(max(0, sm_idx))
        self.schema = PathRow(project.schema or "", self, "file", tr("project.schema.choose"), f"RELAX NG (*.rng);;XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_hint = QLabel(tr("project.schema.hint.auto")); self.schema_hint.setWordWrap(True)
        self.schema_mode.currentIndexChanged.connect(self._schema_mode_changed)
        self.language = QComboBox()
        for code, label in languages: self.language.addItem(label, code)
        idx = self.language.findData(project.language)
        if idx >= 0: self.language.setCurrentIndex(idx)
        self.xslt_mode = QComboBox()
        self.xslt_mode.addItem(tr("project.xslt.mode.builtin"), "builtin")
        self.xslt_mode.addItem(tr("project.xslt.mode.file"), "file")
        idx = self.xslt_mode.findData(project.xslt_mode)
        self.xslt_mode.setCurrentIndex(max(0, idx))
        suggested_custom_xslt = (project.root_dir / "rendering" / "tei-to-html.xsl")
        self.xslt = PathRow(
            project.xslt if project.xslt_mode == "file" else suggested_custom_xslt,
            self, "file", tr("project.xslt.choose"),
            f"XSLT (*.xsl *.xslt);;{tr('common.all_files')} (*)")
        self.xslt_hint = QLabel(tr("project.xslt.hint.builtin"))
        self.xslt_hint.setWordWrap(True)
        self.xslt_mode.currentIndexChanged.connect(self._xslt_mode_changed)
        self.css = PathRow(project.css, self, "file", tr("project.css.choose"), f"CSS (*.css);;{tr('common.all_files')} (*)")
        self.custom = PathRow(project.custom_elements, self, "file", tr("project.custom.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.translations = PathRow(project.translations_dir, self, "dir", tr("project.i18n.choose"))
        self.web_output = PathRow(project.web_output_dir, self, "dir", tr("project.web_output.choose"))
        self.web_filename = QLineEdit(project.web_filename)
        for label, widget in [
            (tr("project.title"), self.title_edit), (tr("project.edition"), self.edition),
            (tr("project.schema.mode"), self.schema_mode),
            (tr("project.schema.file"), self.schema),
            ("", self.schema_hint),
            (tr("common.language"), self.language),
            (tr("project.xslt.mode"), self.xslt_mode),
            (tr("project.xslt"), self.xslt),
            ("", self.xslt_hint),
            (tr("project.css"), self.css), (tr("project.custom"), self.custom),
            (tr("project.i18n"), self.translations), (tr("project.web_output"), self.web_output),
            (tr("project.web_filename"), self.web_filename),
        ]: form.addRow(label, widget)
        self._schema_mode_changed()
        self._xslt_mode_changed()
        root.addLayout(form)
        self.pivot_section = QGroupBox(tr('pivot.title'))
        pivot_box = QVBoxLayout(self.pivot_section)
        self.pivot_prepare = QCheckBox(tr('pivot.option.pb'))
        self.pivot_lines = QCheckBox(tr('pivot.option.lb'))
        self.pivot_lines.setChecked(True)
        self.pivot_lines.setEnabled(False)
        self.pivot_prepare.toggled.connect(self.pivot_lines.setEnabled)
        pivot_box.addWidget(self.pivot_prepare)
        pivot_box.addWidget(self.pivot_lines)
        root.addWidget(self.pivot_section)
        group = QGroupBox(tr("project.witnesses")); gl = QVBoxLayout(group)
        self.witnesses_table = WitnessTable(tr, project.witnesses, project.base_witness, self, project_root=project.root_dir); gl.addWidget(self.witnesses_table)
        root.addWidget(group, 1)
        # Refresh is an explicit manager action; saving settings never refetches
        # existing IIIF images without a deliberate user request.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); outer.addWidget(buttons)

    def _schema_mode_changed(self, *_):
        mode = self.schema_mode.currentData() or "auto"
        self.schema.setEnabled(mode == "file")
        self.schema_hint.setText(self.tr(f"project.schema.hint.{mode}"))

    def _xslt_mode_changed(self, *_):
        mode = self.xslt_mode.currentData() or "builtin"
        self.xslt.setEnabled(mode == "file")
        self.xslt_hint.setText(self.tr("project.xslt.hint.file" if mode == "file" else "project.xslt.hint.builtin"))

    def _accept(self):
        edition = Path(self.edition.text()).expanduser()
        witnesses = self.witnesses_table.witnesses()
        if not edition.is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.edition_missing", path=edition)); return
        if self.schema.text() and not Path(self.schema.text()).expanduser().is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.schema_missing", path=self.schema.text())); return
        if not witnesses:
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_witness")); return
        if not self.witnesses_table.base_witness():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_base")); return
        for w in witnesses:
            if w.alignment is not None and not Path(w.alignment).is_file():
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.alignment_missing", path=w.alignment)); return
        required = [self.css.text(), self.custom.text()]
        if any(not Path(x).expanduser().is_file() for x in required):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.rendering_missing")); return
        if self.xslt_mode.currentData() == "file":
            chosen_xslt = Path(self.xslt.text()).expanduser().resolve()
            expected_xslt = self.project.root_dir / "rendering" / "tei-to-html.xsl"
            if not chosen_xslt.is_file() and chosen_xslt != expected_xslt:
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.xslt_missing", path=chosen_xslt)); return
        if not Path(self.translations.text()).expanduser().is_dir():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.i18n_missing")); return
        self.accept()

    def draft(self):
        return ProjectDraft(
            title=self.title_edit.text().strip() or self.project.path.parent.name,
            edition=Path(self.edition.text()).expanduser().resolve(),
            schema_mode=self.schema_mode.currentData() or "auto",
            schema=Path(self.schema.text()).expanduser().resolve() if self.schema_mode.currentData() == "file" and self.schema.text() else None,
            schema_type="relaxng",
            language=self.language.currentData() or self.project.language,
            fallback_language=self.project.fallback_language,
            translations_dir=Path(self.translations.text()).expanduser().resolve(),
            xslt=Path(self.xslt.text()).expanduser().resolve(),
            xslt_mode=self.xslt_mode.currentData() or "builtin",
            css=Path(self.css.text()).expanduser().resolve(),
            custom_elements=Path(self.custom.text()).expanduser().resolve(),
            web_output_dir=Path(self.web_output.text()).expanduser().resolve(),
            web_filename=self.web_filename.text().strip() or "viewer.html",
            witnesses=self.witnesses_table.witnesses(),
            base_witness=self.witnesses_table.base_witness(),
            # Non modifiables ici : conservés tels quels, sinon la réécriture
            # de project.xml les effacerait.
            documents=list(self.project.documents),
            xpath_queries=list(self.project.xpath_queries),
            parts=list(self.project.parts),
        )
