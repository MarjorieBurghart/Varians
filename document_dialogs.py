# -*- coding: utf-8 -*-
"""Menu Fichier ▸ Documents XML du projet : ajouter un document existant,
créer un nouveau document, une nouvelle feuille XSLT ou (V0.9.2.4) un
nouveau fichier Schematron, retirer un document du projet.

Un nouveau document naît d'un modèle (boîte « Nouveau document XML »,
``NewDocumentDialog``) : ceux de la TEI, comme dans Oxygen, « Même schéma
que l'édition », ceux du dossier ``modeles/`` du projet, ou un document vide
d'élément racine choisi (``document_templates``).

Un fichier situé hors du projet est copié dans son dossier ``xml/`` (un
fichier Schematron ``.sch`` aussi), ou ``xslt/`` pour une feuille XSLT
(``.xsl``, ``.xslt``), jamais par-dessus un fichier existant ; retirer un
document du projet ne supprime jamais son fichier.
"""
from __future__ import annotations

import shutil
from pathlib import Path
from xml.sax.saxutils import escape

from PySide6.QtCore import Qt
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QDialogButtonBox, QFileDialog, QGridLayout, QInputDialog, QLabel, QLineEdit,
    QMessageBox, QPlainTextEdit, QPushButton, QSplitter, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget,
)
from app_context import tr as _t
from code_editor import XMLHighlighter
# Document vide d'élément racine choisi (nom historique).
from document_templates import empty_document_text as new_document_text
from document_templates import (
    PROJECT_TEMPLATES_FOLDER, document_config, document_text, edition_template, empty_template,
    project_templates, rebased_models, tei_templates, tei_templates_version,
)
from project_config import DocumentConfig
from xml_roots import SCHEMATRON_NS

STYLESHEET_SUFFIXES = (".xsl", ".xslt")
SCHEMATRON_SUFFIXES = (".sch",)
# Versions d'une nouvelle feuille, et le moteur qui les exécute.
STYLESHEET_VERSIONS = (("1.0", "lxml"), ("3.0", "saxon"))

_STYLESHEET_HEADS = {
    "1.0": ('<xsl:stylesheet version="1.0"\n'
            '  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"\n'
            '  xmlns:tei="http://www.tei-c.org/ns/1.0"\n'
            '  exclude-result-prefixes="tei">\n\n'
            '  <xsl:output method="html" encoding="UTF-8" indent="yes"/>\n'),
    "3.0": ('<xsl:stylesheet version="3.0"\n'
            '  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"\n'
            '  xmlns:xs="http://www.w3.org/2001/XMLSchema"\n'
            '  xmlns:tei="http://www.tei-c.org/ns/1.0"\n'
            '  exclude-result-prefixes="#all">\n\n'
            '  <xsl:output method="html" html-version="5" encoding="UTF-8" indent="yes"/>\n'),
}
_STYLESHEET_BODY = ('\n'
                    '  <xsl:template match="/">\n'
                    '    <html>\n'
                    '      <head>\n'
                    '        <title><xsl:value-of select="//tei:titleStmt/tei:title[1]"/></title>\n'
                    '      </head>\n'
                    '      <body>\n'
                    '        <xsl:apply-templates select="//tei:text"/>\n'
                    '      </body>\n'
                    '    </html>\n'
                    '  </xsl:template>\n\n'
                    '</xsl:stylesheet>\n')


def is_stylesheet_file(path):
    """Vrai si ``path`` est une feuille XSLT d'après son extension (``.xsl``,
    ``.xslt``, casse ignorée) ; le fichier n'est pas lu."""
    return Path(path).suffix.lower() in STYLESHEET_SUFFIXES


def is_schematron_file(path):
    """Vrai si ``path`` est un fichier Schematron d'après son extension
    (``.sch``, casse ignorée) ; le fichier n'est pas lu."""
    return Path(path).suffix.lower() in SCHEMATRON_SUFFIXES


def document_target_path(source, project_root):
    """Emplacement du document dans le projet, et s'il faut l'y copier.

    Un fichier déjà situé dans le projet est utilisé tel quel ; sinon, il est
    destiné au dossier ``xml/`` du projet (``xslt/`` pour une feuille XSLT),
    sous son nom, suffixé ``_2``, ``_3``… si ce nom est déjà pris.
    """
    source = Path(source).expanduser().resolve()
    root = Path(project_root).expanduser().resolve()
    if source.is_relative_to(root):
        return source, False
    return free_path(root / ("xslt" if is_stylesheet_file(source) else "xml"), source.name), True


