from pathlib import Path
import string
import xml.etree.ElementTree as ET
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {
    "fr": "Français",
    "en": "English",
    "de": "Deutsch",
    "ja": "日本語",
    "cs": "Čeština",
    "it": "Italiano",
    "ru": "Русский",
}


def _catalog(code: str):
    root = ET.parse(ROOT / "i18n" / f"{code}.xml").getroot()
    values = {node.get("key"): "".join(node.itertext()) for node in root.findall("string")}
    return root, values


def _fields(text: str):
    result = []
    for _, field_name, _, _ in string.Formatter().parse(text):
        if field_name:
            # str.format accepts indexing/attributes, but the root placeholder is
            # what must remain stable across translations.
            result.append(field_name.split(".", 1)[0].split("[", 1)[0])
    return sorted(result)


def test_current_version_and_toolbar_filename_label_removed():
    source = application_source()
    assert 'APP_VERSION = "0.8.5.26.2"' in source
    assert "self.file_label" not in source
    assert "tb.addWidget(self.file_label)" not in source


def test_all_seven_catalogs_have_same_keys_and_placeholders():
    _, reference = _catalog("en")
    assert len(reference) >= 446
    for code, label in LANGUAGES.items():
        root, values = _catalog(code)
        assert root.get("lang") == code
        assert root.get("label") == label
        assert set(values) == set(reference), code
        for key in reference:
            assert _fields(values[key]) == _fields(reference[key]), (code, key)


def test_language_specific_help_exists_and_is_current():
    for code in LANGUAGES:
        path = ROOT / "help" / f"{code}.html"
        assert path.is_file(), code
        text = path.read_text(encoding="utf-8")
        assert "0.8.5.4" in text
        assert "<h1" in text.lower()
        assert "TODO" not in text


def test_help_dialog_uses_active_language_with_fallback():
    source = application_source()
    assert 'path = HERE / "help" / f"{language}.html"' in source
    assert 'fallback = I18N.fallback' in source
    # No FR/EN-only gate may remain.
    assert 'language in {"fr", "en"}' not in source


def test_developer_handoff_documents_are_present_and_cover_core_invariants():
    handoff = (ROOT / "DEVELOPER_HANDOFF.md").read_text(encoding="utf-8")
    code_map = (ROOT / "CODE_MAP.md").read_text(encoding="utf-8")
    for needle in (
        "source éditoriale",
        "base_keys",
        "<facsimile>",
        "Marquer la page",
        "Internationalisation",
        "resource_state.py",
        "web_viewer/generator.py",
        "QSettings",
    ):
        assert needle in handoff
    for needle in ("editeur_tei.py", "project_config.py", "tei_facsimile.py", "Tests"):
        assert needle in code_map
