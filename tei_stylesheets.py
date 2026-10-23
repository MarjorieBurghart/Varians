# -*- coding: utf-8 -*-
"""Bibliothèque des TEI Stylesheets (V0.9.2.2), sans Qt.

Les feuilles XSLT du TEI Consortium (https://github.com/TEIC/Stylesheets)
servent aux scénarios de transformation prédéfinis « TEI : … ». Varians les
installe hors des projets, dans le dossier de données de l'utilisateur
(``library_dir``), une version par dossier : ``<bibliothèque>/7.61.0/``.

- **Archive** : celle que publie le TEI-C (``tei-xsl-<version>.zip``). Seuls
  ``xml/tei/stylesheet/`` (les feuilles, à la racine du dossier de la version)
  et ``doc/tei-xsl/LICENCE`` (sous le nom ``LICENCE``) sont extraits.
- **Archive livrée** : Varians en apporte une (``resources/tei-stylesheets``,
  voir son LISEZMOI), installée au premier usage sans réseau
  (``ensure_installed``), ou quand elle est plus récente que la version
  installée.
- **Extraction sûre** (``install_zip``) : chemin absolu, ``..``, ``:``, ``\\``
  ou lien refusent l'archive entière ; nombre de fichiers et taille plafonnés ;
  extraction dans un dossier temporaire voisin (``.tmp-…``), contrôle des
  fichiers indispensables (``REQUIRED``), témoin ``MARKER`` écrit en dernier,
  puis mise en place par un renommage. Une archive refusée ne change rien.
- **Version active** (``active``) : la plus récente installée complètement
  (avec son témoin). Une ancienne version reste en place jusqu'au lancement
  suivant (``remove_old_versions``), jamais pendant une transformation.
- **Réseau** : ``latest_version`` lit la dernière version publiée ;
  ``download`` télécharge une archive, par morceaux, avec progression, Annuler
  et un plafond de taille. Aucune autre fonction n'emploie le réseau.

Les erreurs sont des ``LibraryError`` dont le ``code`` (``network``,
``invalid_reply``, ``invalid_archive``, ``cancelled``, ``write_failed``)
permet à l'interface d'écrire un message traduit.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import stat
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import date
from http.client import HTTPException
from pathlib import Path, PurePosixPath, PureWindowsPath
from urllib.request import Request, urlopen

from project_config import APPLICATION_ROOT

RELEASE_URL = "https://github.com/TEIC/Stylesheets/releases/download/v{version}/tei-xsl-{version}.zip"
LATEST_URL = "https://raw.githubusercontent.com/TEIC/Stylesheets/released/VERSION"
# Adresse officielle des feuilles, que leur catalogue (catalog.xml) renvoie
# vers les fichiers installés.
OFFICIAL_URI = "http://www.tei-c.org/release/xml/tei/stylesheet/"

BUNDLED_DIR = APPLICATION_ROOT / "resources" / "tei-stylesheets"
ENVIRONMENT = "VARIANS_TEI_STYLESHEETS"
ARCHIVE_PREFIX = "xml/tei/stylesheet/"
LICENCE_MEMBER = "doc/tei-xsl/LICENCE"
MARKER = ".varians-installed"
TEMP_PREFIX = ".tmp-"
REQUIRED = ("VERSION", "catalog.xml", "profiles/default/html/to.xsl", "LICENCE")

MAX_MEMBERS = 10_000
MAX_EXTRACTED_BYTES = 100 * 1024 * 1024
MAX_DOWNLOAD_BYTES = 100 * 1024 * 1024
CHUNK = 256 * 1024
HEADERS = {"User-Agent": "Varians (TEI Stylesheets)"}

_VERSION = re.compile(r"\d{1,4}(?:\.\d{1,6}){1,3}")


class LibraryError(Exception):
    """Échec d'une opération sur la bibliothèque ; ``code`` dit lequel."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code
        self.detail = detail


