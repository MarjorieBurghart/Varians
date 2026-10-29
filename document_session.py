# -*- coding: utf-8 -*-
"""État d'un document XML ouvert dans Varians.

Jusqu'à V0.8.5.26.2, cet état était dispersé dans ``MainWindow`` sous forme
d'attributs (chemin, indicateur « modifié », dernière validation RELAX NG,
cache des ``<lb/>``…), ce qui supposait un seul document par fenêtre.
``DocumentSession`` le regroupe : chaque document ouvert possède sa propre
session. ``MainWindow`` y accède par ``self.document`` ; ses anciens noms
d'attributs restent disponibles sous forme de propriétés de compatibilité.

Le module ne dépend pas de Qt : le ``QTextDocument`` (texte et historique
annuler/refaire) est simplement référencé par ``text_document``.
"""
from __future__ import annotations

import bisect
import re
from pathlib import Path
from typing import Any, Iterable, Optional

from rng_completion import XmlContextCache

Span = tuple[int, int]

# Longueur du texte, avant une modification, examinée pour savoir si elle a
# lieu à l'intérieur d'une balise (voir LbIndex.apply_edit).
LB_EDIT_LOOKBACK = 4096
# Fins d'un commentaire, d'une CDATA, d'une instruction de traitement (voir
# LbIndex.apply_edit) ; leurs débuts commencent par « < ».
_CLOSERS = ("-->", "]]>", "?>")
# Une balise complète : guillemets respectés, sans « < » dans une valeur.
_CLOSED_TAG_RE = re.compile(r"<[^<>\"']*(?:(?:\"[^\"<]*\"|'[^'<]*')[^<>\"']*)*>")


def _inside_tag(preceding: str) -> bool:
    """Vrai si la fin de *preceding* est à l'intérieur d'une balise : son
    dernier « < » n'a pas encore été fermé (un « > » entre guillemets ne
    ferme rien)."""
    start = preceding.rfind("<")
    return start >= 0 and _CLOSED_TAG_RE.match(preceding, start) is None


def file_stamp(path) -> Optional[tuple[int, int]]:
    """(date de modification en ns, taille) du fichier *path* ; None s'il
    est introuvable. Un fichier modifié hors de Varians depuis sa lecture
    change d'empreinte (red team, A3)."""
    try:
        stat = Path(path).stat()
    except (OSError, TypeError):
        return None
    return stat.st_mtime_ns, stat.st_size


