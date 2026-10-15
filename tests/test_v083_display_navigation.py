from pathlib import Path

from selection_sync import containing_span_index, occurrence_index_for_position, choose_occurrence
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]


def test_selection_sync_uses_occurrence_not_first_global_match():
    spans = [(10, 13), (25, 28), (40, 43)]
    assert occurrence_index_for_position(spans, 26) == 1
    assert choose_occurrence(spans, 1, 10) == (25, 28)
    assert choose_occurrence(spans, 99, 41) == (40, 43)


def test_containing_paragraph_span():
    paragraphs = [(0, 100), (100, 220), (220, 350)]
    assert containing_span_index(paragraphs, 153) == 1
    assert containing_span_index(paragraphs, 400) is None


def test_editor_has_vertical_witness_splitter_and_project_local_visibility():
    source = application_source()
    assert 'APP_VERSION = "0.8.5.26.2"' in source
    assert 'self.witness_splitter = QSplitter(Qt.Orientation.Vertical)' in source
    assert 'visibleWitnesses' in source
    assert 'witnessHeights' in source
    assert 'WitnessVisibilityDialog' in source
    assert 'self.witness_scroll.setVisible(has_visible)' in source
    assert 'panel.maximizeRequested.connect(self._toggle_witness_panel_maximize)' in source


def test_toolbar_and_display_menu_are_reorganized():
    source = application_source()
    assert 'self._build_display_menu()' in source
    assert 'self.display_menu_button.setText(_t("menu.display"))' in source
    assert 'menu.addAction(self.action_reload_images)' in source
    assert 'menu.addAction(self.action_choose_witnesses)' in source
    assert 'self.language_menu = menu.addMenu(_t("common.language"))' in source
    assert 'self.language_combo = QComboBox()' not in source
    # XML commands are added together and XPath is no longer after the search block.
    xml_block = source.index('tb.addAction(self.action_validate_rng)')
    assert xml_block < source.index('tb.addAction(self.action_format_xml)', xml_block)
    assert xml_block < source.index('tb.addAction(self.action_xpath_search)', xml_block)
    assert source.index('spacer.setSizePolicy', xml_block) < source.index('self.search_source_label = QLabel', xml_block)


def test_selection_transfer_has_paragraph_occurrence_descriptor():
    source = application_source()
    assert 'def selection_descriptor(self, text, selection_start):' in source
    assert 'def select_visible_text_in_paragraph(self, text, descriptor):' in source
    assert 'def _source_selection_descriptor(self, text, selection_start):' in source
    assert 'def _select_xml_text_in_paragraph(self, text, descriptor):' in source
    assert 'preview.select_visible_text_in_paragraph(selected, desc)' in source
    assert 'self._select_xml_text_in_paragraph(selected, desc)' in source


def test_i18n_display_keys_match():
    import xml.etree.ElementTree as ET
    fr = ET.parse(ROOT / 'i18n' / 'fr.xml').getroot()
    en = ET.parse(ROOT / 'i18n' / 'en.xml').getroot()
    fr_keys = {x.attrib['key'] for x in fr.findall('string')}
    en_keys = {x.attrib['key'] for x in en.findall('string')}
    for key in {
        'menu.display', 'view.witnesses.choose', 'view.witnesses.title',
        'view.witnesses.all', 'view.witnesses.none',
    }:
        assert key in fr_keys and key in en_keys
    assert fr_keys == en_keys
