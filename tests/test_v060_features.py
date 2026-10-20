from pathlib import Path
import hashlib
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_v060_version_and_custom_completion_integration_are_present():
    source = application_source()
    assert 'APP_VERSION = "' in source
    assert "load_custom_completion" in source
    assert "merge_suggestion_sources" in source
    assert "completion.custom.replace_notice" in source
    assert "completion.source.both" in (ROOT / "i18n" / "fr.xml").read_text(encoding="utf-8")
    assert (ROOT / "CUSTOM_ELEMENTS.md").is_file()


def test_project_custom_values_are_dynamic_not_hardcoded():
    import xml.etree.ElementTree as ET
    root = ET.parse(ROOT / "rendering" / "custom-elements.xml").getroot()
    # V0.8.8.0 : rdg/@wit suit les <witness> de la TEI (source « ids »), comme
    # lem/@wit et comme la vérification des références.
    attribute = root.find("./element[@name='rdg']/attribute[@name='wit']")
    assert attribute.get("valuesMode") == "replace"
    (values,) = attribute.findall("values")
    assert (values.get("source"), values.get("elements"), values.get("prefix")) == ("ids", "witness", "#")
    # Les identifiants des témoins ne doivent pas être figés dans la configuration active.
    explicit = [(v.text or "").strip() for v in root.findall("./element/attribute/value")]
    assert "#T1" not in explicit and "#T2" not in explicit and "#P" not in explicit


def test_varians_logo_is_real_user_png():
    logo = ROOT / "resources" / "varians_logo.png"
    assert logo.is_file()
    assert logo.stat().st_size > 100_000
