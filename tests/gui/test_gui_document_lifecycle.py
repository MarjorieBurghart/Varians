# -*- coding: utf-8 -*-
"""Cycle de vie du document dans la vraie fenêtre : ouvrir, modifier,
enregistrer, fermer. Tests de caractérisation (comportement V0.8.5.26.2)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

Role = QMessageBox.ButtonRole
Std = QMessageBox.StandardButton


def _edition(project_path) -> Path:
    return Path(project_path).parent / "xml" / "edition.xml"


def _insert_after(window, marker, text):
    """Insère ``text`` juste après la première occurrence de ``marker``."""
    source = window.editor.toPlainText()
    pos = source.index(marker) + len(marker)
    cursor = window.editor.textCursor()
    cursor.setPosition(pos)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_opening_loads_edition_unmodified(open_window, example_project):
    window = open_window(example_project)
    edition = _edition(example_project)
    assert window.current_path == edition
    assert window.editor.toPlainText() == edition.read_text(encoding="utf-8")
    assert window.modified is False
    assert not window.editor.document().isModified()
    assert window.windowTitle().endswith("edition.xml")
    assert window._has_unsaved_work() is False


def test_editing_marks_document_modified(open_window, example_project):
    window = open_window(example_project)
    _insert_after(window, "<body>", "<!-- essai -->")
    assert window.modified is True
    assert window.windowTitle().endswith(" *")
    assert window._has_unsaved_work() is True


def test_save_writes_file_and_clears_modified(open_window, example_project):
    window = open_window(example_project)
    edition = _edition(example_project)
    _insert_after(window, "<body>", "<!-- enregistré -->")
    expected = window.editor.toPlainText()

    assert window.save() is True

    assert edition.read_text(encoding="utf-8") == expected
    assert window.modified is False
    assert not window.windowTitle().endswith(" *")
    # Une copie de sécurité de la version précédente est conservée.
    backups = list(edition.parent.glob("edition.xml*.bak")) + list(edition.parent.glob("edition*.bak"))
    assert backups, "aucune copie de sécurité .bak créée"


def test_saved_text_is_reloaded_by_a_new_window(open_window, example_project):
    window = open_window(example_project)
    _insert_after(window, "<body>", "<!-- relu -->")
    assert window.save() is True
    reopened = open_window(example_project)
    assert "<!-- relu -->" in reopened.editor.toPlainText()
    assert reopened.modified is False


def test_save_of_malformed_xml_asks_confirmation(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    original = edition.read_text(encoding="utf-8")
    _insert_after(window, "<body>", "<p>non fermé")

    dialogs.expect("box", Role.RejectRole)          # « Annuler »
    assert window.save() is False
    assert edition.read_text(encoding="utf-8") == original
    assert window.modified is True

    dialogs.expect("box", Role.AcceptRole)          # « Enregistrer quand même »
    assert window.save() is True
    assert "<p>non fermé" in edition.read_text(encoding="utf-8")
    assert window.modified is False


def test_save_of_schema_invalid_xml_asks_confirmation(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    original = edition.read_text(encoding="utf-8")
    _insert_after(window, "<body>", "<forbidden/>")

    dialogs.expect("box", Role.RejectRole)
    assert window.save() is False
    assert edition.read_text(encoding="utf-8") == original

    dialogs.expect("box", Role.AcceptRole)
    assert window.save() is True
    assert "<forbidden/>" in edition.read_text(encoding="utf-8")


def test_maybe_save_without_changes_asks_nothing(open_window, example_project):
    window = open_window(example_project)
    assert window.maybe_save() is True


def test_maybe_save_cancel_keeps_changes(open_window, example_project, dialogs):
    window = open_window(example_project)
    _insert_after(window, "<body>", "<!-- x -->")
    dialogs.expect("question", Std.Cancel)
    assert window.maybe_save() is False
    assert window.modified is True


def test_maybe_save_discard_does_not_write(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    original = edition.read_text(encoding="utf-8")
    _insert_after(window, "<body>", "<!-- x -->")
    dialogs.expect("question", Std.Discard)
    assert window.maybe_save() is True
    assert edition.read_text(encoding="utf-8") == original


def test_maybe_save_save_writes(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    _insert_after(window, "<body>", "<!-- sauvé -->")
    dialogs.expect("question", Std.Save)
    assert window.maybe_save() is True
    assert "<!-- sauvé -->" in edition.read_text(encoding="utf-8")
    assert window.modified is False


def test_close_without_changes_asks_nothing(open_window, example_project):
    window = open_window(example_project)
    assert window.confirm_close_application() is True


def test_close_with_changes_cancel_then_discard(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    original = edition.read_text(encoding="utf-8")
    _insert_after(window, "<body>", "<!-- x -->")

    dialogs.expect("box", Role.RejectRole)          # Annuler
    assert window.confirm_close_application() is False

    dialogs.expect("box", Role.DestructiveRole)     # Quitter sans enregistrer
    assert window.confirm_close_application() is True
    assert edition.read_text(encoding="utf-8") == original


def test_close_with_changes_save(open_window, example_project, dialogs):
    window = open_window(example_project)
    edition = _edition(example_project)
    _insert_after(window, "<body>", "<!-- avant de quitter -->")
    dialogs.expect("box", Role.AcceptRole)          # Enregistrer et quitter
    assert window.confirm_close_application() is True
    assert "<!-- avant de quitter -->" in edition.read_text(encoding="utf-8")


def test_undo_restores_text(open_window, example_project):
    window = open_window(example_project)
    original = window.editor.toPlainText()
    _insert_after(window, "<body>", "<!-- annulé -->")
    window.editor.undo()
    assert window.editor.toPlainText() == original
