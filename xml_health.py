# -*- coding: utf-8 -*-
"""Contrôle de bonne formation du document affiché (V0.9.4.7).

Mixin de ``MainWindow`` (editeur_tei.py) et son travailleur : après une
pause de la frappe, le texte est analysé hors du fil de la fenêtre
(``XmlHealthWorker``, ``validate_editor``) ; avant un enregistrement ou F8,
aussitôt (``validate_text``), en réutilisant le résultat de la même
révision. L'état du document (bien formé, mal formé, invalide selon le
schéma) colore les onglets (``_set_document_health``) et s'affiche dans la
barre d'état."""
from __future__ import annotations

import xml.etree.ElementTree as ET

from PySide6.QtCore import QObject, QRunnable, Signal, Slot
from PySide6.QtWidgets import QMessageBox

from app_context import call_later, tr as _t


class XmlHealthSignals(QObject):
    """Signal de ``XmlHealthWorker`` : le résultat du contrôle de bonne
    formation revient au fil principal (``_async_xml_health_finished``)."""
    # revision QTextDocument, bien formé, ligne, colonne 0-based, message, spans lb
    finished = Signal(int, bool, int, int, str, object)


class XmlHealthWorker(QRunnable):
    """Contrôle XML automatique hors du thread graphique.

    La validation explicite (sauvegarde/F8) reste synchrone ; seul le contrôle
    de bonne formation déclenché après la frappe est déplacé ici.
    """

    def __init__(self, revision, text, lb_pattern):
        super().__init__()
        self.revision = int(revision)
        self.text = text
        self.lb_pattern = lb_pattern
        self.signals = XmlHealthSignals()

    @Slot()
    def run(self):
        well_formed = True
        line = 0
        column = 0
        message = ""
        spans = None
        try:
            ET.fromstring(self.text)
            # Profiter du même instantané de texte pour reconstruire les repères
            # de lignes sans provoquer une seconde copie de QPlainTextEdit.
            spans = [(m.start(), m.end()) for m in self.lb_pattern.finditer(self.text)]
        except ET.ParseError as exc:
            well_formed = False
            line, column = getattr(exc, "position", (0, 0)) or (0, 0)
            message = str(exc)
        self.signals.finished.emit(
            self.revision, well_formed, int(line or 0), int(column or 0),
            message, spans,
        )


