# -*- coding: utf-8 -*-
"""Repères de ligne du pivot dans le texte de l'éditeur (V0.9.4.7).

Mixin de ``MainWindow`` (editeur_tei.py) : index des ``<lb/>`` du témoin
pivot (``document_session.LbIndex``), tenu à jour à chaque modification,
rang du repère à une position ou au curseur, et état de structure de la
barre d'état (nombre de lignes comparé à celui de la synchronisation)."""
from __future__ import annotations

from app_context import tr as _t
from document_session import LB_EDIT_LOOKBACK, LbIndex


class PivotLineIndexMixin:
    """Repères de ligne du pivot et état de structure (voir le module)."""

    def _source_contents_changed(self, position, chars_removed, chars_added, text):
        """Invalide seulement ce que l'édition rend réellement obsolète.
        Rappel de l'éditeur (``text_change_listener``) : indices Python de
        ``text``, le texte après la modification."""
        self._source_completion_context_cache.invalidate_from(position)
        lb = self.document.lb
        if lb.dirty:
            return
        start = max(0, int(position))
        inserted = text[start:start + max(0, int(chars_added))]
        # Texte qui précède la modification : permet de savoir si elle a lieu
        # à l'intérieur d'une balise.
        end = start + max(0, int(chars_added))
        lb.apply_edit(position, chars_removed, chars_added, inserted, text[max(0, start - LB_EDIT_LOOKBACK):start],
                      removed_text=getattr(self.editor, "last_removed_text", None), following=text[end:end + 2])

    def _set_lb_spans(self, spans):
        self.document.lb.set(spans)
        if not self.document.in_edition:
            return  # l'état de structure est celui de l'édition
        # Édition en parties : lignes comptées dans l'édition assemblée, ou
        # dans le texte synchronisé à part qui est affiché.
        n = self._base_line_count()
        sync = self._text_sync_of(self._active_segment) if self._active_segment is not None else None
        if sync is not None:
            tip = _t("status.structure.text.tip", base=self.witness_siglum(self.base_id), name=sync.name)
        else:
            tip = _t("status.structure.assembled.tip") if self._edition_has_parts() else ""
        self.structure_status.setToolTip(tip)
        if not self.base_id:
            # Projet sans témoin : pas de lignes du pivot à compter.
            self.structure_status.setText(_t("status.structure.no_witness"))
            self.structure_status.setStyleSheet("color:#746b61")
        elif self.expected_base_lines is None:
            self.structure_status.setText(_t("status.structure.free", base=self.witness_siglum(self.base_id), count=n))
            self.structure_status.setStyleSheet("color:#746b61")
        elif n == self.expected_base_lines:
            self.structure_status.setText(_t("status.structure.ok", base=self.witness_siglum(self.base_id), count=n)); self.structure_status.setStyleSheet("color:#376b3c")
        else:
            self.structure_status.setText(_t("status.structure.changed", base=self.witness_siglum(self.base_id), count=n, expected=self.expected_base_lines)); self.structure_status.setStyleSheet("color:#a14b2f;font-weight:600")

    def _rebuild_lb_cache(self, text=None):
        if text is None:
            text = self.editor.toPlainText()
        self._set_lb_spans(LbIndex.scan(text, self.lb_base_re))

    def lb_spans(self):
        """Positions ``(début, fin)`` des ``<lb/>`` du témoin pivot dans le texte de
        l'éditeur. L'index est d'abord rebalayé s'il est périmé (``dirty``) ; dans
        l'édition, l'état de structure de la barre d'état est alors mis à jour."""
        if self.document.lb.dirty:
            self._rebuild_lb_cache()
        return self.document.lb.spans

    def ordinal_at_position(self, position):
        """Rang (à partir de 0) du dernier ``<lb/>`` du pivot qui commence avant ou
        à ``position`` (indice Python dans le texte de l'éditeur) ; 0 avant le
        premier, None si le texte n'en a aucun. Compté dans le seul document
        affiché ; pour une édition en parties, voir ``_base_ordinal_at``."""
        self.lb_spans()
        return self.document.lb.ordinal_at(position)

    def ordinal_at_cursor(self):
        """``ordinal_at_position`` au curseur de l'éditeur (position Qt convertie en
        indice Python)."""
        return self.ordinal_at_position(self.editor.positions().python(self.editor.textCursor().position()))
