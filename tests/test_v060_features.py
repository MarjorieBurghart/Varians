from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]


def test_v060_version_and_custom_completion_integration_are_present():
    source = (ROOT / "editeur_tei.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "' in source
    assert "load_custom_completion" in source
    assert "merge_suggestion_sources" in source
    assert "completion.custom.replace_notice" in source
    assert "completion.source.both" in (ROOT / "i18n" / "fr.xml").read_text(encoding="utf-8")
    assert (ROOT / "CUSTOM_ELEMENTS.md").is_file()


def test_project_custom_values_are_dynamic_not_hardcoded():
    text = (ROOT / "rendering" / "custom-elements.xml").read_text(encoding="utf-8")
    assert '<values source="witnesses" prefix="#"/>' in text
    assert 'valuesMode="replace"' in text
    # Les identifiants des témoins ne doivent pas être figés dans la configuration active.
    import xml.etree.ElementTree as ET
    root = ET.parse(ROOT / "rendering" / "custom-elements.xml").getroot()
    explicit = [(v.text or "").strip() for v in root.findall("./element/attribute/value")]
    assert "#T1" not in explicit and "#T2" not in explicit and "#P" not in explicit


def test_varians_logo_is_real_user_png():
    logo = ROOT / "resources" / "varians_logo.png"
    assert logo.is_file()
    assert logo.stat().st_size > 100_000
