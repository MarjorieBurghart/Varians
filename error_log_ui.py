# -*- coding: utf-8 -*-
"""Le journal des erreurs dans la fenêtre (V0.9.4.6) ; voir ``error_log``.

- ``install_for_application`` : appelé par ``editeur_tei.main``, ouvre le
  journal avec les versions de Varians, de PySide6 et de Qt, et fait dire à
  la barre d'état de chaque fenêtre qu'une erreur inattendue y a été notée ;
- ``open_log_folder`` : menu Aide → Journal des erreurs, ouvre le dossier du
  journal dans le gestionnaire de fichiers du système, pour l'envoyer avec
  un signalement.
"""
from __future__ import annotations

import threading

import PySide6
from PySide6.QtCore import QUrl, qVersion
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QApplication, QMainWindow, QMessageBox

import error_log
from app_context import APP_VERSION, tr as _t

# Durée du message de la barre d'état (ms).
MESSAGE_MSEC = 10_000


def install_for_application():
    """Ouvre le journal des erreurs de Varians (une fois) ; rend son chemin,
    ou None s'il ne peut pas être écrit."""
    path = error_log.install(f"Varians {APP_VERSION} ; PySide6 {PySide6.__version__} ; Qt {qVersion()}")
    if path is not None:
        error_log.remove_listener(_say_unexpected)
        error_log.add_listener(_say_unexpected)
    return path


def _say_unexpected(_exc):
    """Après une exception non rattrapée du fil principal : message dans la
    barre d'état des fenêtres de Varians."""
    if threading.current_thread() is not threading.main_thread() or QApplication.instance() is None:
        return
    for widget in QApplication.topLevelWidgets():
        if isinstance(widget, QMainWindow) and widget.isVisible():
            widget.statusBar().showMessage(_t("error_log.unexpected"), MESSAGE_MSEC)


def log_folder():
    """Dossier du journal : celui du journal ouvert, sinon celui que
    ``error_log.log_dir`` donne."""
    path = error_log.journal_path()
    return path.parent if path is not None else error_log.log_dir()


def open_log_folder(parent=None) -> bool:
    """Ouvre le dossier du journal (créé s'il manque) ; sinon le dit."""
    folder = log_folder()
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError:
        QMessageBox.warning(parent, _t("help.error_log"), _t("error_log.unavailable", folder=str(folder)))
        return False
    return bool(QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder))))
