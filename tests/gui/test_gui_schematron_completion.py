# -*- coding: utf-8 -*-
"""Complétion d'un fichier Schematron dans Varians (V0.9.2.4) : Ctrl+Espace,
liste automatique des attributs et Ctrl+E proposent les éléments et
attributs Schematron, avec le préfixe du fichier, sans les éléments TEI ni
les éléments personnalisés du projet ; valeurs de ``severity``."""
from __future__ import annotations

import pytest

from project_config import DocumentConfig, load_project
from project_management import update_project_documents

SCH_NS = "http://purl.oclc.org/dsdl/schematron"
HEAD = f'<?xml version="1.0" encoding="UTF-8"?>\n<sch:schema xmlns:sch="{SCH_NS}" queryBinding="xslt2">\n'


@pytest.fixture
def rules_window(open_window, example_project):
    """Fenêtre qui affiche xml/regles.sch, document du projet d'exemple."""
    def _open(body):
        path = example_project.parent / "xml" / "regles.sch"
        path.write_text(HEAD + body + "</sch:schema>\n", encoding="utf-8")
        update_project_documents(example_project,
                                 list(load_project(example_project).documents) + [DocumentConfig(path)])
        window = open_window(example_project)
        session = next(s for s in window.documents if s.path == path)
        assert window.show_document(session)
        return window
    return _open


def _cursor_after(window, marker, typed=""):
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(text.index(marker) + len(marker))
    window.editor.setTextCursor(cursor)
    if typed:
        window.editor.insertPlainText(typed)


def _proposals(dialogs, window, choose=None):
    """Propositions de Ctrl+Espace ; ``choose`` : la proposition à insérer."""
    proposed = []

    def answer(dialog):
        proposed.extend(dialog.list_widget.item(i).data(0x0100) for i in range(dialog.list_widget.count()))
        if choose is None:
            return 0                                          # Échap
        dialog.list_widget.setCurrentRow(proposed.index(choose))
        dialog._accept_current()
        return dialog.result()

    dialogs.expect("dialog", answer)
    window.show_rng_completion(window.editor)
    return proposed


def test_ctrl_space_proposes_schematron_elements_with_the_prefix(rules_window, dialogs):
    window = rules_window('  <sch:pattern>\n  </sch:pattern>\n')
    _cursor_after(window, "<sch:pattern>")
    proposed = _proposals(dialogs, window, choose="sch:rule")
    assert {"sch:rule", "sch:let", "sch:title", "sch:p"} <= set(proposed)
    assert not {"app", "rdg", "teiHeader", "varianstest"} & set(proposed)    # TEI, personnalisés : non
    assert "<sch:pattern><sch:rule></sch:rule>" in window.editor.toPlainText()


def test_attributes_and_values_of_an_assertion(rules_window, dialogs):
    window = rules_window('  <sch:pattern>\n    <sch:rule context="x">\n      <sch:assert >m</sch:assert>\n'
                          '    </sch:rule>\n  </sch:pattern>\n')
    _cursor_after(window, "<sch:assert ")
    proposed = _proposals(dialogs, window)
    assert {"test", "role", "severity"} <= set(proposed) and "context" not in proposed
    window.editor.insertPlainText('severity=""')
    cursor = window.editor.textCursor()
    cursor.setPosition(cursor.position() - 1)                         # entre les guillemets
    window.editor.setTextCursor(cursor)
    proposed = _proposals(dialogs, window, choose="warning")
    assert {"error", "warning", "info"} <= set(proposed)
    assert '<sch:assert severity="warning"' in window.editor.toPlainText()


def test_the_attribute_list_opens_while_typing(rules_window):
    window = rules_window('  <sch:pattern>\n    <sch:rule >\n    </sch:rule>\n  </sch:pattern>\n')
    _cursor_after(window, "<sch:rule ", "c")
    names, _context = window._auto_attribute_choices(window.editor)
    assert names == ("context",)


def test_ctrl_e_proposes_schematron_elements(rules_window):
    window = rules_window('  <sch:pattern>\n  </sch:pattern>\n')
    _cursor_after(window, "<sch:pattern>")
    names = [name for name, _source in window.rng_element_suggestions(window.editor)]
    assert "sch:rule" in names and "app" not in names and "varianstest" not in names
