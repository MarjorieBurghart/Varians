"""Fichiers trop volumineux pour l'éditeur.

Varians charge un fichier XML entier dans l'éditeur pour l'afficher, le
colorer, en indexer les ``<lb/>`` et le valider : le temps et la mémoire
croissent avec sa taille. Mesuré sur un TEI ordinaire : 10 Mo ≈ 15 s et
0,5 Go ; 30 Mo ≈ 40 s et 1,1 Go. Un fichier de 700 Mo ne s'ouvre jamais, et,
dernier projet ouvert, il bloquait le démarrage (fenêtre jamais affichée).

Au-delà de :data:`LARGE_FILE_BYTES`, Varians demande donc avant d'ouvrir
(:func:`confirm_large_files`) : un projet dont l'édition ou une partie
incluse dépasse le seuil (:func:`large_edition_files`), un document qu'on
affiche.
"""
from __future__ import annotations

from pathlib import Path

from xml_assembly import find_includes, include_path, path_key

# Seuil au-delà duquel Varians demande avant d'ouvrir un fichier.
LARGE_FILE_BYTES = 20 * 1024 * 1024

_MEGABYTE = 1024 * 1024


def _limit(limit):
    """``limit``, ou le seuil courant (lu à l'appel, pour les tests)."""
    return LARGE_FILE_BYTES if limit is None else limit


def file_size(path) -> int:
    """Taille de ``path`` en octets ; 0 s'il n'existe pas ou n'est pas lisible."""
    try:
        return Path(path).stat().st_size
    except OSError:
        return 0


def is_large(path, limit=None) -> bool:
    """``path`` dépasse-t-il le seuil (``limit`` octets, sinon
    :data:`LARGE_FILE_BYTES`) ?"""
    return file_size(path) > _limit(limit)


def megabytes(size: int) -> int:
    """``size`` octets, en Mo arrondis ; au moins 1."""
    return max(1, round(size / _MEGABYTE))


def large_edition_files(edition, limit=None) -> list[tuple[Path, int]]:
    """Fichiers de l'édition ``edition`` qui dépassent le seuil, avec leur
    taille : l'édition, puis ses parties (``xi:include`` locaux, inclus par
    l'édition ou par une partie), dans l'ordre, chacun une fois.

    Un fichier trop gros est signalé sans être lu ; un fichier absent,
    illisible ou mal formé est ignoré (l'ouverture le signalera)."""
    limit = _limit(limit)
    found: list[tuple[Path, int]] = []
    seen: set[str] = set()

    def visit(path: Path) -> None:
        key = path_key(path)
        if key in seen or not path.is_file():
            return
        seen.add(key)
        size = file_size(path)
        if size > limit:
            found.append((path, size))
            return
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return
        for include in find_includes(text):
            target = include_path(include.href, path)
            if target is not None:
                visit(target)

    visit(Path(edition))
    return found


def confirm_large_files(parent, files) -> bool:
    """Demande s'il faut ouvrir quand même les fichiers ``files``
    (``[(chemin, taille)]``) ; vrai sans question si la liste est vide.
    « Annuler » est le choix par défaut, et celui de la touche Échap."""
    if not files:
        return True
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMessageBox
    from app_context import tr

    items = "\n".join(tr("large_file.item", file=str(path), size=megabytes(size)) for path, size in files)
    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Icon.Warning)
    box.setTextFormat(Qt.TextFormat.PlainText)
    box.setWindowTitle(tr("large_file.title"))
    box.setText(tr("large_file.text", files=items, limit=megabytes(LARGE_FILE_BYTES)))
    open_button = box.addButton(tr("large_file.open"), QMessageBox.ButtonRole.AcceptRole)
    cancel_button = box.addButton(tr("common.cancel"), QMessageBox.ButtonRole.RejectRole)
    box.setDefaultButton(cancel_button)
    box.setEscapeButton(cancel_button)
    box.exec()
    return box.clickedButton() is open_button
