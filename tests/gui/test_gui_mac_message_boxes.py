# -*- coding: utf-8 -*-
"""Titre des boîtes de message sous macOS (V0.9.4.6).

Sous macOS, Qt n'affiche pas le titre d'une boîte de message
(``QMessageBox.setWindowTitle`` n'y fait rien, selon les règles d'Apple) :
« Document non valide », « Fichier très volumineux »… n'étaient pas vus.
Sous macOS, ``mac_message_boxes`` fait du titre le message principal (en
gras) et passe le texte en dessous, comme une alerte du Mac ; ailleurs,
rien ne change. Ici, le comportement de Qt sous macOS est simulé :
``setWindowTitle`` ne retient rien."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication, QMessageBox

import mac_message_boxes as mac

BUTTON = QMessageBox.StandardButton


@pytest.fixture
def macos(qapp, monkeypatch):
    """Qt comme sous macOS (le titre n'est pas retenu), puis la couche de
    Varians par-dessus."""
    monkeypatch.setattr(QMessageBox, "setWindowTitle", lambda box, title: None)
    for name, value in mac.wrappers().items():
        monkeypatch.setattr(QMessageBox, name, value)


def _answer(button, seen):
    """Relève la boîte affichée (texte, texte informatif, titre), puis clique
    sur ``button``."""
    def close():
        box = QApplication.activeModalWidget()
        seen.append((box.text(), box.informativeText(), mac.title_of(box)))
        box.button(button).click()
    QTimer.singleShot(0, close)


def test_the_title_becomes_the_main_message(macos):
    box = QMessageBox()
    box.setWindowTitle("Document non valide")
    box.setText("Le document est bien formé, mais la validation signale 1 erreur.")
    box.setInformativeText("Enregistrer quand même ?")
    box.setStandardButtons(BUTTON.Save | BUTTON.Cancel)
    assert box.windowTitle() == ""                                    # comme sous macOS
    seen = []
    _answer(BUTTON.Cancel, seen)
    box.exec()
    assert seen == [("Document non valide",
                     "Le document est bien formé, mais la validation signale 1 erreur.\n\nEnregistrer quand même ?",
                     "Document non valide")]


def test_a_box_shown_twice_is_not_changed_twice(macos):
    box = QMessageBox()
    box.setWindowTitle("Titre")
    box.setText("Texte")
    seen = []
    for _ in range(2):
        _answer(BUTTON.Ok, seen)
        box.exec()
    assert seen == [("Titre", "Texte", "Titre")] * 2


def test_a_rich_text_title_is_escaped(macos):
    from PySide6.QtCore import Qt
    box = QMessageBox()
    box.setTextFormat(Qt.TextFormat.RichText)
    box.setWindowTitle("Règles <sch> & schéma")
    box.setText("<b>Texte</b>")
    mac.present(box)
    assert box.text() == "Règles &lt;sch&gt; &amp; schéma" and box.informativeText() == "<b>Texte</b>"


@pytest.mark.parametrize("name, buttons, default, click", [
    ("question", BUTTON.Yes | BUTTON.No, BUTTON.Yes, BUTTON.No),
    ("warning", BUTTON.Save | BUTTON.Discard | BUTTON.Cancel, BUTTON.Save, BUTTON.Discard),
    ("critical", None, None, BUTTON.Ok),
    ("information", None, None, BUTTON.Ok),
])
def test_a_ready_made_box_shows_its_title_and_returns_the_button(macos, name, buttons, default, click):
    seen = []
    _answer(click, seen)
    args = [None, "Enregistrer ?", "Le fichier a changé hors de Varians."]
    if buttons is not None:
        args += [buttons, default]
    assert getattr(QMessageBox, name)(*args) == click
    assert seen == [("Enregistrer ?", "Le fichier a changé hors de Varians.", "Enregistrer ?")]


def test_the_default_buttons_of_a_question_are_yes_and_no(macos):
    seen = []

    def close():
        box = QApplication.activeModalWidget()
        seen.append(sorted(box.button(b) is not None for b in (BUTTON.Yes, BUTTON.No)))
        box.button(BUTTON.Yes).click()
    QTimer.singleShot(0, close)
    assert QMessageBox.question(None, "Titre", "Texte") == BUTTON.Yes
    assert seen == [[True, True]]


def test_elsewhere_nothing_changes(qapp):
    assert mac.install("linux") is False and mac.install("win32") is False
    assert QMessageBox.setWindowTitle is not None and not mac.installed()


def test_the_application_installs_it_at_startup():
    from varians_source import application_source
    import editeur_tei
    assert "mac_message_boxes.install()" in application_source()
    assert "mac_message_boxes" in editeur_tei._LOCAL_MODULE_NAMES


def test_the_dialog_script_of_the_tests_reads_the_title_qt_forgets(macos, dialogs):
    """Sous macOS, les tests relevaient un titre vide : le script des boîtes
    lit le titre retenu par Varians."""
    box = QMessageBox()
    box.setWindowTitle("Fichier très volumineux")
    box.setText("Ouvrir quand même ?")
    box.addButton(QMessageBox.StandardButton.Cancel)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    box.exec()
    assert dialogs.seen[-1] == ("box", "Fichier très volumineux", "Ouvrir quand même ?")
