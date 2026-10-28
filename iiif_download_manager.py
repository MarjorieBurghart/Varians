# -*- coding: utf-8 -*-
"""Non-blocking IIIF download manager (PySide6), backed by iiif_local.

Only a user-initiated worker accesses the network. A single project manager
runs one download at a time, keeping its QThread alive until finished.
"""
from __future__ import annotations

import threading

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QComboBox,
    QPushButton, QLabel, QTextEdit, QProgressBar, QMessageBox)

from iiif_local import plan_witness_copy, download_witness_copy


class DownloadThread(QThread):
    progress_update = Signal(int, int, str)
    completed = Signal(object)

    def __init__(self, root, witness, force=False, parent=None):
        super().__init__(parent)
        self.root = root
        self.witness = witness
        self.force = force
        self.cancel_event = threading.Event()
        self.pause_event = threading.Event()

    def run(self):
        w = self.witness
        try:
            result = download_witness_copy(
                self.root, w.id, w.image_source_value or '',
                scope=getattr(w, 'iiif_download_scope', 'all'),
                layout_files=getattr(w, 'alto_files', ()), force=self.force,
                selection_mode=getattr(w, 'iiif_selection_mode', 'all'),
                selected_canvases=getattr(w, 'iiif_selected_canvases', ()),
                ocr_links=getattr(w, 'iiif_ocr_links', ()),
                progress=lambda done, total, label: self._progress(done, total, label),
                cancel_event=self.cancel_event, pause_event=self.pause_event,
            )
            self.completed.emit(result)
        except Exception as exc:
            self.completed.emit({'error': str(exc)})

    def _progress(self, done, total, label):
        self.progress_update.emit(done, total, str(label))
        return not self.cancel_event.is_set()


