from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from tei_facsimile import upsert_pb_at_position, facsimile_ref_at_position
from web_viewer.legacy_v11_core import extract_reading_document
from varians_source import application_source, CURRENT_VERSION

TEI = "http://www.tei-c.org/ns/1.0"


def minimal_tei(body):
    return (
        f'<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
        f'<publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc>'
        f'</fileDesc></teiHeader><text><body>{body}</body></text></TEI>'
    )


def test_mark_page_includes_edref_when_witness_is_known():
    src = minimal_tei('<p>abc</p>')
    pos = src.index('abc')
    out, _, mode = upsert_pb_at_position(src, pos, '1v', 'A1-p0002', witness_id='A1')
    assert mode == 'inserted'
    assert '<pb n="1v" edRef="#A1" facs="#A1-p0002"/>' in out
    ET.fromstring(out)


def test_page_lookup_is_independent_for_each_witness():
    src = minimal_tei(
        '<p>'
        '<pb n="1r" edRef="#A1" facs="#A1-p0001"/>A '
        '<pb n="5r" edRef="#B1" facs="#B1-p0001"/>B '
        '<pb n="1v" edRef="#A1" facs="#A1-p0002"/>C'
        '</p>'
    )
    pos_b = src.index('B ') + 1
    assert facsimile_ref_at_position(src, pos_b, 'A1', {'A1-p0001', 'A1-p0002'}) == 'A1-p0001'
    assert facsimile_ref_at_position(src, pos_b, 'B1', {'B1-p0001'}) == 'B1-p0001'
    pos_c = src.index('C') + 1
    assert facsimile_ref_at_position(src, pos_c, 'A1', {'A1-p0001', 'A1-p0002'}) == 'A1-p0002'
    assert facsimile_ref_at_position(src, pos_c, 'B1', {'B1-p0001'}) == 'B1-p0001'


def test_legacy_pb_without_edref_can_be_assigned_by_known_surface():
    src = minimal_tei('<p><pb n="1r" facs="#A1-p0001"/>abc</p>')
    pos = src.index('abc') + 1
    assert facsimile_ref_at_position(src, pos, 'A1', {'A1-p0001'}) == 'A1-p0001'
    assert facsimile_ref_at_position(src, pos, 'B1', {'B1-p0001'}) is None


def test_reading_document_can_keep_foreign_pb_anchors_without_changing_target_page_state():
    body = (
        '<p><pb n="1r" edRef="#A1" facs="#A1-p0001"/>alpha '
        '<pb n="5r" edRef="#B1" facs="#B1-p0001"/>beta</p>'
    )
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / 'edition.xml'
        p.write_text(minimal_tei(body), encoding='utf-8')
        doc = extract_reading_document(p, '#A1', include_foreign_pagebreaks=True)
    pbs = [s for b in doc['blocks'] for s in b.get('segments', []) if s.get('kind') == 'pb']
    assert [(x['edref'], x['facs'], x['foreign']) for x in pbs] == [
        ('#A1', '#A1-p0001', False),
        ('#B1', '#B1-p0001', True),
    ]


def test_web_viewer_contains_page_mode_click_sync_and_contextual_labels():
    root = Path(__file__).resolve().parents[1]
    web = (root / 'web_viewer' / 'generator.py').read_text(encoding='utf-8')
    assert 'include_foreign_pagebreaks=True' in web
    assert 'syncPagesToDocPosition' in web
    assert 'data-edref' in web
    assert 'foreign-page-anchor' in web
    assert "basePageMode?'viewer.prev_page':'viewer.prev_base'" in web
    assert "basePageMode?'viewer.next_page':'viewer.next_base'" in web


def test_editor_passes_witness_to_page_marker_and_syncs_per_witness():
    root = Path(__file__).resolve().parents[1]
    editor = application_source()
    assert 'witness_id=witness_id' in editor
    assert 'surface_ids=panel._surface_indices.keys()' in editor
    assert 'for witness_id, panel in self.panels.items()' in editor
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in editor


def test_i18n_has_page_navigation_labels_in_both_languages():
    root = Path(__file__).resolve().parents[1]
    fr = (root / 'i18n' / 'fr.xml').read_text(encoding='utf-8')
    en = (root / 'i18n' / 'en.xml').read_text(encoding='utf-8')
    for s in (fr, en):
        assert 'key="viewer.prev_page"' in s
        assert 'key="viewer.next_page"' in s
