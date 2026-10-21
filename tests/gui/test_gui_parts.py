# -*- coding: utf-8 -*-
"""Parties d'une édition assemblée par XInclude : chacune a son onglet, nommé
d'après son fichier, dans l'ordre d'inclusion ; elle s'édite et s'enregistre
seule ; la liste des parties suit les xi:include de l'édition enregistrée.
Projet d'essai « sermons » (tests/data/sermons)."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app_context import tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents

PARTS = ["s01.xml", "s02.xml", "s03.xml", "s04.xml", "s04_exemplum.xml"]


def _tabs(window):
    bar = window.document_tab_bar
    return [bar.tabText(i) for i in range(bar.count())]


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _edition_tab():
    return tr("documents.edition_tab")


def _type_at_end(window, text):
    """Saisie à la fin du document affiché (après la déclaration XML)."""
    cursor = window.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText(text)


def _set_edition_text(window, text):
    window.show_document(window.edition_session)
    window.editor.selectAll()
    window.editor.insertPlainText(text)


def test_each_part_has_a_tab_in_inclusion_order(open_window, sermons_project):
    window = open_window(sermons_project)
    assert _tabs(window) == [_edition_tab()] + PARTS + ["Personnes"]
    assert [s.role for s in window.documents] == ["edition"] + ["part"] * 5 + ["auxiliary"]
    part = _doc(window, "s02.xml")
    assert part.is_part and part.in_edition and not part.is_auxiliary and not part.is_edition
    assert window.edition_session.in_edition and not window.edition_session.is_part
    assert _doc(window, "personnes.xml").is_auxiliary and not _doc(window, "personnes.xml").in_edition
    assert window.document is window.edition_session


def test_a_part_is_edited_and_saved_on_its_own(open_window, sermons_project, qtbot):
    window = open_window(sermons_project)
    part = _doc(window, "s01.xml")
    assert window.show_document(part)
    assert "Sermo in adventu Domini" in window.editor.toPlainText()
    _type_at_end(window, "<!-- essai -->")
    assert part.modified and not window.edition_session.modified
    assert window.save()
    assert part.path.read_text(encoding="utf-8").endswith("<!-- essai -->")
    assert not part.modified
    # Historique d'annulation propre à la partie.
    assert part.text_document.isUndoAvailable()
    assert not window.edition_session.text_document.isUndoAvailable()


def test_a_part_hides_the_witnesses_and_the_preview_like_an_auxiliary_document(open_window, sermons_project):
    window = open_window(sermons_project)
    preview = window.left_tabs.indexOf(window.formatted_view)
    witnesses_hidden = window.witness_scroll.isHidden()        # témoins sans image : déjà masqués
    window.show_document(_doc(window, "s03.xml"))
    assert window.witness_scroll.isHidden() and window.structure_status.isHidden()
    assert not window.left_tabs.isTabEnabled(preview)
    assert not window.action_save_as.isEnabled()
    window.show_document(window.edition_session)
    assert window.witness_scroll.isHidden() is witnesses_hidden
    assert window.left_tabs.isTabEnabled(preview) and window.action_save_as.isEnabled()


def test_quitting_with_a_modified_part_offers_to_save_it(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)
    part = _doc(window, "s02.xml")
    window.show_document(part)
    _type_at_end(window, "<!-- essai -->")
    window.show_document(window.edition_session)
    dialogs.expect("box", QMessageBox.ButtonRole.DestructiveRole)
    assert window.confirm_close_application()
    kind, _title, text = dialogs.seen[-1]
    assert kind == "box" and "s02.xml" in text


def test_rename_and_remove_concern_auxiliary_documents_only(open_window, sermons_project):
    window = open_window(sermons_project)
    for name, enabled in (("s01.xml", False), ("Personnes", True)):
        menu = window._document_tab_menu(_tabs(window).index(name))
        actions = {action.text(): action.isEnabled() for action in menu.actions() if action.text()}
        assert actions[tr("documents.tab.rename")] is enabled
        assert actions[tr("documents.remove.menu")] is enabled
    part = _doc(window, "s01.xml")
    assert not window.rename_document_tab(part)
    assert not window._remove_document(part)
    window.show_document(part)
    assert not window.action_remove_document.isEnabled()
    window.show_document(_doc(window, "personnes.xml"))
    assert window.action_remove_document.isEnabled()


def test_the_parts_follow_the_saved_edition(open_window, sermons_project):
    window = open_window(sermons_project)
    xml = sermons_project.parent / "xml"
    (xml / "sermons" / "s05.xml").write_text(
        '<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="s05" type="sermo" n="5"><head>Sermo</head></div>\n',
        encoding="utf-8")
    text = window.edition_session.text_document.toPlainText()
    text = text.replace('<xi:include href="sermons/s04.xml"/>', '<xi:include href="sermons/s05.xml"/>')
    _set_edition_text(window, text)
    assert _tabs(window)[1:6] == PARTS                     # pas avant l'enregistrement
    assert window.save()
    assert _tabs(window) == [_edition_tab(), "s01.xml", "s02.xml", "s03.xml", "s05.xml", "Personnes"]
    assert _doc(window, "s05.xml").is_part


def test_a_modified_part_keeps_its_tab_until_it_is_saved(open_window, sermons_project):
    window = open_window(sermons_project)
    part = _doc(window, "s02.xml")
    window.show_document(part)
    _type_at_end(window, "<!-- essai -->")
    text = window.edition_session.text_document.toPlainText()
    _set_edition_text(window, text.replace('<xi:include href="sermons/s02.xml" xpointer="s02"/>', ""))
    assert window.save()
    assert "s02.xml *" in _tabs(window)                    # modifications non enregistrées
    assert window._save_session(part)
    assert "s02.xml" not in _tabs(window) and part not in window.documents
    assert window.document is window.edition_session


def test_a_new_part_comes_after_the_existing_parts_whatever_the_saved_order(open_window, sermons_project):
    window = open_window(sermons_project)
    window.set_document_tabs(["xml/personnes.xml", "edition", "xml/sermons/s03.xml"], [])
    assert _tabs(window)[:3] == ["Personnes", _edition_tab(), "s03.xml"]
    edition = sermons_project.parent / "xml" / "edition.xml"
    (edition.parent / "sermons" / "s05.xml").write_text(
        '<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="s05"/>\n', encoding="utf-8")
    edition.write_text(edition.read_text(encoding="utf-8").replace(
        '<xi:include href="sermons/s04.xml"/>',
        '<xi:include href="sermons/s04.xml"/>\n      <xi:include href="sermons/s05.xml"/>'), encoding="utf-8")
    reopened = open_window(sermons_project)
    tabs = _tabs(reopened)
    # Les parties absentes de l'ordre mémorisé suivent les parties connues,
    # dans l'ordre d'inclusion, avant ce qui venait après elles.
    assert tabs == ["Personnes", _edition_tab(), "s03.xml", "s01.xml", "s02.xml", "s04.xml",
                    "s04_exemplum.xml", "s05.xml"]


def test_a_file_both_declared_and_included_is_one_part(open_window, sermons_project):
    s01 = sermons_project.parent / "xml" / "sermons" / "s01.xml"
    documents = list(load_project(sermons_project).documents) + [DocumentConfig(s01, "Sermon 1")]
    update_project_documents(sermons_project, documents)
    window = open_window(sermons_project)
    assert [s.path.name for s in window.documents].count("s01.xml") == 1
    assert _doc(window, "s01.xml").is_part
    assert _tabs(window) == [_edition_tab()] + PARTS + ["Personnes"]


def test_save_as_into_another_folder_warns_about_the_inclusions(open_window, sermons_project, dialogs,
                                                                 monkeypatch, tmp_path):
    window = open_window(sermons_project)
    elsewhere = tmp_path / "ailleurs"
    elsewhere.mkdir()
    target = elsewhere / "edition.xml"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(target), "")))
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert not window.save_as()
    assert not target.exists()
    assert "sermons/s01.xml" in dialogs.seen[-1][2]
    same_folder = sermons_project.parent / "xml" / "edition_copie.xml"
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: (str(same_folder), "")))
    assert window.save_as()                                 # même dossier : aucun avertissement
    assert same_folder.exists()


def test_an_edition_without_inclusion_has_no_part(open_window, project_with_documents):
    window = open_window(project_with_documents)
    assert [s.role for s in window.documents] == ["edition", "auxiliary"]
    assert not any(s.is_part for s in window.documents)