def free_path(folder, name):
    """``folder/name``, suffixé ``_2``, ``_3``… si ce nom est déjà pris."""
    candidate, name = Path(folder) / name, Path(name)
    number = 2
    while candidate.exists():
        candidate = Path(folder) / f"{name.stem}_{number}{name.suffix}"
        number += 1
    return candidate


def copy_document_into_project(source, project_root):
    """Chemin du document dans le projet, après copie si nécessaire."""
    target, copy = document_target_path(source, project_root)
    if copy:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source).expanduser().resolve(), target)
    return target


def new_stylesheet_text(version):
    """Feuille XSLT minimale (``version`` : 1.0 ou 3.0) : espace de noms TEI
    déclaré, ``xsl:output`` HTML et un ``xsl:template match="/"``."""
    if version not in _STYLESHEET_HEADS:
        raise ValueError(version)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + _STYLESHEET_HEADS[version] + _STYLESHEET_BODY


def new_schematron_text(message):
    """Fichier Schematron minimal : ``queryBinding="xslt2"``, préfixe
    ``tei`` déclaré, et un groupe de règles d'exemple, un avertissement de
    texte *message* (dans la langue de l'interface) pour un apparat sans
    lemme ni leçon."""
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<sch:schema xmlns:sch="{SCHEMATRON_NS}" queryBinding="xslt2">\n'
            '  <sch:ns prefix="tei" uri="http://www.tei-c.org/ns/1.0"/>\n\n'
            '  <sch:pattern id="apparat">\n'
            '    <sch:rule context="tei:app">\n'
            '      <sch:assert test="tei:lem or tei:rdg" role="warning">'
            f'{escape(message)}</sch:assert>\n'
            '    </sch:rule>\n'
            '  </sch:pattern>\n\n'
            '</sch:schema>\n')


# Caractères montrés au plus dans l'aperçu d'un modèle du projet.
_PREVIEW_CHARS = 20000
_TEMPLATE_ROLE = Qt.ItemDataRole.UserRole


