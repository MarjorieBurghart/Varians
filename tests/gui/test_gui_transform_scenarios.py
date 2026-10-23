# -*- coding: utf-8 -*-
"""Fichier ▸ « Scénarios de transformation… » (V0.9.2.0) : liste des
scénarios du projet et des scénarios prédéfinis, boîte d'un scénario,
enregistrement dans project.xml."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QMessageBox

from app_context import tr
from project_config import TransformScenario, load_project
from project_management import update_project_transformations

PERSONS = TransformScenario("Personnes", "rendering/personnes.xsl", "publications/personnes.html",
                            source="file", file="xml/personnes.xml", params=(("titre", "Index"),))


def _with_scenarios(project_path, *scenarios):
    root = project_path.parent
    (root / "rendering" / "personnes.xsl").write_text("<xsl:stylesheet/>", encoding="utf-8")
    update_project_transformations(project_path, list(scenarios))
    return project_path


def _in_list(action):
    """Réponse à la liste des scénarios : ``action(dialog)``, puis Fermer."""
    def answer(dialog):
        answer.dialog = dialog
        action(dialog)
        dialog.reject()
        return dialog.result()
    return answer


def _scenario(setup):
    """Réponse à la boîte d'un scénario : ``setup(dialog)``, puis OK."""
    def answer(dialog):
        answer.dialog = dialog
        setup(dialog)
        dialog.accept()
        return dialog.result()
    return answer


def _rows(dialog, group):
    item = dialog.project_group if group == "project" else dialog.predefined_group
    return [[item.child(i).text(c) for c in range(4)] for i in range(item.childCount())]


def test_the_file_menu_lists_the_scenarios_of_the_project_and_the_predefined_ones(open_window, sermons_project,
                                                                                  dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))
    assert window.action_transform_scenarios in window.file_menu.actions()
    listing = _in_list(lambda dialog: None)
    dialogs.expect("dialog", listing)
    window.action_transform_scenarios.trigger()
    dialog = listing.dialog
    assert _rows(dialog, "project") == [["Personnes", tr("transform.source.file", file="xml/personnes.xml"),
                                         tr("transform.engine.lxml"), ""]]
    assert _rows(dialog, "predefined") == [[tr("transform.predefined.varians-html"), tr("transform.source.edition"),
                                            tr("transform.engine.lxml"), ""]]


def test_a_new_scenario_starts_from_the_stylesheet_of_the_preview_and_is_saved(open_window, sermons_project,
                                                                             dialogs):
    window = open_window(sermons_project)

    def fill(dialog):
        # Feuille et CSS de la Vue XSLT / CSS ; le résultat suit le nom.
        assert dialog.xslt_field.text() == "${varians}/tei-to-html.xsl"
        assert dialog.css_field.text() == "rendering/tei.css"
        assert dialog.edition_radio.isChecked() and dialog.engine() == "lxml"
        dialog.name_edit.setText("Édition : HTML")
        assert dialog.output_field.text() == "publications/Édition _ HTML.html"
        dialog.output_field.edit.setText("publications/edition.html")
        dialog.name_edit.setText("Édition HTML")
        assert dialog.output_field.text() == "publications/edition.html"      # choisi : il ne suit plus
        dialog.add_param_row("titre", "Sermons")
        dialog.add_param_row("", "ignoré")

    dialogs.expect("dialog", _in_list(lambda dialog: dialog.add_scenario()))
    dialogs.expect("dialog", _scenario(fill))
    window.transform_scenarios_dialog()
    expected = (TransformScenario("Édition HTML", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                  css="rendering/tei.css", params=(("titre", "Sermons"),)),)
    assert load_project(sermons_project).transformations == expected
    assert window.project.transformations == expected


def test_a_scenario_is_edited_and_keeps_an_unknown_engine(open_window, sermons_project, dialogs):
    future = TransformScenario("Futur", "rendering/personnes.xsl", "publications/futur.html", engine="xsltproc")
    window = open_window(_with_scenarios(sermons_project, PERSONS, future))

    def select_and_edit(row):
        def action(dialog):
            dialog.tree.setCurrentItem(dialog.project_group.child(row))
            dialog.edit_scenario()
        return action

    def change(dialog):
        assert dialog.file_radio.isChecked() and dialog.file_field.text() == "xml/personnes.xml"
        assert dialog.params() == (("titre", "Index"),)
        dialog.remove_param_row(0)
        dialog.engine_combo.setCurrentIndex(dialog.engine_combo.findData("saxon"))

    dialogs.expect("dialog", _in_list(select_and_edit(0)))
    dialogs.expect("dialog", _scenario(change))
    if not __import__("xslt_scenarios").saxon_available():
        dialogs.expect("question", QMessageBox.StandardButton.Yes)       # « Saxon n'est pas installé »
    window.transform_scenarios_dialog()
    dialogs.expect("dialog", _in_list(select_and_edit(1)))
    dialogs.expect("dialog", _scenario(lambda dialog: None))
    dialogs.expect("question", QMessageBox.StandardButton.Yes)           # « Moteur inconnu : xsltproc »
    window.transform_scenarios_dialog()
    assert load_project(sermons_project).transformations == (
        TransformScenario("Personnes", "rendering/personnes.xsl", "publications/personnes.html",
                          source="file", file="xml/personnes.xml", engine="saxon"),
        TransformScenario("Futur", "rendering/personnes.xsl", "publications/futur.html", engine="xsltproc"),
    )


