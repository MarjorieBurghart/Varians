"""V0.8.5.14: adding independent OCR cannot hide existing IIIF working images."""
from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from alto_import import build_alto_cache
from iiif_manifest import parse_manifest, write_cache, cache_path
from iiif_page_selection import canvas_key
from iiif_local import apply_working_copy, index_path, remote_key, _request_url
from image_sources import apply_witness_image_policy, page_navigation_items, page_image_source
from web_viewer.generator import build_dataset
from project_config import load_project


def manifest(n=5):
    raw = {'sequences': [{'canvases': [{
        '@id': f'https://sample.test/canvas/{i}', 'label': f'fol. {i}r',
        'images': [{'resource': {'@id': f'https://sample.test/image/{i}/full/full/0/default.jpg',
                    'service': {'@id': f'https://sample.test/image/{i}',
                                'profile': 'http://iiif.io/api/image/2/level2.json'},
                    'width': 1399, 'height': 1945}}]
    } for i in range(1, n + 1)]}]}
    return parse_manifest(raw, 'https://sample.test/manifest')


def alto(path, filename='scanned_copy_of_page.jpg'):
    path.write_text('''<?xml version="1.0" encoding="UTF-8"?>
    <alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Description>
    <sourceImageInformation><fileName>%s</fileName></sourceImageInformation>
    </Description><Layout><Page WIDTH="1399" HEIGHT="1945" ID="ocr-p1">
    <PrintSpace><TextBlock><TextLine ID="l1" HPOS="100" VPOS="200"
    WIDTH="800" HEIGHT="40"><String CONTENT="Proba"/></TextLine></TextBlock>
    </PrintSpace></Page></Layout></alto>''' % filename, encoding='utf-8')
    return path


def policy(cache, manifest_obj, root, selected=None, ocr_links=(), local=False):
    write_cache(cache_path(root, 'L'), manifest_obj.source, manifest_obj.raw)
    out = apply_witness_image_policy(cache, 'iiif', manifest_obj.source, root, (), 'L',
        'selected' if selected is not None else 'all', selected or (), ocr_links)
    if local:
        out = apply_working_copy(out, root, 'L')
    return out


def add_copy(root, m, number=1):
    picture = m.pages[number-1]['image']
    folder = index_path(root, 'L').parent
    folder.mkdir(parents=True, exist_ok=True)
    file = folder / (f'{number:032x}' + '.jpg')
    file.write_bytes(b'\xff\xd8\xffimage')
    try:
        entries = json.loads(index_path(root, 'L').read_text(encoding='utf8'))['images']
    except FileNotFoundError:
        entries = {}
    entries[remote_key(picture)] = {'file':file.name, 'source':_request_url(picture)}
    index_path(root, 'L').write_text(json.dumps({'format':'varians-iiif-local-1',
        'images':entries}),encoding='utf8')
    return file


def test_adding_unmatched_alto_does_not_disappear_all_iiif_images(tmp_path):
    m = manifest()
    before = policy({'pages': []}, m, tmp_path)
    assert len(before['pages']) == 5
    xml = alto(tmp_path/'unrelated.xml')
    cache = build_alto_cache([xml], 'L')
    after = policy(cache, m, tmp_path)
    assert [p['id'] for p in before['pages']] == [p['id'] for p in after['pages']]
    assert [p['tei_surface_id'] for p in before['pages']] == [p['tei_surface_id'] for p in after['pages']]
    assert all(p['image']['type'] == 'iiif' for p in after['pages'])
    assert len(page_navigation_items(after, tmp_path)) == 5
    assert len(after['unassociated_layout_pages']) == 1
    assert after['meta']['iiif_unassociated_layout_count'] == 1
    assert len(after['unassociated_layout_pages'][0]['lines']) == 1
    assert not any(p['lines'] for p in after['pages'])


