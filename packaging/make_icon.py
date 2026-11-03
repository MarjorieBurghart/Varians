# -*- coding: utf-8 -*-
"""Icône de Varians : le logo (resources/varians_logo.png) sur un carré blanc
aux coins arrondis, visible sur une barre des tâches claire comme sombre.

    python packaging/make_icon.py      # réécrit resources/icons/varians.png

À relancer si le logo change (il faut Pillow, packaging/requirements.txt)."""
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
SIZE = 512          # PyInstaller en tire les tailles de l'icône Windows et macOS
WORK = 4 * SIZE     # dessin à plus grande taille, puis réduction (bords lisses)
MARGIN = 0.12       # marge blanche autour du logo
RADIUS = 0.2        # rayon des coins arrondis


def make_icon(target=ROOT / "resources" / "icons" / "varians.png"):
    """Dessine l'icône (``SIZE`` pixels de côté) : le logo, centré sur un
    carré, réduit avec sa marge sur le carré blanc aux coins arrondis.
    L'écrit dans ``target``, qu'elle remplace, et rend ce chemin."""
    logo = Image.open(ROOT / "resources" / "varians_logo.png").convert("RGBA")
    side = max(logo.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2), logo)
    tile = Image.new("RGBA", (WORK, WORK), (0, 0, 0, 0))
    ImageDraw.Draw(tile).rounded_rectangle((0, 0, WORK - 1, WORK - 1), radius=int(WORK * RADIUS),
                                           fill=(255, 255, 255, 255))
    margin = int(WORK * MARGIN)
    tile.alpha_composite(square.resize((WORK - 2 * margin,) * 2, Image.LANCZOS), (margin, margin))
    tile.resize((SIZE, SIZE), Image.LANCZOS).save(target, optimize=True)
    return target


if __name__ == "__main__":
    print(make_icon())
