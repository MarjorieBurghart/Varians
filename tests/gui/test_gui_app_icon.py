# -*- coding: utf-8 -*-
"""Icône de Varians (V0.9.4.0) : le logo sur un carré blanc arrondi
(resources/icons/varians.png), visible sur une barre des tâches claire comme
sombre. Elle est l'icône de l'application (barre des tâches de Windows,
fenêtres, Dock de macOS), celle de l'exécutable construit (varians.spec) ;
« --self-test » vérifie qu'elle est chargée. Sous Windows, en mode source,
un identifiant d'application propre fait montrer cette icône, et non celle
de Python, par la barre des tâches."""
from __future__ import annotations

import ast
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ICON = ROOT / "resources" / "icons" / "varians.png"


def test_the_icon_is_the_logo_on_a_white_rounded_square(qapp):
    from PySide6.QtGui import QColor, QImage
    image = QImage(str(ICON))
    assert not image.isNull() and image.hasAlphaChannel()
    side = image.width()
    assert image.height() == side >= 256
    assert image.pixelColor(0, 0).alpha() == 0                              # coins arrondis, transparents
    assert image.pixelColor(side // 20, side // 2) == QColor(255, 255, 255, 255)   # fond blanc
    dark = sum(1 for x in range(0, side, 4) for y in range(0, side, 4)
               if (c := image.pixelColor(x, y)).alpha() == 255 and max(c.red(), c.green(), c.blue()) < 100)
    assert dark > (side // 4) ** 2 // 50                                    # le « V » bleu nuit


def test_varians_uses_its_icon(qapp):
    from app_context import ICON_PATH, apply_application_icon
    assert ICON_PATH == ICON
    previous = qapp.windowIcon()
    try:
        icon = apply_application_icon(qapp)
        assert not icon.isNull() and not qapp.windowIcon().isNull()
        assert qapp.windowIcon().availableSizes()
    finally:
        qapp.setWindowIcon(previous)


def test_the_icon_is_set_when_varians_starts():
    tree = ast.parse((ROOT / "editeur_tei.py").read_text(encoding="utf-8"))
    main = next(node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "main")
    calls = [node.func.id for node in ast.walk(main) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)]
    assert "apply_application_icon" in calls


def test_the_built_application_has_the_icon():
    import self_test
    assert "resources/icons/varians.png" in self_test.RESOURCES
    sys.path.insert(0, str(ROOT / "tests"))
    from test_packaging import _spec_constant
    assert _spec_constant("ICON") == "resources/icons/varians.png"
