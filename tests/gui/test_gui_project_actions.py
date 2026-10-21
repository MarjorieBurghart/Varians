# -*- coding: utf-8 -*-
"""Actions de projet dans la vraie fenêtre."""
from __future__ import annotations


def test_validating_project_settings_reloads_project_in_new_window(open_window, example_project, dialogs, qtbot):
    window = open_window(example_project)

    def accept(dialog):
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", accept)                 # Réglages du projet : OK
    dialogs.expect("information")                    # « Réglages enregistrés »
    window.project_settings_dialog()

    new_window = window._replacement_window
    try:
        assert type(new_window) is type(window)
        assert new_window.project.path == window.project.path
        assert new_window.current_path == window.current_path
        assert not window.isVisible()
    finally:
        if new_window is not None:
            new_window._force_close = True
            new_window.close()


def test_project_settings_keep_declared_documents(open_window, example_project, dialogs, qtbot):
    # La fenêtre de réglages régénère project.xml : les documents auxiliaires
    # déclarés ne doivent pas disparaître.
    from project_config import load_project

    root = example_project.parent
    (root / "xml" / "personnes.xml").write_text("<listPerson/>", encoding="utf-8")
    text = example_project.read_text(encoding="utf-8")
    text = text.replace(
        "</teiManuscriptProject>",
        '  <documents><document file="xml/personnes.xml" label="Personnes" schema="none"/></documents>\n'
        "</teiManuscriptProject>")
    example_project.write_text(text, encoding="utf-8")
    declared = load_project(example_project).documents
    assert [d.label for d in declared] == ["Personnes"]

    window = open_window(example_project)

    def accept(dialog):
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", accept)
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    try:
        assert load_project(example_project).documents == declared
    finally:
        if new_window is not None:
            new_window._force_close = True
            new_window.close()


def test_project_settings_keep_saved_xpath_queries(open_window, example_project, dialogs, qtbot):
    # Comme les documents : la réécriture de project.xml garde les requêtes.
    from project_config import XPathQuery, load_project
    from project_management import update_project_xpath_queries

    queries = [XPathQuery("rdg sans @wit", "//tei:rdg[not(@wit)]")]
    update_project_xpath_queries(example_project, queries)
    window = open_window(example_project)

    def accept(dialog):
        dialog.accept()
        return dialog.result()

    dialogs.expect("dialog", accept)
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    try:
        assert load_project(example_project).xpath_queries == tuple(queries)
    finally:
        if new_window is not None:
            new_window._force_close = True
            new_window.close()
