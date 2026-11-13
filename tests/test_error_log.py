# -*- coding: utf-8 -*-
"""Journal des erreurs de Varians (V0.9.4.6), sans Qt.

Quand quelque chose échoue chez un utilisateur, il en reste une trace : un
fichier de taille limitée dans le dossier de données de Varians, avec les
exceptions non rattrapées (fil principal et autres fils), les erreurs
montrées et les processus séparés en échec. Le journal ne gêne jamais
Varians : s'il ne peut pas être écrit, rien ne change."""
from __future__ import annotations

import logging
import sys
import threading
from pathlib import Path

import pytest

import error_log


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    """Chaque test part sans journal et rend les crochets d'exceptions."""
    monkeypatch.setattr(sys, "excepthook", sys.excepthook)
    monkeypatch.setattr(threading, "excepthook", threading.excepthook)
    error_log.uninstall()
    yield
    error_log.uninstall()


def _text(folder):
    return (Path(folder) / error_log.FILE_NAME).read_text(encoding="utf-8")


def test_the_folder_follows_the_system(tmp_path):
    home = tmp_path / "maison"
    assert error_log.log_dir("win32", {"LOCALAPPDATA": r"C:\Users\m\AppData\Local"}, home) == \
        Path(r"C:\Users\m\AppData\Local") / "Varians" / "logs"
    assert error_log.log_dir("darwin", {}, home) == home / "Library" / "Logs" / "Varians"
    assert error_log.log_dir("linux", {}, home) == home / ".local" / "state" / "varians" / "logs"
    state = tmp_path / "etat"
    assert error_log.log_dir("linux", {"XDG_STATE_HOME": str(state)}, home) == state / "varians" / "logs"
    assert error_log.log_dir("linux", {"XDG_STATE_HOME": "relatif"}, home) == home / ".local" / "state" / "varians" / "logs"
    assert error_log.log_dir("win32", {error_log.ENVIRONMENT: str(tmp_path / "ici")}, home) == tmp_path / "ici"


def test_the_journal_opens_once_with_a_header(tmp_path):
    path = error_log.install("Varians 9.9, Qt 6.12.0", tmp_path)
    assert path == tmp_path / error_log.FILE_NAME and error_log.installed()
    assert error_log.install("encore", tmp_path) == path
    text = _text(tmp_path)
    assert text.count("Varians 9.9, Qt 6.12.0") == 1 and "encore" not in text
    assert f"Python {sys.version.split()[0]}" in text


def test_an_uncaught_exception_is_written_and_shown_as_before(tmp_path):
    seen, heard = [], []
    sys.excepthook = lambda *args: seen.append(args[1])
    error_log.install("Varians", tmp_path)
    error_log.add_listener(heard.append)
    try:
        raise ValueError("valeur inattendue")
    except ValueError:
        sys.excepthook(*sys.exc_info())
    text = _text(tmp_path)
    assert "Exception non rattrapée" in text and "ValueError: valeur inattendue" in text
    assert "test_an_uncaught_exception_is_written_and_shown_as_before" in text      # pile d'appels
    assert [str(e) for e in seen] == ["valeur inattendue"]                          # crochet précédent
    assert [str(e) for e in heard] == ["valeur inattendue"]


def test_an_exception_in_another_thread_is_written(tmp_path):
    seen = []
    threading.excepthook = lambda args: seen.append(args.exc_type)       # crochet précédent
    error_log.install("Varians", tmp_path)

    def fail():
        raise RuntimeError("dans un fil")

    thread = threading.Thread(target=fail, name="fil-de-test")
    thread.start()
    thread.join()
    text = _text(tmp_path)
    assert "RuntimeError: dans un fil" in text and "fil-de-test" in text
    assert seen == [RuntimeError]


def test_ctrl_c_is_not_an_error(tmp_path):
    seen = []
    sys.excepthook = lambda *args: seen.append(args[0])
    error_log.install("Varians", tmp_path)
    sys.excepthook(KeyboardInterrupt, KeyboardInterrupt(), None)
    assert seen == [KeyboardInterrupt] and "KeyboardInterrupt" not in _text(tmp_path)


def test_a_listener_that_fails_changes_nothing(tmp_path):
    sys.excepthook = lambda *args: None
    error_log.install("Varians", tmp_path)

    def broken(_exc):
        raise OSError("auditeur en panne")

    error_log.add_listener(broken)
    sys.excepthook(ValueError, ValueError("x"), None)
    assert "ValueError: x" in _text(tmp_path)


def test_the_modules_write_through_their_logger(tmp_path):
    error_log.install("Varians", tmp_path)
    error_log.logger("validation").warning("processus de validation indisponible : %s", "absent")
    text = _text(tmp_path)
    assert "WARNING" in text and "varians.validation" in text and "indisponible : absent" in text


def test_the_journal_keeps_a_limited_size(tmp_path, monkeypatch):
    monkeypatch.setattr(error_log, "MAX_BYTES", 2_000)
    error_log.install("Varians", tmp_path)
    for index in range(200):
        error_log.logger("essai").warning("ligne %d %s", index, "x" * 80)
    files = sorted(path.name for path in tmp_path.iterdir())
    assert files == [error_log.FILE_NAME, error_log.FILE_NAME + ".1", error_log.FILE_NAME + ".2"]
    assert all((tmp_path / name).stat().st_size <= 2_000 + 200 for name in files)
    assert "ligne 199" in _text(tmp_path)


def test_a_journal_that_cannot_be_written_changes_nothing(tmp_path):
    blocked = tmp_path / "fichier"
    blocked.write_text("pas un dossier", encoding="utf-8")
    hook = sys.excepthook
    assert error_log.install("Varians", blocked / "logs") is None
    assert not error_log.installed() and sys.excepthook is hook
    error_log.logger("essai").error("rien ne se passe")                  # sans erreur


def test_uninstall_gives_back_the_hooks(tmp_path):
    hook, thread_hook = sys.excepthook, threading.excepthook
    error_log.install("Varians", tmp_path)
    assert sys.excepthook is not hook and threading.excepthook is not thread_hook
    error_log.uninstall()
    assert sys.excepthook is hook and threading.excepthook is thread_hook and not error_log.installed()
    assert not any(isinstance(h, logging.FileHandler) for h in logging.getLogger(error_log.LOGGER).handlers)
