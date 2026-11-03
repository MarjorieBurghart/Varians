# -*- coding: utf-8 -*-
"""Red team 2 (robustesse, B4 ; cohérence, D3) : numérotation des lignes du
pivot dans une édition en parties.

- B4 : la numérotation gardée pendant la frappe ne l'était plus à bon
  droit quand un xi:include changeait de cible (même nombre d'inclusions),
  qu'une lacune ou un <pb> était ajouté, ou qu'un <pb> changeait de place :
  la barre d'état, les lacunes et les pages des parties suivantes restaient
  celles d'avant, même après un changement d'onglet.
- D3 : dans l'édition, après un texte synchronisé à part, le bureau prenait
  les <pb> de ce texte pour un témoin suivi par pages ; le viewer web ne
  suit que les <pb> du texte affiché, comme les lacunes sur le bureau."""
from __future__ import annotations

from pivot_lines import include_spans, pivot_lb_pattern, pivot_lines


def _fresh(window):
    """La numérotation recalculée de zéro sur les textes affichés."""
    sessions = [s for s in window.documents if s.in_edition]
    texts = {s.path: s.text_document.toPlainText() for s in sessions
             if not s.is_edition and s.text_document is not None}
    base = window.project.base_witness
    return pivot_lines(window.edition_session.text_document.toPlainText(), window.edition_session.path,
                       texts, base, pivot_lb_pattern(base), text_bases=window._text_bases())


def _replace(window, old, new):
    text = window.editor.toPlainText()
    position = text.index(old)
    qt = window.editor.positions(text)
    cursor = window.editor.textCursor()
    cursor.setPosition(qt.qt(position))
    cursor.setPosition(qt.qt(position + len(old)), cursor.MoveMode.KeepAnchor)
    window.editor.setTextCursor(cursor)
    window.editor.textCursor().insertText(new)


def _cursor(window, position):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.positions().qt(position))
    window.editor.setTextCursor(cursor)


def _session(window, name):
    return next(s for s in window.documents if s.path is not None and s.path.name == name)


def test_a_changed_include_target_renumbers_the_lines(open_window, corpus_project, qtbot):
    window = open_window(corpus_project)
    assert window.document.is_edition
    before = window._base_line_count()
    _replace(window, 'href="sermons/s01.xml"', 'href="sermons/s0l.xml"')      # partie absente
    qtbot.wait(50)
    window.sync_panels_to_cursor(True)
    fresh = _fresh(window)
    assert fresh.count != before and window._base_line_count() == fresh.count
    s03 = _session(window, "s03.xml")
    window.show_document(s03)
    position = window.lb_spans()[0][1]
    text = window.editor.toPlainText()
    assert window._base_ordinal_at(position) == _fresh(window).ordinal_at(
        s03.path, position, window.lb_spans(), include_spans(text))


def test_a_lacuna_added_in_a_part_is_seen_in_the_next_one(open_window, corpus_project, qtbot):
    window = open_window(corpus_project)
    window.show_document(_session(window, "s01.xml"))
    window.sync_panels_to_cursor(True)
    text = window.editor.toPlainText()
    _cursor(window, text.rindex("</p>"))
    window.editor.textCursor().insertText('<app><lem wit="#A"/><rdg wit="#C"><lacunaStart/></rdg></app>')
    qtbot.wait(50)
    window.sync_panels_to_cursor(True)
    s03 = _session(window, "s03.xml")
    window.show_document(s03)
    text = window.editor.toPlainText()
    position = window.lb_spans()[0][1]
    _cursor(window, position)
    window.sync_panels_to_cursor(True)
    fresh = _fresh(window).lacunae_at(s03.path, position, text, include_spans(text))
    assert "C" in fresh and sorted(window._lacunae_at_cursor()) == sorted(fresh)


def test_after_a_text_synchronised_apart_a_page_witness_follows_the_edition_pbs(open_window, example_with_text,
                                                                               qtbot):
    from corpus_data import add_text_pages
    add_text_pages(example_with_text, y_locus=True)
    window = open_window(example_with_text)
    assert window.document.is_edition
    text = window.editor.toPlainText()
    # Après l'inclusion de rls185 (où X a ses <pb> 12v et 13r).
    include_end = include_spans(text)[0][1]
    position = next(end for _start, end in window.lb_spans() if end > include_end)
    panel = window.panels["X"]
    lines = window._pivot_lines()
    # Aucun <pb> de X dans l'édition elle-même.
    assert lines.page_at(window.document.path, position, text, include_spans(text), "X", panel.folios) is None
    # Dans le texte à part, puis de nouveau dans l'édition : X revient à sa
    # page de départ dans l'édition (le viewer web garde un état par texte).
    rls185 = next(s for s in window.documents if s.path is not None and s.path.name == "rls185.xml")
    window.show_document(rls185)
    _cursor(window, window.lb_spans()[-1][1])
    window.sync_panels_to_cursor(True)
    assert _label(panel) == "13r"
    window.show_document(window.edition_session)
    _cursor(window, position)
    window.sync_panels_to_cursor(True)
    assert _label(panel) == "12r"


def _label(panel):
    surface = panel.current_item()["p"].get("tei_surface_id")
    return next(folio.label for folio in panel.folios if folio.ref == surface or folio.surface == surface)
