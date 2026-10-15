from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from project_config import load_project
from project_management import (
    WitnessDraft,
    create_new_transcription_project,
    minimal_tei_text,
)
from varians_source import application_source
from schema_resolution import detect_xml_models

ROOT = Path(__file__).resolve().parents[1]
TEI = "{http://www.tei-c.org/ns/1.0}"


def test_minimal_tei_has_required_header_and_editable_body():
    text = minimal_tei_text(
        "Édition test",
        [WitnessDraft("A", "Paris, ms. 1", None, "base")],
        "A",
        language="fr",
        schema_mode="none",
    )
    root = ET.fromstring(text)
    assert root.tag == TEI + "TEI"
    assert root.findtext(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}titleStmt/{TEI}title") == "Édition test"
    assert root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}publicationStmt/{TEI}p") is not None
    list_wit = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc/{TEI}listWit")
    assert list_wit is not None
    witness = list_wit.find(f"{TEI}witness")
    assert witness is not None
    assert witness.get("{http://www.w3.org/XML/1998/namespace}id") == "A"
    assert witness.text == "Paris, ms. 1"
    assert root.find(f"{TEI}text/{TEI}body/{TEI}p") is not None


def test_auto_schema_adds_tei_all_xml_model_but_none_does_not():
    witnesses = [WitnessDraft("A", "A", None, "base")]
    auto = minimal_tei_text("Test", witnesses, "A", schema_mode="auto")
    models = detect_xml_models(auto)
    assert len(models) == 1
    assert models[0].schematypens == "http://relaxng.org/ns/structure/1.0"
    assert models[0].href.endswith("/tei_all.rng")

    none = minimal_tei_text("Test", witnesses, "A", schema_mode="none")
    assert detect_xml_models(none) == ()


def test_new_transcription_project_needs_no_existing_tei_or_alignment():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "new-project"
        project_xml = create_new_transcription_project(
            target_dir=target,
            title="Nouvelle édition",
            witnesses=[WitnessDraft("A", "Manuscrit A", None, "base")],
            base_witness="A",
            template_root=ROOT,
            language="fr",
            fallback_language="en",
            xslt_mode="builtin",
            schema_mode="none",
        )
        assert project_xml == target / "project.xml"
        edition = target / "xml" / "edition.xml"
        assert edition.is_file()
        assert not (target / "edition.xml").exists()
        cfg = load_project(project_xml)
        assert cfg.edition == edition.resolve()
        assert cfg.base_witness == "A"
        assert cfg.base.alignment is None
        xml = edition.read_text(encoding="utf-8")
        assert "Nouvelle édition" in xml
        assert '<listWit>' in xml
        assert 'xml:id="A"' in xml
        assert 'Manuscrit A' in xml


def test_new_transcription_auto_schema_is_immediately_rng_aware():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "new-project"
        project_xml = create_new_transcription_project(
            target_dir=target,
            title="New edition",
            witnesses=[WitnessDraft("A", "Witness A", None, "base")],
            base_witness="A",
            template_root=ROOT,
            language="en",
            fallback_language="en",
            xslt_mode="builtin",
            schema_mode="auto",
        )
        cfg = load_project(project_xml)
        assert cfg.schema_mode == "auto"
        text = cfg.edition.read_text(encoding="utf-8")
        assert detect_xml_models(text)
        assert "Edition in preparation." in text
        assert '<listWit>' in text
        assert 'xml:id="A"' in text


def test_ui_source_contains_both_creation_modes_and_switches_creator():
    dialogs = (ROOT / "project_dialogs.py").read_text(encoding="utf-8")
    editor = application_source()
    assert 'project.new.mode.existing' in dialogs
    assert 'project.new.mode.blank' in dialogs
    assert 'self.edition.setEnabled(mode == "existing")' in dialogs
    assert 'create_new_transcription_project' in editor
    assert 'values.get("creation_mode") == "blank"' in editor
    assert 'APP_VERSION = "0.8.5.26.2"' in editor
