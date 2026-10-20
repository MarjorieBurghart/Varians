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
from pathlib import Path
from typing import Any, Iterable, Optional

from rng_completion import XmlContextCache

Span = tuple[int, int]

# Longueur du texte, avant une modification, examinée pour savoir si elle a
# lieu à l'intérieur d'une balise (voir LbIndex.apply_edit).
LB_EDIT_LOOKBACK = 4096


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
                   inserted: str = "", preceding: str = "") -> None:
        """Répercute une modification du texte sur l'index.

        ``inserted`` est le texte inséré à ``position`` ; ``preceding`` est le
        texte qui précède ``position`` après la modification (quelques milliers
        de caractères suffisent). Une modification qui touche un ``<lb/>``
        existant, qui insère ``<`` ou ``>`` ou qui a lieu à l'intérieur d'une
        balise invalide l'index (nouveau balayage au prochain accès) ; sinon
        les ``<lb/>`` situés après la modification sont simplement décalés.
        """
        if self.dirty:
            return
        # À l'intérieur d'une balise (dernier « < » après le dernier « > »),
        # même sans saisir « < » ni « > », une balise quelconque peut devenir
        # un <lb/> pivot, ou cesser de l'être (ex. edRef="#T" -> "#T1").
        if preceding.rfind("<") > preceding.rfind(">"):
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
        # '>' est également structurel (fermeture d'une balise en cours).
        structural_insert = "<" in inserted or ">" in inserted

        if overlap or structural_insert:
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

    @classmethod
    def auxiliary(cls, config, text_document: Any = None) -> "DocumentSession":
        """Session d'un document auxiliaire (``project_config.DocumentConfig``)."""
        session = cls(text_document, role="auxiliary", label=config.display_label,
                      schema_mode=config.schema_mode, schema_file=config.schema)
        session.path = Path(config.path)
        return session

    @property
    def is_edition(self) -> bool:
        return self.role == "edition"

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
        self.last_processed_edit_revision = int(revision)
        self.lb.invalidate()
        self.completion_context_cache.clear()
        self.last_synced_ordinal = None
        self.last_synced_surface = None

    def mark_saved(self, path: Path) -> None:
        """Le contenu courant vient d'être écrit dans ``path``."""
        self.path = Path(path)
        self.modified = False
