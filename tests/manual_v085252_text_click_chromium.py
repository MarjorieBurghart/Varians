"""Real Chromium HTML behavior: text, annotation, editorial ref, non-linked text.

Synthetic data only. No assertions about real manuscript images/IIIF endpoints.
"""
import base64
import importlib.util
import io
from pathlib import Path
import shutil
import sys
import tempfile

from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('fixture_v085251',ROOT/'tests'/'test_v08526_web_page_anchor_resolution.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from web_viewer.generator import build_dataset,make_html

with tempfile.TemporaryDirectory() as td:
    root=Path(td)
    facs='<facsimile><surface xml:id="Mu-p0008"><zone xml:id="Mu-p0008-left" ulx="0" uly="0" lrx="600" lry="2000"/></surface></facsimile>'
    cfg=fixture.create_project(root,
         '<pb n="f002v" edRef="#Mu" facs="#Mu-p0008-left"/>'
         '<lb edRef="#Mu"/>alpha <ref>editorial</ref>'
         '<lb edRef="#Mu"/>beta<note>explanation</note>',facsimile=facs)
    data,_=build_dataset(cfg)
    assert data['meta']['line_sync']
    img=Image.new('RGB',(1200,2000),'#d2cdc6')
    buf=io.BytesIO();img.save(buf,format='JPEG')
    data_url='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
    for witness in data['witnesses']:
        for p in witness['pages']:
            if p.get('image',{}).get('type')=='file':p['image']['path']=data_url
    html=make_html(data)
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1500,'height':900})
        errors=[]
        page.on('pageerror',lambda err:errors.append(str(err)))
        page.set_content(html,wait_until='load')
        page.wait_for_function('document.querySelectorAll(".card .stage img").length === 2')
        # A real manuscript-line fragment changes both witnesses' statuses.
        page.locator('.line-frag[data-line="physical-A::2"]').first.click()
        assert page.evaluate('selectedKey')=='physical-A::2'
        assert all('l. 2' in x for x in page.locator('[data-role=status]').all_inner_texts())
        # Current line is visibly identified even when other frames are hidden.
        assert page.locator('.hl.current-box, .hl-poly.current-poly').count()==2
        # A note marker repositions both witnesses BEFORE opening a popover.
        page.locator('.line-frag[data-line="physical-A::1"]').first.click()
        page.locator('.ann-marker.n[data-line="physical-A::2"]').first.click()
        assert page.evaluate('selectedKey')=='physical-A::2'
        assert all('l. 2' in x for x in page.locator('[data-role=status]').all_inner_texts())
        assert page.locator('#popover.show').count()==1
        # Clicking an editorial ref keeps the line association (as legacy viewer did).
        page.locator('.editorial-ref[data-line="physical-A::1"]').first.click()
        assert page.evaluate('selectedKey')=='physical-A::1'
        assert all('l. 1' in x for x in page.locator('[data-role=status]').all_inner_texts())
        # No invented line for stale keys, warn without changing current selection.
        page.locator('.line-frag[data-line="physical-A::1"]').first.evaluate("e=>e.dataset.line='physical-A::404'")
        page.locator('.line-frag[data-line="physical-A::404"]').first.click()
        assert page.evaluate('selectedKey')=='physical-A::1'
        assert 'physical-A::404' in page.locator('#syncNotice').inner_text()
        assert not errors,errors
        browser.close()
print('Chromium text click synchronization and diagnostics: OK')
