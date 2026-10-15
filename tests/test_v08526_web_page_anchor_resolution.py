"""V0.8.5.26: folio @n != physical page id must not disable line navigation."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from project_config import load_project
from project_management import ProjectDraft, WitnessDraft, LocalImageDraft, write_project_xml
from web_viewer.generator import build_dataset, make_html
from web_viewer.page_resolver import PageResolver

TEI_NS = 'http://www.tei-c.org/ns/1.0'


def edition(body, facsimile=''):
    return (f'<TEI xmlns="{TEI_NS}">'
            '<teiHeader><fileDesc><titleStmt><title>T</title></titleStmt>'
            '<publicationStmt><p>x</p></publicationStmt><sourceDesc><listWit>'
            '<witness xml:id="Mu">Mu</witness><witness xml:id="F">F</witness>'
            '</listWit></sourceDesc></fileDesc></teiHeader>'
            f'{facsimile}<text><body><p>{body}</p></body></text></TEI>')


def create_project(tmp_path, body, *, links=True, include_image=True, facsimile=''):
    root = Path(__file__).resolve().parents[1]
    (tmp_path / 'xml').mkdir()
    tei = tmp_path / 'xml' / 'edition.xml'
    tei.write_text(edition(body, facsimile), encoding='utf-8')
    a = tmp_path / 'Mu.json'
    a.write_text(json.dumps({'meta': {'witness': 'Mu', 'role': 'base'},
                             'pages': [{'id': 'physical-A', 'lines': [
                                 {'line': 1, 'bbox': {'hpos': 200, 'vpos': 300, 'width': 400, 'height': 50}},
                                 {'line': 2, 'bbox': {'hpos': 200, 'vpos': 360, 'width': 350, 'height': 50}}]}]}), encoding='utf-8')
    b = tmp_path / 'F.json'
    b.write_text(json.dumps({'meta': {'witness': 'F', 'role': 'secondary'},
                             'pages': [{'id': 'physical-F', 'lines': [
                                 {'line': 1, 'base_keys': ['physical-A::1'] if links else [],
                                  'bbox': {'hpos': 220, 'vpos': 480, 'width': 320, 'height': 45}},
                                 {'line': 2, 'base_keys': ['physical-A::2'] if links else [],
                                  'bbox': {'hpos': 220, 'vpos': 535, 'width': 350, 'height': 45}}]}]}), encoding='utf-8')
    images = []
    for name in ('Mu', 'F'):
        img = tmp_path / f'{name}.png'
        img.write_bytes(b'placeholder')
        images.append(img)
    base_images = [LocalImageDraft(images[0], 'f002v', width=1200, height=2000,
                                   surface_id='Mu-p0008')] if include_image else []
    secondary_images = [LocalImageDraft(images[1], 'f055r', width=1200, height=2000,
                                        surface_id='F-p0003')] if include_image else []
    image_type = 'files' if include_image else 'none'
    cfg = ProjectDraft(title='Anchor test', edition=tei, language='fr', fallback_language='en',
                       translations_dir=root / 'i18n', xslt=root / 'rendering' / 'tei-to-html.xsl',
                       css=root / 'rendering' / 'tei.css',
                       custom_elements=root / 'rendering' / 'custom-elements.xml',
                       web_output_dir=tmp_path / 'web_output', web_filename='viewer.html',
                       witnesses=[
                           WitnessDraft('Mu', 'Mu', a, 'base', image_type, None, base_images,
                                        'reference', None, 'auto', [], 'keep', 'reference'),
                           WitnessDraft('F', 'F', b, 'secondary', image_type, None,
                                        secondary_images, 'reference', None, 'auto', [],
                                        'keep', 'reference'),
                       ], base_witness='Mu', xslt_mode='builtin', schema_mode='none')
    return load_project(write_project_xml(tmp_path / 'project.xml', cfg))


def test_folio_n_and_zone_facs_restore_actual_line_sync(tmp_path):
    facs = '<facsimile><surface xml:id="Mu-p0008" n="f002v-003r">' \
           '<zone xml:id="Mu-p0008-left" n="f002v" ulx="0" uly="0" lrx="600" lry="2000"/>' \
           '</surface></facsimile>'
    cfg = create_project(tmp_path,
        '<pb n="f002v" edRef="#Mu" facs="#Mu-p0008-left"/>'
        '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta', facsimile=facs)
    data, missing = build_dataset(cfg)
    assert missing == []
    assert data['meta']['line_sync'] is True
    mu, f = data['witnesses']
    assert mu['line_sync'] is True
    assert f['line_sync'] is True
    assert mu['pages'][0]['id'] == 'physical-A'
    assert [l['corrected'] for l in mu['pages'][0]['lines']] == ['alpha', 'beta']
    assert data['meta']['tei_page_resolution']['resolved_facs'] > 0
    text = [s for block in data['document']['blocks'] for s in block.get('segments', [])
            if s.get('kind') == 'text']
    assert {s['line_key'] for s in text} == {'physical-A::1', 'physical-A::2'}
    html = make_html(data)
    assert 'physical-A::1' in html
    assert 'VariansGeometry.crop' in html


def test_exact_legacy_page_id_survives_stale_facs_with_explicit_witness(tmp_path):
    cfg = create_project(tmp_path,
        '<pb n="physical-A" edRef="#Mu" facs="#unindexed-facs"/>'
        '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta', include_image=False)
    data, _ = build_dataset(cfg)
    assert data['meta']['line_sync'] is True
    assert data['meta']['tei_page_resolution']['resolved_id'] > 0


def test_secondary_without_base_keys_must_stay_page_mode(tmp_path):
    cfg = create_project(tmp_path,
        '<pb n="f002v" edRef="#Mu" facs="#Mu-p0008"/>'
        '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta', links=False)
    data, _ = build_dataset(cfg)
    assert data['meta']['line_sync'] is True
    assert data['witnesses'][1]['line_sync'] is False


def test_unassociated_facs_never_assigned_by_order_or_folio_label(tmp_path):
    cfg = create_project(tmp_path,
        '<pb n="f002v" edRef="#Mu" facs="#a-different-surface"/>'
        '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta')
    data, missing = build_dataset(cfg)
    # A non-resolved folio pointer must not masquerade as a page association.
    # Unlike V0.8.5.25.2, the pivot's lb ordinal is independent of that
    # pointer, exactly as in the desktop editor.
    assert data['meta']['line_sync'] is True
    assert data['witnesses'][0]['line_sync'] is True
    assert data['witnesses'][0]['pages'][0]['id'] == 'physical-A'
    assert data['meta']['tei_page_resolution']['unresolved'] > 0
    assert [s['line_key'] for b in data['document']['blocks']
            for s in b.get('segments', []) if s.get('kind') == 'text'] == [
                'physical-A::1', 'physical-A::2']


def test_duplicate_zone_id_is_ambiguous(tmp_path):
    xml = edition('<pb n="f002v" edRef="#Mu" facs="#shared"/><lb/>alpha',
                  '<facsimile><surface xml:id="Mu-p0008">'
                  '<zone xml:id="shared"/></surface><surface xml:id="Other">'
                  '<zone xml:id="shared"/></surface></facsimile>')
    tei = tmp_path / 'edition.xml'
    tei.write_text(xml, encoding='utf-8')
    p = PageResolver(tei, [{'id': 'physical-A', 'tei_surface_id': 'Mu-p0008'}], 'Mu')
    pb = next(e for e in ET.parse(tei).getroot().iter() if e.tag.endswith('}pb'))
    assert p.resolve(pb) is None
    assert p.stats['ambiguous'] == 1


def test_double_page_two_zones_keep_unique_physical_line_keys(tmp_path):
    facs = ('<facsimile><surface xml:id="Mu-p0008">'
            '<zone xml:id="Mu-p0008-left"/><zone xml:id="Mu-p0008-right"/>'
            '</surface></facsimile>')
    cfg = create_project(tmp_path,
        '<pb n="f002v" edRef="#Mu" facs="#Mu-p0008-left"/>'
        '<lb edRef="#Mu"/>alpha'
        '<pb n="f003r" edRef="#Mu" facs="#Mu-p0008-right"/>'
        '<lb edRef="#Mu"/>beta', facsimile=facs)
    data, _ = build_dataset(cfg)
    assert data['meta']['line_sync'] is True
    lines = data['witnesses'][0]['pages'][0]['lines']
    assert [l['corrected'] for l in lines] == ['alpha', 'beta']
    text = [s for block in data['document']['blocks'] for s in block.get('segments', [])
            if s.get('kind') == 'text']
    assert [s['line_key'] for s in text] == ['physical-A::1', 'physical-A::2']


def test_explicit_graphic_url_matches_physical_page_without_surface_index(tmp_path):
    xml = edition('<pb n="folio-1" edRef="#Mu" facs="#zone1"/><lb/>alpha',
                  '<facsimile><surface xml:id="external-surface">'
                  '<graphic url="https://images.example/service/full/max/0/default.jpg"/>'
                  '<zone xml:id="zone1"/></surface></facsimile>')
    tei = tmp_path / 'edition.xml'
    tei.write_text(xml, encoding='utf-8')
    p = PageResolver(tei, [{'id': 'physical-A', 'image': {
        'type': 'iiif', 'image': 'https://images.example/service/full/max/0/default.jpg'}}], 'Mu')
    pb = next(e for e in ET.parse(tei).getroot().iter() if e.tag.endswith('}pb'))
    assert p.resolve(pb) == 'physical-A'


def test_conflicting_explicit_facs_and_technical_id_fails_closed(tmp_path):
    xml = edition('<pb n="physical-B" edRef="#Mu" facs="#Mu-p0008"/><lb/>alpha')
    tei = tmp_path / 'edition.xml'
    tei.write_text(xml, encoding='utf-8')
    p = PageResolver(tei, [{'id': 'physical-A', 'tei_surface_id': 'Mu-p0008'},
                            {'id': 'physical-B', 'tei_surface_id': 'Mu-p0009'}], 'Mu')
    pb = next(e for e in ET.parse(tei).getroot().iter() if e.tag.endswith('}pb'))
    assert p.resolve(pb) is None
    assert p.stats['ambiguous'] == 1
