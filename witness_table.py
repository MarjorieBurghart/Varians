# -*- coding: utf-8 -*-
"""Table des témoins (V0.9.4.7, extrait de project_dialogs) : ``WitnessTable``,
dans « Nouveau projet » et « Paramètres du projet » (ajouter, modifier,
retirer, ordonner, changer le sigle d'un témoin)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QHeaderView, QMessageBox, QPushButton, QTableWidget,
    QTableWidgetItem, QVBoxLayout, QWidget,
)

from project_management import AltoFileDraft, LocalImageDraft, WitnessDraft
from witness_edit_dialog import WitnessEditDialog


class WitnessTable(QWidget):
    """Tableau des témoins des boîtes « Nouveau projet… » et « Paramètres du projet… », avec
    les boutons « Ajouter… », « Modifier… », « Supprimer », « Définir comme témoin pivot »
    et, pour un projet existant (``saved_ids``), « Changer le sigle… » (signal
    ``rename_requested``). Chaque ligne garde les données de son témoin dans les rôles Qt de
    ses cellules ; ``witnesses()`` les rend en ``WitnessDraft``."""
    # « Changer le sigle… » (V0.9.4.0) : identifiant du témoin choisi.
    rename_requested = Signal(str)
    # Un témoin ajouté ou retiré (le tableau peut être vide).
    witnesses_changed = Signal()

    def __init__(self, tr, witnesses=None, base_witness="", parent=None, project_root=None, saved_ids=None):
        super().__init__(parent)
        self.tr = tr
        self.project_root = Path(project_root).resolve() if project_root else None
        # Identifiants des témoins déjà enregistrés dans le projet ; None pour
        # un nouveau projet, où un sigle se change librement.
        self.saved_ids = None if saved_ids is None else set(saved_ids)
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
        row.addWidget(self.add_btn); row.addWidget(self.edit_btn); row.addWidget(self.remove_btn); row.addWidget(self.base_btn)
        self.rename_btn = None
        if self.saved_ids is not None:
            self.rename_btn = QPushButton(tr("witness_rename.button"))
            self.rename_btn.setToolTip(tr("witness_rename.button.tip"))
            self.rename_btn.setEnabled(False)
            self.rename_btn.clicked.connect(self._rename_clicked)
            row.addWidget(self.rename_btn)
            self.table.itemSelectionChanged.connect(self._update_rename_button)
        row.addStretch(1)
        lay.addLayout(row)
        self.add_btn.clicked.connect(self.add_witness)
        self.edit_btn.clicked.connect(self.edit_witness)
        self.remove_btn.clicked.connect(self.remove_witness)
        self.base_btn.clicked.connect(self.set_base)
        self.table.doubleClicked.connect(lambda *_: self.edit_witness())
        for w in witnesses or []:
            self._append(w, w.id == base_witness or getattr(w, "role", "") == "base")

    def _saved_witness_at(self, r):
        """Identifiant du témoin de la ligne ``r`` s'il est déjà enregistré
        dans le projet, sinon None."""
        if self.saved_ids is None or r < 0 or self.table.item(r, 0) is None:
            return None
        ident = self.table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1)
        return ident if ident in self.saved_ids else None

    def _update_rename_button(self):
        if self.rename_btn is not None:
            self.rename_btn.setEnabled(self._saved_witness_at(self.table.currentRow()) is not None)

    def _rename_clicked(self):
        ident = self._saved_witness_at(self.table.currentRow())
        if ident is not None:
            self.rename_requested.emit(ident)

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
            getattr(w, "display_siglum", w.id), w.label,
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
        self._set_identity(r, w)
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

    def _set_identity(self, r, w):
        """Colonne 0 : le sigle ; l'identifiant XML est gardé à part, et
        montré en infobulle quand il diffère du sigle (V0.9.2.8.2)."""
        item = self.table.item(r, 0)
        siglum = getattr(w, "display_siglum", w.id)
        item.setText(siglum)
        item.setData(Qt.ItemDataRole.UserRole + 1, w.id)
        item.setData(Qt.ItemDataRole.UserRole + 2, siglum if siglum != w.id else "")
        item.setToolTip(self.tr("project.witness.xml_id", id=w.id) if siglum != w.id else "")

    def _identity_conflict(self, new, skip_row=None):
        """Message si le sigle de ``new``, ou l'identifiant qui en est tiré,
        est déjà celui d'un autre témoin ; None sinon."""
        for r, other in enumerate(self.witnesses()):
            if r == skip_row:
                continue
            if other.display_siglum == new.display_siglum:
                return self.tr("project.validation.duplicate_witness", id=new.display_siglum)
            if other.id == new.id:
                return self.tr("project.validation.witness_id_collision",
                               siglum=new.display_siglum, id=new.id, other=other.display_siglum)
        return None

    def add_witness(self):
        """« Ajouter… » : ouvre la boîte d'un nouveau témoin et l'ajoute en fin de tableau ; le
        premier témoin du tableau devient le pivot. Un sigle, ou un identifiant XML, déjà pris
        par un autre témoin est refusé avec un message."""
        dlg = WitnessEditDialog(self.tr, parent=self, project_root=self.project_root)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            w = dlg.witness()
            conflict = self._identity_conflict(w)
            if conflict:
                QMessageBox.warning(self, self.tr("project.validation.title"), conflict)
                return
            self._append(w, self.table.rowCount() == 0)
            self.witnesses_changed.emit()

    def edit_witness(self):
        """« Modifier… » (ou double-clic) : ouvre la boîte du témoin de la ligne courante et reporte
        ses changements dans la ligne ; son rôle (pivot ou non) ne change pas. Le sigle d'un
        témoin déjà enregistré y est verrouillé : il change par « Changer le sigle… »."""
        r = self.table.currentRow()
        if r < 0: return
        old = self.witness_at(r)
        dlg = WitnessEditDialog(self.tr, old, self, project_root=self.project_root,
                                siglum_locked=self._saved_witness_at(r) is not None)
        if dlg.exec() != QDialog.DialogCode.Accepted: return
        new = dlg.witness()
        conflict = self._identity_conflict(new, skip_row=r)
        if conflict:
            QMessageBox.warning(self, self.tr("project.validation.title"), conflict)
            return
        is_base = bool(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))
        self._set_identity(r, new); self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, is_base)
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
        """« Supprimer » : retire du tableau le témoin de la ligne courante ; si c'était le pivot,
        le premier témoin restant le devient."""
        r = self.table.currentRow()
        if r < 0: return
        was_base = bool(self.table.item(r, 0).data(Qt.ItemDataRole.UserRole))
        self.table.removeRow(r)
        if was_base and self.table.rowCount():
            self._mark_base(0)
        self.witnesses_changed.emit()

    def set_base(self):
        """« Définir comme témoin pivot » : le témoin de la ligne courante devient le pivot, les
        autres « Secondaire »."""
        r = self.table.currentRow()
        if r >= 0: self._mark_base(r)

    def _mark_base(self, base_row):
        for r in range(self.table.rowCount()):
            is_base = r == base_row
            self.table.item(r, 0).setData(Qt.ItemDataRole.UserRole, is_base)
            self.table.item(r, 2).setText(self.tr("project.witness.base") if is_base else self.tr("project.witness.secondary"))

    def witness_at(self, r):
        """Le témoin de la ligne ``r`` en ``WitnessDraft``, reconstitué depuis les données gardées
        dans ses cellules ; son rôle est ``base`` s'il est le pivot, ``secondary`` sinon."""
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
        identity = self.table.item(r, 0)
        return WitnessDraft(
            identity.data(Qt.ItemDataRole.UserRole + 1) or identity.text(), self.table.item(r, 1).text(),
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
            identity.data(Qt.ItemDataRole.UserRole + 2) or "",
        )

    def witnesses(self):
        """Les témoins du tableau, dans son ordre (``witness_at``)."""
        return [self.witness_at(r) for r in range(self.table.rowCount())]

    def base_witness(self):
        """Identifiant XML du témoin pivot, ou chaîne vide si aucun ne l'est."""
        for r in range(self.table.rowCount()):
            if self.table.item(r, 0).data(Qt.ItemDataRole.UserRole):
                return self.table.item(r, 0).data(Qt.ItemDataRole.UserRole + 1) or self.table.item(r, 0).text()
        return ""
