# -*- coding: utf-8 -*-
"""Vérification d'un fichier Schematron affiché (V0.9.2.4), « comme le RNG ».

Pour un fichier Schematron (``xml_roots.schematron_info``, ou l'extension
``.sch`` si sa racine est illisible), les déclencheurs de la validation
RELAX NG lancent sa vérification à la place : premier affichage, F8
(« Vérifier les règles Schematron »), frappe une fois F8 utilisé, et
enregistrement. Elle se fait dans le processus de validation
(``op: "check_schematron"``, voir ``schematron_check``) : bonne formation,
structure d'après le schéma ISO livré, inclusions, compilation par Saxon.

Le résultat est un ``ValidationResult`` rangé comme celui d'une validation
RELAX NG sur le document (``last_rng_result``, ``last_rng_revision``,
jeton ``("schematron",)``) : le panneau de validation, la barre d'état et la
couleur de l'onglet le montrent de la même façon. F8 et l'enregistrement
attendent la réponse ; la vérification automatique ne l'attend pas.
"""
from __future__ import annotations

from app_context import tr as _t
from document_dialogs import is_schematron_file
from validation_worker import worker_client
from xml_roots import SchematronInfo, schematron_info

CHECK_TOKEN = ("schematron",)


class SchematronCheckMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    _schematron_check = None            # (document, révision) de la vérification automatique en cours

    def _displayed_schematron(self):
        """``SchematronInfo`` du document affiché si c'est un fichier
        Schematron, sinon None. L'édition et ses parties n'en sont jamais."""
        document = self.document
        if document.in_edition or document.path is None:
            return None
        info = schematron_info(self.editor.toPlainText())
        if info is None and is_schematron_file(document.path):
            return SchematronInfo("", "")
        return info

    def _check_schematron(self, text, revision, *, show_panel, show_success_message, automatic, background):
        """Vérifie le fichier Schematron affiché (texte ``text`` de la
        révision ``revision``) à la place de la validation RELAX NG. Rend le
        résultat, ou None sans attendre (``background``)."""
        session = self.document
        options = dict(revision=revision, show_panel=show_panel, show_success_message=show_success_message,
                       automatic=automatic)
        # Enregistrement, retour au fichier : le résultat de cette révision
        # est réutilisé ; F8 vérifie toujours à nouveau.
        if (not show_success_message and self._last_rng_revision == revision
                and self._last_rng_result is not None and self._last_rng_schema_token == CHECK_TOKEN):
            return self._last_rng_result
        self.rng_status.setText(_t("schematron_check.status.running"))
        self.rng_status.setStyleSheet("color:#777")
        if not background:
            return self._apply_schematron_check(worker_client().check_schematron(text, session.path), **options)
        key = (session, revision)
        if self._schematron_check == key:
            return None                                          # déjà demandée
        self._schematron_check = key

        def arrived(result):
            if self._schematron_check == key:
                self._schematron_check = None
            if self.document is session:
                self._apply_schematron_check(result, **options)
            elif session.view_state:
                session.view_state["status"] = None

        worker_client().check_schematron_async(text, session.path, self, arrived)
        return None

    def _apply_schematron_check(self, result, *, revision, show_panel, show_success_message, automatic):
        """Montre le résultat de la vérification pour la révision
        ``revision`` ; rien si le document a changé depuis."""
        if revision != self.editor.document().revision():
            if self._rng_watch_enabled:
                self.rng_refresh_timer.start(180)
            return None
        self._last_rng_result = result
        self._last_rng_revision = revision
        self._last_rng_schema_token = CHECK_TOKEN
        errors = [issue for issue in result.issues if issue.level not in ("WARNING", "INFO")]
        self._populate_validation_issues(result.issues, jump_to_xml=True)
        notes = [_t("schematron_check.panel.saxon_missing")] if result.schematron_error == "saxon_missing" else []
        if not result.well_formed:
            summary, status, style = (_t("schematron_check.panel.malformed"), _t("schematron_check.status.malformed"),
                                      "color:#a13d32;font-weight:600")
            notes = []
            self._set_document_health("malformed")
        elif errors:
            count = len(errors)
            summary = _t("schematron_check.panel.invalid", count=count)
            status, style = _t("schematron_check.status.invalid", count=count), "color:#a06a20;font-weight:600"
            self._set_document_health("rng_invalid")
        else:
            summary, status, style = _t("schematron_check.panel.valid"), _t("schematron_check.status.valid"), \
                "color:#376b3c"
            self._set_document_health("normal")
        self.validation_summary.setText(" ".join([summary] + notes))
        self.rng_status.setText(status)
        self.rng_status.setStyleSheet(style)
        if show_panel or (errors and not automatic):
            self.show_validation_panel()
        if show_success_message and not errors and result.well_formed:
            self.statusBar().showMessage(_t("schematron_check.message.valid"), 3500)
        return result
