# -*- coding: utf-8 -*-
"""Menu Fichier ▸ Documents XML du projet : ajouter un document existant,
créer un nouveau document ou une nouvelle feuille XSLT, retirer un document
du projet.

Un fichier situé hors du projet est copié dans son dossier ``xml/``, ou
``xslt/`` pour une feuille XSLT (``.xsl``, ``.xslt``), jamais par-dessus un
fichier existant ; retirer un document du projet ne supprime jamais son
fichier.
"""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

from PySide6.QtWidgets import QFileDialog, QInputDialog, QLineEdit, QMessageBox
from app_context import tr as _t
from project_config import DocumentConfig

TEI_NS = "http://www.tei-c.org/ns/1.0"
STYLESHEET_SUFFIXES = (".xsl", ".xslt")
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
    return Path(path).suffix.lower() in STYLESHEET_SUFFIXES


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
    folder = root / ("xslt" if is_stylesheet_file(source) else "xml")
    candidate = folder / source.name
    number = 2
    while candidate.exists():
        candidate = folder / f"{source.stem}_{number}{source.suffix}"
        number += 1
    return candidate, True


def copy_document_into_project(source, project_root):
    """Chemin du document dans le projet, après copie si nécessaire."""
    target, copy = document_target_path(source, project_root)
    if copy:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(source).expanduser().resolve(), target)
    return target


def new_document_text(root_name):
    """Document XML vide d'élément racine ``root_name`` (dans l'espace de
    noms TEI pour ``TEI``). ValueError si ce n'est pas un nom d'élément."""
    namespace = f' xmlns="{TEI_NS}"' if root_name == "TEI" else ""
    text = f'<?xml version="1.0" encoding="UTF-8"?>\n<{root_name}{namespace}>\n</{root_name}>\n'
    try:
        ET.fromstring(text)
    except ET.ParseError:
        raise ValueError(root_name) from None
    return text


def new_stylesheet_text(version):
    """Feuille XSLT minimale (``version`` : 1.0 ou 3.0) : espace de noms TEI
    déclaré, ``xsl:output`` HTML et un ``xsl:template match="/"``."""
    if version not in _STYLESHEET_HEADS:
        raise ValueError(version)
    return '<?xml version="1.0" encoding="UTF-8"?>\n' + _STYLESHEET_HEADS[version] + _STYLESHEET_BODY


class DocumentDialogsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def add_document_dialog(self):
        """Ajoute au projet un document XML ou une feuille XSLT existants et
        l'affiche."""
        fn, _ = QFileDialog.getOpenFileName(
            self, _t("documents.add.title"), str(self.project.root_dir / "xml"),
            f"XML, XSLT (*.xml *.xsl *.xslt);;XML (*.xml);;XSLT (*.xsl *.xslt);;{_t('common.all_files')} (*)")
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
        """Crée un document XML vide, l'ajoute au projet et l'affiche."""
        fn, _ = QFileDialog.getSaveFileName(
            self, _t("documents.new.title"), str(self.project.root_dir / "xml" / "nouveau.xml"),
            "XML (*.xml)")
        if not fn:
            return False
        path = Path(fn).expanduser().resolve()
        if not path.suffix:
            path = path.with_suffix(".xml")
        if path.exists():
            QMessageBox.warning(self, _t("documents.new.title"), _t("documents.new.exists", path=path))
            return False
        name, ok = QInputDialog.getText(self, _t("documents.new.title"), _t("documents.new.root"),
                                        QLineEdit.EchoMode.Normal, "TEI")
        if not ok:
            return False
        name = name.strip()
        try:
            text = new_document_text(name)
        except ValueError:
            QMessageBox.warning(self, _t("documents.new.title"), _t("documents.new.root_invalid", name=name))
            return False
        return self._create_document(path, text)

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

    def _create_document(self, path, text):
        """Écrit le nouveau fichier ``path`` (jamais par-dessus un fichier),
        l'ajoute au projet et l'affiche."""
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, "x", encoding="utf-8", newline="\n") as output:
                output.write(text)
        except OSError as exc:
            QMessageBox.critical(self, _t("file.save.error.title"), str(exc))
            return False
        return self._register_document(DocumentConfig(path))

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
