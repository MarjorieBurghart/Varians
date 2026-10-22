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
le texte, mais qui a ce texte (un ``<pb edRef>`` dans le texte, ou un
``<locus target>`` dans son ``<witness>``), y suit ses pages (V0.9.1.3) ; les
autres gardent leur panneau, vide, avec un message. L'état d'un texte est lu
à sa première visite, puis gardé tant que ses témoins par pages ne changent
pas.
"""
from __future__ import annotations

import re
from dataclasses import replace

from app_context import tr as _t
from folio_navigation import folio_marks, text_start_folio, witness_loci
from pivot_lines import pivot_lb_pattern
from project_config import has_line_synchronization
from text_alignments import text_project, text_syncs
from witness_resource_refresh import RuntimeState, assemble_resources, flatten_primary, read_alignment_json
from witness_route import PageMark, Source, page_identity, witness_route
from xml_assembly import path_key

TEXT_ABSENT = "manuscript.text_absent"
_XML_ID_RE = re.compile(r"(?<![\w:.-])xml:id\s*=\s*(['\"])(.*?)\1", re.S)
_SURFACE_NUMBER_RE = re.compile(r"-p(\d+)$")


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

    # --- Témoins par pages d'un texte (V0.9.1.3) ------------------------------

    def _witness_loci(self):
        """``witness_loci`` du ``<listWit>`` de l'édition, gardé tant qu'elle
        ne change pas."""
        revision = self.edition_session.text_document.revision()
        cache = self.__dict__.get("_witness_loci_cache")
        if cache is None or cache[0] != revision:
            cache = self._witness_loci_cache = (revision, witness_loci(self._edition_text()))
        return cache[1]

    def _segment_files(self, segment):
        """Sessions des fichiers du segment ``segment`` : un texte
        synchronisé à part et les parties qu'il inclut."""
        lines = self._pivot_lines()
        if lines is None:
            return []
        return [session for session in self.documents if session.in_edition
                and lines.file(session.path) is not None and lines.file(session.path).segment == segment]

    @staticmethod
    def _session_text(session):
        """Texte d'une session ; celui de son fichier si elle n'a pas encore
        été affichée."""
        if session.text_document is not None:
            return session.text_document.toPlainText()
        try:
            return session.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return ""

    def _segment_ids(self, segment):
        """``xml:id`` des fichiers du segment ``segment``."""
        return {match.group(2) for session in self._segment_files(segment)
                for match in _XML_ID_RE.finditer(self._session_text(session))}

    def _text_loci(self, segment):
        """``{témoin: (Locus, …)}`` qui valent pour le texte ``segment`` : ceux
        du ``<listWit>`` de l'édition, et ceux de l'en-tête du texte (document
        TEI complet inclus par ``xpointer``)."""
        loci = {wid: tuple(found) for wid, found in self._witness_loci().items()}
        for session in self._segment_files(segment):
            if path_key(session.path) == segment:
                for wid, found in witness_loci(self._session_text(session)).items():
                    loci[wid] = loci.get(wid, ()) + found
        return loci

    def _text_start_folio(self, witness_id, folios):
        """Page de départ du témoin dans le texte affiché, synchronisé à part,
        avant son premier ``<pb>`` dans ce texte (``text_start_folio``)."""
        segment = self._active_segment
        lines = self._pivot_lines()
        first = lines.first_page(segment, witness_id, folios) if lines is not None else None
        return text_start_folio(witness_id, folios, self._text_loci(segment).get(witness_id, ()),
                                self._segment_ids(segment), first)

    def _text_page_witnesses(self, sync):
        """Témoins qui ont le texte ``sync`` sans y avoir de JSON : un ``<pb
        edRef>`` dans le texte, ou un ``<locus target>`` vers l'un de ses
        éléments. Ils y suivent leurs pages."""
        segment = path_key(sync.path)
        lines = self._pivot_lines()
        found = set(lines.page_witnesses(segment)) if lines is not None else set()
        ids = self._segment_ids(segment)
        for wid, loci in self._text_loci(segment).items():
            if any(locus.targets & ids for locus in loci):
                found.add(wid)
        declared = {w.id for w in self.witness_configs}
        return {wid for wid in found if wid in declared}

    # --- Parcours d'un témoin dans son propre ordre (V0.9.1.4) -----------------

    def _witness_route(self, wid):
        """``WitnessRoute`` du témoin dans tous les textes de l'édition, gardé
        tant que la numérotation, les textes à part et leurs états ne
        changent pas."""
        lines = self._pivot_lines() if self._edition_has_parts() else None
        syncs = tuple(self._text_syncs()[0]) if lines is not None else ()
        edition = self._segment_state(None)
        states = self.__dict__.get("_segment_states") or {}
        folios = tuple(self.panels[wid].folios)
        signature = (lines, syncs, tuple((key, id(value[0])) for key, value in states.items()),
                     id(edition[0]), folios)
        routes = self.__dict__.setdefault("_witness_routes", {})
        found = routes.get(wid)
        if found is None or found[0] != signature:
            found = routes[wid] = (signature, witness_route(
                wid, self._route_sources(wid, lines, syncs, states, edition, folios),
                self._declared_page_ranks(wid, states, edition, folios)))
        return found[1]

    def _route_sources(self, wid, lines, syncs, states, edition, folios):
        """``Source`` du témoin pour l'édition, puis pour chaque texte à part,
        dans l'ordre de l'édition : ses lignes (état du segment s'il a été
        lu, sinon ses JSON), ou ses ``<pb>`` dans ce texte."""
        sources = [self._state_source(None, wid, *edition, lines, folios)]
        for sync in syncs:
            segment = path_key(sync.path)
            if segment in states:
                source = self._state_source(segment, wid, *states[segment], lines, folios)
            else:
                source = self._json_source(segment, wid, sync, lines, folios)
            if source.cache is not None or source.marks:
                ids = self._segment_ids(segment)
                locus = next((locus.start for locus in self._text_loci(segment).get(wid, ())
                              if locus.start and locus.targets & ids), None)
                sources.append(replace(source, locus=locus))
        return sources

    def _state_source(self, segment, wid, state, project, lines, folios):
        anchor = lines.anchor(segment) if lines is not None else 0
        is_base = wid == project.base_witness
        if wid in project.witness_by_id and state.base_active and (
                is_base or state.secondary_links.get(wid, 0) > 0):
            return Source(segment, state.caches.get(wid), is_base, state.base_by_key, anchor)
        return Source(segment, marks=self._route_marks(wid, segment, lines, folios), anchor=anchor)

    def _json_source(self, segment, wid, sync, lines, folios):
        """Source d'un texte pas encore visité : ses JSON, lus sans images."""
        anchor = lines.anchor(segment)
        if wid in sync.alignments and sync.base in sync.alignments:
            try:
                cache = read_alignment_json(sync.alignments[wid])
                base_by_key = flatten_primary(read_alignment_json(sync.alignments[sync.base]))[1]
            except (OSError, ValueError):
                return Source(segment, anchor=anchor)
            return Source(segment, cache, wid == sync.base, base_by_key, anchor)
        return Source(segment, marks=self._route_marks(wid, segment, lines, folios), anchor=anchor)

    def _route_marks(self, wid, segment, lines, folios):
        """``<pb>`` du témoin dans le segment : ceux de l'édition assemblée,
        ou, dans une édition en un fichier, ceux de son texte."""
        if not folios:
            return ()
        if lines is None:
            path = self.edition_session.path or self.project.edition
            return tuple(PageMark(folio.ref, folio.label, (path, end), 0)
                         for folio, end in folio_marks(self._edition_text(), wid, list(folios)))
        return tuple(PageMark(mark.folio.ref, mark.folio.label, (mark.path, mark.position), mark.ordinal)
                     for mark in lines.pb_marks(wid, list(folios), segment))

    @staticmethod
    def _declared_page_ranks(wid, states, edition, folios):
        """Rang des pages du témoin tiré de ses images déclarées : le numéro
        de ``tei_surface_id``, sa place dans le manifeste ou les fichiers."""
        ranks, surfaces = {}, {}
        for state, _project in [edition, *states.values()]:
            for page in (state.caches.get(wid) or {}).get("pages", []) or []:
                sid = str(page.get("tei_surface_id") or "")
                match = _SURFACE_NUMBER_RE.search(sid)
                if match:
                    ranks[page_identity(page)] = surfaces[sid] = int(match.group(1))
        for folio in folios:
            if folio.surface in surfaces:
                ranks[f"folio:{folio.ref}"] = surfaces[folio.surface]
        return ranks

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
        return self.project if sync is None else text_project(self.project, sync, self._text_page_witnesses(sync))

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
            items = []
            for sync in syncs:
                witnesses = ", ".join(w.id for w in self.witness_configs if w.id in sync.alignments)
                pages = text_project(self.project, sync, self._text_page_witnesses(sync)).page_witnesses
                pages = ", ".join(w.id for w in self.witness_configs if w.id in pages)
                items.append(_t("diagnostics.text_item.pages", name=sync.name, base=sync.base,
                                witnesses=witnesses, pages=pages) if pages else
                             _t("diagnostics.text_item", name=sync.name, base=sync.base, witnesses=witnesses))
            notes.append(_t("diagnostics.texts", texts="; ".join(items)))
            # Ordre des textes dans chaque manuscrit (V0.9.1.4).
            for w in self.witness_configs:
                route = self._witness_route(w.id)
                runs = self._route_runs(route)
                if len(runs) > 1:
                    uncertain = ", ".join(self._segment_name(segment) for segment in route.uncertain)
                    notes.append(_t("diagnostics.route.uncertain", witness=w.id, runs=" → ".join(runs),
                                    texts=uncertain) if uncertain else
                                 _t("diagnostics.route", witness=w.id, runs=" → ".join(runs)))
        notes.extend(_t("text_sync.problem." + problem.code, name=problem.name, detail=problem.detail)
                     for problem in problems)
        return "\n".join(notes)

    def _segment_name(self, segment):
        sync = self._text_sync_of(segment)
        return sync.name if sync is not None else str(segment)

    def _route_runs(self, route):
        """Le parcours d'un témoin, texte par texte : le nom d'un texte à part,
        ou les lignes de l'édition parcourues d'un seul tenant."""
        runs = []
        for stop in route.stops:
            if runs and runs[-1][0] == stop.segment:
                runs[-1][1].append(stop.ordinal)
            else:
                runs.append((stop.segment, [stop.ordinal]))
        labels = []
        for segment, ordinals in runs:
            if segment is not None:
                labels.append(self._segment_name(segment))
                continue
            ordinals = [ordinal for ordinal in ordinals if ordinal is not None]
            if ordinals:
                labels.append(_t("diagnostics.route.edition", first=min(ordinals) + 1, last=max(ordinals) + 1))
        return labels

    def _segment_project(self):
        """Projet du segment affiché : le projet, ou celui réduit au texte."""
        return self._segment_state(getattr(self, "_active_segment", None))[1]

    def _segment_state(self, segment):
        """``(RuntimeState, projet)`` du segment ; celui d'un texte est lu à
        sa première visite. Un JSON illisible laisse le texte sans données,
        avec un message dans la barre d'état."""
        states = self.__dict__.setdefault("_segment_states", {})
        if segment is not None and segment in states:
            # Un <pb> ou un <locus> ajouté depuis la dernière visite (V0.9.1.3).
            sync = self._text_sync_of(segment)
            if states[segment][1].page_witnesses != text_project(
                    self.project, sync, self._text_page_witnesses(sync)).page_witnesses:
                del states[segment]
        if segment not in states:
            if segment is None:
                states[None] = (self._witness_resource_snapshot(), self.project)
            else:
                sync = self._text_sync_of(segment)
                project = text_project(self.project, sync, self._text_page_witnesses(sync))
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
            # Un témoin par pages sans aucune image (V0.9.1.3) n'a rien à montrer.
            if w.id not in witnesses or (w.id in getattr(project, "page_witnesses", ())
                                         and not state.display_items.get(w.id)):
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
