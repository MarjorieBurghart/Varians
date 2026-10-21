# -*- coding: utf-8 -*-
"""Textes synchronisés à part (V0.9.1.1) : données des témoins par segment.

Dans une édition en parties, un texte qui a son dossier ``alignments/<texte>/``
est synchronisé à part (``text_alignments``) : il forme un *segment*, avec ses
propres JSON et son pivot (celui du projet, sauf ``<part name base>``). Le
reste de l'édition forme le segment de l'édition (clé None), avec les JSON
déclarés dans project.xml.

Un fichier appartient à un seul segment (``pivot_lines``) : le segment change
donc seulement avec le document affiché. Les panneaux des témoins reçoivent
alors les données du nouveau segment, sans être recréés : zoom, cadres,
disposition et fenêtres détachées restent en place. Un témoin sans JSON pour
le texte garde son panneau, vide, avec un message. L'état d'un texte est lu à
sa première visite, puis gardé.
"""
from __future__ import annotations

from dataclasses import replace

from app_context import tr as _t
from pivot_lines import pivot_lb_pattern
from project_config import has_line_synchronization
from text_alignments import text_project, text_syncs
from witness_resource_refresh import RuntimeState, assemble_resources
from xml_assembly import path_key

TEXT_ABSENT = "manuscript.text_absent"


class TextSegmentsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    # --- Textes synchronisés à part -----------------------------------------

    def _text_syncs(self):
        """``(textes synchronisés à part, problèmes)`` de l'édition, relus
        quand la liste des parties change (``_forget_text_syncs``)."""
        found = self.__dict__.get("_text_syncs_cache")
        if found is None:
            parts = [session.path for session in self.documents if session.is_part]
            found = self._text_syncs_cache = text_syncs(self.project, parts)
        return found

    def _forget_text_syncs(self):
        """La liste des parties ou des dossiers a pu changer : textes et états
        des textes seront relus ; l'état de l'édition est gardé."""
        self._text_syncs_cache = None
        self._pivot_lines_cache = None
        states = self.__dict__.get("_segment_states") or {}
        self._segment_states = {None: states[None]} if None in states else {}

    def _text_bases(self):
        """``{fichier: pivot}`` des textes synchronisés à part."""
        return {sync.path: sync.base for sync in self._text_syncs()[0]}

    def _text_witness_ids(self):
        """Témoins qui ont un JSON pour au moins un texte."""
        return {wid for sync in self._text_syncs()[0] for wid in sync.alignments}

    def _text_sync_of(self, segment):
        return next((sync for sync in self._text_syncs()[0] if path_key(sync.path) == segment), None)

    # --- Segment du document affiché ----------------------------------------

    def _document_segment(self, session=None):
        """Segment de ``session`` (le document affiché par défaut) : None pour
        l'édition, sinon la clé du texte synchronisé à part qui le contient."""
        session = session or self.document
        if not session.in_edition or not self._text_syncs()[0]:
            return None
        # La numérotation en cache suffit : un fichier ne change de segment
        # que si les parties ou les dossiers changent, ce qui la recalcule.
        lines = (self.__dict__.get("_pivot_lines_cache") or (None, None, None))[1] or self._pivot_lines()
        found = lines.file(session.path) if lines is not None else None
        return found.segment if found is not None else None

    def _update_segment(self):
        """Après un changement de document affiché : données du segment de
        ce document, s'il appartient à l'édition."""
        if self.document.in_edition:
            self._switch_segment(self._document_segment())

    def _switch_segment(self, segment):
        current = getattr(self, "_active_segment", None)
        if segment == current:
            return
        states = self.__dict__.setdefault("_segment_states", {})
        if current is None and None not in states:
            # L'état de l'édition est celui chargé au démarrage.
            states[None] = (self._witness_resource_snapshot(), self.project)
        state, project = self._segment_state(segment)
        self._active_segment = segment
        self._apply_runtime_state(state, project)
        self._last_synced_ordinal = None
        self._last_synced_surface = None
        self._folio_revision = None
        # État de structure du segment (lignes de son pivot, attendues).
        self._set_lb_spans(self.lb_spans())

    def _refreshed_segment_project(self):
        """« Actualiser les synchronisations » : relit les dossiers des textes
        (les états des autres textes seront relus à leur prochaine visite) et
        renvoie le projet du segment du document affiché."""
        self._forget_text_syncs()
        segment = self._document_segment() if self.document.in_edition else self._active_segment
        sync = self._text_sync_of(segment) if segment is not None else None
        self._refreshing_segment = None if sync is None else segment
        return self.project if sync is None else text_project(self.project, sync)

    def _store_segment_state(self, state, project):
        """Fin de l'actualisation : ``state`` devient l'état du segment."""
        segment = getattr(self, "_refreshing_segment", None)
        self._active_segment = segment
        self.__dict__.setdefault("_segment_states", {})[segment] = (state, project)

    def _diagnostic_scope(self):
        """Portée du diagnostic des témoins : l'édition, ou le texte affiché."""
        sync = self._text_sync_of(self._active_segment) if self._active_segment is not None else None
        if sync is None:
            return _t("diagnostics.scope.edition", base=self.base_id)
        return _t("diagnostics.scope.text", name=sync.name, base=sync.base)

    def _diagnostic_notes(self):
        """Textes synchronisés à part (pivot, témoins) et problèmes de leurs
        dossiers ; vide pour un projet qui n'en a pas."""
        syncs, problems = self._text_syncs()
        notes = []
        if syncs:
            items = [_t("diagnostics.text_item", name=sync.name, base=sync.base,
                        witnesses=", ".join(w.id for w in self.witness_configs if w.id in sync.alignments))
                     for sync in syncs]
            notes.append(_t("diagnostics.texts", texts="; ".join(items)))
        notes.extend(_t("text_sync.problem." + problem.code, name=problem.name, detail=problem.detail)
                     for problem in problems)
        return "\n".join(notes)

    def _segment_project(self):
        """Projet du segment affiché : le projet, ou celui réduit au texte."""
        return self._segment_state(getattr(self, "_active_segment", None))[1]

    def _segment_state(self, segment):
        """``(RuntimeState, projet)`` du segment ; celui d'un texte est lu à
        sa première visite. Un JSON illisible laisse le texte sans données,
        avec un message dans la barre d'état."""
        states = self.__dict__.setdefault("_segment_states", {})
        if segment not in states:
            if segment is None:
                states[None] = (self._witness_resource_snapshot(), self.project)
            else:
                sync = self._text_sync_of(segment)
                project = text_project(self.project, sync)
                try:
                    state = assemble_resources(project)
                except Exception as exc:
                    self.statusBar().showMessage(_t("text_sync.error", name=sync.name, error=exc), 8000)
                    project = text_project(self.project, replace(sync, alignments={}))
                    state = empty_runtime_state()
                states[segment] = (state, project)
        return states[segment]

    # --- Données des témoins ------------------------------------------------

    def _apply_runtime_state(self, state, project, images=None):
        """Applique ``state`` (``RuntimeState`` de ``project``) aux panneaux
        existants, avec le pivot de ``project`` : zoom, cadres et disposition
        sont conservés. Un témoin absent de ``project`` (sans JSON pour le
        texte) reçoit le message d'absence. ``images`` : disponibilité des
        images par témoin, à reprendre (actualisation de l'édition)."""
        base = project.base_witness
        if base != getattr(self, "base_id", None):
            self.base_id = base
            self.lb_base_re = pivot_lb_pattern(base)
            # L'index des <lb/> du document affiché suit le pivot.
            self.document.lb.invalidate()
        self.base_panel = self.panels[base]
        self._raw_alignment_caches = state.raw
        self.alignment_caches = state.caches
        self.witness_items = state.witness_items
        self.witness_display_items = state.display_items
        self.base_by_key = state.base_by_key
        self.base_maps = state.base_maps
        self.base_items = state.base_items
        self._base_sync_line_count = state.base_sync_count
        self.base_alignment_available = state.base_active
        self._secondary_sync_link_counts = state.secondary_links
        if images is not None:
            text_witnesses = self._text_witness_ids()
            self._witness_image_available = {
                w.id: bool(images.get(w.id)) or (
                    w.id in text_witnesses and getattr(w, "image_source_type", "auto") != "none")
                for w in self.witness_configs}
        self.has_any_images = any(self._witness_image_available.values())
        self.expected_base_lines = state.base_sync_count if state.base_active else None
        self.action_reload_images.setEnabled(self.has_any_images)
        self.action_choose_witnesses.setEnabled(self.has_any_images)
        valid_pivot_keys = set(state.base_by_key)
        base_label = self.witness_labels[base]
        witnesses = project.witness_by_id
        for w in self.witness_configs:
            panel = self.panels[w.id]
            panel.set_base(w.id == base, base_label)
            if w.id not in witnesses:
                panel.set_absent(TEXT_ABSENT)
                continue
            panel.absent_key = None
            old = panel.current_item()
            old_page_id = str((old or {}).get('p', {}).get('id', ''))
            old_line_id = str((old or {}).get('l', {}).get('alto_id') or (old or {}).get('l', {}).get('line'))
            new_items = state.display_items[w.id]
            panel.items = new_items
            panel.map_base = state.base_maps.get(w.id) or {}
            panel.sync_enabled = bool(state.base_active and (
                w.id == base or state.secondary_links.get(w.id, 0) > 0))
            # The same witness may switch from page-only to synchronized after
            # a Varians-Synchro JSON refresh; folio controls follow its mode.
            if hasattr(panel, 'folio_combo'):
                panel.folio_combo.setEnabled(not panel.sync_enabled)
            if hasattr(panel, 'split_folio_btn'):
                panel.split_folio_btn.setEnabled(bool(panel.items))
            panel._surface_indices = {
                str(it['p'].get('tei_surface_id')): i
                for i, it in enumerate(new_items) if it['p'].get('tei_surface_id')
            }
            chosen = next((i for i, it in enumerate(new_items)
                           if str(it['p'].get('id', '')) == old_page_id
                           and str(it['l'].get('alto_id') or it['l'].get('line')) == old_line_id), None)
            if chosen is None:
                chosen = next((i for i, it in enumerate(new_items)
                               if str(it['p'].get('id', '')) == old_page_id), None)
            panel.center_index = (chosen if chosen is not None else
                                  min(panel.center_index, max(0, len(new_items) - 1)))
            panel.origin_center_index = panel.center_index
            panel.match_indices = set()
            panel.primary_key = None
            panel.sync_issue.hide()
            panel.sync_issue.setText('')
            if w.id != base and has_line_synchronization(witnesses[w.id]) and state.base_active:
                keys = panel.map_base
                if not state.secondary_links.get(w.id, 0):
                    reason = _t('manuscript.sync.no_base_keys')
                elif not set(keys).intersection(valid_pivot_keys):
                    reason = _t('manuscript.sync.unmatched_base_keys')
                else:
                    reason = ''
                if reason:
                    panel.sync_issue.setText(reason)
                    panel.sync_issue.setToolTip(reason)
                    panel.sync_issue.show()
            unmatched = int((state.caches[w.id].get('meta') or {}).get('iiif_unassociated_layout_count') or 0)
            tip = (_t('manuscript.iiif_unassociated_layout.tip', count=unmatched)
                   if unmatched else '')
            panel.header.setToolTip(tip)
            panel.status.setToolTip(tip)
            panel.reload()


def empty_runtime_state():
    """État sans témoin (texte dont les JSON sont illisibles)."""
    return RuntimeState({}, {}, {}, {}, {}, {}, [], None, False, {}, {})
