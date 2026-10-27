# -*- coding: utf-8 -*-
"""Résultats en plusieurs fichiers d'un scénario Saxon (V0.9.2.7), sans Qt.

Un scénario peut demander un *paquet* (``TransformScenario.package``) :

- ``pages`` : la feuille écrit ses pages (``xsl:result-document``) dans le
  dossier du résultat, dont la première est le résultat du scénario
  (``index.html`` des TEI Stylesheets, avec ``STDOUT=false`` et
  ``splitLevel=0``) ; son résultat principal, vide, n'est pas gardé ;
- ``docx``, ``odt``, ``epub`` : la feuille écrit les fichiers d'une archive
  dans un dossier de travail temporaire, dont elle reçoit l'adresse
  (``word-directory``, ``outputDir``, ``directory``) ; Varians le prépare
  avant (modèle déballé, images), place le résultat principal
  (``word/document.xml``, ``content.xml``), puis en fait l'archive, qui est
  le résultat du scénario : ``mimetype`` en tête et non compressé (ODT,
  EPUB), sans les fichiers de travail.

C'est ce que font, pour les TEI Stylesheets, leurs tâches ant
(``common/teianttasks.xml`` : ``builddocx``, ``buildodt``, ``buildepub``),
sans Java : les images sont copiées sous leur nom ``resource{N}.{ext}``, et
leurs dimensions lues dans l'en-tête des PNG, JPEG et GIF
(``image-size-info.xml``). Une image distante n'est pas téléchargée.
"""
from __future__ import annotations

import io
import shutil
import struct
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

PACKAGES = ("pages", "docx", "odt", "epub")
ARCHIVES = ("docx", "odt", "epub")
# Paramètre qui reçoit l'adresse (file:) du dossier de travail.
FOLDER_PARAMS = {"docx": "word-directory", "odt": "outputDir", "epub": "directory"}
# Paramètres par défaut ; ceux du scénario les remplacent.
DEFAULT_PARAMS = {"pages": (("STDOUT", "false"), ("splitLevel", "0")), "epub": (("fixgraphicsurl", "true"),)}
# Dossier des images dans l'archive, et chemin noté dans image-size-info.xml.
_MEDIA = {"docx": ("word/media", "media"), "odt": ("Pictures", "Pictures"), "epub": ("OPS/media", None)}
# Fichiers de travail, jamais mis dans l'archive.
_WORK_FILES = {"image-size-info.xml", "copy.xml", "tmp1.xml", "tmp2.xml", "newdocument.xml"}
# Ce que les tâches ant retirent du modèle DOCX avant la transformation.
_DOCX_REMOVED = ("docProps/custom.xml", "word/endnotes.xml", "word/footnotes.xml")
_DOCX_REMOVED_PATTERNS = ("word/footer*", "word/header*")
_DOCX_REMOVED_FOLDERS = ("customXml", "word/printerSettings")
_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
_TEI = "http://www.tei-c.org/ns/1.0"
_TEIX = "http://www.tei-c.org/ns/Examples"


class PackageError(Exception):
    """Échec de la préparation d'un paquet : ``code`` (``transform.error``),
    ``write_refused`` pour un fichier du modèle hors du dossier de travail,
    ``xslt_missing`` pour un modèle absent, ``output_failed`` sinon."""

    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def _extract(archive_path, folder):
    """Déballe l'archive ``archive_path`` dans ``folder`` ; un nom qui en
    sortirait est refusé."""
    folder = Path(folder).resolve()
    try:
        with zipfile.ZipFile(archive_path) as archive:
            for info in archive.infolist():
                target = (folder / info.filename).resolve()
                if target != folder and folder not in target.parents:
                    raise PackageError("write_refused", f"{archive_path}: {info.filename}")
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read(info))
    except (OSError, zipfile.BadZipFile) as exc:
        raise PackageError("output_failed", f"{archive_path}: {exc}") from exc


def image_size(data) -> tuple[int, int] | None:
    """``(largeur, hauteur)`` en pixels d'une image PNG, GIF ou JPEG, lues
    dans son en-tête ; None pour un autre format."""
    if data[:8] == b"\x89PNG\r\n\x1a\n" and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a") and len(data) >= 10:
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        index = 2
        while index + 9 <= len(data):
            if data[index] != 0xFF:
                index += 1
                continue
            marker = data[index + 1]
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
                height, width = struct.unpack(">HH", data[index + 5:index + 9])
                return width, height
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            index += 2 + struct.unpack(">H", data[index + 2:index + 4])[0]
    return None


def _base_folder(element, source):
    """Le dossier d'où se résolvent les adresses relatives de ``element``."""
    base = element.base or ""
    parsed = urllib.parse.urlparse(base)
    if parsed.scheme == "file":
        return Path(urllib.request.url2pathname(urllib.parse.unquote(parsed.path))).parent
    if base and not parsed.scheme:
        return Path(base).parent
    return Path(source).parent


