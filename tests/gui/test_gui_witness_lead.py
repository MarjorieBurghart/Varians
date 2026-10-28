# -*- coding: utf-8 -*-
"""Bouton au livre des viewers de manuscrits (V0.9.2.8.1) : enfoncé, les
flèches et le choix du folio de ce manuscrit mènent l'édition ; relâché,
ils ne font que feuilleter le manuscrit. Par défaut, seul le bouton du
pivot est enfoncé ; l'état de chaque manuscrit est retenu pour le projet
(réglage local)."""
from __future__ import annotations

from app_context import tr
from corpus_data import add_text_pages


def _at_line(window, ordinal):
    window._show_base_ordinal(ordinal)
    window.sync_panels_to_cursor(True)


def _recorder(panel):
    led = []
    panel.witnessNavigate.connect(lambda witness, step: led.append((witness, step)))
    return led


def test_each_viewer_has_the_button_after_the_arrows_pressed_for_the_pivot(open_window, example_project):
    window = open_window(example_project)
    for witness, panel in window.panels.items():
        button = panel.lead_btn
        bar = panel.layout().itemAt(1).layout()
        assert bar.indexOf(button) == bar.indexOf(panel.home_btn) + 1
        assert button.isCheckable() and not button.icon().isNull() and button.text() == ""
        assert button.toolTip() == tr("manuscript.lead.tip")
        assert button.isChecked() == (witness == window.base_id) == panel.leads_edition
    # Enfoncé : un style discret (bleu-gris), plus l'orange d'une alerte.
    assert "#dfe8f2" in window.panels["T2"].lead_btn.styleSheet()


def test_a_released_button_lets_the_arrows_browse_only(open_window, example_project, qtbot):
    window = open_window(example_project)
    _at_line(window, 30)
    t2 = window.panels["T2"]
    led = _recorder(t2)
    position = window.editor.textCursor().position()
    start = t2.center_index
    t2.next_btn.click()
    t2.next_btn.click()
    assert t2.center_index == start + 2 and led == []
    assert window.editor.textCursor().position() == position
    qtbot.wait(200)
    window.sync_panels_to_cursor()
    assert t2.center_index == start + 2                          # le curseur n'a pas bougé
    t2.prev_btn.click()
    assert t2.center_index == start + 1 and window.editor.textCursor().position() == position


def test_a_pressed_button_lets_the_arrows_lead(open_window, example_project):
    window = open_window(example_project)
    _at_line(window, 30)
    pivot, t2 = window.base_panel, window.panels["T2"]
    led_pivot, led_t2 = _recorder(pivot), _recorder(t2)
    pivot.next_btn.click()
    assert led_pivot == [(window.base_id, 1)]
    t2.lead_btn.click()
    t2.next_btn.click()
    assert led_t2 == [("T2", 1)]
    # Le pivot relâché ne fait plus que feuilleter.
    pivot.lead_btn.click()
    pivot.next_btn.click()
    assert led_pivot == [(window.base_id, 1)]


def test_the_folio_list_leads_only_when_the_button_is_pressed(open_window, example_with_text):
    add_text_pages(example_with_text, y_locus=True)
    window = open_window(example_with_text)
    window.show_document(next(s for s in window.documents if s.path.name == "rls185.xml"))
    _at_line(window, 1)
    x = window.panels["X"]
    position = window.editor.textCursor().position()
    x.folio_combo.setCurrentIndex(next(i for i, f in enumerate(x.folios) if f.label == "13r"))
    assert str(x.current_item()["p"]["tei_surface_id"]) == "X-p0003"
    assert window.editor.textCursor().position() == position
    led = _recorder(x)
    x.lead_btn.click()
    x.folio_combo.setCurrentIndex(next(i for i, f in enumerate(x.folios) if f.label == "12v"))
    assert led == [("X", 0)]


def test_the_buttons_are_remembered_for_the_project(open_window, example_project):
    window = open_window(example_project)
    window.panels["T2"].lead_btn.click()
    window.base_panel.lead_btn.click()
    again = open_window(example_project)
    assert {witness for witness, panel in again.panels.items() if panel.leads_edition} == {"T2"}
    again.panels["T2"].lead_btn.click()
    again.base_panel.lead_btn.click()
    third = open_window(example_project)
    assert {witness for witness, panel in third.panels.items() if panel.leads_edition} == {third.base_id}


def test_the_tooltip_follows_the_interface_language(open_window, example_project):
    from app_context import current_i18n
    window = open_window(example_project)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert window.panels["T2"].lead_btn.toolTip() == current_i18n().tr("manuscript.lead.tip")