class XmlHealthMixin:
    """Contrôle de bonne formation du document affiché (voir le module)."""

    def _set_document_health(self, state):
        """Signale visuellement la santé XML dans les deux onglets.

        malformed = rouge pâle ; rng_invalid = orange pâle ; normal = thème Qt.
        Le rouge est prioritaire : un XML mal formé n'est pas validable en RNG.
        """
        state = state if state in {"normal", "malformed", "rng_invalid"} else "normal"
        self._document_health = state
        tabbar = self.left_tabs.tabBar()
        if state == "malformed":
            tabbar.setStyleSheet(
                "QTabBar::tab { background:#f6d2d2; } "
                "QTabBar::tab:selected { background:#efbcbc; }"
            )
            tip = _t("xml.health.malformed.tooltip")
        elif state == "rng_invalid":
            tabbar.setStyleSheet(
                "QTabBar::tab { background:#f8e3bd; } "
                "QTabBar::tab:selected { background:#f2d59f; }"
            )
            tip = _t("xml.health.rng_invalid.tooltip")
        else:
            tabbar.setStyleSheet("")
            tip = ""
        for i in range(self.left_tabs.count()):
            self.left_tabs.setTabToolTip(i, tip)
        self._refresh_document_tab(self.document)

    def _xml_health_text(self, well_formed, line=0, column=0, error=""):
        if well_formed:
            return _t("xml.valid")
        where = _t("xml.invalid.where", line=line, column=column + 1) if line else ""
        return _t("xml.invalid", where=where, error=error)

    def _retranslate_xml_health(self):
        """Contrôle XML refait dans la nouvelle langue, comme au premier
        affichage d'un onglet (red team 2, D6)."""
        if getattr(self, "document", None) is None:
            return
        self._last_xml_health_revision = -1
        self.validate_text(False)

    def _apply_xml_health_result(self, well_formed, line=0, column=0, error="", spans=None, show_message=False):
        if not well_formed:
            msg = self._xml_health_text(False, line, column, error)
            self.xml_status.setText(msg); self.xml_status.setStyleSheet("color:#a13d32")
            self._set_document_health("malformed")
            if show_message:
                QMessageBox.warning(self, _t("xml.invalid.title"), msg)
            return False
        self.xml_status.setText(self._xml_health_text(True)); self.xml_status.setStyleSheet("color:#376b3c")
        if spans is not None:
            self._set_lb_spans(spans)
        current_revision = self.editor.document().revision()
        if (
            self._last_rng_revision == current_revision
            and self._last_rng_result is not None
            and self._last_rng_result.well_formed
            and self._rng_invalid_for(self.document, self._last_rng_result)
        ):
            self._set_document_health("rng_invalid")
        else:
            self._set_document_health("normal")
        return True

    def validate_text(self, show_message=False, *, text=None, revision=None):
        """Contrôle synchrone pour les opérations exigeant une réponse immédiate.

        V0.5.6 accepte un instantané déjà extrait de l'éditeur afin que Ctrl+S ne
        recopie pas plusieurs fois un gros document. Si le contrôle automatique a
        déjà validé exactement la révision courante, la sauvegarde peut réutiliser
        directement ce résultat sans reparsing XML.
        """
        revision = self.editor.document().revision() if revision is None else int(revision)
        if revision == self._last_xml_health_revision and self._last_xml_health_well_formed is not None:
            return bool(self._last_xml_health_well_formed)
        text = self.editor.toPlainText() if text is None else text
        try:
            ET.fromstring(text)
        except ET.ParseError as exc:
            line, col = getattr(exc, "position", (0, 0)) or (0, 0)
            self._last_xml_health_revision = revision
            self._last_xml_health_well_formed = False
            return self._apply_xml_health_result(False, line, col, str(exc), None, show_message)
        spans = [(m.start(), m.end()) for m in self.lb_base_re.finditer(text)]
        self._last_xml_health_revision = revision
        self._last_xml_health_well_formed = True
        return self._apply_xml_health_result(True, spans=spans, show_message=show_message)

    def validate_editor(self):
        """Contrôle automatique asynchrone après une pause de saisie."""
        revision = self.editor.document().revision()
        if revision == self._last_xml_health_revision:
            return
        if self._xml_health_running:
            self._xml_health_pending = True
            return
        text = self.editor.toPlainText()
        self._xml_health_running = True
        self._xml_health_pending = False
        self._xml_health_session = self.document
        worker = XmlHealthWorker(revision, text, self.lb_base_re)
        self._xml_health_worker = worker
        worker.signals.finished.connect(self._async_xml_health_finished)
        self._xml_health_pool.start(worker)

    @Slot(int, bool, int, int, str, object)
    def _async_xml_health_finished(self, revision, well_formed, line, column, error, spans):
        self._xml_health_running = False
        self._xml_health_worker = None
        # Le résultat ne vaut que pour le document contrôlé : un autre a pu
        # être affiché entre-temps (les révisions sont propres à chaque document).
        checked = self._xml_health_session
        self._xml_health_session = None
        same_document = checked is None or checked is self.document
        current_revision = self.editor.document().revision()
        if same_document and revision == current_revision:
            self._last_xml_health_revision = revision
            self._last_xml_health_well_formed = bool(well_formed)
            self._apply_xml_health_result(well_formed, line, column, error, spans, False)
        # Si le document a changé pendant un contrôle exceptionnellement long
        # et que le timer a déjà expiré, programmer une nouvelle passe courte.
        if (self._xml_health_pending or not same_document or revision != current_revision) and not self.validate_timer.isActive():
            self._xml_health_pending = False
            call_later(180, self, self.validate_editor)
