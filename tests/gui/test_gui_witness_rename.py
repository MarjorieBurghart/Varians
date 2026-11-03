# -*- coding: utf-8 -*-
"""Changer le sigle d'un témoin depuis Fichier ▸ Paramètres du projet…
(V0.9.4.0).

- Le bouton « Changer le sigle… » des paramètres ouvre une boîte : nouveau
  sigle, « Aperçu » (fichiers modifiés et nombre de changements, fichiers
  renommés, citations du sigle à vérifier), « Appliquer ».
- « Appliquer » n'est possible qu'après un aperçu sans refus, pour le sigle
  affiché.
- Après l'application, le projet est rechargé ; les réglages d'affichage du
  témoin (bouton au livre, ordre…) le suivent.
- Le champ « Sigle » d'un témoin déjà enregistré n'est plus modifiable dans
  sa boîte : il renvoie au bouton (avant, changer le sigle en faisait un
  nouveau témoin, sans rien mettre à jour)."""
from __future__ import annotations

import json

from PySide6.QtCore import Qt


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _select(table, witness_id):
    for row in range(table.table.rowCount()):
        if table.witness_at(row).id == witness_id:
            table.table.selectRow(row)
            return row
    raise AssertionError(witness_id)


def _ask_rename(witness_id):
    def settings(dialog):
        _select(dialog.witnesses_table, witness_id)
        assert dialog.witnesses_table.rename_btn.isEnabled()
        dialog.witnesses_table.rename_btn.click()
        return dialog.result()
    return settings


def _rename_to(siglum, check=None):
    def rename(dialog):
        assert not dialog.apply_button.isEnabled()
        dialog.siglum_edit.setText(siglum)
        dialog.preview_button.click()
        if check is not None:
            check(dialog)
        if not dialog.apply_button.isEnabled():
            dialog.reject()
            return dialog.result()
        dialog.apply_button.click()
        return dialog.result()
    return rename


def _close(window):
    new_window = window._replacement_window
    if new_window is not None:
        new_window._force_close = True
        new_window.close()
    return new_window


def test_the_siglum_is_changed_from_the_project_settings(open_window, example_project, dialogs):
    from app_context import _settings
    root = example_project.parent
    window = open_window(example_project)
    key = window._view_settings_key("witnessLeadsEdition")
    _settings().setValue(key, json.dumps({"T1": True, "P": True}))
    previews = []

    def check(dialog):
        previews.append(dialog.preview.toPlainText())

    dialogs.expect("dialog", _ask_rename("P"))
    dialogs.expect("dialog", _rename_to("P2", check))
    dialogs.expect("information")
    window.project_settings_dialog()
    preview = previews[0]
    assert "xml/edition.xml" in preview and "project.xml" in preview
    assert "alignments/P.json → alignments/P2.json" in preview
    assert dialogs.seen[-1][2].startswith(_tr("witness_rename.done", old="P", new="P2", files=3, moves=1))
    new_window = window._replacement_window
    try:
        assert new_window is not None and window._force_close
        assert [w.id for w in new_window.project.witnesses] == ["T1", "T2", "P2"]
        assert "P2" in new_window.panels and "P" not in new_window.panels
        edition = (root / "xml" / "edition.xml").read_text(encoding="utf-8")
        assert 'edRef="#P2"' in edition and 'edRef="#P"' not in edition
        assert (root / "alignments" / "P2.json").is_file() and not (root / "alignments" / "P.json").exists()
        assert (root / "xml" / "edition.xml.bak").is_file()
        assert json.loads(_settings().value(key)) == {"T1": True, "P2": True}
        assert new_window.panels["P2"].leads_edition
    finally:
        _close(window)


def test_a_refused_siglum_cannot_be_applied(open_window, example_project, dialogs):
    root = example_project.parent
    before = (root / "xml" / "edition.xml").read_text(encoding="utf-8")
    window = open_window(example_project)
    seen = []

    def check(dialog):
        seen.append((dialog.apply_button.isEnabled(), dialog.preview.toPlainText()))

    dialogs.expect("dialog", _ask_rename("P"))
    dialogs.expect("dialog", _rename_to("t1", check))
    window.project_settings_dialog()
    enabled, preview = seen[0]
    assert not enabled
    assert _tr("witness_rename.taken", siglum="t1", witness="T1") in preview
    assert window._replacement_window is None
    assert (root / "xml" / "edition.xml").read_text(encoding="utf-8") == before


