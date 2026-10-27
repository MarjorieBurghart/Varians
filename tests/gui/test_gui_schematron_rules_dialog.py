# -*- coding: utf-8 -*-
"""Boîte « Règles Schematron du document… » (V0.9.2.5) : ouverte par un
clic sur l'étiquette Schematron ou par le bouton « Règles… » du panneau ;
elle choisit la phase d'une déclaration, en ajoute ou en retire une, en
réécrivant les ``<?xml-model?>`` du document en une seule modification
annulable. Une partie affichée : ce sont les déclarations de l'édition."""
from __future__ import annotations

import importlib.util

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QDialog, QFileDialog

from app_context import tr
from schema_resolution import detect_xml_models

needs_saxon = pytest.mark.skipif(importlib.util.find_spec("saxonche") is None,
                                 reason="Saxon (saxonche) n'est pas installé")
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
SCH_MODEL = f'<?xml-model href="regles.sch" type="application/xml" schematypens="{SCH_NS}"?>'
RULES = f"""<?xml version="1.0" encoding="UTF-8"?>
<schema xmlns="{SCH_NS}" queryBinding="xslt2">
  <ns prefix="tei" uri="http://www.tei-c.org/ns/1.0"/>
  <phase id="kind"><active pattern="kind"/></phase>
  <phase id="vide"><active pattern="vide"/></phase>
  <pattern id="kind"><rule context="tei:varianstest"><assert test="@kind = ('a', 'b')">Kind.</assert></rule></pattern>
  <pattern id="vide"><rule context="tei:varianstest"><report test="not(normalize-space())" role="warning">Vide.</report></rule></pattern>
</schema>
"""


def _declare(project, xml_name="edition.xml", rules=RULES):
    xml = project.parent / "xml"
    (xml / "regles.sch").write_text(rules, encoding="utf-8")
    path = xml / xml_name
    text = path.read_text(encoding="utf-8")
    end = text.index("?>", text.index("<?xml-model")) + 2
    path.write_text(text[:end] + "\n" + SCH_MODEL + text[end:], encoding="utf-8")


def _schematron(text):
    return [(d.href, d.phase) for d in detect_xml_models(text) if d.is_schematron]


def _run(dialogs, window, action, opener="panel"):
    """Ouvre la boîte (``opener``) ; ``action(dialog)`` la manipule, puis OK."""
    seen = []

    def answer(dialog):
        seen.append(dialog)
        action(dialog)
        return QDialog.DialogCode.Accepted

    dialogs.expect("dialog", answer)
    if opener == "label":
        QTest.mouseClick(window.schematron_status, Qt.MouseButton.LeftButton)
    else:
        window.validation_rules.click()
    return seen[0]


def test_a_phase_chosen_in_the_dialog_is_written_in_the_declaration(open_window, example_project, dialogs):
    _declare(example_project)
    window = open_window(example_project)
    window.validate_relaxng_manual()
    assert window.validation_rules.text() == tr("schematron.panel.rules_button")
    before = window.editor.toPlainText()

    def choose(dialog):
        assert dialog.windowTitle() == tr("schematron.dialog.title")
        assert [dialog.href(row) for row in range(dialog.row_count())] == ["regles.sch"]
        assert dialog.phase_choices(0) == ["", "#ALL", "kind", "vide"]
        dialog.choose_phase(0, "vide")

    _run(dialogs, window, choose, opener="label")
    text = window.editor.toPlainText()
    assert _schematron(text) == [("regles.sch", "vide")]
    assert text == before.replace(SCH_MODEL, SCH_MODEL[:-2] + ' phase="vide"?>')
    assert window.document.modified
    # Une seule modification à défaire.
    window.editor.undo()
    assert window.editor.toPlainText() == before