class LbIndex:
    """Positions des ``<lb/>`` du témoin pivot dans le texte source.

    L'index est reconstruit à la demande (``dirty``) et décalé sans nouveau
    balayage lors des modifications ordinaires du texte (``apply_edit``).
    """

    def __init__(self) -> None:
        self.spans: list[Span] = []
        self.dirty = True

    def set(self, spans: Iterable[Span] | None) -> None:
        self.spans = list(spans or [])
        self.dirty = False

    def invalidate(self) -> None:
        self.dirty = True

    @staticmethod
    def scan(text: str, pattern) -> list[Span]:
        return [(m.start(), m.end()) for m in pattern.finditer(text)]

    def ordinal_at(self, position: int) -> Optional[int]:
        """Rang du dernier ``<lb/>`` commençant avant ou à ``position``.

        Avant le premier ``<lb/>``, renvoie 0 ; sans ``<lb/>``, ``None``.
        """
        spans = self.spans
        if not spans:
            return None
        starts = [x[0] for x in spans]
        i = bisect.bisect_right(starts, int(position)) - 1
        return max(0, min(len(spans) - 1, i))

    def apply_edit(self, position: int, chars_removed: int, chars_added: int,
                   inserted: str = "", preceding: str = "", removed_text: str | None = "",
                   following: str = "") -> None:
        """Répercute une modification du texte sur l'index.

        ``inserted`` est le texte inséré à ``position`` ; ``preceding`` est le
        texte qui précède ``position`` après la modification (quelques milliers
        de caractères suffisent). Une modification qui touche un ``<lb/>``
        existant, qui insère ou retire (``removed_text`` ; None : inconnu)
        ``<`` ou ``>``, qui forme ou défait une fin de commentaire, de CDATA
        ou d'instruction (``preceding`` et ``following`` : le texte avant et
        après la modification) ou qui a lieu à l'intérieur d'une balise
        invalide l'index (nouveau balayage au prochain accès) ; sinon les
        ``<lb/>`` situés après la modification sont simplement décalés.
        """
        if self.dirty:
            return
        # À l'intérieur d'une balise (dernier « < » après le dernier « > »),
        # même sans saisir « < » ni « > », une balise quelconque peut devenir
        # un <lb/> pivot, ou cesser de l'être (ex. edRef="#T" -> "#T1").
        if _inside_tag(preceding):
            self.dirty = True
            return
        position = max(0, int(position))
        chars_removed = max(0, int(chars_removed))
        chars_added = max(0, int(chars_added))
        old_end = position + chars_removed

        spans = self.spans
        # Une modification à l'intérieur d'un <lb> existant exige un nouveau
        # balayage : son statut de repère peut avoir changé.
        overlap = False
        idx = bisect.bisect_right(spans, (position, 10**18)) - 1
        if idx >= 0:
            start, end = spans[idx]
            overlap = start < position < end
        if chars_removed and not overlap:
            idx = bisect.bisect_left(spans, (position, -1))
            overlap = idx < len(spans) and spans[idx][0] < old_end

        # La création d'une nouvelle balise commence nécessairement par '<'.
        # '>' est également structurel (fermeture d'une balise en cours) ;
        # retirer « <!-- » change aussi ce qui est commenté (red team 2, B3).
        structural_insert = "<" in inserted or ">" in inserted
        structural_removal = (chars_removed > 0 and removed_text is None) or \
            "<" in (removed_text or "") or ">" in (removed_text or "")
        # Former ou défaire « --> », « ]]> » ou « ?> » (« - » retiré, lettre
        # insérée au milieu…) change ce qui est commenté.
        around_before = preceding[-2:] + (removed_text or "") + following[:2]
        around_after = preceding[-2:] + inserted + following[:2]
        closer = any(end in around_before or end in around_after for end in _CLOSERS)

        if overlap or structural_insert or structural_removal or closer:
            self.dirty = True
            return

        # Cas ultra-fréquent : saisie/suppression dans le texte courant. Les
        # <lb> eux-mêmes ne changent pas ; seuls ceux situés après l'édition se
        # décalent. Cela évite un finditer sur tout le document à chaque frappe.
        delta = chars_added - chars_removed
        if not delta or not spans:
            return
        cut = bisect.bisect_left(spans, (old_end, -1))
        if cut < len(spans):
            self.spans = spans[:cut] + [
                (start + delta, end + delta) for start, end in spans[cut:]
            ]