class IIIFDownloadManager(QDialog):
    """One witness at a time; pause/resume/cancel without losing partial cache."""

    def __init__(self, tr, project, parent=None, auto_start=False):
        super().__init__(parent)
        self.tr, self.project = tr, project
        self.thread = None
        self.queue = []
        self.setWindowTitle(tr('iiif.manager.title'))
        self.resize(720, 470)
        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel(tr('iiif.manager.witness')))
        self.witness = QComboBox()
        for w in project.witnesses:
            if w.image_source_type == 'iiif':
                self.witness.addItem(w.display_title, w.id)
        top.addWidget(self.witness, 1)
        layout.addLayout(top)
        self.summary = QLabel()
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.progress = QProgressBar()
        layout.addWidget(self.progress)
        self.current = QLabel()
        self.current.setWordWrap(True)
        layout.addWidget(self.current)
        self.log = QTextEdit()
        self.log.setReadOnly(True)
        layout.addWidget(self.log, 1)
        controls = QHBoxLayout()
        self.start_btn = QPushButton(tr('iiif.manager.start'))
        self.all_btn = QPushButton(tr('iiif.manager.all_witnesses'))
        self.refresh_btn = QPushButton(tr('iiif.manager.refresh'))
        self.pause_btn = QPushButton(tr('iiif.manager.pause'))
        self.stop_btn = QPushButton(tr('iiif.manager.stop'))
        self.close_btn = QPushButton(tr('common.close'))
        for btn in (self.start_btn, self.all_btn, self.refresh_btn, self.pause_btn, self.stop_btn, self.close_btn):
            controls.addWidget(btn)
        layout.addLayout(controls)
        if auto_start:
            for i in range(self.witness.count()):
                w = project.witness_by_id[self.witness.itemData(i)]
                if w.iiif_local_copy or w.iiif_web_local_copy:
                    self.witness.setCurrentIndex(i)
                    break
        self.witness.currentIndexChanged.connect(self.update_plan)
        self.start_btn.clicked.connect(lambda: self.start_download(False))
        self.all_btn.clicked.connect(self.start_all)
        self.refresh_btn.clicked.connect(lambda: self.start_download(True))
        self.pause_btn.clicked.connect(self.toggle_pause)
        self.stop_btn.clicked.connect(self.stop_download)
        self.close_btn.clicked.connect(self.hide)
        self.update_plan()
        if auto_start and self.witness.count():
            self.start_all()

    def _localized_warning(self, message):
        """Translate known matching diagnostics; keep original OCR filename."""
        meanings = {
            'No ALTO/PAGE layout files supplied (no IIIF images selected)':
                'iiif.manager.reason.empty',
            'multiple IIIF canvases have the same image/page name':
                'iiif.manager.reason.duplicate',
            'ambiguous folio label in IIIF manifest':
                'iiif.manager.reason.ambiguous',
            'no matching IIIF canvas (not downloaded)':
                'iiif.manager.reason.unmatched',
        }
        raw = str(message)
        for english, key in meanings.items():
            if raw == english:
                return self.tr(key)
            if raw.endswith(': ' + english):
                return raw[:-len(english)] + self.tr(key)
        return raw

    def selected_witness(self):
        return self.project.witness_by_id.get(self.witness.currentData())

    def update_plan(self, *_):
        if self.thread is not None and self.thread.isRunning():
            return
        w = self.selected_witness()
        if w is None:
            self.summary.setText(self.tr('iiif.manager.none'))
            self.start_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            return
        try:
            plan = plan_witness_copy(self.project.root_dir, w.id,
                w.image_source_value or '',
                scope=getattr(w, 'iiif_download_scope', 'all'),
                layout_files=getattr(w, 'alto_files', ()),
                selection_mode=getattr(w, 'iiif_selection_mode', 'all'),
                selected_canvases=getattr(w, 'iiif_selected_canvases', ()),
                ocr_links=getattr(w, 'iiif_ocr_links', ()))
        except Exception as exc:
            self.summary.setText(self.tr('iiif.manager.plan_error', error=str(exc)))
            self.start_btn.setEnabled(False)
            self.refresh_btn.setEnabled(False)
            return
        self.summary.setText(self.tr('iiif.manager.summary',
            total=plan['total_pages'], eligible=plan['total'],
            cached=plan['cached'], missing=plan['pending'],
            excluded=plan['excluded']))
        self.progress.setRange(0, max(1, plan['total']))
        self.progress.setValue(plan['cached'])
        self.start_btn.setEnabled(bool(plan['pending']))
        self.refresh_btn.setEnabled(bool(plan['total']))
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        for msg in plan['warnings']:
            self.log.append(self.tr('iiif.manager.warning', message=self._localized_warning(msg)))

    def start_download(self, force=False):
        if self.thread is not None and self.thread.isRunning():
            return
        w = self.selected_witness()
        if w is None:
            return
        self.log.clear()
        self.thread = DownloadThread(self.project.root_dir, w, force, self)
        self.thread.progress_update.connect(self._progress)
        self.thread.completed.connect(self._completed)
        self.thread.finished.connect(self._thread_finished)
        self.witness.setEnabled(False)
        self.start_btn.setEnabled(False)
        self.all_btn.setEnabled(False)
        self.refresh_btn.setEnabled(False)
        self.pause_btn.setEnabled(True)
        self.stop_btn.setEnabled(True)
        self.pause_btn.setText(self.tr('iiif.manager.pause'))
        self.current.setText(self.tr('iiif.manager.running'))
        self.thread.start()

    def start_all(self):
        """Queue all witnesses that actually opted in for an IIIF local copy."""
        if self.thread is not None and self.thread.isRunning():
            return
        self.queue = [w.id for w in self.project.witnesses
                      if w.image_source_type == 'iiif' and
                      (w.iiif_local_copy or w.iiif_web_local_copy)]
        self._next_in_queue()

    def _next_in_queue(self):
        if not self.queue:
            return
        wid = self.queue.pop(0)
        index = self.witness.findData(wid)
        if index >= 0:
            self.witness.setCurrentIndex(index)
            self.start_download(False)

    def _progress(self, done, total, label):
        self.progress.setRange(0, max(1, total))
        self.progress.setValue(done)
        self.current.setText(self.tr('iiif.manager.page', index=done, count=total, label=label))

    def toggle_pause(self):
        if not self.thread or not self.thread.isRunning():
            return
        if self.thread.pause_event.is_set():
            self.thread.pause_event.clear()
            self.pause_btn.setText(self.tr('iiif.manager.pause'))
            self.current.setText(self.tr('iiif.manager.running'))
        else:
            self.thread.pause_event.set()
            self.pause_btn.setText(self.tr('iiif.manager.resume'))
            self.current.setText(self.tr('iiif.manager.paused'))

    def stop_download(self):
        self.queue.clear()
        if self.thread and self.thread.isRunning():
            self.thread.cancel_event.set()
            self.thread.pause_event.clear()
            self.current.setText(self.tr('iiif.manager.stopping'))

    def _completed(self, result):
        if 'error' in result:
            self.current.setText(self.tr('iiif.manager.failed', error=result['error']))
            self.log.append(result['error'])
        else:
            self.current.setText(self.tr('iiif.manager.done',
                downloaded=result['downloaded'], skipped=result['skipped'],
                failed=len(result['failed'])))
            for i, error in result['failed']:
                self.log.append(f'{i}: {error}')
            for msg in result.get('warnings', ()):
                self.log.append(self.tr('iiif.manager.warning', message=self._localized_warning(msg)))
            if result['cancelled']:
                self.queue.clear()
                self.log.append(self.tr('iiif.manager.cancelled'))

    def _thread_finished(self):
        owner = self.parent()
        if owner is not None and hasattr(owner, 'refresh_local_iiif_cache'):
            owner.refresh_local_iiif_cache()
        self.witness.setEnabled(True)
        self.all_btn.setEnabled(True)
        self.pause_btn.setEnabled(False)
        self.stop_btn.setEnabled(False)
        self.thread = None
        self.update_plan()
        self._next_in_queue()

    def closeEvent(self, event):
        # Hiding the manager is safe; jobs remain alive and can be reopened.
        event.ignore()
        self.hide()

    def shutdown(self):
        """Called by MainWindow before leaving a project (no orphan threads)."""
        if self.thread and self.thread.isRunning():
            self.stop_download()
            self.thread.wait(30000)
