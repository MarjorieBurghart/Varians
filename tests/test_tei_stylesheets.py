# -*- coding: utf-8 -*-
"""Bibliothèque des TEI Stylesheets (V0.9.2.2), sans Qt : dossier
d'installation, version active, extraction sûre d'une archive du TEI-C,
archive livrée avec Varians, dernière version publiée et téléchargement."""
from __future__ import annotations

import functools
import http.server
import json
import os
import threading
import zipfile
from pathlib import Path

import pytest

import tei_stylesheets as lib
from tei_stylesheets import LibraryError

PREFIX = "xml/tei/stylesheet/"


@pytest.fixture(autouse=True)
def library(tmp_path, monkeypatch):
    """Dossier de la bibliothèque propre à chaque test."""
    base = tmp_path / "bibliotheque"
    monkeypatch.setenv("VARIANS_TEI_STYLESHEETS", str(base))
    return base


def _archive(path, version="7.61.0", *, version_text=None, without=(), extra=(), links=()):
    """Archive au format de celles du TEI-C (``tei-xsl-<version>.zip``)."""
    members = {
        PREFIX + "VERSION": (version if version_text is None else version_text) + "\n\n",
        PREFIX + "catalog.xml": "<catalog/>",
        PREFIX + "tei.css": "body {}",
        PREFIX + "profiles/default/html/to.xsl": f"<!-- html {version} -->",
        PREFIX + "profiles/default/txt/to.xsl": "<!-- txt -->",
        "doc/tei-xsl/LICENCE": "TEI Consortium",
        "doc/tei-xsl/index.html": "<html/>",
    }
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(PREFIX, "")                                   # entrée de dossier
        for name, text in members.items():
            if name.rsplit("/", 1)[-1] not in without and name not in without:
                archive.writestr(name, text)
        for name, text in extra:
            archive.writestr(name, text)
        for name, target in links:
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            info.external_attr = 0o120777 << 16                        # lien symbolique
            archive.writestr(info, target)
    return path


def _entries(folder):
    return sorted(p.name for p in Path(folder).iterdir()) if Path(folder).exists() else []


# --- Dossier et versions ------------------------------------------------------------------------

def test_the_library_folder_can_be_chosen(library):
    assert lib.library_dir() == library


@pytest.mark.skipif(os.name == "nt", reason="dossier de données hors Windows")
def test_the_library_folder_is_in_the_user_data(monkeypatch, tmp_path):
    monkeypatch.delenv("VARIANS_TEI_STYLESHEETS")
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "donnees"))
    assert lib.library_dir() == tmp_path / "donnees" / "varians" / "tei-stylesheets"
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "moi"))
    assert lib.library_dir() == tmp_path / "moi" / ".local" / "share" / "varians" / "tei-stylesheets"


@pytest.mark.skipif(os.name != "nt", reason="dossier de données de Windows")
def test_the_library_folder_is_in_local_app_data(monkeypatch, tmp_path):
    monkeypatch.delenv("VARIANS_TEI_STYLESHEETS")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert lib.library_dir() == tmp_path / "Varians" / "tei-stylesheets"


@pytest.mark.parametrize("text, expected", [
    ("7.61.0", (7, 61, 0)), (" 7.61.0\n\n", (7, 61, 0)), ("7.62", (7, 62)), ("10.0.1.2", (10, 0, 1, 2)),
    ("7", None), ("7.a.0", None), ("../7.61.0", None), ("7.61.0/x", None), ("", None), (None, None),
    ("7.61.0.1.2", None),
])
def test_a_version_is_numbers_separated_by_dots(text, expected):
    assert lib.parse_version(text) == expected


def test_versions_are_compared_as_numbers():
    assert lib.is_newer("7.62.0", "7.61.0") and lib.is_newer("7.100.0", "7.61.0")
    assert not lib.is_newer("7.61.0", "7.61.0") and not lib.is_newer("7.9.0", "7.61.0")
    assert lib.is_newer("7.61.0", None) and not lib.is_newer("n'importe quoi", "7.61.0")


# --- Installation d'une archive -----------------------------------------------------------------

