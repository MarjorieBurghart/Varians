# -*- coding: utf-8 -*-
"""Paramètres du projet (V0.9.2.8.2) : un témoin ajouté est déclaré dans la
<listWit> existante de l'édition, et la boîte « paramètres enregistrés » le
dit. Sans <listWit>, Varians en crée une dans le <sourceDesc>. Quand la TEI
ne permet pas de déclarer un témoin ajouté (paragraphes à côté, identifiant
déjà pris…), l'ajout est refusé : la boîte dit quoi corriger, puis de revenir
l'ajouter. À chaque enregistrement, Varians propose de déclarer les témoins du
projet absents de la <listWit>."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from PySide6.QtWidgets import QMessageBox

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


def _save_settings(window, dialogs, siglum, label, undeclared=None):
    """``undeclared`` : réponse à la question sur les témoins du projet
    absents de la <listWit>, quand elle est posée."""
    settings, witness = _add_witness(siglum, label)
    dialogs.expect("dialog", settings)
    dialogs.expect("dialog", witness)
    if undeclared is not None:
        dialogs.expect("question", undeclared)
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


def test_without_listwit_one_is_created_in_the_source_description(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start, end = text.index("<listWit>"), text.index("</listWit>") + len("</listWit>")
    edition.write_text(text[:start] + text[end:], encoding="utf-8")
    window = open_window(example_project)
    # T1, T2 et P ne sont plus déclarés : Varians le propose ; ici, non.
    message = _save_settings(window, dialogs, "Q", "Témoin Q", undeclared=QMessageBox.StandardButton.No)
    after = edition.read_text(encoding="utf-8")
    root = ET.fromstring(after.split("?>", 1)[1] if after.startswith("<?xml") else after)
    (source_desc,) = root.iter(f"{TEI}sourceDesc")
    # Après le <msDesc> : <sourceDesc> n'a que des éléments structurés.
    assert [child.tag.split("}")[1] for child in source_desc][-2:] == ["msDesc", "listWit"]
    assert [w.get(XML_ID) for w in source_desc.find(f"{TEI}listWit")] == ["Q"]
    assert message == _tr("project.settings.saved") + "\n\n" + _tr("project.listwit.created", witnesses="Q")


def _blocked_settings(siglum, label):
    """« Paramètres du projet » : ajouter un témoin, enregistrer (refusé),
    puis fermer la boîte."""
    def settings(dialog):
        dialog.witnesses_table.add_witness()
        dialog._accept()
        accepted = dialog.result()
        dialog.reject()
        return accepted
    return settings


def test_next_to_paragraphs_the_addition_is_refused_until_corrected(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start = text.index(">", text.index("<sourceDesc")) + 1
    end = text.index("</sourceDesc>")
    edition.write_text(text[:start] + "<p>Transcription en cours</p>" + text[end:], encoding="utf-8")
    before, project_before = edition.read_text(encoding="utf-8"), example_project.read_text(encoding="utf-8")
    window = open_window(example_project)
    dialogs.expect("dialog", _blocked_settings("Q", "Témoin Q"))
    dialogs.expect("dialog", _add_witness("Q", "Témoin Q")[1])
    dialogs.expect("warning")
    window.project_settings_dialog()
    kind, title, message = dialogs.seen[-1]
    assert title == _tr("project.listwit.blocked.title")
    assert _tr("project.listwit.blocked.paragraphs") in message
    # Rien n'est enregistré : ni le témoin dans le projet, ni l'édition.
    assert edition.read_text(encoding="utf-8") == before
    assert example_project.read_text(encoding="utf-8") == project_before

    # L'utilisatrice remplace le paragraphe par un <bibl>, revient, et ajoute le témoin.
    edition.write_text(before.replace("<p>Transcription en cours</p>", "<bibl>Transcription en cours</bibl>"),
                       encoding="utf-8")
    message = _save_settings(window, dialogs, "Q", "Témoin Q", undeclared=QMessageBox.StandardButton.No)
    assert message == _tr("project.settings.saved") + "\n\n" + _tr("project.listwit.created", witnesses="Q")
    assert '<bibl>Transcription en cours</bibl>' in edition.read_text(encoding="utf-8")


def test_an_identifier_already_used_refuses_the_addition(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace("<body>", '<body><!-- --><ab xml:id="Q">x</ab>', 1), encoding="utf-8")
    window = open_window(example_project)
    dialogs.expect("dialog", _blocked_settings("Q", "Témoin Q"))
    dialogs.expect("dialog", _add_witness("Q", "Témoin Q")[1])
    dialogs.expect("warning")
    window.project_settings_dialog()
    assert _tr("project.listwit.blocked.id_used", witnesses="Q") in dialogs.seen[-1][2]


def _without_p(example_project):
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace('<witness xml:id="P">Paris, BnF, Latin 15940</witness>', ""), encoding="utf-8")
    return edition


def _save_unchanged(window, dialogs, answer):
    def settings(dialog):
        dialog._accept()
        return dialog.result()
    dialogs.expect("dialog", settings)
    dialogs.expect("question", answer)
    dialogs.expect("information")
    window.project_settings_dialog()
    new_window = window._replacement_window
    if new_window is not None:
        new_window._force_close = True
        new_window.close()


def test_undeclared_witnesses_are_proposed_at_each_save(open_window, example_project, dialogs):
    from PySide6.QtWidgets import QMessageBox
    edition = _without_p(example_project)
    window = open_window(example_project)
    _save_unchanged(window, dialogs, QMessageBox.StandardButton.Yes)
    question = next(seen for seen in dialogs.seen if seen[0] == "question")
    assert question[1:] == (_tr("project.listwit.missing.title"), _tr("project.listwit.missing", witnesses="P"))
    root = ET.fromstring(edition.read_text(encoding="utf-8").split("?>", 1)[1])
    assert [w.get(XML_ID) for w in root.iter(f"{TEI}witness")] == ["T1", "T2", "P"]
    assert dialogs.seen[-1][2] == _tr("project.settings.saved") + "\n\n" + _tr("project.listwit.added", witnesses="P")


def test_undeclared_witnesses_stay_so_when_refused(open_window, example_project, dialogs):
    from PySide6.QtWidgets import QMessageBox
    edition = _without_p(example_project)
    before = edition.read_text(encoding="utf-8")
    window = open_window(example_project)
    _save_unchanged(window, dialogs, QMessageBox.StandardButton.No)
    assert edition.read_text(encoding="utf-8") == before
