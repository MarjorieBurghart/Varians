# -*- coding: utf-8 -*-
"""Dialogues de création et modification des projets Varians : « Nouveau
projet », « Paramètres du projet », préparation du pivot. La table des
témoins (``witness_table``), la fiche d'un témoin (``witness_edit_dialog``),
le choix des pages IIIF (``iiif_canvas_picker``) et ``PathRow``
(``project_widgets``) ont leur module (V0.9.4.7)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox, QComboBox, QDialog, QDialogButtonBox, QFormLayout, QGroupBox, QLabel,
    QLineEdit, QMessageBox, QScrollArea, QVBoxLayout, QWidget,
)

from project_management import ProjectDraft
from app_context import APP_VERSION
from tei_listwit import add_witnesses_to_listwit, blocking_message
from i18n import message_text
from witness_table import WitnessTable
from project_widgets import PathRow


def run_pivot_scaffold_dialog(tr, parent, witnesses, base_witness, project_root,
                              edition_path, *, include_lb=True):
    """Preview and explicitly authorize the only permitted blank-TEI mutation."""
    from tei_pivot_scaffold import (build_pivot_plan, scaffold_is_empty,
                                   write_pivot_scaffold)
    try:
        source = Path(edition_path).read_text(encoding='utf-8-sig')
        if not scaffold_is_empty(source):
            QMessageBox.warning(parent, tr('pivot.title'), tr('pivot.not_empty'))
            return False
        plan = build_pivot_plan(witnesses, base_witness, project_root, edition_path)
        if not plan.pages:
            QMessageBox.warning(parent, tr('pivot.title'), tr('pivot.no_pages'))
            return False
    except Exception as exc:
        QMessageBox.warning(parent, tr('pivot.title'), message_text(getattr(exc, 'message', exc), tr))
        return False
    message = QMessageBox(parent)
    message.setWindowTitle(tr('pivot.preview.title'))
    message.setIcon(QMessageBox.Icon.Question)
    sigla = {w.id: getattr(w, 'display_siglum', w.id) for w in witnesses}
    message.setText(tr('pivot.preview.summary', witness=sigla.get(plan.witness_id, plan.witness_id),
                       pages=len(plan.pages), lines=plan.line_count if include_lb else 0))
    overview = '\n'.join(f'{x.label} → #{x.surface_id} : {x.line_count if include_lb else 0} lb '
                         f'({message_text(x.evidence, tr)})' for x in plan.pages)
    if plan.warnings:
        overview += ('\n\n' + tr('pivot.preview.warnings') + '\n'
                     + '\n'.join(message_text(w, tr) for w in plan.warnings))
    message.setDetailedText(overview)
    message.setInformativeText(tr('pivot.preview.confirm'))
    message.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    message.setDefaultButton(QMessageBox.StandardButton.No)
    if message.exec() != QMessageBox.StandardButton.Yes:
        return False
    try:
        backup = write_pivot_scaffold(edition_path, plan, include_lb=include_lb)
    except Exception as exc:
        QMessageBox.critical(parent, tr('pivot.title'), message_text(getattr(exc, 'message', exc), tr))
        return False
    QMessageBox.information(parent, tr('pivot.title'),
                            tr('pivot.done', backup=backup or ''))
    return True


class NewProjectDialog(QDialog):
    """Boîte « Nouveau projet… » (menu « Fichier ») : dossier, titre, point de départ (TEI
    existante ou transcription vierge, avec la préparation de la transcription du témoin
    pivot), schéma, langue, XSLT et témoins. Elle vérifie les choix à « OK » mais ne crée
    rien : la fenêtre crée le projet d'après ``values()``."""
    def __init__(self, tr, languages, parent=None):
        super().__init__(parent)
        self.tr = tr
        # La version dans le titre aide à repérer une ancienne session (Spyder, module déjà chargé).
        self.setWindowTitle(f'{tr("project.new.title")} — Varians {APP_VERSION}')
        self.resize(950, 690)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        form = QFormLayout()
        self.folder = PathRow("", self, "dir", tr("project.new.folder.choose"))
        self.title_edit = QLineEdit()
        self.creation_mode = QComboBox()
        self.creation_mode.addItem(tr("project.new.mode.existing"), "existing")
        self.creation_mode.addItem(tr("project.new.mode.blank"), "blank")
        self.creation_mode.currentIndexChanged.connect(self._creation_mode_changed)
        # Keep the TEI preparation choices next to "Starting point", not below
        # the large, resizable witnesses table where they can be clipped.
        self.pivot_section = QGroupBox(tr('pivot.title'))
        pivot_box = QVBoxLayout(self.pivot_section)
        self.pivot_prepare = QCheckBox(tr('pivot.option.pb'))
        self.pivot_lines = QCheckBox(tr('pivot.option.lb'))
        self.pivot_lines.setChecked(True)
        self.pivot_prepare.toggled.connect(self.pivot_lines.setEnabled)
        self.pivot_prepare.toggled.connect(self._pivot_enabled)
        self.pivot_prepare.setChecked(False)
        self.pivot_lines.setEnabled(False)
        pivot_box.addWidget(self.pivot_prepare)
        pivot_box.addWidget(self.pivot_lines)
        self.edition = PathRow("", self, "file", tr("project.edition.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_mode = QComboBox()
        self.schema_mode.addItem(tr("project.schema.mode.auto"), "auto")
        self.schema_mode.addItem(tr("project.schema.mode.file"), "file")
        self.schema_mode.addItem(tr("project.schema.mode.none"), "none")
        self.schema = PathRow("", self, "file", tr("project.schema.choose"), f"RELAX NG (*.rng);;XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_hint = QLabel(tr("project.schema.hint.auto")); self.schema_hint.setWordWrap(True)
        self.schema_mode.currentIndexChanged.connect(self._schema_mode_changed)
        self.language = QComboBox()
        for code, label in languages: self.language.addItem(label, code)
        self.xslt_mode = QComboBox()
        self.xslt_mode.addItem(tr("project.xslt.mode.builtin"), "builtin")
        self.xslt_mode.addItem(tr("project.xslt.mode.file"), "file")
        form.addRow(tr("project.new.folder"), self.folder)
        form.addRow(tr("project.title"), self.title_edit)
        form.addRow(tr("project.new.mode"), self.creation_mode)
        form.addRow('', self.pivot_section)
        form.addRow(tr("project.edition"), self.edition)
        form.addRow(tr("project.schema.mode"), self.schema_mode)
        form.addRow(tr("project.schema.file"), self.schema)
        form.addRow("", self.schema_hint)
        form.addRow(tr("common.language"), self.language)
        form.addRow(tr("project.xslt.mode"), self.xslt_mode)
        self._schema_mode_changed()
        self._creation_mode_changed()
        root.addLayout(form)
        group = QGroupBox(tr("project.witnesses")); gl = QVBoxLayout(group)
        self.witnesses_table = WitnessTable(tr, parent=self); gl.addWidget(self.witnesses_table)
        self.witnesses_table.witnesses_changed.connect(self._creation_mode_changed)
        root.addWidget(group, 1)
        self.info = QLabel(tr("project.new.info")); self.info.setWordWrap(True); root.addWidget(self.info)
        self._creation_mode_changed()
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); outer.addWidget(buttons)

    def _accept(self):
        folder = Path(self.folder.text()).expanduser()
        edition = Path(self.edition.text()).expanduser() if self.edition.text() else None
        witnesses = self.witnesses_table.witnesses()
        if not self.folder.text():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.folder_required")); return
        if folder.exists() and any(folder.iterdir()):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.folder_not_empty")); return
        if self.creation_mode.currentData() == "existing" and (edition is None or not edition.is_file()):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.edition_missing", path=edition or "")); return
        if self.schema_mode.currentData() == "file" and not Path(self.schema.text()).expanduser().is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.schema_missing", path=self.schema.text())); return
        # Sans témoin, le projet n'a pas de pivot : les témoins s'ajoutent plus tard.
        if witnesses and not self.witnesses_table.base_witness():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_base")); return
        self.accept()

    def _creation_mode_changed(self, *_):
        mode = self.creation_mode.currentData() or "existing"
        self.edition.setEnabled(mode == "existing")
        if hasattr(self, 'pivot_prepare'):
            # La transcription du témoin pivot ne se prépare qu'avec un témoin.
            possible = mode == 'blank' and bool(hasattr(self, "witnesses_table") and self.witnesses_table.witnesses())
            self.pivot_prepare.setEnabled(possible)
            self.pivot_lines.setEnabled(possible and self.pivot_prepare.isChecked())
        if hasattr(self, "info"):
            self.info.setText(self.tr("project.new.info.blank" if mode == "blank" else "project.new.info"))

    def _pivot_enabled(self, *_):
        self.pivot_lines.setEnabled(self.pivot_prepare.isChecked() and self.pivot_prepare.isEnabled() and
                                    self.creation_mode.currentData() == 'blank')

    def _schema_mode_changed(self, *_):
        mode = self.schema_mode.currentData() or "auto"
        self.schema.setEnabled(mode == "file")
        self.schema_hint.setText(self.tr(f"project.schema.hint.{mode}"))

    def values(self):
        """Choix de la boîte, en dictionnaire : ``target_dir``, ``title`` (le nom du dossier par
        défaut), ``creation_mode`` (``existing`` ou ``blank``), ``edition`` (None pour une
        transcription vierge), ``schema_mode``, ``schema``, ``language``, ``xslt_mode``,
        ``witnesses``, ``base_witness`` (le pivot), ``prepare_pivot`` (vrai seulement pour une
        transcription vierge) et ``pivot_lines``. Les chemins sont absolus."""
        return {
            "target_dir": Path(self.folder.text()).expanduser().resolve(),
            "title": self.title_edit.text().strip() or Path(self.folder.text()).name,
            "creation_mode": self.creation_mode.currentData() or "existing",
            "edition": (Path(self.edition.text()).expanduser().resolve()
                        if self.creation_mode.currentData() == "existing" and self.edition.text() else None),
            "schema_mode": self.schema_mode.currentData() or "auto",
            "schema": Path(self.schema.text()).expanduser().resolve() if self.schema_mode.currentData() == "file" and self.schema.text() else None,
            "language": self.language.currentData() or "fr",
            "xslt_mode": self.xslt_mode.currentData() or "builtin",
            "witnesses": self.witnesses_table.witnesses(),
            "base_witness": self.witnesses_table.base_witness(),
            "prepare_pivot": self.pivot_prepare.isChecked() and self.creation_mode.currentData() == 'blank'
                             and bool(self.witnesses_table.witnesses()),
            "pivot_lines": self.pivot_lines.isChecked(),
        }


class ProjectSettingsDialog(QDialog):
    """Boîte « Paramètres du projet… » : titre, fichiers de l'édition, du schéma, de la XSLT, de
    la CSS et des éléments personnalisés, traductions, sortie web, préparation de la
    transcription du témoin pivot et témoins. ``exec()`` rend ``Accepted``, ou ``RENAME``
    quand « Changer le sigle… » est demandé (``rename_witness_id``). Elle n'écrit rien :
    ``project_actions`` enregistre ``draft()`` et lit les cases ``pivot_prepare`` et
    ``pivot_lines``."""
    # Code de retour de exec() : changer le sigle de ``rename_witness_id``.
    RENAME = 2

    def __init__(self, tr, project, languages, parent=None):
        super().__init__(parent)
        self.tr = tr; self.project = project
        self.rename_witness_id = None
        self.setWindowTitle(f'{tr("project.settings.title")} — Varians {APP_VERSION}')
        self.resize(980, 740)
        outer = QVBoxLayout(self)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        content = QWidget(scroll)
        root = QVBoxLayout(content)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        form = QFormLayout()
        self.title_edit = QLineEdit(project.title)
        self.edition = PathRow(project.edition, self, "file", tr("project.edition.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_mode = QComboBox()
        self.schema_mode.addItem(tr("project.schema.mode.auto"), "auto")
        self.schema_mode.addItem(tr("project.schema.mode.file"), "file")
        self.schema_mode.addItem(tr("project.schema.mode.none"), "none")
        sm_idx = self.schema_mode.findData(getattr(project, "schema_mode", "auto"))
        self.schema_mode.setCurrentIndex(max(0, sm_idx))
        self.schema = PathRow(project.schema or "", self, "file", tr("project.schema.choose"), f"RELAX NG (*.rng);;XML (*.xml);;{tr('common.all_files')} (*)")
        self.schema_hint = QLabel(tr("project.schema.hint.auto")); self.schema_hint.setWordWrap(True)
        self.schema_mode.currentIndexChanged.connect(self._schema_mode_changed)
        self.language = QComboBox()
        for code, label in languages: self.language.addItem(label, code)
        idx = self.language.findData(project.language)
        if idx >= 0: self.language.setCurrentIndex(idx)
        self.xslt_mode = QComboBox()
        self.xslt_mode.addItem(tr("project.xslt.mode.builtin"), "builtin")
        self.xslt_mode.addItem(tr("project.xslt.mode.file"), "file")
        idx = self.xslt_mode.findData(project.xslt_mode)
        self.xslt_mode.setCurrentIndex(max(0, idx))
        suggested_custom_xslt = (project.root_dir / "rendering" / "tei-to-html.xsl")
        self.xslt = PathRow(
            project.xslt if project.xslt_mode == "file" else suggested_custom_xslt,
            self, "file", tr("project.xslt.choose"),
            f"XSLT (*.xsl *.xslt);;{tr('common.all_files')} (*)")
        self.xslt_hint = QLabel(tr("project.xslt.hint.builtin"))
        self.xslt_hint.setWordWrap(True)
        self.xslt_mode.currentIndexChanged.connect(self._xslt_mode_changed)
        self.css = PathRow(project.css, self, "file", tr("project.css.choose"), f"CSS (*.css);;{tr('common.all_files')} (*)")
        self.custom = PathRow(project.custom_elements, self, "file", tr("project.custom.choose"), f"XML (*.xml);;{tr('common.all_files')} (*)")
        self.translations = PathRow(project.translations_dir, self, "dir", tr("project.i18n.choose"))
        self.web_output = PathRow(project.web_output_dir, self, "dir", tr("project.web_output.choose"))
        self.web_filename = QLineEdit(project.web_filename)
        for label, widget in [
            (tr("project.title"), self.title_edit), (tr("project.edition"), self.edition),
            (tr("project.schema.mode"), self.schema_mode),
            (tr("project.schema.file"), self.schema),
            ("", self.schema_hint),
            (tr("common.language"), self.language),
            (tr("project.xslt.mode"), self.xslt_mode),
            (tr("project.xslt"), self.xslt),
            ("", self.xslt_hint),
            (tr("project.css"), self.css), (tr("project.custom"), self.custom),
            (tr("project.i18n"), self.translations), (tr("project.web_output"), self.web_output),
            (tr("project.web_filename"), self.web_filename),
        ]: form.addRow(label, widget)
        self._schema_mode_changed()
        self._xslt_mode_changed()
        root.addLayout(form)
        self.pivot_section = QGroupBox(tr('pivot.title'))
        pivot_box = QVBoxLayout(self.pivot_section)
        self.pivot_prepare = QCheckBox(tr('pivot.option.pb'))
        self.pivot_lines = QCheckBox(tr('pivot.option.lb'))
        self.pivot_lines.setChecked(True)
        self.pivot_lines.setEnabled(False)
        self.pivot_prepare.toggled.connect(self.pivot_lines.setEnabled)
        pivot_box.addWidget(self.pivot_prepare)
        pivot_box.addWidget(self.pivot_lines)
        root.addWidget(self.pivot_section)
        group = QGroupBox(tr("project.witnesses")); gl = QVBoxLayout(group)
        self.witnesses_table = WitnessTable(tr, project.witnesses, project.base_witness, self, project_root=project.root_dir,
                                            saved_ids={w.id for w in project.witnesses}); gl.addWidget(self.witnesses_table)
        self._saved_witness_ids = {w.id for w in project.witnesses}
        self.witnesses_table.rename_requested.connect(self._rename_requested)
        self.witnesses_table.witnesses_changed.connect(self._pivot_possible)
        self._pivot_possible()
        root.addWidget(group, 1)
        # Refresh is an explicit manager action; saving settings never refetches
        # existing IIIF images without a deliberate user request.
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._accept); buttons.rejected.connect(self.reject); outer.addWidget(buttons)
        self._initial_draft = self._current_draft()

    def _current_draft(self):
        try:
            return self.draft()
        except Exception:
            return None

    def _listwit_blocking(self, edition, witnesses):
        """Message qui refuse l'ajout de ``witnesses`` si l'édition ne permet
        pas de les déclarer dans sa <listWit> (essai à blanc) ; sinon None."""
        try:
            text = Path(edition).read_bytes().decode("utf-8")
        except (OSError, UnicodeError):
            return None
        report = add_witnesses_to_listwit(text, witnesses)[1]
        return blocking_message(report, self.tr, [getattr(w, "display_siglum", w.id) for w in witnesses])

    def _pivot_possible(self, *_):
        """La transcription du témoin pivot ne se prépare qu'avec un témoin."""
        possible = bool(self.witnesses_table.witnesses())
        self.pivot_prepare.setEnabled(possible)
        if not possible:
            self.pivot_prepare.setChecked(False)
        self.pivot_lines.setEnabled(possible and self.pivot_prepare.isChecked())

    def _rename_requested(self, witness_id):
        """« Changer le sigle… » : la boîte se ferme (code RENAME) et Varians
        ouvre celle du changement de sigle, qui écrit aussitôt sur le disque.
        D'autres modifications en cours des paramètres sont d'abord à
        enregistrer ou à annuler."""
        current = self._current_draft()
        if current is None or current != self._initial_draft:
            QMessageBox.information(self, self.tr("witness_rename.title"), self.tr("witness_rename.pending_settings"))
            return
        self.rename_witness_id = witness_id
        self.done(self.RENAME)

    def _schema_mode_changed(self, *_):
        mode = self.schema_mode.currentData() or "auto"
        self.schema.setEnabled(mode == "file")
        self.schema_hint.setText(self.tr(f"project.schema.hint.{mode}"))

    def _xslt_mode_changed(self, *_):
        mode = self.xslt_mode.currentData() or "builtin"
        self.xslt.setEnabled(mode == "file")
        self.xslt_hint.setText(self.tr("project.xslt.hint.file" if mode == "file" else "project.xslt.hint.builtin"))

    def _accept(self):
        edition = Path(self.edition.text()).expanduser()
        witnesses = self.witnesses_table.witnesses()
        if not edition.is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.edition_missing", path=edition)); return
        if self.schema.text() and not Path(self.schema.text()).expanduser().is_file():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.schema_missing", path=self.schema.text())); return
        if witnesses and not self.witnesses_table.base_witness():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.no_base")); return
        # Un témoin ajouté doit pouvoir être déclaré dans la <listWit> de
        # l'édition : sinon l'ajout attend que l'édition soit corrigée.
        added = [w for w in witnesses if w.id not in self._saved_witness_ids]
        blocked = self._listwit_blocking(edition, added) if added else None
        if blocked:
            QMessageBox.warning(self, self.tr("project.listwit.blocked.title"), blocked); return
        for w in witnesses:
            if w.alignment is not None and not Path(w.alignment).is_file():
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.alignment_missing", path=w.alignment)); return
        required = [self.css.text(), self.custom.text()]
        if any(not Path(x).expanduser().is_file() for x in required):
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.rendering_missing")); return
        if self.xslt_mode.currentData() == "file":
            chosen_xslt = Path(self.xslt.text()).expanduser().resolve()
            expected_xslt = self.project.root_dir / "rendering" / "tei-to-html.xsl"
            if not chosen_xslt.is_file() and chosen_xslt != expected_xslt:
                QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.xslt_missing", path=chosen_xslt)); return
        if not Path(self.translations.text()).expanduser().is_dir():
            QMessageBox.warning(self, self.tr("project.validation.title"), self.tr("project.validation.i18n_missing")); return
        self.accept()

    def draft(self):
        """Les réglages de la boîte en ``ProjectDraft`` : chemins absolus, témoins du tableau et
        pivot. Ce que la boîte ne montre pas (documents, requêtes XPath, parties,
        transformations, réglages du texte web) est repris du projet tel quel, pour que la
        réécriture de project.xml ne l'efface pas. Aussi appelée à l'ouverture : « Changer le
        sigle… » n'est permis que si rien n'a changé depuis."""
        return ProjectDraft(
            title=self.title_edit.text().strip() or self.project.path.parent.name,
            edition=Path(self.edition.text()).expanduser().resolve(),
            schema_mode=self.schema_mode.currentData() or "auto",
            schema=Path(self.schema.text()).expanduser().resolve() if self.schema_mode.currentData() == "file" and self.schema.text() else None,
            schema_type="relaxng",
            language=self.language.currentData() or self.project.language,
            fallback_language=self.project.fallback_language,
            translations_dir=Path(self.translations.text()).expanduser().resolve(),
            xslt=Path(self.xslt.text()).expanduser().resolve(),
            xslt_mode=self.xslt_mode.currentData() or "builtin",
            css=Path(self.css.text()).expanduser().resolve(),
            custom_elements=Path(self.custom.text()).expanduser().resolve(),
            web_output_dir=Path(self.web_output.text()).expanduser().resolve(),
            web_filename=self.web_filename.text().strip() or "viewer.html",
            witnesses=self.witnesses_table.witnesses(),
            base_witness=self.witnesses_table.base_witness(),
            # Non modifiables ici : conservés tels quels, sinon la réécriture
            # de project.xml les effacerait.
            documents=list(self.project.documents),
            xpath_queries=list(self.project.xpath_queries),
            parts=list(self.project.parts),
            transformations=list(self.project.transformations),
            web_text_mode=self.project.web_text_mode,
            web_text_witness=self.project.web_text_witness,
            web_highlight_nonlem=self.project.web_highlight_nonlem,
        )
