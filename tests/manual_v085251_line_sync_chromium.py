"""Offline Chromium proof: folio/zone TEI points to alignment page with another ID.

This is a manual integration test, using generated HTML, real JS and a rendered
local bitmap. It does not require the user's manuscripts or an IIIF server.
"""
from pathlib import Path
import base64
import importlib.util
import io
import shutil
import tempfile
import sys
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('fixture_v085251', ROOT / 'tests' / 'test_v08526_web_page_anchor_resolution.py')
fixture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from web_viewer.generator import build_dataset, make_html

with tempfile.TemporaryDirectory() as td:
    root = Path(td)
    facs = ('<facsimile><surface xml:id="Mu-p0008">'
            '<zone xml:id="Mu-p0008-left" ulx="0" uly="0" lrx="600" lry="2000"/>'
            '</surface></facsimile>')
    cfg = fixture.create_project(
        root, '<pb n="f002v" edRef="#Mu" facs="#Mu-p0008-left"/>'
              '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta', facsimile=facs)
    data, _ = build_dataset(cfg)
    assert data['meta']['line_sync']
    rgb = Image.new('RGB', (1200, 2000), '#eee6d8')
    buffer = io.BytesIO()
    rgb.save(buffer, format='JPEG')
    image_url = 'data:image/jpeg;base64,' + base64.b64encode(buffer.getvalue()).decode('ascii')
    for witness in data['witnesses']:
        for page in witness['pages']:
            if page.get('image', {}).get('type') == 'file':
                page['image']['path'] = image_url
    html = make_html(data)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=shutil.which('chromium'), headless=True,
                                      args=['--no-sandbox', '--disable-dev-shm-usage'])
        page = browser.new_page(viewport={'width': 1500, 'height': 900})
        errors = []
        page.on('pageerror', lambda e: errors.append(str(e)))
        page.set_content(html, wait_until='load')
        page.wait_for_function('document.querySelectorAll(".card .stage img").length === 2')
        results = page.evaluate('''() => [...document.querySelectorAll('.card')].map(card => {
          const img = card.querySelector('.stage img');
          return {id:card.dataset.w,status:card.querySelector('[data-role=status]').textContent,
                  crop:img?.dataset.crop,full:img?.dataset.fullWidth,
                  imageQuality:img?.dataset.iiifQuality};})''')
        print('Initial:', results)
        assert [x['crop'] for x in results] == ['176,276,448,158', '196,456,398,148'], results
        assert all(x['full'] == '1200' for x in results), results
        page.locator('.line-frag[data-line="physical-A::2"]').first.click()
        results2 = page.evaluate('''() => [...document.querySelectorAll('.card')].map(card =>
           ({id:card.dataset.w, crop:card.querySelector('.stage img')?.dataset.crop}))''')
        print('After click:', results2)
        # Two adjacent lines remain in one shared contextual crop, but the
        # selected TEI line and both witness status labels MUST advance.
        statuses = page.locator('[data-role="status"]').all_inner_texts()
        assert all('l. 2' in s for s in statuses), statuses
        assert results2[0]['crop'] == results[0]['crop']
        assert results2[1]['crop'] == results[1]['crop']
        assert not errors, errors
        browser.close()
print('Chromium web synchronisation: OK')
