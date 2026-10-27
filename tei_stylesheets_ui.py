# -*- coding: utf-8 -*-
"""Fenêtre « TEI Stylesheets… » et mises à jour des TEI Stylesheets (V0.9.2.2).

- ``TeiStylesheetsDialog`` : la version installée (``tei_stylesheets``), son
  origine, son dossier, sa licence, la dernière vérification, et
  « Rechercher une mise à jour ». Fichier ▸ « TEI Stylesheets… » et le bouton
  de la liste des scénarios l'ouvrent.
- ``at_launch(window)`` : au lancement de Varians, supprime les anciennes
  versions (jamais pendant une transformation : aucune n'a encore commencé),
  puis, si la dernière vérification (réglage ``LAST_CHECK_SETTING``) date
  d'au moins ``CHECK_INTERVAL_DAYS`` jours, demande au TEI-C sa dernière
  version. Sans nouveauté ou sans réseau, rien n'est dit.
- Une nouvelle version est proposée (« Installer » ou « Plus tard » : la
  question revient à la vérification suivante). L'installation montre une
  fenêtre de progression, avec Annuler, puis un message dans la barre
  d'état. Elle sert dès l'exécution suivante ; l'ancienne version reste en
  place jusqu'au lancement suivant.

Le réseau n'est lu que dans un fil à part (``threading``) ; le résultat
revient au fil principal par un signal Qt (``_Task``). ``busy()`` dit si une
vérification ou une installation est en cours.
"""
from __future__ import annotations

import datetime
import shutil
import tempfile
import threading
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout)

import tei_stylesheets
from app_context import _settings, tr as _t
from tei_stylesheets import LibraryError

LAST_CHECK_SETTING = "teiStylesheets/lastCheck"
CHECK_INTERVAL_DAYS = 30
# Codes d'erreur qui ont un message (``tei_stylesheets.error.<code>``) ;
# ``cancelled`` n'en est pas une.
ERROR_CODES = ("network", "invalid_reply", "invalid_archive", "write_failed")

_RUNNING = set()            # opérations en cours, gardées en vie jusqu'à leur fin
_PROGRESS = None            # fenêtre de progression de l'installation en cours


def busy() -> bool:
    """Une vérification ou une installation est-elle en cours ?"""
    return bool(_RUNNING)


def progress_dialog():
    """La fenêtre de progression de l'installation en cours, ou None."""
    return _PROGRESS if _PROGRESS is not None and shiboken6.isValid(_PROGRESS) else None


def last_check() -> datetime.date | None:
    """Date de la dernière vérification, ou None (jamais)."""
    try:
        return datetime.date.fromisoformat(str(_settings().value(LAST_CHECK_SETTING, "") or ""))
    except ValueError:
        return None


def check_due(today=None) -> bool:
    """La vérification du lancement est-elle due (au plus une par mois) ?"""
    today = today or datetime.date.today()
    last = last_check()
    return last is None or last > today or (today - last).days >= CHECK_INTERVAL_DAYS


def at_launch(window, today=None):
    """Au lancement : anciennes versions supprimées, puis vérification si
    elle est due (voir la docstring du module)."""
    tei_stylesheets.remove_old_versions()
    if check_due(today):
        return check_for_update(window, automatic=True)
    return None


def error_text(error) -> str:
    code = error.code if error.code in ERROR_CODES else "network"
    return _t(f"tei_stylesheets.error.{code}", detail=error.detail or error.code)


def _alive(widget):
    return widget is not None and shiboken6.isValid(widget)


def _parent(widget):
    return widget if _alive(widget) else QApplication.activeWindow()


def _status(widget, text):
    """Message dans la barre d'état de la fenêtre de ``widget``, sinon dans
    une boîte."""
    while _alive(widget):
        if hasattr(widget, "statusBar"):
            widget.statusBar().showMessage(text, 10000)
            return
        widget = widget.parentWidget()
    QMessageBox.information(QApplication.activeWindow(), _t("tei_stylesheets.title"), text)


