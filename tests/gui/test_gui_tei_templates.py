# -*- coding: utf-8 -*-
"""Mises à jour des squelettes de document de la TEI (tei_templates_ui) :
bouton « Modèles TEI… » de la boîte « Nouveau document XML », fenêtre qui
montre la version de TEI P5, son origine, son dossier, sa licence et la
dernière vérification ; « Rechercher une mise à jour » ; vérification au
lancement au plus une fois par mois, silencieuse sans nouveauté ; nouvelle
version installée avec l'accord de l'utilisateur, avec Annuler.

Le site de la TEI est remplacé par un faux (``FakeTeiP5``) : les fonctions
réseau elles-mêmes sont essayées dans tests/test_tei_templates.py."""
from __future__ import annotations

import datetime
import time
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox, QPushButton

import document_templates
import tei_templates
import tei_templates_ui
from app_context import _settings, tr
from tei_stylesheets import LibraryError

ROLE = QMessageBox.ButtonRole
NEW = "4.13.0"
TEMPLATE = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>{}</p></body></text></TEI>'


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Bibliothèque propre au test, vide : les squelettes livrés servent."""
    folder = tmp_path / "squelettes"
    monkeypatch.setenv(tei_templates.ENVIRONMENT, str(folder))
    return folder


class FakeTeiP5:
    """Le site de la TEI : sa dernière version et ses squelettes. ``hold`` :
    la lecture attend Annuler."""

    def __init__(self, monkeypatch, latest=NEW, error=None, hold=False):
        self.latest, self.error, self.hold = latest, error, hold
        self.checks, self.downloads = 0, []
        monkeypatch.setattr(tei_templates, "latest_version", self.latest_version)
        monkeypatch.setattr(tei_templates, "download", self.download)

    def latest_version(self, *args, **kwargs):
        self.checks += 1
        if self.error:
            raise LibraryError(self.error, "hors ligne")
        return self.latest

    def download(self, version, progress=None, cancel=None, **kwargs):
        self.downloads.append(version)
        progress(0, 4)
        if self.hold:
            while not cancel():
                time.sleep(0.01)
            raise LibraryError("cancelled")
        files = {f"{name}.xml": TEMPLATE.format(name).encode("utf-8") for name in ("All", "Lite", "Nouveau")}
        progress(4, 4)
        return files, b"Licence du TEI Consortium"


def _last_check():
    return _settings().value(tei_templates_ui.LAST_CHECK_SETTING, "")


def _in_window(qtbot, action):
    """Réponse à la fenêtre « Modèles de document TEI » : ``action(dialog)``,
    puis attendre la fin de la vérification et de l'installation, puis Fermer."""
    def answer(dialog):
        answer.dialog = dialog
        action(dialog)
        qtbot.waitUntil(lambda: not tei_templates_ui.busy(), timeout=20_000)
        answer.seen = dialog.state()
        answer.can_check_again = dialog.check_btn.isEnabled()
        dialog.reject()
        return dialog.result()
    return answer


def _through_new_document(qtbot, inner, after=None):
    """Réponse à la boîte « Nouveau document XML » : clic sur « Modèles
    TEI… » (sa fenêtre reçoit ``inner``), puis ``after(boîte)``, puis Annuler."""
    def answer(dialog):
        answer.before = dialog.tei_group_title()
        dialog.tei_templates_button.click()
        answer.after = dialog.tei_group_title()
        answer.names = dialog.tei_template_names()
        if after is not None:
            after(dialog)
        return 0
    return answer


# --- La fenêtre, depuis « Nouveau document XML » -------------------------------------------------

