# -*- coding: utf-8 -*-
"""Red team 2 (robustesse) : un projet s'ouvre malgré un fichier abîmé.

- B5 : un JSON d'alignement abîmé empêchait d'ouvrir le projet, avec un
  message brut. Le projet s'ouvre ; seule la synchronisation de ce témoin
  est coupée ; un message traduit nomme le fichier et l'endroit fautif.
- B2 : un U+2029 du fichier devenait un saut de ligne à l'enregistrement ;
  il est écrit « &#x2029; » à l'ouverture, et c'est signalé."""
from __future__ import annotations

from pathlib import Path


def test_a_damaged_secondary_alignment_cuts_only_its_witness(open_window, example_project, dialogs):
    path = Path(example_project).parent / "alignments" / "T2.json"
    path.write_text('{"pages": [}', encoding="utf-8")
    dialogs.expect("warning")
    window = open_window(example_project)
    window.show()
    from PySide6.QtWidgets import QApplication
    for _ in range(5):
        QApplication.processEvents()
    kind, title, text = dialogs.seen[-1]
    assert kind == "warning" and "T2.json" in text and "T2" in text
    assert "1" in text and "12" in text                          # ligne et colonne
    assert window._secondary_sync_link_counts["T2"] == 0
    assert window.base_alignment_available                    # le pivot reste synchronisé
    assert window._secondary_sync_link_counts["P"] > 0


def test_a_damaged_pivot_alignment_opens_the_project_without_line_sync(open_window, example_project, dialogs):
    path = Path(example_project).parent / "alignments" / "T1.json"
    path.write_text('{"pages": [{"id": "1r", "lines": [{"line": 1, "base_keys": [3]}]}]}', encoding="utf-8")
    dialogs.expect("warning")
    window = open_window(example_project)
    window.show()
    from PySide6.QtWidgets import QApplication
    for _ in range(5):
        QApplication.processEvents()
    _kind, _title, text = dialogs.seen[-1]
    assert "T1.json" in text and "base_keys" in text
    assert not window.base_alignment_available


def test_a_paragraph_separator_is_kept_as_a_character_reference(open_window, example_project, dialogs):
    edition = Path(example_project).parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace("<body>", "<body><!-- -->\n<p>un deux</p>", 1), encoding="utf-8")
    dialogs.expect("information")
    window = open_window(example_project)
    window.show()
    from PySide6.QtWidgets import QApplication
    for _ in range(5):
        QApplication.processEvents()
    assert "U+2029" in dialogs.seen[-1][2]
    assert "<p>un&#x2029;deux</p>" in window.editor.toPlainText()
    assert " " not in window.editor.toPlainText()
