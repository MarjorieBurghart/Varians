# -*- coding: utf-8 -*-
"""Red team 2 (cohérence des textes, D6, D7) : après un changement de langue,
aucun texte de la fenêtre ne reste dans l'ancienne langue.

Restaient en français : l'infobulle de « Générer viewer web » (menu), la
commande « Éditer cet élément TEI » de l'aperçu, l'infobulle de la feuille
XSLT, « XML bien formé ✓ » dans la barre d'état, « Image non chargée »
d'un panneau, et « lxml (XSLT en cache) » dans le compte rendu de
l'aperçu. La case « Retour à la ligne visuel » du fragment n'avait son
infobulle qu'après un changement de langue."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtGui import QAction
from PySide6.QtWidgets import (QAbstractButton, QComboBox, QGroupBox, QLabel, QLineEdit, QMenu, QTabWidget,
                               QWidget)

from app_context import tr

ROOT = Path(__file__).resolve().parents[2]


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {node.get("key"): "".join(node.itertext()).replace("\\n", "\n") for node in root.findall("string")}


def _french_phrases():
    """Morceaux des textes français (entre les variables) qui n'ont pas
    d'équivalent identique en anglais."""
    english = "\n".join(_catalog("en").values())
    phrases = set()
    for text in _catalog("fr").values():
        for part in re.split(r"[{}#\n]", text):
            part = part.strip(" :·—,.;()«»…")
            if len(part) >= 12 and part not in english and re.search(r"[a-zà-ÿ]{3}", part):
                phrases.add(part)
    return phrases


def _texts(window):
    texts = []
    for widget in window.findChildren(QWidget):
        texts.append(widget.toolTip())
    for action in window.findChildren(QAction):
        texts += [action.text(), action.toolTip(), action.iconText()]
    for label in window.findChildren(QLabel):
        texts.append(label.text())
    for button in window.findChildren(QAbstractButton):
        texts.append(button.text())
    for edit in window.findChildren(QLineEdit):
        texts.append(edit.placeholderText())
    for tabs in window.findChildren(QTabWidget):
        texts += [tabs.tabText(i) for i in range(tabs.count())] + [tabs.tabToolTip(i) for i in range(tabs.count())]
    for menu in window.findChildren(QMenu):
        texts.append(menu.title())
    for combo in window.findChildren(QComboBox):
        texts += [combo.itemText(i) for i in range(combo.count())]
    for group in window.findChildren(QGroupBox):
        texts.append(group.title())
    return [text for text in texts if text]


def test_switching_language_leaves_no_text_of_the_former_language(open_window, example_project, qtbot):
    window = open_window(example_project)
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: not view.dirty_preview, timeout=20000)
    window.validate_text()
    window._set_language_code("en")
    try:
        qtbot.waitUntil(lambda: not view.dirty_preview, timeout=20000)
        qtbot.wait(300)
        phrases = _french_phrases()
        texts = _texts(window)
        found = sorted({(phrase, text[:90]) for text in texts for phrase in phrases if phrase in text})
        assert found == [], "\n".join(map(str, found))
        assert window.xml_status.text() == tr("xml.valid")
        assert not any("en cache" in text for text in texts)
    finally:
        window._set_language_code("fr")


def test_the_wrap_box_has_the_same_tip_before_and_after_a_switch(open_window, example_project):
    window = open_window(example_project)
    box = window.formatted_view.fragment_visual_wrap
    assert box.toolTip() == box.text()
