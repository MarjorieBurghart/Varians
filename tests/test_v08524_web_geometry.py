"""V0.8.5.24: desktop/web coordinate contract, no invented OCR alignment."""
from __future__ import annotations

import ast
import json
import math
from pathlib import Path
import shutil
import subprocess

import pytest

from image_sources import display_window_indices, effective_line_bbox, page_image_dimensions
from web_viewer.generator import make_html, package_local_images

ROOT = Path(__file__).resolve().parents[1]
JS = ROOT / 'web_viewer' / 'geometry.js'


def web_geometry(op: str, **kwargs):
    if not shutil.which('node'):
        pytest.skip('node: JavaScript geometry runtime not available')
    code = r'''const fs=require('fs');
const js=fs.readFileSync(process.argv[1],'utf8');
eval(js+'\n;globalThis.__geom = VariansGeometry;');
const request=JSON.parse(fs.readFileSync(0,'utf8'));
const out=globalThis.__geom[request.op](...request.args);
process.stdout.write(JSON.stringify(out));'''
    args = kwargs['args']
    result = subprocess.run(['node', '-e', code, str(JS)], input=json.dumps({'op': op, 'args': args}),
                            capture_output=True, text=True, timeout=10, check=True)
    return json.loads(result.stdout)


def desktop_geometry():
    """Run only the *actual* two pure geometry functions from the Qt module.

    Extraction avoids importing PySide6 in CI; Python code and calculations
    are still the production functions, not a rewritten test oracle.
    """
    src = ast.parse((ROOT / 'editeur_tei.py').read_text(encoding='utf-8'))
    functions = [node for node in src.body if isinstance(node, ast.FunctionDef)
                 and node.name in ('scaled_bbox', 'crop_for_items')]
    assert len(functions) == 2
    env = {'effective_line_bbox': effective_line_bbox, 'page_image_dimensions': page_image_dimensions}
    exec(compile(ast.Module(body=functions, type_ignores=[]), str(ROOT / 'editeur_tei.py'), 'exec'), env)
    return env


def item(page, n, x, y, w=400, h=42, *, polygon=None):
    line = {'line': n, 'bbox': {'hpos': x, 'vpos': y, 'width': w, 'height': h}}
    if polygon is not None:
        line['polygon'] = polygon
    return {'p': page, 'l': line}


def near_dict(x, y):
    assert x.keys() == y.keys()
    for k in x:
        assert x[k] == pytest.approx(y[k]), (k, x, y)


def test_column_and_page_transitions_are_identical_to_desktop():
    p = {'id': 'f16r', 'alto_width': 1300, 'alto_height': 1900,
         'image': {'type': 'file', 'width': 2600, 'height': 3800}}
    other = {'id': 'f16v', 'alto_width': 1300, 'alto_height': 1900, 'image': p['image']}
    items = [item(p, 26, 125, 1650), item(p, 27, 125, 1710),
             item(p, 28, 700, 210), item(p, 29, 700, 260),
             item(other, 1, 700, 200)]
    for center in range(len(items)):
        expected = display_window_indices(items, center)
        actual = web_geometry('windowIndices', args=[items, center, 1])
        assert actual == expected
    assert web_geometry('windowIndices', args=[items, 2, 1]) == [2, 3]


def test_polygon_concave_keeps_vertices_and_crop_contains_even_outside_bbox():
    p = {'id': 'page-polygon', 'alto_width': 1000, 'alto_height': 2000,
         'image': {'type': 'file', 'width': 2000, 'height': 4000}}
    points = [[100, 300], [300, 300], [295, 330], [240, 315], [170, 345], [85, 325]]
    it = item(p, 1, 100, 302, 180, 20, polygon=points)
    expected_polygon = [[a * 2, b * 2] for a,b in points]
    assert web_geometry('scaledPolygon', args=[p, it['l']]) == expected_polygon
    desktop = desktop_geometry()
    expected_bbox = desktop['scaled_bbox'](it)
    actual_bbox = web_geometry('scaledBBox', args=[p, it['l']])
    near_dict(expected_bbox, actual_bbox)
    expected_crop = desktop['crop_for_items']([it])
    actual_crop = web_geometry('crop', args=[[it],24])
    assert actual_crop == expected_crop
    assert actual_crop['x'] <= min(x for x, _ in expected_polygon)
    assert actual_crop['y'] <= min(y for _, y in expected_polygon)
    assert actual_crop['x'] + actual_crop['w'] >= max(x for x, _ in expected_polygon)
    assert actual_crop['y'] + actual_crop['h'] >= max(y for _, y in expected_polygon)