def test_selected_canvases_survive_unmatched_alto_without_invented_order(tmp_path):
    m = manifest(8)
    chosen = [canvas_key(m.pages[6]), canvas_key(m.pages[2])]
    before = policy({'pages': []}, m, tmp_path, chosen)
    cache = build_alto_cache([alto(tmp_path/'random.xml')], 'L')
    after = policy(cache, m, tmp_path, chosen)
    assert [p['iiif_canvas_key'] for p in after['pages']] == [p['iiif_canvas_key'] for p in before['pages']]
    assert len(after['pages']) == 2
    assert all(p['image']['type'] == 'iiif' for p in after['pages'])
    assert len(after['unassociated_layout_pages']) == 1


def test_explicit_ocr_canvas_link_attaches_geometry_without_changing_image_identity(tmp_path):
    m = manifest(5)
    xml = alto(tmp_path/'completely_unrelated.xml')
    cache = build_alto_cache([xml], 'L')
    chosen = [canvas_key(m.pages[1]), canvas_key(m.pages[3])]
    out = policy(cache, m, tmp_path, chosen, [(str(xml), chosen[1])])
    assert [len(p['lines']) for p in out['pages']] == [0, 1]
    assert out['pages'][1]['lines'][0]['alto_id'] == 'l1'
    assert out['pages'][1]['id'] == m.pages[3]['id']
    assert out['pages'][1]['tei_surface_id'] == 'L-p0004'
    assert out['unassociated_layout_pages'] == []
    assert out['meta']['iiif_unassociated_layout_count'] == 0


def test_exact_folio_label_matches_without_positional_guess(tmp_path):
    m = manifest(4)
    cache = build_alto_cache([alto(tmp_path/'folio.xml', 'fol. 3r.jpg')], 'L')
    out = policy(cache, m, tmp_path)
    assert [len(p['lines']) for p in out['pages']] == [0, 0, 1, 0]
    assert not out['unassociated_layout_pages']


def test_local_working_copy_is_preserved_if_alto_is_unmatched(tmp_path):
    m = manifest(3)
    local = add_copy(tmp_path, m, 1)
    before = policy({'pages': []}, m, tmp_path, local=True)
    after = policy(build_alto_cache([alto(tmp_path/'other.xml')], 'L'),
                   m, tmp_path, local=True)
    assert before['pages'][0]['image']['path'] == str(local)
    assert after['pages'][0]['image']['path'] == str(local)
    assert after['pages'][0]['image']['remote_iiif']['canvas'] == canvas_key(m.pages[0])
    assert page_image_source(after['pages'][0],tmp_path).file_path == local
    assert len(after['pages']) == 3


def test_ocr_source_filename_of_cached_local_copy_maps_exact_canvas(tmp_path):
    m = manifest(4)
    local = add_copy(tmp_path,m,3)
    ocr = alto(tmp_path/'from_local_image.xml', local.name)
    out = policy(build_alto_cache([ocr], 'L'), m, tmp_path, local=True)
    assert [len(p['lines']) for p in out['pages']] == [0, 0, 1, 0]
    assert out['pages'][2]['iiif_resolution']['method'] == 'local_copy'
    assert out['pages'][2]['image']['path'] == str(local)
    assert out['unassociated_layout_pages'] == []


def test_duplicate_or_conflicting_ocr_never_attaches_to_wrong_canvas(tmp_path):
    m = manifest(3)
    local = add_copy(tmp_path,m,1)
    a = alto(tmp_path/'ocr_a.xml',local.name)
    b = alto(tmp_path/'ocr_b.xml',local.name)
    out = policy(build_alto_cache([a,b], 'L'), m, tmp_path)
    assert len(out['pages']) == 3
    assert len(out['unassociated_layout_pages']) == 2
    assert not any(p['lines'] for p in out['pages'])
    assert all(p['image']['type'] == 'iiif' for p in out['pages'])


