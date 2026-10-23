# -*- coding: utf-8 -*-
"""Fichier ▸ « Scénarios de transformation… » (V0.9.2.0) : la liste des
scénarios du projet, enregistrés dans project.xml (``<transformations>``),
et des scénarios prédéfinis fournis par Varians, que « Dupliquer… » copie
dans le projet pour les adapter ; la boîte d'un scénario ; le bouton
« Transformer ▾ » et l'exécution d'un scénario.

Les chemins d'un scénario sont écrits relatifs au projet, ou ``${varians}/…``
pour une feuille de Varians (``xslt_scenarios.scenario_path``). Les règles
(sources, garde-fous du résultat) sont celles de ``xslt_scenarios``.
"""
from __future__ import annotations

import json
import re
import tempfile
from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QButtonGroup, QComboBox, QDialog, QDialogButtonBox, QFileDialog, QFormLayout, QHBoxLayout,
    QHeaderView, QLineEdit, QMenu, QMessageBox, QProgressDialog, QPushButton, QRadioButton, QTableWidget,
    QTableWidgetItem, QToolButton, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from app_context import _settings, tr as _t
from project_config import TransformScenario
from project_management import update_project_transformations
from transform_runner import TransformRunner
from xml_assembly import path_key
from xslt_engines import JOURNAL_CODES
from xslt_scenarios import (predefined_scenarios, project_sources, resolve_path, saxon_available, scenario_path,
                            scenario_problems, scenario_request, scenario_source, stylesheet_path)

# Problèmes qui empêchent d'enregistrer un scénario ; les autres (fichier
# absent, Saxon non installé…) sont signalés, et l'enregistrement reste possible.
_BLOCKING = {"no_xslt", "no_output", "no_file", "output_is_folder", "output_is_source", "css_overwrites_source"}


def problem_text(problem):
    return _t(f"transform.problem.{problem.code}", detail=problem.detail)


def engine_label(engine):
    if engine in ("lxml", "saxon"):
        return _t(f"transform.engine.{engine}")
    return engine


def source_label(scenario):
    if scenario.source == "file":
        return _t("transform.source.file", file=scenario.file)
    if scenario.source in ("edition", "current"):
        return _t(f"transform.source.{scenario.source}")
    return scenario.source


def predefined():
    """Scénarios prédéfinis, avec leur nom dans la langue de l'interface."""
    return predefined_scenarios(lambda key: _t(f"transform.predefined.{key}"))


class _PathField(QWidget):
    """Chemin d'un scénario, tel qu'il est écrit ; « … » choisit un fichier."""

    def __init__(self, project, value="", caption="", save=False, file_filter="", parent=None):
        super().__init__(parent)
        self._project = project
        self._caption = caption
        self._save = save
        self._filter = file_filter
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.edit = QLineEdit(value, self)
        self.button = QPushButton("…", self)
        self.button.setMaximumWidth(34)
        self.button.clicked.connect(self.browse)
        layout.addWidget(self.edit, 1)
        layout.addWidget(self.button)

    def text(self):
        return self.edit.text().strip()

    def browse(self):
        current = resolve_path(self._project, self.text())
        start = str(current if current is not None else self._project.root_dir)
        if self._save:
            value, _filter = QFileDialog.getSaveFileName(self, self._caption, start, self._filter)
        else:
            value, _filter = QFileDialog.getOpenFileName(self, self._caption, start, self._filter)
        if value:
            self.edit.setText(scenario_path(self._project, value))
            self.edit.textEdited.emit(self.edit.text())