class NewDocumentDialog(QDialog):
    """Boîte « Nouveau document XML » : le modèle, avec son schéma et un
    aperçu du document, le fichier à créer et, pour un document vide, son
    élément racine.

    Les modèles : « Même schéma que l'édition » (grisé si l'édition n'a pas
    de schéma), ceux du dossier ``modeles/`` du projet, ceux de la TEI (ceux
    d'Oxygen, groupe « TEI P5 »), le document vide. « OK » vérifie le choix
    et laisse la boîte ouverte sur une erreur ; acceptée, elle donne
    ``target`` (le fichier), ``text`` (son contenu) et ``config`` (sa
    déclaration dans project.xml). Elle n'écrit rien elle-même."""

    def __init__(self, parent, project_root, edition_text="", edition_path=None, schema_mode="auto",
                 project_schema=None):
        super().__init__(parent)
        self.setWindowTitle(_t("documents.new.title"))
        self.resize(900, 560)
        self._root = Path(project_root)
        self._edition_text = edition_text or ""
        self._edition_path = Path(edition_path) if edition_path else self._root / "xml" / "edition.xml"
        self.target = self.text = self.config = None
        self._items = []

        self.tree = QTreeWidget(self)
        self.tree.setHeaderHidden(True)
        edition = edition_template(self._edition_text, schema_mode, project_schema)
        item = self._entry(_t("documents.new.edition"), edition)
        item.setToolTip(0, _t("documents.new.edition.tip" if edition else "documents.new.edition.none"))
        self.tree.addTopLevelItem(item)

        group = self._group(_t("documents.new.group.project", folder=PROJECT_TEMPLATES_FOLDER))
        group.setToolTip(0, _t("documents.new.project.tip", folder=PROJECT_TEMPLATES_FOLDER))
        templates = project_templates(self._root)
        for template in templates:
            group.addChild(self._entry(template.name, template))
        if not templates:
            hint = self._entry(_t("documents.new.project.empty", folder=PROJECT_TEMPLATES_FOLDER), None)
            hint.setToolTip(0, hint.text(0))
            group.addChild(hint)

        self._tei_group = self._group(_t("documents.new.group.tei", version=tei_templates_version()))
        self._tei_group.setToolTip(0, _t("documents.new.tei.source"))
        self._fill_tei_group()
        self.tree.addTopLevelItem(self._entry(_t("documents.new.empty"), empty_template()))
        self.tree.expandAll()

        self.schema_label = QLabel(self)
        self.schema_label.setWordWrap(True)
        self.schema_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.preview = QPlainTextEdit(self)
        self.preview.setReadOnly(True)
        self.preview.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
        font = QFont("Consolas")
        font.setStyleHint(QFont.StyleHint.Monospace)
        self.preview.setFont(font)
        self._highlighter = XMLHighlighter(self.preview.document())
        right = QWidget(self)
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.addWidget(self.schema_label)
        right_layout.addWidget(QLabel(_t("documents.new.preview"), right))
        right_layout.addWidget(self.preview, 1)
        splitter = QSplitter(Qt.Orientation.Horizontal, self)
        splitter.addWidget(self.tree)
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)

        self.root_edit = QLineEdit("TEI", self)
        self.path_edit = QLineEdit(str(free_path(self._root / "xml", "nouveau.xml")), self)
        self.browse_button = QPushButton("…", self)
        self.browse_button.clicked.connect(self._browse)
        form = QGridLayout()
        form.addWidget(QLabel(_t("documents.new.root"), self), 0, 0)
        form.addWidget(self.root_edit, 0, 1, 1, 2)
        form.addWidget(QLabel(_t("documents.new.file"), self), 1, 0)
        form.addWidget(self.path_edit, 1, 1)
        form.addWidget(self.browse_button, 1, 2)
        form.setColumnStretch(1, 1)
        source = QLabel(_t("documents.new.tei.source"), self)
        source.setWordWrap(True)
        source.setStyleSheet("color: palette(placeholder-text);")
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        # Version des squelettes TEI et leurs mises à jour (tei_templates_ui).
        self.tei_templates_button = self.buttons.addButton(_t("tei_templates.button"),
                                                           QDialogButtonBox.ButtonRole.ResetRole)
        self.tei_templates_button.clicked.connect(self._show_tei_templates)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(_t("documents.new.template"), self))
        layout.addWidget(splitter, 1)
        layout.addLayout(form)
        layout.addWidget(source)
        layout.addWidget(self.buttons)

        self.tree.currentItemChanged.connect(lambda *_: self._template_changed())
        self.root_edit.textChanged.connect(lambda *_: self._template_changed())
        self.path_edit.textChanged.connect(lambda *_: self._template_changed())
        if not self.select_template("edition"):
            self.select_template("tei", "All")

    def _fill_tei_group(self):
        """Les squelettes TEI de la version qui sert, dans leur groupe ; le
        modèle choisi reste choisi s'il existe encore."""
        selected = self.selected_template()
        group = self._tei_group
        self._items = [(template, item) for template, item in self._items if item.parent() is not group]
        group.takeChildren()
        group.setText(0, _t("documents.new.group.tei", version=tei_templates_version()))
        for template in tei_templates():
            group.addChild(self._entry(template.name, template))
        group.setExpanded(True)
        if selected is not None and selected.kind == "tei" and not self.select_template("tei", selected.name):
            self.select_template("tei", "All")

    def _show_tei_templates(self):
        """« Modèles TEI… » : la fenêtre des squelettes TEI ; une version
        installée sert aussitôt."""
        from tei_templates_ui import TeiTemplatesDialog
        TeiTemplatesDialog(self).exec()
        self._fill_tei_group()

    def tei_group_title(self):
        """Titre du groupe des squelettes TEI (« TEI P5 (4.12.0) »)."""
        return self._tei_group.text(0)

    def tei_template_names(self):
        """Noms des squelettes TEI de la liste."""
        return [self._tei_group.child(index).text(0) for index in range(self._tei_group.childCount())]

    def _group(self, text):
        """Groupe de modèles : ni choisi ni grisé."""
        group = QTreeWidgetItem([text])
        group.setFlags(Qt.ItemFlag.ItemIsEnabled)
        font = group.font(0)
        font.setBold(True)
        group.setFont(0, font)
        self.tree.addTopLevelItem(group)
        return group

    def _entry(self, text, template):
        """Ligne d'un modèle ; sans modèle, ligne grisée."""
        item = QTreeWidgetItem([text])
        if template is None:
            item.setFlags(Qt.ItemFlag.NoItemFlags)
        else:
            item.setData(0, _TEMPLATE_ROLE, template)
            self._items.append((template, item))
        return item

    def selected_template(self):
        """Le modèle choisi, ou None."""
        item = self.tree.currentItem()
        return item.data(0, _TEMPLATE_ROLE) if item is not None else None

    def select_template(self, kind, name=""):
        """Choisit le modèle de sorte ``kind`` (et de nom ``name`` s'il est
        donné). Faux s'il n'existe pas."""
        for template, item in self._items:
            if template.kind == kind and (not name or template.name == name):
                self.tree.setCurrentItem(item)
                return True
        return False

    def target_path(self):
        """Le fichier à créer (``.xml`` ajouté sans extension ; relatif au
        dossier du projet), ou None si le champ est vide."""
        raw = self.path_edit.text().strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = self._root / path
        if not path.suffix:
            path = path.with_suffix(".xml")
        return path.resolve()

    def _browse(self):
        fn, _ = QFileDialog.getSaveFileName(
            self, _t("documents.new.title"), self.path_edit.text() or str(self._root / "xml" / "nouveau.xml"),
            "XML (*.xml)")
        if fn:
            self.path_edit.setText(fn)

    def _text(self, template, target):
        """Texte du document d'après ``template`` (ValueError, OSError,
        UnicodeError possibles)."""
        return document_text(template, target, edition_text=self._edition_text, edition_path=self._edition_path,
                             root_name=self.root_edit.text().strip())

    def _preview_text(self, template):
        target = self.target_path() or self._root / "xml" / "nouveau.xml"
        try:
            if template.kind == "project":
                # Le début seulement : un modèle peut être volumineux.
                with template.path.open(encoding="utf-8") as stream:
                    return rebased_models(stream.read(_PREVIEW_CHARS), template.path.parent, target.parent)
            return self._text(template, target)
        except (ValueError, OSError, UnicodeError):
            return ""

    def _template_changed(self):
        template = self.selected_template()
        empty = template is not None and template.kind == "empty"
        self.root_edit.setEnabled(empty)
        if template is None:
            self.schema_label.setText("")
            self.preview.setPlainText("")
        else:
            if template.kind == "edition" and template.schema_mode == "file":
                schema = _t("documents.new.schema.project", schema=template.schema)
            elif template.schema:
                schema = _t("documents.new.schema", schema=template.schema)
            else:
                schema = _t("documents.new.schema.none")
            self.schema_label.setText(schema)
            self.preview.setPlainText(self._preview_text(template))
        ok = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        ok.setEnabled(template is not None and bool(self.path_edit.text().strip()))

    def accept(self):
        """Vérifie le choix : un fichier qui existe déjà n'est jamais
        remplacé, l'élément racine d'un document vide doit être un nom
        valide, un modèle du projet doit pouvoir être lu."""
        template, target = self.selected_template(), self.target_path()
        if template is None or target is None:
            return
        if target.exists():
            QMessageBox.warning(self, _t("documents.new.title"), _t("documents.new.exists", path=target))
            return
        try:
            text = self._text(template, target)
        except ValueError:
            QMessageBox.warning(self, _t("documents.new.title"),
                                _t("documents.new.root_invalid", name=self.root_edit.text().strip()))
            return
        except (OSError, UnicodeError) as exc:
            QMessageBox.critical(self, _t("file.open.error.title"), str(exc))
            return
        self.target, self.text, self.config = target, text, document_config(template, target)
        super().accept()


class DocumentDialogsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def add_document_dialog(self):
        """Ajoute au projet un document XML, une feuille XSLT ou un fichier
        Schematron existants et l'affiche."""
        fn, _ = QFileDialog.getOpenFileName(
            self, _t("documents.add.title"), str(self.project.root_dir / "xml"),
            "XML, XSLT, Schematron (*.xml *.xsl *.xslt *.sch);;XML (*.xml);;XSLT (*.xsl *.xslt);;"
            f"Schematron (*.sch);;{_t('common.all_files')} (*)")
        if not fn:
            return False
        source = Path(fn).expanduser().resolve()
        for session in self.documents:
            if Path(session.path).resolve() == source:
                QMessageBox.information(self, _t("documents.add.title"),
                                        _t("documents.add.already", name=self._document_display_name(session)))
                return self.show_document(session)
        try:
            source.read_text(encoding="utf-8")
            target = copy_document_into_project(source, self.project.root_dir)
        except (OSError, UnicodeError) as exc:
            QMessageBox.critical(self, _t("file.open.error.title"), str(exc))
            return False
        if target != source:
            self.statusBar().showMessage(_t("documents.add.copied", path=target), 6000)
        return self._register_document(DocumentConfig(target))

    def new_document_dialog(self):
        """Crée un document XML d'après un modèle (``NewDocumentDialog``),
        l'ajoute au projet et l'affiche."""
        session = self.edition_session
        if session.text_document is not None:
            edition_text = session.text_document.toPlainText()
        else:
            try:
                edition_text = Path(self.project.edition).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                edition_text = ""
        dialog = NewDocumentDialog(self, self.project.root_dir, edition_text, self.project.edition,
                                   self.project.schema_mode, self.project.schema)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        return self._create_document(dialog.target, dialog.text, dialog.config)

    def new_stylesheet_dialog(self):
        """Crée une feuille XSLT minimale (1.0 ou 3.0), proposée dans
        ``xslt/``, l'ajoute au projet et l'affiche."""
        title = _t("documents.new_stylesheet.title")
        fn, _ = QFileDialog.getSaveFileName(
            self, title, str(self.project.root_dir / "xslt" / "nouvelle.xsl"), "XSLT (*.xsl *.xslt)")
        if not fn:
            return False
        path = Path(fn).expanduser().resolve()
        if not path.suffix:
            path = path.with_suffix(".xsl")
        if path.exists():
            QMessageBox.warning(self, title, _t("documents.new.exists", path=path))
            return False
        labels = [_t(f"transform.engine.{engine}") for _version, engine in STYLESHEET_VERSIONS]
        label, ok = QInputDialog.getItem(self, title, _t("documents.new_stylesheet.version"), labels, 0, False)
        if not ok:
            return False
        version = STYLESHEET_VERSIONS[labels.index(label)][0]
        return self._create_document(path, new_stylesheet_text(version))

    def new_schematron_dialog(self):
        """Crée un fichier Schematron minimal, proposé dans ``xml/``,
        l'ajoute au projet et l'affiche ; l'édition n'est pas modifiée (sa
        déclaration ``xml-model`` reste à écrire)."""
        title = _t("documents.new_schematron.title")
        fn, _ = QFileDialog.getSaveFileName(
            self, title, str(self.project.root_dir / "xml" / "regles.sch"), "Schematron (*.sch)")
        if not fn:
            return False
        path = Path(fn).expanduser().resolve()
        if not path.suffix:
            path = path.with_suffix(".sch")
        if path.exists():
            QMessageBox.warning(self, title, _t("documents.new.exists", path=path))
            return False
        return self._create_document(path, new_schematron_text(_t("documents.new_schematron.example")))

    def _create_document(self, path, text, config=None):
        """Écrit le nouveau fichier ``path`` (jamais par-dessus un fichier),
        l'ajoute au projet (déclaration ``config``, par défaut sans schéma
        particulier) et l'affiche."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "x", encoding="utf-8", newline="\n") as output:
                output.write(text)
        except OSError as exc:
            QMessageBox.critical(self, _t("file.save.error.title"), str(exc))
            return False
        return self._register_document(config or DocumentConfig(path))

    def remove_document_from_project(self):
        """Retire du projet le document auxiliaire affiché ; son fichier reste."""
        return self._remove_document(self.document)

    def _remove_document(self, session):
        """Retire ``session`` du projet, après confirmation (et enregistrement
        de ses modifications, si on le demande) ; son fichier reste. Une
        partie de l'édition ne se retire pas : elle suit ses xi:include."""
        if not session.is_auxiliary:
            return False
        answer = QMessageBox.question(
            self, _t("documents.remove.title"),
            _t("documents.remove.question", name=self._document_display_name(session)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return False
        if session.modified and not self._confirm_unsaved_documents([session]):
            return False
        return self._unregister_document(session)
