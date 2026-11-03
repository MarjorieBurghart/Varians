# -*- coding: utf-8 -*-
"""Red team (sécurité, B2) dans la fenêtre : des règles Schematron qu'un
document déclare hors du dossier du projet ne sont appliquées qu'avec
l'accord de l'utilisatrice. La question est posée une fois et la réponse
mémorisée ; des règles refusées ne sont plus demandées par la validation
automatique, mais Valider (F8) repose la question."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

from app_context import rules_choice, tr
from test_gui_schematron import RULES, _declare_rules, _insert_after, needs_saxon

WRONG_KIND = '<varianstest kind="z">x</varianstest>'


def _declare_outside(project, tmp_path):
    """Les règles de test dans ailleurs/regles.sch, hors du projet, déclarées
    par l'édition avec un chemin relatif."""
    outside = tmp_path / "ailleurs" / "regles.sch"
    outside.parent.mkdir()
    outside.write_text(RULES, encoding="utf-8")
    _declare_rules(project).unlink()
    edition = project.parent / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace(
        'href="regles.sch"', 'href="../../ailleurs/regles.sch"'), encoding="utf-8")
    return outside.resolve()


def _boxes(dialogs):
    return [seen for seen in dialogs.seen if seen[0] == "box"]


@needs_saxon
def test_rules_outside_the_project_are_applied_only_once_accepted(open_window, example_project, tmp_path,
                                                                   dialogs):
    outside = _declare_outside(example_project, tmp_path)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    window = open_window(example_project)
    [(_kind, title, text)] = _boxes(dialogs)
    assert title == tr("schematron.outside.title") and str(outside) in text
    assert rules_choice(outside) is False

    # Refusées : la règle n'est pas appliquée, et la validation automatique
    # ne redemande pas.
    _insert_after(window, "<body>", WRONG_KIND)
    window.validate_relaxng_document(automatic=True)
    assert window._last_rng_result.valid
    assert window.schematron_status.text() == tr("schematron.status.refused")
    assert tr("schematron.tip.refused", files=str(outside)) in window.schematron_status.toolTip()
    assert len(_boxes(dialogs)) == 1

    # F8 repose la question ; acceptées, elles s'appliquent.
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    window.validate_relaxng_manual()
    assert len(_boxes(dialogs)) == 2 and rules_choice(outside) is True
    assert not window._last_rng_result.valid
    assert window.schematron_status.text() == tr("schematron.status.errors", count=1)

    # Mémorisé : plus de question, même avec F8.
    window.validate_relaxng_manual()
    assert len(_boxes(dialogs)) == 2 and not window._last_rng_result.valid


@needs_saxon
def test_rules_in_the_project_are_applied_without_a_question(open_window, example_project, dialogs):
    _declare_rules(example_project)
    window = open_window(example_project)
    _insert_after(window, "<body>", WRONG_KIND)
    window.validate_relaxng_manual()
    assert not _boxes(dialogs)
    assert window.schematron_status.text() == tr("schematron.status.errors", count=1)