def test_the_new_document_dialog_opens_the_window(open_window, example_project, dialogs, qtbot, library):
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: None)
    outer = _through_new_document(qtbot, look)
    dialogs.expect("dialog", outer)
    dialogs.expect("dialog", look)
    window.new_document_dialog()
    assert dialogs.seen[1][1] == tr("tei_templates.title")
    assert look.seen == {"version": "4.12.0", "source": tr("tei_templates.source.bundled"),
                         "folder": str(tei_templates.BUNDLED_DIR), "checked": tr("tei_stylesheets.never")}
    assert outer.before == outer.after == tr("documents.new.group.tei", version="4.12.0")


def test_the_templates_are_already_up_to_date(open_window, example_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiP5(monkeypatch, latest="4.12.0")
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", _through_new_document(qtbot, look))
    dialogs.expect("dialog", look)
    dialogs.expect("information")
    window.new_document_dialog()
    assert dialogs.seen[-1][2] == tr("tei_templates.up_to_date", version="4.12.0")
    assert fake.checks == 1 and fake.downloads == []
    assert look.seen["checked"] == datetime.date.today().isoformat()


def test_a_network_error_is_reported(open_window, example_project, dialogs, qtbot, library, monkeypatch):
    FakeTeiP5(monkeypatch, error="network")
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", _through_new_document(qtbot, look))
    dialogs.expect("dialog", look)
    dialogs.expect("warning")
    window.new_document_dialog()
    assert dialogs.seen[-1][2] == tr("tei_templates.error.network", detail="hors ligne")


def test_a_new_version_is_installed_with_consent_and_serves_at_once(open_window, example_project, dialogs, qtbot,
                                                                    library, monkeypatch):
    fake = FakeTeiP5(monkeypatch)
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    outer = _through_new_document(qtbot, look)
    dialogs.expect("dialog", outer)
    dialogs.expect("dialog", look)
    dialogs.expect("box", ROLE.AcceptRole)                           # Installer
    window.new_document_dialog()
    question = [seen for seen in dialogs.seen if seen[0] == "box"][0]
    assert question[2] == tr("tei_templates.available", version=NEW, current="4.12.0")
    assert fake.downloads == [NEW]
    current = tei_templates.current()
    assert current.version == NEW and current.source == "downloaded"
    assert look.seen["version"] == NEW and look.can_check_again
    assert look.seen["source"] == tr("tei_templates.source.downloaded", date=datetime.date.today().isoformat())
    # La boîte « Nouveau document XML » montre aussitôt les nouveaux squelettes.
    assert outer.after == tr("documents.new.group.tei", version=NEW)
    assert outer.names == ["All", "Lite", "Nouveau"]
    assert window.statusBar().currentMessage() == tr("tei_templates.installed", version=NEW)
    assert document_templates.tei_templates_version() == NEW


def test_later_installs_nothing(open_window, example_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiP5(monkeypatch)
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", _through_new_document(qtbot, look))
    dialogs.expect("dialog", look)
    dialogs.expect("box", ROLE.RejectRole)                           # Plus tard
    window.new_document_dialog()
    assert fake.downloads == [] and tei_templates.current().source == "bundled"


def test_the_download_can_be_cancelled(open_window, example_project, dialogs, qtbot, library, monkeypatch):
    FakeTeiP5(monkeypatch, hold=True)
    window = open_window(example_project)

    def check_then_cancel(dialog):
        dialog.check_btn.click()
        qtbot.waitUntil(lambda: tei_templates_ui.progress_dialog() is not None, timeout=10_000)
        tei_templates_ui.progress_dialog().findChild(QPushButton).click()          # Annuler

    look = _in_window(qtbot, check_then_cancel)
    dialogs.expect("dialog", _through_new_document(qtbot, look))
    dialogs.expect("dialog", look)
    dialogs.expect("box", ROLE.AcceptRole)
    window.new_document_dialog()
    assert tei_templates.current().source == "bundled"
    assert not library.exists() or not any(path.name[0].isdigit() for path in library.iterdir())
    assert window.statusBar().currentMessage() == tr("tei_templates.cancelled")


def test_refused_templates_keep_the_current_ones(open_window, example_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiP5(monkeypatch)
    monkeypatch.setattr(tei_templates, "download",
                        lambda version, progress=None, cancel=None, **kw: ({"Lite.xml": b"<TEI/>"}, b"licence"))
    window = open_window(example_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", _through_new_document(qtbot, look))
    dialogs.expect("dialog", look)
    dialogs.expect("box", ROLE.AcceptRole)
    dialogs.expect("warning")
    window.new_document_dialog()
    assert dialogs.seen[-1][2].startswith(tr("tei_templates.error.invalid_archive", detail="\0").split("\0")[0])
    assert tei_templates.current().source == "bundled" and fake.checks == 1


# --- Au lancement --------------------------------------------------------------------------------

def _launch(qtbot, window):
    tei_templates_ui.at_launch(window)
    qtbot.waitUntil(lambda: not tei_templates_ui.busy(), timeout=20_000)


def test_the_launch_proposes_a_new_version_once_a_month(open_window, example_project, dialogs, qtbot, library,
                                                        monkeypatch):
    fake = FakeTeiP5(monkeypatch)
    window = open_window(example_project)
    dialogs.expect("box", ROLE.RejectRole)                           # Plus tard
    _launch(qtbot, window)
    assert fake.checks == 1 and dialogs.seen[-1][2] == tr("tei_templates.available", version=NEW, current="4.12.0")
    assert _last_check() == datetime.date.today().isoformat()
    _launch(qtbot, window)                                           # le même jour : rien
    assert fake.checks == 1
    _settings().setValue(tei_templates_ui.LAST_CHECK_SETTING,
                         (datetime.date.today() - datetime.timedelta(days=10)).isoformat())
    _launch(qtbot, window)
    assert fake.checks == 1
    _settings().setValue(tei_templates_ui.LAST_CHECK_SETTING,
                         (datetime.date.today() - datetime.timedelta(days=30)).isoformat())
    dialogs.expect("box", ROLE.AcceptRole)                           # Installer
    _launch(qtbot, window)
    assert fake.checks == 2 and fake.downloads == [NEW] and tei_templates.current().version == NEW


@pytest.mark.parametrize("latest, error", [(None, "network"), ("4.12.0", None)])
def test_the_launch_says_nothing_without_news(open_window, example_project, dialogs, qtbot, library, monkeypatch,
                                             latest, error):
    fake = FakeTeiP5(monkeypatch, latest=latest, error=error)
    window = open_window(example_project)
    _launch(qtbot, window)                                           # aucune boîte attendue
    assert fake.checks == 1 and _last_check() == datetime.date.today().isoformat()


def test_the_launch_removes_the_old_versions(open_window, example_project, qtbot, library, monkeypatch):
    FakeTeiP5(monkeypatch, latest=NEW)
    files = {"All.xml": TEMPLATE.format("All").encode("utf-8")}
    tei_templates.install(files, b"licence", "4.12.5")
    newer = tei_templates.install(files, b"licence", NEW)
    _settings().setValue(tei_templates_ui.LAST_CHECK_SETTING, datetime.date.today().isoformat())
    window = open_window(example_project)
    _launch(qtbot, window)
    assert sorted(path.name for path in library.iterdir()) == [NEW] and tei_templates.current() == newer


def test_varians_checks_the_templates_at_launch():
    source = (Path(__file__).resolve().parents[2] / "editeur_tei.py").read_text(encoding="utf-8")
    assert "tei_templates_at_launch(win)" in source


def test_each_error_has_a_message_in_the_seven_catalogs():
    import xml.etree.ElementTree as ET
    root = Path(__file__).resolve().parents[2] / "i18n"
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        catalog = {string.get("key") for string in ET.parse(root / f"{language}.xml").getroot().findall("string")}
        assert {f"tei_templates.error.{code}" for code in tei_templates_ui.ERROR_CODES} <= catalog, language
