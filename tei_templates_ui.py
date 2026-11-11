# -*- coding: utf-8 -*-
"""Fenêtre « Modèles de document TEI » et mises à jour des squelettes TEI.

Comme pour les TEI Stylesheets (tei_stylesheets_ui) :

- ``TeiTemplatesDialog`` : la version de TEI P5 des squelettes qui servent
  (``tei_templates.current``), son origine, son dossier, sa licence, la
  dernière vérification, et « Rechercher une mise à jour ». Le bouton
  « Modèles TEI… » de la boîte « Nouveau document XML » l'ouvre.
- ``at_launch(window)`` : au lancement de Varians, supprime les versions qui
  ne servent plus, puis, si la dernière vérification (réglage
  ``LAST_CHECK_SETTING``) date d'au moins ``CHECK_INTERVAL_DAYS`` jours,
  demande la dernière version de TEI P5. Sans nouveauté ou sans réseau, rien
  n'est dit.
- Une nouvelle version est proposée (« Installer » ou « Plus tard » : la
  question revient à la vérification suivante). L'installation (lecture des
  seuls squelettes dans l'archive publiée, quelques Mo) montre une fenêtre de
  progression, avec Annuler, puis un message dans la barre d'état. Les
  nouveaux squelettes servent dès le « Nouveau document XML » suivant.

Le réseau n'est lu que dans un fil à part ; le résultat revient au fil
principal par un signal Qt (``_Task``). ``busy()`` dit si une vérification
ou une installation est en cours.
"""
from __future__ import annotations

import datetime
import threading

import shiboken6
from PySide6.QtCore import QObject, Qt, QUrl, Signal, Slot
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel,
                               QLineEdit, QMessageBox, QProgressDialog, QPushButton, QVBoxLayout)

import tei_templates
from app_context import _settings, tr as _t
from tei_stylesheets import LibraryError, is_newer

LAST_CHECK_SETTING = "teiTemplates/lastCheck"
CHECK_INTERVAL_DAYS = 30
# Codes d'erreur qui ont un message (``tei_templates.error.<code>``) ;
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
    """Au lancement : versions inutiles supprimées, puis vérification si elle
    est due (voir la docstring du module)."""
    tei_templates.remove_old_versions()
    if check_due(today):
        return check_for_update(window, automatic=True)
    return None


def error_text(error) -> str:
    """Message d'une ``LibraryError`` dans la langue de l'interface ; un code
    sans message (hors ``ERROR_CODES``) prend celui d'une erreur de réseau."""
    code = error.code if error.code in ERROR_CODES else "network"
    return _t(f"tei_templates.error.{code}", detail=error.detail or error.code)


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
    QMessageBox.information(QApplication.activeWindow(), _t("tei_templates.title"), text)


class _Task(QObject):
    """``work(progress)`` dans un fil à part ; ``finished(résultat, erreur)``
    et ``progress(fait, total)`` sont appelés dans le fil principal."""

    _progressed = Signal(int, int)
    _completed = Signal(object, object)

    def __init__(self, work, finished, progress=None):
        super().__init__()
        self._work, self._finished, self._progress = work, finished, progress
        self._progressed.connect(self._on_progress)
        self._completed.connect(self._on_completed)

    def start(self):
        """Lance ``work`` dans un fil à part ; la tâche reste dans ``_RUNNING``
        jusqu'à sa fin. Renvoie la tâche."""
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
        _RUNNING.discard(self)
        self._finished(result, error)


# --- Vérification et installation -------------------------------------------------------------

def check_for_update(parent, automatic=False, done=None):
    """Demande la dernière version de TEI P5, puis propose d'en installer les
    squelettes si elle est plus récente. ``automatic`` (au lancement) : rien
    n'est dit sans nouveauté ni réseau. ``done(installée ou None)`` : appelé
    à la fin."""
    _settings().setValue(LAST_CHECK_SETTING, datetime.date.today().isoformat())

    def finished(latest, error):
        widget = _parent(parent)
        current = tei_templates.current().version
        title = _t("tei_templates.title")
        if error is not None:
            if not automatic:
                QMessageBox.warning(widget, title, error_text(error))
        elif not is_newer(latest, current):
            if not automatic:
                QMessageBox.information(widget, title, _t("tei_templates.up_to_date", version=current))
        elif _consent(widget, latest, current):
            install(widget, latest, done)
            return
        if done is not None:
            done(None)

    return _Task(lambda _progress: tei_templates.latest_version(), finished).start()


