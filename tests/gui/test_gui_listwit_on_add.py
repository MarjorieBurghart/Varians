# -*- coding: utf-8 -*-
"""Paramètres du projet (V0.9.2.8.2) : un témoin ajouté est déclaré dans la
<listWit> existante de l'édition, et la boîte « paramètres enregistrés » le
dit. Sans <listWit>, l'édition ne change pas et la boîte le signale. Les
témoins qui étaient déjà dans le projet ne sont pas touchés."""
from __future__ import annotations

import xml.etree.ElementTree as ET

TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def _tr(key, **values):
    from app_context import tr
    return tr(key, **values)


def _add_witness(siglum, label):
    def settings(dialog):
        dialog.witnesses_table.add_witness()
        dialog._accept()
        return dialog.result()

    def witness(dialog):
        dialog.id_edit.setText(siglum)
        dialog.label_edit.setText(label)
        dialog._accept()
        return dialog.result()

    return settings, witness


def _save_settings(window, dialogs, siglum, label):
    settings, witness = _add_witness(siglum, label)
    dialogs.expect("dialog", settings)
    dialogs.expect("dialog", witness)
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    if new_window is not None:
        new_window._force_close = True
        new_window.close()
    return dialogs.seen[-1][2]


def test_an_added_witness_is_declared_in_the_listwit(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    before = edition.read_text(encoding="utf-8")
    window = open_window(example_project)
    message = _save_settings(window, dialogs, "1760", "Troyes 1760 (essai)")
    after = edition.read_text(encoding="utf-8")
    added = '<witness xml:id="_1760"><idno type="siglum">1760</idno>Troyes 1760 (essai)</witness>'
    assert after == before.replace('Latin 15940</witness></listWit>', f'Latin 15940</witness>{added}</listWit>')
    root = ET.fromstring(after.split("?>", 1)[1] if after.startswith("<?xml") else after)
    assert [w.get(XML_ID) for w in root.iter(f"{TEI}witness")] == ["T1", "T2", "P", "_1760"]
    assert message == _tr("project.settings.saved") + "\n\n" + _tr("project.listwit.added", witnesses="1760")
    assert (edition.parent / "edition.xml.bak").read_text(encoding="utf-8") == before


def test_without_listwit_the_edition_is_left_alone(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start, end = text.index("<listWit>"), text.index("</listWit>") + len("</listWit>")
    edition.write_text(text[:start] + text[end:], encoding="utf-8")
    before = edition.read_text(encoding="utf-8")
    window = open_window(example_project)
    message = _save_settings(window, dialogs, "Q", "Témoin Q")
    assert edition.read_text(encoding="utf-8") == before
    assert message == _tr("project.settings.saved") + "\n\n" + _tr("project.listwit.no_listwit", witnesses="Q")
