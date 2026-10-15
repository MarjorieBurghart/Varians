from pathlib import Path
import xml.etree.ElementTree as ET

from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_v059_session_branding_and_ctrl_e_rng_integration_are_present():
    source = application_source()
    assert 'APP_VERSION = "' in source
    assert 'lastOpenProject' in source
    assert 'def close_project(self):' in source
    assert 'forget_open_project()' in source
    assert 'startup_project = last_open_project_path()' in source
    assert 'class AboutDialog' in source
    assert 'Cormorant Garamond' in source and 'SemiBold' in source
    assert 'varians_logo.png' in source
    assert 'def rng_element_suggestions' in source
    assert 'suggestion_provider = getattr(self.main, "rng_element_suggestions", None)' in source
    assert 'allow_custom=True' in source
    assert 'self.action_close_project' in source
    assert 'self.action_about' in source


def test_v059_brand_asset_and_i18n_are_shipped():
    assert (ROOT / "resources" / "varians_logo.png").is_file()
    catalogs = {}
    for lang in ("fr", "en"):
        root = ET.parse(ROOT / "i18n" / f"{lang}.xml").getroot()
        catalogs[lang] = {node.get("key") for node in root.findall("string")}
    assert catalogs["fr"] == catalogs["en"]
    required = {
        "menu.close_project", "help.about", "welcome.subtitle",
        "project.reopen_error.title", "project.reopen_error", "ctrl_e.rng.label",
    }
    assert required <= catalogs["fr"]
