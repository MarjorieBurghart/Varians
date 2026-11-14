# -*- coding: utf-8 -*-
"""Petits widgets communs aux boîtes du projet (V0.9.4.7, extrait de
project_dialogs) : ``PathRow``, une ligne « chemin + Parcourir… »."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QHBoxLayout, QLineEdit, QPushButton, QWidget


class PathRow(QWidget):
    """Champ de chemin suivi d'un bouton « … » qui ouvre un sélecteur de fichier
    (``mode="file"``, filtre ``file_filter``) ou de dossier (``mode="dir"``)."""
    def __init__(self, value="", parent=None, mode="file", caption="", file_filter="Tous les fichiers (*)"):
        super().__init__(parent)
        self.mode = mode
        self.caption = caption
        self.file_filter = file_filter
        lay = QHBoxLayout(self); lay.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(str(value or ""))
        self.button = QPushButton("…")
        self.button.setMaximumWidth(34)
        self.button.clicked.connect(self.browse)
        lay.addWidget(self.edit, 1); lay.addWidget(self.button)

    def browse(self):
        """Bouton « … » : ouvre le sélecteur au chemin du champ (ou au dossier personnel) et met
        dans le champ le chemin choisi ; rien si l'utilisateur annule."""
        start = self.edit.text().strip() or str(Path.home())
        if self.mode == "dir":
            value = QFileDialog.getExistingDirectory(self, self.caption, start)
        else:
            value, _ = QFileDialog.getOpenFileName(self, self.caption, start, self.file_filter)
        if value:
            self.edit.setText(value)

    def text(self):
        """Chemin saisi, sans blancs autour ; chaîne vide si le champ est vide."""
        return self.edit.text().strip()
