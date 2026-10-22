# -*- coding: utf-8 -*-
"""Disposition des panneaux de témoins : ordre, visibilité, tailles, fenêtres détachées, agrandissement."""
from __future__ import annotations

import hashlib
import json

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QCheckBox, QDialog, QDialogButtonBox, QHBoxLayout, QLabel,
    QListWidget, QListWidgetItem, QPushButton, QSplitter, QVBoxLayout, QWidget,
)
from app_context import _settings, call_later, tr as _t


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


class WitnessWorkspaceMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

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
        call_later(0, self, self._restore_workspace_sizes)

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
        call_later(0, self, self._restore_workspace_sizes)
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
        call_later(0, self, self._restore_workspace_sizes)
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
                call_later(0, self, self._restore_workspace_sizes)
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
