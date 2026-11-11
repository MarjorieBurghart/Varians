# -*- coding: utf-8 -*-
"""Gestion des vues nommées de la Vue XSLT / CSS (V0.9.4.4) : menu « Vues »
à côté de la liste, « Nouvelle vue… », « Modifier la vue… », « Retirer la
vue », « Ouvrir la feuille XSLT ». Les vues sont écrites dans project.xml
(sous <edition> ou sous le <document> affiché) ; leurs fichiers ne sont
jamais supprimés. Une nouvelle vue peut avoir une feuille XSLT 1.0 et une
CSS de départ, nommées d'après elle."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox

from app_context import tr
from project_config import ViewConfig, load_project
from test_gui_document_views import _personnes, _wait_preview, views_project  # noqa: F401 (fixture)


def _answer(dialogs, fill, check=None):
    """Réponse programmée à la boîte d'une vue : la remplir (``fill``), puis
    « OK » ; ``check`` examine la boîte avant."""
    opened = []

    def answer(dialog):
        opened.append(dialog)
        if check is not None:
            check(dialog)
        fill(dialog)
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", answer)
    return opened


def _personnes_views(project_path):
    return next(d for d in load_project(project_path).documents if d.path.name == "personnes.xml").views


def test_a_new_view_gets_starter_files_and_the_entries_of_the_list(open_window, project_with_documents,
                                                                   dialogs, qtbot):
    window = open_window(project_with_documents)
    root = project_with_documents.parent
    assert window.show_document(_personnes(window))
    view = window.formatted_view

    def check(dialog):
        assert dialog.windowTitle() == tr("views.new.title")
        assert dialog.create_check.isChecked() and not dialog.create_check.isHidden()
        assert dialog.units_edit.text() == "person"                   # entrées de la liste
        dialog.name_edit.setText("Fiches")
        assert dialog.xslt_edit.text() == "xslt/fiches.xsl" and not dialog.xslt_edit.isEnabled()
        assert dialog.css_edit.text() == "rendering/fiches.css"

    _answer(dialogs, lambda dialog: None, check)
    assert view.new_view()
    assert (root / "xslt" / "fiches.xsl").is_file() and (root / "rendering" / "fiches.css").is_file()
    expected = (ViewConfig("Fiches", "xslt/fiches.xsl", "rendering/fiches.css", ("person",)),)
    assert _personnes_views(project_with_documents) == expected
    assert load_project(project_with_documents).edition_views == ()
    assert view.current_view == expected[0] and view.view_combo.currentText() == "Fiches"
    _wait_preview(qtbot, view, "Fiches")
    assert [index for _marker, _pos, index in view.preview._paragraph_markers] == [0, 1]


def test_a_new_view_of_the_edition_can_use_an_existing_stylesheet(open_window, project_with_documents, dialogs, qtbot):
    window = open_window(project_with_documents)
    view = window.formatted_view

    def fill(dialog):
        assert dialog.units_edit.text() == ""                          # règle de l'édition
        dialog.name_edit.setText("Apparat en notes")
        dialog.create_check.setChecked(False)
        assert dialog.xslt_edit.isEnabled() and dialog.xslt_edit.text() == ""
        dialog.xslt_edit.setText("${varians}/apparat-en-notes.xsl")

    _answer(dialogs, fill)
    assert view.new_view()
    expected = ViewConfig("Apparat en notes", "${varians}/apparat-en-notes.xsl")
    assert load_project(project_with_documents).edition_views == (expected,)
    assert window.project.edition_views == (expected,)
    assert view.current_view == expected
    assert not (project_with_documents.parent / "xslt" / "apparat-en-notes.xsl").exists()


def test_a_wrong_view_is_refused_and_the_dialog_stays_open(open_window, views_project, dialogs):
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    tries = []

    def answer(dialog):
        dialog.create_check.setChecked(False)
        for name, xslt in (("index", "xslt/index.xsl"), ("Fiches", "xslt/absente.xsl"), ("Fiches", "xslt/index.xsl")):
            dialog.name_edit.setText(name)
            dialog.xslt_edit.setText(xslt)
            dialog.accept()
            tries.append(dialog.result())
        return dialog.result()

    dialogs.expect("dialog", answer)
    dialogs.expect("warning")
    dialogs.expect("warning")
    assert view.new_view()
    assert tries == [0, 0, QDialog.DialogCode.Accepted]
    assert [title for kind, title, _text in dialogs.seen if kind == "warning"] == [tr("views.new.title")] * 2
    assert [v.name for v in _personnes_views(views_project)] == ["Index", "Fiches"]


def test_editing_a_view_rewrites_it_and_keeps_the_choice(open_window, views_project, dialogs, qtbot):
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")

    def check(dialog):
        assert dialog.windowTitle() == tr("views.edit.title")
        assert dialog.create_check.isHidden()
        assert (dialog.name_edit.text(), dialog.xslt_edit.text(), dialog.css_edit.text(), dialog.units_edit.text()) \
            == ("Index", "xslt/index.xsl", "rendering/index.css", "person")

    def fill(dialog):
        dialog.name_edit.setText("Fiches")
        dialog.css_edit.setText("")

    _answer(dialogs, fill, check)
    assert view.edit_view()
    expected = ViewConfig("Fiches", "xslt/index.xsl", "", ("person",))
    assert _personnes_views(views_project) == (expected,)
    assert view.current_view == expected and view.view_combo.currentText() == "Fiches"
    assert view.css_path == window.project.css
    again = open_window(views_project)
    assert again.show_document(_personnes(again))
    assert again.formatted_view.current_view == expected


def test_removing_a_view_keeps_its_files(open_window, views_project, dialogs):
    window = open_window(views_project)
    root = views_project.parent
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")
    dialogs.expect("question", QMessageBox.StandardButton.No)
    assert not view.remove_view()
    assert len(_personnes_views(views_project)) == 1
    dialogs.expect("question", QMessageBox.StandardButton.Yes)
    assert view.remove_view()
    assert _personnes_views(views_project) == ()
    assert view.current_view is None and view.view_combo.count() == 1
    assert (root / "xslt" / "index.xsl").is_file() and (root / "rendering" / "index.css").is_file()
    question = [text for kind, _title, text in dialogs.seen if kind == "question"][-1]
    assert question == tr("views.remove.question", name="Index")


def test_the_project_view_is_neither_edited_nor_removed(open_window, views_project):
    window = open_window(views_project)
    view = window.formatted_view
    assert view.current_view is None
    assert view.new_view_action.isEnabled()
    assert not view.edit_view_action.isEnabled() and not view.remove_view_action.isEnabled()
    assert not view.open_view_stylesheet_action.isEnabled()
    assert view.select_view("Brute")
    assert view.edit_view_action.isEnabled() and view.remove_view_action.isEnabled()
    assert view.open_view_stylesheet_action.isEnabled()
    assert view.views_button.menu().actions()[:3] == [view.new_view_action, view.edit_view_action,
                                                     view.remove_view_action]


def test_the_stylesheet_of_a_view_opens_in_a_tab(open_window, views_project):
    window = open_window(views_project)
    assert window.show_document(_personnes(window))
    view = window.formatted_view
    assert view.select_view("Index")
    assert view.open_view_stylesheet()
    stylesheet = (views_project.parent / "xslt" / "index.xsl").resolve()
    assert window.document.path == stylesheet
    assert any(d.path == stylesheet for d in load_project(views_project).documents)
    assert window.show_document(_personnes(window))
    count = len(window.documents)
    assert view.open_view_stylesheet()                                  # déjà ouverte : pas de doublon
    assert len(window.documents) == count and window.document.path == stylesheet
