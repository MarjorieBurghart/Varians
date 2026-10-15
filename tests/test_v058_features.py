from pathlib import Path
import xml.etree.ElementTree as ET
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_v058_version_wrap_and_xpath_ui_are_present():
    source = application_source()
    assert 'APP_VERSION = "' in source
    assert 'set_visual_wrap' in source
    assert 'sourceVisualWrap' in source
    assert 'search_xpath' in source
    assert 'Ctrl+Shift+F' in source
    assert 'cellClicked.connect(self.goto_xpath_result)' in source


def test_xpath_module_and_i18n_are_shipped():
    assert (ROOT / "xpath_search.py").is_file()
    catalogs = {}
    for lang in ("fr", "en"):
        root = ET.parse(ROOT / "i18n" / f"{lang}.xml").getroot()
        catalogs[lang] = {node.get("key") for node in root.findall("string")}
    assert catalogs["fr"] == catalogs["en"]
    required = {
        "source.visual_wrap", "xpath.action", "xpath.panel.title",
        "xpath.placeholder", "xpath.run", "xpath.found", "xpath.none",
    }
    assert required <= catalogs["fr"]
