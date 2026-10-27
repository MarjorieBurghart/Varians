# -*- coding: utf-8 -*-
"""Règles Schematron dans la fenêtre (V0.9.2.3) : messages dans le panneau de
validation (colonne Origine, niveau), à leur ligne, dans leur document ;
onglet orange et question à l'enregistrement pour une erreur, comme pour une
erreur RELAX NG ; étiquette Schematron de la barre d'état. Tests ignorés
sans Saxon, sauf celui de son absence."""
from __future__ import annotations

import importlib.util
import os
import sys
import time

import pytest
from PySide6.QtGui import QColor, QTextCursor
from PySide6.QtWidgets import QMessageBox

from app_context import tr

needs_saxon = pytest.mark.skipif(importlib.util.find_spec("saxonche") is None,
                                 reason="Saxon (saxonche) n'est pas installé")
ERROR_COLOR = QColor("#a06a20")
LEVEL, ORIGIN, LINE, COLUMN, MESSAGE, DOCUMENT = range(6)
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
SCH_MODEL = f'<?xml-model href="regles.sch" type="application/xml" schematypens="{SCH_NS}"?>'
# <varianstest kind="…"> : un kind autre que « a » ou « b » est une erreur,
# un <varianstest> vide un avertissement. TEST_RNG accepte les deux.
RULES = f"""<?xml version="1.0" encoding="UTF-8"?>
<schema xmlns="{SCH_NS}" queryBinding="xslt2">
  <ns prefix="tei" uri="http://www.tei-c.org/ns/1.0"/>
  <pattern id="varianstest">
    <rule context="tei:varianstest">
      <assert test="@kind = ('a', 'b')" id="kind">Le kind « <value-of select="@kind"/> » est inconnu.</assert>
      <report test="not(normalize-space())" role="warning" id="vide">Un varianstest vide.</report>
    </rule>
  </pattern>
</schema>
"""


def _declare_rules(project, rules=RULES, edition="edition.xml"):
    """La règle dans xml/regles.sch, déclarée par l'édition après son RNG."""
    xml = project.parent / "xml"
    (xml / "regles.sch").write_text(rules, encoding="utf-8")
    path = xml / edition
    text = path.read_text(encoding="utf-8")
    end = text.index("?>", text.index("<?xml-model")) + 2
    path.write_text(text[:end] + "\n" + SCH_MODEL + text[end:], encoding="utf-8")
    return xml / "regles.sch"


def _insert_after(window, marker, text):
    source = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(source.index(marker) + len(marker))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(text)


def _line_of(window, needle):
    text = window.editor.toPlainText()
    return text[: text.index(needle)].count("\n") + 1


def _rows(window):
    table = window.validation_table
    return [[table.item(row, column).text() for column in range(table.columnCount())]
            for row in range(table.rowCount())]


def _tab_color(window, session):
    return window.document_tab_bar.tabTextColor(window._tab_sessions.index(session))


def _wait_validation(qtbot):
    import validation_worker
    qtbot.wait(200)
    qtbot.waitUntil(lambda: not validation_worker.worker_client().busy, timeout=60000)
    qtbot.wait(50)


@needs_saxon
def test_a_schematron_error_is_listed_at_its_line_and_leads_to_it(open_window, example_project):
    _declare_rules(example_project)
    window = open_window(example_project)
    assert window.validation_table.horizontalHeaderItem(ORIGIN).text() == tr("rng.column.origin")
    _insert_after(window, "<body>", '\n<varianstest kind="z">x</varianstest>')
    window.validate_relaxng_manual()                                    # F8
    line = _line_of(window, "<varianstest")
    [row] = _rows(window)
    assert row[LEVEL] == tr("rng.level.error") and row[ORIGIN] == tr("rng.origin.schematron")
    assert row[LINE] == str(line) and row[MESSAGE] == "Le kind « z » est inconnu."
    assert window.validation_summary.text() == tr("rng.panel.invalid.schematron", count=1, schema="test.rng",
                                                  rng=0, schematron=1)
    # RELAX NG est satisfait ; l'étiquette Schematron compte l'erreur.
    assert window.rng_status.text() == tr("rng.status.valid")
    assert window.schematron_status.text() == tr("schematron.status.errors", count=1)
    assert "regles.sch" in window.schematron_status.toolTip()
    assert window._document_health == "rng_invalid"
    assert _tab_color(window, window.document) == ERROR_COLOR
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.goto_validation_issue(0)
    assert window.editor.textCursor().blockNumber() + 1 == line


@needs_saxon
def test_rng_and_schematron_errors_are_counted_apart(open_window, example_project):
    _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<forbidden/>\n<varianstest kind="z">x</varianstest>')
    result = window.validate_relaxng_document(show_panel=True)
    assert not result.valid
    origins = [row[ORIGIN] for row in _rows(window)]
    assert origins[-1] == tr("rng.origin.schematron") and tr("rng.origin.relaxng") in origins
    rng = len(origins) - 1
    assert window.validation_summary.text() == tr("rng.panel.invalid.schematron", count=rng + 1,
                                                  schema="test.rng", rng=rng, schematron=1)
    assert window.rng_status.text() == tr("rng.status.invalid", count=rng)


@needs_saxon
def test_saving_asks_first_for_a_schematron_error(open_window, example_project, dialogs):
    _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="z">x</varianstest>')
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)               # annuler
    assert not window.save()
    assert dialogs.seen[-1][1:] == (tr("file.save_rng_invalid.title"), tr("file.save_rng_invalid.text", count=1))