def _consent(parent, version, current):
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Question)
    box.setWindowTitle(_t("tei_templates.title"))
    box.setText(_t("tei_templates.available", version=version, current=current))
    box.setInformativeText(_t("tei_templates.available.detail"))
    install_btn = box.addButton(_t("tei_stylesheets.install"), QMessageBox.ButtonRole.AcceptRole)
    later_btn = box.addButton(_t("tei_stylesheets.later"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(install_btn)
    box.setEscapeButton(later_btn)
    box.exec()
    return box.clickedButton() is install_btn


def install(parent, version, done=None):
    """Lit et installe les squelettes de ``version``, avec une fenêtre de
    progression et Annuler. ``done(installée ou None)`` : appelé à la fin."""
    global _PROGRESS
    cancel = threading.Event()
    progress = QProgressDialog(_t("tei_templates.downloading", version=version), _t("common.cancel"), 0, 0, parent)
    progress.setWindowTitle(_t("tei_templates.title"))
    progress.setMinimumWidth(460)
    progress.setWindowModality(Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)
    progress.setAutoClose(False)
    progress.setAutoReset(False)
    progress.canceled.connect(cancel.set)                       # Annuler
    progress.rejected.connect(cancel.set)                       # Échap
    _PROGRESS = progress
    progress.show()

    def step(done_count, total):
        if not _alive(progress):
            return
        if done_count < 0:
            progress.setLabelText(_t("tei_templates.installing", version=version))
            progress.setRange(0, 0)
        elif total > 0:
            progress.setRange(0, total)
            progress.setValue(min(done_count, total))

    def finished(installed, error):
        global _PROGRESS
        _PROGRESS = None
        if _alive(progress):
            progress.close()
            progress.deleteLater()
        widget = _parent(parent)
        if error is not None and error.code == "cancelled":
            _status(widget, _t("tei_templates.cancelled"))
        elif error is not None:
            QMessageBox.warning(widget, _t("tei_templates.title"), error_text(error))
        else:
            _status(widget, _t("tei_templates.installed", version=installed.version))
        if done is not None:
            done(installed)

    def work(report):
        return tei_templates.download_and_install(version, report, cancel.is_set)

    return _Task(work, finished, step).start()


# --- La fenêtre -------------------------------------------------------------------------------

class TeiTemplatesDialog(QDialog):
    """« Modèles TEI… » de la boîte « Nouveau document XML »."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("tei_templates.title"))
        self.setMinimumWidth(560)
        layout = QVBoxLayout(self)
        intro = QLabel(_t("tei_templates.intro"), self)
        intro.setWordWrap(True)
        layout.addWidget(intro)
        form = QFormLayout()
        self.version_label = QLabel(self)
        self.source_label = QLabel(self)
        self.folder_label = QLineEdit(self)                     # un long chemin : lu en entier
        self.folder_label.setReadOnly(True)
        self.open_folder_btn = QPushButton(_t("common.open_folder"), self)
        self.open_folder_btn.clicked.connect(self.open_folder)
        self.licence_label = QLabel(_t("tei_templates.licence.text"), self)
        self.licence_label.setWordWrap(True)
        self.licence_btn = QPushButton(_t("tei_stylesheets.show_licence"), self)
        self.licence_btn.clicked.connect(self.show_licence)
        self.checked_label = QLabel(self)
        form.addRow(_t("tei_templates.version"), self.version_label)
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

    def refresh(self, *_args):
        """Met à jour ce que montre la fenêtre ; « Rechercher une mise à
        jour » est grisé pendant une vérification ou une installation. Sert
        aussi de rappel ``done`` ; sans effet si la fenêtre est détruite."""
        if not _alive(self):
            return
        current = tei_templates.current()
        self.version_label.setText(current.version)
        self.source_label.setText(_t("tei_templates.source.bundled") if current.source == "bundled"
                                  else _t("tei_templates.source.downloaded", date=current.installed))
        self.folder_label.setText(str(current.folder))
        self.folder_label.setCursorPosition(0)
        self.open_folder_btn.setEnabled(current.folder.is_dir())
        self.licence_btn.setEnabled(current.licence.is_file())
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
        """« Ouvrir le dossier » : le dossier montré, dans le gestionnaire de
        fichiers du système."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(self.folder_label.text()))

    def show_licence(self):
        """« Voir la licence » : la licence des squelettes qui servent."""
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(tei_templates.current().licence)))
