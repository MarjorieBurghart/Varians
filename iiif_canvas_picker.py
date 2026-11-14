# -*- coding: utf-8 -*-
"""Choix des pages d'un Manifest IIIF (V0.9.4.7, extrait de project_dialogs) :
``IIIFCanvasPicker``, ouverte depuis la fiche d'un témoin."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QUrl, Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QComboBox, QDialog, QDialogButtonBox, QHBoxLayout, QHeaderView, QLabel,
    QLineEdit, QMessageBox, QPushButton, QTableWidget, QTableWidgetItem, QVBoxLayout,
)

from iiif_page_selection import canvas_key, propose_exact_ocr_links


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
        """``(canevas, liens)`` d'après le tableau : clés des canevas cochés dans « Inclure », dans
        l'ordre du manifeste, et ``(fichier, clé du canevas)`` pour ceux qui ont un fichier
        « ALTO / PAGE associé »."""
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
