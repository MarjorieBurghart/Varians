# -*- coding: utf-8 -*-
"""Vues nommées de la vue XSLT / CSS (V0.9.4.7, extrait de formatted_view) :
chaque document a la vue du projet et ses vues nommées (project.xml,
``<view>``), choisies dans une liste ; Nouvelle vue, Modifier, Retirer ;
feuille XSLT et CSS de la vue choisie."""
from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtWidgets import QDialog, QMessageBox

from app_context import _settings, tr as _t
from fragment_units import chosen_units
from preview_css import PREVIEW_BASE_CSS, has_own_style


class ViewsMixin:
    """Vues nommées de ``FormattedEditionWidget`` (dont elle hérite)."""

    @property
    def current_view(self):
        """Vue choisie : None pour la vue du projet, sinon une vue nommée
        (``ViewConfig``) du document affiché."""
        return self._current_view

    @property
    def xsl_path(self):
        """Feuille XSLT de la vue choisie : celle de la vue nommée (chemin
        relatif au projet, ou ``${varians}/…``), sinon celle du projet."""
        view = self._current_view
        if view is not None:
            path = self._view_file(view.xslt)
            if path is not None:
                return path
        return self.main.project.xslt

    def _css_mode(self):
        """CSS de l'aperçu (V0.9.4.4) : ``file`` (fichier de la vue),
        ``project`` (vue du projet, ou ``projectCss="always"``), ``never``
        (aucune) ou ``auto`` (celle du projet, sauf si la feuille produit son
        propre ``<style>``)."""
        view = self._current_view
        if view is None:
            return "project"
        if view.css.strip():
            return "file"
        return {"always": "project", "never": "never"}.get(view.project_css, "auto")

    def _preview_css(self, html_text):
        """CSS donnée à l'aperçu pour ``html_text`` : les règles de Varians
        (crayons, repères), puis, selon ``_css_mode``, le fichier CSS de la
        vue ou celui du projet."""
        mode = self._css_mode()
        if mode == "never" or (mode == "auto" and has_own_style(html_text)):
            return PREVIEW_BASE_CSS
        return self._resolved_css_cached()

    @property
    def css_path(self):
        """Fichier CSS de la vue choisie ; une vue nommée sans fichier CSS
        renvoie à celui du projet (``_css_mode`` dit s'il sert)."""
        view = self._current_view
        if view is not None:
            path = self._view_file(view.css)
            if path is not None:
                return path
        return self.main.project.css

    def _view_file(self, raw):
        from xslt_scenarios import resolve_path
        return resolve_path(self.main.project, raw)

    def _view_context(self):
        """``(clé, vues nommées)`` du document affiché : pour l'édition et
        ses parties, celles de l'édition (``<edition>``) ; pour un document
        auxiliaire, celles de son ``<document>``. La clé (chemin relatif au
        projet) retient la vue choisie dans les réglages du projet."""
        main = self.main
        session = getattr(main, "document", None)
        if session is None or session.in_edition or session.path is None:
            edition = getattr(main, "edition_session", None)
            path = getattr(edition, "path", None) or main.project.edition
            return "edition:" + main._place_key(path), tuple(main.project.edition_views)
        config = main.document_config(session)
        return main._place_key(session.path), tuple(config.views) if config is not None else ()

    def _remembered_views(self):
        try:
            data = json.loads(_settings().value(self.main._view_settings_key("previewViews"), "") or "{}")
        except (TypeError, ValueError):
            data = {}
        return data if isinstance(data, dict) else {}

    def _remember_view(self):
        if self._view_key is None:
            return
        data = self._remembered_views()
        if self._current_view is None:
            data.pop(self._view_key, None)
        else:
            data[self._view_key] = self._current_view.name
        _settings().setValue(self.main._view_settings_key("previewViews"), json.dumps(data, ensure_ascii=False))

    def context_changed(self):
        """Document affiché changé, ou ses vues : la liste montre celles du
        nouveau document, et la vue qui y avait été choisie la dernière fois.
        Passer de l'édition à l'une de ses parties ne change rien : l'aperçu
        reste celui de l'édition assemblée."""
        key, views = self._view_context()
        if key == self._view_key and views == self._views:
            return
        self._view_key, self._views = key, views
        name = self._remembered_views().get(key)
        self._current_view = next((view for view in views if view.name == name), None)
        self._fill_view_combo()
        self._reset_preview(clear=True)

    def _fill_view_combo(self):
        combo = self.view_combo
        combo.blockSignals(True)
        try:
            combo.clear()
            combo.addItem(_t("preview.view.project"), None)
            for view in self._views:
                combo.addItem(view.name, view.name)
            index = combo.findData(self._current_view.name) if self._current_view is not None else 0
            combo.setCurrentIndex(max(0, index))
        finally:
            combo.blockSignals(False)
        self._update_view_tip()
        self._update_view_actions()

    def _update_view_actions(self):
        """La vue du projet ne se modifie ni ne se retire ici (Paramètres du
        projet…) ; seule une feuille du projet s'ouvre dans un onglet."""
        named = self._current_view is not None
        self.edit_view_action.setEnabled(named)
        self.remove_view_action.setEnabled(named)
        self.open_view_stylesheet_action.setEnabled(named and self._project_stylesheet() is not None)

    def _project_stylesheet(self):
        """Feuille XSLT de la vue nommée choisie, si elle est un fichier du
        projet ; sinon None (feuille de Varians, fichier absent…)."""
        if self._current_view is None:
            return None
        path = self.xsl_path
        try:
            path.relative_to(Path(self.main.project.root_dir).resolve())
        except ValueError:
            return None
        return path if path.is_file() else None

    def _views_may_change(self):
        """Avant d'écrire les vues : un fragment ouvert est appliqué ou
        abandonné (ses éléments modifiables peuvent changer) ; False si
        l'utilisateur annule."""
        return self.frag_box.isHidden() or self.close_fragment_editor()

    def _store_views(self, views, chosen):
        """Écrit les vues nommées du document affiché dans project.xml, puis
        montre ``chosen`` (None : la vue du projet). False si l'écriture
        échoue (message déjà affiché)."""
        if not self.main.set_preview_views(views):
            return False
        data = self._remembered_views()
        if chosen is None:
            data.pop(self._view_key, None)
        else:
            data[self._view_key] = chosen.name
        _settings().setValue(self.main._view_settings_key("previewViews"), json.dumps(data, ensure_ascii=False))
        self._views = None                       # liste à refaire
        self.context_changed()
        if self.isVisible():
            self.refresh_preview(force=True)
        return True

    def _view_dialog(self, view=None, units=()):
        from view_dialogs import ViewDialog
        taken = [v.name for v in self._views if v is not view]
        dialog = ViewDialog(self, self.main.project, view=view, taken=taken, units=units)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_view is None:
            return None
        return dialog.result_view

    def new_view(self):
        """« Nouvelle vue… » : vue nommée du document affiché, avec au choix
        une feuille XSLT 1.0 et une CSS de départ ; pour un document
        auxiliaire, les entrées de sa première liste sont proposées comme
        éléments modifiables. La nouvelle vue est choisie."""
        from view_files import suggested_units
        if not self._views_may_change():
            return False
        session = self.main.document
        units = () if session is None or session.in_edition else suggested_units(self.main.editor.toPlainText())
        view = self._view_dialog(units=units)
        if view is None:
            return False
        return self._store_views(tuple(self._views) + (view,), view)

    def edit_view(self):
        """« Modifier la vue… » : nom, feuille, CSS et éléments modifiables de
        la vue choisie ; ses anciens fichiers restent."""
        current = self._current_view
        if current is None or not self._views_may_change():
            return False
        view = self._view_dialog(current)
        if view is None:
            return False
        return self._store_views(tuple(view if v == current else v for v in self._views), view)

    def remove_view(self):
        """« Retirer la vue » : après confirmation, la vue choisie quitte
        project.xml ; ses fichiers restent. La vue du projet est alors
        choisie."""
        current = self._current_view
        if current is None:
            return False
        answer = QMessageBox.question(
            self, _t("views.remove.title"), _t("views.remove.question", name=current.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No, QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes or not self._views_may_change():
            return False
        return self._store_views(tuple(v for v in self._views if v != current), None)

    def open_view_stylesheet(self):
        """« Ouvrir la feuille XSLT » : la feuille de la vue choisie, si elle
        est dans le projet, s'affiche dans son onglet (ajoutée aux documents
        du projet au besoin) ; F8 la vérifie."""
        path = self._project_stylesheet()
        return path is not None and self.main.open_project_file(path)

    def _update_view_tip(self):
        view = self._current_view
        lines = []
        if view is None:
            lines.append(_t("project.xslt.mode.builtin" if self.main.project.xslt_mode == "builtin"
                            else "project.xslt.mode.file"))
        mode = self._css_mode()
        css = (_t("preview.view.css.none") if mode == "never"
               else _t("preview.view.css.auto", css=self.css_path) if mode == "auto" else self.css_path)
        lines.append(_t("preview.view.files.tip", xslt=self.xsl_path, css=css))
        if view is not None and view.units:
            lines.append(_t("preview.view.units.tip", units=", ".join(view.units)))
        self.view_combo.setToolTip("\n".join(lines))

    def select_view(self, name):
        """Choisit la vue ``name`` du document affiché (None : la vue du
        projet), comme dans la liste. False si elle n'existe pas ou si le
        changement est annulé (fragment modifié)."""
        index = 0 if name is None else self.view_combo.findData(name)
        if index < 0:
            return False
        if index != self.view_combo.currentIndex():
            self.view_combo.setCurrentIndex(index)
        current = self._current_view
        return (current.name if current is not None else None) == name

    def _view_chosen(self, index):
        """Choix dans la liste des vues : un fragment ouvert est d'abord
        appliqué ou abandonné (sinon le choix est annulé), puis l'aperçu est
        refait avec la feuille, la CSS et les éléments modifiables de la
        vue."""
        name = self.view_combo.itemData(index)
        view = next((v for v in self._views if v.name == name), None)
        if view == self._current_view:
            return
        if not self.frag_box.isHidden() and not self.close_fragment_editor():
            previous = self.view_combo.findData(self._current_view.name) if self._current_view is not None else 0
            self.view_combo.blockSignals(True)
            self.view_combo.setCurrentIndex(max(0, previous))
            self.view_combo.blockSignals(False)
            return
        self._current_view = view
        self._remember_view()
        self._update_view_tip()
        self._update_view_actions()
        self._reset_preview(clear=False)
        if self.isVisible():
            self.refresh_preview(force=True)

    def _reset_preview(self, clear):
        """L'aperçu est à refaire (autre vue, autre document) : ses éléments
        modifiables seront relevés à nouveau. Avec ``clear``, il est vidé : il
        montrait un autre document."""
        self.preview_timer.stop()
        self._preview_generation += 1           # un aperçu en cours est dépassé
        self._pending_job = None
        self._ready_callbacks = []              # ils visaient l'aperçu d'avant
        self.unit_names = None
        self.sources = None
        self.dirty_preview = True
        self._last_preview_key = None
        if clear:
            self.preview.clear()
            self.preview.rebuild_line_markers()

    def view_unit_names(self):
        """Éléments modifiables de la vue choisie : ceux qu'elle nomme
        (``units``, comptés partout dans le document), sinon la règle de
        l'édition (schéma du document, sinon TEI P5)."""
        view = self._current_view
        if view is not None and view.units:
            return chosen_units(view.units)
        return self.main.fragment_unit_names()
