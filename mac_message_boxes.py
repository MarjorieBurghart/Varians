# -*- coding: utf-8 -*-
"""Titre des boîtes de message sous macOS (V0.9.4.6).

Sous macOS, Qt n'affiche pas le titre d'une boîte de message :
``QMessageBox.setWindowTitle`` n'y fait rien, selon les règles d'Apple, et
les fonctions toutes faites (``question``, ``warning``, ``information``,
``critical``) le perdent de même. « Document non valide », « Fichier très
volumineux », « Fichier modifié hors de Varians »… n'étaient donc pas vus.

Sous macOS seulement, ``install`` (appelé au démarrage par
``editeur_tei.py``) fait du titre le message principal de la boîte, en gras,
et passe le texte en dessous (texte informatif), comme une alerte du Mac.
Ailleurs, rien ne change. Le titre est retenu dans une propriété de la boîte
(``title_of``), que Qt garde même sous macOS ; les boîtes des fonctions
toutes faites sont construites ici pour la même raison."""
from __future__ import annotations

import html
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QMessageBox

TITLE_PROPERTY = "variansTitle"
_SHOWN_PROPERTY = "variansTitleShown"
BUTTON = QMessageBox.StandardButton
_READY_MADE = {
    "question": (QMessageBox.Icon.Question, BUTTON.Yes | BUTTON.No),
    "warning": (QMessageBox.Icon.Warning, BUTTON.Ok),
    "information": (QMessageBox.Icon.Information, BUTTON.Ok),
    "critical": (QMessageBox.Icon.Critical, BUTTON.Ok),
}
_installed = {}


def title_of(box):
    """Titre donné à ``box``, même sous macOS, où Qt ne le retient pas."""
    title = box.property(TITLE_PROPERTY)
    return str(title) if title else box.windowTitle()


def present(box):
    """Le titre de ``box`` devient son message principal ; son texte (et son
    texte informatif) passe en dessous. Une seule fois par boîte."""
    title = box.property(TITLE_PROPERTY)
    if not title or box.property(_SHOWN_PROPERTY):
        return
    text, more = box.text(), box.informativeText()
    rich = box.textFormat() == Qt.TextFormat.RichText
    box.setText(html.escape(str(title)) if rich else str(title))
    box.setInformativeText("\n\n".join(part for part in (text, more) if part))
    box.setProperty(_SHOWN_PROPERTY, True)


def wrappers():
    """Ce que ``install`` met sur ``QMessageBox`` : ``setWindowTitle`` (le
    titre retenu), ``exec`` (le titre montré) et les fonctions toutes faites,
    à partir de ce qui y est à cet instant."""
    set_window_title = QMessageBox.setWindowTitle
    exec_box = QMessageBox.exec

    def remember_title(box, title):
        box.setProperty(TITLE_PROPERTY, title)
        set_window_title(box, title)

    def show_title(box):
        present(box)
        return exec_box(box)

    def ready_made(icon, default_buttons):
        def show(parent, title, text, buttons=default_buttons, defaultButton=BUTTON.NoButton):
            box = QMessageBox(icon, "", text, buttons, parent)
            box.setWindowTitle(title)
            if defaultButton != BUTTON.NoButton:
                box.setDefaultButton(defaultButton)
            return BUTTON(box.exec())
        return staticmethod(show)

    result = {"setWindowTitle": remember_title, "exec": show_title}
    for name, (icon, default_buttons) in _READY_MADE.items():
        result[name] = ready_made(icon, default_buttons)
    return result


def installed():
    """Vrai si la couche macOS est en place."""
    return bool(_installed)


def install(platform=None):
    """Sous macOS (``platform`` : ``sys.platform`` par défaut), met la couche
    en place, une seule fois ; rend vrai si elle vient de l'être."""
    if (platform or sys.platform) != "darwin" or _installed:
        return False
    for name, value in wrappers().items():
        _installed[name] = QMessageBox.__dict__.get(name, getattr(QMessageBox, name))
        setattr(QMessageBox, name, value)
    return True
