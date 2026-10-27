# -*- coding: utf-8 -*-
"""Fichier ▸ « Scénarios de transformation… » (V0.9.2.0) : liste des
scénarios du projet et des scénarios prédéfinis, boîte d'un scénario,
enregistrement dans project.xml ; « Ouvrir la feuille » (V0.9.2.1), qui crée
la feuille de personnalisation d'un scénario TEI (V0.9.2.2)."""
from __future__ import annotations

from dataclasses import replace

import pytest
from PySide6.QtWidgets import QDialog, QMessageBox

from app_context import tr
from project_config import TransformScenario, load_project
from project_management import update_project_transformations
from xslt_scenarios import saxon_available

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
    item = {"project": dialog.project_group, "predefined": dialog.predefined_group, "tei": dialog.tei_group}[group]
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
                                            tr("transform.engine.lxml"), ""], [tr("transform.group.tei"), "", "", ""]]
    # V0.9.2.7 : les scénarios des TEI Stylesheets, dans un sous-groupe replié.
    assert dialog.predefined_group.child(1) is dialog.tei_group and not dialog.tei_group.isExpanded()
    assert _rows(dialog, "tei") == [
        [tr(f"transform.predefined.{key}"), tr("transform.source.edition"), tr("transform.engine.saxon"), ""]
        for key in ("tei-html", "tei-txt", "tei-markdown", "tei-latex")]


def test_a_tei_scenario_is_chosen_in_its_sub_group(open_window, sermons_project, dialogs):
    from transform_ui import predefined
    window = open_window(sermons_project)

    def check(dialog):
        from PySide6.QtCore import Qt
        assert not dialog.tei_group.flags() & Qt.ItemFlag.ItemIsSelectable
        dialog.tree.setCurrentItem(dialog.tei_group)
        assert dialog.selected() is None and not dialog.run_btn.isEnabled()
        item = dialog.item_for("predefined", 2)
        assert item.parent() is dialog.tei_group
        dialog.tree.setCurrentItem(item)
        assert dialog.selected() == ("predefined", 2, predefined()[2]) and dialog.run_btn.isEnabled()
        assert dialog.item_for("predefined", 0).parent() is dialog.predefined_group

    listing = _in_list(check)
    dialogs.expect("dialog", listing)
    window.action_transform_scenarios.trigger()


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


def test_the_package_of_a_scenario_is_chosen_and_an_unknown_one_is_kept(open_window, sermons_project, dialogs):
    book = TransformScenario("Livre", "rendering/personnes.xsl", "publications/livre.docx", engine="saxon",
                             package="docx")
    future = TransformScenario("Futur", "rendering/personnes.xsl", "publications/futur.pdf", engine="saxon",
                               package="pdf")
    window = open_window(_with_scenarios(sermons_project, book, future))
    seen = {}

    def select_and_edit(row):
        def action(dialog):
            dialog.tree.setCurrentItem(dialog.project_group.child(row))
            dialog.edit_scenario()
        return action

    def change(dialog):
        seen["choices"] = [dialog.package_combo.itemData(i) for i in range(dialog.package_combo.count())]
        seen["docx"] = dialog.package_combo.currentData()
        dialog.package_combo.setCurrentIndex(dialog.package_combo.findData("odt"))

    def keep(dialog):
        seen["pdf"] = dialog.package_combo.currentData()

    answers = [] if saxon_available() else [("question", QMessageBox.StandardButton.Yes)]
    dialogs.expect("dialog", _in_list(select_and_edit(0)))
    dialogs.expect("dialog", _scenario(change))
    for answer in answers:
        dialogs.expect(*answer)
    window.transform_scenarios_dialog()
    dialogs.expect("dialog", _in_list(select_and_edit(1)))
    dialogs.expect("dialog", _scenario(keep))
    dialogs.expect("question", QMessageBox.StandardButton.Yes)           # « Paquet inconnu : pdf »
    window.transform_scenarios_dialog()
    assert seen == {"choices": ["", "pages", "docx", "odt", "epub"], "docx": "docx", "pdf": "pdf"}
    assert [s.package for s in load_project(sermons_project).transformations] == ["odt", "pdf"]