@needs_saxon
def test_warnings_alone_leave_the_document_valid(open_window, example_project):
    _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="a"/>')
    result = window.validate_relaxng_document(show_panel=True)
    assert result.valid
    [row] = _rows(window)
    assert row[LEVEL] == tr("rng.level.warning") and row[MESSAGE] == "Un varianstest vide."
    assert window.validation_summary.text() == tr("rng.panel.valid.messages", schema="test.rng", count=1)
    assert window.schematron_status.text() == tr("schematron.status.messages", count=1)
    assert window._document_health == "normal"
    assert window.save()                                                 # sans question


@needs_saxon
def test_without_message_the_rules_are_marked_as_checked(open_window, example_project):
    _declare_rules(example_project)
    window = open_window(example_project)
    assert window._last_rng_result.valid and window.validation_table.rowCount() == 0
    assert window.schematron_status.text() == tr("schematron.status.valid")
    assert window._last_rng_result.schematron_rules[-1].endswith("regles.sch")


@needs_saxon
def test_the_rules_of_the_rng_are_applied_without_declaration(open_window, example_project):
    # Comme tei_all.rng : des règles intégrées au RNG déclaré.
    rng = example_project.parent / "xml" / "test.rng"
    text = rng.read_text(encoding="utf-8")
    rng.write_text(text.replace("</grammar>", f"""
  <pattern xmlns="{SCH_NS}">
    <rule context="*:varianstest"><assert test="@kind = 'a'">Seul le kind « a ».</assert></rule>
  </pattern>
</grammar>"""), encoding="utf-8")
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="b">x</varianstest>')
    window.validate_relaxng_manual()
    assert [row[MESSAGE] for row in _rows(window)] == ["Seul le kind « a »."]


@needs_saxon
def test_a_changed_rule_is_checked_again_before_saving(open_window, example_project, dialogs):
    rules = _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="z">x</varianstest>')
    assert not window.validate_relaxng_document(show_panel=True).valid
    rules.write_text(RULES.replace("('a', 'b')", "('a', 'b', 'z')"), encoding="utf-8")
    stamp = time.time() + 5
    os.utime(rules, (stamp, stamp))
    assert window.save()                                                 # sans question : règle changée


@needs_saxon
def test_an_error_in_a_part_colors_that_part_only(open_window, collection_project, qtbot):
    # Erreur : un titre (ligne 2) autre que « Sermo 2 » ; avertissement :
    # chaque titre.
    _declare_rules(collection_project, RULES.replace("tei:varianstest", "tei:head").replace(
        "@kind = ('a', 'b')", "ends-with(., '2')").replace("not(normalize-space())", "true()"))
    window = open_window(collection_project)
    result = window._last_rng_result
    assert not result.valid
    s02 = next(s for s in window.documents if s.path.name == "s02.xml")
    s01 = next(s for s in window.documents if s.path.name == "s01.xml")
    errors = [(row[DOCUMENT], row[LINE]) for row in _rows(window) if row[LEVEL] == tr("rng.level.error")]
    assert sorted(errors) == [("s01.xml", "2"), ("s03.xml", "2")]
    # s02 n'a qu'un avertissement : son onglet garde sa couleur.
    assert _tab_color(window, s01) == ERROR_COLOR and _tab_color(window, s02) != ERROR_COLOR
    window.show_document(s02)
    _wait_validation(qtbot)
    assert window.schematron_status.text() == tr("schematron.status.errors", count=2)


@needs_saxon
def test_incorrect_rules_are_reported_without_invalidating_the_document(open_window, example_project):
    _declare_rules(example_project, RULES.replace("@kind = ('a', 'b')", "@kind = ("))
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="z">x</varianstest>')
    result = window.validate_relaxng_document(show_panel=True)
    assert result.valid and window._document_health == "normal"
    assert window.schematron_status.text() == tr("schematron.status.rules_error")
    assert "regles.sch:6:" in window.schematron_status.toolTip()
    assert "regles.sch:6:" in window.validation_summary.text()


def test_without_saxon_the_rng_validation_goes_on(open_window, example_project, monkeypatch, qtbot):
    import validation_worker
    import xslt_engines
    import schematron
    from validation_worker import RelaxNGWorkerClient
    # Validation dans Varians même (processus indisponible), sans Saxon.
    client = RelaxNGWorkerClient([str(example_project.parent / "absent")])
    monkeypatch.setattr(validation_worker, "_client", client)
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    monkeypatch.setitem(sys.modules, "saxonche", None)
    schematron.clear_cache()
    _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", '\n<varianstest kind="z">x</varianstest>')
    result = window.validate_relaxng_document(show_panel=True)
    assert result.valid and result.schematron_error == "saxon_missing"
    assert window.schematron_status.text() == tr("schematron.status.saxon_missing")
    assert tr("schematron.panel.saxon_missing") in window.validation_summary.text()
    schematron.clear_cache()


def test_without_validation_the_rules_are_not_checked(open_window, example_project):
    _declare_rules(example_project)
    project = example_project.read_text(encoding="utf-8")
    example_project.write_text(project.replace('<schema type="relaxng" source="xml-model"',
                                               '<schema type="relaxng" source="none"'), encoding="utf-8")
    window = open_window(example_project)
    assert window._schema_mode == "none"
    assert window.schematron_status.text() == tr("schematron.status.disabled")
