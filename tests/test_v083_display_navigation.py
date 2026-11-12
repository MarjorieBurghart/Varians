from pathlib import Path

from selection_sync import containing_span_index
from varians_source import application_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_containing_paragraph_span():
    paragraphs = [(0, 100), (100, 220), (220, 350)]
    assert containing_span_index(paragraphs, 153) == 1
    assert containing_span_index(paragraphs, 400) is None


def test_editor_has_vertical_witness_splitter_and_project_local_visibility():
    source = application_source()
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in source
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
    # V0.9.2.8 : « Indenter » n'est plus que dans le menu Éditer.
    assert 'tb.addAction(self.action_format_xml)' not in source
    assert xml_block < source.index('tb.addAction(self.action_xpath_search)', xml_block)
    assert source.index('spacer.setSizePolicy', xml_block) < source.index('self.search_source_label = QLabel', xml_block)


def test_selection_transfer_uses_a_quote_with_its_context():
    """V0.9.4.5 : la sélection passe d'un onglet à l'autre par sa citation et
    son contexte (selection_quote) ; l'élément modifiable ne fait que
    départager."""
    source = application_source()
    assert 'def selection_context(self):' in source
    assert 'def select_quote(self, context, focus=True, anywhere=True):' in source
    assert 'def _source_selection_context(self, cursor):' in source
    assert 'def _select_source_quote(self, context, near_cursor=False):' in source
    assert 'preview.select_quote(context)' in source
    assert 'self._select_source_quote(context, near_cursor)' in source


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
