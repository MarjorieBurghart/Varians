# -*- coding: utf-8 -*-
"""Écriture atomique des éditions XML et de project.xml, avec sauvegarde .bak.

Un fichier enregistré garde ses droits et ses fins de ligne (CRLF ou LF) ;
un fichier en lecture seule n'est pas remplacé (red team, A5, A7, A8)."""
from __future__ import annotations

import errno
import os
import re
import stat
import tempfile
import xml.etree.ElementTree as ET
from pathlib import Path


class ReadOnlyFileError(PermissionError):
    """Le fichier est en lecture seule : Varians ne le remplace pas."""


def _line_ending(path: Path) -> str:
    """Fin de ligne du fichier existant *path* : celle de sa première ligne."""
    try:
        with open(path, "rb") as stream:
            head = stream.read(65536)
    except OSError:
        return "\n"
    index = head.find(b"\n")
    return "\r\n" if index > 0 and head[index - 1:index] == b"\r" else "\n"


def _new_file_mode() -> int:
    """Droits d'un fichier nouveau, comme les donne le système (masque)."""
    mask = os.umask(0)
    os.umask(mask)
    return 0o666 & ~mask


def atomic_write_text_with_backup(path: str | Path, text: str, *, encoding: str = "utf-8",
                                  newline: str | None = None) -> Path:
    """Écrit *text* atomiquement et conserve l'ancienne version en ``.bak``.

    Le nouveau contenu est d'abord écrit dans le même dossier. L'ancien fichier
    est ensuite renommé en ``<suffix>.bak`` puis le temporaire prend sa place.
    Contrairement à ``shutil.copy2`` + écriture, cela évite une copie complète
    supplémentaire sur le disque ou le partage réseau.

    Le fichier garde ses droits et, sans *newline*, sa fin de ligne (CRLF ou
    LF ; LF pour un fichier nouveau). Un fichier en lecture seule lève
    ``ReadOnlyFileError``, sans rien écrire.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_suffix(path.suffix + ".bak")
    exists = path.exists()
    if exists:
        mode = stat.S_IMODE(path.stat().st_mode)
        # Sans aucun droit d'écriture (même pour l'administrateur), ou refusé.
        if not mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH) or not os.access(path, os.W_OK):
            raise ReadOnlyFileError(errno.EACCES, "Fichier en lecture seule", str(path))
    else:
        mode = _new_file_mode()
    newline = newline or (_line_ending(path) if exists else "\n")
    text = text.replace("\r\n", "\n")
    if newline != "\n":
        text = text.replace("\n", newline)
    temp_path = None
    old_moved = False

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=encoding,
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as fh:
            temp_path = Path(fh.name)
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.chmod(temp_path, mode)

        if exists:
            os.replace(path, backup)
            old_moved = True

        try:
            os.replace(temp_path, path)
            temp_path = None
        except Exception:
            # En cas d'échec après déplacement de l'original, restaurer avant de
            # propager l'erreur afin que l'utilisateur ne perde jamais son fichier.
            if old_moved and backup.exists() and not path.exists():
                os.replace(backup, path)
                old_moved = False
            raise
        return backup
    finally:
        if temp_path is not None:
            try:
                temp_path.unlink(missing_ok=True)
            except Exception:
                pass


# --- project.xml ---------------------------------------------------------------------------

_PROLOG = re.compile(r"\A﻿?(?:<\?xml\b.*?\?>)?((?:\s+|<!--.*?-->|<\?.*?\?>)*)", re.S)
_MISC = re.compile(r"<!--.*?-->|<\?.*?\?>", re.S)


def _root_end(text: str) -> int:
    """Fin de l'élément racine : ce qui suit n'est que commentaires,
    instructions de traitement et blancs."""
    end = len(text.rstrip())
    while True:
        head = text[:end]
        start = head.rfind("<!--") if head.endswith("-->") else head.rfind("<?") if head.endswith("?>") else -1
        if start < 0:
            return end
        end = len(text[:start].rstrip())


def _misc(text: str) -> str:
    return "\n".join(match.group(0) for match in _MISC.finditer(text))


class XmlFile:
    """Un fichier XML (project.xml) lu avec ses commentaires et instructions
    de traitement, y compris ceux d'avant et d'après l'élément racine,
    qu'ElementTree ne garde pas ; ``write`` le réécrit atomiquement,
    l'ancienne version en ``.bak``. Avec *tree*, l'arbre remplace celui du
    fichier, dont les commentaires d'avant et d'après sont gardés s'il est
    lisible."""

    def __init__(self, path: str | Path, tree: ET.ElementTree | None = None):
        self.path = Path(path)
        self.prolog = self.epilogue = ""
        try:
            text = self.path.read_text(encoding="utf-8")
            parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True, insert_pis=True))
            parser.feed(text)
            root = parser.close()
        except (OSError, UnicodeError, ET.ParseError):
            if tree is None:
                raise
        else:
            self.prolog = _misc(_PROLOG.match(text).group(1))
            self.epilogue = _misc(text[_root_end(text):])
            tree = tree if tree is not None else ET.ElementTree(root)
        self.tree = tree

    def write(self) -> Path:
        ET.indent(self.tree, space="  ")
        parts = ["<?xml version='1.0' encoding='utf-8'?>", self.prolog,
                 ET.tostring(self.tree.getroot(), encoding="unicode"), self.epilogue]
        atomic_write_text_with_backup(self.path, "\n".join(part for part in parts if part))
        return self.path
