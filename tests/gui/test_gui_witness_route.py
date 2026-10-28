# -*- coding: utf-8 -*-
"""Les flèches de tout panneau mènent l'édition (V0.9.1.4) : le témoin est
suivi dans son propre ordre, l'édition va à la ligne du pivot que désigne sa
ligne, dans la bonne partie ou le bon texte ; les autres témoins suivent le
pivot.

- Projet exemple (un fichier ; T1 pivot, T2, P).
- Projet exemple dont RLS_185 est dans xml/rls185.xml, synchronisé à part
  (T1 et T2 y ont un JSON ; P non) : dans le manuscrit T1, RLS_185 vient
  entre la ligne 116 de l'édition (rang 115) et RLS_186 (rang 116)."""
from __future__ import annotations

import json

import pytest

from app_context import tr


@pytest.fixture
def open_window(open_window):
    """Les flèches de tous les témoins mènent l'édition : bouton au livre
    enfoncé partout (V0.9.2.8.1 ; par défaut, seul celui du pivot l'est)."""
    def _open(*args, **kwargs):
        window = open_window(*args, **kwargs)
        for panel in window.panels.values():
            panel.set_leads_edition(True)
        return window
    return _open


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _at_line(window, ordinal):
    window._show_base_ordinal(ordinal)
    window.sync_panels_to_cursor(True)


def _linked(window, item):
    ranks = [window.base_by_key[k] for k in item["l"].get("base_keys") or [] if k in window.base_by_key]
    return min(ranks) if ranks else None


def _cursor_line(window):
    return window._base_ordinal_at_cursor()


def test_the_arrows_of_a_secondary_witness_lead_the_edition(open_window, example_project, qtbot):
    window = open_window(example_project)
    _at_line(window, 30)
    t2, p = window.panels["T2"], window.panels["P"]
    # La ligne suivante de T2 désigne une autre ligne du pivot que la 31e.
    start = next(i for i in range(t2.center_index, len(t2.items) - 1)
                 if _linked(window, t2.items[i + 1]) not in (None, 30))
    t2.center_index = start
    expected = _linked(window, t2.items[start + 1])
    t2.navigate(1)
    assert t2.center_index == start + 1                     # T2 garde sa ligne
    assert _cursor_line(window) == expected == window._last_synced_ordinal
    assert p.primary_key == window.base_items[expected]["key"]   # P suit le pivot
    assert window.base_panel.center_index == expected
    # Le minuteur du curseur ne ramène pas T2 sur la ligne « reliée ».
    qtbot.wait(200)
    window.sync_panels_to_cursor()
    assert t2.center_index == start + 1


