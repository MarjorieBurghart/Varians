# -*- coding: utf-8 -*-
"""Fichiers Schematron (.sch) comme documents du projet (V0.9.2.4) : ajout,
« Nouveau fichier Schematron… », et vérification « comme le RNG » (F8,
premier affichage, frappe après F8, enregistrement) : structure d'après le
schéma ISO livré, expressions XPath compilées par Saxon, à leur ligne.
L'édition garde sa validation RELAX NG."""
from __future__ import annotations

import importlib.util
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest
from PySide6.QtWidgets import QFileDialog, QMessageBox

from app_context import tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents

needs_saxon = pytest.mark.skipif(importlib.util.find_spec("saxonche") is None,
                                 reason="Saxon (saxonche) n'est pas installé")
ROLE = QMessageBox.ButtonRole
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
GOOD = f"""<?xml version="1.0" encoding="UTF-8"?>
<sch:schema xmlns:sch="{SCH_NS}" queryBinding="xslt2">
  <sch:ns prefix="tei" uri="http://www.tei-c.org/ns/1.0"/>
  <sch:pattern id="apparat">
    <sch:rule context="tei:app">
      <sch:assert test="tei:lem or tei:rdg" severity="warning">Apparat sans leçon.</sch:assert>
    </sch:rule>
  </sch:pattern>
</sch:schema>
"""
# Ligne 6 : une expression XPath fautive.
XPATH = GOOD.replace('test="tei:lem or tei:rdg"', 'test="tei:lem or tei:rdg["')
# Ligne 5 : un attribut sans espace de noms que Schematron ne connaît pas.
STRUCTURE = GOOD.replace('<sch:rule context="tei:app">', '<sch:rule context="tei:app" sorte="x">')


@pytest.fixture
def with_rules(example_project):
    """Projet d'exemple avec xml/regles.sch inscrit à ses documents."""
    def _make(text):
        path = example_project.parent / "xml" / "regles.sch"
        path.write_text(text, encoding="utf-8")
        update_project_documents(example_project, list(load_project(example_project).documents)
                                 + [DocumentConfig(path)])
        return example_project
    return _make


def _show(window, name="regles.sch"):
    session = next(s for s in window.documents if s.path is not None and s.path.name == name)
    assert window.show_document(session)
    return session


def _rows(window):
    """Niveau, origine, ligne, message."""
    table = window.validation_table
    return [[table.item(row, column).text() for column in (0, 1, 2, 4)] for row in range(table.rowCount())]


def _errors(window):
    return sum(1 for row in _rows(window) if row[0] == tr("rng.level.error"))


def _checked(qtbot, window, text):
    qtbot.waitUntil(lambda: window.rng_status.text() == text, timeout=60_000)


# --- Vérification ---------------------------------------------------------------------

@needs_saxon
def test_f8_checks_the_displayed_rules_and_lists_their_errors(open_window, with_rules):
    window = open_window(with_rules(XPATH))
    assert window.action_validate_rng.text() == tr("toolbar.validate_rng")
    _show(window)
    assert window.action_validate_rng.text() == tr("schematron_check.action")
    assert window.action_validate_rng.toolTip() == tr("schematron_check.action.tip")
    assert window.validation_title.text() == tr("schematron_check.panel.title")
    window.action_validate_rng.trigger()                               # F8 : attend le résultat
    assert window.validation_panel.isVisible()
    [(level, origin, line, message)] = _rows(window)
    assert (level, origin, line) == (tr("rng.level.error"), tr("rng.origin.schematron_rules"), "6")
    assert message.startswith(tr("schematron.rules.xpath", detail="").strip())
    assert window.rng_status.text() == tr("schematron_check.status.invalid", count=1)
    assert window.validation_summary.text() == tr("schematron_check.panel.invalid", count=1)
    assert window.document.health == "rng_invalid"

    window.goto_validation_issue(0)
    assert window.editor.textCursor().blockNumber() == 5                # ligne 6

    # L'édition garde sa validation RELAX NG.
    window.show_document(window.edition_session)
    assert window.action_validate_rng.text() == tr("toolbar.validate_rng")
    assert window.validation_title.text() == tr("rng.panel.title")


def test_a_structure_error_is_listed_at_its_line(open_window, with_rules):
    window = open_window(with_rules(STRUCTURE))
    _show(window)
    window.action_validate_rng.trigger()
    # Une seule erreur, à sa ligne, sans les messages en cascade de libxml2.
    assert _rows(window) == [[tr("rng.level.error"), tr("rng.origin.schematron_rules"), "5",
                              tr("schematron.rules.attribute", name="sorte", parent="sch:rule")]]
    assert window.rng_status.text() == tr("schematron_check.status.invalid", count=1)
    assert window.document.health == "rng_invalid"


def test_correct_rules_are_reported_as_such(open_window, with_rules):
    window = open_window(with_rules(GOOD))
    _show(window)
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("schematron_check.status.valid")
    assert window.statusBar().currentMessage() == tr("schematron_check.message.valid")
    assert _rows(window) == []
    assert window.document.health == "normal"
    if importlib.util.find_spec("saxonche") is not None:
        assert window.validation_summary.text() == tr("schematron_check.panel.valid")


def test_malformed_rules_are_reported(open_window, with_rules):
    window = open_window(with_rules(GOOD.replace("</sch:rule>", "</sch:regle>")))
    _show(window)
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("schematron_check.status.malformed")
    assert window.validation_summary.text() == tr("schematron_check.panel.malformed")
    assert "7" in [row[2] for row in _rows(window)]


