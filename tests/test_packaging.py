# -*- coding: utf-8 -*-
"""Version prête à l'emploi (V0.9.4.0) : recette PyInstaller
(packaging/varians.spec) et script de construction (packaging/build.py).

La construction elle-même (PyInstaller, quelques minutes) est faite par le
workflow « Binaries » sur Windows, macOS et Linux ; ici, ce qui se vérifie
sans construire : l'archive (nom, dossier, liens symboliques et droits
gardés), la plateforme, le contrôle du rapport de « --self-test », et que
la recette emporte tous les fichiers de données de Varians."""
from __future__ import annotations

import ast
import importlib.util
import os
import stat
import sys
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
# Dossiers du dépôt qui ne font pas partie de l'application.
NOT_SHIPPED = {".git", ".github", "tests", "docs", "packaging", "build", "dist", "__pycache__", ".pytest_cache",
               ".venv", "venv"}


def _build():
    spec = importlib.util.spec_from_file_location("varians_packaging_build", ROOT / "packaging" / "build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _spec_constant(name):
    tree = ast.parse((ROOT / "packaging" / "varians.spec").read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(getattr(t, "id", None) == name for t in node.targets):
            return ast.literal_eval(node.value)
    raise AssertionError(f"{name} absent de varians.spec")


def test_archive_and_platform_names():
    build = _build()
    assert build.archive_name("0.9.4.0", "windows-x64") == "Varians-0.9.4.0-windows-x64.zip"
    assert build.platform_tag("win32", "AMD64") == "windows-x64"
    assert build.platform_tag("darwin", "arm64") == "macos-arm64"
    assert build.platform_tag("darwin", "x86_64") == "macos-x64"
    assert build.platform_tag("linux", "x86_64") == "linux-x64"
    assert build.platform_tag("linux", "aarch64") == "linux-arm64"


def test_version_is_the_application_version():
    from app_context import APP_VERSION
    assert _build().app_version() == APP_VERSION


def test_executable_inside_the_built_folder(tmp_path):
    build = _build()
    assert build.executable_path(tmp_path, "win32") == tmp_path / "Varians.exe"
    assert build.executable_path(tmp_path, "linux") == tmp_path / "Varians"
    assert build.executable_path(tmp_path, "darwin") == tmp_path / "Varians.app" / "Contents" / "MacOS" / "Varians"


def test_the_recipe_ships_every_data_folder_of_varians():
    """Un dossier de données ajouté à Varians sans être ajouté à la recette
    manquerait à la version prête à l'emploi : tout dossier du dépôt qui
    contient autre chose que du Python est emporté."""
    folders = set(_spec_constant("DATA_FOLDERS"))
    patterns = _spec_constant("WEB_VIEWER_FILES")
    for entry in sorted(ROOT.iterdir()):
        if not entry.is_dir() or entry.name in NOT_SHIPPED or entry.name.startswith("."):
            continue
        data = [p for p in entry.rglob("*") if p.is_file() and p.suffix not in {".py", ".pyc"}
                and "__pycache__" not in p.parts]
        if entry.name == "web_viewer":
            missing = [p.name for p in data if not any(p.match(pattern) for pattern in patterns)]
            assert not missing, f"web_viewer : fichiers non emportés {missing}"
        elif data:
            assert entry.name in folders, f"dossier de données {entry.name}/ absent de DATA_FOLDERS"
    import self_test
    for resource in self_test.RESOURCES:
        first = resource.split("/")[0]
        assert first in folders or (first == "web_viewer" and any(Path(resource).match(p) for p in patterns))


def test_the_self_test_report_is_checked():
    build = _build()
    good = {"ok": True, "frozen": True, "version": "0.9.4.0",
            "checks": [{"name": name, "ok": True, "detail": ""} for name in build.EXPECTED_CHECKS]}
    assert build.report_problems(good, "0.9.4.0") == []
    assert build.report_problems(dict(good, ok=False), "0.9.4.0")
    assert build.report_problems(dict(good, frozen=False), "0.9.4.0")
    assert build.report_problems(dict(good, version="0.9.3.4"), "0.9.4.0")
    failed = dict(good, checks=good["checks"][:-1] + [{"name": "window", "ok": False, "detail": "xcb"}])
    assert any("window" in problem for problem in build.report_problems(failed, "0.9.4.0"))
    # Une vérification qui n'a pas eu lieu (fenêtre) est un échec.
    partial = dict(good, checks=good["checks"][:-1])
    assert any("window" in problem for problem in build.report_problems(partial, "0.9.4.0"))


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques et droits Unix")
def test_the_archive_keeps_its_folder_symlinks_and_permissions(tmp_path):
    """Le zip garde le dossier « Varians-<version>/ », les droits
    d'exécution et les liens symboliques (bibliothèques Qt sous Linux et
    macOS) : décompressé, Varians se lance."""
    build = _build()
    folder = tmp_path / "Varians-0.9.4.0"
    (folder / "_internal" / "lib").mkdir(parents=True)
    program = folder / "Varians"
    program.write_bytes(b"#!/bin/sh\n")
    program.chmod(0o755)
    (folder / "_internal" / "lib" / "libQt6Core.so.6").write_bytes(b"ELF")
    os.symlink("libQt6Core.so.6", folder / "_internal" / "lib" / "libQt6Core.so")
    os.symlink("_internal/lib", folder / "lib")
    archive = tmp_path / "Varians.zip"
    build.zip_folder(folder, archive)
    with zipfile.ZipFile(archive) as zf:
        infos = {info.filename: info for info in zf.infolist()}
        assert all(name.startswith("Varians-0.9.4.0/") for name in infos)
        mode = infos["Varians-0.9.4.0/Varians"].external_attr >> 16
        assert stat.S_ISREG(mode) and mode & 0o111
        link = infos["Varians-0.9.4.0/_internal/lib/libQt6Core.so"]
        assert stat.S_ISLNK(link.external_attr >> 16)
        assert zf.read(link) == b"libQt6Core.so.6"
        directory_link = infos["Varians-0.9.4.0/lib"]
        assert stat.S_ISLNK(directory_link.external_attr >> 16)
        assert zf.read(directory_link) == b"_internal/lib"
        # Le contenu du dossier pointé n'est pas emporté deux fois.
        assert "Varians-0.9.4.0/lib/libQt6Core.so.6" not in infos
        assert zf.read("Varians-0.9.4.0/_internal/lib/libQt6Core.so.6") == b"ELF"


def test_the_archive_has_its_checksum(tmp_path):
    build = _build()
    archive = tmp_path / "Varians-0.9.4.0-linux-x64.zip"
    archive.write_bytes(b"abc")
    checksum = build.write_checksum(archive)
    assert checksum.name == "Varians-0.9.4.0-linux-x64.zip.sha256"
    assert checksum.read_text(encoding="ascii") == (
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad  Varians-0.9.4.0-linux-x64.zip\n")


@pytest.mark.skipif(sys.platform == "win32", reason="Linux, macOS")
def test_bundled_certificates_only_when_the_system_ones_are_missing(monkeypatch):
    """Crochet d'exécution : certificats de certifi seulement si ceux du
    système ne sont pas où OpenSSL les cherche ; SSL_CERT_FILE respecté."""
    import ssl
    import types
    source = (ROOT / "packaging" / "rthook_certificates.py").read_text(encoding="utf-8")
    fake_certifi = types.SimpleNamespace(where=lambda: "/certifi/cacert.pem")
    monkeypatch.setitem(sys.modules, "certifi", fake_certifi)

    def run(paths, environment):
        monkeypatch.setattr(ssl, "get_default_verify_paths", lambda: paths)
        for name in ("SSL_CERT_FILE", "SSL_CERT_DIR"):
            monkeypatch.delenv(name, raising=False)
        for name, value in environment.items():
            monkeypatch.setenv(name, value)
        exec(compile(source, "rthook_certificates.py", "exec"), {"__name__": "__main__"})
        return os.environ.get("SSL_CERT_FILE")

    missing = types.SimpleNamespace(cafile=None, capath=None)
    assert run(missing, {}) == "/certifi/cacert.pem"
    assert run(missing, {"SSL_CERT_FILE": "/mine.pem"}) == "/mine.pem"
    present = types.SimpleNamespace(cafile=__file__, capath=None)
    assert run(present, {}) is None


@pytest.mark.skipif(os.name == "nt", reason="liens symboliques Unix")
def test_a_broken_link_in_the_built_folder_is_found(tmp_path):
    """Un lien symbolique vers une bibliothèque retirée par la recette ne
    doit pas partir dans l'archive : la construction le refuse."""
    build = _build()
    (tmp_path / "lib").mkdir()
    (tmp_path / "lib" / "libQt6Core.so.6").write_bytes(b"ELF")
    os.symlink("lib/libQt6Core.so.6", tmp_path / "libQt6Core.so.6")
    assert build.broken_links(tmp_path) == []
    os.symlink("lib/libQt6Pdf.so.6", tmp_path / "libQt6Pdf.so.6")
    assert build.broken_links(tmp_path) == ["libQt6Pdf.so.6"]


def test_the_binaries_workflow_builds_for_every_system_and_each_release():
    """Workflow « Binaries » : Windows, macOS (Apple Silicon et Intel),
    Linux ; à chaque release publiée et à la main ; mêmes dépendances que
    la recette ; seul l'envoi à la release peut écrire dans le dépôt."""
    text = (ROOT / ".github" / "workflows" / "binaries.yml").read_text(encoding="utf-8")
    for runner in ("windows-latest", "macos-latest", "macos-15-intel", "ubuntu-22.04"):
        assert f"os: {runner}" in text
    assert "  release:\n    types: [published]\n" in text
    assert "  workflow_dispatch:\n" in text
    assert "python -m pip install -r requirements.txt -r packaging/requirements.txt" in text
    assert "python packaging/build.py" in text
    assert 'gh release upload "$TAG"' in text
    assert "permissions:\n  contents: read\n" in text and text.count("contents: write") == 1


README_FILES = {"fr": "LISEZMOI.txt", "en": "README.txt", "de": "LIESMICH.txt", "ja": "README-ja.txt",
                "cs": "README-cs.txt", "it": "LEGGIMI.txt", "ru": "README-ru.txt"}


def test_the_archive_explains_itself_in_seven_languages(tmp_path):
    """À côté de Varians : le LISEZMOI dans les sept langues de
    l'interface (installation et premier lancement non signé sur chaque
    système, mise à jour, vérification, licences), à la version construite."""
    build = _build()
    build.add_documents(tmp_path, "0.9.4.0", system="linux")
    for language, name in README_FILES.items():
        text = (tmp_path / name).read_text(encoding="utf-8")
        assert "{version}" not in text and "Varians-0.9.4.0-linux-x64.zip" in text, language
        for command in ("Varians.exe", "xattr -dr com.apple.quarantine /Applications/Varians.app",
                        "start /wait Varians.exe --self-test", "./Varians --self-test", "Get-FileHash",
                        "https://github.com/MarjorieBurghart/Varians/releases",
                        "https://github.com/MarjorieBurghart/Varians/issues", "https://code.qt.io", "licences"):
            assert command in text, (language, command)
    assert sorted(p.name for p in tmp_path.glob("*.txt")) == sorted(README_FILES.values())


def test_the_readmes_name_the_menus_as_varians_shows_them():
    """« Aide → Aide du logiciel », « Affichage → Langue »… : les libellés
    des menus, pris dans les catalogues de l'interface."""
    import xml.etree.ElementTree as ET
    for language, name in README_FILES.items():
        strings = {node.get("key"): node.text for node in ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()}
        text = (ROOT / "packaging" / "readme" / name).read_text(encoding="utf-8")
        assert f"{strings['menu.help']} → {strings['help.software']} (F1)" in text, language
        assert f"{strings['menu.display']} → {strings['common.language'].rstrip(' :：:')}" in text, language


def test_the_archive_carries_the_licence_texts(tmp_path):
    build = _build()
    build.add_documents(tmp_path, "0.9.4.0", system="linux")
    licences = tmp_path / "licences"
    expected = {"LGPL-3.0.txt": "LESSER GENERAL PUBLIC LICENSE", "GPL-3.0.txt": "GNU GENERAL PUBLIC LICENSE",
                "LGPL-2.1.txt": "Version 2.1", "MPL-2.0.txt": "Mozilla Public License Version 2.0",
                "Python.txt": "PYTHON SOFTWARE FOUNDATION LICENSE", "lxml.txt": "libxml2",
                "TEI-Stylesheets.txt": "TEI Consortium", "SchXslt2.txt": "David Maus"}
    for name, words in expected.items():
        assert words in (licences / name).read_text(encoding="utf-8"), name


def test_windows_readmes_open_in_any_editor(tmp_path):
    """Sous Windows : fins de ligne CRLF et marque UTF-8 (Bloc-notes)."""
    build = _build()
    build.add_documents(tmp_path, "0.9.4.0", system="win32")
    data = (tmp_path / "LISEZMOI.txt").read_bytes()
    assert data.startswith(b"\xef\xbb\xbf") and b"\r\n" in data and b"\n" not in data.replace(b"\r\n", b"")