def test_polygon_without_bbox_and_absent_geometry_do_not_make_false_frames():
    page = {'id': 'x', 'alto_width': 1000, 'alto_height': 2000,
            'image': {'type': 'file', 'width': 2000, 'height': 4000}}
    poly_only = {'polygon': [[50, 60], [120, 59], [150, 94], [60, 100]]}
    it = {'p':page, 'l':poly_only}
    d = desktop_geometry()
    near_dict(web_geometry('scaledBBox',args=[page,poly_only]), d['scaled_bbox'](it))
    assert web_geometry('crop',args=[[it]]) == d['crop_for_items']([it])
    missing = {'p':page,'l':{'line':2}}
    assert d['crop_for_items']([missing]) is None
    assert web_geometry('scaledBBox',args=[page,missing['l']]) is None
    assert web_geometry('crop',args=[[it, missing]]) is None
    assert web_geometry('scaledPolygon',args=[page, {'polygon':[[1,2],[3,None],[4,6]]}]) == []


def test_leiden_zone_coordinates_are_image_pixels_not_ocr_pixels():
    p={'id':'L8','alto_width':1962,'alto_height':1352,
       'image':{'type':'file','width':3924,'height':2704}}
    assert web_geometry('folioRegion', args=[p,[1962,0,1962,2704]]) == {
        'x':1962,'y':0,'w':1962,'h':2704}
    assert web_geometry('folioRegion', args=[p,[0,0,1962,2704]]) == {
        'x':0,'y':0,'w':1962,'h':2704}
    assert web_geometry('folioRegion', args=[p,[1950,0,2500,2704]]) == {
        'x':1950,'y':0,'w':1974,'h':2704}


def test_iiif_full_canvas_preview_has_same_reference_space():
    page={'id':'L','alto_width':3924,'alto_height':2704,
          'image':{'type':'iiif','width':3924,'height':2704}}
    line={'polygon':[[2200,1200],[3500,1200],[3400,1350],[2300,1400]]}
    p=web_geometry('scaledPolygon', args=[page,line])
    assert p[0][0] == 2200
    # Example physical image 490px wide; coordinates must be reduced only
    # by bitmap display size, not by pretending 490px is a source crop.
    assert p[0][0] * 490/3924 == pytest.approx(274.71967,abs=.001)


def test_nearest_linked_secondary_never_uses_unrelated_arithmetic_midpoint():
    assert web_geometry('nearestIndex',args=[[1,9],8,12]) == 9
    assert web_geometry('nearestIndex',args=[[1,9],0,12]) == 1
    assert web_geometry('nearestIndex',args=[[],0,12]) is None


def test_html_embeds_offline_geometry_and_escapes_user_title():
    data={'meta':{'title':'A <img src=x onerror=alert(1)>', 'base_witness':'A',
                   'has_images':False,'line_sync':False,'lines':0,'variants':0},
          'witnesses':[], 'document':{'blocks':[]},
          'i18n':{'default':'fr','fallback':'fr','languages':[],'catalogs':{'fr':{}}}}
    html=make_html(data)
    assert '&lt;img src=x onerror=alert(1)&gt;' in html
    assert '<title>A <img ' not in html
    assert 'const VariansGeometry = ' in html
    assert '__GEOMETRY_JS__' not in html
    assert 'function windowItems(st)' in html


def test_local_assets_are_packaged_or_explicitly_flagged(tmp_path):
    img=tmp_path/'present.png';img.write_bytes(b'valid copy placeholder')
    data={'meta':{},'witnesses':[{'id':'W','pages':[
        {'id':'p1','image':{'type':'file','path':str(img)}},
        {'id':'p2','image':{'type':'file','path':str(tmp_path/'absent.png')}},
    ]}]}
    project=type('P',(),{'root_dir':tmp_path})()
    package_local_images(data,project,tmp_path/'website')
    assert (tmp_path/'website'/data['witnesses'][0]['pages'][0]['image']['path']).read_bytes()==img.read_bytes()
    assert data['witnesses'][0]['pages'][1]['image']['type']=='none'
    assert data['meta']['export_warnings'][0]['page']=='p2'


def test_orphaned_base_keys_do_not_activate_web_line_mode(tmp_path):
    """Real project build, no ordinal alignment invented by the web exporter."""
    from test_v084_consolidation import _alignment, _project
    from project_management import WitnessDraft
    from web_viewer.generator import build_dataset
    a = _alignment(tmp_path / 'A1.json', 'A1', 'base')
    b = _alignment(tmp_path / 'B1.json', 'B1', 'secondary', links=True)
    content = json.loads(b.read_text(encoding='utf8'))
    for line in content['pages'][0]['lines']:
        line['base_keys'] = ['A1-unknown::999']
    b.write_text(json.dumps(content), encoding='utf8')
    cfg = _project(tmp_path, [
        WitnessDraft('A1','A1',a,'base','none',None,[],'keep',None,'auto',[],'keep','reference'),
        WitnessDraft('B1','B1',b,'secondary','none',None,[],'keep',None,'auto',[],'keep','reference')])
    data, _ = build_dataset(cfg)
    by_id = {w['id']: w for w in data['witnesses']}
    assert by_id['A1']['line_sync'] is True
    assert by_id['B1']['line_sync'] is False
    # The original scientific data remain intact.
    assert json.loads(b.read_text(encoding='utf8'))['pages'][0]['lines'][0]['base_keys'] == ['A1-unknown::999']
