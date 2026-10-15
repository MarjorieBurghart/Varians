from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from project_config import load_project
from project_management import WitnessDraft, create_new_transcription_project
from image_sources import apply_witness_image_policy, page_image_source
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_explicit_no_image_source_roundtrips_through_project_xml():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "project"
        project_xml = create_new_transcription_project(
            target_dir=target,
            title="Sans fac-similé",
            witnesses=[WitnessDraft(
                "A", "Manuscrit A", None, "base",
                image_source_type="none",
            )],
            base_witness="A",
            template_root=ROOT,
            language="fr",
            fallback_language="en",
            xslt_mode="builtin",
            schema_mode="none",
        )
        tree = ET.parse(project_xml)
        images = tree.getroot().find("./witnesses/witness/images")
        assert images is not None
        assert images.get("type") == "none"
        cfg = load_project(project_xml)
        assert cfg.base.image_source_type == "none"
        assert cfg.base.image_source_value is None
        assert cfg.base.alignment is None


def test_legacy_witness_without_images_block_stays_auto():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "xml").mkdir()
        (root / "xml" / "edition.xml").write_text(
            "<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>",
            encoding="utf-8",
        )
        (root / "project.xml").write_text("""<teiManuscriptProject version='1'>
<title>Legacy</title><edition file='xml/edition.xml'/><schema type='relaxng' source='none'/>
<interface language='fr' translationsDir='i18n' fallbackLanguage='en'/>
<rendering xsltMode='builtin' css='rendering/tei.css' customElements='rendering/custom-elements.xml'/>
<webViewer outputDir='web_output' filename='viewer.html'/>
<witnesses base='A'><witness id='A' role='base' label='A'/></witnesses>
</teiManuscriptProject>""", encoding="utf-8")
        cfg = load_project(root / "project.xml")
        assert cfg.base.image_source_type == "auto"
        assert cfg.base.image_source_value is None


def test_no_image_source_is_visible_in_witness_ui_and_defaults_for_new_witnesses():
    source = (ROOT / "project_dialogs.py").read_text(encoding="utf-8")
    assert 'project.witness.images.none' in source
    assert 'project.witness.images.auto' in source
    assert 'self.image_source.currentData() or "none"' in source
    assert 'QTableWidget(0, 6)' in source



def test_explicit_none_suppresses_legacy_iiif_but_keeps_alto_lines():
    cache = {
        "meta": {"witness": "A"},
        "pages": [{
            "id": "p1",
            "iiif": {"service": "https://example.org/iiif/a", "label": "f. 1r"},
            "lines": [{"line": 1, "alto": "verbum", "base_keys": ["p1::1"]}],
        }],
    }
    out = apply_witness_image_policy(cache, "none")
    assert out is not cache
    assert out["pages"][0]["lines"][0]["alto"] == "verbum"
    assert "iiif" not in out["pages"][0]
    assert page_image_source(out["pages"][0]).kind == "none"
    # La donnée originale n'est pas détruite en mémoire.
    assert "iiif" in cache["pages"][0]

def test_v072_version_and_documentation_present():
    editor = application_source()
    assert 'APP_VERSION = "0.8.5.26.2"' in editor
    image_doc = (ROOT / "IMAGE_SOURCES.md").read_text(encoding="utf-8")
    assert 'V0.7.2' in image_doc
    assert '<images type="none"' in image_doc
