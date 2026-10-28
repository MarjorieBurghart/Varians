# -*- coding: utf-8 -*-
"""Panneau des résultats de la recherche XML (V0.9.2.8) : « Tout lister »
(bouton près du champ de recherche, Rechercher ▸ Lister toutes les
occurrences, Ctrl+Maj+L) liste chaque occurrence avec sa ligne et son
contexte (KWIC) ; le document affiché, ou tout le projet ; un clic mène à
l'occurrence ; le panneau suit les recherches suivantes."""
from __future__ import annotations

TEXT = "alpha beta\n<rdg>beta</rdg>\nBeta gamma"
# Colonnes : Document, Ligne, Avant, Résultat, Après.
DOCUMENT, LINE, BEFORE, MATCH, AFTER = range(5)


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _rows(window):
    table = window.search_results_table
    return [tuple(table.item(row, column).text() for column in range(5)) for row in range(table.rowCount())]


def _list(window, query):
    window.find_box.setText(query)
    window.action_search_list.trigger()


def test_list_all_shows_each_occurrence_in_context(open_window, example_project):
    window = open_window(example_project)
    assert window.action_search_list.shortcut().toString() == "Ctrl+Shift+L"
    assert window.main_toolbar.widgetForAction(window.action_search_list).text() == _tr("search.list")
    entries = [action for action in window.search_menu.actions() if not action.isSeparator()]
    assert entries.index(window.action_search_list) == entries.index(window.action_find_next) + 1
    window.editor.setPlainText(TEXT)
    assert not window.search_results_panel.isVisible()
    _list(window, "beta")
    assert window.search_results_panel.isVisible()
    assert [row[LINE:] for row in _rows(window)] == [
        ("1", "alpha ", "beta", " <rdg>beta</rdg> Beta gamma"),
        ("2", "alpha beta <rdg>", "beta", "</rdg> Beta gamma"),
        ("3", "alpha beta <rdg>beta</rdg> ", "Beta", " gamma"),
    ]
    # Le document affiché : pas de colonne Document.
    assert window.search_results_table.isColumnHidden(DOCUMENT)
    assert window.search_results_summary.text() == _tr("results.summary", count=3, query="beta")


def test_a_click_goes_to_the_occurrence(open_window, example_project):
    window = open_window(example_project)
    window.editor.setPlainText(TEXT)
    _list(window, "beta")
    window.search_results_table.cellClicked.emit(2, MATCH)
    start = TEXT.index("Beta")
    assert window.editor._search_match == (start, start + 4)
    assert window.editor.textCursor().position() == start + 4 and not window.editor.textCursor().hasSelection()


def test_the_panel_follows_the_search_the_options_and_the_text(open_window, example_project, qtbot):
    window = open_window(example_project)
    window.editor.setPlainText(TEXT)
    _list(window, "beta")
    window.action_search_case.trigger()                    # respecter la casse
    assert len(_rows(window)) == 2
    window.action_search_case.trigger()
    window.find_box.setText("gamma")
    window.find_source_next()                              # une nouvelle recherche
    assert [row[MATCH] for row in _rows(window)] == ["gamma"]
    cursor = window.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText("\ngamma")
    qtbot.waitUntil(lambda: len(_rows(window)) == 2, timeout=3000)
    window.action_search_regex.trigger()
    window.find_box.setText("a(b")
    window.action_search_list.trigger()
    assert _rows(window) == []
    assert window.search_results_summary.text().startswith(_tr("search.error.pattern", detail=""))
    window.search_results_close.click()
    assert not window.search_results_panel.isVisible()


def test_the_whole_project_can_be_listed(open_window, project_with_documents):
    window = open_window(project_with_documents)
    window.editor.setPlainText("<TEI><p><persName>Bernardus</persName></p></TEI>")
    _list(window, "persName")
    assert len(_rows(window)) == 2
    # Le document affiché : la liste suit le changement de document.
    edition = window.document
    people = next(session for session in window.documents if session.path.name == "personnes.xml")
    window.show_document(people)
    assert len(_rows(window)) == 4
    window.show_document(edition)
    assert len(_rows(window)) == 2
    window.search_results_project.setChecked(True)
    rows = _rows(window)
    assert not window.search_results_table.isColumnHidden(DOCUMENT)
    assert [row[DOCUMENT] for row in rows] == [_tr("documents.edition_tab")] * 2 + ["Personnes"] * 4
    assert window.search_results_summary.text() == _tr("results.summary.project", count=6, query="persName",
                                                       documents=2)
    # Un clic sur une occurrence d'un autre document affiche ce document.
    window.search_results_table.cellClicked.emit(4, MATCH)
    assert window.document.path.name == "personnes.xml"
    start, end = window.editor._search_match
    cursor = window.editor.textCursor()
    cursor.setPosition(start)
    cursor.setPosition(end, cursor.MoveMode.KeepAnchor)
    assert cursor.selectedText() == "persName"


