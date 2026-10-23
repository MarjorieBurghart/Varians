# -*- coding: utf-8 -*-
"""Vérification d'une feuille XSLT dans Varians (V0.9.2.1), « comme le
RNG » : F8, premier affichage, frappe après F8, enregistrement ; panneau de
validation avec les lignes des erreurs, barre d'état, couleur de l'onglet.
L'édition et les autres documents gardent leur validation RELAX NG."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QMessageBox

from app_context import tr
from project_config import DocumentConfig, TransformScenario, load_project
from project_management import update_project_documents, update_project_transformations
from xslt_scenarios import saxon_available

ROLE = QMessageBox.ButtonRole
HEAD = ('<xsl:stylesheet version="{version}" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
        ' xmlns:tei="http://www.tei-c.org/ns/1.0">\n')
GOOD = HEAD.format(version="1.0") + '<xsl:template match="/"><r/></xsl:template>\n</xsl:stylesheet>\n'
BAD = (HEAD.format(version="1.0") + '<xsl:template match="/">\n'      # ligne 2
       '<xsl:value-of select="(("/>\n'                                 # ligne 3
       '<r/>\n'
       '<xsl:apply-templates select="]"/>\n'                           # ligne 5
       '</xsl:template>\n</xsl:stylesheet>\n')


def _lxml():
    return tr("transform.engine.lxml")


@pytest.fixture
def with_stylesheets(sermons_project):
    """Projet « sermons » avec des feuilles dans xslt/, inscrites au projet."""
    def _make(**stylesheets):
        root = sermons_project.parent
        (root / "xslt").mkdir(exist_ok=True)
        documents = list(load_project(sermons_project).documents)
        for name, text in stylesheets.items():
            path = root / "xslt" / name.replace("_", ".")
            path.write_text(text, encoding="utf-8")
            documents.append(DocumentConfig(path))
        update_project_documents(sermons_project, documents)
        return sermons_project
    return _make


def _show(window, name):
    session = next(s for s in window.documents if s.path is not None and s.path.name == name)
    assert window.show_document(session)
    return session


def _rows(window):
    table = window.validation_table
    return [[table.item(row, column).text() for column in range(5)] for row in range(table.rowCount())]


def _checked(qtbot, window, text):
    qtbot.waitUntil(lambda: window.rng_status.text() == text, timeout=60_000)


def test_f8_checks_the_displayed_stylesheet_and_lists_its_errors(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=BAD))
    assert window.action_validate_rng.text() == tr("toolbar.validate_rng")
    _show(window, "index.xsl")
    assert window.action_validate_rng.text() == tr("xslt_check.action")
    assert window.validation_title.text() == tr("xslt_check.panel.title")
    window.action_validate_rng.trigger()                               # F8 : attend le résultat
    assert window.validation_panel.isVisible()
    rows = _rows(window)
    assert [(row[0], row[1]) for row in rows] == [(tr("rng.level.error"), "3"), (tr("rng.level.error"), "5")]
    assert all(row[3] for row in rows)
    assert window.validation_table.isColumnHidden(4)
    assert window.rng_status.text() == tr("xslt_check.status.invalid", engines=_lxml(), count=2)
    assert window.validation_summary.text() == tr("xslt_check.panel.invalid", engines=_lxml(), count=2)
    assert window.document.health == "rng_invalid"

    window.goto_validation_issue(1)
    assert window.editor.textCursor().blockNumber() == 4                # ligne 5

    # L'édition garde sa validation RELAX NG.
    window.show_document(window.edition_session)
    assert window.action_validate_rng.text() == tr("toolbar.validate_rng")
    assert window.validation_title.text() == tr("rng.panel.title")


def test_a_correct_stylesheet_is_reported_as_such(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=GOOD))
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("xslt_check.status.valid", engines=_lxml())
    assert window.validation_summary.text() == tr("xslt_check.panel.valid", engines=_lxml())
    assert window.statusBar().currentMessage() == tr("xslt_check.message.valid")
    assert _rows(window) == []
    assert window.document.health == "normal"


def test_the_first_display_checks_without_waiting(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=BAD))
    _show(window, "index.xsl")
    _checked(qtbot, window, tr("xslt_check.status.invalid", engines=_lxml(), count=2))
    assert window.document.health == "rng_invalid"
    assert not window.validation_panel.isVisible()                    # automatique : panneau fermé

    # Retour à la feuille : le résultat est gardé, sans nouvelle vérification.
    window.show_document(window.edition_session)
    _show(window, "index.xsl")
    assert window.rng_status.text() == tr("xslt_check.status.invalid", engines=_lxml(), count=2)
    assert len(_rows(window)) == 2


def test_after_f8_typing_checks_again(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=GOOD))
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("xslt_check.status.valid", engines=_lxml())
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<r/>"))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText('<xsl:value-of select="(("/>')
    _checked(qtbot, window, tr("xslt_check.status.invalid", engines=_lxml(), count=1))
    assert [row[1] for row in _rows(window)] == ["2"]


def test_saving_a_stylesheet_with_errors_asks_first(open_window, with_stylesheets, dialogs, qtbot):
    project = with_stylesheets(index_xsl=GOOD)
    path = project.parent / "xslt" / "index.xsl"
    window = open_window(project)
    _show(window, "index.xsl")
    _checked(qtbot, window, tr("xslt_check.status.valid", engines=_lxml()))
    window.editor.selectAll()
    window.editor.insertPlainText(BAD)
    dialogs.expect("box", ROLE.RejectRole)                             # Annuler
    assert not window.save()
    kind, title, text = dialogs.seen[-1]
    assert title == tr("file.save_xslt_invalid.title")
    assert text == tr("file.save_xslt_invalid.text", count=2)
    assert path.read_text(encoding="utf-8") == GOOD
    dialogs.expect("box", ROLE.AcceptRole)                             # Enregistrer quand même
    assert window.save()
    assert path.read_text(encoding="utf-8") == BAD


def test_a_correct_stylesheet_is_saved_without_question(open_window, with_stylesheets, dialogs, qtbot):
    project = with_stylesheets(index_xsl=BAD)
    window = open_window(project)
    _show(window, "index.xsl")
    window.editor.selectAll()
    window.editor.insertPlainText(GOOD)
    assert window.save()                                               # aucune boîte attendue
    assert (project.parent / "xslt" / "index.xsl").read_text(encoding="utf-8") == GOOD
    assert window.rng_status.text() == tr("xslt_check.status.valid", engines=_lxml())


def test_a_malformed_stylesheet_is_shown_as_malformed(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=GOOD.replace("<r/>", "<r>")))
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("xslt_check.status.malformed")
    assert window.document.health == "malformed"
    assert [row[1] for row in _rows(window)] in (["2"], ["3"])


def test_an_error_in_an_imported_stylesheet_leads_to_its_document(open_window, with_stylesheets, qtbot):
    imported = HEAD.format(version="1.0") + '<xsl:template name="c">\n<xsl:value-of select="(("/>\n' \
                                            "</xsl:template>\n</xsl:stylesheet>\n"
    main = HEAD.format(version="1.0") + '<xsl:import href="commun.xsl"/>\n' \
                                        '<xsl:template match="/"><r/></xsl:template>\n</xsl:stylesheet>\n'
    window = open_window(with_stylesheets(index_xsl=main, commun_xsl=imported))
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    (row,) = _rows(window)
    assert row[1] == "3" and not window.validation_table.isColumnHidden(4)
    assert row[4] == window._document_tab_name(next(s for s in window.documents if s.path.name == "commun.xsl"))
    window.goto_validation_issue(0)
    assert window.document.path.name == "commun.xsl"
    qtbot.waitUntil(lambda: window.editor.textCursor().blockNumber() == 2, timeout=5_000)


@pytest.mark.skipif(not saxon_available(), reason="Saxon (saxonche) n'est pas installé")
def test_the_engine_is_that_of_the_scenarios_of_the_stylesheet(open_window, with_stylesheets, qtbot):
    text = HEAD.format(version="3.0") + '<xsl:template match="/" mode2="x"><r/></xsl:template>\n</xsl:stylesheet>\n'
    project = with_stylesheets(index_xsl=text)
    update_project_transformations(project, [TransformScenario("Index", "xslt/index.xsl", "publications/i.html",
                                                               engine="saxon")])
    window = open_window(project)
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    saxon = tr("transform.engine.saxon")
    assert window.rng_status.text() == tr("xslt_check.status.invalid", engines=saxon, count=1)
    (row,) = _rows(window)
    assert row[1] == "2" and "XTSE0090" in row[3]


def test_a_stylesheet_without_scenario_is_checked_according_to_its_version(open_window, with_stylesheets, qtbot):
    window = open_window(with_stylesheets(index_xsl=GOOD.replace('version="1.0"', 'version="3.0"')))
    _show(window, "index.xsl")
    window.action_validate_rng.trigger()
    saxon = tr("transform.engine.saxon")
    if saxon_available():
        assert window.rng_status.text() == tr("xslt_check.status.valid", engines=saxon)
    else:
        assert window.rng_status.text() == tr("xslt_check.status.failed")
        assert tr("transform.error.saxon_missing", detail="") in window.validation_summary.text()
