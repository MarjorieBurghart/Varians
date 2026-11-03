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
