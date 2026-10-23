# -*- coding: utf-8 -*-
"""Fenêtre « TEI Stylesheets… » (V0.9.2.2) : version installée, origine,
dossier, licence, dernière vérification ; « Rechercher une mise à jour » ;
vérification au lancement, au plus une fois par mois, silencieuse sans
nouveauté ; nouvelle version installée avec l'accord de l'utilisateur, avec
Annuler ; anciennes versions supprimées au lancement suivant.

Le TEI-C est remplacé par un faux (``FakeTeiC``) : les fonctions réseau
elles-mêmes sont essayées dans tests/test_tei_stylesheets.py."""
from __future__ import annotations

import datetime
import time
import zipfile
from pathlib import Path

import pytest
from PySide6.QtWidgets import QMessageBox, QPushButton

import tei_stylesheets
import tei_stylesheets_ui
from app_context import _settings, tr
from tei_stylesheets import LibraryError

ROLE = QMessageBox.ButtonRole
PREFIX = "xml/tei/stylesheet/"
NEW = "7.62.0"


@pytest.fixture
def library(tmp_path, monkeypatch):
    """Bibliothèque propre au test, avec la version livrée."""
    monkeypatch.setenv("VARIANS_TEI_STYLESHEETS", str(tmp_path / "bibliotheque"))
    return tei_stylesheets.ensure_installed()


def _archive(path, version):
    with zipfile.ZipFile(path, "w") as archive:
        for name, text in {"VERSION": version + "\n", "catalog.xml": "<catalog/>", "tei.css": "",
                           "profiles/default/html/to.xsl": "<x/>"}.items():
            archive.writestr(PREFIX + name, text)
        archive.writestr(tei_stylesheets.LICENCE_MEMBER, "TEI Consortium")
    return path


class FakeTeiC:
    """Le TEI-C : sa dernière version, et ses archives. ``hold`` : le
    téléchargement attend Annuler."""

    def __init__(self, monkeypatch, latest=NEW, error=None, hold=False):
        self.latest, self.error, self.hold = latest, error, hold
        self.checks, self.downloads = 0, []
        monkeypatch.setattr(tei_stylesheets, "latest_version", self.latest_version)
        monkeypatch.setattr(tei_stylesheets, "download", self.download)

    def latest_version(self, *args, **kwargs):
        self.checks += 1
        if self.error:
            raise LibraryError(self.error, "hors ligne")
        return self.latest

    def download(self, version, folder, progress=None, cancel=None, **kwargs):
        self.downloads.append((version, Path(folder)))
        progress(0, 1000)
        if self.hold:
            while not cancel():
                time.sleep(0.01)
            raise LibraryError("cancelled")
        progress(500, 1000)
        path = _archive(Path(folder) / f"tei-xsl-{version}.zip", version)
        progress(1000, 1000)
        return path


def _last_check():
    return _settings().value(tei_stylesheets_ui.LAST_CHECK_SETTING, "")


def _in_window(qtbot, action):
    """Réponse à la fenêtre « TEI Stylesheets » : ``action(dialog)``, puis
    attendre la fin de la vérification et de l'installation, puis Fermer."""
    def answer(dialog):
        answer.dialog = dialog
        action(dialog)
        qtbot.waitUntil(lambda: not tei_stylesheets_ui.busy(), timeout=20_000)
        answer.seen = dialog.state()
        answer.can_check_again = dialog.check_btn.isEnabled()
        dialog.reject()
        return dialog.result()
    return answer


# --- La fenêtre ----------------------------------------------------------------------------------

def test_the_file_menu_opens_the_window_after_the_transformation_scenarios(open_window, sermons_project, dialogs,
                                                                            qtbot, library):
    window = open_window(sermons_project)
    actions = window.file_menu.actions()
    assert actions[actions.index(window.action_transform_scenarios) + 1] is window.action_tei_stylesheets
    assert window.action_tei_stylesheets.text() == tr("tei_stylesheets.menu")
    look = _in_window(qtbot, lambda dialog: None)
    dialogs.expect("dialog", look)
    window.action_tei_stylesheets.trigger()
    assert look.dialog.windowTitle() == tr("tei_stylesheets.title")
    assert look.seen == {"version": library.version, "source": tr("tei_stylesheets.source.bundled"),
                         "folder": str(library.folder), "checked": tr("tei_stylesheets.never")}
    assert "TEI Consortium" in look.dialog.licence_label.text()


