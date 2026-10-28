# -*- coding: utf-8 -*-
"""Le sigle d'un témoin à l'écran (V0.9.2.8.2).

Partout où Varians nommait un témoin par son identifiant, il le nomme par
son sigle (``siglum`` de project.xml, sinon l'identifiant) : témoin
détaché, menus et listes de témoins, barre d'état, structure, diagnostic,
paramètre ``temoin-de-base`` d'un scénario, « Débugger l'apparat ». Le
XML, lui, garde les identifiants.

Projet exemple, avec les sigles « T 1 » (pivot T1) et « P 15940 » (P) ;
T2 n'a pas de sigle à part."""
from __future__ import annotations

import pytest


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


@pytest.fixture
def siglum_project(example_project):
    text = example_project.read_text(encoding="utf-8")
    for old, new in (('<witness id="T1" ', '<witness id="T1" siglum="T 1" '),
                     ('<witness id="P" ', '<witness id="P" siglum="P 15940" ')):
        assert old in text
        text = text.replace(old, new)
    example_project.write_text(text, encoding="utf-8")
    return example_project


def test_the_window_names_witnesses_by_their_siglum(open_window, siglum_project):
    window = open_window(siglum_project)
    assert [window.witness_siglum(wid) for wid in ("T1", "T2", "P", "X")] == ["T 1", "T2", "P 15940", "X"]
    assert "T 1" in window.structure_status.text() and "T1" not in window.structure_status.text()


def test_the_status_bar_names_witnesses_by_their_siglum(open_window, siglum_project):
    window = open_window(siglum_project)
    window._show_base_line_status(4, set())
    assert window.statusBar().currentMessage() == _tr(
        "status.base_line", base="T 1", line=5, total=len(window.base_items))
    window._show_base_line_status(4, {"T1"})
    assert window.statusBar().currentMessage() == _tr("status.base_lacuna", base="T 1")
    window._show_witness_end("P", 1)
    assert window.statusBar().currentMessage() == _tr("status.witness_end", witness="P 15940")


def test_the_detached_witness_shows_its_siglum(open_window, siglum_project):
    window = open_window(siglum_project)
    texts = [action.text() for action in window.detach_witness_menu.actions()]
    assert "P 15940 — P · Paris, BnF, Latin 15940" in texts and "T2 — T2 · Troyes 1760" in texts
    window._toggle_detached_witness("P")
    assert window._detached_windows["P"].windowTitle() == _tr("workspace.detached.title", witness="P 15940")
    window._toggle_detached_witness("P")


def test_the_witness_choice_lists_the_sigla(open_window, siglum_project, dialogs):
    window = open_window(siglum_project)
    seen = []

    def look(dialog):
        seen.extend(dialog.list.item(row).text() for row in range(dialog.list.count()))
        return 0

    dialogs.expect("dialog", look)
    window.choose_visible_witnesses()
    assert seen == ["T 1 — T1 · Troyes 816", "T2 — T2 · Troyes 1760", "P 15940 — P · Paris, BnF, Latin 15940"]


def test_the_diagnostics_show_the_sigla(open_window, siglum_project, dialogs):
    window = open_window(siglum_project)
    seen = {}

    def look(dialog):
        seen["cells"] = [dialog.table.item(row, 0).text() for row in range(dialog.table.rowCount())]
        return 0

    dialogs.expect("dialog", look)
    window.show_witness_diagnostics()
    assert seen["cells"] == ["T 1 — T1 · Troyes 816", "T2 — T2 · Troyes 1760",
                             "P 15940 — P · Paris, BnF, Latin 15940"]
    assert window._diagnostic_scope() == _tr("diagnostics.scope.edition", base="T 1")


def test_the_apparatus_window_shows_the_sigla_and_queries_the_identifiers(open_window, siglum_project, dialogs):
    window = open_window(siglum_project)
    seen = {}

    def look(dialog):
        combo = dialog.witness_combo
        seen["items"] = [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]
        seen["label"] = dialog.witnesses_label.text()
        dialog.witness_radio.setChecked(True)
        combo.setCurrentIndex(combo.findData("P"))
        seen["expression"] = dialog.selected_expression()
        return 0

    dialogs.expect("dialog", look)
    window.debug_apparatus()
    assert seen["items"] == [("T 1", "T1"), ("T2", "T2"), ("P 15940", "P")]
    assert "T 1, T2, P 15940" in seen["label"]
    assert "#P" in seen["expression"] and "15940" not in seen["expression"]


def test_the_witness_parameter_lists_the_sigla_and_keeps_the_identifiers(open_window, siglum_project, dialogs):
    from PySide6.QtWidgets import QMessageBox
    from project_config import TransformScenario, load_project
    from test_gui_transform_scenarios import _in_list, _scenario, _with_scenarios
    from xslt_scenarios import saxon_available
    critique = TransformScenario("Critique", "${varians}/edition-critique.xsl", "publications/critique.html",
                                 engine="saxon", params=(("temoin-de-base", "${pivot}"),))
    window = open_window(_with_scenarios(siglum_project, critique))
    seen = {}

    def edit(dialog):
        dialog.tree.setCurrentItem(dialog.project_group.child(0))
        dialog.edit_scenario()

    def choose(dialog):
        combo = dialog.params_table.cellWidget(0, 1)
        seen["items"] = [(combo.itemText(i), combo.itemData(i)) for i in range(combo.count())]
        combo.setCurrentIndex(combo.findData("P"))

    dialogs.expect("dialog", _in_list(edit))
    dialogs.expect("dialog", _scenario(choose))
    if not saxon_available():
        dialogs.expect("question", QMessageBox.StandardButton.Yes)
    window.transform_scenarios_dialog()
    assert seen["items"] == [(_tr("transform.param.pivot", witness="T 1"), "${pivot}"), ("T2", "T2"),
                             ("P 15940", "P"), (_tr("transform.param.no_witness"), "aucun")]
    assert load_project(siglum_project).transformations[0].params == (("temoin-de-base", "P"),)
