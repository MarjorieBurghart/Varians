from pathlib import Path
import json
import tempfile

from project_management import ProjectDraft, WitnessDraft, LocalImageDraft, AltoFileDraft, write_project_xml
from project_config import load_project
from resource_state import (
    primary_sync_line_count,
    secondary_sync_link_count,
    effective_base_line_sync,
    effective_secondary_line_sync,
)
from varians_source import application_source
from web_viewer.generator import build_dataset

ROOT = Path(__file__).resolve().parents[1]
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _tei(two_witnesses=False):
    wit_b = '<witness xml:id="B1">B1</witness>' if two_witnesses else ''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="{TEI_NS}">
  <teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt>
    <publicationStmt><p>x</p></publicationStmt>
    <sourceDesc><listWit><witness xml:id="A1">A1</witness>{wit_b}</listWit></sourceDesc>
  </fileDesc></teiHeader>
  <text><body><p><pb n="p1" edRef="#A1" facs="#A1-p0001"/><lb edRef="#A1"/>alpha<lb edRef="#A1"/>beta</p></body></text>
</TEI>'''


def _alto(path: Path, image_name="a.jpg", page_id="p1"):
    path.write_text(f'''<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
 <Description><sourceImageInformation><fileName>{image_name}</fileName></sourceImageInformation></Description>
 <Layout><Page ID="{page_id}" WIDTH="1000" HEIGHT="2000"><PrintSpace><TextBlock>
  <TextLine ID="L1" HPOS="10" VPOS="20" WIDTH="300" HEIGHT="40"><String CONTENT="alpha"/></TextLine>
  <TextLine ID="L2" HPOS="10" VPOS="70" WIDTH="300" HEIGHT="40"><String CONTENT="beta"/></TextLine>
 </TextBlock></PrintSpace></Page></Layout>
