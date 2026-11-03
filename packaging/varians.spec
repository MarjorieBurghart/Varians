# -*- mode: python ; coding: utf-8 -*-
"""Recette PyInstaller de la version prête à l'emploi de Varians (V0.9.4.0).

Lancée par ``packaging/build.py`` (qui construit, vérifie avec
``--self-test`` et zippe) ; à la main :
``python -m PyInstaller --noconfirm packaging/varians.spec``.

Un dossier (pas un exécutable unique) : démarrage rapide, rien n'est
décompressé à chaque lancement, et les bibliothèques Qt restent des
fichiers distincts (LGPL). Les fichiers de données sont lus à côté des
modules (``Path(__file__).parent``) : ils sont placés dans ``_internal/``
(``Contents/Resources`` d'un paquet macOS), sous le même nom de dossier
que dans les sources. Les processus de validation et de transformation
relancent l'exécutable lui-même (``--relaxng-worker``,
``--transform-worker``, voir validation_worker et transform_worker)."""
import re
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, copy_metadata

ROOT = Path(SPECPATH).resolve().parent
NAME = "Varians"
VERSION = re.search(r'^APP_VERSION\s*=\s*"([^"]+)"', (ROOT / "app_context.py").read_text(encoding="utf-8"),
                    re.MULTILINE).group(1)

# Dossiers de données, copiés tels quels (sans __pycache__) ; self_test.py
# vérifie qu'ils sont bien là, ainsi que les scripts du viewer web.
DATA_FOLDERS = ("i18n", "help", "rendering", "resources")
WEB_VIEWER_FILES = ("*.js",)


def _data_files():
    files = []
    for folder in DATA_FOLDERS:
        for path in sorted((ROOT / folder).rglob("*")):
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
                files.append((str(path), str(path.parent.relative_to(ROOT))))
    for pattern in WEB_VIEWER_FILES:
        files += [(str(path), "web_viewer") for path in sorted((ROOT / "web_viewer").glob(pattern))]
    return files


def _icon():
    """Icône carrée tirée du logo (convertie en .ico ou .icns par
    PyInstaller, avec Pillow)."""
    from PIL import Image
    logo = Image.open(ROOT / "resources" / "varians_logo.png").convert("RGBA")
    side = max(logo.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(logo, ((side - logo.width) // 2, (side - logo.height) // 2))
    square = square.resize((512, 512), Image.LANCZOS)
    path = Path(workpath) / "varians-icon.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    square.save(path)
    return str(path)


# Saxon (saxonche) n'est cherché que par importlib.util.find_spec : à
# collecter expressément, avec sa bibliothèque native.
saxon_datas, saxon_binaries, saxon_hidden = collect_all("saxonche")
datas = _data_files() + saxon_datas
for package in ("lxml", "saxonche", "certifi"):     # licences des composants
    datas += copy_metadata(package)

a = Analysis(
    [str(ROOT / "editeur_tei.py")],
    pathex=[str(ROOT)],
    binaries=saxon_binaries,
    datas=datas,
    hiddenimports=saxon_hidden + ["certifi"],
    runtime_hooks=[str(Path(SPECPATH) / "rthook_certificates.py")],
    excludes=[
        "tkinter", "_tkinter", "pytest", "_pytest", "pytestqt", "IPython", "matplotlib", "numpy",
        "PySide6.QtTest", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQml",
        "PySide6.QtQuick", "PySide6.QtQuickWidgets", "PySide6.Qt3DCore", "PySide6.QtMultimedia",
        "PySide6.QtPdf", "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtBluetooth",
    ],
    noarchive=False,
)


# Greffons Qt inutiles à un éditeur de bureau, et les bibliothèques qu'eux
# seuls emportent : clavier virtuel (QML, Qt Quick), images PDF, plateformes
# embarquées (eglfs, linuxfb, vnc…), entrées evdev, thème GTK et la pile GTK
# de la machine de construction (sous Linux : conflits de versions avec
# celle du système ; Qt garde ses propres boîtes de dialogue). Gardés :
# windows, cocoa, xcb, wayland, offscreen (vérification), formats d'images
# (TIFF, WebP, SVG…), méthodes de saisie (ibus, compose), portails.
UNUSED_QT = re.compile(
    r"plugins/(platforminputcontexts/[^/]*virtualkeyboard|imageformats/[^/]*qpdf|platformthemes/[^/]*gtk3"
    r"|platforms/[^/]*(eglfs|linuxfb|vnc|minimal|vkkhrdisplay)|egldeviceintegrations/|generic/)"
    r"|Qt6?(VirtualKeyboard|Qml|Quick|Pdf|EglFS|EglFsKms)")
UNUSED_LINUX = re.compile(
    r"^lib(gtk-3|gdk-3|atk-1\.0|atk-bridge-2\.0|atspi|gdk_pixbuf-2\.0|cairo-gobject|cairo|pangocairo-1\.0"
    r"|pangoft2-1\.0|pango-1\.0|epoxy|pixman-1|thai|datrie|fribidi|Xcomposite|Xdamage|Xinerama|Xi|Xrandr"
    r"|Xcursor)\.so")


def _wanted(entry):
    name = entry[0].replace("\\", "/")
    if UNUSED_QT.search(name):
        return False
    return not (sys.platform.startswith("linux") and "/" not in name and UNUSED_LINUX.match(name))


# Les liens symboliques vers ces bibliothèques sont rangés avec les données.
a.binaries = [entry for entry in a.binaries if _wanted(entry)]
a.datas = [entry for entry in a.datas if _wanted(entry)]
pyz = PYZ(a.pure)
icon = _icon()
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=NAME,
    console=False,                  # application fenêtrée (pas de console sous Windows)
    upx=False,                      # UPX : fausses alertes des antivirus
    strip=False,
    icon=icon,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name=NAME, upx=False, strip=False)

if sys.platform == "darwin":
    short_version = ".".join(VERSION.split(".")[:3])
    app = BUNDLE(
        coll,
        name=f"{NAME}.app",
        icon=icon,
        bundle_identifier="io.github.marjorieburghart.varians",
        version=short_version,
        info_plist={
            "CFBundleName": NAME,
            "CFBundleDisplayName": NAME,
            "CFBundleShortVersionString": short_version,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "NSHumanReadableCopyright": "Varians",
        },
    )