def test_the_panel_is_translated(open_window, example_project):
    from app_context import current_i18n
    window = open_window(example_project)
    window.language_actions["en"].trigger()
    assert current_i18n().language == "en"
    assert window.search_results_title.text() == "Search results"
    assert window.search_results_table.horizontalHeaderItem(3).text() == "Match"
    assert window.main_toolbar.widgetForAction(window.action_search_list).text() == current_i18n().tr("search.list")


def _long_notes(project, lines=400):
    """Document auxiliaire xml/notes.xml de *lines* lignes, « persName »
    tout à la fin."""
    from project_config import DocumentConfig
    from project_management import update_project_documents
    notes = project.parent / "xml" / "notes.xml"
    body = "\n".join(f"<p>ligne {number}</p>" for number in range(lines))
    notes.write_text(f'<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body>\n{body}\n'
                     f'<p><persName>Petrus</persName></p></body></text></TEI>', encoding="utf-8")
    update_project_documents(project, [DocumentConfig(notes, "Notes")])
    return notes


def _row_of(window, document):
    return next(row for row in range(window.search_results_table.rowCount())
                if window.search_results_table.item(row, DOCUMENT).text() == document)


def test_a_click_in_another_document_shows_the_occurrence(open_window, example_project, qtbot):
    """Le défilement mémorisé du document affiché, restauré juste après
    son affichage, ne cache pas l'occurrence."""
    _long_notes(example_project)
    window = open_window(example_project)
    _list(window, "persName")
    window.search_results_project.setChecked(True)
    window.search_results_table.cellClicked.emit(_row_of(window, "Notes"), MATCH)
    qtbot.wait(100)
    assert window.document.path.name == "notes.xml"
    editor = window.editor
    assert editor.viewport().rect().contains(editor.cursorRect().center())


def test_the_list_is_not_rebuilt_when_only_the_document_changes(open_window, project_with_documents, qtbot):
    """Afficher un autre document ne change aucun texte : la liste de tout
    le projet reste telle quelle (ni reconstruite ni défilée)."""
    from PySide6.QtCore import Qt
    window = open_window(project_with_documents)
    window.editor.setPlainText("<TEI><p><persName>Bernardus</persName></p></TEI>")
    _list(window, "persName")
    window.search_results_project.setChecked(True)
    table = window.search_results_table
    table.item(4, MATCH).setData(Qt.ItemDataRole.UserRole + 7, "marque")
    table.cellClicked.emit(4, MATCH)
    assert window.document.path.name == "personnes.xml"
    qtbot.wait(700)
    assert table.item(4, MATCH).data(Qt.ItemDataRole.UserRole + 7) == "marque"
    # Une vraie modification du texte refait la liste.
    cursor = window.editor.textCursor()
    cursor.movePosition(cursor.MoveOperation.End)
    cursor.insertText("<persName/>")
    qtbot.waitUntil(lambda: table.rowCount() == 7, timeout=3000)


def test_a_click_gives_a_hidden_document_its_tab_back(open_window, project_with_documents):
    window = open_window(project_with_documents)
    people = next(session for session in window.documents if session.path.name == "personnes.xml")
    assert window.hide_document_tab(people)
    window.editor.setPlainText("<TEI><p><persName>Bernardus</persName></p></TEI>")
    _list(window, "persName")
    window.search_results_project.setChecked(True)
    window.search_results_table.cellClicked.emit(_row_of(window, "Personnes"), MATCH)
    assert window.document is people
    bar = window.document_tab_bar
    assert people in window._visible_document_sessions()
    assert bar.tabText(bar.currentIndex()).startswith("Personnes")


def test_each_cell_is_clipped_to_its_own_box(open_window, example_project):
    """Le contexte trop long d'une case ne déborde pas sur la case voisine,
    même avec un style qui ne coupe pas le texte (Windows 11)."""
    from PySide6.QtCore import QRect, Qt
    from PySide6.QtGui import QColor, QImage, QPainter
    from PySide6.QtWidgets import QProxyStyle, QStyle, QStyleOptionViewItem

    class NoClipStyle(QProxyStyle):
        def drawControl(self, element, option, painter, widget=None):
            if element == QStyle.ControlElement.CE_ItemViewItem:
                painter.drawText(option.rect, int(option.displayAlignment | Qt.TextFlag.TextDontClip), option.text)
                return
            super().drawControl(element, option, painter, widget)

    window = open_window(example_project)
    window.editor.setPlainText("x" * 60 + "beta")
    _list(window, "beta")
    table = window.search_results_table
    style = NoClipStyle()
    table.setStyle(style)
    image = QImage(300, 30, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    option = QStyleOptionViewItem()
    option.initFrom(table)
    option.widget = table                                # le style de la table
    option.rect = QRect(200, 0, 60, 30)                  # case « Avant », étroite
    index = table.model().index(0, BEFORE)
    table.itemDelegateForIndex(index).paint(painter, option, index)
    painter.end()
    table.setStyle(None)
    outside = [image.pixelColor(x, y) for x in range(0, 200, 2) for y in range(0, 30, 2)]
    assert all(colour == QColor("white") for colour in outside)