</alto>''', encoding="utf-8")
    return path


def _alignment(path: Path, witness="A1", role="base", *, links=True, empty=False):
    if empty:
        pages = []
    elif role == "base":
        pages = [{"id": "p1", "lines": [
            {"line": 1, "alto_id": "L1", "bbox": {"hpos": 10, "vpos": 20, "width": 300, "height": 40}},
            {"line": 2, "alto_id": "L2", "bbox": {"hpos": 10, "vpos": 70, "width": 300, "height": 40}},
        ]}]
    else:
        rows = [
            {"line": 1, "alto_id": "BL1", "order": 1, "bbox": {"hpos": 10, "vpos": 20, "width": 300, "height": 40}},
            {"line": 2, "alto_id": "BL2", "order": 2, "bbox": {"hpos": 10, "vpos": 70, "width": 300, "height": 40}},
        ]
        if links:
            rows[0]["base_keys"] = ["p1::1"]
            rows[1]["base_keys"] = ["p1::2"]
        pages = [{"id": "b1", "lines": rows}]
    data = {"meta": {"format": "tei-manuscript-alignment", "format_version": 1,
                     "witness": witness, "role": role}, "pages": pages}
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return path


def _project(root: Path, witnesses):
    (root / "xml").mkdir(parents=True, exist_ok=True)
    (root / "web_output").mkdir(exist_ok=True)
    edition = root / "xml" / "edition.xml"
    edition.write_text(_tei(two_witnesses=len(witnesses) > 1), encoding="utf-8")
    draft = ProjectDraft(
        title="Matrix",
        edition=edition,
        language="fr",
        fallback_language="en",
        translations_dir=ROOT / "i18n",
        xslt=ROOT / "rendering" / "tei-to-html.xsl",
        css=ROOT / "rendering" / "tei.css",
        custom_elements=ROOT / "rendering" / "custom-elements.xml",
        web_output_dir=root / "web_output",
        web_filename="viewer.html",
        witnesses=witnesses,
        base_witness="A1",
        xslt_mode="builtin",
        schema_mode="none",
    )
    return load_project(write_project_xml(root / "project.xml", draft))


def test_resource_state_distinguishes_alignment_file_from_usable_sync():
    empty = {"pages": []}
    base = {"pages": [{"id": "p1", "lines": [{"line": 1}, {"line": 2}]}]}
    sec_unlinked = {"pages": [{"id": "b1", "lines": [{"line": 1}]}]}
    sec_linked = {"pages": [{"id": "b1", "lines": [{"line": 1, "base_keys": ["p1::1"]}]}]}
    assert primary_sync_line_count(empty) == 0
    assert primary_sync_line_count(base) == 2
    assert secondary_sync_link_count(sec_unlinked) == 0
    assert secondary_sync_link_count(sec_linked) == 1
    assert effective_base_line_sync(True, empty) is False
    assert effective_base_line_sync(True, base) is True
    assert effective_secondary_line_sync(True, sec_unlinked, base_line_sync=True) is False
    assert effective_secondary_line_sync(True, sec_linked, base_line_sync=True) is True


def test_empty_base_alignment_plus_local_image_and_alto_stays_page_mode():
    """Régression V0.8.4 : un JSON vide ne doit pas masquer les pages locales."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        image = root / "a.jpg"; image.write_bytes(b"image")
        alto = _alto(root / "a.xml")
        align = _alignment(root / "empty.json", empty=True)
        cfg = _project(root, [
            WitnessDraft("A1", "A1", align, "base", "files", None,
                         [LocalImageDraft(image, "p1", surface_id="A1-p0001")], "reference", None,
                         "files", [AltoFileDraft(alto, "p1")], "reference", "reference")
        ])
        data, missing = build_dataset(cfg)
        base = data["witnesses"][0]
        assert missing == []
        assert data["meta"]["line_sync"] is False
        assert base["line_sync"] is False
        assert len(base["pages"]) == 1
        assert base["pages"][0]["image"]["type"] == "file"
        assert len(base["pages"][0]["lines"]) == 2  # ALTO conservé comme géométrie


def test_secondary_alignment_without_base_keys_stays_page_mode_in_web_viewer():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a = root / "a.jpg"; a.write_bytes(b"a")
        b = root / "b.jpg"; b.write_bytes(b"b")
        base_align = _alignment(root / "A1.json", "A1", "base")
        sec_align = _alignment(root / "B1.json", "B1", "secondary", links=False)
        cfg = _project(root, [
            WitnessDraft("A1", "A1", base_align, "base", "files", None,
                         [LocalImageDraft(a, "p1", surface_id="A1-p0001")], "reference", None,
                         "auto", [], "keep", "reference"),
            WitnessDraft("B1", "B1", sec_align, "secondary", "files", None,
                         [LocalImageDraft(b, "b1", surface_id="B1-p0001")], "reference", None,
                         "auto", [], "keep", "reference"),
        ])
        data, _ = build_dataset(cfg)
        by_id = {w["id"]: w for w in data["witnesses"]}
        assert data["meta"]["line_sync"] is True
        assert by_id["A1"]["line_sync"] is True
        assert by_id["B1"]["line_sync"] is False
        assert len(by_id["B1"]["pages"]) == 1


def test_full_base_and_secondary_alignment_remain_line_mode():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        base_align = _alignment(root / "A1.json", "A1", "base")
        sec_align = _alignment(root / "B1.json", "B1", "secondary", links=True)
        cfg = _project(root, [
            WitnessDraft("A1", "A1", base_align, "base", "none", None, [], "keep", None,
                         "auto", [], "keep", "reference"),
            WitnessDraft("B1", "B1", sec_align, "secondary", "none", None, [], "keep", None,
                         "auto", [], "keep", "reference"),
        ])
        data, missing = build_dataset(cfg)
        by_id = {w["id"]: w for w in data["witnesses"]}
        assert missing == []
        assert data["meta"]["line_sync"] is True
        assert by_id["A1"]["line_sync"] is True
        assert by_id["B1"]["line_sync"] is True
        assert data["meta"]["lines"] == 2


def test_editor_uses_raw_sync_counts_before_alto_overlay():
    source = application_source()
    assert "self._base_sync_line_count = primary_sync_line_count(cache)" in source
    assert "self._secondary_sync_link_counts[w.id] = secondary_sync_link_count(cache)" in source
    assert "(self._base_sync_line_count or 0) > 0" in source
    assert 'APP_VERSION = "0.8.5.26.2"' in source
