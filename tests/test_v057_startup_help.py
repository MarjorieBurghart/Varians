from pathlib import Path
import xml.etree.ElementTree as ET
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_launcher_does_not_open_demo_project_by_default():
    launcher = (ROOT / "lancer_editeur.bat").read_text(encoding="utf-8").lower()
    assert "python editeur_tei.py" in launcher
    assert "python editeur_tei.py project.xml" not in launcher


def test_welcome_branding_assets_and_help_are_shipped():
    assert (ROOT / "resources" / "ciham.png").is_file()
    assert (ROOT / "resources" / "cnrs.png").is_file()
    assert (ROOT / "help" / "fr.html").is_file()
    assert (ROOT / "help" / "en.html").is_file()
    source = application_source()
    assert 'APP_VERSION = "' in source
    assert "class WelcomeWindow" in source
    assert "win.showMaximized()" in source
    assert 'https://enigma.huma-num.fr' in source
    assert 'https://www.vocabula.lat/?q=' in source
    assert 'QKeySequence("Ctrl+?")' in source


def test_i18n_catalogues_keep_same_keys_and_new_help_completion_keys():
    catalogs = {}
    for lang in ("fr", "en"):
        root = ET.parse(ROOT / "i18n" / f"{lang}.xml").getroot()
        catalogs[lang] = {node.get("key") for node in root.findall("string")}
    assert catalogs["fr"] == catalogs["en"]
    required = {
        "menu.help", "help.enigma", "help.latin_dictionary", "help.software",
        "completion.values.title", "completion.values.label",
        "welcome.project_name", "welcome.pi", "welcome.version",
    }
    assert required <= catalogs["fr"]