def test_a_new_preview_is_needed_after_editing_the_siglum(qtbot, open_window, example_project):
    from witness_rename_ui import WitnessRenameDialog
    window = open_window(example_project)
    dialog = WitnessRenameDialog(_tr, window.project, "P", window)
    qtbot.addWidget(dialog)
    assert dialog.siglum_edit.text() == "P" and not dialog.apply_button.isEnabled()
    dialog.siglum_edit.setText("P2")
    dialog.preview_button.click()
    assert dialog.apply_button.isEnabled() and dialog.plan.new_id == "P2"
    dialog.siglum_edit.setText("P3")
    assert not dialog.apply_button.isEnabled()
    assert dialog.preview.toPlainText() == _tr("witness_rename.preview_needed")
    dialog.siglum_edit.setText("1761")
    assert dialog.xml_id_hint.text() == _tr("project.witness.xml_id", id="_1761")


def test_other_pending_settings_come_first(open_window, example_project, dialogs):
    window = open_window(example_project)

    def settings(dialog):
        dialog.title_edit.setText("Autre titre")
        _select(dialog.witnesses_table, "P")
        dialog.witnesses_table.rename_btn.click()
        assert dialog.result() == 0 and dialog.rename_witness_id is None
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", settings)
    dialogs.expect("information")
    window.project_settings_dialog()
    assert dialogs.seen[-1][2] == _tr("witness_rename.pending_settings")


