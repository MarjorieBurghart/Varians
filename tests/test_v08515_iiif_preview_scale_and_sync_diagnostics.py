"""V0.8.5.15 regressions: IIIF thumbnail geometry and missing JSON base links."""
from pathlib import Path
from math import isclose
import xml.etree.ElementTree as ET

from image_sources import (image_scene_reference_crop, page_image_dimensions,
                           page_image_request)
from resource_state import secondary_sync_link_count
from varians_source import application_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _line_x_on_display(page, pix_width, x):
    crop = image_scene_reference_crop(page, pix_width, 330)
    return (x - crop['x']) * pix_width / crop['w']


def test_leiden_full_canvas_dimensions_scale_preview_geometry():
    # Image API reports 3924x2704 but a cached derivative is only 490px wide.
    page = {'id': 'L-008', 'alto_width': 3924, 'alto_height': 2704,
            'image': {'type': 'file', 'path': 'iiif/local/L/preview.jpg',
                      'width': 3924, 'height': 2704}}
    crop = image_scene_reference_crop(page, 490, 338)
    assert crop == {'x': 0.0, 'y': 0.0, 'w': 3924.0, 'h': 2704.0}
    assert isclose(_line_x_on_display(page, 490, 3000), 490 * 3000 / 3924)
    assert _line_x_on_display(page, 490, 3900) < 490


def test_unscaled_old_default_was_wrong_for_low_resolution_bitmap():
    page = {'id': 'L', 'image': {'type': 'iiif', 'width': 3924, 'height': 2704,
                              'image': 'https://server.test/thumb.jpg'}}
    # Old view used {'w':pix.width()} for full pages: a line at x=3200
    # appeared OUTSIDE a 490px bitmap and polluted scene.itemsBoundingRect().
    crop = image_scene_reference_crop(page, 490, 338)
    assert 3200 * 490 / crop['w'] < 490
    assert crop['w'] != 490


def test_cropped_geometry_preserves_region_basis():
    page = {'image': {'type': 'iiif', 'width': 3924, 'height': 2704}}
    region = {'x': 500, 'y': 700, 'w': 600, 'h': 200}
    assert image_scene_reference_crop(page, 300, 100, region) is region
    assert (650 - region['x']) * 300 / region['w'] == 75


def test_full_page_prefers_high_resolution_image_api_service():
    page = {'image': {'type': 'iiif', 'width': 3924, 'height': 2704,
                      'service': 'https://example.test/iiif/2/abc',
                      'image': 'https://example.test/thumb/abc.jpg', 'iiif_version': 2}}
    req = page_image_request(page, None)
    assert req['url'] == 'https://example.test/iiif/2/abc/full/full/0/default.jpg'
    assert req['fallback_url'] == 'https://example.test/thumb/abc.jpg'
    assert not req['local_crop'] and not req['fallback_local_crop']


def test_image_api3_uses_max_and_direct_url_only_still_works():
    page = {'image': {'type': 'iiif', 'service': 'https://server.test/iiif3',
                      'image': 'https://server.test/small', 'iiif_version': 3}}
    req = page_image_request(page, None)
    assert req['url'].endswith('/full/max/0/default.jpg')
    assert page_image_request({'image': {'type': 'iiif', 'image': 'https://server.test/img'}}, None)['url'] == 'https://server.test/img'


def test_link_count_not_inferred_from_ocr_geometry():
    # The project may contain a fully segmented IIIF spread but no line links.
    cache = {'pages': [{'id': 'L', 'lines': [
        {'alto_id': 'line1', 'bbox': {'hpos': 12, 'vpos': 13, 'width': 10, 'height': 10}},
        {'alto_id': 'line2', 'base_keys': [], 'bbox': {'hpos': 30, 'vpos': 40, 'width': 10, 'height': 10}}
    ]}]}
    assert secondary_sync_link_count(cache) == 0
    cache['pages'][0]['lines'][1]['base_keys'] = ['mu-page::6']
    assert secondary_sync_link_count(cache) == 1


def test_seven_locales_include_line_sync_diagnostics():
    for lang in ('fr', 'en', 'de', 'ja', 'cs', 'it', 'ru'):
        xml = ET.parse(ROOT / 'i18n' / f'{lang}.xml').getroot()
        keys = {s.attrib.get('key') for s in xml.findall('string')}
        assert {'manuscript.sync.no_base_keys', 'manuscript.sync.unmatched_base_keys'} <= keys


def test_ui_scales_full_page_frames_and_explains_fallback():
    ui = application_source()
    assert 'image_scene_reference_crop(' in ui
    assert "_t('manuscript.sync.no_base_keys')" in ui
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in ui
