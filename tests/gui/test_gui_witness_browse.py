# -*- coding: utf-8 -*-
"""Bouton « feuilleter » des viewers de manuscrits (V0.9.2.8.1) : enfoncé,
les flèches et le choix du folio parcourent le manuscrit sans déplacer le
curseur dans l'édition ; relâché, ils la mènent comme avant. L'état est
retenu pour chaque manuscrit du projet (réglage local)."""
from __future__ import annotations

import pytest

from app_context import tr
from corpus_data import add_text_pages


def _at_line(window, ordinal):
    window._show_base_ordinal(ordinal)
    window.sync_panels_to_cursor(True)


def test_each_viewer_has_the_browse_button_after_the_arrows(open_window, example_project):
    window = open_window(example_project)
    for panel in window.panels.values():
        button = panel.browse_btn
        bar = panel.layout().itemAt(1).layout()
        assert bar.indexOf(button) == bar.indexOf(panel.home_btn) + 1
        assert button.isCheckable() and not button.isChecked()
        assert not button.icon().isNull() and button.text() == ""
        assert button.toolTip() == tr("manuscript.browse.tip")


@pytest.mark.parametrize("witness", ["T2", "T1"])                 # un témoin, le pivot
def test_a_pressed_button_lets_the_arrows_browse_only(open_window, example_project, qtbot, witness):
    window = open_window(example_project)
    _at_line(window, 30)
    panel = window.panels[witness]
    position = window.editor.textCursor().position()
    panel.browse_btn.click()
    start = panel.center_index
    panel.next_btn.click()
    panel.next_btn.click()
    assert panel.center_index == start + 2
    assert window.editor.textCursor().position() == position
    qtbot.wait(200)
    window.sync_panels_to_cursor()
    assert panel.center_index == start + 2                       # le curseur n'a pas bougé
    panel.prev_btn.click()
    assert panel.center_index == start + 1
    assert window.editor.textCursor().position() == position


def test_a_released_button_lets_the_arrows_lead_again(open_window, example_project):
    window = open_window(example_project)
    _at_line(window, 30)
    t2 = window.panels["T2"]
    led = []
    t2.witnessNavigate.connect(lambda witness, step: led.append((witness, step)))
    t2.browse_btn.click()
    t2.next_btn.click()
    assert led == []
    t2.browse_btn.click()
    t2.next_btn.click()
    assert led == [("T2", 1)]


def test_a_pressed_button_lets_the_folio_list_browse_only(open_window, example_with_text):
    add_text_pages(example_with_text, y_locus=True)
    window = open_window(example_with_text)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    _at_line(window, 1)
    x = window.panels["X"]
    position = window.editor.textCursor().position()
    x.browse_btn.click()
    x.folio_combo.setCurrentIndex(next(i for i, f in enumerate(x.folios) if f.label == "13r"))
    assert str(x.current_item()["p"]["tei_surface_id"]) == "X-p0003"
    assert window.editor.textCursor().position() == position


def test_the_pressed_buttons_are_remembered_for_the_project(open_window, example_project):
    window = open_window(example_project)
    window.panels["T2"].browse_btn.click()
    again = open_window(example_project)
    assert [witness for witness, panel in again.panels.items() if panel.browse_btn.isChecked()] == ["T2"]
    again.panels["T2"].browse_btn.click()
    third = open_window(example_project)
    assert not any(panel.browse_btn.isChecked() for panel in third.panels.values())


def test_the_tooltip_follows_the_interface_language(open_window, example_project):
    from app_context import current_i18n
    window = open_window(example_project)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert window.panels["T2"].browse_btn.toolTip() == current_i18n().tr("manuscript.browse.tip")