def test_an_archive_is_installed_in_a_folder_named_after_its_version(tmp_path, library):
    installed = lib.install_zip(_archive(tmp_path / "tei-xsl-7.61.0.zip"), source="bundled")
    assert installed.version == "7.61.0" and installed.source == "bundled"
    assert installed.folder == library / "7.61.0"
    assert (installed.folder / "profiles" / "default" / "html" / "to.xsl").read_text() == "<!-- html 7.61.0 -->"
    assert installed.catalog == installed.folder / "catalog.xml" and installed.catalog.is_file()
    assert installed.licence.read_text() == "TEI Consortium"                # doc/tei-xsl/LICENCE, seul gardé
    assert not (installed.folder / "doc").exists() and not (installed.folder / "index.html").exists()
    assert _entries(library) == ["7.61.0"]                                  # aucun dossier temporaire
    marker = json.loads((installed.folder / lib.MARKER).read_text(encoding="utf-8"))
    assert marker["version"] == "7.61.0" and marker["source"] == "bundled" and marker["installed"]
    assert lib.active() == installed


def test_the_most_recent_complete_version_is_the_active_one(tmp_path, library):
    lib.install_zip(_archive(tmp_path / "a.zip", "7.61.0"))
    lib.install_zip(_archive(tmp_path / "b.zip", "7.62.0"))
    (library / "7.63.0").mkdir()                                            # incomplète : pas de témoin
    (library / "notes").mkdir()
    assert [item.version for item in lib.installed()] == ["7.61.0", "7.62.0"]
    assert lib.active().version == "7.62.0" and lib.active().source == "downloaded"


def test_no_library_no_active_version(library):
    assert lib.installed() == [] and lib.active() is None


def test_an_installed_version_is_not_installed_again(tmp_path):
    first = lib.install_zip(_archive(tmp_path / "a.zip"), source="bundled")
    again = lib.install_zip(_archive(tmp_path / "b.zip"), source="downloaded")
    assert again == first and again.source == "bundled"


def test_the_expected_version_must_match(tmp_path, library):
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", "7.61.0"), expected_version="7.62.0")
    assert error.value.code == "invalid_archive"
    assert _entries(library) == []


@pytest.mark.parametrize("name", [
    PREFIX + "../../evil.xsl", PREFIX + "a/../../../evil.xsl", "/tmp/evil.xsl", PREFIX + "C:/evil.xsl",
    PREFIX + "a\\..\\..\\evil.xsl", "../evil.xsl",
])
def test_an_unsafe_path_refuses_the_archive(tmp_path, library, name):
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", extra=[(name, "mal")]))
    assert error.value.code == "invalid_archive"
    assert _entries(library) == [] and not (tmp_path / "evil.xsl").exists()


def test_a_link_refuses_the_archive(tmp_path, library):
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", links=[(PREFIX + "lien.xsl", "/etc/passwd")]))
    assert error.value.code == "invalid_archive"
    assert _entries(library) == []


@pytest.mark.parametrize("without", ["VERSION", "catalog.xml", "to.xsl", "LICENCE"])
def test_an_incomplete_archive_is_refused(tmp_path, library, without):
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", without=(without,)))
    assert error.value.code == "invalid_archive"
    assert _entries(library) == []


def test_a_wrong_version_file_is_refused(tmp_path, library):
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", version_text="../../x"))
    assert error.value.code == "invalid_archive"
    assert _entries(library) == []


def test_a_too_large_archive_is_refused(tmp_path, library, monkeypatch):
    monkeypatch.setattr(lib, "MAX_EXTRACTED_BYTES", 1000)
    with pytest.raises(LibraryError) as error:
        lib.install_zip(_archive(tmp_path / "a.zip", extra=[(PREFIX + "gros.xsl", "x" * 2000)]))
    assert error.value.code == "invalid_archive"
    assert _entries(library) == []


