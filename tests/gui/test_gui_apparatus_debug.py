# -*- coding: utf-8 -*-
"""Aide ▸ « Débugger l'apparat… » : requêtes XPath toutes prêtes lancées dans
le panneau XPath, et requêtes personnelles enregistrées dans le projet.

L'apparat du projet exemple ne cite que T1 et T2 (P n'y a jamais de leçon) :
ses 184 <app> sont donc tous « incomplets »."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from apparatus_xpath import incomplete_app_xpath, repeated_witness_xpath, witness_xpath
from app_context import tr
from project_config import XPathQuery, load_project
from project_management import update_project_xpath_queries

WITNESSES = ["T1", "T2", "P"]
SAVED = [XPathQuery("rdg vides", "//tei:rdg[not(node())]"), XPathQuery("lem", "//tei:lem")]


def _choose(setup):
    """Réponse à la fenêtre : ``setup(dialog)``, puis « Rechercher »."""
    def answer(dialog):
        setup(dialog)
        dialog.accept()
        return dialog.result()
    return answer


def _query_dialog(name, expression):
    def answer(dialog):
        dialog.name_edit.setText(name)
        dialog.expression_edit.setText(expression)
        dialog.accept()
        return dialog.result()
    return answer


def _close(dialog):
    dialog.reject()
    return dialog.result()


def test_the_command_opens_the_help_menu(open_window, example_project):
    # Débugger en tête, puis les outils externes ; l'aide du logiciel reste
    # en bas, juste au-dessus de « À propos ».
    window = open_window(example_project)
    separator = object()
    assert [separator if action.isSeparator() else action for action in window.help_menu.actions()] == [
        window.action_debug_apparatus, separator,
        window.action_enigma, window.action_latin_dictionary, separator,
        window.action_software_help, window.action_about]
    assert window.action_debug_apparatus.text() == tr("apparatus.menu")


def test_repeated_witness_check_runs_in_the_xpath_panel(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = {}

    def setup(dialog):
        seen["witnesses"] = dialog.witnesses_label.text()
        dialog.repeated_radio.setChecked(True)

    dialogs.expect("dialog", _choose(setup))
    assert window.debug_apparatus()
    assert seen["witnesses"] == tr("apparatus.witnesses", ids="T1, T2, P")
    assert window.xpath_query.text() == repeated_witness_xpath(WITNESSES)
    assert not window.xpath_panel.isHidden()
    assert window.xpath_table.rowCount() == 0
    assert window.xpath_summary.text() == tr("xpath.none")


def test_incomplete_check_lists_the_apps_and_a_click_selects_one(open_window, example_project, dialogs):
    window = open_window(example_project)
    dialogs.expect("dialog", _choose(lambda dialog: dialog.incomplete_radio.setChecked(True)))
    assert window.debug_apparatus()
    assert window.xpath_query.text() == incomplete_app_xpath(WITNESSES)
    assert window.xpath_table.rowCount() == 184
    window.goto_xpath_result(0)
    assert window.editor.textCursor().selectedText().startswith("<app>")


def test_a_witness_in_lacuna_is_not_expected_in_its_apps(open_window, example_project, dialogs):
    """V0.9.1.3 : P, en lacune dans le sermon RLS_184, n'y est plus attendu ;
    les <app> de ce sermon ne sont plus incomplets."""
    import re
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    sermon = text[text.index('<div xml:id="RLS_184">'):text.index('<div xml:id="RLS_185">')]
    edition.write_text(text.replace('<div xml:id="RLS_184">', '<lacunaStart wit="#P"/><div xml:id="RLS_184">', 1)
                       .replace('<div xml:id="RLS_185">', '<lacunaEnd wit="#P"/><div xml:id="RLS_185">', 1),
                       encoding="utf-8")
    window = open_window(example_project)
    dialogs.expect("dialog", _choose(lambda dialog: dialog.incomplete_radio.setChecked(True)))
    assert window.debug_apparatus()
    assert window.xpath_query.text() == incomplete_app_xpath(WITNESSES, ["P"])
    assert window.xpath_table.rowCount() == 184 - len(re.findall(r"<app\b", sermon))


def test_witness_check_uses_the_chosen_witness_and_options(open_window, example_project, dialogs):
    window = open_window(example_project)
    seen = {}

    def setup(dialog):
        seen["ids"] = [dialog.witness_combo.itemText(i) for i in range(dialog.witness_combo.count())]
        dialog.witness_radio.setChecked(True)
        dialog.witness_combo.setCurrentText("T1")
        dialog.presence_combo.setCurrentIndex(1)                       # n'apparaît pas
        dialog.scope_combo.setCurrentIndex(0)                          # dans <lem> ou <rdg>

    dialogs.expect("dialog", _choose(setup))
    assert window.debug_apparatus()
    assert seen["ids"] == WITNESSES
    assert window.xpath_query.text() == witness_xpath("T1", present=False, rdg_only=False)
    assert window.xpath_table.rowCount() == 1

    def rdg_only(dialog):
        dialog.witness_radio.setChecked(True)
        dialog.witness_combo.setCurrentText("P")
        dialog.presence_combo.setCurrentIndex(0)                       # apparaît
        dialog.scope_combo.setCurrentIndex(1)                          # dans <rdg> seulement

    dialogs.expect("dialog", _choose(rdg_only))
    assert window.debug_apparatus()
    assert window.xpath_query.text() == witness_xpath("P", present=True, rdg_only=True)
    assert window.xpath_table.rowCount() == 0


def test_closing_the_window_runs_nothing(open_window, example_project, dialogs):
    window = open_window(example_project)
    dialogs.expect("dialog", _close)
    assert not window.debug_apparatus()
    assert window.xpath_query.text() == ""
    assert window.xpath_panel.isHidden()


def test_checks_are_unavailable_without_a_list_wit(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    window.show_document(window.documents[1])                          # personnes.xml
    seen = {}

    def look(dialog):
        seen.update(label=dialog.witnesses_label.text(),
                    checks=[dialog.repeated_radio.isEnabled(), dialog.incomplete_radio.isEnabled(),
                            dialog.witness_radio.isEnabled()],
                    queries=dialog.query_radio.isEnabled(), search=dialog.search_btn.isEnabled())
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", look)
    window.debug_apparatus()
    assert seen == {"label": tr("apparatus.no_witness"), "checks": [False, False, False],
                    "queries": True, "search": False}


def test_a_saved_query_is_written_to_the_project_and_found_after_reopening(
        open_window, example_project, dialogs):
    window = open_window(example_project)
    window.xpath_query.setText("//tei:rdg[not(node())]")
    proposed = {}

    def add(dialog):
        dialog.add_btn.click()
        proposed["items"] = [dialog.queries_list.item(i).text() for i in range(dialog.queries_list.count())]
        dialog.query_radio.setChecked(True)
        dialog.queries_list.setCurrentRow(0)

    def new_query(dialog):
        proposed["expression"] = dialog.expression_edit.text()
        return _query_dialog("rdg vides", dialog.expression_edit.text())(dialog)

    dialogs.expect("dialog", _choose(add))
    dialogs.expect("dialog", new_query)
    assert window.debug_apparatus()
    assert proposed == {"expression": "//tei:rdg[not(node())]", "items": ["rdg vides"]}
    assert load_project(example_project).xpath_queries == (XPathQuery("rdg vides", "//tei:rdg[not(node())]"),)
    assert window.xpath_table.rowCount() == 60                         # 32 + 28 <rdg/> vides

    reopened = open_window(example_project)
    listed = []
    dialogs.expect("dialog", lambda dialog: listed.extend(
        dialog.queries_list.item(i).text() for i in range(dialog.queries_list.count())) or _close(dialog))
    reopened.debug_apparatus()
    assert listed == ["rdg vides"]


def test_edit_and_remove_saved_queries(open_window, example_project, dialogs):
    update_project_xpath_queries(example_project, SAVED)
    window = open_window(example_project)

    def edit_then_remove(dialog):
        dialog.queries_list.setCurrentRow(0)
        dialog.edit_btn.click()
        dialog.queries_list.setCurrentRow(1)
        dialog.remove_btn.click()
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", edit_then_remove)
    dialogs.expect("dialog", _query_dialog("rdg sans texte", "//tei:rdg[not(text())]"))
    dialogs.expect("question", QMessageBox.StandardButton.Yes)          # supprimer « lem » ?
    window.debug_apparatus()
    assert load_project(example_project).xpath_queries == (XPathQuery("rdg sans texte", "//tei:rdg[not(text())]"),)
    assert window.project.xpath_queries == load_project(example_project).xpath_queries


@pytest.mark.parametrize("name, expression", [("cassée", "//tei:app["), ("lem", "//tei:rdg")])
def test_an_invalid_or_duplicate_query_is_refused(open_window, example_project, dialogs, name, expression):
    update_project_xpath_queries(example_project, SAVED)
    window = open_window(example_project)
    before = example_project.read_bytes()

    def add(dialog):
        dialog.add_btn.click()
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", add)
    dialogs.expect("dialog", _query_dialog(name, expression))
    dialogs.expect("warning")
    window.debug_apparatus()
    assert example_project.read_bytes() == before


def test_the_command_follows_the_interface_language(open_window, example_project):
    window = open_window(example_project)
    window._set_language_code("en")
    try:
        assert window.action_debug_apparatus.text() == tr("apparatus.menu") == "Debug the apparatus…"
    finally:
        window._set_language_code("fr")
