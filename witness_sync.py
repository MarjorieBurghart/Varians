# -*- coding: utf-8 -*-
"""Synchronisation XML ↔ témoins, navigation par folios, partage des doubles pages et rechargement des ressources des témoins."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from collections import defaultdict

from PySide6.QtCore import (
    QObject, QPointF, QRectF, QSize, Qt, QThreadPool, QTimer, Signal, Slot,
)
from PySide6.QtGui import QColor, QImageReader, QPainter, QPen, QPixmap, QTextCursor
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QDoubleSpinBox,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMessageBox, QPushButton,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)
from app_context import call_later, tr as _t
from folio_navigation import (
    configure_surface_parts, folio_at_position, folio_marks, folios_for_witness,
    inspect_surface_part_split,
)
from iiif_local import apply_working_copy
from image_fetch import FetchWorker
from image_sources import (
    image_only_items, matched_line_center, page_image_dimensions, page_image_request as generic_image_request,
    page_image_source, page_label as image_page_label, page_navigation_items, valid_matched_indices,
)
from lacunae import lacuna_events, lacunae_at
from pivot_lines import include_spans
from tei_facsimile import (
    facsimile_ref_at_position, position_inside_xml_markup, previous_surface_labels,
    project_facsimile_pages, sync_facsimile_text, upsert_pb_at_position,
)
from witness_resource_refresh import (
    assemble_resources, changed_witnesses, diagnostic_rows, RuntimeState,
)
from witness_route import Stop, page_identity
from xml_assembly import path_key


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


class WitnessDiagnosticDialog(QDialog):
    """Read-only audit of witness resources (no OCR or TEI text is exposed)."""

    def __init__(self, rows, parent=None, scope='', notes=''):
        """``scope`` : l'édition ou le texte synchronisé à part (V0.9.1.1) ;
        ``notes`` : textes synchronisés à part et problèmes de leurs dossiers."""
        super().__init__(parent)
        self.setWindowTitle(_t('diagnostics.title'))
        self.resize(1040, 520)
        self._rows = tuple(rows)
        self._scope, self._notes = scope, notes
        root = QVBoxLayout(self)
        self.intro = QLabel(_t('diagnostics.intro'))
        self.intro.setWordWrap(True)
        root.addWidget(self.intro)
        self.scope = QLabel(scope)
        self.scope.setVisible(bool(scope))
        root.addWidget(self.scope)
        self.notes = QLabel(notes)
        self.notes.setWordWrap(True)
        self.notes.setVisible(bool(notes))
        root.addWidget(self.notes)
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
        lines = [_t('diagnostics.title')] + [text for text in (self._scope, self._notes) if text]
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


def _patch_text_document(document, old_text, new_text):
    """Remplace ``old_text`` par ``new_text`` dans ``document`` en ne
    réécrivant que la portion qui diffère, en un seul pas d'annulation.
    Renvoie le curseur, placé à la fin du texte inséré."""
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
    c = QTextCursor(document)
    c.beginEditBlock()
    c.setPosition(prefix)
    c.setPosition(old_end, QTextCursor.MoveMode.KeepAnchor)
    c.insertText(new_text[prefix:new_end])
    c.endEditBlock()
    return c


# Bandeaux des panneaux pendant une lacune (V0.9.1.3) : le témoin est en
# lacune ; le pivot est en lacune (témoins synchronisés par lignes).
LACUNA = "manuscript.lacuna"
PIVOT_LACUNA = "manuscript.lacuna.pivot"


class WitnessSyncMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _refresh_folio_navigation(self, text=None, force=False):
        if not hasattr(self, 'panels'):
            return
        # Les folios sont décrits dans le <facsimile> de l'édition, même quand
        # l'une de ses parties est affichée (V0.9.1.0).
        document = self.edition_session.text_document
        if text is None or self.document is not self.edition_session:
            text = document.toPlainText()
        revision = document.revision()
        if not force and getattr(self, '_folio_revision', None) == revision:
            return
        for wid, panel in self.panels.items():
            ids = list(panel._surface_indices)
            labels = {str(it['p']['tei_surface_id']): image_page_label(it['p'], self.project.root_dir)
                      for it in panel.items if it.get('p', {}).get('tei_surface_id')}
            panel.set_folios(folios_for_witness(text, wid, ids, labels))
        self._folio_revision = revision

    def _sync_page_panels_to_cursor(self, force=False, lacunae=None):
        """Synchronise chaque témoin avec son dernier ``pb/@edRef`` précédent.

        Depuis V0.8.3, une position de texte peut correspondre à des pages
        différentes selon le témoin. Les anciens ``pb`` sans ``@edRef`` restent
        reconnus lorsque leur ``@facs`` pointe sans ambiguïté vers une surface
        connue du panneau concerné. Un témoin en lacune (V0.9.1.3, ``lacunae``
        : ``{témoin: Lacuna}`` au curseur) garde la page de son dernier ``pb``,
        où son texte s'interrompt, avec le bandeau « Lacune ».
        """
        if not self.has_any_images:
            return
        if lacunae is None:
            lacunae = self._lacunae_at_cursor()
        for witness_id, panel in self.panels.items():
            if not panel.sync_enabled and panel.items:
                panel.set_lacuna(LACUNA if witness_id in lacunae else None)
        cursor = self.editor.textCursor()
        text = self.editor.toPlainText()
        pos = cursor.position()
        if hasattr(self, '_refresh_folio_navigation'):
            self._refresh_folio_navigation(text)
        # Édition en parties (V0.9.1.0) : le dernier pb précédent est cherché
        # dans l'ordre du document assemblé, d'une partie à l'autre.
        lines = self._pivot_lines()
        includes = include_spans(text) if lines is not None else ()
        refs = {}
        for witness_id, panel in self.panels.items():
            # V0.8.5.11 : le choix page/ligne est propre à chaque témoin.
            # Un témoin relié par base_keys doit continuer à suivre ses lignes,
            # même lorsque des pb de ce même témoin figurent dans la TEI.
            if panel.sync_enabled:
                continue
            if hasattr(panel, 'folios') and panel.folios:
                if lines is not None:
                    target = lines.page_at(self.document.path, pos, text, includes, witness_id, panel.folios)
                    # Texte synchronisé à part (V0.9.1.3) : avant le premier pb
                    # du témoin dans le texte, sa page de départ.
                    if target is None and getattr(self, "_active_segment", None) is not None:
                        target = self._text_start_folio(witness_id, panel.folios)
                else:
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

    def _edition_text(self):
        """Texte de l'édition, où se trouve le <facsimile>, même quand l'une
        de ses parties est affichée."""
        if self._edition_displayed():
            return self.editor.toPlainText()
        return self.edition_session.text_document.toPlainText()

    def _write_edition_text(self, old_text, new_text):
        """Remplace ``old_text`` par ``new_text`` dans l'édition. Quand l'une de
        ses parties est affichée (V0.9.1.0), l'édition est modifiée sans être
        affichée : son onglet porte « * », son index des <lb/> est à refaire et
        la validation de l'édition assemblée repart."""
        if self._edition_displayed():
            self._replace_editor_text_minimally(old_text, new_text)
            return
        if old_text == new_text:
            return
        edition = self.edition_session
        _patch_text_document(edition.text_document, old_text, new_text)
        edition.modified = True
        edition.lb.invalidate()
        self._refresh_document_tab(edition)
        self._assembly_changed()
        self.document.invalidate_rng()
        if self._rng_watch_enabled and self._schema_mode != 'none':
            self.rng_refresh_timer.start()

    def _replace_editor_text_minimally(self, old_text, new_text, target_position=None):
        """Applique un patch textuel minimal afin de conserver Undo et le contexte."""
        if old_text == new_text:
            return
        c = _patch_text_document(self.editor.document(), old_text, new_text)
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
        # Vérifier l'existence de la surface dans le XML de l'édition AVANT
        # d'ouvrir un dialogue que l'utilisateur remplirait pour rien. Le
        # <facsimile> est celui de l'édition, même si une partie est affichée.
        old = self._edition_text()
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
        old = self._edition_text()
        try:
            updated, (lref, rref) = configure_surface_parts(
                old, surface_id, left.text(), right.text(), int(iw), int(ih),
                split_pixel=preview.split_px)
        except ValueError as exc:
            QMessageBox.warning(self, _t('folio.split.title'), str(exc))
            return
        self._write_edition_text(old, updated)
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
        """Crée/complète le facsimile puis insère un <pb n facs> en position sûre.

        Dans une partie de l'édition (V0.9.1.0), le pb est inséré dans la
        partie et le facsimile complété dans l'édition, même non affichée."""
        old = self.editor.toPlainText()
        original_pos = self.editor.textCursor().position()
        # Règle conservatrice : « Marquer la page » n'édite jamais une balise
        # existante. S'il est dans du markup XML, le curseur est probablement là
        # par erreur ; surtout, ne pas créer non plus <facsimile> avant de sortir.
        if position_inside_xml_markup(old, original_pos):
            self.statusBar().showMessage(_t("manuscript.mark_page.inside_tag"), 3200)
            return
        # Le <facsimile> est celui de l'édition.
        in_part = not self._edition_displayed()
        edition = self._edition_text() if in_part else old
        # When marking one region of a spread, validate the target BEFORE
        # changing the source, even if an older in-memory list is stale.
        panel = self.panels.get(witness_id)
        if panel is not None and surface_id not in getattr(panel, '_surface_indices', {}):
            ids = list(getattr(panel, '_surface_indices', {}).keys())
            actual = folios_for_witness(edition, witness_id, ids)
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
        with_facsimile, report = sync_facsimile_text(edition, pages, previous_surface_labels(self.witness_configs))
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
        if not in_part and with_facsimile != old:
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
            old if in_part else with_facsimile, original_pos, label, surface_id, witness_id=witness_id
        )
        if mode == "blocked":
            # Double garde-fou : ne devrait pas arriver après le test ci-dessus,
            # sauf si une future transformation déplace le curseur dans du markup.
            self.statusBar().showMessage(_t("manuscript.mark_page.inside_tag"), 3200)
            return
        if in_part:
            self._write_edition_text(edition, with_facsimile)
        self._replace_editor_text_minimally(old, updated, new_pos)
        self._last_synced_surface = None
        self._sync_page_panels_to_cursor(True)
        self.statusBar().showMessage(
            _t("manuscript.mark_page.inserted", page=label),
            2200,
        )

    def sync_panels_to_cursor(self, force=False):
        # Témoins en lacune au curseur (V0.9.1.3).
        lacunae = self._lacunae_at_cursor()
        # En mode mixte, mettre à jour les folios indépendants sur la foi des
        # pb/edRef/facs, même si le pivot possède une synchronisation de lignes.
        self._sync_page_panels_to_cursor(force, lacunae)
        if not self.base_alignment_available:
            return
        # Édition en parties (V0.9.1.0) : ligne comptée dans l'édition assemblée.
        ordinal=self._base_ordinal_at_cursor()
        if ordinal is None or not self.base_items: return
        ordinal=max(0,min(len(self.base_items)-1,ordinal))
        # Entrer dans une lacune au milieu d'une ligne change aussi l'affichage.
        state = frozenset(lacunae)
        if not force and ordinal == self._last_synced_ordinal and state == self._last_synced_lacunae:
            return
        self._last_synced_ordinal = ordinal
        self._last_synced_lacunae = state
        self._follow_base_line(ordinal, lacunae)
        self._show_base_line_status(ordinal, lacunae)

    def _lacunae_at_cursor(self):
        """``{témoin: Lacuna}`` des témoins en lacune au curseur (V0.9.1.3),
        d'une partie à l'autre dans une édition assemblée. Le relevé du texte
        affiché est gardé tant qu'il ne change pas."""
        text = self.editor.toPlainText()
        revision = self.editor.document().revision()
        cache = self.__dict__.get("_lacuna_events_cache")
        if cache is None or cache[0] is not self.document or cache[1] != revision:
            cache = self._lacuna_events_cache = (self.document, revision, lacuna_events(text))
        position = self.editor.textCursor().position()
        lines = self._pivot_lines()
        if lines is not None:
            return lines.lacunae_at(self.document.path, position, text, include_spans(text), cache[2])
        return lacunae_at(text, position, cache[2])

    def _follow_base_line(self, ordinal, lacunae, skip=None):
        """Les témoins synchronisés par lignes (sauf ``skip``) suivent la ligne
        ``ordinal`` du pivot. Un témoin en lacune montre la ligne où son texte
        s'interrompt, avec le bandeau « Lacune » ; pendant une lacune du
        pivot, les autres restent sur sa dernière ligne, avec un bandeau
        (V0.9.1.3)."""
        key = self.base_items[ordinal]["key"]
        pivot_gap = self.base_id in lacunae
        for wid, panel in self.panels.items():
            if not panel.sync_enabled or wid == skip:
                continue
            lacuna = lacunae.get(wid) if wid != self.base_id else None
            if lacuna is not None:
                panel.set_primary(*self._last_linked_line(panel, self._lacuna_ordinal(lacuna)))
                panel.set_lacuna(LACUNA)
            else:
                panel.set_primary(ordinal, key)
                panel.set_lacuna(None if not pivot_gap else LACUNA if wid == self.base_id else PIVOT_LACUNA)

    def _lacuna_ordinal(self, lacuna):
        """Ligne du pivot où commence ``lacuna``."""
        if lacuna.ordinal is not None:
            return lacuna.ordinal
        return self._base_ordinal_at(lacuna.position) or 0

    def _last_linked_line(self, panel, ordinal):
        """``(ligne, clé)`` du pivot la plus proche de ``ordinal``, en
        remontant, à laquelle ``panel`` a une ligne reliée : la dernière ligne
        du témoin avant sa lacune."""
        ordinal = max(0, min(len(self.base_items) - 1, int(ordinal)))
        for candidate in range(ordinal, -1, -1):
            key = self.base_items[candidate]["key"]
            if panel.map_base.get(key):
                return candidate, key
        return ordinal, self.base_items[ordinal]["key"]

    def _show_base_line_status(self, ordinal, lacunae):
        if self.base_id in lacunae:
            self.statusBar().showMessage(_t("status.base_lacuna", base=self.base_id), 4000)
        else:
            self.statusBar().showMessage(_t("status.base_line", base=self.base_id, line=ordinal+1,
                                            total=len(self.base_items)), 1500)

    def navigate_to_base_ordinal(self, ordinal, move_xml_cursor=True):
        """Synchronise tous les témoins sur un segment cliqué dans la vue mise en forme."""
        if not self.document.in_edition:
            return
        if not self.base_alignment_available or not self.base_items:
            return
        ordinal = max(0, min(len(self.base_items)-1, int(ordinal)))
        if move_xml_cursor:
            self._sync_from_panel = True
            try:
                self._show_base_ordinal(ordinal)
            finally:
                call_later(90, self, self._release_panel_sync)
        self._last_synced_ordinal = ordinal
        # Le curseur n'a pas bougé (table des matières) : pas de lacune.
        lacunae = self._lacunae_at_cursor() if move_xml_cursor else {}
        self._last_synced_lacunae = frozenset(lacunae)
        self._follow_base_line(ordinal, lacunae)
        # Le déplacement dans la vue mise en forme peut inhiber temporairement
        # le timer du curseur : actualiser également les témoins en mode page.
        self._sync_page_panels_to_cursor(force=True, lacunae=lacunae)
        self._show_base_line_status(ordinal, lacunae)

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
        # Témoins du segment affiché : l'édition, ou le texte synchronisé à part.
        rows = diagnostic_rows(self._segment_project(), self._witness_resource_snapshot())
        WitnessDiagnosticDialog(rows, self, self._diagnostic_scope(), self._diagnostic_notes()).exec()

    def refresh_witness_synchronizations(self):
        """Reload the alignments and OCR without replacing the editor widget.

        The entire new state is staged before commit: a broken/partial JSON
        cannot destroy the current display. A confirmation shows changes to
        scientific line keys (even if the line counts happen to be equal).
        No modifications to TEI, project.xml, image sources or external files.
        """
        old_rows = diagnostic_rows(self._segment_project(), self._witness_resource_snapshot())
        # Segment du document affiché (V0.9.1.1) : l'édition, ou un texte
        # synchronisé à part ; les dossiers des textes sont relus.
        project = self._refreshed_segment_project()
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            staged = assemble_resources(project)
            new_rows = diagnostic_rows(project, staged)
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
        self._apply_runtime_state(staged, project,
                                  images=staged.images_available if project is self.project else None)
        self._store_segment_state(staged, project)
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
        if not self.base_items: return
        self._sync_from_panel=True
        try:
            # Dans une édition en parties, la ligne peut être dans une autre
            # partie : elle est alors affichée.
            ordinal=self._show_base_ordinal(min(len(self.base_items)-1, int(ordinal)))
            if ordinal is None: return
            self._last_synced_ordinal = ordinal
            lacunae = self._lacunae_at_cursor()
            self._last_synced_lacunae = frozenset(lacunae)
            # Le témoin de base vient déjà de naviguer ; on actualise tous les panneaux.
            self.base_panel.match_indices={ordinal}; self.base_panel.center_index=self.base_panel.origin_center_index=ordinal; self.base_panel.reload()
            self.base_panel.set_lacuna(LACUNA if self.base_id in lacunae else None)
            self._follow_base_line(ordinal, lacunae, skip=self.base_id)
            self._sync_page_panels_to_cursor(force=True, lacunae=lacunae)
        finally:
            call_later(90, self, self._release_panel_sync)

    def _release_panel_sync(self): self._sync_from_panel=False

    # --- Les flèches d'un panneau mènent l'édition (V0.9.1.4) -----------------

    @Slot(str, int)
    def _witness_panel_navigate(self, wid, step):
        """Flèches du panneau ``wid`` : le témoin mène l'édition dans son
        propre ordre, d'une partie ou d'un texte à l'autre ; les autres
        témoins suivent le pivot. Hors de l'édition, ou sans lignes reliées
        au pivot, le témoin est seulement feuilleté."""
        panel = self.panels.get(wid)
        if panel is None:
            return
        if not self.document.in_edition:
            panel.browse(step)
            return
        if panel.absent_key is not None or not panel.items:
            # Le témoin n'a pas le texte affiché : texte suivant ou précédent
            # qui l'a, dans l'ordre de l'édition.
            stop = self._present_stop(wid, step)
            if stop is None:
                self._show_witness_end(wid, step)
            else:
                self._go_to_witness_stop(wid, stop)
            return
        if not panel.sync_enabled:
            if not panel.folios:
                panel.browse(step)
                return
            before = (panel.center_index, panel._active_folio)
            panel.browse(step)
            if step and (panel.center_index, panel._active_folio) == before:
                self._show_witness_end(wid, step)
                return
            self._lead_to_page(wid, panel)
            return
        segment = getattr(self, "_active_segment", None)
        key = panel.current_item()["key"]
        route = self._witness_route(wid)
        if route.index(segment, key) is not None:
            stop = route.step(segment, key, step)
        else:
            stop = self._panel_stop(wid, panel, panel.center_index + step)
        if stop is None:
            self._show_witness_end(wid, step)
            return
        self._go_to_witness_stop(wid, stop)
        if stop.segment != segment and stop.segment in route.uncertain:
            self.statusBar().showMessage(
                _t("status.route_uncertain", witness=wid, text=self._segment_name(stop.segment)), 6000)

    def _show_witness_end(self, wid, step):
        self.statusBar().showMessage(
            _t("status.witness_end" if step > 0 else "status.witness_start", witness=wid), 4000)

    def _lead_to_page(self, wid, panel):
        """Témoin par pages : l'édition va à la page affichée par ``panel`` :
        à sa première ligne dans un JSON du témoin, sinon à son ``<pb>``,
        sinon au début du texte dont le ``<locus from>`` est cette page."""
        folio = panel._current_folio()
        if folio is None:
            return
        route = self._witness_route(wid)
        item = panel.current_item()
        stop = route.on_page(page_identity(item["p"])) if item is not None else None
        if stop is None or (stop.location is None and stop.ordinal is None):
            surface = {f.ref for f in panel.folios if f.surface == folio.surface}
            stop = route.on_page(f"folio:{folio.ref}") or next(
                (s for s in route.stops if s.location is not None and s.key in surface), None)
        if stop is not None:
            self._go_to_witness_stop(wid, stop)
            panel = self.panels[wid]
            if not panel.sync_enabled and panel.folios:
                panel.set_folio(folio.ref)
            return
        segment = self._locus_text(wid, folio)
        if segment is None:
            self.statusBar().showMessage(_t("status.page_unmarked", witness=wid, folio=folio.label), 5000)
            return
        self._sync_from_panel = True
        try:
            if self._show_segment_ordinal(segment, 0) is not None:
                self.sync_panels_to_cursor(True)
                self.panels[wid].set_folio(folio.ref)
        finally:
            call_later(90, self, self._release_panel_sync)

    def _locus_text(self, wid, folio):
        """Texte synchronisé à part dont le ``<locus from>`` du témoin est
        ``folio``, ou None."""
        label = folio.label.strip().casefold()
        for sync in self._text_syncs()[0] if self._edition_has_parts() else ():
            segment = path_key(sync.path)
            ids = self._segment_ids(segment)
            if any(locus.start and locus.start.strip().casefold() == label and locus.targets & ids
                   for locus in self._text_loci(segment).get(wid, ())):
                return segment
        return None

    def _present_stop(self, wid, step):
        """Premier arrêt du témoin dans le texte suivant (``step`` > 0) ou
        dernier dans le texte précédent où il est présent, dans l'ordre de
        l'édition ; None s'il n'y en a pas."""
        lines = self._pivot_lines()
        if lines is None:
            return None
        syncs = [path_key(sync.path) for sync in self._text_syncs()[0]]
        after = len(syncs) + 1

        def place(segment, ordinal=None):
            if segment is None:
                return (ordinal if ordinal is not None else -1, after)
            return (lines.anchor(segment), syncs.index(segment) if segment in syncs else after)

        segment = getattr(self, "_active_segment", None)
        here = place(segment, self._base_ordinal_at_cursor() or 0)
        route = self._witness_route(wid)
        found = None
        for stop in route.stops:
            key = place(stop.segment, stop.ordinal)
            if (key > here if step > 0 else key < here) and (
                    found is None or (key < found[0] if step > 0 else key >= found[0])):
                found = (key, stop)
        if found is None:
            return None
        stop = found[1]
        if stop.segment is not None:
            stop = route.first(stop.segment) if step > 0 else route.last(stop.segment)
        return stop

    def _show_witness_mark(self, wid, stop):
        """Place le curseur à la fin du ``<pb>`` de ``stop`` (folio
        ``stop.key``), dans son fichier, affiché au besoin. La position est
        relue dans le texte affiché, qui a pu changer depuis la
        numérotation."""
        path, position = stop.location
        session = next((s for s in self.documents if s.in_edition and path_key(s.path) == path_key(path)), None)
        if session is None:
            return False
        if session is not self.document and not self.show_document(session):
            return False
        self.show_document_tab(session)
        text = self.editor.toPlainText()
        ends = [end for folio, end in folio_marks(text, wid, self.panels[wid].folios) if folio.ref == stop.key]
        if ends:
            position = min(ends, key=lambda end: abs(end - position))
        cursor = self.editor.textCursor()
        cursor.setPosition(max(0, min(int(position), len(text))))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        return True

    def _panel_stop(self, wid, panel, index):
        """Arrêt de rang ``index`` dans le panneau (élément hors du parcours) :
        sa ligne du pivot, ou celle de la ligne reliée qui la précède."""
        if not 0 <= index < len(panel.items):
            return None
        ordinal = None
        for candidate in range(index, -1, -1):
            ordinal = self._item_base_ordinal(wid, panel.items[candidate])
            if ordinal is not None:
                break
        linked = self._item_base_ordinal(wid, panel.items[index]) is not None
        return Stop(getattr(self, "_active_segment", None), panel.items[index]["key"], "", ordinal, linked)

    def _item_base_ordinal(self, wid, item):
        """Ligne du pivot que désigne l'élément ``item`` du panneau ``wid``."""
        if wid == self.base_id:
            return self.base_by_key.get(item["key"])
        ranks = [self.base_by_key[str(k)] for k in (item["l"].get("base_keys") or item["l"].get("keys816") or [])
                 if str(k) in self.base_by_key]
        return min(ranks) if ranks else None

    def _go_to_witness_stop(self, wid, stop):
        """L'édition va à la ligne du pivot de ``stop`` (dans son texte), ou à
        son ``<pb>`` ; le panneau ``wid`` se place sur l'élément de ``stop`` ;
        les autres suivent le pivot."""
        if stop.location is not None:
            self._sync_from_panel = True
            try:
                if self._show_witness_mark(wid, stop):
                    self.sync_panels_to_cursor(True)
                    panel = self.panels[wid]
                    if not panel.sync_enabled and panel.folios:
                        panel.set_folio(stop.key)
            finally:
                call_later(90, self, self._release_panel_sync)
            return
        if stop.ordinal is None:
            return
        self._sync_from_panel = True
        try:
            reached = self._show_segment_ordinal(stop.segment, stop.ordinal)
            if reached is None:
                return
            panel = self.panels[wid]
            lacunae = self._lacunae_at_cursor()
            self._last_synced_ordinal = reached
            self._last_synced_lacunae = frozenset(lacunae)
            key = self.base_items[reached]["key"]
            index = next((i for i, item in enumerate(panel.items) if item["key"] == stop.key), None)
            if index is not None:
                panel.primary_key = key
                if panel.is_base:
                    panel.match_indices = {index}
                    panel.origin_center_index = index
                else:
                    matches = valid_matched_indices(panel.map_base.get(key, []), len(panel.items))
                    panel.match_indices = matches
                    center = matched_line_center(sorted(matches), index, len(panel.items))
                    panel.origin_center_index = center if center is not None else index
                panel.center_index = index
                panel.reload()
            pivot_gap = self.base_id in lacunae
            panel.set_lacuna(LACUNA if wid in lacunae else
                             PIVOT_LACUNA if pivot_gap and wid != self.base_id else None)
            self._follow_base_line(reached, lacunae, skip=wid)
            self._sync_page_panels_to_cursor(force=True, lacunae=lacunae)
            if stop.linked:
                self._show_base_line_status(reached, lacunae)
            else:
                self.statusBar().showMessage(_t("status.witness_unlinked", witness=wid, line=reached + 1), 4000)
        finally:
            call_later(90, self, self._release_panel_sync)

    def goto_xml_from_base(self):
        if not self.document.in_edition: return
        if self._show_base_ordinal(self.base_panel.center_index) is not None: self.editor.setFocus()
