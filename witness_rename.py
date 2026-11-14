# -*- coding: utf-8 -*-
"""Changer le sigle d'un témoin (V0.9.4.0), sans Qt.

Le sigle P devient P2 : l'identifiant du témoin devient celui du nouveau
sigle, partout où il est écrit. :func:`witness_rename_plan.plan_witness_rename`
en fait le plan, sans rien écrire (project.xml, documents XML du projet,
JSON d'alignement, fichiers et dossiers nommés d'après le témoin ; refus) ;
ce module l'applique (V0.9.4.7 : plan et application dans deux modules).

:func:`apply_witness_rename` applique le plan d'un bloc : écritures
atomiques avec copie ``.bak``, puis renommages ; rien n'est fait si un
fichier a changé depuis le plan, et au moindre échec tout est remis dans
l'état d'avant. :func:`migrate_view_settings` reporte sur le nouvel
identifiant les réglages d'affichage du projet (ordre, hauteurs, fenêtres
détachées…).

Avant toute modification, un journal (``witness_rename_plan.journal_path``)
décrit le changement : si Varians ou l'ordinateur s'arrête en plein
changement, :func:`recover_interrupted_rename` remet le projet dans son
état d'avant (``journal_state`` dit où il en est)."""
from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from i18n import Message
from witness_rename_plan import Move, RenamePlan, _DRIVE_RE, _entry_path, journal_path, read_journal


# --- Application : tout ou rien -------------------------------------------------------------

class RenameError(Exception):
    """Le changement n'a pas pu se faire ; ``message`` (i18n.Message) dit
    pourquoi, et si les fichiers ont été remis dans leur état d'avant."""

    def __init__(self, message):
        super().__init__(str(message))
        self.message = message


@dataclass(frozen=True)
class RenameResult:
    """Ce qu'a fait :func:`apply_witness_rename` : fichiers réécrits, leurs
    copies ``.bak`` (état d'avant le changement) et renommages faits."""
    written: tuple = ()          # fichiers réécrits (à leur place d'avant les renommages)
    backups: tuple = ()          # leurs copies .bak
    moved: tuple = ()            # Move faits


def _rename(move: Move) -> None:
    """Renomme un fichier ou un dossier ; jamais par-dessus un autre. Un
    changement de casse seule passe par un nom provisoire (Windows, macOS)."""
    source, target = move.source, move.target
    if target.exists() and not (move.case_only and os.path.samefile(source, target)):
        raise FileExistsError(17, "Le fichier existe déjà", str(target))
    if not move.case_only:
        os.rename(source, target)
        return
    temporary = source.with_name(f".{source.name}.varians-rename")
    os.rename(source, temporary)
    try:
        os.rename(temporary, target)
    except OSError:
        os.rename(temporary, source)
        raise


def _set_aside(backup):
    """Copie ``.bak`` d'un enregistrement précédent mise de côté (renommée)
    avant l'écriture qui la remplacerait ; None s'il n'y en a pas."""
    if not backup.exists():
        return None
    aside = backup.with_name(f".{backup.name}.varians-rename")
    os.replace(backup, aside)
    return aside


