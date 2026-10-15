"""Chromium integration: physically distinct pages and ordinal TEI lb -> base_keys."""
from __future__ import annotations
import base64
import importlib.util
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('fixture_v085253',ROOT/'tests'/'test_v08526_web_page_anchor_resolution.py')
fixture=importlib.util.module_from_spec(spec)
spec.loader.exec_module(fixture)
from web_viewer.generator import build_dataset,make_html

with tempfile.TemporaryDirectory() as td:
    cfg=fixture.create_project(Path(td),
        '<pb n="f. 12r" edRef="#Mu" facs="#unresolvable"/>'
        '<lb edRef="#Mu"/>alpha'
        '<pb edRef="#F" n="f. 21v" facs="#F-p0003"/>'
        '<lb edRef="#Mu"/>beta'
        '<pb n="f. 12v" edRef="#Mu"/>'
        '<lb edRef="#Mu"/>gamma')
    bbox={'hpos':150,'vpos':270,'width':650,'height':75}
    (Path(td)/'Mu.json').write_text(json.dumps({'meta':{'witness':'Mu','role':'base'},
        'pages':[{'id':'src-page-A','lines':[{'line':7,'bbox':bbox},{'line':11,'bbox':dict(bbox,vpos=550)}]},
                 {'id':'src-page-B','lines':[{'line':2,'bbox':dict(bbox,vpos=400)}]}]}))
    (Path(td)/'F.json').write_text(json.dumps({'meta':{'witness':'F','role':'secondary'},
        'pages':[{'id':'src-page-F','lines':[
            {'line':1,'order':1,'base_keys':['src-page-A::7'],'bbox':bbox},
            {'line':2,'order':2,'base_keys':['src-page-A::11'],'bbox':dict(bbox,vpos=550)},
            {'line':3,'order':3,'base_keys':['src-page-B::2'],'bbox':dict(bbox,vpos=800)}]}]}))
    data,_=build_dataset(cfg)
    assert data['meta']['pivot_lb_index']['count_match']
    im=Image.new('RGB',(1200,1500),'#c5c3bb')
    buf=io.BytesIO();im.save(buf,format='JPEG')
    uri='data:image/jpeg;base64,'+base64.b64encode(buf.getvalue()).decode()
    for witness in data['witnesses']:
        for p in witness['pages']:
            p['image']={'type':'file','path':uri,'width':1200,'height':1500,'label':p['id']}
            p['alto_width']=1200;p['alto_height']=1500
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=shutil.which('chromium'),headless=True,
                                   args=['--no-sandbox','--disable-dev-shm-usage'])
        page=browser.new_page(viewport={'width':1500,'height':900})
        errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
        page.set_content(make_html(data),wait_until='load')
        page.wait_for_function('document.querySelectorAll(".stage img").length===2')
        for key,position in [('src-page-A::7',0),('src-page-A::11',1),('src-page-B::2',2)]:
            page.locator('.line-frag[data-line="'+key+'"]').first.click()
            assert page.evaluate('selectedKey')==key
            state=page.evaluate('''() => {
                const a=states.get('Mu'), b=states.get('F');
                return {a:a.center,b:b.center,base:a.physical[a.center].p.id,
                        refs:[...b.byBase.get(selectedKey)||[]]}
            }''')
            assert state['a']==position,state
            assert state['b']==position,state
            assert state['refs']==[position],state
            assert len(page.locator('.current-box, .current-poly').all()) >= 1
        assert not errs,errs
        browser.close()
print('Chromium 3 physical lines, multi-page and 2 manuscripts: PASS')