class DocumentSession:
    """Tout ce qui appartient à un document XML ouvert.

    Les attributs sont regroupés par domaine ; leur sémantique est celle des
    anciens attributs de ``MainWindow`` indiqués en commentaire.
    """

    def __init__(self, text_document: Any = None, *, role: str = "edition", label: str = "",
                 schema_mode: str = "auto", schema_file: Optional[Path] = None) -> None:
        # Texte et historique annuler/refaire (QTextDocument).
        self.text_document = text_document
        # Coloration syntaxique attachée à text_document (XMLHighlighter).
        self.highlighter = None
        # Position du curseur et défilement, mémorisés quand un autre document
        # est affiché.
        self.view_state = None

        # « edition » : l'édition TEI du projet, liée aux témoins et à l'aperçu ;
        # « part » : partie de l'édition, incluse par un xi:include (V0.9.0.0) ;
        # « auxiliary » : document XML auxiliaire déclaré dans <documents>.
        self.role = role
        self.label = label

        # Politique de schéma RELAX NG du document (valeurs de
        # ProjectConfig.schema_mode ; schema_file n'est utilisé qu'en mode file).
        self.schema_mode = schema_mode
        self.schema_file = schema_file

        # Fichier et état d'enregistrement.
        self.path: Optional[Path] = None                 # current_path
        self.modified = False                            # modified
        # Date et taille du fichier lu ou enregistré (red team, A3) : voir
        # file_stamp.
        self.disk_stamp: Optional[tuple[int, int]] = None

        # Suivi des révisions du QTextDocument.
        self.last_processed_edit_revision = -1           # _last_processed_edit_revision
        self.loading = False                             # _loading_editor_document

        # Repères <lb/> du témoin pivot.
        self.lb = LbIndex()                              # _lb_spans, _lb_cache_dirty

        # Bonne formation XML (contrôle automatique après la frappe).
        self.health = "normal"                           # _document_health
        self.last_xml_health_revision = -1               # _last_xml_health_revision
        self.last_xml_health_well_formed: Optional[bool] = None  # _last_xml_health_well_formed

        # Validation RELAX NG.
        self.last_rng_result = None                      # _last_rng_result
        self.last_rng_revision = -1                      # _last_rng_revision
        self.last_rng_schema_token = None                # _last_rng_schema_token
        self.last_schema_resolution = None               # _last_schema_resolution

        # Schéma et modèle de complétion.
        self.completion_model = None                     # _completion_model
        self.completion_model_key = None                 # _completion_model_key
        self.completion_resolution = None                # _completion_resolution
        self.completion_resolution_key = None            # _completion_resolution_key
        self.completion_context_cache = XmlContextCache()  # _source_completion_context_cache

        # Dernière position synchronisée avec les témoins.
        self.last_synced_ordinal: Optional[int] = None   # _last_synced_ordinal
        self.last_synced_surface = None                  # _last_synced_surface
        self.last_synced_lacunae = frozenset()           # _last_synced_lacunae (V0.9.1.3)

    @classmethod
    def auxiliary(cls, config, text_document: Any = None) -> "DocumentSession":
        """Session d'un document auxiliaire (``project_config.DocumentConfig``)."""
        session = cls(text_document, role="auxiliary", label=config.display_label,
                      schema_mode=config.schema_mode, schema_file=config.schema)
        session.path = Path(config.path)
        return session

    @classmethod
    def part(cls, path, schema_mode: str = "auto", schema_file: Optional[Path] = None) -> "DocumentSession":
        """Session d'une partie de l'édition (fichier inclus par XInclude) ;
        son onglet porte le nom du fichier. Le schéma est celui de l'édition."""
        session = cls(role="part", label=Path(path).name, schema_mode=schema_mode, schema_file=schema_file)
        session.path = Path(path)
        return session

    @property
    def is_edition(self) -> bool:
        return self.role == "edition"

    @property
    def is_part(self) -> bool:
        return self.role == "part"

    @property
    def is_auxiliary(self) -> bool:
        return self.role == "auxiliary"

    @property
    def in_edition(self) -> bool:
        """L'édition ou l'une de ses parties : le document assemblé."""
        return self.role in ("edition", "part")

    # --- Transitions d'état -------------------------------------------------

    def invalidate_rng(self) -> None:
        """Le texte a changé : le dernier résultat RELAX NG n'est plus valable."""
        self.last_rng_result = None
        self.last_rng_revision = -1
        self.last_rng_schema_token = None

    def reset_validation(self) -> None:
        """Nouveau document : oublier aussi le schéma résolu précédemment."""
        self.invalidate_rng()
        self.last_schema_resolution = None

    def mark_loaded(self, path: Path, revision: int) -> None:
        """Un fichier vient d'être chargé dans ``text_document``."""
        self.path = Path(path)
        self.modified = False
        self.disk_stamp = file_stamp(path)
        self.last_processed_edit_revision = int(revision)
        self.lb.invalidate()
        self.completion_context_cache.clear()
        self.last_synced_ordinal = None
        self.last_synced_surface = None
        self.last_synced_lacunae = frozenset()

    def mark_saved(self, path: Path) -> None:
        """Le contenu courant vient d'être écrit dans ``path``."""
        self.path = Path(path)
        self.modified = False
        self.disk_stamp = file_stamp(path)
