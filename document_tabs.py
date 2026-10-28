# -*- coding: utf-8 -*-
"""Documents XML du projet dans la fenêtre principale : l'édition, ses
parties (V0.9.0.0 : fichiers inclus par ses xi:include) et les documents
auxiliaires déclarés dans <documents> (fichier d'autorités, notes…).

Un seul document est affiché à la fois dans l'éditeur. Chacun possède sa
session (``DocumentSession``) : texte et historique d'annulation, état
« modifié », coloration, validation, position du curseur. Les témoins et
leur synchronisation concernent l'édition et ses parties (V0.9.1.0 : lignes
du pivot comptées dans l'édition assemblée) ; l'aperçu, l'édition seule.

Les parties se déduisent des xi:include de l'édition enregistrée, sans
déclaration dans project.xml ; la liste est relue après chaque
enregistrement de l'édition ou d'une partie. Un fichier à la fois inclus et
déclaré dans <documents> est une partie : une seule session par fichier.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtGui import QActionGroup, QColor, QFont, QFontMetrics, QTextCursor, QTextDocument
from PySide6.QtWidgets import (QHBoxLayout, QMenu, QMessageBox, QPlainTextDocumentLayout, QStyle, QStyleOptionTab,
                               QStylePainter, QTabBar, QToolButton, QVBoxLayout, QWidget)
from app_context import call_later, current_i18n, tr as _t
from code_editor import XMLHighlighter
from document_session import DocumentSession
from pivot_lines import include_spans, pivot_lb_pattern, pivot_lines
from preview_sources import preview_sources
from project_management import update_project_documents
from lxml import etree
from xml_assembly import assemble, path_key


# Couleur du nom d'un document selon sa bonne formation (cf. _set_document_health).
_HEALTH_TAB_COLORS = {"malformed": "#a13d32", "rng_invalid": "#a06a20"}

# Onglet du document affiché (V0.9.1.6) : fond blanc, filet de couleur en haut,
# nom en gras ; les autres onglets en retrait, sur un fond plus sombre.
CURRENT_TAB_ACCENT = "#3272a6"
_DOCUMENT_TAB_QSS = f"""
QTabBar::tab {{ padding: 5px 14px; margin-right: 2px; border: 1px solid #bdb5aa; border-bottom: none;
               border-top-left-radius: 4px; border-top-right-radius: 4px; background: #dcd6cd; }}
QTabBar::tab:!selected {{ margin-top: 4px; }}
QTabBar::tab:hover:!selected {{ background: #ebe7e1; }}
QTabBar::tab:selected {{ background: #ffffff; border-color: #9c9184; border-top: 3px solid {CURRENT_TAB_ACCENT}; }}
"""
_CURRENT_TAB_TEXT = QColor("#111111")
_OTHER_TAB_TEXT = QColor("#4f4840")


class DocumentTabBar(QTabBar):
    """Rangée d'onglets des documents. La feuille de style dessine les
    onglets ; les noms sont écrits ici, en gras pour le document affiché, et
    dans la couleur de l'état XML de chaque document (``setTabTextColor``),
    qu'une feuille de style ferait oublier."""

    # Taille de la rangée ou place des onglets changée (flèche ▾, V0.9.2.8).
    layoutChanged = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(_DOCUMENT_TAB_QSS)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.layoutChanged.emit()

    def tabLayoutChange(self):
        super().tabLayoutChange()
        self.layoutChanged.emit()

    def _label_font(self, bold):
        font = QFont(self.font())
        font.setBold(bold)
        return font

    def label_font(self, index):
        """Police du nom de l'onglet ``index`` : en gras pour l'onglet courant."""
        return self._label_font(index == self.currentIndex())

    def label_colour(self, index):
        """Couleur du nom de l'onglet ``index`` : celle de l'état XML du
        document, sinon plus foncée pour l'onglet courant."""
        colour = self.tabTextColor(index)
        if colour.isValid():
            return colour
        return _CURRENT_TAB_TEXT if index == self.currentIndex() else _OTHER_TAB_TEXT

    def tabSizeHint(self, index):
        # Place du nom en gras pour chaque onglet : changer d'onglet ne
        # déplace pas les autres.
        size = super().tabSizeHint(index)
        text = self.tabText(index)
        extra = (QFontMetrics(self._label_font(True)).horizontalAdvance(text)
                 - QFontMetrics(self._label_font(False)).horizontalAdvance(text))
        return QSize(size.width() + max(0, extra), size.height())

    def paintEvent(self, event):
        painter = QStylePainter(self)
        current = self.currentIndex()
        # L'onglet courant en dernier, par-dessus ses voisins.
        order = [index for index in range(self.count()) if index != current]
        if current >= 0:
            order.append(current)
        for index in order:
            option = QStyleOptionTab()
            self.initStyleOption(option, index)
            painter.drawControl(QStyle.ControlElement.CE_TabBarTabShape, option)
            rect = self.style().subElementRect(QStyle.SubElement.SE_TabBarTabText, option, self)
            painter.setFont(self.label_font(index))
            painter.setPen(self.label_colour(index))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, option.text)


class DocumentTabsMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _init_documents(self):
        """Registre des documents, une fois le projet lu, avant le chargement
        du texte de l'édition : l'édition, ses parties dans l'ordre
        d'inclusion, puis les documents auxiliaires."""
        self.edition_session = self.document
        parts = self._edition_part_paths() or []
        included = {path_key(path) for path in parts}
        self.documents = [self.edition_session] + [self._new_part(path) for path in parts] + [
            DocumentSession.auxiliary(config) for config in self.project.documents
            if path_key(config.path) not in included
        ]
        self._load_document_tabs()

    def _new_part(self, path):
        """Session d'une partie ; son schéma est celui de l'édition."""
        return DocumentSession.part(path, self.project.schema_mode, self.project.schema)

    def _edition_part_paths(self):
        """Parties de l'édition enregistrée, dans l'ordre d'inclusion ; None
        si elle ne peut pas être lue ou si elle est mal formée."""
        path = self.edition_session.path or self.project.edition
        try:
            text = Path(path).read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            return None
        assembly = assemble(text, path)
        return None if assembly.root is None else list(assembly.parts)

    def _refresh_parts(self):
        """Après l'enregistrement de l'édition ou d'une partie : les parties
        suivent les xi:include enregistrés. Une partie qui n'est plus incluse
        perd son onglet, sauf si elle a des modifications non enregistrées
        (elle le garde jusqu'à leur enregistrement) ; déclarée dans
        <documents>, elle redevient un document auxiliaire."""
        paths = self._edition_part_paths()
        if paths is None:
            return
        wanted = {path_key(path): path for path in paths}
        declared = {path_key(config.path): config for config in self.project.documents}
        sessions = {path_key(session.path): session for session in self.documents[1:]}
        changed = False
        for key, session in sessions.items():
            if not session.is_part or key in wanted or session.modified:
                continue
            changed = True
            config = declared.get(key)
            if config is not None:
                session.role, session.label = "auxiliary", config.display_label
                session.schema_mode, session.schema_file = config.schema_mode, config.schema
                continue
            if session is self.document:
                self.show_document(self.edition_session)
            self.documents.remove(session)
            self._hidden_documents.discard(session)
            if session.text_document is not None:
                session.text_document.deleteLater()
        for key, path in wanted.items():
            session = sessions.get(key)
            if session is not None and session.is_part:
                continue
            changed = True
            if session is not None:                          # document auxiliaire désormais inclus
                session.role, session.label = "part", Path(path).name
                session.schema_mode, session.schema_file = self.project.schema_mode, self.project.schema
            else:
                self.documents.append(self._new_part(path))
        if not changed:
            return
        position = {key: index for index, key in enumerate(wanted)}
        others = self.documents[1:]
        self.documents = ([self.edition_session]
                          + sorted((s for s in others if s.is_part and path_key(s.path) in position),
                                   key=lambda s: position[path_key(s.path)])
                          + [s for s in others if s.is_part and path_key(s.path) not in position]
                          + [s for s in others if not s.is_part])
        self._update_document_tabs()
        self._save_document_tabs()
        # Les textes synchronisés à part et la numérotation des lignes du
        # pivot suivent les parties.
        self._forget_text_syncs()
        if self.document.in_edition:
            self._update_segment()
            self._rebuild_lb_cache()

    def _edition_displayed(self):
        return self.document.is_edition

    def _edition_has_parts(self):
        """L'édition inclut des parties (XInclude) : elle est validée
        assemblée."""
        return any(session.is_part for session in self.documents)

    def _assembled_preview_sources(self):
        """Sources de l'aperçu de l'édition assemblée (``preview_sources``),
        parties comprises (texte en mémoire des parties ouvertes), quel que
        soit le document affiché ; None pour une édition sans parties, ou mal
        formée."""
        if not self._edition_has_parts():
            return None
        edition = self.edition_session
        parts = {s.path: s.text_document.toPlainText() for s in self.documents
                 if s.is_part and s.text_document is not None}
        base = self.project.base_witness
        return preview_sources(edition.text_document.toPlainText(), edition.path or self.project.edition,
                               parts, base, pivot_lb_pattern(base))

    def _edition_file_session(self, path, load=False):
        """Document du fichier ``path`` de l'édition (l'édition ou l'une de ses
        parties), ou None. Avec ``load``, son texte est lu s'il ne l'a jamais
        été, sans qu'il soit affiché (None si le fichier est illisible)."""
        session = next((s for s in self.documents if s.in_edition and path_key(s.path) == path_key(path)), None)
        if session is not None and load and session.text_document is None:
            try:
                text = Path(session.path).read_text(encoding="utf-8")
            except (OSError, UnicodeError):
                return None
            self._load_session_text(session, text)
        return session

    def _show_file_position(self, path, position):
        """Place le curseur à ``position`` dans le fichier ``path`` de
        l'édition, affiché au besoin (l'aperçu reste à l'écran)."""
        session = self._edition_file_session(path)
        if session is None or not self.show_document(session):
            return False
        self.show_document_tab(session)
        text_length = self.editor.document().characterCount() - 1
        cursor = self.editor.textCursor()
        cursor.setPosition(max(0, min(int(position), text_length)))
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        return True

    def navigate_to_preview_line(self, index):
        """Repère de ligne ``index`` de l'aperçu d'une édition assemblée
        (V0.9.1.5) : le curseur va à ce ``<lb/>`` dans son fichier ; les
        témoins suivent, avec la numérotation du texte qui le contient."""
        sources = self.formatted_view.sources
        if sources is None or not 0 <= int(index) < len(sources.lines) or sources.lines[int(index)] is None:
            return False
        path, end = sources.lines[int(index)]
        self._sync_from_panel = True
        try:
            if not self._show_file_position(path, end):
                return False
            self.sync_panels_to_cursor(True)
        finally:
            call_later(90, self, self._release_panel_sync)
        return True

    # --- Lignes du pivot dans l'édition assemblée (V0.9.1.0) -------------------

    def _pivot_lines(self):
        """Lignes du pivot dans l'édition assemblée (``PivotLines``) ; None
        pour une édition sans parties, ou jamais assemblée (mal formée).

        Le résultat est gardé tant que les documents de l'édition ne changent
        pas, et pendant la saisie tant que le document affiché garde le même
        nombre de <lb/> du pivot et de xi:include : les positions viennent de
        son index, tenu à jour. Une partie (ou l'édition) devenue mal formée
        laisse la numérotation précédente."""
        if not self._edition_has_parts():
            return None
        sessions = [s for s in self.documents if s.in_edition]
        revisions = {s: (s.text_document.revision() if s.text_document is not None else None) for s in sessions}
        cache = self.__dict__.get("_pivot_lines_cache")
        if cache is not None:
            known, lines, malformed = cache
            if known == revisions:
                return lines
            changed = [s for s in sessions if known.get(s, -1) != revisions[s]]
            if (lines is not None and known.keys() == revisions.keys() and changed == [self.document]
                    and lines.matches(self.document.path, len(self.lb_spans()),
                                      len(include_spans(self.editor.toPlainText())))):
                self._pivot_lines_cache = (revisions, lines, malformed)
                return lines
        edition = self.edition_session
        texts = {s.path: s.text_document.toPlainText() for s in sessions
                 if not s.is_edition and s.text_document is not None}
        base = self.project.base_witness
        lines = pivot_lines(edition.text_document.toPlainText(), edition.path or self.project.edition,
                            texts, base, pivot_lb_pattern(base), text_bases=self._text_bases())
        malformed = (None if lines is None else
                     frozenset(path_key(p.file) for p in lines.problems if p.code == "malformed"))
        if cache is not None and cache[1] is not None and (lines is None or not malformed <= cache[2]):
            lines, malformed = cache[1], cache[2]
        self._pivot_lines_cache = (revisions, lines, malformed)
        return lines

    def _base_ordinal_at(self, position):
        """Rang de la ligne du pivot à ``position`` dans le document affiché,
        compté dans l'édition assemblée si elle a des parties ; None hors de
        l'édition ou sans <lb/> du pivot."""
        if not self._edition_has_parts():
            return self.ordinal_at_position(position)
        lines = self._pivot_lines()
        if lines is None:
            return None
        return lines.ordinal_at(self.document.path, position, self.lb_spans(),
                                include_spans(self.editor.toPlainText()))

    def _base_ordinal_at_cursor(self):
        return self._base_ordinal_at(self.editor.textCursor().position())

    def _base_line_count(self):
        """Nombre de <lb/> du pivot : dans l'édition assemblée si elle a des
        parties, sinon dans le document affiché."""
        if not self._edition_has_parts():
            return len(self.lb_spans())
        lines = self._pivot_lines()
        return lines.segment_count(self._active_segment) if lines is not None else 0

    def _show_base_ordinal(self, ordinal):
        """Place le curseur à la fin du <lb/> du pivot de rang ``ordinal``
        (borné), au centre de l'éditeur. Dans une édition en parties, le
        document qui le contient est affiché ; son onglet réapparaît s'il était
        masqué. Renvoie le rang atteint, ou None."""
        return self._show_segment_ordinal(getattr(self, "_active_segment", None), ordinal)

    def _show_segment_ordinal(self, segment, ordinal):
        """``_show_base_ordinal`` dans le segment ``segment`` : l'édition
        (None) ou un texte synchronisé à part, affiché au besoin
        (V0.9.1.4, un témoin suivi d'un texte à l'autre)."""
        lines = self._pivot_lines()
        switched = None
        if lines is None:
            if self._edition_has_parts():
                return None
            spans = self.lb_spans()
            if not spans:
                return None
            ordinal = max(0, min(len(spans) - 1, int(ordinal)))
            position = spans[ordinal][1]
        else:
            # Les lignes du segment : l'édition, ou le texte synchronisé à part.
            count = lines.segment_count(segment)
            if not count:
                return None
            ordinal = max(0, min(count - 1, int(ordinal)))
            location = lines.location(ordinal, segment)
            if location is None:
                return None
            path, index = location
            session = next((s for s in self.documents
                            if s.in_edition and path_key(s.path) == path_key(path)), None)
            if session is None:
                return None
            if session is not self.document:
                if not self.show_document(session):
                    return None
                switched = session
            self.show_document_tab(session)
            spans = self.lb_spans()
            if index >= len(spans):
                return None
            position = spans[index][1]
        cursor = self.editor.textCursor()
        cursor.setPosition(position)
        self.editor.setTextCursor(cursor)
        self.editor.centerCursor()
        if switched is not None:
            # Le défilement du document affiché est restauré juste après.
            call_later(0, self, lambda: self.document is switched and self.editor.centerCursor())
        return ordinal

    def _build_document_area(self, views):
        """Rangée d'onglets des documents au-dessus de ``views`` (source et
        aperçu), un par document visible (voir document_display). Elle reste
        masquée tant que le projet ne compte que l'édition."""
        bar = DocumentTabBar(self)
        bar.setDocumentMode(True)
        bar.setExpanding(False)
        bar.setUsesScrollButtons(True)
        self.document_tab_bar = bar
        # Onglets trop nombreux pour leur rangée (V0.9.2.8) : une flèche ▾ à
        # sa droite déroule le menu de tous les onglets.
        button = QToolButton(self)
        button.setArrowType(Qt.ArrowType.DownArrow)
        button.setAutoRaise(True)
        button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        button.setStyleSheet("QToolButton::menu-indicator { image: none; }")
        button.setToolTip(_t("documents.tabs.menu"))
        menu = QMenu(button)
        menu.aboutToShow.connect(self._fill_document_tabs_menu)
        button.setMenu(menu)
        button.setVisible(False)
        self.document_tabs_button = button
        row = QWidget(self)
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(0)
        row_layout.addWidget(bar, 1)
        row_layout.addWidget(button)
        self.document_tab_row = row
        self._normal_tab_color = bar.tabTextColor(0)
        for session in self._tab_sessions:
            bar.addTab("")
            self._refresh_document_tab(session)
        # L'onglet de l'édition n'est pas forcément le premier.
        self._select_document_tab()
        bar.setVisible(len(self.documents) > 1)
        self._update_document_tabs_button()
        bar.layoutChanged.connect(self._update_document_tabs_button)
        bar.currentChanged.connect(self._document_tab_changed)
        bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        bar.customContextMenuRequested.connect(self._document_tab_context_menu)
        area = QWidget(self)
        layout = QVBoxLayout(area)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(row)
        layout.addWidget(views, 1)
        return area

    def _update_document_tabs_button(self):
        """La rangée d'onglets suit la barre (masquée tant que le projet ne
        compte que l'édition) ; la flèche ▾ s'y affiche quand les onglets
        n'y tiennent pas."""
        bar = self.document_tab_bar
        shown = not bar.isHidden()
        self.document_tab_row.setVisible(shown)
        needed = sum(bar.tabSizeHint(index).width() for index in range(bar.count()))
        self.document_tabs_button.setVisible(shown and needed > self.document_tab_row.width())

    def _fill_document_tabs_menu(self):
        """Menu de la flèche ▾ : tous les onglets, celui du document affiché
        coché, puis « Choisir les documents affichés… »."""
        menu = self.document_tabs_button.menu()
        menu.clear()
        for group in menu.findChildren(QActionGroup):
            group.deleteLater()
        bar = self.document_tab_bar
        group = QActionGroup(menu)
        for index in range(bar.count()):
            action = menu.addAction(bar.tabText(index))
            action.setActionGroup(group)
            action.setCheckable(True)
            action.setChecked(index == bar.currentIndex())
            action.setToolTip(bar.tabToolTip(index))
            action.triggered.connect(lambda _checked=False, index=index: bar.setCurrentIndex(index))
        menu.addSeparator()
        menu.addAction(self.action_choose_documents)

    def _register_document(self, config):
        """Déclare ``config`` dans project.xml, l'ajoute aux onglets et l'affiche."""
        documents = list(self.project.documents) + [config]
        try:
            update_project_documents(self.project.path, documents)
        except Exception as exc:
            QMessageBox.critical(self, _t("documents.error.title"), str(exc))
            return False
        self.project = replace(self.project, documents=tuple(documents))
        session = DocumentSession.auxiliary(config)
        self.documents.append(session)
        self._update_document_tabs()
        self._save_document_tabs()
        return self.show_document(session)

    def _unregister_document(self, session):
        """Retire ``session`` de project.xml et des onglets ; le fichier reste."""
        documents = [config for config in self.project.documents
                     if Path(config.path).resolve() != Path(session.path).resolve()]
        try:
            update_project_documents(self.project.path, documents)
        except Exception as exc:
            QMessageBox.critical(self, _t("documents.error.title"), str(exc))
            return False
        self.project = replace(self.project, documents=tuple(documents))
        if session is self.document:
            self.show_document(self.edition_session)
        self.documents.remove(session)
        self._update_document_tabs()
        self._save_document_tabs()
        if session.text_document is not None:
            session.text_document.deleteLater()
        return True

    def _update_document_tabs(self):
        """Un onglet par document visible (après un ajout, un retrait, un
        onglet masqué ou rendu, un nouvel ordre)."""
        self._sync_document_tabs()
        bar = self.document_tab_bar
        bar.blockSignals(True)
        try:
            while bar.count() > len(self._tab_sessions):
                bar.removeTab(bar.count() - 1)
            while bar.count() < len(self._tab_sessions):
                bar.addTab("")
        finally:
            bar.blockSignals(False)
        for session in self._tab_sessions:
            self._refresh_document_tab(session)
        bar.setVisible(len(self.documents) > 1)
        self._update_document_tabs_button()
        self.action_choose_documents.setEnabled(len(self.documents) > 1)
        self._select_document_tab()

    def _document_tab_changed(self, index):
        if 0 <= index < len(self._tab_sessions) and not self.show_document(self._tab_sessions[index]):
            self._select_document_tab()

    def _select_document_tab(self):
        """Onglet courant = document affiché, sans redéclencher l'affichage.
        Un document masqué affiché le temps de l'enregistrer n'a pas d'onglet."""
        bar = getattr(self, "document_tab_bar", None)
        if bar is None or self.document not in self._tab_sessions:
            return
        bar.blockSignals(True)
        try:
            bar.setCurrentIndex(self._tab_sessions.index(self.document))
        finally:
            bar.blockSignals(False)

    def _refresh_document_tab(self, session):
        """Nom, « * » si modifié, couleur et info-bulle selon l'état XML
        (rien pour un document masqué)."""
        bar = getattr(self, "document_tab_bar", None)
        if bar is None or session not in self._tab_sessions:
            return
        index = self._tab_sessions.index(session)
        bar.setTabText(index, self._document_tab_name(session) + (" *" if session.modified else ""))
        color = _HEALTH_TAB_COLORS.get(session.health)
        bar.setTabTextColor(index, QColor(color) if color else self._normal_tab_color)
        tip = str(session.path)
        if session.health == "malformed":
            tip += "\n" + _t("xml.health.malformed.tooltip")
        elif session.health == "rng_invalid":
            tip += "\n" + _t("xml.health.rng_invalid.tooltip")
        bar.setTabToolTip(index, tip)

    def show_document(self, session):
        """Affiche ``session`` dans l'éditeur.

        Un document auxiliaire est lu à son premier affichage. Renvoie False
        si son fichier ne peut pas être lu ; le document affiché ne change
        alors pas.
        """
        if session is self.document:
            return True
        text = None
        if session.text_document is None:
            try:
                text = Path(session.path).read_text(encoding="utf-8")
            except Exception as exc:
                QMessageBox.critical(self, _t("file.open.error.title"), str(exc))
                return False
        # L'aperçu montre l'édition assemblée : passer d'une partie à l'autre
        # ne le quitte pas (V0.9.1.5) ; un document auxiliaire, si.
        if self.document.in_edition and not session.in_edition and not self._leave_edition_view():
            return False
        if text is not None:
            self._load_session_text(session, text)
        self._attach_document(session)
        return True

    def _leave_edition_view(self):
        """Avant d'afficher un autre document que l'édition : un fragment
        modifié dans l'aperçu est appliqué ou abandonné (ou la demande est
        annulée), puis l'onglet de la source est affiché."""
        view = self.formatted_view
        if not view.frag_box.isHidden() and not view.close_fragment_editor():
            return False
        self.left_tabs.setCurrentIndex(0)
        return True

    def _load_session_text(self, session, text):
        """Crée le QTextDocument d'une session et y place ``text``, avant tout
        affichage : aucun signal n'atteint encore la fenêtre."""
        document = QTextDocument(self)
        document.setDocumentLayout(QPlainTextDocumentLayout(document))
        # Coloration attachée AVANT le texte : attachée à un document déjà
        # rempli, sa passe différée incrémenterait la révision, que la fenêtre
        # prendrait pour une modification.
        session.highlighter = XMLHighlighter(document)
        document.setPlainText(text)
        document.setModified(False)
        session.text_document = document
        session.mark_loaded(session.path, document.revision())

    def _attach_document(self, session):
        """Remplace le document affiché par ``session``."""
        previous = self.document
        # Minuteries du document quitté ; l'aperçu lit toujours le texte affiché.
        for timer in (self.sync_timer, self.validate_timer, self.rng_refresh_timer,
                      self.formatted_view.preview_timer):
            timer.stop()
        self._remember_document_view(previous)
        old = previous.text_document
        for signal, slot in ((old.contentsChange, self._source_contents_changed),
                             (old.contentsChanged, self._text_changed),
                             (old.contentsChanged, self._assembly_changed)):
            try:
                signal.disconnect(slot)
            except (RuntimeError, TypeError):
                pass
        # La session doit être courante AVANT que l'éditeur n'affiche son texte :
        # les signaux émis pendant le changement (curseur, texte) la concernent.
        self.document = session
        self.editor.set_text_document(session.text_document)
        session.text_document.contentsChange.connect(self._source_contents_changed)
        session.text_document.contentsChanged.connect(self._text_changed)
        session.text_document.contentsChanged.connect(self._assembly_changed)
        # Les numéros de révision sont propres à chaque document.
        self._folio_revision = None
        self.xpath_table.setRowCount(0)
        self.xpath_summary.setText("")
        self._set_title()
        self._select_document_tab()
        # Données des témoins du segment de ce document (V0.9.1.1), avant
        # l'index de ses <lb/> : le pivot peut changer.
        self._update_segment()
        self._apply_edition_ui()
        self._restore_document_view(session)
        self.search_results_document_changed()

    def _remember_document_view(self, session):
        cursor = self.editor.textCursor()
        session.view_state = {
            "cursor": (cursor.anchor(), cursor.position()),
            "scroll": (self.editor.verticalScrollBar().value(),
                       self.editor.horizontalScrollBar().value()),
            "status": (self.xml_status.text(), self.xml_status.styleSheet(),
                       self.rng_status.text(), self.rng_status.styleSheet(),
                       self.schematron_status.text(), self.schematron_status.styleSheet(),
                       self.schematron_status.toolTip(), self.validation_summary.text()),
            # Les textes d'état ci-dessus sont dans la langue de l'interface.
            "language": current_i18n().language,
        }

    def _restore_document_view(self, session):
        """Curseur, défilement, état XML/RELAX NG du document affiché."""
        state = session.view_state or {}
        document = session.text_document
        last = max(0, document.characterCount() - 1)
        anchor, position = state.get("cursor", (0, 0))
        cursor = QTextCursor(document)
        cursor.setPosition(min(anchor, last))
        cursor.setPosition(min(position, last), QTextCursor.MoveMode.KeepAnchor)
        self.editor.setTextCursor(cursor)
        vertical, horizontal = state.get("scroll", (0, 0))

        def restore_scroll(shown=session):
            if self.document is shown:
                self.editor.verticalScrollBar().setValue(vertical)
                self.editor.horizontalScrollBar().setValue(horizontal)

        call_later(0, self, restore_scroll)
        self._set_document_health(session.health)
        status = state.get("status")
        if state.get("language") != current_i18n().language:
            status = None
        revision = document.revision()
        if status is None:
            # Premier affichage (ou langue changée entre-temps) : contrôle XML
            # immédiat, RELAX NG juste après.
            self._reset_validation_state()
            session.last_xml_health_revision = -1   # afficher le résultat
            self.validate_text(False)
            call_later(120, self, lambda shown=session: self.document is shown and
                       self.validate_relaxng_document(show_panel=False, automatic=True, background=True))
            return
        (xml_text, xml_style, rng_text, rng_style,
         schematron_text, schematron_style, schematron_tip, summary) = status
        self.xml_status.setText(xml_text)
        self.xml_status.setStyleSheet(xml_style)
        self.rng_status.setText(rng_text)
        self.rng_status.setStyleSheet(rng_style)
        self._set_schematron_label(schematron_text, schematron_style, schematron_tip)
        self.validation_summary.setText(summary)
        result = session.last_rng_result
        rows = (tuple(result.issues) + tuple(result.schematron_errors)) if result is not None else ()
        if session.last_rng_revision == revision and rows:
            self._populate_validation_issues(rows, jump_to_xml=result.schema_loaded)
        else:
            self._clear_validation_table()
        # Schéma ou règles changés depuis ce résultat (V0.9.2.4) : nouvelle
        # validation.
        if session.last_rng_revision == revision and self._validation_outdated(session):
            call_later(120, self, lambda shown=session: self.document is shown and
                       self.validate_relaxng_document(show_panel=False, automatic=True, background=True))
        # Contrôles interrompus par le changement de document.
        if session.last_xml_health_revision != revision:
            self.validate_timer.start()
        if (self._rng_watch_enabled and self._schema_mode != "none"
                and session.last_rng_revision != revision):
            self.rng_refresh_timer.start()

    # --- Enregistrement de plusieurs documents --------------------------------

    def _unsaved_sessions(self):
        """Documents dont des modifications ne sont pas enregistrées. Un
        fragment modifié dans l'aperçu compte pour le document dont il vient
        (V0.9.1.5 : une partie de l'édition, affichée ou non)."""
        fragment = self.formatted_view.dirty_fragment_session() if hasattr(self, "formatted_view") else None
        return [session for session in self.documents
                if (self.modified if session is self.document else session.modified) or session is fragment]

    def _document_display_name(self, session):
        return f"{self._document_tab_name(session)} ({Path(session.path).name})"

    def _save_session(self, session):
        """Enregistre ``session``. Un document non affiché l'est le temps de
        l'enregistrement : les avertissements (XML mal formé…) le montrent.
        En cas d'échec, il reste affiché, avec son onglet s'il était masqué."""
        if session is self.document:
            return bool(self.save())
        previous = self.document
        if not self.show_document(session) or not self.save():
            if self.document is session:
                self.show_document_tab(session)
            return False
        # L'enregistrement a pu retirer une partie qui n'est plus incluse.
        self.show_document(previous if previous in self.documents else self.edition_session)
        return True

    def _confirm_unsaved_documents(self, sessions, *, quitting=False):
        """Plusieurs documents (ou un document auxiliaire) à enregistrer :
        Tout enregistrer / Ignorer / Annuler. Renvoie True si l'on peut
        continuer."""
        box = QMessageBox(self)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setWindowTitle(_t("file.unsaved.title"))
        box.setText(_t("documents.unsaved.text") + "\n\n" + "\n".join(
            "• " + self._document_display_name(session) for session in sessions))
        save_btn = box.addButton(_t("documents.save_all"), QMessageBox.ButtonRole.AcceptRole)
        discard_btn = box.addButton(_t("file.discard_quit") if quitting else _t("common.discard"),
                                    QMessageBox.ButtonRole.DestructiveRole)
        cancel_btn = box.addButton(_t("common.cancel"), QMessageBox.ButtonRole.RejectRole)
        box.setDefaultButton(save_btn)
        box.setEscapeButton(cancel_btn)
        box.exec()
        clicked = box.clickedButton()
        if clicked is discard_btn:
            return True
        if clicked is not save_btn:
            return False
        view = self.formatted_view
        if view.dirty_fragment_session() is not None and not view.apply_fragment():
            return False
        return all(self._save_session(session) for session in sessions)

    # --- Interface réservée à l'édition ---------------------------------------

    def _edition_only_actions(self):
        return [self.action_save_as]

    def _witness_actions(self):
        return [self.action_reload_images, self.action_choose_witnesses,
                self.workspace_layout_menu.menuAction(), self.action_diagnose_witnesses,
                self.action_refresh_synchronizations]

    def _apply_edition_ui(self):
        """Aperçu et « Enregistrer l'édition sous… » : réservés à l'édition.
        Témoins (y compris détachés), état de structure et commandes des
        témoins : pour l'édition et ses parties (V0.9.1.0). Masqués quand un
        autre document est affiché, puis rétablis à l'identique."""
        edition = self._edition_displayed()
        hidden = getattr(self, "_edition_ui_hidden", None)
        if edition and hidden is not None:
            self._edition_ui_hidden = None
            for action, enabled in hidden:
                action.setEnabled(enabled)
        elif not edition and hidden is None:
            self._edition_ui_hidden = hidden = [(action, action.isEnabled())
                                                for action in self._edition_only_actions()]
            for action, _enabled in hidden:
                action.setEnabled(False)
        # L'aperçu (l'édition assemblée) : pour l'édition et ses parties
        # (V0.9.1.5).
        witnesses = self.document.in_edition
        preview = self.left_tabs.indexOf(self.formatted_view)
        hidden = getattr(self, "_preview_ui_hidden", None)
        if witnesses and hidden is not None:
            self._preview_ui_hidden = None
            self.action_preview.setEnabled(hidden)
            self.left_tabs.setTabEnabled(preview, True)
        elif not witnesses and hidden is None:
            self._preview_ui_hidden = self.action_preview.isEnabled()
            self.action_preview.setEnabled(False)
            self.left_tabs.setTabEnabled(preview, False)
        hidden = getattr(self, "_witness_ui_hidden", None)
        if witnesses and hidden is not None:
            self._witness_ui_hidden = None
            for action, enabled in hidden["actions"]:
                action.setEnabled(enabled)
            self.structure_status.setVisible(hidden["structure"])
            self.witness_scroll.setVisible(hidden["witnesses"])
            self.main_splitter.setSizes(hidden["sizes"])
            for window in hidden["detached"]:
                window.show()
        elif not witnesses and hidden is None:
            self._witness_ui_hidden = hidden = {
                "actions": [(action, action.isEnabled()) for action in self._witness_actions()],
                "structure": not self.structure_status.isHidden(),
                "witnesses": not self.witness_scroll.isHidden(),
                "sizes": self.main_splitter.sizes(),
                # Masquées, non fermées : fermer une fenêtre la rattacherait.
                "detached": [w for w in self._detached_windows.values() if w.isVisible()],
            }
            for action, _enabled in hidden["actions"]:
                action.setEnabled(False)
            self.structure_status.hide()
            self.witness_scroll.hide()
            for window in hidden["detached"]:
                window.hide()
        self.action_save.setText(_t("menu.save_edition" if edition else "menu.save_document"))
        # Retirer un document réécrit <documents> : une partie n'y figure pas.
        self.action_remove_document.setEnabled(self.document.is_auxiliary)
        # F8 : vérification d'une feuille XSLT, ou validation RELAX NG.
        self._update_check_labels()

    # --- Garde-fous : commandes réservées à l'édition -------------------------

    def _edition_write(self, method):
        """Commande d'un panneau de témoin qui écrit dans l'édition : acceptée
        pour l'édition et ses parties (V0.9.1.0 : le pb va dans la partie, le
        facsimile dans l'édition) ; refusée, avec un message, pour un document
        auxiliaire (elle s'appliquerait à un endroit que l'utilisateur ne voit
        pas)."""
        def guarded(*args):
            if not self.document.in_edition:
                QMessageBox.information(
                    self, _t("documents.edition_required.title"),
                    _t("documents.edition_required.text", name=self.edition_session.path.name))
                return None
            return method(*args)
        return guarded

    def _edition_navigation(self, method):
        """Navigation depuis un témoin : sans effet hors de l'édition et de
        ses parties."""
        def guarded(*args):
            if self.document.in_edition:
                return method(*args)
            return None
        return guarded
