# -*- coding: utf-8 -*-
"""Panneaux des témoins manuscrits : affichage des images (locales ou IIIF), lignes OCR, navigation et synchronisation visuelle."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import (
    QBuffer, QByteArray, QIODevice, QPointF, QRectF, Qt, QThreadPool, QTimer, QUrl, Signal,
    Slot,
)
from PySide6.QtGui import (
    QBrush, QColor, QDesktopServices, QImageReader, QPen, QPixmap, QPolygonF,
)
from PySide6.QtWidgets import (
    QComboBox, QFrame, QGraphicsPixmapItem, QGraphicsPolygonItem, QGraphicsRectItem,
    QGraphicsScene, QGraphicsView, QHBoxLayout, QInputDialog, QLabel, QPushButton,
    QVBoxLayout, QWidget,
)
from app_context import call_later, tr as _t
from folio_navigation import markable_part_for_line, scene_rect_for_folio
from image_fetch import FetchWorker
from image_sources import (
    display_window_indices, effective_line_bbox, full_page_target,
    image_scene_reference_crop, matched_line_center, page_image_dimensions,
    page_image_request as generic_image_request, page_image_source,
    page_label as image_page_label, valid_matched_indices, visible_line_frame_indices,
)


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

        call_later(0, self, run)

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
    witnessNavigate = Signal(str, int)  # témoin, pas des flèches (V0.9.1.4)
    markPageRequested = Signal(str, str, str)  # témoin, surface/zone xml:id, @n
    splitFolioRequested = Signal(str, str)  # témoin, surface xml:id
    maximizeRequested = Signal(str)
    detachRequested = Signal(str)

    _memory_cache = {}

    def __init__(self, siglum, label, items, map_base=None, is_base=False, base_label="base", project_root=None, sync_enabled=True, parent=None):
        super().__init__(parent)
        self.siglum = siglum; self.label = label; self.items = items; self.map_base = map_base or {}; self.is_base = bool(is_base); self.base_label = base_label; self.project_root = Path(project_root).resolve() if project_root else None
        self.sync_enabled = bool(sync_enabled)
        # Clé du message affiché quand le témoin n'a pas de données pour le
        # texte en cours (V0.9.1.1, textes synchronisés à part) ; voir set_absent.
        self.absent_key = None
        # Clé du bandeau « Lacune » (V0.9.1.3) ; voir set_lacuna.
        self.lacuna_key = None
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
        self.lacuna_label = QLabel("")
        self.lacuna_label.setWordWrap(True)
        self.lacuna_label.setStyleSheet(
            "color:#6b4a1f;background:#f6e7c9;border:1px solid #d9b77a;border-radius:4px;"
            "padding:2px 6px;font-size:11px;font-weight:bold")
        self.lacuna_label.hide()
        root.addWidget(self.lacuna_label)
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
        if self.lacuna_key:
            self.lacuna_label.setText(_t(self.lacuna_key))
        # Update labels/status without refetching IIIF images.
        if not self.items:
            self._show_empty()
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
        """Flèches du panneau (V0.9.1.4) : la fenêtre fait mener l'édition
        par le témoin, dans son propre ordre, ou le feuillette (``browse``)."""
        self.witnessNavigate.emit(self.siglum, int(step))

    def browse(self, step):
        """Feuillette le témoin, sans toucher à l'édition."""
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
        self.reload()

    def go_home(self):
        if self.is_base: return
        self.center_index = self.origin_center_index; self.reload()

    def set_base(self, is_base, base_label):
        """Le pivot change avec le texte affiché (V0.9.1.1) : ce panneau est-il
        celui du pivot, et comment s'appelle le pivot."""
        self.is_base = bool(is_base)
        self.base_label = base_label
        self.home_btn.setVisible(not self.is_base)

    def set_absent(self, key):
        """Le témoin n'a pas de données pour le texte affiché : le panneau
        reste à sa place, vide, avec le message ``key`` (catalogue i18n)."""
        self.absent_key = key
        self.items = []
        self.map_base = {}
        self.sync_enabled = False
        self._surface_indices = {}
        self.center_index = self.origin_center_index = 0
        self.match_indices = set()
        self.primary_key = None
        self.sync_issue.hide()
        self.set_lacuna(None)
        self.reload()

    def set_lacuna(self, key):
        """Bandeau au-dessus de l'image (V0.9.1.3) : le témoin, ou le pivot,
        est en lacune à cet endroit du texte. ``key`` : message du catalogue
        i18n, ou None pour retirer le bandeau."""
        if key == self.lacuna_key:
            return
        self.lacuna_key = key
        self.lacuna_label.setText(_t(key) if key else "")
        self.lacuna_label.setVisible(bool(key))

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

    def _show_empty(self):
        """Panneau sans ligne : le message d'absence du texte, s'il y a lieu."""
        if self.absent_key:
            self.status.setText(_t(self.absent_key))
            self.message.setText(_t(self.absent_key))
            self.message.show()
        else:
            self.status.setText(_t("manuscript.no_line"))

    def reload(self):
        self.load_token += 1; token = self.load_token
        self.loaded_groups = {}; self.group_specs = []
        self.view.scene().clear(); self.message.hide(); self.message.setText("")
        inds = self._window_indices()
        if not inds:
            self._show_empty(); return
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

