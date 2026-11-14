# -*- coding: utf-8 -*-
"""Fiche d'un témoin (V0.9.4.7, extrait de project_dialogs) :
``WitnessEditDialog`` (sigle, images locales ou IIIF, fichiers ALTO/PAGE,
synchronisation), ouverte depuis la table des témoins."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout,
    QGroupBox, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout,
)

from project_management import AltoFileDraft, LocalImageDraft, WitnessDraft
from iiif_manifest import fetch_manifest, parse_manifest
from tei_facsimile import default_surface_id, valid_xml_id
from witness_ids import witness_id_for_siglum
from iiif_page_selection import natural_key
from iiif_canvas_picker import IIIFCanvasPicker
from project_widgets import PathRow


class WitnessEditDialog(QDialog):
    """Boîte « Témoin du projet » : sigle, nom, source des images (fichiers locaux, ou Manifest
    IIIF et sa sélection de canevas), fichier de synchronisation JSON et fichiers ALTO/PAGE
    d'un témoin. Ouverte par « Ajouter… » et « Modifier… » du tableau des témoins ; avec
    ``siglum_locked``, le sigle n'y est pas modifiable (« Changer le sigle… »). Elle vérifie
    les fichiers à « OK » mais n'écrit rien : ``witness()`` rend le témoin décrit."""
    IMAGE_FILTER = "Images (*.jpg *.jpeg *.png *.tif *.tiff *.bmp *.webp)"

    def __init__(self, tr, witness=None, parent=None, project_root=None, siglum_locked=False):
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
        # Le champ « Sigle » reçoit le sigle tel quel (V0.9.2.8.2) ; quand il
        # n'est pas un identifiant XML, le témoin reçoit l'identifiant qui en
        # est tiré, montré sous le champ. Un sigle inchangé garde l'identifiant
        # du témoin.
        self._original_id = getattr(witness, "id", "")
        self._original_siglum = getattr(witness, "display_siglum", None) or self._original_id
        self.id_edit = QLineEdit(self._original_siglum)
        self.xml_id_hint = QLabel()
        # Témoin déjà enregistré dans le projet (V0.9.4.0) : son sigle change
        # par « Changer le sigle… » des paramètres du projet, qui met à jour
        # tout ce qui le cite ; ici, il le changerait en nouveau témoin.
        self.id_edit.setReadOnly(bool(siglum_locked))
        self.siglum_lock_hint = QLabel(tr("witness_rename.locked"))
        self.siglum_lock_hint.setWordWrap(True)
        self.siglum_lock_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.siglum_lock_hint.setVisible(bool(siglum_locked))
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
        form.addRow("", self.xml_id_hint)
        form.addRow("", self.siglum_lock_hint)
        self.id_edit.textChanged.connect(self._siglum_changed)
        self._siglum_changed()
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
        sid = str(surface_id or default_surface_id(self.witness_id() or "W", row + 1))
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
                wid = self.witness_id()
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
                 project_root=self.project_root, witness_id=self.witness_id(),
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

    def witness_id(self):
        """Identifiant XML du témoin : celui d'origine tant que le sigle n'a
        pas changé, sinon celui qui est tiré du sigle."""
        siglum = self.id_edit.text().strip()
        if self._original_id and siglum == self._original_siglum:
            return self._original_id
        return witness_id_for_siglum(siglum)

    def _siglum_changed(self, *_):
        wid = self.witness_id()
        differs = bool(wid) and wid != self.id_edit.text().strip()
        self.xml_id_hint.setText(self.tr("project.witness.xml_id", id=wid) if differs else "")
        self.xml_id_hint.setVisible(differs)

    def _accept(self):
        wid = self.witness_id()
        if not wid:
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
        """Le témoin décrit par la boîte, en ``WitnessDraft`` : identifiant (``witness_id``), sigle
        s'il en diffère, nom (le sigle par défaut), mode d'import de la synchronisation, des
        images et des fichiers ALTO/PAGE (``copy``, ``reference`` ou ``keep``). Seules les
        données du type d'images choisi sont reprises. Le rôle est toujours ``secondary`` : le
        pivot se désigne dans le tableau des témoins."""
        raw = self.alignment.text().strip()
        image_type = self.image_source.currentData() or "none"
        alignment_path = Path(raw).expanduser().resolve() if raw else None
        alignment_mode = "keep"
        if alignment_path is not None:
            same_as_original = self._original_alignment is not None and alignment_path == self._original_alignment
            copy_changed = self.copy_alignment.isChecked() != self._alignment_copy_default
            if not same_as_original or copy_changed or self._original_alignment is None:
                alignment_mode = "copy" if self.copy_alignment.isChecked() else "reference"
        wid = self.witness_id()
        siglum = self.id_edit.text().strip()
        return WitnessDraft(
            wid,
            self.label_edit.text().strip() or siglum,
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
            siglum if siglum != wid else "",
        )
