# -*- coding: utf-8 -*-
"""Boîte « Générer viewer web » : choix du texte du viewer (V0.9.3.0).

Texte établi (le <lem>, à défaut la leçon du témoin choisi) ou texte du
témoin choisi, même quand il n'est pas le <lem>. La liste des témoins
commence par « Pivot (de chaque texte) » (valeur vide). Les passages où le
témoin choisi n'a pas de leçon sont signalés dans le viewer.

Texte établi (V0.9.3.1) : une case fixe l'état de départ du surlignage des
leçons qui ne viennent pas d'un <lem> ; le lecteur le change dans le viewer."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QButtonGroup, QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QLabel, QRadioButton, QVBoxLayout,
)

from app_context import tr as _t


class WebTextDialog(QDialog):
    def __init__(self, witnesses, mode="established", witness="", parent=None, highlight=False):
        super().__init__(parent)
        self.setWindowTitle(_t("webgen.text.title"))
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_t("webgen.text.label")))
        self.established = QRadioButton(_t("webgen.text.established"))
        self.witness_mode = QRadioButton(_t("webgen.text.witness"))
        group = QButtonGroup(self)
        for button in (self.established, self.witness_mode):
            group.addButton(button)
            layout.addWidget(button)
        self.highlight_box = QCheckBox(_t("webgen.text.highlight"))
        self.highlight_box.setStyleSheet("QCheckBox { margin-left: 20px; }")
        layout.insertWidget(layout.indexOf(self.established) + 1, self.highlight_box)
        self.established.toggled.connect(self.highlight_box.setEnabled)
        form = QFormLayout()
        self.witness_box = QComboBox()
        self.witness_box.addItem(_t("webgen.text.pivot"), "")
        for item in witnesses:
            self.witness_box.addItem(item.display_title, item.id)
        form.addRow(_t("webgen.text.chosen"), self.witness_box)
        layout.addLayout(form)
        hint = QLabel(_t("webgen.text.missing_hint"))
        hint.setWordWrap(True)
        layout.addWidget(hint)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        buttons.addButton(_t("webgen.text.generate"), QDialogButtonBox.ButtonRole.AcceptRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.set_choice(mode, witness, highlight)

    def set_choice(self, mode, witness="", highlight=False):
        """Coche le mode et choisit le témoin ; un témoin inconnu : le pivot."""
        (self.witness_mode if mode == "witness" else self.established).setChecked(True)
        self.highlight_box.setEnabled(mode != "witness")
        self.highlight_box.setChecked(bool(highlight))
        index = self.witness_box.findData(witness or "")
        self.witness_box.setCurrentIndex(max(index, 0))

    def highlight(self):
        """Leçons hors <lem> surlignées au départ (texte établi seulement ;
        le réglage est gardé quand on choisit le texte d'un témoin)."""
        return self.highlight_box.isChecked()

    def choice(self):
        """``(mode, témoin)`` ; témoin vide : le pivot de chaque texte."""
        mode = "witness" if self.witness_mode.isChecked() else "established"
        return mode, self.witness_box.currentData() or ""