def test_a_predefined_scenario_is_duplicated_into_the_project(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)

    def duplicate(dialog):
        dialog.tree.setCurrentItem(dialog.predefined_group.child(0))
        assert not dialog.edit_btn.isEnabled() and not dialog.remove_btn.isEnabled()
        dialog.duplicate_scenario()

    dialogs.expect("dialog", _in_list(duplicate))
    dialogs.expect("dialog", _scenario(lambda dialog: dialog.add_param_row("css", "edition.css")))
    window.transform_scenarios_dialog()
    (scenario,) = load_project(sermons_project).transformations
    assert scenario == TransformScenario(tr("transform.predefined.varians-html"), "${varians}/tei-to-html.xsl",
                                         "publications/edition.html", css="${varians}/tei.css",
                                         params=(("css", "edition.css"),))

    # Une seconde copie prend un autre nom.
    dialogs.expect("dialog", _in_list(duplicate))
    copy = _scenario(lambda dialog: None)
    dialogs.expect("dialog", copy)
    window.transform_scenarios_dialog()
    assert copy.dialog.name_edit.text() == tr("transform.copy_name", name=scenario.name)


def test_a_scenario_is_removed_after_confirmation(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))

    def remove(dialog):
        dialog.tree.setCurrentItem(dialog.project_group.child(0))
        dialog.remove_scenario()

    dialogs.expect("dialog", _in_list(remove))
    dialogs.expect("question", QMessageBox.StandardButton.Yes)
    window.transform_scenarios_dialog()
    assert load_project(sermons_project).transformations == ()


def test_the_list_shows_the_problem_of_a_scenario(open_window, sermons_project, dialogs):
    missing = TransformScenario("Sans feuille", "rendering/absente.xsl", "publications/a.html")
    window = open_window(_with_scenarios(sermons_project, missing))
    listing = _in_list(lambda dialog: None)
    dialogs.expect("dialog", listing)
    window.transform_scenarios_dialog()
    item = listing.dialog.project_group.child(0)
    assert item.text(3) == tr("transform.problem.xslt_missing", detail="rendering/absente.xsl")


def test_a_scenario_that_would_overwrite_a_source_is_refused(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)

    def fill(dialog):
        dialog.name_edit.setText("Écrase")
        dialog.output_field.edit.setText("xml/edition.xml")
        dialog.accept()                                   # refusé : la boîte reste ouverte
        assert dialog.result() != QDialog.DialogCode.Accepted
        dialog.output_field.edit.setText("publications/ecrase.html")

    dialogs.expect("dialog", _in_list(lambda dialog: dialog.add_scenario()))
    dialogs.expect("dialog", _scenario(fill))
    dialogs.expect("warning")
    window.transform_scenarios_dialog()
    assert [s.output for s in load_project(sermons_project).transformations] == ["publications/ecrase.html"]


def test_two_scenarios_may_not_share_a_name(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))

    def fill(dialog):
        dialog.name_edit.setText("Personnes")
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        dialog.name_edit.setText("Personnes 2")

    dialogs.expect("dialog", _in_list(lambda dialog: dialog.add_scenario()))
    dialogs.expect("dialog", _scenario(fill))
    dialogs.expect("warning")
    window.transform_scenarios_dialog()
    assert [s.name for s in load_project(sermons_project).transformations] == ["Personnes", "Personnes 2"]


def test_saxon_missing_is_shown_in_the_choice_of_engine(open_window, sermons_project, dialogs, monkeypatch):
    import transform_ui
    monkeypatch.setattr(transform_ui, "saxon_available", lambda: False)
    window = open_window(sermons_project)
    seen = {}

    def look(dialog):
        seen["saxon"] = dialog.engine_combo.itemText(dialog.engine_combo.findData("saxon"))

    dialogs.expect("dialog", _in_list(lambda dialog: dialog.add_scenario()))
    dialogs.expect("dialog", lambda dialog: (look(dialog), dialog.reject(), dialog.result())[-1])
    window.transform_scenarios_dialog()
    assert seen["saxon"] == tr("transform.engine.missing", engine=tr("transform.engine.saxon"))