@dataclass(frozen=True)
class Installed:
    """Une version installée : ``source`` vaut ``bundled`` (archive livrée
    avec Varians) ou ``downloaded`` ; ``installed`` est la date ISO."""
    version: str
    folder: Path
    source: str
    installed: str

    @property
    def catalog(self) -> Path:
        return self.folder / "catalog.xml"

    @property
    def licence(self) -> Path:
        return self.folder / "LICENCE"


# --- Dossier et versions ------------------------------------------------------------------------

def library_dir() -> Path:
    """Dossier de la bibliothèque : ``VARIANS_TEI_STYLESHEETS`` s'il est
    donné, sinon ``%LOCALAPPDATA%\\Varians\\tei-stylesheets`` sous Windows et
    ``$XDG_DATA_HOME`` (ou ``~/.local/share``) ``/varians/tei-stylesheets``
    ailleurs."""
    override = os.environ.get(ENVIRONMENT, "").strip()
    if override:
        return Path(os.path.abspath(os.path.expanduser(override)))
    if os.name == "nt" and os.environ.get("LOCALAPPDATA"):
        return Path(os.environ["LOCALAPPDATA"]) / "Varians" / "tei-stylesheets"
    data = os.environ.get("XDG_DATA_HOME", "").strip()
    root = Path(data) if data and os.path.isabs(data) else Path.home() / ".local" / "share"
    return root / "varians" / "tei-stylesheets"


def parse_version(text) -> tuple[int, ...] | None:
    """``"7.61.0"`` → ``(7, 61, 0)`` ; None si ce n'est pas un numéro de
    version (de deux à quatre nombres séparés par des points)."""
    if not isinstance(text, str) or not _VERSION.fullmatch(text.strip()):
        return None
    return tuple(int(part) for part in text.strip().split("."))


def is_newer(candidate, current) -> bool:
    """``candidate`` est-elle une version plus récente que ``current`` (None :
    aucune version) ?"""
    new = parse_version(candidate)
    if new is None:
        return False
    old = parse_version(current) if current is not None else None
    return old is None or new > old


def _base(base) -> Path:
    return Path(base) if base is not None else library_dir()