@needs_saxon
def test_the_chosen_phase_is_applied(open_window, example_project, dialogs, qtbot):
    _declare(example_project)
    window = open_window(example_project)
    window.validate_relaxng_manual()
    _run(dialogs, window, lambda dialog: dialog.choose_phase(0, "vide"))
    window.validate_relaxng_manual()
    assert tr("schematron.tip.phase", name="regles.sch", phase="vide") in window.schematron_status.toolTip()


def test_an_unknown_phase_is_shown_as_such(open_window, example_project, dialogs):
    _declare(example_project)
    edition = example_project.parent / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace(SCH_MODEL, SCH_MODEL[:-2] + ' phase="autre"?>'),
                       encoding="utf-8")
    window = open_window(example_project)

    def check(dialog):
        assert dialog.phase_choices(0) == ["", "#ALL", "kind", "vide", "autre"]
        assert dialog.phase_label(0, "autre") == tr("schematron.dialog.unknown_phase", phase="autre")
        assert dialog.current_phase(0) == "autre"

    _run(dialogs, window, check)
    assert _schematron(window.editor.toPlainText()) == [("regles.sch", "autre")]      # inchangé


def test_a_declaration_is_added_then_removed(open_window, example_project, dialogs, monkeypatch):
    other = example_project.parent / "xml" / "autres.sch"
    other.write_text(RULES, encoding="utf-8")
    window = open_window(example_project)
    monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(lambda *a, **k: (str(other), "")))
    _run(dialogs, window, lambda dialog: dialog.add())
    assert ("autres.sch", "") in _schematron(window.editor.toPlainText())

    def remove(dialog):
        row = [dialog.href(row) for row in range(dialog.row_count())].index("autres.sch")
        dialog.remove(row)

    _run(dialogs, window, remove)
    assert ("autres.sch", "") not in _schematron(window.editor.toPlainText())


def test_cancel_changes_nothing(open_window, example_project, dialogs):
    _declare(example_project)
    window = open_window(example_project)
    before = window.editor.toPlainText()

    def cancel(dialog):
        dialog.choose_phase(0, "kind")
        return QDialog.DialogCode.Rejected

    dialogs.expect("dialog", cancel)
    window.validation_rules.click()
    assert window.editor.toPlainText() == before and not window.document.modified


def test_with_a_part_displayed_the_edition_is_changed(open_window, collection_project, dialogs):
    window = open_window(collection_project)
    part = next(session for session in window.documents if session.is_part)
    window.show_document(part)
    part_text = window.editor.toPlainText()
    edition_before = window.edition_session.text_document.toPlainText()
    _run(dialogs, window, lambda dialog: dialog.add_href("regles.sch"))
    assert window.editor.toPlainText() == part_text
    edition_text = window.edition_session.text_document.toPlainText()
    assert _schematron(edition_text)[-1] == ("regles.sch", "")
    assert edition_text != edition_before and window.edition_session.text_document.isModified()


def test_the_rules_button_is_disabled_for_a_rules_file(open_window, example_project):
    from project_config import DocumentConfig, load_project
    from project_management import update_project_documents
    _declare(example_project)
    rules = example_project.parent / "xml" / "regles.sch"
    update_project_documents(example_project, list(load_project(example_project).documents) + [DocumentConfig(rules)])
    window = open_window(example_project)
    assert window.validation_rules.isEnabled()
    window.show_document(next(s for s in window.documents if s.path == rules))
    assert not window.validation_rules.isEnabled()


def test_a_change_of_language_keeps_the_columns_and_the_rules_button(open_window, example_project):
    window = open_window(example_project)
    window._set_language_code("en")
    try:
        headers = [window.validation_table.horizontalHeaderItem(column).text()
                   for column in range(window.validation_table.columnCount())]
        assert headers == [tr(key) for key in ("rng.column.level", "rng.column.origin", "rng.column.line",
                                                    "rng.column.column", "rng.column.message", "rng.column.document")]
        assert window.validation_rules.text() == tr("schematron.panel.rules_button")
    finally:
        window._set_language_code("fr")
