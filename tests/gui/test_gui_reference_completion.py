# -*- coding: utf-8 -*-
"""Ctrl+Espace dans un attribut de référence : identifiants des documents du projet."""
from __future__ import annotations

import pytest

from project_config import DocumentConfig, load_project
from project_management import update_project_documents

LIEUX = """<?xml version="1.0" encoding="UTF-8"?>
<listPlace xmlns="http://www.tei-c.org/ns/1.0">
  <place xml:id="clairvaux"><placeName>Clara Vallis</placeName></place>
</listPlace>
"""


@pytest.fixture
def project_with_authorities(project_with_documents):
    """personnes.xml (bernard, petrus) et lieux.xml (clairvaux)."""
    lieux = project_with_documents.parent / "xml" / "lieux.xml"
    lieux.write_text(LIEUX, encoding="utf-8")
    documents = list(load_project(project_with_documents).documents) + [DocumentConfig(lieux, "Lieux")]
    update_project_documents(project_with_documents, documents)
    return project_with_documents


def _type_in_body(window, markup, inside):
    """Insère ``markup`` après <body> et place le curseur après ``inside``."""
    text = window.editor.toPlainText()
    position = text.index("<body>") + len("<body>")
    cursor = window.editor.textCursor()
    cursor.setPosition(position)
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText(markup)
    cursor = window.editor.textCursor()
    cursor.setPosition(position + markup.index(inside) + len(inside))
    window.editor.setTextCursor(cursor)


def _proposals(dialogs, choose=None):
    seen = {}

    def answer(dialog):
        items = [dialog.list_widget.item(i) for i in range(dialog.list_widget.count())]
        seen.update((item.data(0x0100), item.text()) for item in items)
        if choose is None:
            return 0
        values = [item.data(0x0100) for item in items]
        dialog.list_widget.setCurrentRow(values.index(choose))
        dialog._accept_current()
        return dialog.result()

    dialogs.expect("dialog", answer)
    return seen


def test_person_name_proposes_the_persons_of_the_authority_file(open_window, project_with_authorities, dialogs):
    window = open_window(project_with_authorities)
    _type_in_body(window, '<persName ref=""></persName>', 'ref="')
    seen = _proposals(dialogs, choose="#bernard")
    window.show_rng_completion(window.editor)
    assert set(seen) == {"#bernard", "#petrus"}                   # ni lieux, ni citations
    assert "Bernardus — personnes.xml" in seen["#bernard"]
    assert '<persName ref="#bernard">' in window.editor.toPlainText()


def test_place_name_proposes_only_places(open_window, project_with_authorities, dialogs):
    window = open_window(project_with_authorities)
    _type_in_body(window, '<placeName ref="#"></placeName>', 'ref="#')
    seen = _proposals(dialogs)
    window.show_rng_completion(window.editor)
    assert set(seen) == {"#clairvaux"}
    assert "Clara Vallis — lieux.xml" in seen["#clairvaux"]


def test_typed_text_filters_on_the_label_too(open_window, project_with_authorities, dialogs):
    window = open_window(project_with_authorities)
    _type_in_body(window, '<placeName ref=""></placeName>', 'ref="')
    seen = []

    def answer(dialog):
        dialog.filter_box.setText("Clara")              # texte de l'entrée, pas l'identifiant
        seen.extend(dialog.list_widget.item(i).data(0x0100) for i in range(dialog.list_widget.count()))
        return 0

    dialogs.expect("dialog", answer)
    window.show_rng_completion(window.editor)
    assert seen == ["#clairvaux"]


def test_project_rule_in_custom_elements_restricts_the_list(open_window, project_with_authorities, dialogs):
    custom = project_with_authorities.parent / "rendering" / "custom-elements.xml"
    text = custom.read_text(encoding="utf-8").replace(
        "</customElements>",
        '<element name="name"><attribute name="ref" valuesMode="replace">'
        '<values source="ids" elements="place" prefix="#"/></attribute></element></customElements>')
    custom.write_text(text, encoding="utf-8")
    window = open_window(project_with_authorities)
    _type_in_body(window, '<name ref=""></name>', 'ref="')
    seen = _proposals(dialogs)
    window.show_rng_completion(window.editor)
    assert set(seen) == {"#clairvaux"}


def test_rdg_wit_keeps_the_project_witnesses(open_window, project_with_authorities, dialogs):
    window = open_window(project_with_authorities)
    _type_in_body(window, '<app><rdg wit=""></rdg></app>', 'wit="')
    seen = _proposals(dialogs)
    window.show_rng_completion(window.editor)
    assert set(seen) == {"#T1", "#T2", "#P"}
    assert "T1 · Troyes 816" in seen["#T1"]


def test_without_auxiliary_documents_the_document_identifiers_are_proposed(open_window, example_project, dialogs):
    window = open_window(example_project)
    _type_in_body(window, '<lem wit=""></lem>', 'wit="')
    seen = _proposals(dialogs)
    window.show_rng_completion(window.editor)
    # @wit vise les <witness> de la <listWit> de l'édition.
    assert set(seen) == {"#T1", "#T2", "#P"}
