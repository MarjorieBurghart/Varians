# -*- coding: utf-8 -*-
"""Barre d'outils, menus, projets récents et changement de langue de la fenêtre principale."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QActionGroup, QKeySequence
from PySide6.QtWidgets import (
    QApplication, QLabel, QLineEdit, QMenu, QPlainTextEdit, QSizePolicy, QTextEdit, QToolBar, QToolButton,
    QWidget,
)
from app_context import (
    _settings, apply_qt_language, clear_recent_projects, current_i18n, recent_project_paths,
    remember_recent_project, tr as _t,
)
from help_dialogs import (
    _open_external, _open_latin_dictionary, _show_about, _show_software_help,
)
from project_config import load_project, update_project_language
from text_search import SearchOptions


def _setting_flag(name):
    value = _settings().value(name, False)
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


class MainMenusMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _build_toolbar(self):
        # V0.8.3 : menus à gauche, commandes XML regroupées, recherche à droite.
        # V0.9.2.8 : « Éditer » et « Rechercher » juste après « Fichier ».
        self._build_file_menu()
        self._build_edit_menu()
        self._build_search_menu()
        self._build_display_menu()
        self._build_help_menu()

        tb = QToolBar(_t("toolbar.title"), self)
        self.main_toolbar = tb
        tb.setMovable(False)
        self.addToolBar(tb)

        self.file_menu_button = QToolButton(self)
        self.file_menu_button.setText(_t("menu.file"))
        self.file_menu_button.setMenu(self.file_menu)
        self.file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.file_menu_button.setAutoRaise(True)
        tb.addWidget(self.file_menu_button)

        self.edit_menu_button = QToolButton(self)
        self.edit_menu_button.setText(_t("menu.edit"))
        self.edit_menu_button.setMenu(self.edit_menu)
        self.edit_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.edit_menu_button.setAutoRaise(True)
        tb.addWidget(self.edit_menu_button)

        self.search_menu_button = QToolButton(self)
        self.search_menu_button.setText(_t("menu.search"))
        self.search_menu_button.setMenu(self.search_menu)
        self.search_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.search_menu_button.setAutoRaise(True)
        tb.addWidget(self.search_menu_button)

        self.display_menu_button = QToolButton(self)
        self.display_menu_button.setText(_t("menu.display"))
        self.display_menu_button.setMenu(self.display_menu)
        self.display_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.display_menu_button.setAutoRaise(True)
        tb.addWidget(self.display_menu_button)

        self.help_menu_button = QToolButton(self)
        self.help_menu_button.setText(_t("menu.help"))
        self.help_menu_button.setMenu(self.help_menu)
        self.help_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        self.help_menu_button.setAutoRaise(True)
        tb.addWidget(self.help_menu_button)
        menu_gap = QWidget()
        menu_gap.setFixedWidth(14)
        tb.addWidget(menu_gap)

        self.action_generate_web = self._make_action(
            _t("toolbar.generate_web"), "", self.generate_web_viewer, _t("toolbar.generate_web.tip")
        )
        tb.addAction(self.action_generate_web)
        tb.addWidget(self._build_transform_button())
        tool_gap = QWidget()
        tool_gap.setFixedWidth(12)
        tb.addWidget(tool_gap)

        # Bloc XML : conserver ces commandes côte à côte.
        self.action_validate_rng = self._make_action(
            _t("toolbar.validate_rng"), "F8", self.validate_relaxng_manual, _t("toolbar.validate_rng.tip")
        )
        # Indenter et XPath viennent des menus Éditer et Rechercher (V0.9.2.8) ;
        # la barre d'outils les montre sous leur libellé court (iconText).
        tb.addAction(self.action_validate_rng)
        tb.addAction(self.action_format_xml)
        self.action_check_references = self._make_action(
            _t("references.action"), "", self.check_references, _t("references.action.tip")
        )
        tb.addAction(self.action_xpath_search)
        tb.addAction(self.action_check_references)
        xml_gap = QWidget()
        xml_gap.setFixedWidth(12)
        tb.addWidget(xml_gap)

        # Ctrl+1 / Ctrl+2 restent disponibles comme raccourcis, mais les boutons
        # redondants ont été supprimés : les onglets sont l'interface principale.
        self.action_xml_source = self._make_action(_t("toolbar.xml_source"), "Ctrl+1", lambda: self.left_tabs.setCurrentIndex(0))
        self.action_preview = self._make_action(_t("toolbar.preview"), "Ctrl+2", lambda: self.left_tabs.setCurrentIndex(1))
        self.addAction(self.action_xml_source)
        self.addAction(self.action_preview)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)

        # Recherche source alignée à droite.
        self.search_source_label = QLabel(" " + _t("toolbar.search_source") + " ")
        tb.addWidget(self.search_source_label)
        self.find_box = QLineEdit()
        self.find_box.setClearButtonEnabled(True)
        self.find_box.setMaximumWidth(260)
        self.find_box.setPlaceholderText("Ctrl+F")
        self.find_box.returnPressed.connect(self.find_source_next)
        tb.addWidget(self.find_box)
        # « Aa » et « .* » (V0.9.2.8) : les options du menu Rechercher, aussi
        # dans la barre de recherche du fragment.
        tb.addAction(self.action_search_case)
        tb.addAction(self.action_search_regex)
        self.formatted_view.add_fragment_find_options((self.action_search_case, self.action_search_regex))
        tb.addAction(self.action_search)
        tb.addAction(self.action_find_prev)
        tb.addAction(self.action_find_next)

    def _build_file_menu(self):
        # QMenu autonome : contrairement à menuBar().addMenu(), aucun bandeau
        # supplémentaire n'est créé au-dessus de la barre d'outils.
        menu = QMenu(_t("menu.file"), self)
        self.file_menu = menu

        self.action_new_project = self._make_action(_t("menu.new_project"), "Ctrl+N", self.new_project_dialog)
        self.action_open_project = self._make_action(_t("menu.open_project"), "Ctrl+O", self.open_project_dialog)
        self.recent_menu = menu.addMenu(_t("menu.recent_projects"))
        self.action_project_settings = self._make_action(_t("menu.project_settings"), "", self.project_settings_dialog)
        self.action_close_project = self._make_action(_t("menu.close_project"), "Ctrl+W", self.close_project)
        self.action_save = self._make_action(_t("menu.save_edition"), "Ctrl+S", self.save_contextual)
        self.action_save_as = self._make_action(_t("menu.save_edition_as"), "Ctrl+Shift+S", self.save_as)
        self.action_ctrl_e_config = self._make_action(
            _t("menu.ctrl_e_config"), "", self.open_ctrl_e_config, _t("toolbar.ctrl_e_config.tip", path=self.project.custom_elements)
        )
        self.action_generate_web_menu = self._make_action(
            _t("menu.generate_web"), "", self.generate_web_viewer, _t("toolbar.generate_web.tip")
        )
        self.action_transform_scenarios = self._make_action(
            _t("menu.transform_scenarios"), "", self.transform_scenarios_dialog)
        self.action_tei_stylesheets = self._make_action(_t("tei_stylesheets.menu"), "", self.tei_stylesheets_dialog)
        self.action_quit = self._make_action(_t("menu.quit"), "Ctrl+Q", self.close)

        menu.insertAction(self.recent_menu.menuAction(), self.action_new_project)
        menu.insertAction(self.recent_menu.menuAction(), self.action_open_project)
        menu.addAction(self.action_project_settings)
        # « Documents XML / XSLT du projet… », sous « Paramètres du projet… » (V0.9.2.1).
        self.documents_menu = menu.addMenu(_t("documents.menu"))
        self.action_add_document = self._make_action(_t("documents.add.menu"), "", self.add_document_dialog)
        self.action_new_document = self._make_action(_t("documents.new.menu"), "", self.new_document_dialog)
        self.action_new_stylesheet = self._make_action(
            _t("documents.new_stylesheet.menu"), "", self.new_stylesheet_dialog)
        self.action_new_schematron = self._make_action(
            _t("documents.new_schematron.menu"), "", self.new_schematron_dialog)
        self.action_remove_document = self._make_action(
            _t("documents.remove.menu"), "", self.remove_document_from_project)
        self.action_remove_document.setEnabled(False)       # l'édition est affichée
        for action in (self.action_add_document, self.action_new_document, self.action_new_stylesheet,
                       self.action_new_schematron, self.action_remove_document):
            self.documents_menu.addAction(action)
        self.action_iiif_manager = self._make_action(_t('iiif.manager.menu'), '', self.open_iiif_download_manager)
        menu.addAction(self.action_iiif_manager)
        menu.addAction(self.action_close_project)
        menu.addSeparator()
        menu.addAction(self.action_save)
        menu.addAction(self.action_save_as)
        menu.addSeparator()
        menu.addAction(self.action_ctrl_e_config)
        menu.addSeparator()
        menu.addAction(self.action_generate_web_menu)
        menu.addAction(self.action_transform_scenarios)
        menu.addAction(self.action_tei_stylesheets)
        menu.addSeparator()
        menu.addAction(self.action_quit)
        # Dans un QMenu attaché à un QToolButton, les raccourcis doivent aussi
        # être enregistrés auprès de la fenêtre pour rester actifs menu fermé.
        for action in (
            self.action_new_project, self.action_open_project, self.action_close_project,
            self.action_save, self.action_save_as, self.action_quit,
        ):
            self.addAction(action)
        self.update_recent_projects_menu()

    def _build_edit_menu(self):
        """Menu « Éditer » (V0.9.2.8). Les commandes agissent sur le champ qui
        a le focus (XML, fragment, champ de texte), sinon sur le XML. Leurs
        raccourcis restent ceux de chaque champ : le menu les affiche sans les
        reprendre (contexte WidgetShortcut : inactifs menu fermé)."""
        menu = QMenu(_t("menu.edit"), self)
        self.edit_menu = menu
        self.action_undo = self._edit_action("edit.undo", "Ctrl+Z", "undo")
        self.action_redo = self._edit_action("edit.redo", "Ctrl+Y", "redo")
        self.action_cut = self._edit_action("edit.cut", "Ctrl+X", "cut")
        self.action_copy = self._edit_action("edit.copy", "Ctrl+C", "copy")
        self.action_paste = self._edit_action("edit.paste", "Ctrl+V", "paste")
        self.action_select_all = self._edit_action("edit.select_all", "Ctrl+A", "selectAll")
        self.action_format_xml = self._make_action(
            _t("edit.format_xml"), "", self.format_xml_source, _t("toolbar.format_xml.tip")
        )
        self.action_format_xml.setIconText(_t("toolbar.format_xml"))
        menu.addAction(self.action_undo)
        menu.addAction(self.action_redo)
        menu.addSeparator()
        menu.addAction(self.action_cut)
        menu.addAction(self.action_copy)
        menu.addAction(self.action_paste)
        menu.addSeparator()
        menu.addAction(self.action_select_all)
        menu.addSeparator()
        menu.addAction(self.action_format_xml)
        menu.aboutToShow.connect(self._update_edit_actions)

    def _edit_action(self, key, shortcut, method):
        action = self._make_action(_t(key), shortcut, lambda checked=False: getattr(self._edit_target(), method)())
        action.setShortcutContext(Qt.ShortcutContext.WidgetShortcut)
        return action

    def _edit_target(self):
        widget = QApplication.focusWidget()
        if isinstance(widget, (QLineEdit, QPlainTextEdit, QTextEdit)):
            return widget
        return self.editor

    def _update_edit_actions(self):
        target = self._edit_target()
        if isinstance(target, QLineEdit):
            undo, redo, selection = target.isUndoAvailable(), target.isRedoAvailable(), target.hasSelectedText()
        else:
            document = target.document()
            undo, redo = document.isUndoAvailable(), document.isRedoAvailable()
            selection = target.textCursor().hasSelection()
        writable = not target.isReadOnly()
        self.action_undo.setEnabled(writable and undo)
        self.action_redo.setEnabled(writable and redo)
        self.action_cut.setEnabled(writable and selection)
        self.action_copy.setEnabled(selection)
        self.action_paste.setEnabled(writable and bool(QApplication.clipboard().text()))

    def _build_search_menu(self):
        """Menu « Rechercher » (V0.9.2.8) : recherche simple, occurrences
        précédente et suivante, recherche XPath. La barre d'outils garde ses
        boutons, sous leur libellé court (iconText)."""
        menu = QMenu(_t("menu.search"), self)
        self.search_menu = menu
        self.action_search = self._make_action(_t("search.find"), "Ctrl+F", self.focus_find)
        self.action_search.setIconText(_t("toolbar.search"))
        self.action_find_prev = self._make_action(_t("search.previous"), "Shift+F3", self.find_previous)
        self.action_find_prev.setIconText(_t("toolbar.previous"))
        self.action_find_next = self._make_action(_t("search.next"), "F3", self.find_next)
        self.action_find_next.setIconText(_t("toolbar.next"))
        self.action_xpath_search = self._make_action(
            _t("search.xpath"), "Ctrl+Shift+F", self.focus_xpath_search
        )
        self.action_xpath_search.setIconText(_t("xpath.action"))
        # Options communes au XML et au fragment, retenues d'une session à l'autre.
        self.action_search_case = self._search_option_action("search.case", "Aa", "search/caseSensitive")
        self.action_search_regex = self._search_option_action("search.regex", ".*", "search/regex")
        menu.addAction(self.action_search)
        menu.addAction(self.action_find_prev)
        menu.addAction(self.action_find_next)
        menu.addSeparator()
        menu.addAction(self.action_search_case)
        menu.addAction(self.action_search_regex)
        menu.addSeparator()
        menu.addAction(self.action_xpath_search)

    def _search_option_action(self, key, short, setting):
        action = QAction(_t(key), self)
        action.setIconText(short)
        action.setToolTip(_t(key))
        action.setCheckable(True)
        action.setChecked(_setting_flag(setting))
        action.toggled.connect(lambda checked: _settings().setValue(setting, bool(checked)))
        return action

    def search_options(self):
        """Options de la recherche du XML et du fragment (V0.9.2.8)."""
        return SearchOptions(case_sensitive=self.action_search_case.isChecked(),
                             regex=self.action_search_regex.isChecked())

    def _build_display_menu(self):
        I18N = current_i18n()
        menu = QMenu(_t("menu.display"), self)
        self.display_menu = menu

        self.action_reload_images = self._make_action(_t("toolbar.reload_images"), "F5", self.reload_images)
        self.action_reload_images.setEnabled(bool(getattr(self, "has_any_images", True)))
        self.action_choose_witnesses = self._make_action(
            _t("view.witnesses.choose"), "", self.choose_visible_witnesses, _t("view.witnesses.choose.tip")
        )
        self.action_choose_witnesses.setEnabled(bool(getattr(self, "has_any_images", True)))
        self.action_choose_documents = self._make_action(
            _t("documents.view.choose"), "", self.choose_displayed_documents, _t("documents.view.choose.tip")
        )
        self.action_choose_documents.setEnabled(len(self.documents) > 1)
        menu.addAction(self.action_reload_images)
        menu.addAction(self.action_choose_witnesses)
        menu.addAction(self.action_choose_documents)
        self.workspace_layout_menu = menu.addMenu(_t('workspace.menu'))
        self.workspace_mode_group = QActionGroup(self)
        self.workspace_mode_group.setExclusive(True)
        self.workspace_mode_actions = {}
        for mode, key in (('vertical', 'workspace.vertical'),
                          ('horizontal', 'workspace.horizontal'),
                          ('grid', 'workspace.grid')):
            action = QAction(_t(key), self)
            action.setCheckable(True)
            action.setChecked(mode == self._workspace_mode)
            action.triggered.connect(lambda checked=False, m=mode:
                                     self._set_workspace_mode(m) if checked else None)
            self.workspace_mode_group.addAction(action)
            self.workspace_layout_menu.addAction(action)
            self.workspace_mode_actions[mode] = action
        self.workspace_layout_menu.addSeparator()
        self.detach_witness_menu = self.workspace_layout_menu.addMenu(_t('workspace.detach.menu'))
        self._detach_actions = {}
        for w in self.witness_configs:
            action = QAction(f'{w.id} — {w.label}' if w.label else str(w.id), self)
            action.setCheckable(True)
            action.triggered.connect(lambda checked=False, wid=w.id:
                                     self._toggle_detached_witness(wid))
            self.detach_witness_menu.addAction(action)
            self._detach_actions[w.id] = action
        self.action_attach_all = QAction(_t('workspace.attach_all'), self)
        self.action_attach_all.triggered.connect(self._dock_all_witnesses)
        self.workspace_layout_menu.addAction(self.action_attach_all)
        self._refresh_detach_actions()
        menu.addSeparator()
        self.xml_folding_menu = menu.addMenu(_t('fold.menu'))
        self.action_fold_current = self._make_action(
            _t('fold.current'), 'Ctrl+Alt+F', lambda checked=False: self.editor.toggle_xml_fold())
        self.action_fold_all = self._make_action(
            _t('fold.all'), '', lambda checked=False: self.editor.fold_all_xml())
        self.action_unfold_all = self._make_action(
            _t('fold.none'), 'Ctrl+Alt+Shift+F', lambda checked=False: self.editor.unfold_all_xml())
        for action in (self.action_fold_current, self.action_fold_all, self.action_unfold_all):
            self.xml_folding_menu.addAction(action)
            self.addAction(action)
        menu.addSeparator()
        self.action_diagnose_witnesses = self._make_action(
            _t('diagnostics.menu'), '', self.show_witness_diagnostics)
        self.action_refresh_synchronizations = self._make_action(
            _t('diagnostics.refresh'), 'Ctrl+Shift+R', self.refresh_witness_synchronizations)
        self.action_refresh_synchronizations.setToolTip(_t('diagnostics.refresh.tip'))
        menu.addAction(self.action_diagnose_witnesses)
        menu.addAction(self.action_refresh_synchronizations)
        self.addAction(self.action_refresh_synchronizations)
        menu.addSeparator()

        self.language_menu = menu.addMenu(_t("common.language"))
        self.language_action_group = QActionGroup(self)
        self.language_action_group.setExclusive(True)
        self.language_actions = {}
        for info in I18N.available_languages():
            action = QAction(info.label, self)
            action.setCheckable(True)
            action.setChecked(info.code == I18N.language)
            action.triggered.connect(lambda checked=False, code=info.code: self._set_language_code(code) if checked else None)
            self.language_action_group.addAction(action)
            self.language_menu.addAction(action)
            self.language_actions[info.code] = action

    def _build_help_menu(self):
        menu = QMenu(_t("menu.help"), self)
        self.help_menu = menu
        self.action_enigma = self._make_action(
            _t("help.enigma"), "", lambda: _open_external("https://enigma.huma-num.fr")
        )
        self.action_latin_dictionary = self._make_action(
            _t("help.latin_dictionary"), "", lambda: _open_latin_dictionary(self)
        )
        self.action_latin_dictionary.setShortcuts([QKeySequence("Ctrl+?")])
        self.action_software_help = self._make_action(
            _t("help.software"), "F1", lambda: _show_software_help(self)
        )
        self.action_debug_apparatus = self._make_action(
            _t("apparatus.menu"), "", self.debug_apparatus, _t("apparatus.menu.tip")
        )
        self.action_about = self._make_action(
            _t("help.about"), "", lambda: _show_about(self)
        )
        # « Débugger l'apparat » en tête, puis les ressources en ligne ;
        # l'aide du logiciel reste en bas, juste au-dessus de « À propos ».
        menu.addAction(self.action_debug_apparatus)
        menu.addSeparator()
        menu.addAction(self.action_enigma)
        menu.addAction(self.action_latin_dictionary)
        menu.addSeparator()
        menu.addAction(self.action_software_help)
        menu.addAction(self.action_about)
        self.addAction(self.action_latin_dictionary)
        self.addAction(self.action_software_help)

    def update_recent_projects_menu(self):
        self.recent_menu.clear()
        paths = recent_project_paths()
        if not paths:
            empty = QAction(_t("menu.recent_empty"), self)
            empty.setEnabled(False)
            self.recent_menu.addAction(empty)
        else:
            for raw in paths:
                path = Path(raw)
                try:
                    title = load_project(path).title if path.is_file() else path.parent.name
                except Exception:
                    title = path.parent.name or path.stem
                label = _t("menu.recent_item", title=title, path=path)
                action = QAction(label, self)
                action.setToolTip(str(path))
                action.triggered.connect(lambda checked=False, p=path: self.open_recent_project(p))
                self.recent_menu.addAction(action)
        self.recent_menu.addSeparator()
        clear_action = QAction(_t("menu.recent_clear"), self)
        clear_action.triggered.connect(self.clear_recent_projects_action)
        self.recent_menu.addAction(clear_action)

    def clear_recent_projects_action(self):
        clear_recent_projects()
        remember_recent_project(self.project.path)
        self.update_recent_projects_menu()

    def _set_language_code(self, code):
        I18N = current_i18n()
        code = str(code or "")
        if not code or code == I18N.language:
            return
        if not I18N.set_language(code):
            return
        apply_qt_language(code)
        _settings().setValue("startupLanguage", code)
        try:
            update_project_language(self.project.path, code)
        except Exception as exc:
            # Language still changes for the current session even if project.xml
            # is read-only. The status bar is deliberately non-blocking here.
            self.statusBar().showMessage(str(exc), 5000)
        self.retranslate_ui()

    def _language_changed(self, index):
        """Compatibilité avec d'anciens appels internes de la combo supprimée en V0.8.3."""
        if hasattr(self, "language_combo"):
            self._set_language_code(self.language_combo.itemData(index))

    def retranslate_ui(self):
        I18N = current_i18n()
        app = QApplication.instance()
        if app is not None:
            app.setApplicationName(_t("app.name"))
        self.main_toolbar.setWindowTitle(_t("toolbar.title"))
        self.file_menu.setTitle(_t("menu.file"))
        self.file_menu_button.setText(_t("menu.file"))
        self.edit_menu.setTitle(_t("menu.edit"))
        self.edit_menu_button.setText(_t("menu.edit"))
        self.search_menu.setTitle(_t("menu.search"))
        self.search_menu_button.setText(_t("menu.search"))
        for action, key in ((self.action_undo, "edit.undo"), (self.action_redo, "edit.redo"),
                            (self.action_cut, "edit.cut"), (self.action_copy, "edit.copy"),
                            (self.action_paste, "edit.paste"), (self.action_select_all, "edit.select_all")):
            action.setText(_t(key))
        self.display_menu.setTitle(_t("menu.display"))
        self.display_menu_button.setText(_t("menu.display"))
        self.help_menu.setTitle(_t("menu.help"))
        self.help_menu_button.setText(_t("menu.help"))
        self.action_enigma.setText(_t("help.enigma"))
        self.action_latin_dictionary.setText(_t("help.latin_dictionary"))
        self.action_software_help.setText(_t("help.software"))
        self.action_debug_apparatus.setText(_t("apparatus.menu"))
        self.action_debug_apparatus.setToolTip(_t("apparatus.menu.tip"))
        self.action_about.setText(_t("help.about"))
        self.action_new_project.setText(_t("menu.new_project"))
        self.action_open_project.setText(_t("menu.open_project"))
        self.recent_menu.setTitle(_t("menu.recent_projects"))
        self.action_project_settings.setText(_t("menu.project_settings"))
        self.action_iiif_manager.setText(_t('iiif.manager.menu'))
        self.action_close_project.setText(_t("menu.close_project"))
        self.action_save.setText(_t("menu.save_edition" if self._edition_displayed() else "menu.save_document"))
        self.action_save_as.setText(_t("menu.save_edition_as"))
        self.documents_menu.setTitle(_t("documents.menu"))
        self.action_add_document.setText(_t("documents.add.menu"))
        self.action_new_document.setText(_t("documents.new.menu"))
        self.action_new_stylesheet.setText(_t("documents.new_stylesheet.menu"))
        self.action_new_schematron.setText(_t("documents.new_schematron.menu"))
        self.action_remove_document.setText(_t("documents.remove.menu"))
        self.action_ctrl_e_config.setText(_t("menu.ctrl_e_config"))
        self.action_ctrl_e_config.setToolTip(_t("toolbar.ctrl_e_config.tip", path=self.project.custom_elements))
        self.action_generate_web_menu.setText(_t("menu.generate_web"))
        self.action_transform_scenarios.setText(_t("menu.transform_scenarios"))
        self.action_tei_stylesheets.setText(_t("tei_stylesheets.menu"))
        self.action_quit.setText(_t("menu.quit"))
        self.action_generate_web.setText(_t("toolbar.generate_web"))
        self.action_generate_web.setToolTip(_t("toolbar.generate_web.tip"))
        self.action_transform.setText(_t("toolbar.transform"))
        self.action_transform.setToolTip(_t("toolbar.transform.tip"))
        self.action_xml_source.setText(_t("toolbar.xml_source"))
        self.action_preview.setText(_t("toolbar.preview"))
        self.action_reload_images.setText(_t("toolbar.reload_images"))
        self.action_choose_witnesses.setText(_t("view.witnesses.choose"))
        self.action_choose_witnesses.setToolTip(_t("view.witnesses.choose.tip"))
        self.action_choose_documents.setText(_t("documents.view.choose"))
        self.action_choose_documents.setToolTip(_t("documents.view.choose.tip"))
        self.workspace_layout_menu.setTitle(_t('workspace.menu'))
        self.detach_witness_menu.setTitle(_t('workspace.detach.menu'))
        for mode, key in (('vertical', 'workspace.vertical'), ('horizontal', 'workspace.horizontal'), ('grid', 'workspace.grid')):
            self.workspace_mode_actions[mode].setText(_t(key))
        self.action_attach_all.setText(_t('workspace.attach_all'))
        self.xml_folding_menu.setTitle(_t('fold.menu'))
        self.action_fold_current.setText(_t('fold.current'))
        self.action_fold_all.setText(_t('fold.all'))
        self.action_unfold_all.setText(_t('fold.none'))
        for win in self._detached_windows.values():
            win.retranslate_ui()
        self.action_diagnose_witnesses.setText(_t('diagnostics.menu'))
        self.action_refresh_synchronizations.setText(_t('diagnostics.refresh'))
        self.action_refresh_synchronizations.setToolTip(_t('diagnostics.refresh.tip'))
        self.language_menu.setTitle(_t("common.language"))
        language_labels = {info.code: info.label for info in I18N.available_languages()}
        for code, action in self.language_actions.items():
            action.setText(language_labels.get(code, code))
            action.setChecked(code == I18N.language)
        self.rng_busy.setToolTip(_t("rng.status.running.tip"))
        self._update_check_labels()
        self.action_format_xml.setText(_t("edit.format_xml"))
        self.action_format_xml.setIconText(_t("toolbar.format_xml"))
        self.action_format_xml.setToolTip(_t("toolbar.format_xml.tip"))
        self.search_source_label.setText(" " + _t("toolbar.search_source") + " ")
        for action, key, short in ((self.action_search, "search.find", "toolbar.search"),
                                   (self.action_find_prev, "search.previous", "toolbar.previous"),
                                   (self.action_find_next, "search.next", "toolbar.next"),
                                   (self.action_xpath_search, "search.xpath", "xpath.action")):
            action.setText(_t(key))
            action.setIconText(_t(short))
        for action, key in ((self.action_search_case, "search.case"), (self.action_search_regex, "search.regex")):
            action.setText(_t(key))
            action.setToolTip(_t(key))
        self._retranslate_references()
        self.source_visual_wrap.setText(_t("source.visual_wrap"))
        self.xpath_title.setText(_t("xpath.panel.title"))
        self.xpath_query.setPlaceholderText(_t("xpath.placeholder"))
        self.xpath_run_button.setText(_t("xpath.run"))
        self.xpath_close.setToolTip(_t("xpath.close"))
        self.xpath_table.setHorizontalHeaderLabels([
            _t("xpath.column.line"), _t("xpath.column.element"),
            _t("xpath.column.path"), _t("xpath.column.preview"),
        ])
        self.left_tabs.setTabText(0, _t("tab.xml_source"))
        for session in self.documents:
            self._refresh_document_tab(session)
        self.left_tabs.setTabText(1, _t("tab.preview"))
        self.validation_refresh.setToolTip(_t("rng.panel.refresh"))
        self.validation_close.setToolTip(_t("rng.panel.close"))
        self.validation_rules.setText(_t("schematron.panel.rules_button"))
        self.validation_rules.setToolTip(_t("schematron.panel.rules_button.tip"))
        self.validation_table.setHorizontalHeaderLabels([
            _t("rng.column.level"), _t("rng.column.origin"), _t("rng.column.line"),
            _t("rng.column.column"), _t("rng.column.message"), _t("rng.column.document"),
        ])
        self.source_wrap_element_action.setText(_t("fragment.wrap"))
        self.source_completion_action.setText(_t("completion.action"))
        self.formatted_view.retranslate_ui()
        for panel in self.panels.values():
            panel.retranslate_ui()
        self.update_recent_projects_menu()
        self._set_title()
        self._rebuild_lb_cache()
        self._cursor_changed()
        self.validate_text(False)
        self.validate_relaxng_document(show_panel=self.validation_panel.isVisible(), show_success_message=False)
        self._set_document_health(self._document_health)