def test_the_siglum_of_a_saved_witness_is_locked_in_its_box(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = []

    def witness(dialog):
        seen.append((dialog.id_edit.isReadOnly(), dialog.siglum_lock_hint.text(),
                     dialog.siglum_lock_hint.isHidden()))
        dialog.reject()
        return dialog.result()

    def settings(dialog):
        table = dialog.witnesses_table
        _select(table, "P")
        table.edit_witness()
        table.add_witness()
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", settings)
    dialogs.expect("dialog", witness)
    dialogs.expect("dialog", witness)
    window.project_settings_dialog()
    assert seen[0] == (True, _tr("witness_rename.locked"), False)
    assert seen[1][0] is False and seen[1][2] is True


def test_the_rename_button_is_only_in_the_project_settings(qtbot):
    from app_context import tr
    from project_dialogs import WitnessTable
    from project_management import WitnessDraft
    table = WitnessTable(tr, [WitnessDraft("T1", "Troyes 816")], "T1")
    qtbot.addWidget(table)
    assert table.rename_btn is None
    table = WitnessTable(tr, [WitnessDraft("T1", "Troyes 816")], "T1", saved_ids={"T1"})
    qtbot.addWidget(table)
    assert table.rename_btn.text() == tr("witness_rename.button")
    assert not table.rename_btn.isEnabled()
    table.table.selectRow(0)
    assert table.rename_btn.isEnabled()
    assert table.table.item(0, 0).data(Qt.ItemDataRole.UserRole + 1) == "T1"


def test_a_detached_witness_stays_detached_under_its_new_siglum(qtbot, open_window, example_project, dialogs):
    from app_context import _settings
    from corpus_data import add_page_witness
    add_page_witness(example_project, "M", ["45r", "45v"])
    window = open_window(example_project)
    assert window._detach_witness("M")
    dialogs.expect("dialog", _ask_rename("M"))
    dialogs.expect("dialog", _rename_to("M2"))
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    try:
        assert (example_project.parent / "images" / "M2" / "0001.png").is_file()
        # Fenêtres détachées rétablies après la construction (call_later).
        qtbot.waitUntil(lambda: "M2" in new_window._detached_windows, timeout=5000)
        assert "M" not in new_window._detached_windows
        key = new_window._view_settings_key
        assert json.loads(_settings().value(key("detachedWitnesses"))) == ["M2"]
        # La fenêtre détachée de l'ancienne fenêtre, fermée après coup, n'a
        # pas réécrit l'ancien identifiant.
        assert _settings().value(key("floatingGeometry/M2")) is not None
        assert not _settings().contains(key("floatingGeometry/M"))
    finally:
        _close(window)


class _Crash(BaseException):
    """Arrêt brutal de Varians ou de l'ordinateur."""


def test_an_interrupted_change_is_undone_when_the_project_opens(open_window, example_project, dialogs,
                                                                 monkeypatch):
    import save_io
    import witness_rename
    from project_config import load_project
    root = example_project.parent
    edition = root / "xml" / "edition.xml"
    before = edition.read_text(encoding="utf-8")
    plan = witness_rename.plan_witness_rename(load_project(example_project), "P", "P2")
    write = save_io.atomic_write_text_with_backup
    calls = []

    def crash_on_the_third(path, text, **kwargs):
        calls.append(path)
        if len(calls) == 3:
            raise _Crash()
        return write(path, text, **kwargs)

    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", crash_on_the_third)
    try:
        witness_rename.apply_witness_rename(plan)
    except _Crash:
        pass
    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", write)
    assert 'edRef="#P2"' in edition.read_text(encoding="utf-8")
    from PySide6.QtWidgets import QMessageBox
    dialogs.expect("question", QMessageBox.StandardButton.Yes)
    dialogs.expect("information")
    window = open_window(example_project)
    assert dialogs.seen[-2][2] == _tr("witness_rename.recover_question", old="P", new="P2")
    assert dialogs.seen[-1][2] == _tr("witness_rename.recovered", old="P", new="P2")
    assert edition.read_text(encoding="utf-8") == before
    assert [w.id for w in window.project.witnesses] == ["T1", "T2", "P"]
    assert not witness_rename.journal_path(root).exists()


def test_a_failed_reload_never_leaves_the_old_documents_open(open_window, example_project, dialogs,
                                                             monkeypatch, editor_module):
    root = example_project.parent
    window = open_window(example_project)
    # Texte non enregistré, écarté à la question « Enregistrer ? » : il ne
    # doit jamais être réécrit par-dessus le projet changé.
    window.editor.insertPlainText("<!-- brouillon -->")

    def refuse(*_args, **_kwargs):
        raise OSError("projet illisible")

    from PySide6.QtWidgets import QMessageBox
    dialogs.expect("question", QMessageBox.StandardButton.Discard)
    dialogs.expect("dialog", _ask_rename("P"))
    dialogs.expect("question", QMessageBox.StandardButton.Discard)
    dialogs.expect("dialog", _rename_to("P2"))
    dialogs.expect("information")
    dialogs.expect("critical")
    monkeypatch.setattr(editor_module, "load_project", refuse)
    window.project_settings_dialog()
    replacement = window._replacement_window
    try:
        assert type(replacement).__name__ == "WelcomeWindow"
        assert window._force_close and not window.isVisible()
        assert 'edRef="#P2"' in (root / "xml" / "edition.xml").read_text(encoding="utf-8")
        assert "brouillon" not in (root / "xml" / "edition.xml").read_text(encoding="utf-8")
    finally:
        replacement.close()



def _interrupt(example_project, monkeypatch):
    """Changement P → P2 interrompu après deux fichiers écrits."""
    import save_io
    import witness_rename
    from project_config import load_project
    plan = witness_rename.plan_witness_rename(load_project(example_project), "P", "P2")
    write = save_io.atomic_write_text_with_backup
    calls = []

    def crash_on_the_third(path, text, **kwargs):
        calls.append(path)
        if len(calls) == 3:
            raise _Crash()
        return write(path, text, **kwargs)

    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", crash_on_the_third)
    try:
        witness_rename.apply_witness_rename(plan)
    except _Crash:
        pass
    monkeypatch.setattr(save_io, "atomic_write_text_with_backup", write)


def test_the_recovery_can_be_put_off(open_window, example_project, dialogs, monkeypatch):
    import witness_rename
    from PySide6.QtWidgets import QMessageBox
    _interrupt(example_project, monkeypatch)
    dialogs.expect("question", QMessageBox.StandardButton.No)
    open_window(example_project)
    assert witness_rename.journal_path(example_project.parent).is_file()


def test_a_journal_from_elsewhere_is_set_aside_at_opening(open_window, example_project, dialogs, tmp_path):
    import witness_rename
    outside = tmp_path / "ailleurs.txt"
    outside.write_text("à moi", encoding="utf-8")
    path = witness_rename.journal_path(example_project.parent)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"format": 1, "old": "P", "new": "P2", "files": [], "moves": [
        {"source": str(outside), "target": "xml/edition.xml"}]}), encoding="utf-8")
    dialogs.expect("warning")
    window = open_window(example_project)
    assert dialogs.seen[-1][2] == _tr("witness_rename.journal_rejected")
    assert outside.read_text(encoding="utf-8") == "à moi"
    assert (example_project.parent / "xml" / "edition.xml").is_file() and window.project is not None
    assert not path.exists()


