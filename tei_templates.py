# -*- coding: utf-8 -*-
"""Squelettes de document de la TEI et leurs mises à jour, sans Qt.

Les modèles « TEI P5 » de « Nouveau document XML » (document_templates) sont
ceux que la TEI publie avec TEI P5 (``xml/tei/custom/templates`` de son
archive), ceux d'Oxygen. Varians en livre une version (``BUNDLED_DIR``,
voir son LISEZMOI) ; une version plus récente peut s'installer hors des
projets, comme les TEI Stylesheets (tei_stylesheets), dans le dossier de
données de l'utilisateur (``library_dir``), une version par dossier :
``<bibliothèque>/4.13.0/`` (les squelettes, ``LICENCE.txt`` et le témoin
``MARKER``, écrit en dernier).

- **Version active** (``current``) : la plus récente installée complètement,
  si elle est plus récente que celle livrée ; sinon celle livrée.
- **Réseau** : ``latest_version`` lit la dernière version de TEI P5 (fichier
  ``VERSION`` de la branche ``released`` du dépôt TEIC/TEI). ``download`` lit
  l'archive publiée (``tei-<version>.zip``, plus de 300 Mo) par morceaux,
  avec des requêtes partielles (« Range ») : son répertoire central, puis les
  seuls squelettes (quelques Mo en tout) ; puis la licence. Un serveur qui
  ignore ces requêtes est refusé : l'archive n'est jamais lue entière.
- **Installation sûre** (``install``) : noms de fichiers simples (``x.xml``),
  nombre et tailles plafonnés, XML bien formé et sans DOCTYPE, ``All.xml``
  et la licence exigés ; écriture dans un dossier temporaire voisin, témoin
  en dernier, puis renommage. Un ensemble refusé ne change rien.
- ``remove_old_versions`` (au lancement) supprime les versions qui ne servent
  plus et les installations interrompues.

Les erreurs sont des ``tei_stylesheets.LibraryError`` (mêmes codes :
``network``, ``invalid_reply``, ``invalid_archive``, ``cancelled``,
``write_failed``).
"""
from __future__ import annotations

import io
import json
import os
import re
import shutil
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import date
from http.client import HTTPException
from pathlib import Path
from urllib.request import Request, urlopen

from lxml import etree

from project_config import APPLICATION_ROOT
from tei_stylesheets import LibraryError, parse_version

LATEST_URL = "https://raw.githubusercontent.com/TEIC/TEI/released/P5/VERSION"
ARCHIVE_URL = "https://github.com/TEIC/TEI/releases/download/P5_Release_{version}/tei-{version}.zip"
LICENCE_URL = "https://raw.githubusercontent.com/TEIC/TEI/P5_Release_{version}/P5/COPYING.txt"

BUNDLED_DIR = APPLICATION_ROOT / "resources" / "templates" / "tei"
# Version de TEI P5 des squelettes livrés.
BUNDLED_VERSION = "4.12.0"
ENVIRONMENT = "VARIANS_TEI_TEMPLATES"
MEMBER_PREFIX = "xml/tei/custom/templates/"
LICENCE_NAME = "LICENCE.txt"
REQUIRED_TEMPLATE = "All.xml"          # squelette de « Même schéma que l'édition »
MARKER = ".varians-installed"
TEMP_PREFIX = ".tmp-"

MAX_TEMPLATES = 200
MAX_TEMPLATE_BYTES = 1_000_000
MAX_LICENCE_BYTES = 1_000_000
# Octets lus au plus dans l'archive publiée : son répertoire central (TEI P5
# 4.12.0 : 15 303 fichiers, environ 3 Mo) et les squelettes.
MAX_READ_BYTES = 32 * 1024 * 1024
BLOCK = 256 * 1024
HEADERS = {"User-Agent": "Varians (TEI templates)"}

_VERSION = re.compile(r"\d{1,4}\.\d{1,4}\.\d{1,4}")
_NAME = re.compile(r"[^/\\:\x00-\x1f]+\.xml")


