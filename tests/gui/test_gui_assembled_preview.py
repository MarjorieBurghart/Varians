# -*- coding: utf-8 -*-
"""La Vue XSLT / CSS d'une édition assemblée (V0.9.1.5) : comme pour un
document unique, ses paragraphes ont leur ✎ et ses lignes leurs repères ; un
clic mène le curseur dans le bon fichier, et les témoins suivent. L'aperçu
reste disponible, et affiché, quand une partie est affichée.

- Jeu « sermons » (tests/data/sermons) : quatre sermons inclus, l'exemplum
  inclus par s04.
- Projet exemple dont RLS_185 (xml/rls185.xml) est synchronisé à part."""
from __future__ import annotations

from pathlib import Path


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _preview(window):
    view = window.formatted_view
    window.left_tabs.setCurrentIndex(window.left_tabs.indexOf(view))
    view.refresh_preview(force=True)
    return view


def _preview_shown(window):
    return window.left_tabs.currentWidget() is window.formatted_view


def test_the_assembled_preview_has_its_pencils_and_line_markers(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)
    html = view.preview.toHtml()
    # Le <head> et les <p> de chaque sermon (V0.9.2.9).
    assert html.count("tei-edit://p/") == len(view.sources.paragraphs) == 16
    assert len(view.preview._marker_lines) == len(view.sources.lines) == 27


def test_the_preview_stays_available_and_shown_with_a_part(open_window, sermons_project):
    window = open_window(sermons_project)
    window.show_document(_doc(window, "s02.xml"))
    index = window.left_tabs.indexOf(window.formatted_view)
    assert window.left_tabs.isTabEnabled(index) and window.action_preview.isEnabled()
    view = _preview(window)
    assert "Sermo in adventu Domini" in view.preview.toPlainText()        # toute l'édition
    window.show_document(_doc(window, "s03.xml"))
    assert _preview_shown(window)
    window.show_document(window.edition_session)
    assert _preview_shown(window)


def test_a_click_on_a_line_leads_the_cursor_into_its_file(open_window, sermons_project):
    window = open_window(sermons_project)
    view = _preview(window)
    index = next(i for i, (path, _end) in enumerate(view.sources.lines) if Path(path).name == "s03.xml") + 2
    path, end = view.sources.lines[index]
    view._line_clicked(index)
    assert window.document is _doc(window, "s03.xml")
    assert window.editor.textCursor().position() == end
    assert _preview_shown(window)


def test_a_click_in_a_text_synchronized_apart_syncs_its_witnesses(open_window, example_with_text):
    window = open_window(example_with_text)
    view = _preview(window)
    index = next(i for i, (path, _end) in enumerate(view.sources.lines) if Path(path).name == "rls185.xml") + 10
    view._line_clicked(index)
    assert window.document is _doc(window, "rls185.xml")
    assert window._active_segment is not None
    assert window._last_synced_ordinal == 10                    # numérotation propre au texte
    assert _preview_shown(window)
    # Un repère de l'édition, après le texte : retour dans sa numérotation.
    after = next(i for i, (path, _end) in enumerate(view.sources.lines)
                 if i > index and Path(path).name == "edition.xml")
    view._line_clicked(after)
    assert window.document is window.edition_session and window._active_segment is None
    assert window._last_synced_ordinal == 116


def test_an_auxiliary_document_still_leaves_the_preview(open_window, project_with_documents):
    window = open_window(project_with_documents)
    _preview(window)
    window.show_document(_doc(window, "personnes.xml"))
    assert not _preview_shown(window)