class ScenarioDialog(QDialog):
    """Boîte d'un scénario : nom, source, moteur, feuille XSLT, CSS, résultat,
    paramètres. Refuse un nom déjà pris (``taken``) ou un résultat qui
    remplacerait une source du projet ; signale les autres problèmes."""

    def __init__(self, scenario, project, taken=(), current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("transform.scenario.title"))
        self.resize(720, 460)
        self._project = project
        self._taken = set(taken)
        self._current = current
        self._unknown_source = scenario.source if scenario.source not in ("edition", "current", "file") else None
        form = QFormLayout(self)

        self.name_edit = QLineEdit(scenario.name, self)
        form.addRow(_t("transform.scenario.name"), self.name_edit)

        source_row = QHBoxLayout()
        self.source_buttons = QButtonGroup(self)
        self.edition_radio = QRadioButton(_t("transform.source.edition"), self)
        self.current_radio = QRadioButton(_t("transform.source.current"), self)
        self.file_radio = QRadioButton(_t("transform.source.file_choice"), self)
        self.file_field = _PathField(project, scenario.file, _t("transform.browse.file"),
                                     file_filter="XML (*.xml);;*", parent=self)
        for button in (self.edition_radio, self.current_radio, self.file_radio):
            self.source_buttons.addButton(button)
            source_row.addWidget(button)
        source_row.addWidget(self.file_field, 1)
        {"edition": self.edition_radio, "current": self.current_radio,
         "file": self.file_radio}.get(scenario.source, QRadioButton()).setChecked(True)
        self.file_radio.toggled.connect(self.file_field.setEnabled)
        self.file_field.setEnabled(self.file_radio.isChecked())
        form.addRow(_t("transform.scenario.source"), source_row)

        self.engine_combo = QComboBox(self)
        self.engine_combo.addItem(_t("transform.engine.lxml"), "lxml")
        saxon = _t("transform.engine.saxon")
        self.engine_combo.addItem(saxon if saxon_available() else _t("transform.engine.missing", engine=saxon), "saxon")
        if self.engine_combo.findData(scenario.engine) < 0:          # moteur inconnu : gardé
            self.engine_combo.addItem(scenario.engine, scenario.engine)
        self.engine_combo.setCurrentIndex(self.engine_combo.findData(scenario.engine))
        form.addRow(_t("transform.scenario.engine"), self.engine_combo)

        self.xslt_field = _PathField(project, scenario.xslt, _t("transform.browse.xslt"),
                                     file_filter="XSLT (*.xsl *.xslt);;*", parent=self)
        self.css_field = _PathField(project, scenario.css, _t("transform.browse.css"),
                                    file_filter="CSS (*.css);;*", parent=self)
        self.output_field = _PathField(project, scenario.output, _t("transform.browse.output"), save=True, parent=self)
        form.addRow(_t("transform.scenario.xslt"), self.xslt_field)
        form.addRow(_t("transform.scenario.css"), self.css_field)
        form.addRow(_t("transform.scenario.output"), self.output_field)
        # Un nouveau scénario propose publications/<nom>.html, tant que le
        # résultat n'a pas été choisi.
        self._proposed_output = "" if not scenario.output else None
        self.name_edit.textChanged.connect(self._name_changed)

        self.params_table = QTableWidget(0, 2, self)
        self.params_table.setHorizontalHeaderLabels([_t("transform.param.name"), _t("transform.param.value")])
        self.params_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.params_table.verticalHeader().setVisible(False)
        for name, value in scenario.params:
            self.add_param_row(name, value)
        param_buttons = QHBoxLayout()
        self.add_param_btn = QPushButton(_t("transform.param.add"), self)
        self.remove_param_btn = QPushButton(_t("transform.param.remove"), self)
        self.add_param_btn.clicked.connect(lambda: self.add_param_row())
        self.remove_param_btn.clicked.connect(lambda: self.remove_param_row(self.params_table.currentRow()))
        param_buttons.addWidget(self.add_param_btn)
        param_buttons.addWidget(self.remove_param_btn)
        param_buttons.addStretch(1)
        params = QVBoxLayout()
        params.addWidget(self.params_table)
        params.addLayout(param_buttons)
        form.addRow(_t("transform.scenario.params"), params)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
                                   parent=self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        form.addRow(buttons)
        for edit in (self.name_edit, self.xslt_field.edit, self.output_field.edit):
            edit.textChanged.connect(self._update_ok_button)
        self._update_ok_button()

    # --- Champs -----------------------------------------------------------------

    def _name_changed(self, name):
        if self._proposed_output is None or self.output_field.text() != self._proposed_output:
            self._proposed_output = None
            return
        safe = re.sub(r'[\\/:*?"<>|]', "_", name.strip())
        self._proposed_output = f"publications/{safe}.html" if safe else ""
        self.output_field.edit.setText(self._proposed_output)

    def _update_ok_button(self, *_args):
        self.ok_button.setEnabled(bool(self.name_edit.text().strip() and self.xslt_field.text()
                                       and self.output_field.text()))

    def engine(self):
        return self.engine_combo.currentData()

    def source(self):
        for value, button in (("edition", self.edition_radio), ("current", self.current_radio),
                              ("file", self.file_radio)):
            if button.isChecked():
                return value
        return self._unknown_source or "edition"

    def add_param_row(self, name="", value=""):
        row = self.params_table.rowCount()
        self.params_table.insertRow(row)
        self.params_table.setItem(row, 0, QTableWidgetItem(name))
        self.params_table.setItem(row, 1, QTableWidgetItem(value))
        self.params_table.setCurrentCell(row, 0)

    def remove_param_row(self, row):
        if 0 <= row < self.params_table.rowCount():
            self.params_table.removeRow(row)

    def params(self):
        """Paramètres du tableau ; une ligne sans nom est ignorée, à nom égal
        la première est gardée."""
        params = {}
        for row in range(self.params_table.rowCount()):
            name_item, value_item = self.params_table.item(row, 0), self.params_table.item(row, 1)
            name = (name_item.text() if name_item else "").strip()
            if name and name not in params:
                params[name] = value_item.text() if value_item else ""
        return tuple(params.items())

    def scenario(self):
        source = self.source()
        return TransformScenario(self.name_edit.text().strip(), self.xslt_field.text(), self.output_field.text(),
                                 source=source, file=self.file_field.text() if source == "file" else "",
                                 engine=self.engine(), css=self.css_field.text(), params=self.params())

    def accept(self):
        scenario = self.scenario()
        if scenario.name in self._taken:
            QMessageBox.warning(self, self.windowTitle(), _t("transform.scenario.duplicate_name", name=scenario.name))
            return
        problems = [problem for problem in scenario_problems(scenario, self._project, self._current)
                    if problem.code != "no_current"]
        blocking = [problem for problem in problems if problem.code in _BLOCKING]
        if blocking:
            QMessageBox.warning(self, self.windowTitle(),
                                _t("transform.scenario.refused", problem=problem_text(blocking[0])))
            return
        if problems:
            answer = QMessageBox.question(
                self, self.windowTitle(),
                _t("transform.scenario.problems", problems="\n".join(problem_text(p) for p in problems)),
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return
        super().accept()


class ScenarioListDialog(QDialog):
    """Scénarios du projet et scénarios prédéfinis.

    ``save(scenarios)`` enregistre les scénarios du projet après chaque ajout,
    modification ou suppression ; elle renvoie False en cas d'échec (la liste
    affichée n'est alors pas modifiée). ``current`` : le document affiché."""

    def __init__(self, project, scenarios, save, current=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_t("transform.title"))
        self.resize(860, 440)
        self._project = project
        self._scenarios = list(scenarios)
        self._predefined = list(predefined())
        self._save = save
        self._current = current
        root = QVBoxLayout(self)
        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels([_t("transform.column.name"), _t("transform.column.source"),
                                   _t("transform.column.engine"), _t("transform.column.problem")])
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.tree.currentItemChanged.connect(self._update_buttons)
        self.tree.itemDoubleClicked.connect(lambda _item, _column: self.edit_scenario())
        self.project_group = QTreeWidgetItem(self.tree, [_t("transform.group.project")])
        self.predefined_group = QTreeWidgetItem(self.tree, [_t("transform.group.predefined")])
        for group in (self.project_group, self.predefined_group):
            group.setFlags(Qt.ItemFlag.ItemIsEnabled)
            group.setFirstColumnSpanned(True)
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
        root.addWidget(self.tree, 1)

        row = QHBoxLayout()
        self.add_btn = QPushButton(_t("transform.add"), self)
        self.edit_btn = QPushButton(_t("transform.edit"), self)
        self.duplicate_btn = QPushButton(_t("transform.duplicate"), self)
        self.remove_btn = QPushButton(_t("transform.remove"), self)
        self.add_btn.clicked.connect(self.add_scenario)
        self.edit_btn.clicked.connect(self.edit_scenario)
        self.duplicate_btn.clicked.connect(self.duplicate_scenario)
        self.remove_btn.clicked.connect(self.remove_scenario)
        for button in (self.add_btn, self.edit_btn, self.duplicate_btn, self.remove_btn):
            row.addWidget(button)
        row.addStretch(1)
        root.addLayout(row)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, parent=self)
        self.preview_btn = self.buttons.addButton(_t("transform.preview"), QDialogButtonBox.ButtonRole.ActionRole)
        self.run_btn = self.buttons.addButton(_t("transform.run"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.preview_btn.clicked.connect(lambda: self._choose(True))
        self.run_btn.clicked.connect(lambda: self._choose(False))
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)
        # Scénario à exécuter quand la liste se ferme : (scénario, aperçu).
        self.chosen = None
        self._refresh()

    # --- Liste ------------------------------------------------------------------

    def _refresh(self, select=None):
        """Remplit les deux groupes ; ``select`` : ``(groupe, rang)`` à choisir."""
        sources = project_sources(self._project)
        for group, scenarios in ((self.project_group, self._scenarios), (self.predefined_group, self._predefined)):
            group.takeChildren()
            for scenario in scenarios:
                problems = scenario_problems(scenario, self._project, self._current, sources)
                item = QTreeWidgetItem(group, [scenario.name, source_label(scenario), engine_label(scenario.engine),
                                               problem_text(problems[0]) if problems else ""])
                if problems:
                    item.setToolTip(3, "\n".join(problem_text(problem) for problem in problems))
                    item.setForeground(3, Qt.GlobalColor.darkRed)
            group.setExpanded(True)
        for column in range(4):
            self.tree.resizeColumnToContents(column)
        if select is not None:
            group = self.project_group if select[0] == "project" else self.predefined_group
            if 0 <= select[1] < group.childCount():
                self.tree.setCurrentItem(group.child(select[1]))
        self._update_buttons()

    def selected(self):
        """``(groupe, rang, scénario)`` choisi, ou None."""
        item = self.tree.currentItem()
        parent = item.parent() if item is not None else None
        if parent is self.project_group:
            index = parent.indexOfChild(item)
            return "project", index, self._scenarios[index]
        if parent is self.predefined_group:
            index = parent.indexOfChild(item)
            return "predefined", index, self._predefined[index]
        return None

    def selected_scenario(self):
        chosen = self.selected()
        return chosen[2] if chosen is not None else None

    def _update_buttons(self, *_args):
        chosen = self.selected()
        own = chosen is not None and chosen[0] == "project"
        self.edit_btn.setEnabled(own)
        self.remove_btn.setEnabled(own)
        for button in (self.duplicate_btn, self.preview_btn, self.run_btn):
            button.setEnabled(chosen is not None)

    def _choose(self, preview):
        """« Aperçu » ou « Exécuter » : la liste se ferme sur ce choix."""
        scenario = self.selected_scenario()
        if scenario is not None:
            self.chosen = (scenario, preview)
            self.accept()

    # --- Modifications ----------------------------------------------------------

    def _names(self, skip=None):
        return [scenario.name for scenario in self._scenarios if scenario is not skip]

    def _store(self, scenarios, current):
        if not self._save(scenarios):
            return False
        self._scenarios = list(scenarios)
        self._refresh(("project", current))
        return True

    def _ask(self, scenario, skip=None):
        dialog = ScenarioDialog(scenario, self._project, self._names(skip), self._current, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        return dialog.scenario()

    def add_scenario(self):
        """« Ajouter… » : la feuille et la CSS de la Vue XSLT / CSS sont proposées."""
        css = scenario_path(self._project, self._project.css) if Path(self._project.css).is_file() else ""
        scenario = self._ask(TransformScenario("", scenario_path(self._project, self._project.xslt), "", css=css))
        if scenario is None:
            return False
        return self._store(self._scenarios + [scenario], len(self._scenarios))

    def edit_scenario(self):
        chosen = self.selected()
        if chosen is None or chosen[0] != "project":
            return False
        _group, index, old = chosen
        scenario = self._ask(old, skip=old)
        if scenario is None:
            return False
        scenarios = list(self._scenarios)
        scenarios[index] = scenario
        return self._store(scenarios, index)

    def duplicate_scenario(self):
        """« Dupliquer… » : copie dans le projet, sous un nom libre."""
        chosen = self.selected()
        if chosen is None:
            return False
        original = chosen[2]
        names, name, rank = set(self._names()), original.name, 1
        while name in names:
            name = _t("transform.copy_name", name=original.name) + (f" {rank}" if rank > 1 else "")
            rank += 1
        scenario = self._ask(replace(original, name=name))
        if scenario is None:
            return False
        return self._store(self._scenarios + [scenario], len(self._scenarios))

    def remove_scenario(self):
        chosen = self.selected()
        if chosen is None or chosen[0] != "project":
            return False
        _group, index, scenario = chosen
        answer = QMessageBox.question(
            self, self.windowTitle(), _t("transform.remove.question", name=scenario.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return False
        return self._store(self._scenarios[:index] + self._scenarios[index + 1:], -1)


def _worker_command():
    """Commande du processus de transformation (None : Varians relancé)."""
    return None


class TransformScenariosMixin:
    """Méthodes de MainWindow : voir la docstring du module.

    Une exécution (``run_transform_scenario``) : vérifier le scénario,
    enregistrer ce qu'il lit, lancer son processus (``TransformRunner``),
    montrer « Transformation en cours… » au-delà d'une demi-seconde, puis le
    compte rendu (« Ouvrir », journal en détail) ou l'erreur. L'aperçu écrit
    dans un dossier temporaire de la session et s'ouvre aussitôt."""

    transform_progress = None
    _transform_runner = None
    _transform_running = None
    _transform_preview_folder = None
    _LAST_SCENARIO_SETTING = "transformLastScenario"

    # --- Liste, bouton et menu ----------------------------------------------------

    def transform_scenarios_dialog(self):
        """Fichier ▸ « Scénarios de transformation… »."""
        dialog = ScenarioListDialog(self.project, self.project.transformations, self._save_transformations,
                                    self._transform_current_path(), self)
        if dialog.exec() == QDialog.DialogCode.Accepted and dialog.chosen is not None:
            scenario, preview = dialog.chosen
            self.run_transform_scenario(scenario, preview=preview)
        return dialog

    def _build_transform_button(self):
        """Bouton « Transformer ▾ » de la barre d'outils : un clic relance le
        dernier scénario (Ctrl+Shift+T), la flèche donne la liste."""
        self.transform_menu = QMenu(self)
        self.transform_menu.aboutToShow.connect(self._fill_transform_menu)
        self.action_transform = self._make_action(_t("toolbar.transform"), "Ctrl+Shift+T",
                                                  self.run_last_transform_scenario, _t("toolbar.transform.tip"))
        self.addAction(self.action_transform)
        self.transform_button = QToolButton(self)
        self.transform_button.setDefaultAction(self.action_transform)
        self.transform_button.setMenu(self.transform_menu)
        self.transform_button.setPopupMode(QToolButton.ToolButtonPopupMode.MenuButtonPopup)
        return self.transform_button

    def _fill_transform_menu(self):
        menu = self.transform_menu
        menu.clear()
        for scenarios in (self.project.transformations, predefined()):
            for scenario in scenarios:
                action = menu.addAction(scenario.name)
                action.triggered.connect(lambda _checked=False, s=scenario: self.run_transform_scenario(s))
            if scenarios:
                menu.addSeparator()
        menu.addAction(self.action_transform_scenarios)

    def _transform_current_path(self):
        """Fichier du document affiché, ou None."""
        document = getattr(self, "document", None)
        return Path(document.path) if document is not None and document.path else None

    def _save_transformations(self, scenarios):
        """Enregistre les scénarios du projet dans project.xml."""
        try:
            update_project_transformations(self.project.path, scenarios)
        except Exception as exc:
            QMessageBox.critical(self, _t("transform.title"), str(exc))
            return False
        self.project = replace(self.project, transformations=tuple(scenarios))
        return True

    # --- Dernier scénario ------------------------------------------------------------

    def _last_scenarios(self):
        try:
            value = json.loads(str(_settings().value(self._LAST_SCENARIO_SETTING, "{}") or "{}"))
        except ValueError:
            value = {}
        return value if isinstance(value, dict) else {}

    def _remember_transform_scenario(self, scenario):
        group = "predefined" if scenario in predefined() else "project"
        last = self._last_scenarios()
        last[path_key(self.project.path)] = [group, scenario.name]
        _settings().setValue(self._LAST_SCENARIO_SETTING, json.dumps(last, ensure_ascii=False))

    def last_transform_scenario(self):
        """Dernier scénario lancé dans ce projet, s'il existe encore."""
        entry = self._last_scenarios().get(path_key(self.project.path))
        if not isinstance(entry, list) or len(entry) != 2:
            return None
        group, name = entry
        scenarios = predefined() if group == "predefined" else self.project.transformations
        return next((scenario for scenario in scenarios if scenario.name == name), None)

    def run_last_transform_scenario(self):
        """Bouton « Transformer », Ctrl+Shift+T : sans dernier scénario, la liste."""
        scenario = self.last_transform_scenario()
        if scenario is None:
            self.transform_scenarios_dialog()
            return False
        return self.run_transform_scenario(scenario)

    # --- Exécution -------------------------------------------------------------------

    def transform_runner(self):
        if self._transform_runner is None:
            self._transform_runner = TransformRunner(_worker_command(), self)
            self._transform_runner.finished.connect(self._transform_finished)
        return self._transform_runner

    def run_transform_scenario(self, scenario, preview=False):
        """Lance ``scenario`` (``preview`` : dans un dossier temporaire, ouvert
        aussitôt). True si l'exécution a commencé ; le compte rendu vient
        quand le processus a fini."""
        runner = self.transform_runner()
        if runner.running():
            QMessageBox.information(self, _t("transform.title"), _t("transform.busy"))
            return False
        current = self._transform_current_path()
        problems = scenario_problems(scenario, self.project, current)
        if problems:
            QMessageBox.warning(self, _t("transform.title"), _t(
                "transform.cannot_run", name=scenario.name, problems="\n".join(problem_text(p) for p in problems)))
            return False
        if not self._save_for_transform(scenario, current):
            return False
        output_dir = self._transform_preview_dir() if preview else None
        request = scenario_request(scenario, self.project, current, output_dir)
        if not preview:
            self._remember_transform_scenario(scenario)
        self._transform_running = (scenario, preview, request)
        runner.start(request)
        self._show_transform_progress(scenario)
        return True

    def _save_for_transform(self, scenario, current):
        """Enregistre ce que le scénario lit et qui est modifié : l'édition, ses
        parties et le fragment non appliqué (comme pour l'export web), le
        document ou le fichier source, la feuille et la CSS s'ils sont ouverts.
        False si l'un d'eux ne l'est pas."""
        source, assembled = scenario_source(scenario, self.project, current)
        if assembled and not self._save_edition_for_export():
            return False
        read = {path_key(path) for path in (source, stylesheet_path(scenario, self.project),
                                           resolve_path(self.project, scenario.css)) if path}
        for session in list(self.documents):
            if session.path is None or path_key(session.path) not in read:
                continue
            if session is self.document:
                if self._has_unsaved_work() and not self.save_contextual():
                    return False
            elif session.modified and not self._save_session(session):
                return False
        return True

    def _transform_preview_dir(self):
        """Dossier temporaire des aperçus, effacé à la fin de la session."""
        if self._transform_preview_folder is None:
            self._transform_preview_folder = tempfile.TemporaryDirectory(prefix="varians-apercu-")
        return Path(self._transform_preview_folder.name)

    def _show_transform_progress(self, scenario):
        progress = QProgressDialog(_t("transform.running", name=scenario.name), _t("transform.cancel"), 0, 0, self)
        progress.setWindowTitle(_t("transform.title"))
        progress.setWindowModality(Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(10 ** 8)         # montrée par la minuterie ci-dessous
        progress.setAutoClose(False)
        progress.setAutoReset(False)
        progress.canceled.connect(self.transform_runner().cancel)
        self.transform_progress = progress

        def show():
            if self.transform_progress is progress:
                progress.show()

        QTimer.singleShot(500, show)

    def _transform_finished(self, result):
        progress, self.transform_progress = self.transform_progress, None
        if progress is not None:
            progress.canceled.disconnect()
            progress.close()
            progress.deleteLater()
        if self._transform_running is None:
            return
        scenario, preview, request = self._transform_running
        self._transform_running = None
        if result.error_code == "cancelled":
            self.statusBar().showMessage(_t("transform.cancelled", name=scenario.name), 8000)
            return
        journal = transform_journal(result, request)
        if not result.ok:
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Warning)
            box.setWindowTitle(_t("transform.failed.title"))
            box.setText(_t("transform.failed.text", name=scenario.name,
                           error=_t(f"transform.error.{result.error_code}", detail=result.error)))
            box.setDetailedText(journal)
            box.addButton(_t("common.close"), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            return
        output = result.outputs[0]
        if preview:
            QDesktopServices.openUrl(QUrl.fromLocalFile(output))
            return
        text = _t("transform.done.text", name=scenario.name, count=len(result.outputs),
                  seconds=f"{result.seconds:.2f}", output=output)
        refused = [detail for code, detail in result.journal if code == "write_refused"]
        if refused:
            text += _t("transform.done.refused", files="\n".join(refused))
        box = QMessageBox(self)
        box.setWindowTitle(_t("transform.done.title"))
        box.setText(text)
        box.setDetailedText(journal)
        open_btn = box.addButton(_t("common.open"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_t("common.close"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(output))


def transform_journal(result, request):
    """Journal d'une exécution, ligne à ligne, dans la langue de l'interface."""
    engine = engine_label(result.engine) + (f" — {result.version}" if result.version else "")
    lines = [_t("transform.journal.engine", engine=engine, seconds=f"{result.seconds:.2f}")]
    params = request.get("params") or []
    if params:
        lines.append(_t("transform.journal.params", params=" ; ".join(f"{name} = {value}" for name, value in params)))
    for code, detail in result.journal:
        lines.append(_t(f"transform.journal.{code}", detail=detail) if code in JOURNAL_CODES else f"{code}: {detail}")
    return "\n".join(lines)