def _read_marker(folder: Path) -> Installed | None:
    """La version installée dans ``folder``, si elle est complète."""
    if parse_version(folder.name) is None:
        return None
    try:
        marker = json.loads((folder / MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(marker, dict) or marker.get("version") != folder.name:
        return None
    if not all((folder / name).is_file() for name in REQUIRED):
        return None
    source = marker.get("source") if marker.get("source") in ("bundled", "downloaded") else "downloaded"
    return Installed(folder.name, folder, source, str(marker.get("installed", "")))


def installed(base=None) -> list[Installed]:
    """Versions installées complètement, de la plus ancienne à la plus récente."""
    base = _base(base)
    try:
        folders = [entry for entry in base.iterdir() if entry.is_dir()]
    except OSError:
        return []
    found = [item for item in map(_read_marker, folders) if item is not None]
    return sorted(found, key=lambda item: parse_version(item.version))


def active(base=None) -> Installed | None:
    """La version qu'emploient les scénarios : la plus récente installée."""
    versions = installed(base)
    return versions[-1] if versions else None


# --- Installation -------------------------------------------------------------------------------

def _destination(info: zipfile.ZipInfo) -> PurePosixPath | None:
    """Chemin d'un membre de l'archive dans le dossier de la version (None :
    non extrait). Un membre dangereux refuse l'archive entière."""
    name = info.filename
    if stat.S_ISLNK(info.external_attr >> 16):
        raise LibraryError("invalid_archive", f"lien : {name}")
    windows = PureWindowsPath(name)
    parts = name.rstrip("/").split("/")
    if ("\\" in name or ":" in name or name.startswith("/") or windows.drive or windows.root
            or any(part in ("", ".", "..") for part in parts)):
        raise LibraryError("invalid_archive", f"chemin refusé : {name}")
    if name == LICENCE_MEMBER:
        return PurePosixPath("LICENCE")
    if name.startswith(ARCHIVE_PREFIX) and len(name) > len(ARCHIVE_PREFIX):
        return PurePosixPath(name[len(ARCHIVE_PREFIX):].rstrip("/"))
    return None


def _remove(path: Path) -> None:
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    elif path.exists() or path.is_symlink():
        path.unlink()


def _extract(archive: zipfile.ZipFile, members, folder: Path) -> None:
    total = 0
    for info, relative in members:
        target = folder.joinpath(*relative.parts)
        if info.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(info) as source, target.open("wb") as stream:
            while chunk := source.read(CHUNK):
                total += len(chunk)
                if total > MAX_EXTRACTED_BYTES:
                    raise LibraryError("invalid_archive", "archive trop grande")
                stream.write(chunk)


def install_zip(zip_path, base=None, *, source: str = "downloaded", expected_version: str | None = None) -> Installed:
    """Installe l'archive ``zip_path`` du TEI-C dans la bibliothèque et
    renvoie la version installée. Une version déjà installée ne l'est pas de
    nouveau. ``expected_version`` : la version que doit contenir l'archive."""
    base = _base(base)
    try:
        archive = zipfile.ZipFile(zip_path)
    except (OSError, zipfile.BadZipFile, zlib.error, ValueError) as error:
        raise LibraryError("invalid_archive", str(error)) from error
    with archive:
        infos = archive.infolist()
        if len(infos) > MAX_MEMBERS:
            raise LibraryError("invalid_archive", "trop de fichiers")
        members = [(info, path) for info in infos if (path := _destination(info)) is not None]
        if sum(info.file_size for info, _path in members) > MAX_EXTRACTED_BYTES:
            raise LibraryError("invalid_archive", "archive trop grande")
        try:
            version = archive.read(ARCHIVE_PREFIX + "VERSION")[:64].decode("utf-8", "replace").strip()
        except (KeyError, OSError, zipfile.BadZipFile, zlib.error, EOFError) as error:
            raise LibraryError("invalid_archive", f"VERSION : {error}") from error
        if parse_version(version) is None:
            raise LibraryError("invalid_archive", f"VERSION : {version[:20]!r}")
        if expected_version is not None and parse_version(expected_version) != parse_version(version):
            raise LibraryError("invalid_archive", f"version {version}, attendue {expected_version}")
        target = base / version
        existing = _read_marker(target)
        if existing is not None:
            return existing
        try:
            base.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f"{TEMP_PREFIX}{version}-", dir=base))
        except OSError as error:
            raise LibraryError("write_failed", str(error)) from error
        try:
            try:
                _extract(archive, members, temporary)
            except (zipfile.BadZipFile, zlib.error, EOFError) as error:
                raise LibraryError("invalid_archive", str(error)) from error
            missing = [name for name in REQUIRED if not (temporary / name).is_file()]
            if missing:
                raise LibraryError("invalid_archive", "manque : " + ", ".join(missing))
            marker = {"version": version, "source": source, "installed": date.today().isoformat()}
            (temporary / MARKER).write_text(json.dumps(marker), encoding="utf-8")
            if target.exists() or target.is_symlink():                      # reste d'une version incomplète
                _remove(target)
            try:
                os.replace(temporary, target)
            except OSError:
                concurrent = _read_marker(target)                           # installée entre-temps ailleurs
                if concurrent is None:
                    raise
                return concurrent
        except OSError as error:
            raise LibraryError("write_failed", str(error)) from error
        finally:
            if temporary.exists():
                shutil.rmtree(temporary, ignore_errors=True)
    result = _read_marker(target)
    if result is None:
        raise LibraryError("write_failed", str(target))
    return result


def remove_old_versions(base=None) -> list[str]:
    """Supprime les versions autres que l'active, les versions incomplètes et
    les installations interrompues ; renvoie les noms supprimés. À appeler au
    lancement, avant toute transformation. Les autres fichiers sont laissés."""
    base = _base(base)
    current = active(base)
    removed = []
    try:
        entries = list(base.iterdir())
    except OSError:
        return removed
    for entry in entries:
        if not entry.is_dir() or entry.is_symlink():
            continue
        old = parse_version(entry.name) is not None and (current is None or entry.name != current.version)
        if old or entry.name.startswith(TEMP_PREFIX):
            try:
                shutil.rmtree(entry)
            except OSError:                                         # fichier ouvert (Windows) : plus tard
                continue
            removed.append(entry.name)
    return removed