def test_a_predefined_scenario_is_duplicated_into_the_project(open_window, sermons_project, dialogs):
    window = open_window(sermons_project)

    def duplicate(dialog):
        dialog.tree.setCurrentItem(dialog.item_for("predefined", 0))
        assert not dialog.edit_btn.isEnabled() and not dialog.remove_btn.isEnabled()
        dialog.duplicate_scenario()

    dialogs.expect("dialog", _in_list(duplicate))
    dialogs.expect("dialog", _scenario(lambda dialog: dialog.add_param_row("css", "edition.css")))
    window.transform_scenarios_dialog()
    (scenario,) = load_project(sermons_project).transformations
    assert scenario == TransformScenario(tr("transform.predefined.varians-html"), "${varians}/tei-to-html.xsl",
                                         "publications/edition.html", css="${varians}/tei.css",
                                         params=(("tocTitle", tr("preview.toc")), ("css", "edition.css")))

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


# --- « Ouvrir la feuille » (V0.9.2.1) -----------------------------------------------------------

ROLE = QMessageBox.ButtonRole


def _keep_open(action):
    """Réponse à la liste : ``action(dialog)``, qui la ferme elle-même."""
    def answer(dialog):
        answer.dialog = dialog
        action(dialog)
        return dialog.result()
    return answer


def _open_row(group, row):
    def action(dialog):
        dialog.tree.setCurrentItem(dialog.item_for(group, row))
        dialog.open_stylesheet_btn.click()
    return action


def _declared(project_path):
    """Documents inscrits au projet, hors ceux du jeu d'essai (xml/personnes.xml)."""
    return [d.path for d in load_project(project_path).documents if d.path.parent.name != "xml"]


def test_the_stylesheet_of_a_scenario_opens_as_a_document_of_the_project(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))
    stylesheet = sermons_project.parent / "rendering" / "personnes.xsl"
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    window.transform_scenarios_dialog()
    assert window.document.path == stylesheet
    assert _declared(sermons_project) == [stylesheet]
    assert load_project(sermons_project).transformations == (PERSONS,)

    # Une seconde fois : le document déjà inscrit est affiché.
    window.show_document(window.edition_session)
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    window.transform_scenarios_dialog()
    assert window.document.path == stylesheet
    assert _declared(sermons_project) == [stylesheet]


def test_the_open_button_needs_a_stylesheet_of_the_project(open_window, sermons_project, dialogs):
    missing = TransformScenario("Sans feuille", "rendering/absente.xsl", "publications/a.html")
    window = open_window(_with_scenarios(sermons_project, PERSONS, missing))

    def check(dialog):
        button = dialog.open_stylesheet_btn
        assert button.text() == tr("transform.open_stylesheet")
        dialog.tree.setCurrentItem(dialog.project_group.child(0))
        assert button.isEnabled() and button.toolTip() == tr("transform.open_stylesheet.tip")
        dialog.tree.setCurrentItem(dialog.project_group.child(1))
        assert not button.isEnabled()
        dialog.tree.setCurrentItem(dialog.item_for("predefined", 0))
        assert not button.isEnabled() and button.toolTip() == tr("transform.open_stylesheet.predefined")

    dialogs.expect("dialog", _in_list(check))
    window.transform_scenarios_dialog()


def _outside(tmp_path):
    outside = tmp_path / "ailleurs" / "index.xsl"
    outside.parent.mkdir()
    outside.write_text('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"/>',
                       encoding="utf-8")
    return outside


