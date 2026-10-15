# -*- coding: utf-8 -*-
"""Accès au code source de l'application pour les tests historiques.

Depuis V0.8.6.0, le code de ``editeur_tei.py`` est réparti entre plusieurs
modules (``app_context``, ``document_session`` et les mixins de
``MainWindow``). Les tests qui inspectent le source ou extraient une méthode
de ``MainWindow`` passent par ces fonctions plutôt que de lire un seul
fichier.
"""
from __future__ import annotations

import ast
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# Ordre de concaténation : editeur_tei.py d'abord (les recherches de texte
# par position, comme source.index(...), y trouvent leurs repères en premier).
APPLICATION_MODULES = (
    "editeur_tei.py",
    "app_context.py",
    "document_session.py",
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


def main_window_classes():
    """``MainWindow`` et les mixins dont elle hérite, avec leur fichier."""
    result = []
    for path, tree in _trees():
        for node in tree.body:
            if isinstance(node, ast.ClassDef) and (node.name == "MainWindow" or node.name.endswith("Mixin")):
                result.append((path, node))
    return result


def class_method_node(class_name: str, method_name: str):
    """Nœud AST et fichier d'une méthode.

    ``class_name == "MainWindow"`` cherche aussi dans les mixins de
    ``MainWindow`` ; tout autre nom de classe est cherché tel quel.
    """
    for path, tree in _trees():
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            if class_name == "MainWindow":
                if not (node.name == "MainWindow" or node.name.endswith("Mixin")):
                    continue
            elif node.name != class_name:
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
