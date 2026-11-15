# -*- coding: utf-8 -*-
"""Accès au code source de l'application pour les tests historiques.

Depuis V0.8.6.0, le code de ``editeur_tei.py`` est réparti entre plusieurs
modules (``app_context``, ``document_session`` et les mixins de
``MainWindow``) ; depuis V0.9.4.7, celui de ``formatted_view.py`` aussi
(``preview_css``, ``preview_browser`` et les mixins de
``FormattedEditionWidget``), et de nouveaux mixins de ``MainWindow``
(``source_selection``, ``pivot_line_index``…). Les tests qui inspectent le
source ou extraient une méthode passent par ces fonctions plutôt que de lire
un seul fichier.
Les méthodes d'un mixin sont rendues à la classe qui en hérite.
"""
from __future__ import annotations

import ast
import copy
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Version attendue de l'application (app_context.APP_VERSION). À changer ici,
# en même temps que APP_VERSION, à chaque nouvelle version.
CURRENT_VERSION = "0.9.4.6"

# Nombre de messages de chaque catalogue i18n (i18n/*.xml, identique dans les
# sept langues). À changer ici à chaque ajout ou retrait de message.
CATALOG_SIZE = 1351

# Ordre de concaténation : editeur_tei.py d'abord (les recherches de texte
# par position, comme source.index(...), y trouvent leurs repères en premier).
APPLICATION_MODULES = (
    "editeur_tei.py",
    "source_selection.py",
    "pivot_line_index.py",
    "xml_health.py",
    "find_commands.py",
    "window_setup.py",
    "app_context.py",
    "document_session.py",
    "formatted_view.py",
    "preview_css.py",
    "preview_browser.py",
    "formatted_views.py",
    "fragment_editor.py",
    "preview_find.py",
    "element_wrap.py",
    "manuscript_panel.py",
    "code_editor.py",
    "witness_sync.py",
    "project_actions.py",
    "main_menus.py",
    "help_dialogs.py",
    "image_fetch.py",
    "witness_workspace.py",
    "document_io.py",
    "completion_ui.py",
    "validation_panel.py",
    "xpath_panel.py",
    "document_tabs.py",
    "text_segments.py",
    "document_display.py",
    "document_dialogs.py",
    "references_ui.py",
    "apparatus_ui.py",
    "validation_worker.py",
    "busy_indicator.py",
    "transform_ui.py",
    "transform_runner.py",
    "xslt_check_ui.py",
    "schematron_check_ui.py",
    "schematron_rules_dialog.py",
    "tei_stylesheets_ui.py",
)


def module_paths():
    return [ROOT / name for name in APPLICATION_MODULES if (ROOT / name).is_file()]


@lru_cache(maxsize=None)
def application_source() -> str:
    """Source de l'interface de Varians, tous modules réunis."""
    return "\n\n".join(path.read_text(encoding="utf-8") for path in module_paths())


@lru_cache(maxsize=None)
def _trees():
    return [(path, ast.parse(path.read_text(encoding="utf-8"))) for path in module_paths()]


@lru_cache(maxsize=None)
def _mixin_hosts():
    """Mixin → classe qui en hérite (``MainWindow``, ``FormattedEditionWidget``…)."""
    hosts = {}
    for _path, tree in _trees():
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                for base in node.bases:
                    if isinstance(base, ast.Name) and base.id.endswith("Mixin"):
                        hosts[base.id] = node.name
    return hosts


def _host(mixin_name):
    """Classe qui hérite du mixin ; ``MainWindow`` si aucune (comportement
    d'avant V0.9.4.7)."""
    return _mixin_hosts().get(mixin_name, "MainWindow")


def _belongs_to(node, class_name):
    """Vrai si la classe ``node`` est ``class_name`` ou l'un de ses mixins."""
    return node.name == class_name or (node.name.endswith("Mixin") and _host(node.name) == class_name)


def main_window_classes():
    """``MainWindow`` et les mixins dont elle hérite, avec leur fichier."""
    result = []
    for path, tree in _trees():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and _belongs_to(node, "MainWindow"):
                result.append((path, node))
    return result


def class_method_node(class_name: str, method_name: str):
    """Nœud AST et fichier d'une méthode, cherchée dans la classe et dans les
    mixins dont elle hérite."""
    for path, tree in _trees():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef) or not _belongs_to(node, class_name):
                continue
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name == method_name:
                    return path, item
    raise LookupError(f"{class_name}.{method_name} introuvable")


def main_window_method_node(method_name: str):
    return class_method_node("MainWindow", method_name)[1]


def method_source(class_name: str, method_name: str) -> str:
    path, node = class_method_node(class_name, method_name)
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node)


@lru_cache(maxsize=None)
def application_ast() -> ast.Module:
    """Arbre syntaxique de l'interface, tous modules réunis.

    Les méthodes des mixins sont replacées dans le corps de la classe qui en
    hérite (``MainWindow``, ``FormattedEditionWidget``), comme lorsqu'elles y
    étaient définies ; les classes ``*Mixin`` elles-mêmes sont omises.
    L'arbre est partagé entre les tests : ne pas le modifier.
    """
    body = []
    hosts = {}
    mixin_methods = {}
    for path, tree in _trees():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and node.name.endswith("Mixin"):
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        item = copy.deepcopy(item)
                        _tag(item, path)
                        mixin_methods.setdefault(_host(node.name), []).append(item)
                continue
            node = copy.deepcopy(node)
            _tag(node, path)
            if isinstance(node, ast.ClassDef):
                hosts.setdefault(node.name, node)
            body.append(node)
    for class_name, methods in mixin_methods.items():
        if class_name in hosts:
            hosts[class_name].body.extend(methods)
    return ast.Module(body=body, type_ignores=[])


def _tag(node, path):
    for sub in ast.walk(node):
        sub._varians_path = path


def node_source(node) -> str:
    """Texte source exact d'un nœud de ``application_ast()``, lu dans son fichier."""
    path = getattr(node, "_varians_path", ROOT / "editeur_tei.py")
    return ast.get_source_segment(path.read_text(encoding="utf-8"), node)
