# -*- coding: utf-8 -*-
"""Squelettes de document de la TEI et leurs mises à jour (tei_templates, sans Qt).

Comme les TEI Stylesheets : une version par dossier dans le dossier de
données de l'utilisateur, la plus récente servant si elle est plus récente
que celle livrée avec Varians. Une nouvelle version n'est lue que par
morceaux dans l'archive publiée de TEI P5 (requêtes « Range ») : son
répertoire, puis les seuls squelettes.
"""
from __future__ import annotations

import functools
import http.server
import io
import os
import re
import threading
import zipfile
from pathlib import Path

import pytest

import document_templates
import tei_templates as lib
from tei_templates import LibraryError

PREFIX = "xml/tei/custom/templates/"
TEMPLATE = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<?xml-model href="http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/{schema}.rng" '
            'type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
            '<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>{name}</p></body></text></TEI>\n')
LICENCE = b"Copyright TEI Consortium. CC BY 3.0 / BSD 2-Clause.\n"


def _template(name, schema="tei_all"):
    return TEMPLATE.format(name=name, schema=schema).encode("utf-8")


def _files(**extra):
    files = {"All.xml": _template("All"), "Lite.xml": _template("Lite", "tei_lite")}
    files.update(extra)
    return files


@pytest.fixture
def library(tmp_path, monkeypatch):
    folder = tmp_path / "bibliotheque"
    monkeypatch.setenv(lib.ENVIRONMENT, str(folder))
    return folder


# --- Dossier et version active ------------------------------------------------------------------

def test_the_library_folder_can_be_chosen(library):
    assert lib.library_dir() == library


@pytest.mark.skipif(os.name == "nt", reason="dossier de données hors de Windows")
def test_the_library_folder_is_in_the_user_data(monkeypatch, tmp_path):
    monkeypatch.delenv(lib.ENVIRONMENT, raising=False)
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "data"))
    assert lib.library_dir() == tmp_path / "data" / "varians" / "tei-templates"
    monkeypatch.delenv("XDG_DATA_HOME")
    monkeypatch.setenv("HOME", str(tmp_path / "moi"))
    assert lib.library_dir() == tmp_path / "moi" / ".local" / "share" / "varians" / "tei-templates"