def test_the_scenario_list_opens_the_window(open_window, sermons_project, dialogs, qtbot, library):
    window = open_window(sermons_project)

    def in_list(dialog):
        dialog.tei_stylesheets_btn.click()
        dialog.reject()
        return dialog.result()

    dialogs.expect("dialog", in_list)
    dialogs.expect("dialog", _in_window(qtbot, lambda dialog: None))
    window.transform_scenarios_dialog()
    assert dialogs.seen[-1] == ("dialog", tr("tei_stylesheets.title"), "TeiStylesheetsDialog")


def test_without_library_the_window_says_so(open_window, sermons_project, dialogs, qtbot, tmp_path, monkeypatch):
    monkeypatch.setenv("VARIANS_TEI_STYLESHEETS", str(tmp_path / "vide"))
    monkeypatch.setattr(tei_stylesheets, "BUNDLED_DIR", tmp_path / "sans-archive")
    window = open_window(sermons_project)
    look = _in_window(qtbot, lambda dialog: None)
    dialogs.expect("dialog", look)
    window.action_tei_stylesheets.trigger()
    assert look.seen["version"] == tr("tei_stylesheets.none")


# --- Rechercher une mise à jour ------------------------------------------------------------------

def test_the_library_is_already_up_to_date(open_window, sermons_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiC(monkeypatch, latest=library.version)
    window = open_window(sermons_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", look)
    dialogs.expect("information")
    window.action_tei_stylesheets.trigger()
    assert fake.checks == 1 and fake.downloads == []
    assert dialogs.seen[-1][2] == tr("tei_stylesheets.up_to_date", version=library.version)
    today = datetime.date.today().isoformat()
    assert _last_check() == today and look.seen["checked"] == today
    assert look.can_check_again


def test_a_network_error_is_reported(open_window, sermons_project, dialogs, qtbot, library, monkeypatch):
    FakeTeiC(monkeypatch, error="network")
    window = open_window(sermons_project)
    dialogs.expect("dialog", _in_window(qtbot, lambda dialog: dialog.check_btn.click()))
    dialogs.expect("warning")
    window.action_tei_stylesheets.trigger()
    assert dialogs.seen[-1][2] == tr("tei_stylesheets.error.network", detail="hors ligne")


def test_a_new_version_is_installed_with_consent(open_window, sermons_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiC(monkeypatch)
    window = open_window(sermons_project)
    look = _in_window(qtbot, lambda dialog: dialog.check_btn.click())
    dialogs.expect("dialog", look)
    dialogs.expect("box", ROLE.AcceptRole)                           # Installer
    window.action_tei_stylesheets.trigger()
    question = dialogs.seen[1]
    assert question[2] == tr("tei_stylesheets.available", version=NEW, current=library.version)
    assert [version for version, _folder in fake.downloads] == [NEW]
    active = tei_stylesheets.active()
    assert active.version == NEW and active.source == "downloaded"
    assert look.seen["version"] == NEW and look.can_check_again
    assert look.seen["source"] == tr("tei_stylesheets.source.downloaded", date=datetime.date.today().isoformat())
    # L'ancienne version reste jusqu'au lancement suivant ; le téléchargement est effacé.
    assert library.folder.is_dir() and not fake.downloads[0][1].exists()
    assert window.statusBar().currentMessage() == tr("tei_stylesheets.installed", version=NEW)


def test_later_installs_nothing(open_window, sermons_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiC(monkeypatch)
    window = open_window(sermons_project)
    dialogs.expect("dialog", _in_window(qtbot, lambda dialog: dialog.check_btn.click()))
    dialogs.expect("box", ROLE.RejectRole)                           # Plus tard
    window.action_tei_stylesheets.trigger()
    assert fake.downloads == [] and tei_stylesheets.active() == library


def test_the_download_can_be_cancelled(open_window, sermons_project, dialogs, qtbot, library, monkeypatch):
    fake = FakeTeiC(monkeypatch, hold=True)
    window = open_window(sermons_project)

    def check_then_cancel(dialog):
        dialog.check_btn.click()
        qtbot.waitUntil(lambda: tei_stylesheets_ui.progress_dialog() is not None, timeout=10_000)
        tei_stylesheets_ui.progress_dialog().findChild(QPushButton).click()          # Annuler

    dialogs.expect("dialog", _in_window(qtbot, check_then_cancel))
    dialogs.expect("box", ROLE.AcceptRole)
    window.action_tei_stylesheets.trigger()
    assert tei_stylesheets.active() == library
    assert not fake.downloads[0][1].exists()
    assert sorted(p.name for p in tei_stylesheets.library_dir().iterdir()) == [library.version]
    assert window.statusBar().currentMessage() == tr("tei_stylesheets.cancelled")


def test_a_damaged_archive_keeps_the_installed_version(open_window, sermons_project, dialogs, qtbot, library,
                                                       monkeypatch):
    fake = FakeTeiC(monkeypatch)

    def damaged(version, folder, progress=None, cancel=None, **kwargs):
        fake.downloads.append((version, Path(folder)))
        path = Path(folder) / f"tei-xsl-{version}.zip"
        path.write_bytes(b"<html>Not Found</html>")
        return path

    monkeypatch.setattr(tei_stylesheets, "download", damaged)
    window = open_window(sermons_project)
    dialogs.expect("dialog", _in_window(qtbot, lambda dialog: dialog.check_btn.click()))
    dialogs.expect("box", ROLE.AcceptRole)
    dialogs.expect("warning")
    window.action_tei_stylesheets.trigger()
    assert dialogs.seen[-1][2].startswith(tr("tei_stylesheets.error.invalid_archive", detail="\0").split("\0")[0])
    assert tei_stylesheets.active() == library


# --- Au lancement --------------------------------------------------------------------------------

def _launch(qtbot, window):
    tei_stylesheets_ui.at_launch(window)
    qtbot.waitUntil(lambda: not tei_stylesheets_ui.busy(), timeout=20_000)


def test_the_launch_proposes_a_new_version_once_a_month(open_window, sermons_project, dialogs, qtbot, library,
                                                        monkeypatch):
    fake = FakeTeiC(monkeypatch)
    window = open_window(sermons_project)
    dialogs.expect("box", ROLE.RejectRole)                           # Plus tard
    _launch(qtbot, window)
    assert fake.checks == 1 and dialogs.seen[-1][2] == tr("tei_stylesheets.available", version=NEW,
                                                            current=library.version)
    assert _last_check() == datetime.date.today().isoformat()
    _launch(qtbot, window)                                           # le même jour : rien
    assert fake.checks == 1
    ten_days = (datetime.date.today() - datetime.timedelta(days=10)).isoformat()
    _settings().setValue(tei_stylesheets_ui.LAST_CHECK_SETTING, ten_days)
    _launch(qtbot, window)
    assert fake.checks == 1
    a_month = (datetime.date.today() - datetime.timedelta(days=30)).isoformat()
    _settings().setValue(tei_stylesheets_ui.LAST_CHECK_SETTING, a_month)
    dialogs.expect("box", ROLE.RejectRole)
    _launch(qtbot, window)
    assert fake.checks == 2 and fake.downloads == []


@pytest.mark.parametrize("latest, error", [(None, "network"), ("current", None)])
def test_the_launch_says_nothing_without_news(open_window, sermons_project, dialogs, qtbot, library, monkeypatch,
                                             latest, error):
    fake = FakeTeiC(monkeypatch, latest=library.version if latest == "current" else latest, error=error)
    window = open_window(sermons_project)
    _launch(qtbot, window)                                           # aucune boîte attendue
    assert fake.checks == 1 and _last_check() == datetime.date.today().isoformat()


def test_the_launch_removes_the_old_versions(open_window, sermons_project, qtbot, library, monkeypatch, tmp_path):
    FakeTeiC(monkeypatch, latest=NEW)
    newer = tei_stylesheets.install_zip(_archive(tmp_path / "b.zip", NEW))
    _settings().setValue(tei_stylesheets_ui.LAST_CHECK_SETTING, datetime.date.today().isoformat())
    window = open_window(sermons_project)
    _launch(qtbot, window)
    assert not library.folder.exists() and tei_stylesheets.active() == newer


def test_each_error_has_a_message_in_the_seven_catalogs():
    import xml.etree.ElementTree as ET
    root = Path(__file__).resolve().parents[2] / "i18n"
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        catalog = {string.get("key") for string in ET.parse(root / f"{language}.xml").getroot().findall("string")}
        assert {f"tei_stylesheets.error.{code}" for code in tei_stylesheets_ui.ERROR_CODES} <= catalog, language
