# -*- coding: utf-8 -*-
"""Red team (intégrité, A4) dans la fenêtre : un document qui déclare un
autre encodage que UTF-8 n'est enregistré qu'après correction de sa
déclaration ; refuser la correction annule l'enregistrement."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app_context import tr


def _declare_latin1(project):
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    assert text.startswith("<?xml version='1.0' encoding='UTF-8'?>")
    text = text.replace("encoding='UTF-8'", "encoding='ISO-8859-1'", 1)
    edition.write_text(text, encoding="utf-8")
    return edition, text


def _edit(window):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    cursor.insertText("<!-- relu : é -->")


def _boxes(dialogs):
    return [seen for seen in dialogs.seen if seen[0] == "box"]


def test_a_non_utf8_declaration_is_corrected_before_saving(open_window, example_project, dialogs):
    edition, before = _declare_latin1(example_project)
    window = open_window(example_project)
    _edit(window)

    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)           # Annuler
    assert not window.save()
    [(_kind, title, text)] = _boxes(dialogs)
    assert title == tr("file.encoding.title") and "ISO-8859-1" in text
    assert edition.read_text(encoding="utf-8") == before and window.modified
    assert "encoding='ISO-8859-1'" in window.editor.toPlainText()

    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)           # Corriger et enregistrer
    assert window.save()
    saved = edition.read_bytes().decode("utf-8")
    assert saved.startswith("<?xml version='1.0' encoding='UTF-8'?>") and "<!-- relu : é -->" in saved
    assert window.editor.toPlainText() == saved and not window.modified

    # Corrigé : plus de question.
    _edit(window)
    assert window.save() and len(_boxes(dialogs)) == 2


def test_the_correction_can_be_undone(open_window, example_project, dialogs):
    _declare_latin1(example_project)
    window = open_window(example_project)
    _edit(window)
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    assert window.save()
    window.editor.undo()
    assert "encoding='ISO-8859-1'" in window.editor.toPlainText()
