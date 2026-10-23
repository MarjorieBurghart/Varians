# -*- coding: utf-8 -*-
"""Complétion d'une feuille XSLT dans Varians (V0.9.2.1) : Ctrl+Espace, liste
automatique des attributs et Ctrl+E proposent les éléments et attributs
XSLT, avec le préfixe de la feuille, sans les éléments TEI personnalisés du
projet ; un préfixe tapé (« <xsl:te ») filtre les noms qualifiés."""
from __future__ import annotations

import pytest

from app_context import tr
from project_config import DocumentConfig, load_project
from project_management import update_project_documents

HEAD = ('<xsl:stylesheet version="{version}" xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'
        ' xmlns:tei="http://www.tei-c.org/ns/1.0">\n')


@pytest.fixture
def stylesheet_window(open_window, sermons_project):
    """Fenêtre qui affiche la feuille xslt/index.xsl du projet « sermons »."""
    def _open(body, version="3.0"):
        root = sermons_project.parent
        (root / "xslt").mkdir(exist_ok=True)
        path = root / "xslt" / "index.xsl"
        path.write_text(HEAD.format(version=version) + body + "</xsl:stylesheet>\n", encoding="utf-8")
        update_project_documents(sermons_project, list(load_project(sermons_project).documents) + [DocumentConfig(path)])
        window = open_window(sermons_project)
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


def test_ctrl_space_proposes_xslt_instructions_with_the_prefix(stylesheet_window, dialogs):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n')
    _cursor_after(window, '<xsl:template match="/">')
    proposed = _proposals(dialogs, window, choose="xsl:apply-templates")
    assert {"xsl:apply-templates", "xsl:value-of", "xsl:param", "xsl:sequence"} <= set(proposed)
    assert not {"hi", "lb", "rdg", "teiHeader"} & set(proposed)      # éléments personnalisés TEI : non
    assert '<xsl:template match="/"><xsl:apply-templates></xsl:apply-templates>' in window.editor.toPlainText()


def test_a_literal_result_element_receives_instructions(stylesheet_window, dialogs):
    from PySide6.QtCore import Qt
    window = stylesheet_window('<xsl:template match="/"><div>\n</div></xsl:template>\n')
    _cursor_after(window, "<div>")
    labels = []
    dialogs.expect("dialog", lambda dialog: (labels.append((dialog.label.text(), dialog.label.textFormat())), 0)[1])
    window.show_rng_completion(window.editor)
    # Le nom du parent, entre chevrons, se lit tel quel (et non comme du HTML).
    assert labels == [(tr("completion.elements.label", parent="div"), Qt.TextFormat.PlainText)]
    proposed = _proposals(dialogs, window)
    assert {"xsl:value-of", "xsl:apply-templates"} <= set(proposed)
    assert "xsl:template" not in proposed and "xsl:param" not in proposed


def test_a_typed_prefix_filters_the_qualified_names(stylesheet_window, dialogs):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n')
    _cursor_after(window, '<xsl:template match="/">', "<xsl:va")
    proposed = _proposals(dialogs, window, choose="xsl:variable")
    assert proposed == ["xsl:value-of", "xsl:variable"]
    assert "<xsl:variable></xsl:variable>" in window.editor.toPlainText()
    assert "<<" not in window.editor.toPlainText()


def test_a_stylesheet_1_0_only_receives_xslt_1_0(stylesheet_window, dialogs):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n', version="1.0")
    _cursor_after(window, '<xsl:template match="/">')
    proposed = _proposals(dialogs, window)
    assert "xsl:value-of" in proposed and "xsl:sequence" not in proposed and "xsl:for-each-group" not in proposed


def test_attributes_of_an_xslt_element(stylesheet_window, dialogs):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n', version="1.0")
    _cursor_after(window, '<xsl:template match="/">', '<xsl:apply-templates >')
    cursor = window.editor.textCursor()
    cursor.setPosition(cursor.position() - 1)                         # avant « > »
    window.editor.setTextCursor(cursor)
    assert _proposals(dialogs, window) == ["mode", "select"]


def test_the_attribute_list_opens_while_typing(stylesheet_window):
    window = stylesheet_window('<xsl:template match="/">\n<xsl:value-of />\n</xsl:template>\n')
    _cursor_after(window, "<xsl:value-of ", "s")
    names, _context = window._auto_attribute_choices(window.editor)
    assert "select" in names and "separator" in names


def test_ctrl_e_proposes_xslt_elements(stylesheet_window):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n')
    _cursor_after(window, '<xsl:template match="/">')
    names = [name for name, _source in window.rng_element_suggestions(window.editor)]
    assert "xsl:value-of" in names and "hi" not in names


def test_the_edition_keeps_its_own_completion(stylesheet_window, dialogs):
    window = stylesheet_window('<xsl:template match="/">\n</xsl:template>\n')
    window.show_document(window.edition_session)
    text = window.editor.toPlainText()
    _cursor_after(window, text[text.index("<body"):].split(">", 1)[0] + ">")
    proposed = _proposals(dialogs, window)
    assert proposed and not [name for name in proposed if name.startswith("xsl:")]