def bundled_zip(folder=None) -> tuple[str, Path] | None:
    """L'archive livrée avec Varians (la plus récente du dossier) : ``(version,
    chemin)``, ou None."""
    folder = Path(folder) if folder is not None else BUNDLED_DIR
    found = []
    for path in folder.glob("tei-xsl-*.zip"):
        version = path.name[len("tei-xsl-"):-len(".zip")]
        if parse_version(version) is not None and path.is_file():
            found.append((parse_version(version), version, path))
    if not found:
        return None
    _key, version, path = max(found)
    return version, path


def ensure_installed(bundled_folder=None, base=None) -> Installed | None:
    """La version active, après avoir installé l'archive livrée si aucune
    version n'est installée ou si elle est plus récente. None si rien n'est
    installé (archive livrée absente ou abîmée)."""
    current = active(base)
    found = bundled_zip(bundled_folder)
    if found is not None and is_newer(found[0], current.version if current else None):
        try:
            return install_zip(found[1], base, source="bundled", expected_version=found[0])
        except LibraryError:
            pass
    return current


# --- Réseau -------------------------------------------------------------------------------------

def latest_version(url: str = LATEST_URL, timeout: float = 15) -> str:
    """Dernière version publiée par le TEI-C (fichier ``VERSION`` de sa branche
    ``released``)."""
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as reply:
            data = reply.read(64)
    except (OSError, ValueError, HTTPException) as error:
        raise LibraryError("network", str(error)) from error
    text = data.decode("utf-8", "replace").strip()
    if parse_version(text) is None:
        raise LibraryError("invalid_reply", text[:40])
    return text


def download(version: str, folder, progress=None, cancel=None, *, url: str = RELEASE_URL,
             timeout: float = 30, max_bytes: int = MAX_DOWNLOAD_BYTES) -> Path:
    """Télécharge l'archive de ``version`` dans ``folder`` et renvoie son
    chemin (``tei-xsl-<version>.zip``). ``progress(reçu, total)`` suit le
    téléchargement (total : 0 s'il est inconnu) ; ``cancel()`` vrai l'arrête.
    Le fichier n'apparaît qu'une fois complet (``.part`` entre-temps)."""
    if parse_version(version) is None:
        raise LibraryError("invalid_reply", str(version)[:40])
    folder = Path(folder)
    path = folder / f"tei-xsl-{version}.zip"
    part = path.with_name(path.name + ".part")
    try:
        folder.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise LibraryError("write_failed", str(error)) from error
    try:
        reply = urlopen(Request(url.format(version=version), headers=HEADERS), timeout=timeout)
    except (OSError, ValueError, HTTPException) as error:
        raise LibraryError("network", str(error)) from error
    try:
        with reply:
            try:
                total = max(0, int(reply.headers.get("Content-Length") or 0))
            except ValueError:
                total = 0
            if total > max_bytes:
                raise LibraryError("invalid_archive", "archive trop grande")
            if progress is not None:
                progress(0, total)
            try:
                stream = part.open("wb")
            except OSError as error:
                raise LibraryError("write_failed", str(error)) from error
            done = 0
            with stream:
                while True:
                    if cancel is not None and cancel():
                        raise LibraryError("cancelled")
                    try:
                        chunk = reply.read(CHUNK)
                    except (OSError, HTTPException) as error:
                        raise LibraryError("network", str(error)) from error
                    if not chunk:
                        break
                    done += len(chunk)
                    if done > max_bytes:
                        raise LibraryError("invalid_archive", "archive trop grande")
                    try:
                        stream.write(chunk)
                    except OSError as error:
                        raise LibraryError("write_failed", str(error)) from error
                    if progress is not None:
                        progress(done, total)
        if total and done != total:
            raise LibraryError("network", f"{done} octets reçus sur {total}")
        try:
            os.replace(part, path)
        except OSError as error:
            raise LibraryError("write_failed", str(error)) from error
        return path
    finally:
        try:
            part.unlink(missing_ok=True)
        except OSError:
            pass