def test_non_sync_iiif_with_alto_works_in_web_dataset(tmp_path):
    m = manifest(4)
    add_copy(tmp_path,m,2)
    ocr = alto(tmp_path/'mysterious.xml', 'entirely_different.jpg')
    template = load_project(Path(__file__).resolve().parents[1]/'project.xml')
    from project_config import AltoFileConfig
    manuscript = replace(template.witnesses[1], id='L', label='L', alignment=None,
        role='secondary', image_source_type='iiif', image_source_value=m.source,
        iiif_selection_mode='selected',
        iiif_selected_canvases=(canvas_key(m.pages[1]),canvas_key(m.pages[3])),
        iiif_local_copy=True, iiif_web_local_copy=True,
        alto_source_type='files', alto_files=(AltoFileConfig(ocr),))
    project = replace(template, witnesses=(template.witnesses[0], manuscript),
                      path=tmp_path/'project.xml')
    write_cache(cache_path(tmp_path,'L'), m.source, m.raw)
    data,_ = build_dataset(project)
    got = next(w for w in data['witnesses'] if w['id']=='L')
    assert len(got['pages'])==2
    assert [p['image']['type'] for p in got['pages']] == ['file','iiif']
    assert got['pages'][0]['image']['remote_iiif']['canvas']==canvas_key(m.pages[1])
    assert got['line_sync'] is False


def test_sync_json_with_unidentified_pages_stays_conservative(tmp_path):
    m = manifest(5)
    from iiif_resolution import overlay_resolved_manifest
    cache = {'meta':{'format':'tei-manuscript-alignment','witness':'F'},
        'pages':[{'id':'stable-json-id', 'lines':[{'line':1,'base_keys':['Mu::1']}]}]}
    out=overlay_resolved_manifest(cache,m,'F')
    assert len(out['pages'])==1
    assert out['pages'][0]['image']['type']=='none'
    assert out['pages'][0]['lines'][0]['base_keys']==['Mu::1']
    assert 'unassociated_layout_pages' not in out


def test_selected_mode_is_preserved_when_all_canvases_selected(tmp_path):
    m = manifest(3)
    cache = build_alto_cache([alto(tmp_path/'unknown.xml')], 'L')
    out = policy(cache, m, tmp_path, [canvas_key(p) for p in m.pages])
    assert out['meta']['iiif_selection_mode'] == 'selected'
    assert len(out['pages']) == 3


def test_repeated_ocr_page_ids_still_allow_file_specific_manual_links(tmp_path):
    m = manifest(3)
    one = alto(tmp_path/'one.xml', 'unknown.jpg')
    two = alto(tmp_path/'two.xml', 'unknown.jpg')
    cache = build_alto_cache([one,two], 'L')
    chosen = [canvas_key(m.pages[0]), canvas_key(m.pages[2])]
    out = policy(cache, m, tmp_path, chosen,
        [(str(one), chosen[1]), (str(two),chosen[0])])
    assert [len(p['lines']) for p in out['pages']] == [1, 1]
    assert [p['alto_source_file'] for p in out['pages']] == [str(two), str(one)]
    assert not out['unassociated_layout_pages']


def test_conflicting_local_copy_and_manual_link_preserves_images_without_wrong_geometry(tmp_path):
    m = manifest(3)
    local = add_copy(tmp_path,m,1)
    ocr = alto(tmp_path/'mismatched.xml', local.name)
    out = policy(build_alto_cache([ocr], 'L'), m, tmp_path,
        ocr_links=[(str(ocr), canvas_key(m.pages[1]))])
    assert len(out['pages']) == 3
    assert not any(p['lines'] for p in out['pages'])
    assert out['unassociated_layout_pages'][0]['iiif_resolution']['method'] == 'ocr_local_copy_conflict'
    assert all(page_image_source(p, tmp_path).available for p in out['pages'])


def test_source_layout_cache_is_not_mutated(tmp_path):
    m = manifest(3)
    src = build_alto_cache([alto(tmp_path/'unknown.xml')], 'L')
    before = json.dumps(src, sort_keys=True)
    _out = policy(src, m, tmp_path)
    assert json.dumps(src, sort_keys=True) == before
