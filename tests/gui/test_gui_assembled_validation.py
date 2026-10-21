# -*- coding: utf-8 -*-
"""Validation RELAX NG d'une édition assemblée par XInclude, dans la
fenêtre : l'édition et chaque partie font valider l'édition assemblée ;
chaque erreur indique son document (colonne Document) et y mène au
double-clic ; l'onglet de chaque partie prend la couleur de ses propres
erreurs. Petite collection de trois sermons (fixture collection_project)."""
from __future__ import annotations

from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QMessageBox

from app_context import tr

ERROR_COLOR = QColor("#a06a20")
DOCUMENT_COLUMN = 4


def _doc(window, name):
    return next(s for s in window.documents if s.path.name == name)


def _part_file(project, name):
    return project.parent / "xml" / "sermons" / name


def _break(path):
    """Élément interdit dans le paragraphe du sermon (ligne 3)."""
    path.write_text(path.read_text(encoding="utf-8").replace("Sermo <hi>breuis</hi>.", "Sermo <forbidden/>."),
                    encoding="utf-8")


def _rows(window):
    table = window.validation_table
    return [(table.item(row, DOCUMENT_COLUMN).text(), table.item(row, 1).text())
            for row in range(table.rowCount())]


def _tab_color(window, session):
    return window.document_tab_bar.tabTextColor(window._tab_sessions.index(session))


def _wait_validation(qtbot):
    import validation_worker
    qtbot.wait(200)
    qtbot.waitUntil(lambda: not validation_worker.worker_client().busy, timeout=60000)
    qtbot.wait(50)


def test_an_error_in_a_part_shows_its_document_and_leads_to_it(open_window, collection_project, qtbot):
    _break(_part_file(collection_project, "s02.xml"))
    window = open_window(collection_project)
    assert window.document is window.edition_session
    assert window._last_rng_result is not None and not window._last_rng_result.valid
    assert not window.validation_table.isColumnHidden(DOCUMENT_COLUMN)
    assert set(_rows(window)) == {("s02.xml", "3")}
    window.goto_validation_issue(0)
    qtbot.wait(50)
    assert window.document is _doc(window, "s02.xml")
    assert window.editor.textCursor().blockNumber() == 2                 # ligne 3
    assert window.document_tab_bar.currentIndex() == window._tab_sessions.index(window.document)


def test_editing_a_part_revalidates_the_assembled_edition(open_window, collection_project, qtbot):
    window = open_window(collection_project)
    assert window._last_rng_result.valid
    part = _doc(window, "s01.xml")
    window.show_document(part)
    _wait_validation(qtbot)
    assert window._last_rng_result.valid                                 # schéma de l'édition
    edition = window.edition_session
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index("Sermo <hi>"))
    cursor.insertText("<forbidden/>")
    # Le résultat partagé de l'édition n'est plus valable.
    assert edition.last_rng_result is None
    result = window.validate_relaxng_document(show_panel=True)
    assert not result.valid
    assert set(_rows(window)) == {("s01.xml", "3")}
    assert edition.last_rng_result is result                             # rangé aussi sur l'édition
    assert _tab_color(window, part) == ERROR_COLOR
    assert _tab_color(window, edition) != ERROR_COLOR
    window.editor.undo()
    assert window.validate_relaxng_document(show_panel=True).valid
    assert _tab_color(window, part) != ERROR_COLOR


def test_each_tab_takes_the_color_of_its_own_errors(open_window, collection_project):
    _break(_part_file(collection_project, "s02.xml"))
    window = open_window(collection_project)
    assert _tab_color(window, _doc(window, "s02.xml")) == ERROR_COLOR
    assert _tab_color(window, _doc(window, "s01.xml")) != ERROR_COLOR
    assert _tab_color(window, window.edition_session) != ERROR_COLOR
    assert window._document_health == "normal"                           # l'édition elle-même est valide


def test_a_part_is_shown_with_the_result_of_the_assembled_edition(open_window, collection_project, qtbot):
    _break(_part_file(collection_project, "s02.xml"))
    window = open_window(collection_project)
    window.show_document(_doc(window, "s03.xml"))
    _wait_validation(qtbot)
    assert window.rng_status.text() == tr("rng.status.invalid", count=len(window._last_rng_result.issues))
    assert set(_rows(window)) == {("s02.xml", "3")}
    assert window._document_health == "normal"                           # s03 n'a pas d'erreur


def test_saving_a_part_checks_the_assembled_edition(open_window, collection_project, dialogs):
    _break(_part_file(collection_project, "s02.xml"))
    window = open_window(collection_project)
    part = _doc(window, "s01.xml")
    window.show_document(part)
    cursor = window.editor.textCursor()
    cursor.movePosition(QTextCursor.MoveOperation.End)
    cursor.insertText("<!-- essai -->")
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)             # enregistrer quand même
    assert window.save()
    assert dialogs.seen[-1][1] == tr("file.save_rng_invalid.title")
    assert part.path.read_text(encoding="utf-8").endswith("<!-- essai -->")


def test_an_inclusion_problem_is_an_error_of_the_edition(open_window, collection_project):
    edition = collection_project.parent / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace(
        '<xi:include href="sermons/s03.xml"/>', '<xi:include href="sermons/absent.xml"/>'), encoding="utf-8")
    window = open_window(collection_project)
    table = window.validation_table
    assert _rows(window) == [(tr("documents.edition_tab"), "9")]
    missing = edition.parent / "sermons" / "absent.xml"
    assert table.item(0, 3).text() == tr("rng.xinclude.missing", detail=str(missing))


def test_a_simple_project_has_no_document_column(open_window, example_project):
    window = open_window(example_project)
    assert window.validation_table.isColumnHidden(DOCUMENT_COLUMN)
