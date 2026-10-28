# -*- coding: utf-8 -*-
"""Contexte partagé de l'application Varians.

Traductions actives (avec celles de Qt, ``apply_qt_language``), réglages
QSettings et projets récents. Ces services
étaient définis dans ``editeur_tei.py`` ; ils sont regroupés ici pour que les
modules de l'interface (panneaux, menus, etc.) puissent les importer sans
importer ``editeur_tei`` lui-même. Ce dernier peut en effet être exécuté comme
script (``__main__``) : l'importer depuis un autre module en chargerait une
seconde copie, avec ses propres traductions.
"""
from __future__ import annotations

from pathlib import Path

import shiboken6
from PySide6.QtCore import QCoreApplication, QLibraryInfo, QSettings, QTimer, QTranslator

HERE = Path(__file__).resolve().parent
APP_VERSION = "0.9.2.8"

# --- Traductions --------------------------------------------------------------

_i18n = None


def set_i18n(manager) -> None:
    """Déclare le gestionnaire de traductions actif (I18nManager)."""
    global _i18n
    _i18n = manager


def current_i18n():
    return _i18n


def tr(key, default=None, **values):
    """Texte traduit dans la langue active (équivalent de ``_t``)."""
    return _i18n.tr(key, default=default, **values)


_qt_translator = None


def apply_qt_language(code) -> bool:
    """Textes standard de Qt dans la langue ``code`` de l'interface :
    boutons des boîtes (« Fermer », « Annuler »…), « Montrer les détails… »,
    menus contextuels des champs, boîtes de fichiers. Ce sont les traductions
    livrées avec Qt (``qtbase_<code>.qm``) ; sans traduction pour ``code``,
    Qt reste en anglais. Rend vrai si une traduction est installée."""
    global _qt_translator
    app = QCoreApplication.instance()
    if app is None:
        return False
    if _qt_translator is not None:
        app.removeTranslator(_qt_translator)
        _qt_translator = None
    translator = QTranslator(app)
    folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
    if not code or not translator.load(f"qtbase_{code}", folder):
        return False
    app.installTranslator(translator)
    _qt_translator = translator
    return True


def error_message(exc) -> str:
    """Texte d'une exception pour l'interface : traduit lorsqu'elle porte une
    clé des catalogues (``project_config.ProjectConfigError``), sinon tel quel."""
    key = getattr(exc, "key", None)
    if key:
        return tr(key, default=str(exc), **getattr(exc, "values", {}))
    return str(exc)


# --- Appels différés -----------------------------------------------------------


def call_later(msec, owner, callback) -> None:
    """Comme ``QTimer.singleShot(msec, callback)``, sans effet si ``owner`` (un
    QObject, en général la fenêtre) a été détruit entre-temps."""
    def guarded():
        if shiboken6.isValid(owner):
            callback()

    QTimer.singleShot(int(msec), guarded)


# --- Réglages locaux (QSettings) ------------------------------------------------

SETTINGS_ORGANIZATION = "TEIManuscriptTools"
SETTINGS_APPLICATION = "GenericTEIManuscriptEditor"
MAX_RECENT_PROJECTS = 10


# Fichier de réglages imposé (fichier INI). ``None`` : emplacement standard du
# système (registre sous Windows, ~/.config sous Linux, etc.). Utilisé par les
# tests pour ne jamais toucher aux réglages réels de l'utilisateur.
SETTINGS_FILE_OVERRIDE = None


def _settings():
    if SETTINGS_FILE_OVERRIDE is not None:
        return QSettings(str(SETTINGS_FILE_OVERRIDE), QSettings.Format.IniFormat)
    # Identifiants stables et indépendants de la langue affichée.
    return QSettings(SETTINGS_ORGANIZATION, SETTINGS_APPLICATION)


def recent_project_paths():
    value = _settings().value("recentProjects", [])
    if isinstance(value, str):
        value = [value]
    result = []
    seen = set()
    for raw in value or []:
        try:
            path = str(Path(raw).expanduser().resolve())
        except Exception:
            continue
        if path not in seen:
            seen.add(path); result.append(path)
    return result[:MAX_RECENT_PROJECTS]


def remember_recent_project(path):
    path = str(Path(path).expanduser().resolve())
    values = [p for p in recent_project_paths() if p != path]
    values.insert(0, path)
    _settings().setValue("recentProjects", values[:MAX_RECENT_PROJECTS])


def remove_recent_project(path):
    target = str(Path(path).expanduser().resolve())
    _settings().setValue("recentProjects", [p for p in recent_project_paths() if p != target])


def clear_recent_projects():
    _settings().remove("recentProjects")


def last_open_project_path():
    """Projet à rouvrir au démarrage s'il était encore ouvert à la fermeture.

    Cette préférence est volontairement distincte de la liste des récents :
    « Fermer le projet » l'efface, tandis que quitter l'application avec un
    projet ouvert la conserve.
    """
    raw = _settings().value("lastOpenProject", "")
    if not raw:
        return None
    try:
        path = Path(str(raw)).expanduser().resolve()
    except Exception:
        _settings().remove("lastOpenProject")
        return None
    if not path.is_file():
        _settings().remove("lastOpenProject")
        return None
    return path


def remember_open_project(path):
    _settings().setValue("lastOpenProject", str(Path(path).expanduser().resolve()))


def forget_open_project():
    _settings().remove("lastOpenProject")
