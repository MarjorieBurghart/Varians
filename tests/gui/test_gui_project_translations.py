# -*- coding: utf-8 -*-
"""Traductions d'un projet. Un projet garde sa copie des catalogues
(dossier i18n/), prioritaire ; sans ce dossier, il suit ceux de Varians.
C'est le conseil donné aux projets créés avant la V0.8.8.0 pour adopter
« témoin pivot »."""
from __future__ import annotations

import shutil

from app_context import tr


def test_project_copy_of_the_catalogs_keeps_priority(open_window, example_project):
    catalog = example_project.parent / "i18n" / "fr.xml"
    text = catalog.read_text(encoding="utf-8")
    catalog.write_text(text.replace('<string key="project.witness.base">Pivot</string>',
                                    '<string key="project.witness.base">Manuscrit pivot</string>'),
                       encoding="utf-8")
    open_window(example_project)
    assert tr("project.witness.base") == "Manuscrit pivot"


def test_project_without_its_translation_folder_uses_those_of_varians(open_window, example_project):
    shutil.rmtree(example_project.parent / "i18n")
    window = open_window(example_project)
    assert tr("project.witness.base") == "Pivot"
    assert "témoin pivot" in tr("manuscript.no_match")
    assert window.action_check_references.text() == "Références"
    window._set_language_code("en")
    assert window.action_check_references.text() == "References"


def test_the_standard_texts_of_qt_follow_the_interface_language(open_window, sermons_project):
    """Boutons et textes standard de Qt (« Montrer les détails… » d'une boîte
    de message, « Fermer »…) : traductions de Qt dans la langue de l'interface."""
    from PySide6.QtCore import QCoreApplication

    def details():
        return QCoreApplication.translate("QMessageBox", "Show Details...")

    window = open_window(sermons_project)
    assert details() == "Montrer les détails…"
    assert QCoreApplication.translate("QPlatformTheme", "Close") == "Fermer"
    window._set_language_code("de")
    assert details() == "Details einblenden..."
    window._set_language_code("en")
    assert details() == "Show Details..."
