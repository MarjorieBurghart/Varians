"""IIIF web V0.8.5.25: API versions, sizes, fallbacks and offline metadata."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest
from iiif_manifest import parse_manifest
from image_sources import normalized_image_block
from web_viewer.generator import make_html

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'web_viewer' / 'iiif.js'


def javascript(method, *args):
    if not shutil.which('node'):
        pytest.skip('Node.js unavailable')
    script = r'''const fs=require('fs');
const js=fs.readFileSync(process.argv[1],'utf8');
eval(js+'\n;globalThis.iiifTest=VariansIIIF;');
const req=JSON.parse(fs.readFileSync(0,'utf8'));
process.stdout.write(JSON.stringify(globalThis.iiifTest[req.method](...req.args)));'''
    result = subprocess.run(['node', '-e', script, str(JS)],
                            input=json.dumps({'method': method, 'args': args}),
                            capture_output=True, text=True, timeout=15, check=True)
    return json.loads(result.stdout)


FULL = {'x': 0, 'y': 0, 'w': 3924, 'h': 2704}
CROP = {'x': 1962, 'y': 100, 'w': 1900, 'h': 500}


@pytest.mark.parametrize('v,quality,full', [(1, 'native', 'full'), (2, 'default', 'full'), (3, 'default', 'max')])
def test_image_api_versioned_url(v, quality, full):
    src = {'type': 'iiif', 'service': 'https://images.example/iiif/id/', 'iiif_version': v,
           'image': 'https://images.example/thumbnail.jpg'}
    all_urls = javascript('plan', src, FULL, FULL, 900, 1)
    assert all_urls[0]['url'] == f'https://images.example/iiif/id/full/1260,/0/{quality}.jpg'
    assert all_urls[0]['local'] is False
    assert javascript('fullPageURL', src, FULL) == f'https://images.example/iiif/id/full/{full}/0/{quality}.jpg'
    assert all_urls[-1] == {'url': src['image'], 'local': True, 'kind': 'preview'}


def test_region_keeps_same_coords_then_local_reduced_image():
    src = {'type': 'iiif', 'service': 'https://images.example/id', 'iiif_version': 3,
           'image': 'https://images.example/image_490px.jpg'}
    steps = javascript('plan', src, CROP, FULL, 1200, 2)
    assert steps[0]['url'].startswith('https://images.example/id/1962,100,1900,500/')
    assert '/max/0/default.jpg' in steps[0]['url']  # exact-resolution region in IIIF 3
    assert steps[0]['local'] is False
    assert any(p['kind'] == 'full-reduced' and p['local'] and '/full/' in p['url'] for p in steps)
    assert steps[-1]['kind'] == 'preview' and steps[-1]['local']
    assert len({p['url'] for p in steps}) == len(steps)


def test_explicit_iiif_size_constraints_are_respected():
    src = {'type': 'iiif', 'service': 'https://host/id', 'maxWidth': 800,
           'maxHeight': 300, 'maxArea': 150000}
    steps = javascript('plan', src, CROP, FULL, 3000, 2)
    # First region: height cap 300 -> 1140 px max width;
    # area cap sqrt(150000*1900/500) -> 754 px, strongest.
    assert '/754,/0/default.jpg' in steps[0]['url']
    assert steps[0]['kind'] == 'region-best'
    # Full image size must likewise be constrained independently.
    assert next(p for p in steps if p['kind'] == 'full-reduced')['local'] is True


def test_no_service_preview_and_local_are_clipped_not_falsely_iiif_cropped():
    no_service = {'type': 'iiif', 'image': 'https://museum.test/preview.jpg'}
    assert javascript('plan', no_service, CROP, FULL)[0]['local'] is True
    assert javascript('plan', {'type': 'file', 'path': 'images/001.jpg'}, CROP, FULL) == [
        {'url': 'images/001.jpg', 'local': True, 'kind': 'local'}]
    assert javascript('plan', {'type': 'none'}, CROP, FULL) == []
    assert javascript('plan', {'type': 'iiif', 'service': 'javascript:alert(1)'}, CROP, FULL) == []
    assert javascript('acceptInfo', {'width': 3000, 'height': 2000, 'maxWidth': 850})['maxWidth'] == 850
    assert javascript('acceptInfo', {'error': 404}) is None


def test_manifest_v3_preserves_iiif_advertised_limits_without_network():
    example = {'items': [{'id': 'https://sample/iiif/c1', 'type': 'Canvas', 'label': {'en': ['folio']},
              'width': 3924, 'height': 2704, 'items': [{'items': [{
                  'motivation': 'painting', 'body': {'type': 'Image', 'id': 'https://sample/thumbnail',
                      'service': [{'id': 'https://sample/image', 'type': 'ImageService3',
                                   'maxWidth': 1200, 'maxHeight': 1000, 'maxArea': 900000}]}}]}]}]}
    result = parse_manifest(example)
    img = normalized_image_block(result.pages[0])
    assert img['iiif_version'] == 3
    assert img['maxWidth'] == 1200 and img['maxHeight'] == 1000
    assert img['maxArea'] == 900000


def test_export_contains_autonomous_iiif_module_and_no_external_script():
    data = {'meta': {'title': 'Test', 'base_witness': 'Mu', 'has_images': False, 'line_sync': False,
                     'lines': 0, 'variants': 0, 'notes': 0},
            'witnesses': [], 'document': {'blocks': []},
            'i18n': {'default': 'fr', 'fallback': 'fr', 'languages': [], 'catalogs': {'fr': {}}}}
    html = make_html(data)
    assert 'const VariansIIIF = (() =>' in html
    assert 'VariansIIIF.bindStage(stage' in html
    assert '__IIIF_JS__' not in html
    assert 'VariansIIIF.cancelStage(stage)' in html
    assert '<script src=' not in html
