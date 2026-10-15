from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from project_management import WitnessDraft, create_new_transcription_project
from project_config import load_project
from web_viewer.generator import build_dataset, make_html
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]
TEI = "{http://www.tei-c.org/ns/1.0}"
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"


def test_blank_project_uses_structured_listwit_for_all_witnesses():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "p"
        project = create_new_transcription_project(
            target, "Test",
            [WitnessDraft("A1", "Assisi, Sacro convento, 541", None, "base"),
             WitnessDraft("B", "Paris, ms. 2", None, "secondary")],
            "A1", ROOT, "fr", "en", xslt_mode="builtin", schema_mode="none",
        )
        cfg = load_project(project)
        root = ET.parse(cfg.edition).getroot()
        list_wit = root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc/{TEI}listWit")
        assert list_wit is not None
        witnesses = list_wit.findall(f"{TEI}witness")
        assert [(w.get(XML_ID), w.text) for w in witnesses] == [
            ("A1", "Assisi, Sacro convento, 541"),
            ("B", "Paris, ms. 2"),
        ]
        assert root.find(f"{TEI}teiHeader/{TEI}fileDesc/{TEI}sourceDesc/{TEI}p") is None


def test_web_viewer_marks_image_less_project_and_hides_side_column():
    with tempfile.TemporaryDirectory() as td:
        target = Path(td) / "p"
        project = create_new_transcription_project(
            target, "Sans image",
            [WitnessDraft("A", "A", None, "base", image_source_type="none")],
            "A", ROOT, "fr", "en", xslt_mode="builtin", schema_mode="none",
        )
        cfg = load_project(project)
        data, missing = build_dataset(cfg)
        assert missing == []
        assert data["meta"]["has_images"] is False
        html = make_html(data)
        assert '<body class="no-images">' in html
        assert '.no-images .resizer,.no-images .side{display:none}' in html


def test_ui_uses_global_pale_selection_and_hides_manuscript_column_without_images():
    source = application_source()
    assert '#d9ecff' in source
    assert '#eef7ff' in source
    assert 'QAbstractItemView::item:selected' in source
    assert 'self.validation_table.setMouseTracking(True)' in source
    assert 'self.has_any_images = any(' in source
    assert 'self.witness_scroll.setVisible(has_visible)' in source
    assert 'self.action_reload_images.setEnabled' in source


def test_opening_document_explicitly_resets_rng_diagnostics():
    source = application_source()
    assert 'def _reset_validation_state(self):' in source
    open_section = source[source.index('    def open_path(self,path):'):source.index('    def _confirm_save_warning', source.index('    def open_path(self,path):'))]
    assert 'self._reset_validation_state()' in open_section
    assert 'self._clear_validation_table()' in source[source.index('    def _reset_validation_state(self):'):source.index('    def show_validation_panel', source.index('    def _reset_validation_state(self):'))]


def test_version_is_077():
    source = application_source()
    assert 'APP_VERSION = "0.8.5.26.2"' in source