def test_enter_in_the_siglum_field_shows_the_preview_only(qtbot, open_window, example_project):
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QDialog
    from witness_rename_ui import WitnessRenameDialog
    window = open_window(example_project)
    dialog = WitnessRenameDialog(_tr, window.project, "P", window)
    qtbot.addWidget(dialog)
    dialog.show()
    QTest.qWaitForWindowExposed(dialog)
    dialog.siglum_edit.setFocus()
    dialog.siglum_edit.selectAll()
    QTest.keyClicks(dialog.siglum_edit, "P2")
    QTest.keyClick(dialog.siglum_edit, Qt.Key.Key_Return)
    assert dialog.result() != QDialog.DialogCode.Accepted and dialog.isVisible()
    assert dialog.apply_button.isEnabled() and "xml/edition.xml" in dialog.preview.toPlainText()
    assert dialog.preview_button.isDefault() and not dialog.apply_button.isDefault()


def test_a_failed_preview_says_so(qtbot, open_window, example_project, monkeypatch):
    import witness_rename_ui
    from witness_rename_ui import WitnessRenameDialog
    window = open_window(example_project)
    dialog = WitnessRenameDialog(_tr, window.project, "P", window)
    qtbot.addWidget(dialog)

    def broken(*_args):
        raise RuntimeError("aperçu impossible")

    monkeypatch.setattr(witness_rename_ui, "plan_witness_rename", broken)
    dialog.siglum_edit.setText("P2")
    dialog.preview_button.click()
    assert not dialog.apply_button.isEnabled()
    assert dialog.preview.toPlainText() == _tr("witness_rename.preview_error", error="aperçu impossible")


def test_the_preview_reads_the_project_as_it_is_on_disk(qtbot, open_window, example_project):
    from witness_rename_ui import WitnessRenameDialog
    window = open_window(example_project)
    example_project.write_text(example_project.read_text(encoding="utf-8").replace(
        "</witnesses>", '<witness id="P2" label="P2 · Poitiers" /></witnesses>'), encoding="utf-8")
    dialog = WitnessRenameDialog(_tr, window.project, "P", window)
    qtbot.addWidget(dialog)
    dialog.siglum_edit.setText("P2")
    dialog.preview_button.click()
    assert not dialog.apply_button.isEnabled()
    assert _tr("witness_rename.taken", siglum="P2", witness="P2") in dialog.preview.toPlainText()


def test_downloads_in_progress_stop_the_change(open_window, example_project, dialogs):
    from types import SimpleNamespace
    root = example_project.parent
    before = (root / "xml" / "edition.xml").read_text(encoding="utf-8")
    window = open_window(example_project)
    window._iiif_download_dialog = SimpleNamespace(
        shutdown=lambda: None, thread=SimpleNamespace(isRunning=lambda: True))
    dialogs.expect("dialog", _ask_rename("P"))
    dialogs.expect("dialog", _rename_to("P2"))
    dialogs.expect("critical")
    window.project_settings_dialog()
    assert dialogs.seen[-1][2] == _tr("witness_rename.downloads_running")
    assert (root / "xml" / "edition.xml").read_text(encoding="utf-8") == before
    window._iiif_download_dialog = None


def test_an_unexpected_error_is_reported(open_window, example_project, dialogs, monkeypatch):
    import witness_rename_ui
    window = open_window(example_project)

    def broken(_plan):
        raise RuntimeError("disque débranché")

    monkeypatch.setattr(witness_rename_ui, "apply_witness_rename", broken)
    dialogs.expect("dialog", _ask_rename("P"))
    dialogs.expect("dialog", _rename_to("P2"))
    dialogs.expect("critical")
    window.project_settings_dialog()
    assert dialogs.seen[-1][2] == _tr("witness_rename.error", error="disque débranché")
    assert window._replacement_window is None
