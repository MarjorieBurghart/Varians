# -*- coding: utf-8 -*-
"""Red team (intégrité, A3) : un fichier modifié hors de Varians depuis sa
lecture ou son dernier enregistrement (par un autre logiciel, une
synchronisation…) était écrasé sans un mot. L'enregistrement propose
désormais Écraser, Recharger ou Annuler."""
from __future__ import annotations

import os

from PySide6.QtWidgets import QMessageBox

from app_context import tr

MINE, THEIRS = "<!-- relu dans Varians -->", "<!-- modifié ailleurs -->"


def _edit(window, text=MINE):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("<body>") + len("<body>"))
    cursor.insertText(text)


def _change_on_disk(path):
    """Le fichier modifié par un autre logiciel ; renvoie son nouveau texte."""
    text = path.read_text(encoding="utf-8").replace("<body>", "<body>" + THEIRS, 1)
    path.write_text(text, encoding="utf-8")
    stat = path.stat()
    os.utime(path, ns=(stat.st_atime_ns, stat.st_mtime_ns + 2_000_000_000))
    return text


def _boxes(dialogs):
    return [seen for seen in dialogs.seen if seen[0] == "box"]


def test_saving_over_an_external_change_asks_first(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    window = open_window(example_project)
    _edit(window)
    theirs = _change_on_disk(edition)

    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)            # Annuler
    assert not window.save()
    [(_kind, title, text)] = _boxes(dialogs)
    assert title == tr("file.changed.title") and str(edition) in text
    assert edition.read_text(encoding="utf-8") == theirs and window.modified

    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)            # Écraser
    assert window.save()
    saved = edition.read_text(encoding="utf-8")
    assert MINE in saved and THEIRS not in saved
    assert edition.with_suffix(".xml.bak").read_text(encoding="utf-8") == theirs

    # Enregistré par Varians : plus de question.
    _edit(window, "<!-- encore -->")
    assert window.save() and len(_boxes(dialogs)) == 2


def test_reloading_shows_the_file_as_it_is_now(open_window, example_project, dialogs):
    edition = example_project.parent / "xml" / "edition.xml"
    window = open_window(example_project)
    _edit(window)
    theirs = _change_on_disk(edition)
    dialogs.expect("box", QMessageBox.ButtonRole.DestructiveRole)       # Recharger
    assert not window.save()
    assert window.editor.toPlainText() == theirs and not window.modified
    assert edition.read_text(encoding="utf-8") == theirs

    # Rechargé : enregistrer ne demande plus.
    _edit(window)
    assert window.save() and len(_boxes(dialogs)) == 1
    assert THEIRS in edition.read_text(encoding="utf-8") and MINE in edition.read_text(encoding="utf-8")


def test_an_unchanged_file_is_saved_without_a_question(open_window, example_project, dialogs):
    window = open_window(example_project)
    _edit(window)
    assert window.save()
    _edit(window, "<!-- encore -->")
    assert window.save() and not _boxes(dialogs)


def test_an_auxiliary_document_is_protected_too(open_window, project_with_documents, dialogs):
    personnes = project_with_documents.parent / "xml" / "personnes.xml"
    window = open_window(project_with_documents)
    session = next(s for s in window.documents if s.path is not None and s.path.name == "personnes.xml")
    assert window.show_document(session)
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.toPlainText().index("</listPerson>"))
    cursor.insertText("<!-- ici -->")
    text = personnes.read_text(encoding="utf-8").replace("Petrus", "Petrus Lombardus")
    personnes.write_text(text, encoding="utf-8")
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    assert not window.save()
    assert personnes.read_text(encoding="utf-8") == text
