# -*- coding: utf-8 -*-
"""Vérification d'une feuille XSLT affichée (V0.9.2.1), « comme le RNG ».

Pour une feuille XSLT (``xslt_scenarios.stylesheet_info``, ou l'extension
``.xsl``/``.xslt`` si sa racine est illisible), les déclencheurs de la
validation RELAX NG lancent sa compilation à la place : premier affichage,
F8 (« Vérifier la feuille XSLT »), frappe une fois F8 utilisé, et
enregistrement. La compilation se fait dans le processus de transformation
(``op: "check"``, ``xslt_engines.check``), avec les moteurs que donne
``xslt_scenarios.check_engines`` (ceux des scénarios qui emploient la
feuille, sinon d'après sa version).

Le résultat prend la forme d'un ``ValidationResult`` : il est rangé comme
celui d'une validation RELAX NG sur le document (``last_rng_result``,
``last_rng_revision``), et le panneau de validation, la barre d'état et la
couleur de l'onglet le montrent de la même façon. F8 et l'enregistrement
attendent la réponse (la fenêtre se redessine, sans traiter clics ni
frappes) ; la vérification automatique ne l'attend pas.
"""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QEventLoop, QTimer, Qt
from PySide6.QtWidgets import QApplication

from app_context import tr as _t
from document_dialogs import is_stylesheet_file
from relaxng_validation import ValidationIssue, ValidationResult
from transform_runner import TransformRunner
from validation_worker import _InputBlocker
from xslt_scenarios import StylesheetInfo, check_engines, check_request, stylesheet_info

# Au-delà, F8 et l'enregistrement n'attendent plus la vérification.
CHECK_TIMEOUT_MSEC = 60_000
_ENGINE_NAMES = {"lxml": "lxml", "saxon": "Saxon"}
# Le compte rendu d'un moteur qui n'a pas pu vérifier la feuille.
_FAILURES = {"saxon_missing", "unknown_engine", "worker_failed", "cancelled", "internal", "xslt_missing"}


class StylesheetCheckMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    _stylesheet_check = None            # (runner, clé) de la vérification automatique en cours

    # --- La feuille affichée ---------------------------------------------------

    def _displayed_stylesheet(self):
        """``StylesheetInfo`` du document affiché si c'est une feuille XSLT,
        sinon None. L'édition et ses parties n'en sont jamais."""
        document = self.document
        if document.in_edition or document.path is None:
            return None
        info = stylesheet_info(self.editor.toPlainText())
        if info is None and is_stylesheet_file(document.path):
            return StylesheetInfo("xsl", "", "")
        return info

    def _update_check_labels(self):
        """F8 et le titre du panneau : vérification XSLT ou validation RNG."""
        stylesheet = getattr(self, "document", None) is not None and self._displayed_stylesheet() is not None
        self.action_validate_rng.setText(_t("xslt_check.action" if stylesheet else "toolbar.validate_rng"))
        self.action_validate_rng.setToolTip(_t("xslt_check.action.tip" if stylesheet
                                               else "toolbar.validate_rng.tip"))
        self.validation_title.setText(_t("xslt_check.panel.title" if stylesheet else "rng.panel.title"))

    # --- Vérification ------------------------------------------------------------

    def _check_stylesheet(self, text, revision, *, show_panel, show_success_message, automatic, background):
        """Vérifie la feuille affichée (texte ``text`` de la révision
        ``revision``) à la place de la validation RELAX NG. Rend le résultat,
        ou None sans attendre (``background``)."""
        session = self.document
        path = Path(session.path)
        engines = check_engines(path, self.project, text)
        token = ("xslt",) + engines
        options = dict(engines=engines, revision=revision, show_panel=show_panel,
                       show_success_message=show_success_message, automatic=automatic)
        # Enregistrement, retour à la feuille : le résultat de cette révision
        # est réutilisé ; F8 vérifie toujours à nouveau.
        if (not show_success_message and self._last_rng_revision == revision
                and self._last_rng_result is not None and self._last_rng_schema_token == token):
            return self._last_rng_result
        requests = [check_request(engine, path, text) for engine in engines]
        self.rng_status.setText(_t("xslt_check.status.running"))
        self.rng_status.setStyleSheet("color:#777")
        if background:
            self._check_in_background(session, requests, options)
            return None
        return self._apply_check_results([self._check_now(request) for request in requests], **options)

    def _check_now(self, request):
        """Une vérification attendue : la fenêtre se redessine, sans traiter
        clics ni frappes ; au-delà de ``CHECK_TIMEOUT_MSEC``, elle est arrêtée."""
        runner = TransformRunner(parent=self)
        results = []
        loop = QEventLoop()

        def finished(result):
            results.append(result)
            loop.quit()

        runner.finished.connect(finished)
        timeout = QTimer()
        timeout.setSingleShot(True)
        timeout.timeout.connect(runner.cancel)
        blocker = _InputBlocker()
        app = QCoreApplication.instance()
        app.installEventFilter(blocker)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            runner.start(request)
            timeout.start(CHECK_TIMEOUT_MSEC)
            if not results:
                loop.exec()
        finally:
            QApplication.restoreOverrideCursor()
            app.removeEventFilter(blocker)
            timeout.stop()
            runner.deleteLater()
        return results[0]

    def _check_in_background(self, session, requests, options):
        """Vérification automatique : les moteurs l'un après l'autre, sans
        attendre ; une nouvelle demande remplace la précédente. Le résultat
        est montré s'il concerne encore le document et la révision affichés."""
        previous = self._stylesheet_check
        if previous is not None:
            runner, key = previous
            if key == (session, options["revision"], options["engines"]):
                return                                           # déjà demandée
            self._stylesheet_check = None
            runner.cancel()
        runner = TransformRunner(parent=self)
        key = (session, options["revision"], options["engines"])
        self._stylesheet_check = (runner, key)
        results = []

        def finished(result):
            if self._stylesheet_check is None or self._stylesheet_check[0] is not runner:
                runner.deleteLater()                             # remplacée entre-temps
                return
            results.append(result)
            if len(results) < len(requests):
                runner.start(requests[len(results)])
                return
            self._stylesheet_check = None
            runner.deleteLater()
            if self.document is session:
                self._apply_check_results(results, **options)
            elif session.view_state:
                session.view_state["status"] = None

        runner.finished.connect(finished)
        runner.start(requests[0])

    # --- Résultat ------------------------------------------------------------------

    def _apply_check_results(self, results, *, engines, revision, show_panel, show_success_message, automatic):
        """Montre les comptes rendus des moteurs (``TransformResult``) pour la
        révision ``revision`` ; rien si le document a changé depuis."""
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        result = check_validation_result(results, self.document.path)
        self._last_rng_result = result
        self._last_rng_revision = revision
        self._last_rng_schema_token = ("xslt",) + tuple(engines)
        labels = " + ".join(_t(f"transform.engine.{engine}") for engine in engines)
        failures = [_t("xslt_check.panel.failed", engine=_t(f"transform.engine.{r.engine}"),
                       error=_t(f"transform.error.{r.error_code}", detail=r.error))
                    for r in results if r.error_code in _FAILURES]
        errors = [issue for issue in result.issues if issue.level != "WARNING"]
        self._populate_validation_issues(result.issues, jump_to_xml=True)
        if not result.well_formed:
            summary, status, style = (_t("xslt_check.panel.malformed"), _t("xslt_check.status.malformed"),
                                      "color:#a13d32;font-weight:600")
            self._set_document_health("malformed")
        elif errors:
            count = len(errors)
            summary = _t("xslt_check.panel.invalid", engines=labels, count=count)
            status, style = _t("xslt_check.status.invalid", engines=labels, count=count), "color:#a06a20;font-weight:600"
            self._set_document_health("rng_invalid")
        elif failures:
            summary, status, style = "", _t("xslt_check.status.failed"), "color:#a14b2f;font-weight:600"
            self._set_document_health("normal")
        else:
            warnings = len(result.issues)
            summary = (_t("xslt_check.panel.warnings", engines=labels, count=warnings) if warnings
                       else _t("xslt_check.panel.valid", engines=labels))
            status, style = _t("xslt_check.status.valid", engines=labels), "color:#376b3c"
            self._set_document_health("normal")
        self.validation_summary.setText(" ".join(part for part in [summary] + failures if part))
        self.rng_status.setText(status)
        self.rng_status.setStyleSheet(style)
        if show_panel or (errors and not automatic):
            self.show_validation_panel()
        if show_success_message and result.valid and not failures:
            self.statusBar().showMessage(_t("xslt_check.message.valid"), 3500)
        return result


def check_validation_result(results, path) -> ValidationResult:
    """Les comptes rendus de ``xslt_engines.check`` d'une feuille, réunis en
    un ``ValidationResult`` : une erreur ou un avertissement par ligne, le
    moteur en tête du message s'il y en a plusieurs."""
    several = len(results) > 1
    issues = []
    for result in results:
        for file, line, level, message in result.issues:
            text = f"[{_ENGINE_NAMES.get(result.engine, result.engine)}] {message}" if several else message
            issues.append(ValidationIssue(int(line), 0, level.upper(), text, "XSLT", result.engine, str(file or path)))
    return ValidationResult(
        available=True, schema_loaded=True,
        well_formed=not any(r.error_code == "xslt_malformed" for r in results),
        valid=not any(issue.level != "WARNING" for issue in issues),
        issues=tuple(issues),
        error=" ; ".join(r.error for r in results if r.error_code in _FAILURES and r.error),
    )