@pytest.mark.parametrize("damage", ["truncated", "not_a_zip", "crc"])
def test_a_damaged_archive_keeps_the_previous_version(tmp_path, library, damage):
    previous = lib.install_zip(_archive(tmp_path / "a.zip", "7.61.0"))
    path = _archive(tmp_path / "b.zip", "7.62.0", extra=[(PREFIX + "gros.xsl", "abcdefgh" * 4000)])
    data = bytearray(path.read_bytes())
    if damage == "truncated":
        data = data[: len(data) // 2]
    elif damage == "not_a_zip":
        data = bytearray(b"<html>Not Found</html>")
    else:                                                       # une donnée compressée modifiée
        with zipfile.ZipFile(path) as archive:
            info = archive.getinfo(PREFIX + "gros.xsl")
        start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
        data[start + info.compress_size // 2] ^= 0xFF
    path.write_bytes(bytes(data))
    with pytest.raises(LibraryError) as error:
        lib.install_zip(path)
    assert error.value.code == "invalid_archive"
    assert lib.active() == previous and _entries(library) == ["7.61.0"]


def test_old_versions_are_removed_later(tmp_path, library):
    lib.install_zip(_archive(tmp_path / "a.zip", "7.61.0"))
    lib.install_zip(_archive(tmp_path / "b.zip", "7.62.0"))
    (library / "7.63.0").mkdir()                                            # incomplète
    (library / ".tmp-7.64.0-abc").mkdir()                                   # installation interrompue
    (library / "notes.txt").write_text("à l'utilisateur")
    assert sorted(lib.remove_old_versions()) == [".tmp-7.64.0-abc", "7.61.0", "7.63.0"]
    assert _entries(library) == ["7.62.0", "notes.txt"]
    assert lib.remove_old_versions() == []


# --- Archive livrée avec Varians ----------------------------------------------------------------

def test_the_bundled_archive_is_installed_on_first_use(tmp_path, library):
    bundled = tmp_path / "livree"
    _archive(bundled / "tei-xsl-7.61.0.zip", "7.61.0")
    assert lib.bundled_zip(bundled) == ("7.61.0", bundled / "tei-xsl-7.61.0.zip")
    installed = lib.ensure_installed(bundled)
    assert installed.version == "7.61.0" and installed.source == "bundled"
    stamp = (installed.folder / lib.MARKER).stat().st_mtime_ns
    assert lib.ensure_installed(bundled) == installed                       # pas de nouvelle extraction
    assert (installed.folder / lib.MARKER).stat().st_mtime_ns == stamp


def test_a_newer_downloaded_version_is_kept(tmp_path):
    bundled = tmp_path / "livree"
    _archive(bundled / "tei-xsl-7.61.0.zip", "7.61.0")
    lib.install_zip(_archive(tmp_path / "b.zip", "7.62.0"))
    assert lib.ensure_installed(bundled).version == "7.62.0"
    assert [item.version for item in lib.installed()] == ["7.62.0"]


def test_a_newer_bundled_version_replaces_an_older_one(tmp_path):
    bundled = tmp_path / "livree"
    _archive(bundled / "tei-xsl-7.62.0.zip", "7.62.0")
    lib.install_zip(_archive(tmp_path / "a.zip", "7.61.0"))
    assert lib.ensure_installed(bundled).version == "7.62.0"


def test_without_bundled_archive_nothing_is_installed(tmp_path):
    assert lib.bundled_zip(tmp_path / "absent") is None
    assert lib.ensure_installed(tmp_path / "absent") is None
    (tmp_path / "livree").mkdir()
    (tmp_path / "livree" / "tei-xsl-faux.zip").write_bytes(b"")
    assert lib.bundled_zip(tmp_path / "livree") is None


def test_a_damaged_bundled_archive_leaves_the_library_as_it_was(tmp_path, library):
    bundled = tmp_path / "livree"
    bundled.mkdir()
    (bundled / "tei-xsl-7.61.0.zip").write_bytes(b"abime")
    assert lib.ensure_installed(bundled) is None and _entries(library) == []


def test_the_archive_bundled_with_varians(library):
    found = lib.bundled_zip()
    assert found is not None
    version, path = found
    assert path.parent == lib.BUNDLED_DIR and path.name == f"tei-xsl-{version}.zip"
    assert sorted(p.name for p in lib.BUNDLED_DIR.glob("*.zip")) == [path.name]
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
    # Les feuilles et la licence seules, avec les dossiers qui les contiennent.
    assert all(name.startswith(PREFIX) or name == lib.LICENCE_MEMBER
               or (name.endswith("/") and (PREFIX.startswith(name) or lib.LICENCE_MEMBER.startswith(name)))
               for name in names)
    installed = lib.ensure_installed()
    assert installed.version == version and installed.source == "bundled"
    for output in ("html", "txt", "markdown", "latex"):
        assert (installed.folder / "profiles" / "default" / output / "to.xsl").is_file()
    assert (installed.folder / "tei.css").is_file()
    catalog = installed.catalog.read_text(encoding="utf-8")
    assert 'rewritePrefix="./"' in catalog and lib.OFFICIAL_URI in catalog
    licence = installed.licence.read_text(encoding="utf-8")
    assert "TEI Consortium" in licence and "BSD" in licence and "Creative Commons" in licence
    readme = (lib.BUNDLED_DIR / "LISEZMOI.md").read_text(encoding="utf-8")
    assert "github.com/TEIC/Stylesheets" in readme and version in readme and "LICENCE" in readme


# --- Réseau : dernière version et téléchargement ------------------------------------------------

class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass                                        # connexion fermée par Annuler


@pytest.fixture
def server(tmp_path):
    folder = tmp_path / "serveur"
    folder.mkdir()
    handler = functools.partial(_QuietHandler, directory=str(folder))
    httpd = _QuietServer(("127.0.0.1", 0), handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield folder, f"http://127.0.0.1:{httpd.server_port}/"
    httpd.shutdown()
    httpd.server_close()


def test_the_latest_version_is_read_from_the_tei_c(server):
    folder, url = server
    (folder / "VERSION").write_text("7.62.0\n\n")
    assert lib.latest_version(url + "VERSION") == "7.62.0"
    assert lib.LATEST_URL == "https://raw.githubusercontent.com/TEIC/Stylesheets/released/VERSION"


@pytest.mark.parametrize("reply, code", [("<html>erreur</html>", "invalid_reply"), (None, "network")])
def test_a_wrong_reply_is_reported(server, reply, code):
    folder, url = server
    if reply is not None:
        (folder / "VERSION").write_text(reply)
    with pytest.raises(LibraryError) as error:
        lib.latest_version(url + "VERSION")
    assert error.value.code == code


def test_an_unreachable_server_is_reported():
    with pytest.raises(LibraryError) as error:
        lib.latest_version("http://127.0.0.1:9/VERSION", timeout=2)
    assert error.value.code == "network"


def _published(folder, version="7.62.0", size=600_000):
    path = _archive(folder / f"v{version}" / f"tei-xsl-{version}.zip", version,
                    extra=[(PREFIX + "gros.bin", os.urandom(size))])
    return path


def test_a_version_is_downloaded_then_installed(server, tmp_path):
    folder, url = server
    published = _published(folder)
    steps = []
    path = lib.download("7.62.0", tmp_path / "telechargement", progress=lambda done, total: steps.append((done, total)),
                        url=url + "v{version}/tei-xsl-{version}.zip")
    assert path == tmp_path / "telechargement" / "tei-xsl-7.62.0.zip"
    assert path.read_bytes() == published.read_bytes()
    assert _entries(path.parent) == ["tei-xsl-7.62.0.zip"]                  # pas de .part
    size = published.stat().st_size
    assert len(steps) >= 2 and steps[-1] == (size, size)
    assert [done for done, _total in steps] == sorted(done for done, _total in steps)
    installed = lib.install_zip(path, expected_version="7.62.0")
    assert installed.version == "7.62.0" and installed.source == "downloaded"
    assert lib.RELEASE_URL.format(version="7.62.0") == \
        "https://github.com/TEIC/Stylesheets/releases/download/v7.62.0/tei-xsl-7.62.0.zip"


def test_a_download_can_be_cancelled(server, tmp_path):
    folder, url = server
    _published(folder)
    steps = []
    with pytest.raises(LibraryError) as error:
        lib.download("7.62.0", tmp_path / "telechargement", progress=lambda done, total: steps.append(done),
                     cancel=lambda: bool(steps), url=url + "v{version}/tei-xsl-{version}.zip")
    assert error.value.code == "cancelled"
    assert _entries(tmp_path / "telechargement") == []


def test_a_too_large_download_is_stopped(server, tmp_path):
    folder, url = server
    _published(folder)
    with pytest.raises(LibraryError) as error:
        lib.download("7.62.0", tmp_path / "telechargement", url=url + "v{version}/tei-xsl-{version}.zip",
                     max_bytes=100_000)
    assert error.value.code == "invalid_archive"
    assert _entries(tmp_path / "telechargement") == []


def test_a_missing_release_is_a_network_error(server, tmp_path):
    _folder, url = server
    with pytest.raises(LibraryError) as error:
        lib.download("7.62.0", tmp_path / "telechargement", url=url + "v{version}/tei-xsl-{version}.zip")
    assert error.value.code == "network"
    assert _entries(tmp_path / "telechargement") == []


def test_only_a_real_version_is_downloaded(tmp_path):
    with pytest.raises(LibraryError) as error:
        lib.download("../../x", tmp_path, url="http://127.0.0.1:9/{version}")
    assert error.value.code == "invalid_reply"