def _rollback(written, moved, aside):
    """Remet les fichiers dans leur état d'avant, anciennes copies ``.bak``
    comprises ; renvoie ceux qui n'ont pas pu l'être."""
    failed = []
    for move in reversed(moved):
        try:
            _rename(Move(move.target, move.source))
        except OSError:
            failed.append(move.target)
    for path, backup in reversed(written):
        try:
            os.replace(backup, path)
        except OSError:
            failed.append(path)
    for backup, previous in reversed(aside):
        # Tant que la copie d'avant le changement est là (son fichier n'a pas
        # pu être rendu), l'ancienne copie reste de côté.
        if os.path.lexists(backup):
            continue
        try:
            os.replace(previous, backup)
        except OSError:
            failed.append(backup)
    return failed


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _file_digest(path):
    try:
        return _digest(Path(path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError):
        return None


def _stored(root, path) -> str:
    return Path(path).relative_to(root).as_posix()


def _write_journal(plan):
    """Écrit, avant toute modification, de quoi remettre le projet dans son
    état d'avant si Varians ou l'ordinateur s'arrête en plein changement.
    Chemins relatifs au dossier du projet (tous y sont)."""
    root = _entry_path(plan.root / "project.xml").parent
    data = {"format": 1, "old": plan.old_siglum, "new": plan.new_siglum, "old_id": plan.old_id,
            "new_id": plan.new_id,
            "files": [{"path": _stored(root, _entry_path(c.path)), "original": _digest(c.original),
                       "new": _digest(c.text)} for c in plan.changes],
            "moves": [{"source": _stored(root, m.source), "target": _stored(root, m.target)} for m in plan.moves]}
    path = journal_path(plan.root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with open(temporary, "w", encoding="utf-8") as stream:
        json.dump(data, stream, ensure_ascii=False, indent=1)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


_DIGEST_RE = re.compile(r"[0-9a-f]{64}")


def _journal_entries(root, data):
    """``(fichiers, renommages)`` d'un journal vérifié, ou None. Un journal
    vient du dossier du projet, qui peut avoir été reçu d'ailleurs : chaque
    chemin doit être relatif, sans « .. », dans le projet (liens suivis
    pour les dossiers), et un renommage ne change qu'un nom, dans son
    dossier."""
    if not isinstance(data, dict) or data.get("format") != 1 or data.get("damaged"):
        return None
    files, moves = data.get("files"), data.get("moves")
    if not isinstance(files, list) or not isinstance(moves, list):
        return None
    real_root = os.path.realpath(root)

    def inside(value):
        if not isinstance(value, str) or not value or value.startswith(("/", "\\")) or _DRIVE_RE.match(value):
            return None
        parts = re.split(r"[\\/]", value)
        if any(part in ("", ".", "..") or ":" in part for part in parts):
            return None
        parent = os.path.realpath(os.path.join(real_root, *parts[:-1]))
        try:
            if os.path.commonpath([real_root, parent]) != real_root:
                return None
        except ValueError:
            return None
        return Path(parent) / parts[-1]

    checked_files, checked_moves = [], []
    for entry in files:
        if not isinstance(entry, dict):
            return None
        path = inside(entry.get("path"))
        original, new = entry.get("original"), entry.get("new")
        if path is None or not all(isinstance(x, str) and _DIGEST_RE.fullmatch(x) for x in (original, new)):
            return None
        checked_files.append((path, original, new))
    for entry in moves:
        if not isinstance(entry, dict):
            return None
        source, target = inside(entry.get("source")), inside(entry.get("target"))
        if source is None or target is None or source.parent != target.parent:
            return None
        checked_moves.append(Move(source, target))
    return checked_files, checked_moves


def _present(path) -> bool:
    """L'entrée existe-t-elle sous ce nom exact (casse comprise) ?"""
    try:
        return path.name in os.listdir(path.parent)
    except OSError:
        return False


def _after_moves(path, moves):
    """Où se trouve, une fois les renommages faits, le fichier ``path``."""
    for move in moves:
        if path == move.source:
            return move.target
        try:
            return move.target / path.relative_to(move.source)
        except ValueError:
            continue
    return path


def _aside(path):
    backup = path.with_suffix(path.suffix + ".bak")
    return backup, backup.with_name(f".{backup.name}.varians-rename")


@dataclass(frozen=True)
class Recovery:
    """Issue de la reprise d'un changement interrompu : ``none`` (pas de
    journal), ``rejected`` (journal non valable, écarté sans rien toucher),
    ``completed`` (le changement était achevé : gardé), ``restored``
    (projet remis dans son état d'avant) ou ``failed`` (``failed`` : les
    fichiers non remis ; le journal reste)."""
    status: str
    data: dict = field(default_factory=dict)
    failed: list = field(default_factory=list)


def journal_state(root):
    """``(état, journal)`` : none, invalid, completed ou interrupted."""
    data = read_journal(root)
    if data is None:
        return "none", {}
    entries = _journal_entries(root, data)
    if entries is None:
        return "invalid", data if isinstance(data, dict) else {}
    files, moves = entries
    done = all(_present(m.target) and not _present(m.source) for m in moves) and all(
        _file_digest(_after_moves(path, moves)) == new for path, _original, new in files)
    return ("completed" if done else "interrupted"), data


def _reject_journal(root):
    path = journal_path(root)
    try:
        os.replace(path, path.with_name("witness-rename.rejected.json"))
    except OSError:
        pass


def recover_interrupted_rename(root) -> Recovery:
    """Reprise d'un changement de sigle interrompu (journal présent).
    Journal non valable : écarté (renommé), rien d'autre n'est touché.
    Changement achevé (tous les fichiers dans leur état d'après) : gardé,
    journal effacé. Sinon, renommages défaits, fichiers rendus depuis leur
    copie .bak (vérifiée par son empreinte), anciennes copies .bak remises ;
    un fichier qui n'est ni l'avant ni l'après n'est pas touché, et le
    journal reste."""
    root = Path(root)
    state, data = journal_state(root)
    if state == "none":
        return Recovery("none")
    if state == "invalid":
        _reject_journal(root)
        return Recovery("rejected", data)
    files, moves = _journal_entries(root, data)
    if state == "completed":
        for path, _original, _new in files:
            _backup, aside = _aside(_after_moves(path, moves))
            if os.path.lexists(aside):
                try:
                    os.unlink(aside)
                except OSError:
                    pass
        try:
            journal_path(root).unlink()
        except OSError:
            pass
        return Recovery("completed", data)
    failed = []
    for move in reversed(moves):
        source, target = move.source, move.target
        temporary = source.with_name(f".{source.name}.varians-rename")
        try:
            if os.path.lexists(temporary) and not _present(source):
                os.rename(temporary, source)
            elif _present(target) and not _present(source):
                _rename(Move(target, source))
        except OSError:
            failed.append(target)
    for path, original, new in reversed(files):
        backup, aside = _aside(path)
        try:
            current = _file_digest(path) if os.path.lexists(path) else None
            if current != original:
                if current not in (new, None) or _file_digest(backup) != original:
                    failed.append(path)
                    continue
                os.replace(backup, path)
            if os.path.lexists(aside) and not os.path.lexists(backup):
                os.replace(aside, backup)
            for temporary in path.parent.glob(f".{path.name}.*.tmp"):
                temporary.unlink()
        except OSError:
            failed.append(path)
    if failed:
        return Recovery("failed", data, failed)
    try:
        journal_path(root).unlink()
    except OSError:
        pass
    return Recovery("restored", data)


def _verify(plan):
    """Le projet changé se lit, avec le témoin sous son nouvel identifiant."""
    from project_config import load_project
    project = load_project(plan.project_path)
    ids = [witness.id for witness in project.witnesses]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{plan.new_id} : deux témoins ont le même identifiant")
    if plan.new_id not in project.witness_by_id or (
            plan.old_id != plan.new_id and plan.old_id in project.witness_by_id):
        raise ValueError(f"{plan.old_id} → {plan.new_id} : témoin introuvable après le changement")


def apply_witness_rename(plan: RenamePlan) -> RenameResult:
    """Applique le plan d'un bloc : chaque fichier réécrit (écriture
    atomique, copie ``.bak`` de l'ancien), puis les fichiers et dossiers
    renommés. Rien n'est fait si un fichier a changé depuis le plan ; au
    moindre échec, tout est remis dans l'état d'avant (``RenameError``)."""
    from save_io import atomic_write_text_with_backup
    if not plan.ok:
        raise ValueError("Plan refusé : " + "; ".join(plan.problems))
    for change in plan.changes:
        try:
            current = change.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            current = None
        if current != change.original:
            raise RenameError(Message("witness_rename.changed", file=plan.display_path(change.path)))
    for move in plan.moves:
        if not move.source.exists():
            raise RenameError(Message("witness_rename.changed", file=plan.display_path(move.source)))
        if move.target.exists() and not (move.case_only and os.path.samefile(move.source, move.target)):
            raise RenameError(Message("witness_rename.target_exists", file=plan.display_path(move.target)))
    interrupted = read_journal(plan.root)
    if interrupted is not None:
        raise RenameError(Message("witness_rename.interrupted", old=interrupted.get("old", "?"),
                                  new=interrupted.get("new", "?")))
    written, moved, aside = [], [], []
    current = plan.project_path
    try:
        _write_journal(plan)
    except OSError as error:
        journal_path(plan.root).unlink(missing_ok=True)
        raise RenameError(Message("witness_rename.failed", file=plan.display_path(journal_path(plan.root)),
                                  error=getattr(error, "strerror", None) or str(error))) from error
    try:
        for change in plan.changes:
            current = change.path
            backup = change.path.with_suffix(change.path.suffix + ".bak")
            previous = _set_aside(backup)
            if previous is not None:
                aside.append((backup, previous))
            written.append((change.path, atomic_write_text_with_backup(change.path, change.text)))
        for move in plan.moves:
            current = move.source
            _rename(move)
            moved.append(move)
        current = plan.project_path
        _verify(plan)
    except Exception as error:
        failed = _rollback(written, moved, aside)
        if not failed:
            try:
                journal_path(plan.root).unlink(missing_ok=True)
            except OSError:
                pass
        detail = getattr(error, "strerror", None) or str(error)
        if failed:
            raise RenameError(Message("witness_rename.rollback_failed", file=plan.display_path(current),
                                      error=detail, files=", ".join(plan.display_path(p) for p in failed))) from error
        raise RenameError(Message("witness_rename.failed", file=plan.display_path(current), error=detail)) from error
    # Réussite : chaque .bak garde l'état d'avant le changement ; les copies
    # plus anciennes sont abandonnées.
    for _backup, previous in aside:
        try:
            previous.unlink()
        except OSError:
            pass
    # Un journal qui ne s'efface pas (fichier verrouillé) ne défait rien : à
    # la prochaine ouverture, le changement est reconnu achevé.
    try:
        journal_path(plan.root).unlink(missing_ok=True)
    except OSError:
        pass
    return RenameResult(tuple(path for path, _backup in written), tuple(backup for _path, backup in written),
                        tuple(moved))


# --- Réglages d'affichage -----------------------------------------------------------------

_SETTING_LISTS = ("witnessOrder", "visibleWitnesses", "detachedWitnesses")
_SETTING_MAPS = ("witnessLeadsEdition", "witnessHeights", "horizontalSizes", "gridSizes")
_SETTING_PER_WITNESS = ("floatingGeometry", "floatingAlwaysOnTop")


def _decoded(raw, kind):
    """``(valeur, enregistrée en JSON)`` d'un réglage, ou ``(None, False)``."""
    if isinstance(raw, str):
        try:
            value = json.loads(raw) if raw else None
        except ValueError:
            return None, False
        return (value, True) if isinstance(value, kind) else (None, False)
    if isinstance(raw, kind) or (kind is list and isinstance(raw, tuple)):
        return (list(raw) if kind is list else dict(raw)), False
    return None, False


def migrate_view_settings(settings, prefix: str, old: str, new: str) -> None:
    """Reporte sur ``new`` les réglages d'affichage du témoin ``old`` sous
    ``prefix`` (``projectView/<empreinte du projet>/``) : ordre, témoins
    visibles et détachés, bouton au livre, hauteurs et largeurs, position et
    « toujours au premier plan » des fenêtres détachées. ``settings`` :
    QSettings, ou tout objet de mêmes méthodes (``value``, ``setValue``,
    ``remove``, ``contains``)."""
    if old == new:
        return
    for name in _SETTING_LISTS:
        key = prefix + name
        items, encoded = _decoded(settings.value(key, None), list)
        if items and old in items:
            items = [new if item == old else item for item in items]
            settings.setValue(key, json.dumps(items, ensure_ascii=False) if encoded else items)
    for name in _SETTING_MAPS:
        key = prefix + name
        values, encoded = _decoded(settings.value(key, None), dict)
        if values and old in values:
            values = {new if item == old else item: value for item, value in values.items()}
            settings.setValue(key, json.dumps(values, ensure_ascii=False) if encoded else values)
    for name in _SETTING_PER_WITNESS:
        before, after = f"{prefix}{name}/{old}", f"{prefix}{name}/{new}"
        if settings.contains(before):
            value = settings.value(before)
            settings.remove(before)
            settings.setValue(after, value)
