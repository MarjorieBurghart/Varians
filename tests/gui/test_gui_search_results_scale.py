# -*- coding: utf-8 -*-
"""Red team 2 (robustesse, A1) : le panneau des résultats déjà ouvert se
remplit de nouveau à chaque pause de frappe, option cochée ou document
affiché. Ses colonnes « à la taille du contenu » se recalculaient à chaque
cellule posée : 1 000 résultats figeaient la fenêtre 16 s à chaque frappe.
Remplir le panneau ouvert doit coûter à peu près autant que le remplir
fermé."""
from __future__ import annotations

import time

import search_results


def test_refreshing_an_open_results_panel_is_as_fast_as_the_first_listing(open_window, example_project,
                                                                         monkeypatch, qtbot):
    monkeypatch.setattr(search_results, "MAX_RESULTS", 800)
    window = open_window(example_project)
    window.find_box.setText("et")
    started = time.perf_counter()
    window.list_search_results()
    first = time.perf_counter() - started
    assert window.search_results_panel.isVisible() and window.search_results_table.rowCount() == 800
    qtbot.wait(300)                                    # le panneau est dessiné
    started = time.perf_counter()
    window.refresh_search_results()
    again = time.perf_counter() - started
    assert window.search_results_table.rowCount() == 800
    assert again < max(2.0, 10 * first), (first, again)
    # Les colonnes gardent la taille de leur contenu.
    table = window.search_results_table
    assert table.columnWidth(1) >= table.horizontalHeader().sectionSizeHint(1) - 1