class _Task(QObject):
    """``work(progress)`` dans un fil à part ; ``finished(résultat, erreur)``
    et ``progress(reçu, total)`` sont appelés dans le fil principal."""

    _progressed = Signal(int, int)
    _completed = Signal(object, object)

    def __init__(self, work, finished, progress=None):
        super().__init__()
        self._work, self._finished, self._progress = work, finished, progress
        self._progressed.connect(self._on_progress)
        self._completed.connect(self._on_completed)

    def start(self):
        _RUNNING.add(self)
        threading.Thread(target=self._run, daemon=True).start()
        return self

    def _run(self):
        try:
            result, error = self._work(self._progressed.emit), None
        except LibraryError as exc:
            result, error = None, exc
        except Exception as exc:                  # le fil répond toujours
            result, error = None, LibraryError("write_failed", f"{type(exc).__name__}: {exc}")
        self._completed.emit(result, error)

    @Slot(int, int)
    def _on_progress(self, done, total):
        if self._progress is not None:
            self._progress(done, total)

    @Slot(object, object)
    def _on_completed(self, result, error):
        # Terminée avant sa suite : une installation qu'elle lance s'ajoute
        # à son tour, et la fenêtre rafraîchie voit l'état juste.
        _RUNNING.discard(self)
        self._finished(result, error)


# --- Vérification et installation -------------------------------------------------------------

def check_for_update(parent, automatic=False, done=None):
    """Demande au TEI-C sa dernière version, puis propose de l'installer si
    elle est plus récente. ``automatic`` (au lancement) : rien n'est dit sans
    nouveauté ni réseau. ``done(installée ou None)`` : appelé à la fin."""
    _settings().setValue(LAST_CHECK_SETTING, datetime.date.today().isoformat())

    def finished(latest, error):
        widget = _parent(parent)
        current = tei_stylesheets.ensure_installed()
        current_version = current.version if current is not None else None
        title = _t("tei_stylesheets.title")
        if error is not None:
            if not automatic:
                QMessageBox.warning(widget, title, error_text(error))
        elif not tei_stylesheets.is_newer(latest, current_version):
            if not automatic:
                QMessageBox.information(widget, title, _t("tei_stylesheets.up_to_date",
                                                          version=current_version or latest))
        elif _consent(widget, latest, current_version):
            install(widget, latest, done)
            return
        if done is not None:
            done(None)

    return _Task(lambda _progress: tei_stylesheets.latest_version(), finished).start()