def test_an_outside_stylesheet_is_copied_into_xslt_and_the_scenario_uses_the_copy(open_window, sermons_project,
                                                                                  dialogs, tmp_path):
    outside = _outside(tmp_path)
    scenario = TransformScenario("Index", outside.as_posix(), "publications/index.html")
    (sermons_project.parent / "xslt").mkdir()
    (sermons_project.parent / "xslt" / "index.xsl").write_text("<existant/>", encoding="utf-8")
    window = open_window(_with_scenarios(sermons_project, scenario))
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.AcceptRole)                           # Copier dans le projet
    window.transform_scenarios_dialog()
    copy = sermons_project.parent / "xslt" / "index_2.xsl"
    assert copy.read_text(encoding="utf-8") == outside.read_text(encoding="utf-8")
    assert (sermons_project.parent / "xslt" / "index.xsl").read_text(encoding="utf-8") == "<existant/>"
    kind, title, text = dialogs.seen[-1]
    assert title == tr("transform.open_stylesheet") and str(outside) in text and str(copy) in text
    expected = (TransformScenario("Index", "xslt/index_2.xsl", "publications/index.html"),)
    assert load_project(sermons_project).transformations == expected
    assert window.project.transformations == expected
    assert window.document.path == copy
    assert _declared(sermons_project) == [copy]


def test_an_outside_stylesheet_may_be_opened_in_place_or_left_alone(open_window, sermons_project, dialogs,
                                                                    tmp_path):
    outside = _outside(tmp_path)
    scenario = TransformScenario("Index", outside.as_posix(), "publications/index.html")
    window = open_window(_with_scenarios(sermons_project, scenario))
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.RejectRole)                           # Annuler
    window.transform_scenarios_dialog()
    assert window.document is window.edition_session
    assert _declared(sermons_project) == []

    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.ActionRole)                           # Ouvrir sans copier
    window.transform_scenarios_dialog()
    assert window.document.path == outside
    assert _declared(sermons_project) == [outside]
    assert load_project(sermons_project).transformations == (scenario,)
    assert not (sermons_project.parent / "xslt").exists()


def test_a_stylesheet_of_varians_is_copied_before_it_is_opened(open_window, sermons_project, dialogs):
    import xslt_scenarios
    original = TransformScenario("Édition", "${varians}/tei-to-html.xsl", "publications/edition.html",
                                 css="${varians}/tei.css")
    window = open_window(_with_scenarios(sermons_project, PERSONS, original))
    dialogs.expect("dialog", _keep_open(_open_row("project", 1)))
    dialogs.expect("box", ROLE.AcceptRole)
    window.transform_scenarios_dialog()
    copy = sermons_project.parent / "xslt" / "tei-to-html.xsl"
    assert copy.read_bytes() == (xslt_scenarios.VARIANS_STYLESHEETS / "tei-to-html.xsl").read_bytes()
    kind, title, text = dialogs.seen[-1]
    assert tr("transform.open_stylesheet.copy") and "tei-to-html.xsl" in text and str(copy) in text
    assert load_project(sermons_project).transformations == (
        PERSONS, TransformScenario("Édition", "xslt/tei-to-html.xsl", "publications/edition.html",
                                   css="${varians}/tei.css"))
    assert window.document.path == copy


def test_the_scenario_dialog_saves_the_scenario_then_opens_its_stylesheet(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))

    def edit(dialog):
        dialog.tree.setCurrentItem(dialog.project_group.child(0))
        dialog.edit_scenario()

    def change_and_open(dialog):
        change_and_open.dialog = dialog
        assert dialog.open_stylesheet_btn.text() == tr("transform.open_stylesheet")
        dialog.remove_param_row(0)
        dialog.open_stylesheet_btn.click()
        return dialog.result()

    dialogs.expect("dialog", _keep_open(edit))
    dialogs.expect("dialog", change_and_open)
    window.transform_scenarios_dialog()
    assert load_project(sermons_project).transformations == (replace(PERSONS, params=()),)
    assert window.document.path == sermons_project.parent / "rendering" / "personnes.xsl"


def test_the_scenario_dialog_does_not_open_a_refused_scenario(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, PERSONS))

    def add(dialog):
        dialog.add_scenario()
        dialog.reject()

    def refused(dialog):
        dialog.name_edit.setText("Personnes")                       # nom déjà pris
        dialog.open_stylesheet_btn.click()
        assert dialog.result() != QDialog.DialogCode.Accepted and not dialog.open_after
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", _keep_open(add))
    dialogs.expect("dialog", refused)
    dialogs.expect("warning")
    window.transform_scenarios_dialog()
    assert window.document is window.edition_session
    assert load_project(sermons_project).transformations == (PERSONS,)