@dataclass(frozen=True)
class Installed:
    """Une version des squelettes : ``source`` vaut ``bundled`` (livrée avec
    Varians) ou ``downloaded`` ; ``installed`` est la date ISO (vide pour
    la version livrée)."""
    version: str
    folder: Path
    source: str
    installed: str

    @property
    def licence(self) -> Path:
        """La licence de la TEI, qu'ouvre le bouton « Voir la licence »."""
        return self.folder / LICENCE_NAME


def bundled() -> Installed:
    """Les squelettes livrés avec Varians."""
    return Installed(BUNDLED_VERSION, BUNDLED_DIR, "bundled", "")


# --- Dossier et versions ------------------------------------------------------------------------

def library_dir() -> Path:
    """Dossier des versions téléchargées : ``VARIANS_TEI_TEMPLATES`` s'il est
    donné, sinon ``%LOCALAPPDATA%\\Varians\\tei-templates`` sous Windows et
    ``$XDG_DATA_HOME`` (ou ``~/.local/share``) ``/varians/tei-templates``
    ailleurs."""
    override = os.environ.get(ENVIRONMENT, "").strip()
    if override:
        return Path(os.path.abspath(os.path.expanduser(override)))
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Varians" / "tei-templates"
    data = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(data) if data and os.path.isabs(data) else Path.home() / ".local" / "share"
    return root / "varians" / "tei-templates"


def _base(base) -> Path:
    return Path(base) if base is not None else library_dir()


def _version_ok(version) -> bool:
    return isinstance(version, str) and _VERSION.fullmatch(version) is not None


