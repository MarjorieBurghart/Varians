# -*- coding: utf-8 -*-
"""Rangée d'onglets des documents, au-dessus de la source et de l'aperçu."""
from __future__ import annotations

from PySide6.QtGui import QColor

from app_context import tr


def _aux(window):
    (aux,) = window.documents[1:]
    return aux


def _type_at_end(window, text):
    cursor = window.editor.textCursor()
    cursor.setPosition(len(window.editor.toPlainText()))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def test_simple_project_shows_no_document_tabs(open_window, example_project):
    window = open_window(example_project)
    assert window.document_tab_bar.isHidden()
    assert window.document_tab_bar.count() == 1


def test_tabs_list_the_edition_then_the_auxiliary_documents(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    assert not bar.isHidden()
    # Au-dessus des vues, dans sa rangée avec la flèche ▾ (V0.9.2.8).
    assert bar.parentWidget() is window.document_tab_row
    assert window.document_tab_row.parentWidget() is window.left_tabs.parentWidget()
    assert [bar.tabText(i) for i in range(bar.count())] == [tr("documents.edition_tab"), "Personnes"]
    assert str(window.edition_session.path) in bar.tabToolTip(0)
    assert str(_aux(window).path) in bar.tabToolTip(1)
    assert bar.currentIndex() == 0


def test_choosing_a_tab_shows_its_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    bar.setCurrentIndex(1)
    assert window.document is _aux(window)
    bar.setCurrentIndex(0)
    assert window.document is window.edition_session


def test_current_tab_follows_the_displayed_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window.show_document(_aux(window))
    assert window.document_tab_bar.currentIndex() == 1


def test_refused_switch_keeps_the_current_tab(open_window, project_with_documents, dialogs):
    window = open_window(project_with_documents)
    _aux(window).path.unlink()
    dialogs.expect("critical")
    window.document_tab_bar.setCurrentIndex(1)
    assert window.document_tab_bar.currentIndex() == 0
    assert window.document is window.edition_session


def test_modified_documents_are_marked(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    _type_at_end(window, " ")
    assert bar.tabText(0) == tr("documents.edition_tab") + " *"

    window.show_document(_aux(window))
    _type_at_end(window, " ")
    assert bar.tabText(1) == "Personnes *"
    assert bar.tabText(0) == tr("documents.edition_tab") + " *"
    assert window.save()
    assert bar.tabText(1) == "Personnes"


def test_tab_colour_follows_the_health_of_each_document(open_window, project_with_documents):
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    normal = bar.tabTextColor(0)
    window.show_document(_aux(window))
    _type_at_end(window, "<")
    window.validate_text(False)
    assert bar.tabTextColor(1) == QColor("#a13d32")
    assert tr("xml.health.malformed.tooltip") in bar.tabToolTip(1)

    window.show_document(window.edition_session)
    assert bar.tabTextColor(1) == QColor("#a13d32")              # propre au document
    assert bar.tabTextColor(0) == normal


# --- Onglet courant bien distinct (V0.9.1.6) ------------------------------------------

def _tab_colours(bar, index):
    """Couleurs des pixels de l'onglet ``index`` tel qu'il est dessiné."""
    image = bar.grab().toImage()
    rect = bar.tabRect(index)
    return [QColor(image.pixel(x, y)) for x in range(rect.left(), rect.right()) for y in range(rect.top(), rect.bottom())]


def _has_red_text(colours):
    return any(c.red() - max(c.green(), c.blue()) > 60 for c in colours)


def test_the_current_tab_stands_out(open_window, project_with_documents):
    from document_tabs import CURRENT_TAB_ACCENT
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    window.show_document(_aux(window))
    current = {c.name() for c in _tab_colours(bar, 1)}
    other = {c.name() for c in _tab_colours(bar, 0)}
    # Fond blanc et filet de couleur en haut pour l'onglet courant seulement.
    assert CURRENT_TAB_ACCENT in current and CURRENT_TAB_ACCENT not in other
    assert "#ffffff" in current and "#ffffff" not in other
    window.show_document(window.edition_session)
    assert CURRENT_TAB_ACCENT in {c.name() for c in _tab_colours(bar, 0)}


def test_the_name_of_the_current_tab_is_bold_and_whole(open_window, project_with_documents):
    from PySide6.QtGui import QFont, QFontMetrics
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    bold = QFont(bar.font())
    bold.setBold(True)
    for index in range(bar.count()):
        assert QFontMetrics(bold).horizontalAdvance(bar.tabText(index)) < bar.tabRect(index).width(), index


def test_the_health_colour_shows_on_the_current_tab_too(open_window, project_with_documents):
    # La couleur et la graisse du nom sont lues sur l'onglet (label_colour,
    # label_font) ; les pixels ne servent qu'à voir le rouge dessiné : le
    # lissage sous-pixel de Linux borde de couleurs un texte noir.
    window = open_window(project_with_documents)
    bar = window.document_tab_bar
    red = QColor("#a13d32")
    window.show_document(_aux(window))
    _type_at_end(window, "<")
    window.validate_text(False)
    assert bar.label_colour(1) == red and bar.label_font(1).bold()          # onglet courant
    assert _has_red_text(_tab_colours(bar, 1))
    window.show_document(window.edition_session)
    assert bar.label_colour(1) == red and not bar.label_font(1).bold()      # autre onglet
    assert _has_red_text(_tab_colours(bar, 1))
    assert bar.label_colour(0) != red and bar.label_font(0).bold()
