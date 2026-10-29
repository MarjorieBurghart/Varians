# -*- coding: utf-8 -*-
"""Boîte « Générer viewer web » : choix du texte (V0.9.3.0).

Avant l'export, une boîte demande le texte du viewer : le texte établi (le
<lem>, à défaut la leçon du témoin choisi) ou le texte du témoin choisi ; la
liste des témoins commence par « Pivot (de chaque texte) ». Elle s'ouvre sur
le choix gardé dans project.xml ; un choix modifié y est enregistré ;
« Annuler » n'exporte rien. Le compte rendu donne le nombre de passages sans
leçon du témoin choisi."""
from __future__ import annotations

import re

from PySide6.QtWidgets import QDialog, QMessageBox

from app_context import tr
from project_config import load_project
from project_management import update_project_web_text


def _output(window):
    return window.project.web_output_dir / window.project.web_filename


def test_the_dialog_opens_on_the_choice_of_the_project_and_cancel_exports_nothing(open_window, example_project,
                                                                                    dialogs):
    update_project_web_text(example_project, "witness", "T2")
    before = example_project.read_text(encoding="utf-8")
    window = open_window(example_project)
    seen = {}

    def cancel(dialog):
        seen["title"] = dialog.windowTitle()
        seen["choice"] = dialog.choice()
        seen["items"] = [dialog.witness_box.itemText(i) for i in range(dialog.witness_box.count())]
        return QDialog.DialogCode.Rejected

    dialogs.expect("dialog", cancel)
    window.generate_web_viewer()
    assert seen["title"] == tr("webgen.text.title")
    assert seen["choice"] == ("witness", "T2")
    assert seen["items"][0] == tr("webgen.text.pivot") and len(seen["items"]) == 1 + len(window.project.witnesses)
    assert not _output(window).exists()
    assert example_project.read_text(encoding="utf-8") == before


def test_generate_keeps_the_choice_and_exports_with_it(open_window, example_project, dialogs):
    window = open_window(example_project)

    def choose(dialog):
        assert dialog.choice() == ("established", "")                    # sans réglage
        dialog.set_choice("witness", "P")
        return QDialog.DialogCode.Accepted

    dialogs.expect("dialog", choose)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # compte rendu : fermer
    window.generate_web_viewer()
    project = load_project(example_project)
    assert (project.web_text_mode, project.web_text_witness) == ("witness", "P")
    assert (window.project.web_text_mode, window.project.web_text_witness) == ("witness", "P")
    assert _output(window).is_file()
    before, after = tr("webgen.text.missing", count="§", witness="P").split("§")
    found = re.search(re.escape(before) + r"(\d+)" + re.escape(after), dialogs.seen[-1][2])
    assert found and int(found.group(1)) > 0


# --- Leçons hors <lem> surlignées (V0.9.3.1) -----------------------------------------------------
# Une case, active dans le texte établi seulement, fixe l'état de départ du
# surlignage ; elle s'ouvre sur le réglage de project.xml, qui garde le choix.

def test_the_highlight_box_follows_the_project_and_the_text_mode(open_window, example_project, dialogs):
    update_project_web_text(example_project, "established", "", highlight_nonlem=True)
    window = open_window(example_project)
    seen = {}

    def look(dialog):
        seen["label"] = dialog.highlight_box.text()
        seen["opened"] = (dialog.highlight_box.isChecked(), dialog.highlight_box.isEnabled(), dialog.highlight())
        dialog.witness_mode.setChecked(True)
        seen["witness"] = dialog.highlight_box.isEnabled()
        dialog.established.setChecked(True)
        seen["established"] = dialog.highlight_box.isEnabled()
        return QDialog.DialogCode.Rejected

    dialogs.expect("dialog", look)
    window.generate_web_viewer()
    assert seen["label"] == tr("webgen.text.highlight")
    assert seen["opened"] == (True, True, True)
    assert seen["witness"] is False and seen["established"] is True


def test_generate_keeps_the_highlight_and_exports_with_it(open_window, example_project, dialogs):
    window = open_window(example_project)

    def choose(dialog):
        assert dialog.highlight() is False                                 # sans réglage : non surligné
        dialog.set_choice("established", "", highlight=True)
        return QDialog.DialogCode.Accepted

    dialogs.expect("dialog", choose)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    window.generate_web_viewer()
    assert load_project(example_project).web_highlight_nonlem is True
    assert window.project.web_highlight_nonlem is True
    assert '"highlight":true' in _output(window).read_text(encoding="utf-8")