def _consent(parent, version, current):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(_t("tei_stylesheets.title"))
    box.setText(_t("tei_stylesheets.available", version=version, current=current or _t("tei_stylesheets.none")))
    box.setInformativeText(_t("tei_stylesheets.available.detail"))
    install_btn = box.addButton(_t("tei_stylesheets.install"), QMessageBox.ButtonRole.AcceptRole)
    later_btn = box.addButton(_t("tei_stylesheets.later"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(install_btn)
    box.setEscapeButton(later_btn)
    box.exec()
    return box.clickedButton() is install_btn


def _install_work(version, cancel):
    def work(progress):
        base = tei_stylesheets.library_dir()
        try:
            base.mkdir(parents=True, exist_ok=True)
            # Un dossier « .tmp-… » : remove_old_versions le supprime s'il reste.
            folder = Path(tempfile.mkdtemp(prefix=tei_stylesheets.TEMP_PREFIX + "telechargement-", dir=base))
        except OSError as exc:
            raise LibraryError("write_failed", str(exc)) from exc
        try:
            path = tei_stylesheets.download(version, folder, progress=progress, cancel=cancel.is_set)
            progress(-1, 0)                                         # installation
            return tei_stylesheets.install_zip(path, expected_version=version, source="downloaded")
        finally:
            shutil.rmtree(folder, ignore_errors=True)
    return work


def install(parent, version, done=None):
    """Télécharge et installe ``version``, avec une fenêtre de progression et
    Annuler. ``done(installée ou None)`` : appelé à la fin."""
    global _PROGRESS
    cancel = threading.Event()
    progress = QProgressDialog(_t("tei_stylesheets.downloading", version=version), _t("common.cancel"), 0, 0,
                               parent)
    progress.setWindowTitle(_t("tei_stylesheets.title"))
    progress.setMinimumWidth(460)                               # le libellé entier
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.canceled.connect(cancel.set)                       # Annuler
    progress.rejected.connect(cancel.set)                       # Échap
    _PROGRESS = progress
    progress.show()

    def step(received, total):
        if not _alive(progress):
            return
        if received < 0:
            progress.setLabelText(_t("tei_stylesheets.installing", version=version))
            progress.setRange(0, 0)
        elif total > 0:
            progress.setRange(0, total)
            progress.setValue(min(received, total))

    def finished(installed, error):
        global _PROGRESS
        _PROGRESS = None
        if _alive(progress):
            progress.close()
            progress.deleteLater()
        widget = _parent(parent)
        if error is not None and error.code == "cancelled":
            _status(widget, _t("tei_stylesheets.cancelled"))
        elif error is not None:
            QMessageBox.warning(widget, _t("tei_stylesheets.title"), error_text(error))
        else:
            _status(widget, _t("tei_stylesheets.installed", version=installed.version))
        if done is not None:
            done(installed)

    return _Task(_install_work(version, cancel), finished, step).start()


# --- La fenêtre -------------------------------------------------------------------------------

class TeiStylesheetsDialog(QDialog):
    """Fichier ▸ « TEI Stylesheets… »."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("tei_stylesheets.title"))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        intro = QLabel(_t("tei_stylesheets.intro"), self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.version_label = QLabel(self)
        self.source_label = QLabel(self)
        self.folder_label = QLineEdit(self)                     # un long chemin : lu en entier
        self.folder_label.setReadOnly(True)
        self.open_folder_btn = QPushButton(_t("common.open_folder"), self)
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.licence_label = QLabel(_t("tei_stylesheets.licence.text"), self)
        self.licence_label.setWordWrap(True)
        self.licence_btn = QPushButton(_t("tei_stylesheets.show_licence"), self)
        self.licence_btn.clicked.connect(self.show_licence)
        self.checked_label = QLabel(self)
        form.addRow(_t("tei_stylesheets.version"), self.version_label)
        form.addRow(_t("tei_stylesheets.source"), self.source_label)
        form.addRow(_t("tei_stylesheets.folder"), self.folder_label)
        form.addRow(_t("tei_stylesheets.licence"), self.licence_label)
        form.addRow(_t("tei_stylesheets.checked"), self.checked_label)
        layout.addLayout(form)
        row = QHBoxLayout()
        row.addWidget(self.open_folder_btn)
        row.addWidget(self.licence_btn)
        row.addStretch(1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.check_btn = buttons.addButton(_t("tei_stylesheets.check"), QDialogButtonBox.ButtonRole.ActionRole)
        self.check_btn.clicked.connect(self.check)
        buttons.rejected.connect(self.reject)
        row.addWidget(buttons)
        layout.addLayout(row)
        self.refresh()

    def library(self):
        return tei_stylesheets.ensure_installed()

    def refresh(self, *_args):
        if not _alive(self):
            return
        library = self.library()
        if library is None:
            self.version_label.setText(_t("tei_stylesheets.none"))
            self.source_label.setText("")
            folder = tei_stylesheets.library_dir()
        else:
            self.version_label.setText(library.version)
            self.source_label.setText(_t("tei_stylesheets.source.bundled") if library.source == "bundled"
                                      else _t("tei_stylesheets.source.downloaded", date=library.installed))
            folder = library.folder
        self.folder_label.setText(str(folder))
        self.folder_label.setCursorPosition(0)
        self.open_folder_btn.setEnabled(Path(folder).is_dir())
        self.licence_btn.setEnabled(library is not None and library.licence.is_file())
        last = last_check()
        self.checked_label.setText(last.isoformat() if last is not None else _t("tei_stylesheets.never"))
        self.check_btn.setEnabled(not busy())

    def state(self) -> dict:
        """Ce que montre la fenêtre (version, origine, dossier, vérification)."""
        return {"version": self.version_label.text(), "source": self.source_label.text(),
                "folder": self.folder_label.text(), "checked": self.checked_label.text()}

    def check(self):
        """« Rechercher une mise à jour »."""
        if busy():
            return
        check_for_update(self, done=self.refresh)
        self.refresh()

    def open_folder(self):
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_label.text()))

    def show_licence(self):
        library = self.library()
        if library is not None:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(library.licence)))
