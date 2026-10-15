from pathlib import Path
import json
import tempfile

from image_sources import (
    page_image_source, page_image_dimensions, page_image_request,
    normalized_image_block, full_page_target,
)
from project_config import load_project
from project_management import create_portable_project, WitnessDraft

ROOT = Path(__file__).resolve().parents[1]


def test_legacy_iiif_block_is_still_supported():
    page = {
        "id": "p1", "alto_width": 1000, "alto_height": 2000,
        "iiif": {"service": "https://example.org/iiif/abc", "width": 2000,
                 "height": 4000, "iiif_version": 2, "label": "f. 1r"},
    }
    src = page_image_source(page)
    assert src.kind == "iiif"
    assert src.service == "https://example.org/iiif/abc"
    assert src.label == "f. 1r"
    assert page_image_dimensions(page) == (2000.0, 4000.0)
    req = page_image_request(page, {"x": 1, "y": 2, "w": 100, "h": 200})
    assert req and req["source_type"] == "iiif"
    assert "/1,2,100,200/" in req["url"]


def test_new_iiif_block_is_supported():
    page = {"id": "p1", "image": {"type": "iiif", "service": "https://x/iiif/id",
                                     "image": "https://x/iiif/id/full/max/0/default.jpg",
                                     "width": 3000, "height": 4000, "iiif_version": 3}}
    src = page_image_source(page)
    assert src.kind == "iiif"
    assert src.iiif_version == 3
    block = normalized_image_block(page)
    assert block["type"] == "iiif"
    assert block["service"] == "https://x/iiif/id"


def test_local_file_source_resolves_relative_to_project_and_requests_local_crop():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        img = root / "images" / "A" / "001.jpg"
        img.parent.mkdir(parents=True)
        img.write_bytes(b"fake")
        page = {"id": "p1", "alto_width": 100, "alto_height": 100,
                "image": {"type": "file", "path": "images/A/001.jpg",
                          "width": 1000, "height": 1000, "label": "f. 1r"}}
        src = page_image_source(page, root)
        assert src.kind == "file"
        assert src.file_path == img.resolve()
        req = page_image_request(page, {"x": 0, "y": 0, "w": 50, "h": 50}, root)
        assert req["source_type"] == "file"
        assert req["local_crop"] is True
        assert req["url"].startswith("file:")
        kind, target = full_page_target(page, root)
        assert kind == "file" and target == img.resolve()
        assert normalized_image_block(page, root)["path"] == "images/A/001.jpg"


def test_page_without_image_is_a_valid_none_source():
    src = page_image_source({"id": "p1", "lines": []})
    assert src.kind == "none"
    assert src.available is False
    assert page_image_request({"id": "p1"}, {"x": 0, "y": 0, "w": 1, "h": 1}) is None


def test_project_accepts_witness_without_alignment():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / "xml").mkdir()
        (root / "xml" / "edition.xml").write_text("<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>", encoding="utf-8")
        (root / "project.xml").write_text("""<teiManuscriptProject version='1'>
<title>Sans ressources</title><edition file='xml/edition.xml'/><schema type='relaxng' source='none'/>
<interface language='fr' translationsDir='i18n' fallbackLanguage='en'/>
<rendering xsltMode='builtin' css='rendering/tei.css' customElements='rendering/custom-elements.xml'/>
<webViewer outputDir='web_output' filename='viewer.html'/>
<witnesses base='A'><witness id='A' role='base' label='A'/></witnesses>
</teiManuscriptProject>""", encoding="utf-8")
        cfg = load_project(root / "project.xml")
        assert cfg.base_witness == "A"
        assert cfg.base.alignment is None


def test_new_portable_project_can_be_created_without_alignment_file():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        source = td / "source.xml"
        source.write_text("<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>", encoding="utf-8")
        target = td / "project"
        project_xml = create_portable_project(
            target_dir=target, title="Sans image", edition_source=source,
            witnesses=[WitnessDraft("A", "A", None, "base")], base_witness="A",
            template_root=ROOT, language="fr", fallback_language="en",
            xslt_mode="builtin", schema_mode="none",
        )
        text = project_xml.read_text(encoding="utf-8")
        assert '<witness id="A" label="A" role="base"' in text
        assert 'alignment=' not in text
        assert load_project(project_xml).base.alignment is None


def test_v070_source_code_uses_generic_image_model_and_optional_base_alignment():
    source = (ROOT / "editeur_tei.py").read_text(encoding="utf-8")
    assert 'APP_VERSION = "0.8.5.26.2"' in source
    assert 'from image_sources import' in source
    assert 'self.base_alignment_available' in source
    assert 'manuscript.no_image_source' in source


def test_web_viewer_accepts_missing_alignment_and_generic_image_blocks():
    source = (ROOT / "web_viewer" / "generator.py").read_text(encoding="utf-8")
    assert 'normalized_image_block' in source
    assert 'alignment_available = has_line_synchronization(w)' in source
    assert 'function imageSource(p)' in source