def copy_images(package, root, source, folder, journal):
    """Copie dans ``folder`` les images locales de ``root`` (``graphic`` et
    ``media`` avec ``@url``, numérotées comme le font les TEI Stylesheets,
    ``resource{N}.{ext}``) ; pour DOCX et ODT, écrit leurs dimensions dans
    ``image-size-info.xml``. Une image distante ou absente va au journal
    (``image_skipped``)."""
    from lxml import etree
    media, noted = _MEDIA[package]
    counters, sizes = {}, []
    for element in root.iter(f"{{{_TEI}}}graphic", f"{{{_TEI}}}media"):
        name = etree.QName(element).localname
        counters[name] = counters.get(name, 0) + 1
        url = (element.get("url") or "").strip()
        if not url or any(etree.QName(parent).namespace == _TEIX for parent in element.iterancestors()):
            continue
        extension = url.rsplit(".", 1)[-1] if "." in url.rsplit("/", 1)[-1] else ""
        target = f"resource{counters[name]}.{extension}"
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme and parsed.scheme != "file":
            journal.append(["image_skipped", url])
            continue
        path = (Path(urllib.request.url2pathname(urllib.parse.unquote(parsed.path))) if parsed.scheme
                else _base_folder(element, source) / urllib.parse.unquote(url))
        try:
            data = path.read_bytes()
        except OSError:
            journal.append(["image_skipped", url])
            continue
        destination = Path(folder) / media / target
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        size = image_size(data)
        if noted is not None and size is not None:
            sizes.append((f"{noted}/{target}", size))
    if noted is not None and sizes:
        images = etree.Element("images")
        for url, (width, height) in sizes:
            image = etree.SubElement(images, "image", url=url)
            etree.SubElement(image, "height").text = str(height)
            etree.SubElement(image, "width").text = str(width)
        Path(folder, "image-size-info.xml").write_bytes(etree.tostring(images, xml_declaration=True, encoding="utf-8"))


def prepare(package, folder, template=None, fixstyle=None, apply_xslt=None):
    """Prépare le dossier de travail ``folder`` d'une archive : le modèle
    déballé (DOCX, ODT), sans ce qu'en retirent les tâches ant, et les
    styles du DOCX passés par ``fixstyle`` (``apply_xslt(feuille, xml)``
    rend le résultat)."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    if package in ("docx", "odt"):
        if not template or not Path(template).is_file():
            raise PackageError("xslt_missing", str(template or package))
        _extract(template, folder)
    if package == "docx":
        for name in _DOCX_REMOVED:
            (folder / name).unlink(missing_ok=True)
        for pattern in _DOCX_REMOVED_PATTERNS:
            for path in folder.glob(pattern):
                path.unlink()
        for name in _DOCX_REMOVED_FOLDERS:
            shutil.rmtree(folder / name, ignore_errors=True)
        styles = folder / "word" / "styles.xml"
        if fixstyle and apply_xslt is not None and Path(fixstyle).is_file() and styles.is_file():
            styles.write_bytes(apply_xslt(Path(fixstyle), styles))


def finish(package, folder, main) -> bytes:
    """L'archive du paquet : le résultat principal ``main`` mis à sa place,
    les fichiers renommés comme le font les tâches ant, puis ``folder`` mis
    en archive."""
    folder = Path(folder)
    if package == "docx":
        (folder / "word").mkdir(parents=True, exist_ok=True)
        (folder / "word" / "document.xml").write_bytes(main)
        for name in ("core", "app", "custom"):
            new = folder / "docProps" / f"new{name}.xml"
            if new.is_file():
                new.replace(folder / "docProps" / f"{name}.xml")
        comments = folder / "word" / "comments.xml"
        if not comments.is_file():                         # cité par document.xml.rels
            comments.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<w:comments xmlns:w="{_W}"/>\n',
                                encoding="utf-8")
    elif package == "odt":
        (folder / "content.xml").write_bytes(main)
    elif package == "epub" and main.strip() and not (folder / "OPS" / "index.html").is_file():
        (folder / "OPS").mkdir(parents=True, exist_ok=True)
        (folder / "OPS" / "index.html").write_bytes(main)
    first = "[Content_Types].xml" if package == "docx" else "mimetype"
    files = sorted(path.relative_to(folder).as_posix() for path in folder.rglob("*") if path.is_file())
    files = [name for name in files if name not in _WORK_FILES]
    if first in files:
        files.remove(first)
        files.insert(0, first)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in files:
            data = (folder / name).read_bytes()
            if name == "mimetype":
                archive.writestr(zipfile.ZipInfo("mimetype", date_time=(1980, 1, 1, 0, 0, 0)), data,
                                 compress_type=zipfile.ZIP_STORED)
            else:
                archive.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()