def _read_marker(folder: Path) -> Installed | None:
    """La version installée dans ``folder``, si elle est complète."""
    if not _version_ok(folder.name):
        return None
    try:
        marker = json.loads((folder / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(marker, dict) or marker.get("version") != folder.name:
        return None
    if not ((folder / REQUIRED_TEMPLATE).is_file() and (folder / LICENCE_NAME).is_file()):
        return None
    return Installed(folder.name, folder, "downloaded", str(marker.get("installed", "")))


def installed(base=None) -> list[Installed]:
    """Versions téléchargées et installées complètement, de la plus ancienne
    à la plus récente."""
    base = _base(base)
    try:
        folders = [entry for entry in base.iterdir() if entry.is_dir() and not entry.is_symlink()]
    except OSError:
        return []
    found = [item for item in map(_read_marker, folders) if item is not None]
    return sorted(found, key=lambda item: parse_version(item.version))


def current(base=None) -> Installed:
    """Les squelettes qui servent : la plus récente version installée si elle
    est plus récente que celle livrée, sinon celle livrée."""
    versions = installed(base)
    if versions and parse_version(versions[-1].version) > parse_version(BUNDLED_VERSION):
        return versions[-1]
    return bundled()


def remove_old_versions(base=None) -> list[str]:
    """Supprime les versions qui ne servent pas (toutes, si la version livrée
    sert) et les installations interrompues ; renvoie les noms supprimés. À
    appeler au lancement. Les autres fichiers sont laissés."""
    base = _base(base)
    keep = current(base)
    removed = []
    try:
        entries = list(base.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if not entry.is_dir() or entry.is_symlink():
            continue
        old = _version_ok(entry.name) and not (keep.source == "downloaded" and entry.name == keep.version)
        if old or entry.name.startswith(TEMP_PREFIX):
            try:
                shutil.rmtree(entry)
            except OSError:                                         # fichier ouvert (Windows) : plus tard
                continue
            removed.append(entry.name)
    return removed


# --- Installation -------------------------------------------------------------------------------

def _check_template(name, data):
    """Refuse (``invalid_archive``) un squelette au nom ou au contenu suspect."""
    if not isinstance(name, str) or not _NAME.fullmatch(name) or name.startswith(".") or name in (".", ".."):
        raise LibraryError("invalid_archive", f"nom refusé : {name!r}")
    if not isinstance(data, bytes) or len(data) > MAX_TEMPLATE_BYTES:
        raise LibraryError("invalid_archive", f"{name} : taille refusée")
    parser = etree.XMLParser(resolve_entities=False, no_network=True, load_dtd=False, huge_tree=False)
    try:
        tree = etree.fromstring(data, parser).getroottree()
    except etree.XMLSyntaxError as error:
        raise LibraryError("invalid_archive", f"{name} : {error}") from error
    if tree.docinfo.doctype or tree.docinfo.internalDTD is not None:
        raise LibraryError("invalid_archive", f"{name} : DOCTYPE refusé")


def install(files, licence, version, base=None) -> Installed:
    """Installe les squelettes ``files`` (``{nom.xml: octets}``) et la licence
    de ``version`` ; rend la version installée (celle déjà installée si elle
    l'est complètement). ``LibraryError`` si l'ensemble est refusé : rien ne
    change alors."""
    if not _version_ok(version):
        raise LibraryError("invalid_reply", str(version)[:40])
    base = _base(base)
    target = base / version
    already = _read_marker(target)
    if already is not None:
        return already
    if not files or len(files) > MAX_TEMPLATES or REQUIRED_TEMPLATE not in files:
        raise LibraryError("invalid_archive", "squelettes incomplets")
    if not isinstance(licence, bytes) or not licence.strip() or len(licence) > MAX_LICENCE_BYTES:
        raise LibraryError("invalid_archive", "licence absente")
    for name, data in files.items():
        _check_template(name, data)
    try:
        base.mkdir(parents=True, exist_ok=True)
        folder = Path(tempfile.mkdtemp(prefix=f"{TEMP_PREFIX}{version}-", dir=base))
    except OSError as error:
        raise LibraryError("write_failed", str(error)) from error
    try:
        for name, data in files.items():
            (folder / name).write_bytes(data)
        (folder / LICENCE_NAME).write_bytes(licence)
        marker = {"version": version, "installed": date.today().isoformat(), "templates": len(files)}
        (folder / MARKER).write_text(json.dumps(marker), encoding="utf-8")
        if target.exists():                                        # installation interrompue
            shutil.rmtree(target)
        os.replace(folder, target)
    except OSError as error:
        shutil.rmtree(folder, ignore_errors=True)
        raise LibraryError("write_failed", str(error)) from error
    result = _read_marker(target)
    if result is None:
        raise LibraryError("write_failed", str(target))
    return result


# --- Réseau -------------------------------------------------------------------------------------

def _get(url, timeout, headers=None):
    try:
        return urlopen(Request(url, headers=dict(HEADERS, **(headers or {}))), timeout=timeout)
    except (OSError, ValueError, HTTPException) as error:
        raise LibraryError("network", str(error)) from error


def latest_version(url: str = LATEST_URL, timeout: float = 15) -> str:
    """Dernière version publiée de TEI P5 (fichier ``VERSION`` de la branche
    ``released`` de TEIC/TEI)."""
    with _get(url, timeout) as reply:
        try:
            data = reply.read(64)
        except (OSError, HTTPException) as error:
            raise LibraryError("network", str(error)) from error
    text = data.decode("utf-8", "replace").strip()
    if not _version_ok(text):
        raise LibraryError("invalid_reply", text[:40])
    return text


class _RemoteArchive(io.RawIOBase):
    """L'archive publiée, lue par blocs avec des requêtes « Range » : ce que
    ``zipfile`` en lit est seul téléchargé. Le premier bloc donne sa taille
    (``Content-Range``) ; une réponse sans 206 est refusée."""

    def __init__(self, url, timeout, cancel):
        super().__init__()
        self._url, self._timeout, self._cancel = url, timeout, cancel
        self._blocks, self._pos, self.read_bytes = {}, 0, 0
        self.size = self._first()

    def _fetch(self, start, end):
        if self._cancel is not None and self._cancel():
            raise LibraryError("cancelled")
        reply = _get(self._url, self._timeout, {"Range": f"bytes={start}-{end}"})
        with reply:
            content_range = reply.headers.get("Content-Range") or ""
            if reply.status != 206 or not content_range.startswith("bytes "):
                raise LibraryError("invalid_reply", "lecture partielle refusée par le serveur")
            self._url = reply.geturl()                             # adresse finale, après redirection
            try:
                data = reply.read(end - start + 1)
            except (OSError, HTTPException) as error:
                raise LibraryError("network", str(error)) from error
        self.read_bytes += len(data)
        if self.read_bytes > MAX_READ_BYTES:
            raise LibraryError("invalid_archive", "trop d'octets à lire")
        return data, content_range

    def _first(self):
        data, content_range = self._fetch(0, BLOCK - 1)
        match = re.fullmatch(r"bytes \d+-\d+/(\d+)", content_range.strip())
        if match is None:
            raise LibraryError("invalid_reply", content_range[:60])
        self._blocks[0] = data
        return int(match.group(1))

    def readable(self):
        return True

    def seekable(self):
        return True

    def tell(self):
        return self._pos

    def seek(self, offset, whence=io.SEEK_SET):
        base = {io.SEEK_SET: 0, io.SEEK_CUR: self._pos, io.SEEK_END: self.size}[whence]
        self._pos = max(0, base + offset)
        return self._pos

    def _block(self, index):
        if index not in self._blocks:
            start = index * BLOCK
            self._blocks[index], _range = self._fetch(start, min(self.size, start + BLOCK) - 1)
        return self._blocks[index]

    def read(self, size=-1):
        if size is None or size < 0:
            size = self.size - self._pos
        out = bytearray()
        while size > 0 and self._pos < self.size:
            index, offset = divmod(self._pos, BLOCK)
            chunk = self._block(index)[offset:offset + size]
            if not chunk:
                break
            out += chunk
            self._pos += len(chunk)
            size -= len(chunk)
        return bytes(out)

    def readinto(self, buffer):
        data = self.read(len(buffer))
        buffer[:len(data)] = data
        return len(data)


def _template_member(name):
    """Le nom d'un squelette de l'archive (dossier des modèles, sans
    sous-dossier, ni ``catalog.xml`` ni documentation ``*.doc.xml``), ou None."""
    if not name.startswith(MEMBER_PREFIX):
        return None
    rest = name[len(MEMBER_PREFIX):]
    if "/" in rest or not rest.endswith(".xml") or rest == "catalog.xml" or rest.endswith(".doc.xml"):
        return None
    return rest


def download(version, progress=None, cancel=None, *, archive_url: str = ARCHIVE_URL,
             licence_url: str = LICENCE_URL, timeout: float = 30):
    """Lit les squelettes et la licence de ``version`` : ``({nom.xml: octets},
    licence)``. ``progress(fait, total)`` suit la lecture ; ``cancel()`` vrai
    l'arrête (``LibraryError("cancelled")``)."""
    if not _version_ok(version):
        raise LibraryError("invalid_reply", str(version)[:40])
    if progress is not None:
        progress(0, 0)
    remote = _RemoteArchive(archive_url.format(version=version), timeout, cancel)
    try:
        archive = zipfile.ZipFile(remote)
        members = [(info, _template_member(info.filename)) for info in archive.infolist()]
        members = [(info, name) for info, name in members if name is not None]
        if not members or len(members) > MAX_TEMPLATES:
            raise LibraryError("invalid_archive", f"{len(members)} squelettes")
        total = len(members) + 1
        files = {}
        for done, (info, name) in enumerate(members):
            if info.file_size > MAX_TEMPLATE_BYTES or info.compress_size > MAX_TEMPLATE_BYTES:
                raise LibraryError("invalid_archive", f"{name} : taille refusée")
            if progress is not None:
                progress(done, total)
            files[name] = archive.read(info)
    except (zipfile.BadZipFile, zlib.error, EOFError, NotImplementedError) as error:
        raise LibraryError("invalid_archive", str(error)) from error
    if cancel is not None and cancel():
        raise LibraryError("cancelled")
    with _get(licence_url.format(version=version), timeout) as reply:
        try:
            licence = reply.read(MAX_LICENCE_BYTES + 1)
        except (OSError, HTTPException) as error:
            raise LibraryError("network", str(error)) from error
    if len(licence) > MAX_LICENCE_BYTES:
        raise LibraryError("invalid_archive", "licence trop grande")
    if progress is not None:
        progress(total, total)
    return files, licence


def download_and_install(version, progress=None, cancel=None, *, base=None, **urls) -> Installed:
    """Lit puis installe les squelettes de ``version`` (``download``,
    ``install``) ; ``progress(-1, 0)`` annonce l'installation."""
    files, licence = download(version, progress, cancel, **urls)
    if progress is not None:
        progress(-1, 0)
    return install(files, licence, version, base)
