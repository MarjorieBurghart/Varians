# -*- coding: utf-8 -*-
"""Actions de projet de la fenêtre principale : export du viewer web, ouverture, création et réglages de projet, gestionnaire IIIF."""
from __future__ import annotations

import os
import shutil
import tempfile
import xml.etree.ElementTree as ET

from pathlib import Path

from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import QDialog, QFileDialog, QMessageBox
from app_context import (
    current_i18n, HERE, remember_recent_project, remove_recent_project, tr as _t,
)
from project_dialogs import NewProjectDialog, ProjectSettingsDialog, run_pivot_scaffold_dialog
from project_management import (
    create_local_xslt_if_needed, create_new_transcription_project, create_portable_project,
    prepare_alignment_files_for_project, prepare_alto_files_for_project,
    prepare_iiif_manifests_for_project, prepare_local_images_for_project,
    write_project_xml,
)
from tei_facsimile import (
    previous_surface_labels, project_facsimile_pages, removable_generated_iiif_surfaces,
    sync_facsimile_file,
)


class ProjectActionsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def generate_web_viewer(self):
        """Sauvegarde l'édition du projet puis lance le générateur web générique.

        L'édition est enregistrée si nécessaire, même lorsqu'un document
        auxiliaire est affiché ; les autres documents ne sont pas concernés.
        """
        edition = self.edition_session
        if edition.path is None:
            return
        if edition.path.resolve() != self.project.edition.resolve():
            QMessageBox.warning(
                self, _t("webgen.wrong_file.title"), _t("webgen.wrong_file.text")
            )
            return
        if edition is self.document:
            if self._has_unsaved_work() and not self.save_contextual():
                return
        elif edition.modified and not self._save_session(edition):
            return
        try:
            from web_viewer.generator import generate
            # Presentation preferences belong to QSettings, NOT project.xml.
            # Export their *current* effective state, including detached panels.
            # The generator keeps the pivot as a technical source when hidden.
            visible = set(self._visible_witness_ids)
            display_ids = [wid for wid in self._witness_display_order if wid in visible]
            output, missing, data = generate(
                self.project.path, display_witness_ids=display_ids)
        except Exception as exc:
            QMessageBox.critical(self, _t("webgen.error.title"), str(exc))
            return
        msg = _t("webgen.done.text", output=output, witnesses=len(data.get("witnesses", [])), lines=data.get("meta", {}).get("lines", 0))
        if missing:
            msg += _t("webgen.missing", pages=", ".join(missing))
        box = QMessageBox(self)
        box.setWindowTitle(_t("webgen.done.title"))
        box.setText(msg)
        open_btn = box.addButton(_t("common.open"), QMessageBox.ButtonRole.AcceptRole)
        box.addButton(_t("common.close"), QMessageBox.ButtonRole.RejectRole)
        box.exec()
        if box.clickedButton() is open_btn:
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(output)))

    def open_project_dialog(self):
        """Sélectionne un project.xml puis recharge l'application sur ce projet."""
        fn, _ = QFileDialog.getOpenFileName(
            self,
            _t("project.open.title"),
            str(self.project.path.parent),
            f"{_t('project.open.filter')} (*.xml);;{_t('common.all_files')} (*)",
        )
        if fn:
            self._replace_with_project(Path(fn))

    def open_recent_project(self, path):
        path = Path(path).expanduser().resolve()
        if not path.is_file():
            remove_recent_project(path)
            self.update_recent_projects_menu()
            QMessageBox.warning(self, _t("project.recent.missing.title"), _t("project.recent.missing", path=path))
            return
        self._replace_with_project(path)

    def new_project_dialog(self):
        """Crée un projet depuis une TEI existante ou une nouvelle transcription."""
        I18N = current_i18n()
        languages = [(info.code, info.label) for info in I18N.available_languages()]
        dlg = NewProjectDialog(_t, languages, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        values = dlg.values()
        try:
            creator = (create_new_transcription_project
                       if values.get("creation_mode") == "blank" else create_portable_project)
            if values.get("creation_mode") == "blank":
                project_path = creator(
                    values["target_dir"], values["title"],
                    values["witnesses"], values["base_witness"], HERE,
                    values["language"], self.project.fallback_language,
                    xslt_mode=values["xslt_mode"],
                    schema_source=values.get("schema"),
                    schema_mode=values.get("schema_mode", "auto"),
                )
            else:
                project_path = creator(
                    values["target_dir"], values["title"], values["edition"],
                    values["witnesses"], values["base_witness"], HERE,
                    values["language"], self.project.fallback_language,
                    xslt_mode=values["xslt_mode"],
                    schema_source=values.get("schema"),
                    schema_mode=values.get("schema_mode", "auto"),
                )
        except Exception as exc:
            message = _t("project.new.error.target_not_empty") if str(exc) == "TARGET_NOT_EMPTY" else str(exc)
            QMessageBox.critical(self, _t("project.new.error.title"), message)
            return
        if values.get('prepare_pivot') and values.get('creation_mode') == 'blank':
            from project_config import load_project as _load_pivot_project
            created = _load_pivot_project(project_path)
            run_pivot_scaffold_dialog(_t, self, created.witnesses, created.base_witness,
                                      created.root_dir, created.edition,
                                      include_lb=values.get('pivot_lines', True))
        remember_recent_project(project_path)
        QMessageBox.information(self, _t("project.new.done.title"), _t("project.new.done", path=project_path))
        if self._replace_with_project(project_path):
            new_window = self._replacement_window
            if any(w.image_source_type == 'iiif' and (
                w.iiif_local_copy or w.iiif_web_local_copy) for w in values['witnesses']):
                QTimer.singleShot(0, lambda: new_window.open_iiif_download_manager(auto_start=True))

    def open_iiif_download_manager(self, auto_start=False):
        """Open the non-modal IIIF manager; one job at a time per project."""
        from iiif_download_manager import IIIFDownloadManager
        manager = getattr(self, '_iiif_download_dialog', None)
        if manager is not None:
            manager.show()
            manager.raise_()
            manager.activateWindow()
            return
        manager = IIIFDownloadManager(_t, self.project, self, auto_start=auto_start)
        self._iiif_download_dialog = manager
        manager.show()

    def project_settings_dialog(self):
        """Modifie graphiquement project.xml puis recharge le projet."""
        I18N = current_i18n()
        if not self.maybe_save():
            return
        languages = [(info.code, info.label) for info in I18N.available_languages()]
        dlg = ProjectSettingsDialog(_t, self.project, languages, self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            draft = dlg.draft()
            draft.witnesses = prepare_alignment_files_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_local_images_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_alto_files_for_project(self.project.root_dir, draft.witnesses)
            draft.witnesses = prepare_iiif_manifests_for_project(self.project.root_dir, draft.witnesses)
            # Le gestionnaire est lancé après la sauvegarde, hors du thread UI.
            start_iiif = any(w.image_source_type == 'iiif' and (
                w.iiif_local_copy or w.iiif_web_local_copy) for w in draft.witnesses)

            # La couche page↔image conserve l'autorité TEI sans altérer les zones.
            facsimile_pages = project_facsimile_pages(draft.witnesses, self.project.root_dir, draft.edition)
            facsimile_report = sync_facsimile_file(
                draft.edition, facsimile_pages, previous_surface_labels(self.project.witnesses)
            ) if facsimile_pages else None
            # En passant du mode « XSLT application » au mode « personnalisée »,
            # initialiser une copie locale si elle n'existe pas, sans jamais
            # remplacer un fichier personnalisé déjà présent.
            create_local_xslt_if_needed(self.project.path.parent, draft)
            if self.project.path.exists():
                shutil.copy2(self.project.path, self.project.path.with_suffix(self.project.path.suffix + ".bak"))
            write_project_xml(self.project.path, draft)
            # Existing TEI surfaces belong to the edition. They are never
            # silently deleted when a new IIIF page selection excludes them.
            # Only strictly unchanged and unreferenced Varians-generated
            # surfaces may be offered for explicit removal, with a backup.
            for w in draft.witnesses:
                if (w.image_source_type != 'iiif' or
                    getattr(w, 'iiif_selection_mode', 'all') != 'selected'):
                    continue
                previous_witness = self.project.witness_by_id.get(w.id)
                if (previous_witness is not None and
                    getattr(previous_witness, 'iiif_selection_mode', 'all') == 'selected' and
                    tuple(getattr(previous_witness, 'iiif_selected_canvases', ())) ==
                    tuple(getattr(w, 'iiif_selected_canvases', ()))):
                    # Don't repeatedly prompt a scholar who has chosen to
                    # retain existing TEI surfaces on a previous save.
                    continue
                from iiif_manifest import cache_path, read_cache
                manifest = read_cache(cache_path(self.project.root_dir, w.id), w.image_source_value)
                if manifest is None:
                    continue
                xml_text = Path(draft.edition).read_text(encoding='utf-8-sig')
                try:
                    updated, candidates = removable_generated_iiif_surfaces(
                        xml_text, manifest, w.id, getattr(w, 'iiif_selected_canvases', ()))
                except ET.ParseError:
                    # Optional cleanup must not prevent valid project setting
                    # changes if an in-progress TEI cannot be parsed here.
                    continue
                if not candidates:
                    continue
                choice = QMessageBox.question(
                    self, _t('iiif.prune.title'),
                    _t('iiif.prune.question', witness=w.label, count=len(candidates),
                       ids=', '.join(candidates[:8]) + ('…' if len(candidates) > 8 else '')),
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No,
                )
                if choice != QMessageBox.StandardButton.Yes:
                    continue
                path = Path(draft.edition)
                # Unique dated backup, never overwrite an existing backup.
                from datetime import datetime
                stamp = datetime.now().strftime('%Y%m%d-%H%M%S-%f')
                backup = path.with_name(path.name + '.pre-iiif-cleanup-' + stamp + '.bak')
                shutil.copy2(path, backup)
                with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                                                 prefix='.varians-iiif-', suffix='.tmp',
                                                 delete=False) as output:
                    output.write(updated)
                    temp_name = output.name
                try:
                    os.replace(temp_name, path)
                finally:
                    if os.path.exists(temp_name):
                        os.unlink(temp_name)
            if dlg.pivot_prepare.isChecked():
                run_pivot_scaffold_dialog(_t, self, draft.witnesses, draft.base_witness,
                                          self.project.root_dir, draft.edition,
                                          include_lb=dlg.pivot_lines.isChecked())
            remember_recent_project(self.project.path)
        except Exception as exc:
            QMessageBox.critical(self, _t("project.settings.error.title"), str(exc))
            return
        if facsimile_report is not None and facsimile_report.conflicts:
            QMessageBox.warning(
                self, _t("facsimile.warning.title"),
                _t("facsimile.warning.preserved") + "\n\n" + "\n".join(facsimile_report.conflicts),
            )
        QMessageBox.information(self, _t("project.settings.saved.title"), _t("project.settings.saved"))
        # maybe_save() a déjà été exécuté ; on recharge immédiatement les chemins,
        # témoins et ressources qui viennent d'être modifiés.
        try:
            new_window = type(self)(self.project.path)
        except Exception as exc:
            QMessageBox.critical(self, _t("project.open_error"), str(exc))
            return
        self._replacement_window = new_window
        new_window.showMaximized()
        if start_iiif:
            QTimer.singleShot(0, lambda: new_window.open_iiif_download_manager(auto_start=True))
        self._force_close = True
        self.close()
