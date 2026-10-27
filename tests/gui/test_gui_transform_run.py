# -*- coding: utf-8 -*-
"""Exécution d'un scénario de transformation depuis Varians (V0.9.2.0) :
liste, bouton « Transformer ▾ », Ctrl+Shift+T, enregistrement préalable,
compte rendu, erreurs, annulation, aperçu."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QUrl
from PySide6.QtGui import QDesktopServices, QKeySequence
from PySide6.QtWidgets import QMessageBox, QPushButton

from app_context import tr
from project_config import TransformScenario
from project_management import update_project_transformations

ROLE = QMessageBox.ButtonRole


@pytest.fixture
def opened(monkeypatch):
    urls = []
    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(lambda url: urls.append(url.toLocalFile())))
    return urls


def _project(project_path, *scenarios):
    root = project_path.parent
    (root / "rendering" / "noms.xsl").write_text(
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
        'xmlns:tei="http://www.tei-c.org/ns/1.0"><xsl:output method="text"/>'
        '<xsl:template match="/"><xsl:message>noms</xsl:message>'
        '<xsl:for-each select="//tei:persName"><xsl:value-of select="normalize-space()"/>|</xsl:for-each>'
        '</xsl:template></xsl:stylesheet>', encoding="utf-8")
    (root / "rendering" / "casse.xsl").write_text(
        '<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform">\n'
        '<xsl:template match="/">\n<xsl:value-of select="(("/>\n</xsl:template>\n</xsl:stylesheet>',
        encoding="utf-8")
    update_project_transformations(project_path, list(scenarios))
    return project_path


NAMES = TransformScenario("Noms", "rendering/noms.xsl", "publications/noms.txt")


def _finish(qtbot, window, start):
    with qtbot.waitSignal(window.transform_runner().finished, timeout=60_000):
        start()
    qtbot.wait(50)


def _choose(group, row, button):
    def answer(dialog):
        dialog.tree.setCurrentItem(dialog.item_for(group, row))
        getattr(dialog, button).click()
        return dialog.result()
    return answer


def test_the_predefined_scenario_runs_from_the_list(open_window, sermons_project, dialogs, qtbot, opened):
    window = open_window(sermons_project)
    output = sermons_project.parent / "publications" / "edition.html"
    dialogs.expect("dialog", _choose("predefined", 0, "run_btn"))
    dialogs.expect("box", ROLE.AcceptRole)                           # compte rendu : Ouvrir
    _finish(qtbot, window, window.transform_scenarios_dialog)
    assert "Sermones" in output.read_text(encoding="utf-8")
    assert (output.parent / "tei.css").is_file()
    kind, title, text = dialogs.seen[-1]
    assert title == tr("transform.done.title") and str(output) in text
    assert [Path(path) for path in opened] == [output]


def test_the_report_opens_the_folder_of_the_result(open_window, sermons_project, dialogs, qtbot, opened):
    window = open_window(sermons_project)
    output = sermons_project.parent / "publications" / "edition.html"
    dialogs.expect("dialog", _choose("predefined", 0, "run_btn"))
    dialogs.expect("box", tr("common.open_folder"))                 # Ouvrir le dossier
    _finish(qtbot, window, window.transform_scenarios_dialog)
    assert output.is_file() and [Path(path) for path in opened] == [output.parent]


def test_a_tei_scenario_runs_from_the_list_and_names_the_library(open_window, sermons_project, dialogs, qtbot,
                                                                 opened, monkeypatch):
    from app_context import current_i18n
    from xslt_scenarios import tei_library
    details = []
    monkeypatch.setattr(QMessageBox, "setDetailedText", lambda box, text: details.append(text))
    window = open_window(sermons_project)
    output = sermons_project.parent / "publications" / "tei" / "edition.html"
    dialogs.expect("dialog", _choose("predefined", 1, "run_btn"))                # « TEI : HTML »
    dialogs.expect("box", ROLE.RejectRole)
    _finish(qtbot, window, window.transform_scenarios_dialog)
    assert "Sermo in adventu Domini" in output.read_text(encoding="utf-8")
    assert (output.parent / "tei.css").is_file()
    # Le journal nomme la version des TEI Stylesheets ; elles parlent la langue de l'interface.
    assert tr("transform.journal.library", detail=f"TEI Stylesheets {tei_library().version}") in details[-1]
    assert f"documentationLanguage = {current_i18n().language}" in details[-1]
    assert opened == []


def test_the_toolbar_button_lists_the_scenarios_and_reruns_the_last_one(open_window, sermons_project, dialogs,
                                                                       qtbot, opened):
    window = open_window(_project(sermons_project, NAMES))
    button = window.transform_button
    assert window.action_transform.shortcut() == QKeySequence("Ctrl+Shift+T")
    window.transform_menu.aboutToShow.emit()
    labels = [action.text() for action in window.transform_menu.actions() if not action.isSeparator()]
    assert labels == ["Noms", tr("transform.predefined.varians-html"), tr("transform.group.tei"),
                      tr("menu.transform_scenarios")]
    # V0.9.2.7 : les scénarios des TEI Stylesheets, dans un sous-menu.
    tei = next(action.menu() for action in window.transform_menu.actions() if action.menu() is not None)
    assert [action.text() for action in tei.actions()] == [tr(f"transform.predefined.{key}") for key in (
        "tei-html", "tei-pages", "tei-docx", "tei-odt", "tei-epub", "tei-txt", "tei-markdown", "tei-latex")]
    assert button.menu() is window.transform_menu

    # Aucun scénario lancé : le bouton ouvre la liste.
    dialogs.expect("dialog", lambda dialog: (dialog.reject(), dialog.result())[1])
    window.action_transform.trigger()

    output = sermons_project.parent / "publications" / "noms.txt"
    dialogs.expect("box", ROLE.RejectRole)
    _finish(qtbot, window, window.transform_menu.actions()[0].trigger)
    assert output.read_text(encoding="utf-8").startswith("saint Bernard|")
    output.unlink()
    dialogs.expect("box", ROLE.RejectRole)
    _finish(qtbot, window, window.action_transform.trigger)          # le dernier scénario
    assert output.is_file()
    assert opened == []


def test_what_the_scenario_reads_is_saved_first(open_window, sermons_project, dialogs, qtbot, opened):
    window = open_window(_project(sermons_project, NAMES))
    cursor = window.editor.textCursor()
    text = window.editor.toPlainText()
    cursor.setPosition(text.index("saint Bernard") + len("saint "))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("frère ")
    assert window.modified
    dialogs.expect("box", ROLE.RejectRole)
    _finish(qtbot, window, lambda: window.run_transform_scenario(NAMES))
    assert not window.modified
    assert "saint frère Bernard" in window.project.edition.read_text(encoding="utf-8")
    assert (sermons_project.parent / "publications" / "noms.txt").read_text(encoding="utf-8").startswith(
        "saint frère Bernard|")


def test_an_error_of_the_stylesheet_is_shown_with_its_line(open_window, sermons_project, dialogs, qtbot):
    broken = TransformScenario("Cassé", "rendering/casse.xsl", "publications/casse.html")
    window = open_window(_project(sermons_project, broken))
    dialogs.expect("box", ROLE.RejectRole)
    _finish(qtbot, window, lambda: window.run_transform_scenario(broken))
    kind, title, text = dialogs.seen[-1]
    assert title == tr("transform.failed.title")
    assert "casse.xsl:3" in text
    assert not (sermons_project.parent / "publications").exists()


def test_a_scenario_with_a_problem_is_not_run(open_window, sermons_project, dialogs):
    missing = TransformScenario("Sans feuille", "rendering/absente.xsl", "publications/a.html")
    window = open_window(_project(sermons_project, missing))
    dialogs.expect("warning")
    assert window.run_transform_scenario(missing) is False
    assert tr("transform.problem.xslt_missing", detail="rendering/absente.xsl") in dialogs.seen[-1][2]
    assert not window.transform_runner().running()


def test_a_long_run_can_be_cancelled(open_window, sermons_project, dialogs, qtbot, monkeypatch):
    import transform_ui
    window = open_window(_project(sermons_project, NAMES))
    monkeypatch.setattr(transform_ui, "_worker_command", lambda: [sys.executable, "-c", "import time; time.sleep(60)"])
    window._transform_runner = None
    assert window.run_transform_scenario(NAMES) is True
    qtbot.waitUntil(lambda: window.transform_progress is not None and window.transform_progress.isVisible(),
                    timeout=5_000)
    dialogs.expect("information")                                    # « déjà en cours »
    assert window.run_transform_scenario(NAMES) is False
    with qtbot.waitSignal(window.transform_runner().finished, timeout=10_000):
        window.transform_progress.findChild(QPushButton).click()          # « Annuler »
    assert window.statusBar().currentMessage() == tr("transform.cancelled", name="Noms")
    assert not (sermons_project.parent / "publications").exists()


def test_the_preview_opens_a_copy_without_touching_the_result(open_window, sermons_project, dialogs, qtbot,
                                                              opened):
    window = open_window(_project(sermons_project, NAMES))
    _finish(qtbot, window, lambda: window.run_transform_scenario(NAMES, preview=True))
    assert not (sermons_project.parent / "publications").exists()
    (path,) = opened
    assert path.endswith("noms.txt") and "saint Bernard|" in open(path, encoding="utf-8").read()
    assert QUrl.fromLocalFile(path).isLocalFile()
