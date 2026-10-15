# -*- coding: utf-8 -*-
"""Diagnostic et rechargement des ressources des témoins dans la vraie fenêtre."""
from __future__ import annotations


def test_witness_diagnostics_lists_each_witness(open_window, example_project, dialogs):
    window = open_window(example_project)
    rows = []
    dialogs.expect("dialog", lambda dialog: rows.append(dialog.table.rowCount()) or 0)
    window.show_witness_diagnostics()
    assert rows == [len(window.witness_configs)]


def test_refresh_unchanged_resources_keeps_editor_and_panels(open_window, example_project):
    window = open_window(example_project)
    text = window.editor.toPlainText()
    panels = dict(window.panels)
    assert window.refresh_witness_synchronizations() is True
    assert window.editor.toPlainText() == text
    assert window.modified is False
    assert all(window.panels[wid] is panel for wid, panel in panels.items())


def test_refresh_with_changed_sync_asks_confirmation(open_window, example_project, dialogs):
    import json
    from pathlib import Path
    from PySide6.QtWidgets import QMessageBox

    window = open_window(example_project)
    alignment = Path(example_project).parent / "alignments" / "T2.json"
    data = json.loads(alignment.read_text(encoding="utf-8"))
    # Retirer les correspondances d'une ligne du témoin T2.
    for page in data.get("pages", []):
        for line in page.get("lines", []):
            if line.get("base_keys"):
                line["base_keys"] = []
                break
        else:
            continue
        break
    alignment.write_text(json.dumps(data), encoding="utf-8")

    dialogs.expect("question", QMessageBox.StandardButton.No)
    assert window.refresh_witness_synchronizations() is False
