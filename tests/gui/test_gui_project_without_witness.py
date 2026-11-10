# -*- coding: utf-8 -*-
"""Projet sans témoin : les boîtes « Nouveau projet… » et « Paramètres du
projet… » acceptent un tableau des témoins vide ; la préparation de la
transcription du témoin pivot n'est possible qu'avec un témoin."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QDialog

import app_context
from i18n import I18nManager
from project_config import load_project

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = [("fr", "Français")]


def _tr():
    manager = I18nManager(ROOT / "i18n", "fr", "en")
    app_context.set_i18n(manager)
    return manager.tr


def _fill_witness(siglum, label):
    def fill(dialog):
        dialog.id_edit.setText(siglum)
        dialog.label_edit.setText(label)
        dialog._accept()
        return dialog.result()
    return fill


def test_a_new_project_needs_no_witness(qapp, qtbot, tmp_path, dialogs):
    from project_dialogs import NewProjectDialog
    dlg = NewProjectDialog(_tr(), LANGUAGES)
    qtbot.addWidget(dlg)
    dlg.creation_mode.setCurrentIndex(dlg.creation_mode.findData("blank"))
    dlg.folder.edit.setText(str(tmp_path / "nouveau"))
    dlg.title_edit.setText("Essai")
    # Sans témoin, pas de transcription du pivot à préparer.
    assert not dlg.pivot_prepare.isEnabled()
    dlg._accept()                                  # aucune boîte d'avertissement
    assert dlg.result() == QDialog.DialogCode.Accepted
    values = dlg.values()
    assert values["witnesses"] == [] and values["base_witness"] == "" and values["prepare_pivot"] is False


def test_the_pivot_preparation_follows_the_witnesses(qapp, qtbot, dialogs):
    from project_dialogs import NewProjectDialog
    dlg = NewProjectDialog(_tr(), LANGUAGES)
    qtbot.addWidget(dlg)
    dlg.creation_mode.setCurrentIndex(dlg.creation_mode.findData("blank"))
    dialogs.expect("dialog", _fill_witness("A", "Manuscrit A"))
    dlg.witnesses_table.add_witness()
    assert dlg.pivot_prepare.isEnabled()
    dlg.pivot_prepare.setChecked(True)
    dlg.witnesses_table.table.setCurrentCell(0, 0)
    dlg.witnesses_table.remove_witness()
    assert not dlg.pivot_prepare.isEnabled()
    assert dlg.values()["prepare_pivot"] is False


def test_the_settings_accept_removing_every_witness(qapp, qtbot, example_project, dialogs):
    from project_dialogs import ProjectSettingsDialog
    dlg = ProjectSettingsDialog(_tr(), load_project(example_project), LANGUAGES)
    qtbot.addWidget(dlg)
    assert dlg.pivot_prepare.isEnabled()
    while dlg.witnesses_table.table.rowCount():
        dlg.witnesses_table.table.setCurrentCell(0, 0)
        dlg.witnesses_table.remove_witness()
    assert not dlg.pivot_prepare.isEnabled()
    dlg._accept()                                  # aucune boîte d'avertissement
    assert dlg.result() == QDialog.DialogCode.Accepted
    draft = dlg.draft()
    assert draft.witnesses == [] and draft.base_witness == ""
