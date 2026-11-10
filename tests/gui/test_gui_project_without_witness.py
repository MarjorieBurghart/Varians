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


# -- La fenêtre d'un projet sans témoin ---------------------------------------

import pytest


@pytest.fixture
def project_without_witness(tmp_path):
    from project_management import create_new_transcription_project
    return create_new_transcription_project(
        tmp_path / "sans_temoin", "Essai", [], "", ROOT, "fr", "en", xslt_mode="builtin", schema_mode="none")


def test_a_project_without_witness_opens_and_saves(open_window, project_without_witness, dialogs, qtbot):
    from app_context import tr
    window = open_window(project_without_witness)
    assert window.base_id == "" and window.panels == {} and window.base_panel is None
    assert window.structure_status.text() == tr("status.structure.no_witness")
    # L'édition se modifie et s'enregistre comme d'habitude.
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<p></p>") + 3)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("Incipit")
    assert window.save()
    assert "<p>Incipit</p>" in window.project.edition.read_text(encoding="utf-8")
    assert window.structure_status.text() == tr("status.structure.no_witness")


def test_refreshing_synchronizations_without_witness(open_window, project_without_witness, dialogs):
    window = open_window(project_without_witness)
    assert window.refresh_witness_synchronizations() is True    # sans boîte d'erreur
    assert window.base_panel is None


def test_the_preview_works_without_witness(open_window, project_without_witness, dialogs):
    window = open_window(project_without_witness)
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    assert "tei-edit://p/" in view.preview.toHtml()


def test_the_first_witness_gets_a_listwit_and_becomes_the_pivot(open_window, project_without_witness, dialogs):
    from app_context import tr
    edition = project_without_witness.parent / "xml" / "edition.xml"
    window = open_window(project_without_witness)

    def settings(dialog):
        dialog.witnesses_table.add_witness()
        dialog._accept()
        return dialog.result()

    dialogs.expect("dialog", settings)
    dialogs.expect("dialog", _fill_witness("T1", "Paris, BnF, latin 1234"))
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    try:
        assert dialogs.seen[-1][2] == (tr("project.settings.saved") + "\n\n"
                                       + tr("project.listwit.created", witnesses="T1"))
        text = edition.read_text(encoding="utf-8")
        assert "<bibl><!--" not in text and "scholarly digital edition" in text
        assert '<witness xml:id="T1">Paris, BnF, latin 1234</witness>' in text
        assert new_window.base_id == "T1" and new_window.base_panel is not None
        assert load_project(project_without_witness).base_witness == "T1"
    finally:
        new_window._force_close = True
        new_window.close()


def test_the_web_viewer_is_generated_without_text_choice(open_window, project_without_witness, dialogs):
    from PySide6.QtWidgets import QMessageBox
    from app_context import tr
    window = open_window(project_without_witness)
    # Pas de boîte « texte du viewer » : sans témoin, le texte établi.
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    window.generate_web_viewer()
    kind, title, text = dialogs.seen[-1]
    assert title == tr("webgen.done.title")
    before, after = tr("webgen.done.text_only", output="§").split("§")
    assert text.startswith(before) and text.endswith(after)
    output = Path(text[len(before):len(text) - len(after)])
    assert output.is_file() and output.parent == load_project(project_without_witness).web_output_dir