def test_an_unlinked_line_keeps_the_edition_on_the_previous_linked_line(open_window, example_project):
    path = example_project.parent / "alignments" / "T2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = [line for page in data["pages"] for line in page["lines"]]
    lines.sort(key=lambda line: int(line.get("order") or 0))
    unlinked = lines[41]
    unlinked["base_keys"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    window = open_window(example_project)
    t2 = window.panels["T2"]
    index = next(i for i, item in enumerate(t2.items) if item["l"] is not None and item["l"].get("order") == unlinked["order"])
    previous = _linked(window, t2.items[index - 1])
    _at_line(window, previous)
    t2.center_index = index - 1
    t2.navigate(1)
    assert t2.center_index == index
    assert _cursor_line(window) == previous
    assert window.statusBar().currentMessage() == tr("status.witness_unlinked", witness="T2", line=previous + 1)


def test_the_ends_of_the_manuscript(open_window, example_project):
    window = open_window(example_project)
    _at_line(window, 0)
    base = window.base_panel
    base.navigate(-1)
    assert base.center_index == 0 and _cursor_line(window) == 0
    assert window.statusBar().currentMessage() == tr("status.witness_start", witness="T1")
    _at_line(window, len(window.base_items) - 1)
    base.navigate(1)
    assert window.statusBar().currentMessage() == tr("status.witness_end", witness="T1")


def test_the_pivot_arrows_still_go_line_by_line(open_window, example_project):
    window = open_window(example_project)
    _at_line(window, 10)
    window.base_panel.navigate(1)
    assert _cursor_line(window) == 11 and window.base_panel.center_index == 11
    window.base_panel.navigate(-1)
    assert _cursor_line(window) == 10


def test_a_witness_in_lacuna_at_the_new_place_gets_its_banner(open_window, example_project):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    import re
    lbs = [m.end() for m in re.finditer(r'<lb edRef="#T1"[^>]*/>', text)]
    text = text[:lbs[40]] + '<app><lem wit="#T1 #T2"/><rdg wit="#P"><lacunaStart/></rdg></app>' + text[lbs[40]:]
    edition.write_text(text, encoding="utf-8")
    window = open_window(example_project)
    _at_line(window, 30)
    t2 = window.panels["T2"]
    while (_cursor_line(window) or 0) < 41:
        before = t2.center_index
        t2.navigate(1)
        assert t2.center_index != before
    assert window.panels["P"].lacuna_key == "manuscript.lacuna"
    assert t2.lacuna_key is None


def test_outside_the_edition_the_arrows_only_browse(open_window, project_with_documents):
    window = open_window(project_with_documents)
    _at_line(window, 30)
    window.show_document(_doc(window, "personnes.xml"))
    t2 = window.panels["T2"]
    start = t2.center_index
    t2.navigate(1)
    assert t2.center_index == start + 1
    assert window.document is _doc(window, "personnes.xml")


# --- D'un texte à l'autre -------------------------------------------------------------

def test_the_pivot_crosses_into_a_text_synchronized_apart_and_back(open_window, example_with_text):
    window = open_window(example_with_text)
    _at_line(window, 115)
    assert window.document is window.edition_session
    window.base_panel.navigate(1)
    assert window.document is _doc(window, "rls185.xml")
    assert window._last_synced_ordinal == 0 and window.base_panel.center_index == 0
    assert window.editor.textCursor().position() == window.lb_spans()[0][1]
    window._primary_panel_navigate(164)
    window.base_panel.navigate(1)
    assert window.document is window.edition_session
    assert window._last_synced_ordinal == 116
    window.base_panel.navigate(-1)
    assert window.document is _doc(window, "rls185.xml") and window._last_synced_ordinal == 164


def test_a_secondary_witness_crosses_into_the_text_in_its_own_order(open_window, example_with_text):
    window = open_window(example_with_text)
    _at_line(window, 115)
    t2 = window.panels["T2"]
    # Dernière ligne de T2 dans l'édition avant RLS_185.
    while True:
        following = t2.items[t2.center_index + 1]
        if (_linked(window, following) or 0) > 115:
            break
        t2.navigate(1)
    t2.navigate(1)
    assert window.document is _doc(window, "rls185.xml")
    assert t2.current_item()["key"] in {item["key"] for item in window.witness_display_items["T2"]}
    assert window.panels["P"].absent_key == "manuscript.text_absent"


# --- Diagnostic et ordre incertain (M.5) ----------------------------------------------

def _notes(window, dialogs):
    found = []
    dialogs.expect("dialog", lambda dialog: found.append(dialog.notes.text()) or 0)
    window.show_witness_diagnostics()
    return found[0]


def test_the_diagnostics_give_the_order_of_the_texts_in_each_manuscript(open_window, example_with_text, dialogs):
    window = open_window(example_with_text)
    notes = _notes(window, dialogs)
    # Dans T1, RLS_185 (xml/rls185.xml) est entre deux passages du fichier
    # maître de l'édition.
    runs = " → ".join((tr("diagnostics.route.edition"), "rls185", tr("diagnostics.route.edition")))
    expected = tr("diagnostics.route", witness="T1", runs=runs)
    assert expected != "diagnostics.route" and expected in notes
    # P n'est que dans l'édition : rien à dire de son ordre.
    prefix = tr("diagnostics.route", witness="P", runs="§").split("§")[0]
    assert prefix not in notes


def test_an_uncertain_place_is_said(open_window, example_with_text, dialogs):
    """Les pages de T2 dans rls185 ne se rattachent pas aux autres (ni page
    commune, ni foliotation) : rls185 garde sa place dans l'ordre de
    l'édition, et la fenêtre le dit."""
    path = example_with_text.parent / "alignments" / "rls185" / "T2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    for index, page in enumerate(data["pages"]):
        page["id"] = f"autre-{index}"
        for field in ("iiif", "image", "image_name", "label"):
            page.pop(field, None)
    path.write_text(json.dumps(data), encoding="utf-8")
    window = open_window(example_with_text)
    head, tail = tr("diagnostics.route.uncertain", witness="T2", runs="§", texts="rls185").split("§")
    line = next(line for line in _notes(window, dialogs).splitlines() if line.startswith(head))
    assert line.endswith(tail)
    _at_line(window, 115)
    t2 = window.panels["T2"]
    while (_linked(window, t2.items[t2.center_index + 1]) or 0) <= 115:
        t2.navigate(1)
    t2.navigate(1)
    assert window.document is _doc(window, "rls185.xml")
    assert window.statusBar().currentMessage() == tr("status.route_uncertain", witness="T2", text="rls185")