@pytest.mark.skipif(os.name != "nt", reason="dossier de données de Windows")
def test_the_library_folder_is_in_local_app_data(monkeypatch, tmp_path):
    monkeypatch.delenv(lib.ENVIRONMENT, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert lib.library_dir() == tmp_path / "Varians" / "tei-templates"


def test_without_installed_version_the_bundled_templates_serve(library):
    current = lib.current()
    assert (current.version, current.folder, current.source) == ("4.12.0", document_templates.TEI_TEMPLATES_DIR,
                                                                 "bundled")
    assert lib.BUNDLED_VERSION == document_templates.TEI_TEMPLATES_VERSION == "4.12.0"
    assert current.licence == document_templates.TEI_TEMPLATES_DIR / "LICENCE.txt"


def test_an_installed_newer_version_serves(library):
    installed = lib.install(_files(), LICENCE, "4.13.0")
    assert installed.folder == library / "4.13.0" and installed.source == "downloaded"
    assert sorted(path.name for path in installed.folder.glob("*.xml")) == ["All.xml", "Lite.xml"]
    assert installed.licence.read_bytes() == LICENCE
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", installed.installed)
    assert lib.current() == installed
    assert lib.install(_files(), LICENCE, "4.14.0").version == lib.current().version == "4.14.0"


def test_an_installed_version_not_newer_than_the_bundled_one_does_not_serve(library):
    lib.install(_files(), LICENCE, "4.11.0")
    assert lib.current().source == "bundled"


def test_an_interrupted_installation_does_not_serve(library):
    (library / "4.13.0").mkdir(parents=True)                       # sans témoin
    (library / "4.13.0" / "All.xml").write_bytes(_template("All"))
    assert lib.current().source == "bundled"


def test_old_versions_and_interrupted_installations_are_removed(library):
    lib.install(_files(), LICENCE, "4.13.0")
    lib.install(_files(), LICENCE, "4.14.0")
    (library / ".tmp-reste").mkdir()
    (library / "notes.txt").write_text("à garder", encoding="utf-8")
    assert sorted(lib.remove_old_versions()) == [".tmp-reste", "4.13.0"]
    assert sorted(path.name for path in library.iterdir()) == ["4.14.0", "notes.txt"]
    assert lib.current().version == "4.14.0"


# --- Installation sûre --------------------------------------------------------------------------

@pytest.mark.parametrize("name", ["../All2.xml", "sous/Lite.xml", "..\\x.xml", "C:x.xml", ".cache.xml",
                                  "notes.txt", ""])
def test_an_unsafe_name_refuses_the_whole_set(library, name):
    with pytest.raises(LibraryError) as error:
        lib.install(_files(**{name: _template("x")}), LICENCE, "4.13.0")
    assert error.value.code == "invalid_archive"
    assert not (library / "4.13.0").exists() and lib.current().source == "bundled"


def test_a_malformed_template_refuses_the_whole_set(library):
    with pytest.raises(LibraryError) as error:
        lib.install(_files(**{"Bare.xml": b"<TEI><text>"}), LICENCE, "4.13.0")
    assert error.value.code == "invalid_archive"
    assert lib.current().source == "bundled"


def test_entities_are_not_expanded_and_refuse_the_template(library):
    bomb = (b'<?xml version="1.0"?><!DOCTYPE TEI [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;">]>'
            b"<TEI>&b;</TEI>")
    with pytest.raises(LibraryError) as error:
        lib.install(_files(**{"Bare.xml": bomb}), LICENCE, "4.13.0")
    assert error.value.code == "invalid_archive"


@pytest.mark.parametrize("files, licence", [
    ({"Lite.xml": _template("Lite")}, LICENCE),                    # All.xml sert à « Même schéma que l'édition »
    (_files(), b""),                                                # licence absente
    ({}, LICENCE),
])
def test_an_incomplete_set_is_refused(library, files, licence):
    with pytest.raises(LibraryError) as error:
        lib.install(files, licence, "4.13.0")
    assert error.value.code == "invalid_archive"


def test_too_many_or_too_large_templates_are_refused(library, monkeypatch):
    monkeypatch.setattr(lib, "MAX_TEMPLATE_BYTES", 100)
    with pytest.raises(LibraryError):
        lib.install(_files(**{"Gros.xml": b"<TEI>" + b"x" * 200 + b"</TEI>"}), LICENCE, "4.13.0")
    monkeypatch.setattr(lib, "MAX_TEMPLATE_BYTES", 1_000_000)
    monkeypatch.setattr(lib, "MAX_TEMPLATES", 2)
    with pytest.raises(LibraryError):
        lib.install(_files(**{"Bare.xml": _template("Bare")}), LICENCE, "4.13.0")


@pytest.mark.parametrize("version", ["4.13", "", "dernière", "../4.13.0", "4.13.0.1.2"])
def test_only_a_real_version_is_installed(library, version):
    with pytest.raises(LibraryError) as error:
        lib.install(_files(), LICENCE, version)
    assert error.value.code in ("invalid_reply", "invalid_archive")
    assert not any(library.iterdir()) if library.exists() else True


def test_the_same_version_is_not_installed_twice(library):
    first = lib.install(_files(), LICENCE, "4.13.0")
    again = lib.install(_files(**{"Bare.xml": _template("Bare")}), LICENCE, "4.13.0")
    assert again == first
    assert not (first.folder / "Bare.xml").exists()


# --- Réseau : dernière version et lecture partielle de l'archive ------------------------------

class _RangeHandler(http.server.SimpleHTTPRequestHandler):
    """Serveur de fichiers qui comprend « Range: bytes=a-b » (206), comme
    GitHub ; ``ranges`` et ``sent`` comptent les requêtes et les octets."""

    honour_ranges = True
    log = None

    def log_message(self, *args):
        pass

    def do_GET(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return
        data = path.read_bytes()
        wanted = self.headers.get("Range")
        match = re.fullmatch(r"bytes=(\d+)-(\d+)", wanted or "")
        if self.honour_ranges and match:
            start, end = int(match.group(1)), min(int(match.group(2)), len(data) - 1)
            body = data[start:end + 1]
            self.send_response(206)
            self.send_header("Content-Range", f"bytes {start}-{end}/{len(data)}")
        else:
            body = data
            self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        try:
            self.wfile.write(body)
        except OSError:
            return
        if self.log is not None:
            self.log.append((self.path, len(body)))

    def do_HEAD(self):
        path = Path(self.translate_path(self.path))
        if not path.is_file():
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Length", str(path.stat().st_size))
        self.send_header("Accept-Ranges", "bytes")
        self.end_headers()


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass


@pytest.fixture
def server(tmp_path):
    folder = tmp_path / "serveur"
    folder.mkdir()
    log = []
    handler = type("Handler", (_RangeHandler,), {"log": log})
    httpd = _QuietServer(("127.0.0.1", 0), functools.partial(handler, directory=str(folder)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield folder, f"http://127.0.0.1:{httpd.server_port}/", log, handler
    httpd.shutdown()
    httpd.server_close()


def _publish(folder, version="4.13.0", *, filler=3_000_000, templates=None, compression=zipfile.ZIP_STORED):
    """Archive publiée comme celle de TEI P5 : les squelettes, d'autres
    fichiers (non lus), et la licence à part."""
    templates = templates if templates is not None else _files(**{"Bare.xml": _template("Bare")})
    archive = folder / f"P5_Release_{version}" / f"tei-{version}.zip"
    archive.parent.mkdir(parents=True)
    with zipfile.ZipFile(archive, "w", compression) as bundle:
        bundle.writestr("xml/tei/odd/p5subset.xml", os.urandom(filler))
        for name, data in templates.items():
            bundle.writestr(PREFIX + name, data)
        bundle.writestr(PREFIX + "catalog.xml", b"<catalog/>")
        bundle.writestr(PREFIX + "tei_lite.doc.xml", b"<TEI/>")
        bundle.writestr(PREFIX + "Lite.properties", b"smallIcon=x")
        bundle.writestr(PREFIX + "sous/Autre.xml", b"<TEI/>")
        bundle.writestr("doc/tei-p5-doc/fr/html/index.html", os.urandom(filler))
    licence = folder / f"licence-{version}" / "COPYING.txt"
    licence.parent.mkdir(parents=True)
    licence.write_bytes(LICENCE)
    return archive


def _urls(url):
    return {"archive_url": url + "P5_Release_{version}/tei-{version}.zip",
            "licence_url": url + "licence-{version}/COPYING.txt"}


def test_the_latest_version_is_read_from_the_tei_c(server):
    folder, url, _log, _handler = server
    (folder / "VERSION").write_text("4.13.0\n")
    assert lib.latest_version(url + "VERSION") == "4.13.0"
    assert lib.LATEST_URL == "https://raw.githubusercontent.com/TEIC/TEI/released/P5/VERSION"
    assert lib.ARCHIVE_URL == "https://github.com/TEIC/TEI/releases/download/P5_Release_{version}/tei-{version}.zip"
    assert lib.LICENCE_URL == "https://raw.githubusercontent.com/TEIC/TEI/P5_Release_{version}/P5/COPYING.txt"


@pytest.mark.parametrize("reply, code", [("<html>erreur</html>", "invalid_reply"), (None, "network")])
def test_a_wrong_reply_is_reported(server, reply, code):
    folder, url, _log, _handler = server
    if reply is not None:
        (folder / "VERSION").write_text(reply)
    with pytest.raises(LibraryError) as error:
        lib.latest_version(url + "VERSION")
    assert error.value.code == code


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_only_the_templates_are_read_from_the_published_archive(server, compression):
    folder, url, log, _handler = server
    archive = _publish(folder, compression=compression)
    steps = []
    files, licence = lib.download("4.13.0", progress=lambda done, total: steps.append((done, total)), **_urls(url))
    assert sorted(files) == ["All.xml", "Bare.xml", "Lite.xml"]
    assert files["Lite.xml"] == _template("Lite", "tei_lite") and licence == LICENCE
    read = sum(size for path, size in log if path.endswith(".zip"))
    assert read < archive.stat().st_size / 4                        # l'archive n'est pas lue entière
    assert steps[-1][0] == steps[-1][1] and steps[-1][1] > 0


def test_a_server_that_ignores_ranges_is_refused(server):
    folder, url, log, handler = server
    _publish(folder)
    handler.honour_ranges = False
    with pytest.raises(LibraryError) as error:
        lib.download("4.13.0", **_urls(url))
    assert error.value.code == "invalid_reply"


def test_a_download_can_be_cancelled(server):
    folder, url, _log, _handler = server
    _publish(folder)
    with pytest.raises(LibraryError) as error:
        lib.download("4.13.0", cancel=lambda: True, **_urls(url))
    assert error.value.code == "cancelled"


def test_too_much_reading_is_stopped(server, monkeypatch):
    folder, url, _log, _handler = server
    _publish(folder)
    monkeypatch.setattr(lib, "MAX_READ_BYTES", 10_000)
    with pytest.raises(LibraryError) as error:
        lib.download("4.13.0", **_urls(url))
    assert error.value.code == "invalid_archive"


def test_a_too_large_template_is_not_read(server, monkeypatch):
    folder, url, _log, _handler = server
    _publish(folder, templates=_files(**{"Gros.xml": b"<TEI>" + b"x" * 5000 + b"</TEI>"}))
    monkeypatch.setattr(lib, "MAX_TEMPLATE_BYTES", 1000)
    with pytest.raises(LibraryError) as error:
        lib.download("4.13.0", **_urls(url))
    assert error.value.code == "invalid_archive"


def test_a_missing_release_is_a_network_error(server):
    _folder, url, _log, _handler = server
    with pytest.raises(LibraryError) as error:
        lib.download("4.13.0", **_urls(url))
    assert error.value.code == "network"



def test_a_template_altered_in_the_archive_is_refused(server, library):
    """V0.9.4.6 : seuls quelques fichiers de l'archive de TEI P5 sont lus
    (requêtes « Range ») ; son empreinte entière ne peut donc pas être
    vérifiée, mais celle (CRC-32) de chaque squelette lu l'est : un squelette
    altéré refuse tout l'ensemble, rien n'est installé."""
    folder, url, _log, _handler = server
    archive = _publish(folder)
    with zipfile.ZipFile(archive) as bundle:
        info = bundle.getinfo(PREFIX + "Bare.xml")
    data = bytearray(archive.read_bytes())
    start = info.header_offset + 30 + len(info.filename.encode()) + len(info.extra)
    position = data.index(b"<TEI", start)
    data[position + 1:position + 4] = b"XYZ"                          # même taille, autre contenu
    archive.write_bytes(bytes(data))
    with pytest.raises(LibraryError) as error:
        lib.download_and_install("4.13.0", **_urls(url))
    assert error.value.code == "invalid_archive" and "CRC" in error.value.detail
    assert lib.current().version == lib.BUNDLED_VERSION

def test_a_downloaded_version_is_installed_and_serves(server, library):
    folder, url, _log, _handler = server
    _publish(folder)
    installed = lib.download_and_install("4.13.0", **_urls(url))
    assert installed.version == "4.13.0" and lib.current() == installed
    names = [template.name for template in document_templates.tei_templates()]
    assert names == ["All", "Bare", "Lite"]                         # la version active sert
    assert document_templates.tei_templates_version() == "4.13.0"
