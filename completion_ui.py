# -*- coding: utf-8 -*-
"""Complétion XML guidée par le schéma RELAX NG (Ctrl+Espace, attributs) dans la source."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QTextCursor
from PySide6.QtWidgets import (
    QDialog, QLabel, QLineEdit, QListWidget, QListWidgetItem, QMessageBox, QVBoxLayout,
)
from app_context import tr as _t
from custom_completion import load_custom_completion, merge_suggestion_sources
from rng_completion import (
    adapt_pointer_list_value_context, format_pointer_list_insertion, load_completion_model,
)
from schema_resolution import resolve_schema
from xml_references import REFERENCE_ATTRIBUTES, parse_pointer, target_elements


class CompletionDialog(QDialog):
    """Petit sélecteur filtrable pour Ctrl+Espace.

    Le dialogue est volontairement générique : le calcul du contexte et les
    modifications XML restent dans MainWindow, ce qui facilite les tests du
    moteur RELAX NG sans Qt.
    """

    def __init__(self, title, label, items, prefix="", parent=None, allow_custom=False):
        super().__init__(parent)
        # Chaque entrée peut être une simple chaîne (compatibilité historique)
        # ou un couple (valeur, provenance) où provenance vaut rng/custom/both.
        # La provenance n'est qu'une information d'interface : elle ne change
        # jamais la validité du document.
        self._all_items = []
        for item in items:
            if isinstance(item, (tuple, list)) and len(item) >= 2:
                value, source = str(item[0]), str(item[1])
                # Troisième élément facultatif : description de la valeur
                # (texte de l'entrée visée par un identifiant, nom du témoin).
                description = str(item[2]) if len(item) >= 3 and item[2] else ""
                source_key = {
                    "rng": "completion.source.rng",
                    "custom": "completion.source.custom",
                    "both": "completion.source.both",
                }.get(source)
                if description:
                    display = f"{value}    [{description}]"
                else:
                    display = (f"{value}    [{_t(source_key)}]" if source_key else value)
            else:
                value = str(item)
                display = value
            self._all_items.append((value, display))
        self._selected = None
        self._allow_custom = bool(allow_custom)
        self.setWindowTitle(title)
        # Plus large lorsque des descriptions (nom d'une personne…) suivent les valeurs.
        self.resize(560 if any(display != value for value, display in self._all_items) else 360, 330)
        root = QVBoxLayout(self)
        root.setContentsMargins(8, 8, 8, 8)
        root.setSpacing(6)
        self.label = QLabel(label)
        self.label.setWordWrap(True)
        root.addWidget(self.label)
        self.filter_box = QLineEdit()
        self.filter_box.setPlaceholderText(_t("completion.filter.placeholder"))
        root.addWidget(self.filter_box)
        self.list_widget = QListWidget()
        root.addWidget(self.list_widget, 1)
        self.filter_box.textChanged.connect(self._refilter)
        self.filter_box.returnPressed.connect(self._accept_current)
        self.list_widget.itemActivated.connect(lambda _item: self._accept_current())
        self.list_widget.itemDoubleClicked.connect(lambda _item: self._accept_current())
        self.filter_box.setText(prefix or "")
        self._refilter(prefix or "")
        self.filter_box.setFocus()
        self.filter_box.setCursorPosition(len(prefix or ""))

    @property
    def selected_value(self):
        return self._selected

    def _refilter(self, text):
        needle = (text or "").casefold()
        starts = [x for x in self._all_items if x[0].casefold().startswith(needle)]
        contains = [x for x in self._all_items
                    if (needle in x[0].casefold() or needle in x[1].casefold()) and x not in starts]
        values = starts + contains
        self.list_widget.clear()
        for value, display in values:
            item = QListWidgetItem(display)
            item.setData(Qt.ItemDataRole.UserRole, value)
            self.list_widget.addItem(item)
        if self.list_widget.count():
            self.list_widget.setCurrentRow(0)

    def _accept_current(self):
        typed = self.filter_box.text().strip()
        raw_values = {value for value, _display in self._all_items}
        if self._allow_custom and typed and typed not in raw_values:
            # En mode Ctrl+E, le champ reste réellement éditable : une saisie
            # manuelle ne doit pas être remplacée par le premier résultat dont
            # elle n'est qu'un préfixe.
            self._selected = typed
            self.accept()
            return
        item = self.list_widget.currentItem()
        if item is not None:
            self._selected = item.data(Qt.ItemDataRole.UserRole) or item.text()
            self.accept()
            return
        if self._allow_custom and typed:
            self._selected = typed
            self.accept()


class CompletionMixin:
    """Méthodes de MainWindow : voir la docstring du module."""

    def _resolve_completion_schema(self, xml_text=None):
        """Résout le RNG actif en réutilisant la résolution tant que le prologue
        ``xml-model`` n'a pas changé.

        Cela évite notamment de reconsulter un RNG distant/cache réseau à chaque
        Ctrl+Espace lorsque l'utilisateur ne modifie que le corps de la TEI.
        """
        text = self.editor.toPlainText() if xml_text is None else xml_text
        key = self._schema_resolution_cache_key(text)
        if self._completion_resolution_key == key and self._completion_resolution is not None:
            resolution = self._completion_resolution
            if resolution.schema_path is None or Path(resolution.schema_path).is_file():
                return resolution
        resolution = resolve_schema(
            mode=self._schema_mode,
            xml_text=text,
            xml_path=self.current_path or self.project.edition,
            project_schema=self._schema_file,
            force_refresh=False,
        )
        self._completion_resolution_key = key
        self._completion_resolution = resolution
        return resolution

    def _completion_model_for_schema(self, schema_path):
        path = Path(schema_path).expanduser().resolve()
        stat = path.stat()
        key = (str(path), int(stat.st_mtime_ns), int(stat.st_size))
        if self._completion_model is None or self._completion_model_key != key:
            self.statusBar().showMessage(_t("completion.status.loading"), 2000)
            self._completion_model = load_completion_model(path)
            self._completion_model_key = key
        return self._completion_model

    def _custom_completion_config(self):
        """Relit la configuration projet de saisie personnalisée.

        Le fichier est petit et volontairement relu à chaque invocation pour
        que l'éditeur interne de custom-elements.xml prenne effet immédiatement.
        Une erreur est signalée à l'utilisateur, puis la complétion RNG reste
        utilisable sans cette couche de commodité.
        """
        try:
            return load_custom_completion(self.project.custom_elements)
        except Exception as exc:
            detail = (_t("ctrl_e.config.root_error", file=self.project.custom_elements.name)
                      if str(exc) == "ROOT_NOT_CUSTOM_ELEMENTS"
                      else _t("ctrl_e.config.read_error",
                              file=self.project.custom_elements.name, error=exc))
            self.statusBar().showMessage(detail, 6500)
            return None

    def _custom_witness_ids(self):
        return tuple(w.id for w in getattr(self.project, "witnesses", ()) if getattr(w, "id", ""))

    @staticmethod
    def _filter_existing_attributes(values, existing_attributes):
        existing = set(existing_attributes or ())
        existing_local = {x.split(":", 1)[-1] for x in existing}
        return tuple(
            x for x in values
            if x not in existing and x.split(":", 1)[-1] not in existing_local
        )

    def rng_element_suggestions(self, editor, position=None):
        """Suggestions de Ctrl+E, enrichies par custom-elements.xml.

        Le résultat conserve la provenance de chaque entrée (RNG / Projet /
        les deux). Les suggestions projet sont une aide de saisie uniquement :
        elles ne rendent jamais un élément valide si le RNG l'interdit.
        """
        source_text = self.editor.toPlainText()
        text = source_text if editor is self.editor else editor.toPlainText()
        cursor = editor.textCursor()
        pos = cursor.position() if position is None else int(position)
        cache = (
            self._source_completion_context_cache
            if editor is self.editor
            else self._fragment_completion_context_cache
        )
        try:
            context = cache.analyze(text, pos)
        except Exception:
            return ()
        if context.kind != "element":
            return ()

        custom = self._custom_completion_config()
        custom_items = custom.element_names() if custom is not None else ()
        rng_items = ()
        try:
            resolution = self._resolve_completion_schema(source_text)
            if (self._schema_mode != "none" and not resolution.error
                    and resolution.schema_path is not None):
                model = self._completion_model_for_schema(resolution.schema_path)
                rng_items = model.child_elements_at(
                    context.parent_element,
                    context.preceding_siblings,
                    context.following_siblings,
                )
        except Exception:
            # Ctrl+E reste disponible pendant une correction ou une panne du RNG.
            rng_items = ()
        return tuple(merge_suggestion_sources(rng_items, custom_items, "append"))

    def _auto_attribute_choices(self, editor):
        """A02: filtrage RNG strict sans dialogue ni auto-ajout de valeurs libres."""
        text = editor.toPlainText()
        cursor = editor.textCursor()
        cache = (self._source_completion_context_cache if editor is self.editor
                 else self._fragment_completion_context_cache)
        context = cache.analyze(text, cursor.position())
        if context.kind != "attribute" or not context.prefix:
            return (), context
        model = None
        resolution = self._resolve_completion_schema(self.editor.toPlainText())
        if self._schema_mode != "none" and not resolution.error and resolution.schema_path:
            model = self._completion_model_for_schema(resolution.schema_path)
        # La complétion automatique est strictement limitée aux noms démontrés
        # par le RELAX NG. Les suggestions libres du projet restent accessibles
        # par Ctrl+Espace et ne sont pas présentées comme autorisées par le RNG.
        rng_names = model.allowed_attributes(context.current_element) if model else ()
        names = self._filter_existing_attributes(rng_names, context.existing_attributes)
        prefix = context.prefix.casefold()
        return tuple(dict.fromkeys(n for n in names if n.casefold().startswith(prefix))), context

    def _auto_value_choices(self, editor):
        """Liste automatique des pointeurs (frappe de « # » dans une valeur
        d'attribut) : les valeurs de Ctrl+Espace, à condition qu'elles soient
        toutes des pointeurs (« #id », ou « fichier.xml#id » pour un
        identifiant ambigu). Le texte tapé (« #mo ») est cherché dans la
        valeur, ce qui trouve aussi « personnes.xml#molesme ». Renvoie
        ``([(valeur, description)], contexte)``. Les valeurs finies du RNG,
        qui ne sont jamais des pointeurs, ne sont pas consultées à chaque
        frappe."""
        text = editor.toPlainText()
        position = editor.textCursor().position()
        cache = (self._source_completion_context_cache if editor is self.editor
                 else self._fragment_completion_context_cache)
        context = cache.analyze(text, position)
        if context.kind != "attribute_value":
            return (), context
        context, items, _custom_values, _mode = self._attribute_value_suggestions(
            context, text, position, None, self._custom_completion_config())
        if not items or not all(parse_pointer(value) is not None for value, _source, _description in items):
            return (), context
        prefix = (context.prefix or "").casefold()
        return tuple((value, description) for value, _source, description in items
                     if prefix in value.casefold()), context

    def show_rng_completion(self, editor):
        """Ctrl+Espace : fermeture XML prioritaire, sinon RNG / aides projet."""
        if editor.show_closing_tag_completion(force=True):
            return
        source_text = self.editor.toPlainText()
        model = None
        resolution = self._resolve_completion_schema(source_text)
        if self._schema_mode != "none":
            if resolution.error:
                QMessageBox.warning(
                    self, _t("completion.error.title"),
                    _t("completion.schema_error", error=resolution.error)
                )
            elif resolution.schema_path is not None:
                try:
                    model = self._completion_model_for_schema(resolution.schema_path)
                except Exception as exc:
                    QMessageBox.warning(
                        self, _t("completion.error.title"),
                        _t("completion.analysis_error", error=exc)
                    )

        custom = self._custom_completion_config()
        text = source_text if editor is self.editor else editor.toPlainText()
        cursor = editor.textCursor()
        position = cursor.position()
        cache = (
            self._source_completion_context_cache
            if editor is self.editor
            else self._fragment_completion_context_cache
        )
        context = cache.analyze(text, position)
        has_project_suggestions = False

        if context.kind == "element":
            rng_values = (model.child_elements_at(
                context.parent_element,
                context.preceding_siblings,
                context.following_siblings,
            ) if model is not None else ())
            custom_values = custom.element_names() if custom is not None else ()
            items = merge_suggestion_sources(rng_values, custom_values, "append")
            has_project_suggestions = bool(custom_values)
            title = _t("completion.elements.title")
            parent = context.parent_element or _t("completion.document_root")
            label = _t("completion.elements.label", parent=parent)

        elif context.kind == "attribute":
            rng_values = (model.allowed_attributes(context.current_element)
                          if model is not None else ())
            custom_values = (custom.attribute_names(context.current_element)
                             if custom is not None else ())
            rng_values = self._filter_existing_attributes(rng_values, context.existing_attributes)
            custom_values = self._filter_existing_attributes(custom_values, context.existing_attributes)
            items = merge_suggestion_sources(rng_values, custom_values, "append")
            has_project_suggestions = bool(custom_values)
            title = _t("completion.attributes.title")
            label = _t("completion.attributes.label", element=context.current_element or "?")

        elif context.kind == "attribute_value":
            context, items, custom_values, custom_mode = self._attribute_value_suggestions(
                context, text, position, model, custom)
            has_project_suggestions = bool(custom_values)
            title = _t("completion.values.title")
            # Identifiants du projet : des suggestions, non des valeurs imposées par le schéma.
            label = _t(
                "completion.ids.label" if any(item[1] != "rng" and item[2] for item in items)
                else "completion.values.label",
                attribute=context.current_attribute or "?",
                element=context.current_element or "?",
            )
            if custom_values and custom_mode == "replace":
                label += "\n" + _t("completion.custom.replace_notice")
        else:
            self.statusBar().showMessage(_t("completion.unavailable_here"), 4000)
            return

        if has_project_suggestions and not (
            context.kind == "attribute_value" and custom_values and custom_mode == "replace"
        ):
            label += "\n" + _t("completion.custom.notice")

        # Filtrage par le fragment déjà saisi. Les tuples conservent la source.
        prefix = (context.prefix or "").casefold()
        if prefix:
            filtered = [item for item in items if item[0].casefold().startswith(prefix)]
            if filtered:
                items = filtered
        # Dédupliquer sans perdre l'ordre RNG d'abord, Projet ensuite.
        dedup = []
        seen = set()
        for item in items:
            if item[0] in seen:
                continue
            seen.add(item[0])
            dedup.append(item)
        items = dedup
        if not items:
            if model is None and custom is None:
                self.statusBar().showMessage(_t("completion.no_schema"), 4500)
            else:
                self.statusBar().showMessage(_t("completion.no_suggestions"), 4500)
            return

        dlg = CompletionDialog(title, label, items, context.prefix, self)
        try:
            point = editor.viewport().mapToGlobal(editor.cursorRect().bottomLeft())
            dlg.move(point)
        except Exception:
            pass
        if dlg.exec() != QDialog.DialogCode.Accepted or not dlg.selected_value:
            return
        self._apply_rng_completion(editor, context, dlg.selected_value)

    def _attribute_value_suggestions(self, context, text, position, model, custom):
        """Valeurs proposées dans la valeur d'un attribut : valeurs finies du
        RNG, valeurs de custom-elements.xml et, pour un attribut de référence
        (@ref, @who, @wit…), identifiants des documents du projet.

        Renvoie ``(contexte, [(valeur, provenance, description)], valeurs
        projet, mode)``. Pour une liste de pointeurs (``wit="#T1 #T2"``), le
        contexte est réduit au jeton courant et les pointeurs déjà saisis
        sont retirés.
        """
        element, attribute = context.current_element, context.current_attribute
        rng_values = (model.allowed_attribute_values(element, attribute)
                      if model is not None else ())
        entries_by_targets = {}

        def entries(elements):
            key = frozenset(elements) if elements else None
            if key not in entries_by_targets:
                entries_by_targets[key] = self._reference_id_entries(key)
            return entries_by_targets[key]

        def ids_for(elements):
            # « bernard », ou « personnes.xml#molesme » pour un identifiant ambigu.
            return tuple(dict.fromkeys(value[1:] if value.startswith("#") else value
                                       for value, _d, _e in entries(elements)))

        custom_values, custom_mode = (
            custom.attribute_values(element, attribute, self._custom_witness_ids(), ids_for)
            if custom is not None else ((), "append")
        )
        id_values = ()
        if ((attribute or "").split(":", 1)[-1] in REFERENCE_ATTRIBUTES
                and not (custom_values and custom_mode == "replace")):
            id_values = tuple(value for value, _d, _e in entries(target_elements(element, attribute)))
        items = merge_suggestion_sources(rng_values, tuple(custom_values) + id_values, custom_mode)
        descriptions = {}
        for found in entries_by_targets.values():
            for value, description, _element in found:
                descriptions.setdefault(value, description)
        for witness_id, label in getattr(self, "witness_labels", {}).items():
            descriptions[f"#{witness_id}"] = label
        context, remaining_pointer_values = adapt_pointer_list_value_context(
            context, text, position, [value for value, _source in items]
        )
        if remaining_pointer_values != tuple(value for value, _source in items):
            remaining_set = set(remaining_pointer_values)
            items = [item for item in items if item[0] in remaining_set]
        items = [(value, source, descriptions.get(value, "")) for value, source in items]
        return context, items, custom_values, custom_mode

    def _apply_rng_completion(self, editor, context, value):
        """Insère la suggestion sans remplacer une sélection éditoriale existante."""
        doc = editor.document()
        cursor = QTextCursor(doc)
        start = max(0, int(context.replace_start))
        end = max(start, int(context.replace_end))
        cursor.setPosition(start)
        cursor.setPosition(end, QTextCursor.MoveMode.KeepAnchor)

        if context.kind == "element":
            if context.typed_lt:
                replacement = f"{value}></{value}>"
                inner_pos = start + len(value) + 1
            else:
                replacement = f"<{value}></{value}>"
                inner_pos = start + len(value) + 2
            cursor.insertText(replacement)
            out = QTextCursor(doc)
            out.setPosition(inner_pos)
            editor.setTextCursor(out)
        elif context.kind == "attribute_value":
            replacement, final_pos = format_pointer_list_insertion(
                editor.toPlainText(), start, end, value
            )
            cursor.insertText(replacement)
            out = QTextCursor(doc)
            out.setPosition(final_pos)
            editor.setTextCursor(out)
        else:
            before = editor.toPlainText()[max(0, start - 1):start]
            lead = "" if (before.isspace() or before in {"<", ""}) else " "
            replacement = f'{lead}{value}=""'
            cursor.insertText(replacement)
            quote_pos = start + len(lead) + len(value) + 2
            out = QTextCursor(doc)
            out.setPosition(quote_pos)
            editor.setTextCursor(out)
        editor.ensureCursorVisible()
        editor.setFocus()
