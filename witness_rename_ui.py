# -*- coding: utf-8 -*-
"""Boîte « Changer le sigle d'un témoin » (V0.9.4.0).

Ouverte par le bouton « Changer le sigle… » de Projet ▸ Paramètres du
projet : nouveau sigle, « Aperçu » (witness_rename.plan_witness_rename :
fichiers modifiés et nombre de changements, fichiers renommés, citations du
sigle à vérifier), « Appliquer » (witness_rename.apply_witness_rename, d'un
bloc). « Appliquer » n'est possible qu'après un aperçu sans refus du sigle
affiché. Ensuite, les réglages d'affichage du témoin le suivent et le projet
est rechargé."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QFormLayout, QHBoxLayout, QLabel, QLineEdit, QMessageBox,
    QPlainTextEdit, QPushButton, QVBoxLayout,
)

from i18n import message_text
from witness_ids import witness_id_for_siglum
from witness_rename import RenameError, apply_witness_rename, migrate_view_settings, plan_witness_rename

# Au-delà, l'aperçu n'énumère plus les citations (il en donne le nombre).
MENTIONS_SHOWN = 200


def preview_text(plan, tr) -> str:
    """Texte de l'aperçu d'un plan, dans la langue de ``tr``."""
    display = plan.display_path
    if plan.problems:
        return "\n".join([tr("witness_rename.preview.refused")]
                         + ["  " + message_text(problem, tr) for problem in plan.problems])
    lines = [tr("witness_rename.preview.files")]
    for change in plan.changes:
        categories = ", ".join(tr(f"witness_rename.category.{category}") for category, _n in change.counts)
        lines.append("  " + tr("witness_rename.preview.file", file=display(change.path), count=change.count,
                               categories=categories))
    if plan.moves:
        lines += ["", tr("witness_rename.preview.moves")]
        lines += [f"  {display(move.source)} → {display(move.target)}" for move in plan.moves]
    if plan.notes:
        lines += ["", tr("witness_rename.preview.notes")]
        lines += ["  " + message_text(note, tr) for note in plan.notes]
    if plan.mentions:
        lines += ["", tr("witness_rename.preview.mentions", count=len(plan.mentions))]
        lines += ["  " + tr("witness_rename.preview.mention", file=display(m.path), line=m.line, excerpt=m.excerpt)
                  for m in plan.mentions[:MENTIONS_SHOWN]]
        if len(plan.mentions) > MENTIONS_SHOWN:
            lines.append("  …")
    return "\n".join(lines)


class WitnessRenameDialog(QDialog):
    def __init__(self, tr, project, witness_id, parent=None):
        super().__init__(parent)
        self.tr = tr
        self.project = project
        self.witness_id = witness_id
        self.plan = None
        witness = project.witness_by_id[witness_id]
        self.setWindowTitle(tr("witness_rename.title"))
        self.resize(820, 600)
        layout = QVBoxLayout(self)
        intro = QLabel(tr("witness_rename.intro", witness=witness.display_title))
        intro.setWordWrap(True)
        intro.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(intro)
        form = QFormLayout()
        self.siglum_edit = QLineEdit(witness.display_siglum)
        self.xml_id_hint = QLabel()
        self.xml_id_hint.setTextFormat(Qt.TextFormat.PlainText)
        self.xml_id_hint.setVisible(False)
        form.addRow(tr("witness_rename.new_siglum"), self.siglum_edit)
        form.addRow("", self.xml_id_hint)
        layout.addLayout(form)
        row = QHBoxLayout()
        self.preview_button = QPushButton(tr("witness_rename.preview"))
        row.addWidget(self.preview_button)
        row.addStretch(1)
        layout.addLayout(row)
        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlainText(tr("witness_rename.preview_needed"))
        layout.addWidget(self.preview, 1)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.apply_button = buttons.addButton(tr("witness_rename.apply"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.apply_button.setEnabled(False)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.siglum_edit.textChanged.connect(self._siglum_changed)
        self.preview_button.clicked.connect(self.run_preview)
        self.siglum_edit.returnPressed.connect(self.run_preview)
        self.siglum_edit.selectAll()

    def _siglum_changed(self, *_):
        self.plan = None
        self.apply_button.setEnabled(False)
        self.preview.setPlainText(self.tr("witness_rename.preview_needed"))
        text = self.siglum_edit.text().strip()
        ident = witness_id_for_siglum(text)
        differs = bool(ident) and ident != text
        self.xml_id_hint.setText(self.tr("project.witness.xml_id", id=ident) if differs else "")
        self.xml_id_hint.setVisible(differs)

    def run_preview(self):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self.plan = plan_witness_rename(self.project, self.witness_id, self.siglum_edit.text())
        finally:
            QApplication.restoreOverrideCursor()
        self.preview.setPlainText(preview_text(self.plan, self.tr))
        self.apply_button.setEnabled(self.plan.ok)

    def _apply(self):
        if self.plan is not None and self.plan.ok:
            self.accept()


def _carry_view_settings(window, old, new):
    """Réglages d'affichage du témoin reportés sur son nouvel identifiant.
    Une fenêtre détachée enregistre sa position en se fermant : elle la
    garde déjà sous le nouvel identifiant, que la nouvelle fenêtre lira."""
    from app_context import _settings
    settings = _settings()
    for ident, detached in list(getattr(window, "_detached_windows", {}).items()):
        settings.setValue(window._view_settings_key(f"floatingGeometry/{ident}"), detached.saveGeometry())
        if ident == old:
            detached.witness_id = new
    migrate_view_settings(settings, window._view_settings_key(""), old, new)


def run_witness_rename(window, witness_id, tr) -> bool:
    """Changer le sigle de ``witness_id`` depuis la fenêtre ``window`` :
    documents modifiés enregistrés d'abord, boîte d'aperçu, application d'un
    bloc, réglages d'affichage reportés, projet rechargé."""
    if not window.maybe_save():
        return False
    dialog = WitnessRenameDialog(tr, window.project, witness_id, window)
    if dialog.exec() != QDialog.DialogCode.Accepted or dialog.plan is None or not dialog.plan.ok:
        return False
    plan = dialog.plan
    # Les téléchargements IIIF écrivent dans iiif/local/<témoin>/ : arrêtés
    # avant que le dossier ne change de nom.
    manager = getattr(window, "_iiif_download_dialog", None)
    if manager is not None:
        manager.shutdown()
    try:
        result = apply_witness_rename(plan)
    except RenameError as error:
        QMessageBox.critical(window, tr("witness_rename.title"), message_text(error.message, tr))
        return False
    _carry_view_settings(window, plan.old_id, plan.new_id)
    text = tr("witness_rename.done", old=plan.old_siglum, new=plan.new_siglum,
              files=len(result.written), moves=len(result.moved))
    if plan.mentions:
        text += "\n\n" + tr("witness_rename.done.mentions", old=plan.old_siglum, count=len(plan.mentions))
    QMessageBox.information(window, tr("witness_rename.title"), text)
    from app_context import error_message
    try:
        new_window = type(window)(window.project.path)
    except Exception as exc:
        QMessageBox.critical(window, tr("project.open_error"), error_message(exc))
        return False
    window._replacement_window = new_window
    new_window.showMaximized()
    window._force_close = True
    window.close()
    return True
