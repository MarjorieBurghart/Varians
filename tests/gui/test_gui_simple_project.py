# -*- coding: utf-8 -*-
"""Parcours de référence « une image, une transcription, sans options avancées ».

Reproduit ce que fait « Nouveau projet » en mode transcription vierge, avec
un seul témoin et une seule image locale, puis l'utilisation de base :
saisir, enregistrer, rouvrir, exporter le viewer web. Ce parcours doit
rester simple quelles que soient les évolutions de Varians.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage
from PySide6.QtWidgets import QDialog, QMessageBox

LINE = "In principio erat verbum"


def _create_simple_project(tmp_path, editor_module) -> Path:
    from project_management import LocalImageDraft, WitnessDraft, create_new_transcription_project

    photo = tmp_path / "photos" / "folio 1r.png"
    photo.parent.mkdir()
    image = QImage(40, 60, QImage.Format.Format_RGB32)
    image.fill(QColor("white"))
    assert image.save(str(photo), "PNG")
    witness = WitnessDraft(
        "A", "Manuscrit A", None, "base", "files", None,
        [LocalImageDraft(photo, "1r")], "copy",
    )
    return create_new_transcription_project(
        tmp_path / "projet", "Transcription simple", [witness], "A",
        editor_module.HERE, "fr", "en",
    )


def test_simple_project_is_created_with_defaults(tmp_path, editor_module):
    project_path = _create_simple_project(tmp_path, editor_module)
    from project_config import load_project

    project = load_project(project_path)
    assert project.edition.is_file()
    assert [w.id for w in project.witnesses] == ["A"]
    assert project.base_witness == "A"
    copied = project.witnesses[0].image_files
    assert len(copied) == 1 and copied[0].path.is_file()
    assert copied[0].path.parent != tmp_path / "photos"      # image copiée dans le projet


def test_transcribe_save_reopen_and_export(tmp_path, editor_module, open_window, dialogs):
    project_path = _create_simple_project(tmp_path, editor_module)
    window = open_window(project_path)

    # Le document vierge s'ouvre sans travail en attente ni boîte de dialogue.
    assert window.modified is False
    assert window.panels and "A" in window.panels

    # Saisie d'une ligne dans le paragraphe vide du squelette TEI. Le viewer
    # web découpe le texte selon les <lb/> : une transcription en comporte.
    text = window.editor.toPlainText()
    start = text.index("<p>", text.index("<body>")) + len("<p>")
    cursor = window.editor.textCursor()
    cursor.setPosition(start)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(f'<pb n="1r" facs="#A-p0001"/><lb n="1"/>{LINE}')
    assert window.modified is True

    # Hors ligne, le schéma TEI distant est indisponible : l'enregistrement
    # ne doit pas en être empêché.
    assert window.save() is True
    edition = window.project.edition
    assert LINE in edition.read_text(encoding="utf-8")

    reopened = open_window(project_path)
    assert LINE in reopened.editor.toPlainText()

    # Export du viewer web autonome ; la boîte finale est fermée sans
    # ouvrir le navigateur.
    dialogs.expect("dialog", lambda dialog: QDialog.DialogCode.Accepted)   # texte du viewer : par défaut
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    reopened.generate_web_viewer()
    output = reopened.project.web_output_dir / reopened.project.web_filename
    assert output.is_file()
    assert LINE in output.read_text(encoding="utf-8")