@needs_saxon
def test_the_first_display_checks_without_waiting(open_window, with_rules, qtbot):
    window = open_window(with_rules(XPATH))
    _show(window)
    _checked(qtbot, window, tr("schematron_check.status.invalid", count=1))
    assert window.document.health == "rng_invalid"
    assert not window.validation_panel.isVisible()                    # automatique : panneau fermé

    # Retour au fichier : le résultat est gardé.
    window.show_document(window.edition_session)
    _show(window)
    assert window.rng_status.text() == tr("schematron_check.status.invalid", count=1)
    assert len(_rows(window)) == 1


@needs_saxon
def test_after_f8_typing_checks_again(open_window, with_rules, qtbot):
    window = open_window(with_rules(GOOD))
    _show(window)
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("schematron_check.status.valid")
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index('" severity'))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("[")
    _checked(qtbot, window, tr("schematron_check.status.invalid", count=1))
    assert [row[2] for row in _rows(window)] == ["6"]


@needs_saxon
def test_saving_rules_with_errors_asks_first(open_window, with_rules, dialogs, qtbot):
    project = with_rules(GOOD)
    path = project.parent / "xml" / "regles.sch"
    window = open_window(project)
    _show(window)
    _checked(qtbot, window, tr("schematron_check.status.valid"))
    window.editor.selectAll()
    window.editor.insertPlainText(XPATH)
    dialogs.expect("box", ROLE.RejectRole)                             # Annuler
    assert not window.save()
    kind, title, text = dialogs.seen[-1]
    assert title == tr("file.save_schematron_invalid.title")
    assert text == tr("file.save_schematron_invalid.text", count=1)
    assert path.read_text(encoding="utf-8") == GOOD


def test_without_saxon_only_the_structure_is_checked(open_window, with_rules, monkeypatch):
    import schematron
    import validation_worker
    import xslt_engines
    from validation_worker import RelaxNGWorkerClient
    # Vérification dans Varians même (processus indisponible), sans Saxon.
    project = with_rules(XPATH)
    client = RelaxNGWorkerClient([str(project.parent / "absent")])
    monkeypatch.setattr(validation_worker, "_client", client)
    monkeypatch.setattr(xslt_engines, "_SAXON", None)
    monkeypatch.setitem(sys.modules, "saxonche", None)
    schematron.clear_cache()
    window = open_window(project)
    _show(window)
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("schematron_check.status.valid")
    assert tr("schematron_check.panel.saxon_missing") in window.validation_summary.text()
    assert _rows(window) == [] and window.document.health == "normal"


# --- Ajout et création ----------------------------------------------------------------

@pytest.fixture
def file_dialog_calls(monkeypatch):
    calls = []

    def _set(path):
        def answer(*args, **kwargs):
            calls.append(args)
            return (str(path), "") if path else ("", "")
        monkeypatch.setattr(QFileDialog, "getOpenFileName", staticmethod(answer))
        monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(answer))
        return calls
    return _set


def _declared(project):
    return [document.path for document in load_project(project).documents]


def test_an_outside_rules_file_is_copied_into_xml(open_window, example_project, file_dialog_calls, tmp_path):
    outside = tmp_path / "ailleurs" / "apparat.sch"
    outside.parent.mkdir()
    outside.write_text(GOOD, encoding="utf-8")
    window = open_window(example_project)
    calls = file_dialog_calls(outside)
    assert window.add_document_dialog()
    (_parent, _title, _folder, filters), = calls
    assert "Schematron (*.sch)" in filters.split(";;")
    copy = example_project.parent / "xml" / "apparat.sch"
    assert copy.read_text(encoding="utf-8") == GOOD
    assert _declared(example_project) == [copy]
    assert window.document.path == copy
    assert window.action_validate_rng.text() == tr("schematron_check.action")


def test_a_new_rules_file_is_created_in_xml_declared_displayed_and_correct(open_window, example_project,
                                                                          file_dialog_calls):
    window = open_window(example_project)
    assert window.action_new_schematron.text() == tr("documents.new_schematron.menu")
    actions = window.documents_menu.actions()
    assert actions.index(window.action_new_schematron) == actions.index(window.action_new_stylesheet) + 1
    target = example_project.parent / "xml" / "apparat.sch"
    calls = file_dialog_calls(target)
    assert window.new_schematron_dialog()
    (_parent, title, proposed, filters), = calls
    assert title == tr("documents.new_schematron.title")
    assert Path(proposed) == example_project.parent / "xml" / "regles.sch"
    assert filters == "Schematron (*.sch)"
    root = ET.parse(target).getroot()
    assert root.tag == f"{{{SCH_NS}}}schema" and root.get("queryBinding") == "xslt2"
    assert tr("documents.new_schematron.example") in target.read_text(encoding="utf-8")
    assert _declared(example_project) == [target]
    assert window.document.path == target and not window.document.modified
    window.action_validate_rng.trigger()
    assert window.rng_status.text() == tr("schematron_check.status.valid")


def test_a_new_rules_file_receives_the_sch_suffix_and_never_overwrites(open_window, example_project,
                                                                       file_dialog_calls, dialogs):
    window = open_window(example_project)
    file_dialog_calls(example_project.parent / "xml" / "controle")
    assert window.new_schematron_dialog()
    target = example_project.parent / "xml" / "controle.sch"
    assert _declared(example_project) == [target]
    text = target.read_text(encoding="utf-8")
    file_dialog_calls(target)
    dialogs.expect("warning")
    assert not window.new_schematron_dialog()
    assert target.read_text(encoding="utf-8") == text
    file_dialog_calls(None)
    assert not window.new_schematron_dialog()