# --- « Ouvrir la feuille » d'un scénario TEI (V0.9.2.2) ----------------------------------------

TEI_COPY = TransformScenario("TEI perso", "${tei}/profiles/default/html/to.xsl", "publications/tei/perso.html",
                             engine="saxon", css="${tei}/tei.css", params=(("cssFile", "tei.css"),))
IMPORT = '<xsl:import href="http://www.tei-c.org/release/xml/tei/stylesheet/profiles/default/html/to.xsl"/>'


def test_a_tei_stylesheet_opens_as_a_new_customization_stylesheet(open_window, sermons_project, dialogs):
    from xslt_scenarios import tei_library
    library = tei_library()
    official = (library.folder / "profiles" / "default" / "html" / "to.xsl").read_bytes()
    window = open_window(_with_scenarios(sermons_project, PERSONS, TEI_COPY))
    dialogs.expect("dialog", _keep_open(_open_row("project", 1)))
    dialogs.expect("box", ROLE.AcceptRole)                           # Créer la feuille de personnalisation
    window.transform_scenarios_dialog()
    target = sermons_project.parent / "xslt" / "tei-html.xsl"
    text = target.read_text(encoding="utf-8")
    assert IMPORT in text and 'xmlns="http://www.w3.org/1999/xhtml"' in text
    assert tr("transform.customization.comment", name="profiles/default/html/to.xsl").split()[0] in text
    kind, title, message = dialogs.seen[-1]
    assert title == tr("transform.open_stylesheet") and "profiles/default/html/to.xsl" in message
    assert str(target) in message and "TEI perso" in message
    # Le scénario emploie la feuille de personnalisation ; le reste ne change pas.
    expected = (PERSONS, replace(TEI_COPY, xslt="xslt/tei-html.xsl"))
    assert load_project(sermons_project).transformations == expected
    assert window.project.transformations == expected
    assert window.document.path == target
    assert _declared(sermons_project) == [target]
    assert (library.folder / "profiles" / "default" / "html" / "to.xsl").read_bytes() == official


def test_a_customization_is_not_created_on_cancel(open_window, sermons_project, dialogs):
    window = open_window(_with_scenarios(sermons_project, TEI_COPY))
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.RejectRole)                           # Annuler
    window.transform_scenarios_dialog()
    assert not (sermons_project.parent / "xslt").exists()
    assert load_project(sermons_project).transformations == (TEI_COPY,)
    assert window.document is window.edition_session


def test_an_existing_customization_is_not_replaced(open_window, sermons_project, dialogs):
    (sermons_project.parent / "xslt").mkdir()
    (sermons_project.parent / "xslt" / "tei-html.xsl").write_text("<existant/>", encoding="utf-8")
    window = open_window(_with_scenarios(sermons_project, TEI_COPY))
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.AcceptRole)
    window.transform_scenarios_dialog()
    target = sermons_project.parent / "xslt" / "tei-html_2.xsl"
    assert IMPORT in target.read_text(encoding="utf-8")
    assert (sermons_project.parent / "xslt" / "tei-html.xsl").read_text(encoding="utf-8") == "<existant/>"
    assert load_project(sermons_project).transformations == (replace(TEI_COPY, xslt="xslt/tei-html_2.xsl"),)


@pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
def test_the_customization_is_checked_with_the_tei_stylesheets(open_window, sermons_project, dialogs, qtbot):
    window = open_window(_with_scenarios(sermons_project, TEI_COPY))
    dialogs.expect("dialog", _keep_open(_open_row("project", 0)))
    dialogs.expect("box", ROLE.AcceptRole)
    window.transform_scenarios_dialog()
    window.action_validate_rng.trigger()                               # F8, hors ligne
    assert window.rng_status.text() == tr("xslt_check.status.valid", engines=tr("transform.engine.saxon"))
