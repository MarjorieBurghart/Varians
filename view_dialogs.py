# -*- coding: utf-8 -*-
"""Boîte d'une vue nommée de la Vue XSLT / CSS (V0.9.4.4) : « Nouvelle
vue… » et « Modifier la vue… ».

Une vue a un nom, une feuille XSLT, une CSS (vide : celle du projet) et, en
option, ses éléments modifiables (vide : la règle de l'édition). Les chemins
s'écrivent comme dans les scénarios de transformation : relatifs au projet,
ou ``${varians}/…`` pour une feuille fournie avec Varians. Une nouvelle vue
peut avoir une feuille XSLT 1.0 et une CSS de départ, écrites à
l'acceptation (``view_files.write_starter``), en XSLT 1.0 (lxml) ou
3.0 (Saxon, V0.9.4.4)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout, QLabel, QLineEdit,
    QMessageBox, QPushButton, QVBoxLayout, QWidget,
)

from app_context import tr as _t
from project_config import ViewConfig
from view_files import STARTER_VERSIONS, check_view, parse_units, starter_paths, write_starter

# Moteur de chaque version d'une feuille de départ (libellés transform.engine.*).
_ENGINES = {"1.0": "lxml", "3.0": "saxon"}
# CSS d'une vue (V0.9.4.4) : les trois valeurs de ViewConfig.project_css,
# puis un fichier CSS de la vue.
CSS_MODES = ("auto", "always", "never", "file")


class ViewDialog(QDialog):
    """Boîte d'une vue : nouvelle (``view`` None) ou existante. ``taken`` :
    les noms des autres vues du document ; ``units`` : les éléments
    modifiables proposés pour une nouvelle vue. Acceptée, ``result_view``
    est la vue à écrire dans project.xml."""

    def __init__(self, parent, project, *, view=None, taken=(), units=()):
        super().__init__(parent)
        self.project = project
        self.view = view
        self.taken = tuple(taken)
        self.result_view = None
        self.setWindowTitle(_t("views.edit.title" if view is not None else "views.new.title"))
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(view.name if view is not None else "")
        form.addRow(_t("views.name"), self.name_edit)
        self.create_check = QCheckBox(_t("views.create_starter"))
        self.create_check.setToolTip(_t("views.create_starter.tip"))
        self.create_check.setChecked(view is None)
        self.create_check.setVisible(view is None)
        form.addRow("", self.create_check)
        # Version de la feuille de départ (V0.9.4.4) : 1.0 (lxml) ou 3.0 (Saxon).
        self.version_combo = QComboBox()
        for version in STARTER_VERSIONS:
            self.version_combo.addItem(_t(f"transform.engine.{_ENGINES[version]}"), version)
        self.version_label = QLabel(_t("documents.new_stylesheet.version"))
        form.addRow(self.version_label, self.version_combo)
        self.version_label.setVisible(view is None)
        self.version_combo.setVisible(view is None)
        self.xslt_edit, xslt_row = self._file_row(view.xslt if view is not None else "", "xslt")
        form.addRow(_t("views.xslt"), xslt_row)
        # CSS de la vue : automatique (celle de la feuille si elle produit son
        # <style>, sinon celle du projet), celle du projet, aucune, un fichier.
        self.css_mode_combo = QComboBox()
        for mode in CSS_MODES:
            self.css_mode_combo.addItem(_t(f"views.css.mode.{mode}"), mode)
        form.addRow(_t("views.css"), self.css_mode_combo)
        self.css_edit, css_row = self._file_row(view.css if view is not None else "", "css")
        form.addRow(_t("views.css.file"), css_row)
        if view is not None:
            self._set_css_mode("file" if view.css.strip() else view.project_css)
        self.units_edit = QLineEdit(" ".join(view.units if view is not None else units))
        self.units_edit.setPlaceholderText(_t("views.units.placeholder"))
        self.units_edit.setToolTip(_t("views.units.tip"))
        form.addRow(_t("views.units"), self.units_edit)
        layout.addLayout(form)
        note = QLabel(_t("views.note"))
        note.setWordWrap(True)
        layout.addWidget(note)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.name_edit.textChanged.connect(self._starter_changed)
        self.create_check.toggled.connect(self._starter_changed)
        self.css_mode_combo.currentIndexChanged.connect(self._css_mode_changed)
        self._starter_changed()
        self._css_mode_changed()

    def _set_css_mode(self, mode):
        self.css_mode_combo.setCurrentIndex(max(0, self.css_mode_combo.findData(mode)))

    def _css_mode(self):
        return self.css_mode_combo.currentData()

    def _css_mode_changed(self, *_args):
        """Le champ du fichier CSS ne sert qu'à « Un fichier CSS »."""
        editable = self._css_mode() == "file" and not self._starter()
        self.css_edit.setEnabled(editable)
        self.css_edit.browse_button.setEnabled(editable)

    def _file_row(self, text, kind):
        row = QWidget()
        box = QHBoxLayout(row)
        box.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(text)
        button = QPushButton("…")
        button.setToolTip(_t("views.browse.tip"))
        button.clicked.connect(lambda _checked=False, e=edit, k=kind: self._browse(e, k))
        box.addWidget(edit, 1)
        box.addWidget(button)
        edit.browse_button = button
        return edit, row

    def _starter(self):
        return self.view is None and self.create_check.isChecked()

    def _starter_changed(self, *_args):
        """Feuille et CSS de départ : leurs chemins, tirés du nom, sont
        montrés et ne se modifient pas ; sans elles, les champs se
        libèrent (vides)."""
        starter = self._starter()
        self.xslt_edit.setEnabled(not starter)
        self.xslt_edit.browse_button.setEnabled(not starter)
        self.version_combo.setEnabled(starter)
        # La feuille de départ vient avec sa CSS : un fichier.
        self.css_mode_combo.setEnabled(not starter)
        if starter:
            xslt, css = starter_paths(self.project.root_dir, self.name_edit.text())
            root = Path(self.project.root_dir)
            self.xslt_edit.setText(xslt.relative_to(root).as_posix())
            self.css_edit.setText(css.relative_to(root).as_posix())
            self._set_css_mode("file")
        elif self.view is None and self.sender() is self.create_check:
            self.xslt_edit.clear()
            self.css_edit.clear()
            self._set_css_mode("auto")
        self._css_mode_changed()

    def _browse(self, edit, kind):
        from xslt_scenarios import resolve_path, scenario_path
        current = resolve_path(self.project, edit.text())
        folder = current.parent if current is not None else Path(self.project.root_dir)
        pattern = ("XSLT (*.xsl *.xslt)" if kind == "xslt" else "CSS (*.css)") + f";;{_t('common.all_files')} (*)"
        fn, _ = QFileDialog.getOpenFileName(self, _t(f"views.{kind}"), str(folder), pattern)
        if fn:
            edit.setText(scenario_path(self.project, fn))

    def accept(self):
        """Contrôle la vue (``check_view``) ; refusée, un message le dit et
        la boîte reste ouverte. Avec la feuille et la CSS de départ, elles
        sont écrites ici, sous des noms libres."""
        from xslt_scenarios import resolve_path
        name = self.name_edit.text().strip()
        starter = self._starter()
        mode = self._css_mode()
        xslt = resolve_path(self.project, self.xslt_edit.text())
        css = resolve_path(self.project, self.css_edit.text()) if mode == "file" else None
        error = check_view(name, xslt, css, self.units_edit.text(), self.taken, starter=starter)
        if error is None and mode == "file" and not starter and css is None:
            error = "views.error.css"                      # « Un fichier CSS » sans fichier
        if error is not None:
            QMessageBox.warning(self, self.windowTitle(), _t(error))
            return
        units = parse_units(self.units_edit.text())
        if starter:
            try:
                xslt_text, css_text = write_starter(self.project.root_dir, name, self.version_combo.currentData())
            except OSError as exc:
                QMessageBox.critical(self, _t("file.save.error.title"), str(exc))
                return
        else:
            xslt_text = self.xslt_edit.text().strip()
            css_text = self.css_edit.text().strip() if mode == "file" else ""
        self.result_view = ViewConfig(name, xslt_text, css_text, units, "auto" if mode == "file" else mode)
        super().accept()
