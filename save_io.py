# -*- coding: utf-8 -*-
"""Écriture atomique des éditions XML avec sauvegarde .bak."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path


def atomic_write_text_with_backup(path: str | Path, text: str, *, encoding: str = "utf-8") -> Path:
    """Écrit *text* atomiquement et conserve l'ancienne version en ``.bak``.

    Le nouveau contenu est d'abord écrit dans le même dossier. L'ancien fichier
    est ensuite renommé en ``<suffix>.bak`` puis le temporaire prend sa place.
    Contrairement à ``shutil.copy2`` + écriture, cela évite une copie complète
    supplémentaire sur le disque ou le partage réseau.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    backup = path.with_suffix(path.suffix + ".bak")
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

        if path.exists():
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
