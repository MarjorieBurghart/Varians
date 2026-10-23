# -*- coding: utf-8 -*-
"""Parties d'une édition assemblée par XInclude : chacune a son onglet, nommé
d'après son fichier, dans l'ordre d'inclusion ; elle s'édite et s'enregistre
seule ; la liste des parties suit les xi:include de l'édition enregistrée.
Projet d'essai « sermons » (tests/data/sermons)."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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


def test_a_part_keeps_the_witnesses_and_the_preview(open_window, sermons_project):
    window = open_window(sermons_project)
    preview = window.left_tabs.indexOf(window.formatted_view)
    witnesses_hidden = window.witness_scroll.isHidden()        # témoins sans image : déjà masqués
    window.show_document(_doc(window, "s03.xml"))
    # V0.9.1.0 : témoins et état de structure, comme sur l'édition ; V0.9.1.5 :
    # l'aperçu de l'édition assemblée aussi.
    assert window.witness_scroll.isHidden() is witnesses_hidden
    assert not window.structure_status.isHidden()
    assert window.left_tabs.isTabEnabled(preview) and window.action_preview.isEnabled()
    assert not window.action_save_as.isEnabled()
    window.show_document(_doc(window, "personnes.xml"))
    assert window.witness_scroll.isHidden() and window.structure_status.isHidden()
    assert not window.left_tabs.isTabEnabled(preview) and not window.action_preview.isEnabled()
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


def test_the_web_export_warns_that_the_parts_are_not_exported_yet(open_window, sermons_project, dialogs,
                                                                   monkeypatch, tmp_path):
    import web_viewer.generator
    calls = []

    def generate(project_path, **kwargs):
        calls.append(project_path)
        return tmp_path / "viewer.html", [], {"witnesses": [], "meta": {"lines": 0}}

    monkeypatch.setattr(web_viewer.generator, "generate", generate)
    window = open_window(sermons_project)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # annuler
    window.generate_web_viewer()
    assert calls == [] and dialogs.seen[-1][1] == tr("parts.webgen.title")
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)            # exporter quand même
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # fermer le compte rendu
    window.generate_web_viewer()
    assert calls == [sermons_project]


def test_the_web_export_of_a_simple_project_does_not_warn(open_window, project_with_documents, dialogs,
                                                           monkeypatch, tmp_path):
    import web_viewer.generator
    monkeypatch.setattr(web_viewer.generator, "generate",
                        lambda project_path, **kwargs: (tmp_path / "viewer.html", [], {}))
    window = open_window(project_with_documents)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # compte rendu seulement
    window.generate_web_viewer()
    assert dialogs.seen[-1][1] == tr("webgen.done.title")


# --- Vue XSLT / CSS d'une édition en parties : lecture seule ------------------

def _preview(window):
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    return view


def test_the_preview_shows_the_assembled_edition(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)
    text = view.preview.toPlainText()
    for included in ("Sermo in adventu Domini", "Puer natus est nobis", "Surrexit Dominus vere",
                     "Veni, Sancte Spiritus", "Narrat"):                 # s01 à s04 et l'exemplum
        assert included in text, included
    # Ses paragraphes ont leur ✎ (V0.9.1.5 ; voir test_gui_assembled_preview).
    assert "tei-edit:" in view.preview.toHtml()


def test_the_preview_shows_the_unsaved_text_of_a_part(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)                                             # aperçu déjà calculé
    window.left_tabs.setCurrentIndex(0)
    window.show_document(_doc(window, "s02.xml"))
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    start = text.index("Sermo in nativitate Domini</head>")
    cursor.setPosition(start)
    cursor.setPosition(start + len("Sermo in nativitate Domini"), QTextCursor.MoveMode.KeepAnchor)
    cursor.insertText("Sermo non enregistré")
    window.show_document(window.edition_session)
    # Retour sur l'aperçu, sans actualisation forcée : la partie a changé.
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    assert "Sermo non enregistré" in view.preview.toPlainText()
    view.refresh_preview()                                              # déjà à jour
    assert view.info.text() == tr("preview.up_to_date", engine=view._last_preview_engine)


def test_the_preview_of_a_simple_edition_stays_editable(open_window, project_with_documents):
    window = open_window(project_with_documents)
    view = _preview(window)
    assert "tei-edit:" in view.preview.toHtml()


# --- « Marquer la page » et « Couper le folio » depuis une partie (V0.9.1.0) ---

def test_the_edition_can_be_written_while_a_part_is_displayed(open_window, sermons_project):
    window = open_window(sermons_project)
    part = _doc(window, "s01.xml")
    window.show_document(part)
    edition = window.edition_session
    old = window._edition_text()
    assert old == edition.text_document.toPlainText() and "<facsimile" not in old
    new = old.replace("</teiHeader>", '</teiHeader>\n  <facsimile><surface xml:id="A-13v" n="13v"/></facsimile>', 1)
    window._write_edition_text(old, new)
    assert window.document is part                            # la partie reste affichée
    assert edition.text_document.toPlainText() == new and window._edition_text() == new
    assert edition.modified and edition.lb.dirty
    assert _tabs(window)[0] == _edition_tab() + " *"
    assert edition.text_document.isUndoAvailable()           # dans l'historique de l'édition
    assert not part.modified


def test_marking_a_page_from_a_part(open_window, sermons_project, monkeypatch):
    import witness_sync

    def with_surface(old, *_args):
        return (old.replace("</teiHeader>", '</teiHeader>\n  <facsimile><surface xml:id="A-13v" n="13v"/>'
                            '</facsimile>', 1), SimpleNamespace(conflicts=[]))

    monkeypatch.setattr(witness_sync, "sync_facsimile_text", with_surface)
    window = open_window(sermons_project)
    part = _doc(window, "s01.xml")
    window.show_document(part)
    if "A" in window.panels:
        window.panels["A"]._surface_indices = {"A-13v": 0}
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("nostri. Triplex"))
    window.editor.setTextCursor(cursor)
    window._edition_write(window._mark_page_in_tei)("A", "A-13v", "13v")
    assert '<pb n="13v" edRef="#A" facs="#A-13v"/>nostri. Triplex' in window.editor.toPlainText()
    assert '<surface xml:id="A-13v" n="13v"/>' in window.edition_session.text_document.toPlainText()
    assert part.modified and window.edition_session.modified
    # Annuler dans la partie retire le pb ; le facsimile reste dans l'édition.
    window.editor.undo()
    assert window.editor.toPlainText() == text
    assert '<surface xml:id="A-13v"' in window.edition_session.text_document.toPlainText()


def test_witness_commands_writing_the_edition_are_refused_on_an_auxiliary_document(open_window, sermons_project,
                                                                                   dialogs):
    window = open_window(sermons_project)
    calls = []
    command = window._edition_write(lambda *args: calls.append(args))
    window.show_document(_doc(window, "s01.xml"))
    command("A", "A-13v", "13v")
    assert calls == [("A", "A-13v", "13v")]
    window.show_document(_doc(window, "personnes.xml"))
    dialogs.expect("information")
    command("A", "A-13v", "13v")
    assert len(calls) == 1
