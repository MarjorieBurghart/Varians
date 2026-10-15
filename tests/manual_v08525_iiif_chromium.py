"""Opt-in offline Chromium QA for IIIF image errors and stale image DOM.

Run ``python tests/manual_v08525_iiif_chromium.py``. Only synthetic images;
all IIIF requests are intercepted (no institution contacted).
"""
from pathlib import Path
import io
import shutil
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from web_viewer.generator import make_html

image=Image.new('RGB',(1000,600),'#eeeedc')
ImageDraw.Draw(image).rectangle((500,0,999,599),fill='#aac6dd')
buf=io.BytesIO();image.save(buf,format='JPEG');jpg=buf.getvalue()

pages=[]
for i in (1,2):
    pages.append({'id':f'p{i}','tei_surface_id':f'surf{i}','alto_width':1000,'alto_height':600,
                  'image':{'type':'iiif','service':f'https://synthetic.iiif.invalid/{i}',
                           'iiif_version':2 if i==1 else 3,'image':f'https://synthetic.iiif.invalid/preview{i}.jpg',
                           'width':1000,'height':600},
                  'lines':[{'line':1,'polygon':[[620,220],[840,210],[760,320],[610,290]]}]})
data={'meta':{'title':'Browser IIIF 0.8.5.25','base_witness':'Mu','has_images':True,
               'line_sync':False,'lines':0,'notes':0,'variants':0,'external_iiif_images':2},
      'document':{'blocks':[{'type':'p','segments':[{'kind':'pb','facs':'#zone-right','page':'right','edref':'#Mu','label':'right'}]}]},
      'witnesses':[{'id':'Mu','label':'Mu','role':'base','line_sync':False,'pages':pages,
                    'folios':[{'ref':'zone-right','surface':'surf1','label':'right','region':[500,0,500,600]},
                              {'ref':'surf1','surface':'surf1','label':'spread','region':None},
                              {'ref':'surf2','surface':'surf2','label':'next','region':None}]}],
      'i18n':{'default':'en','fallback':'en','languages':[{'code':'en','label':'English'}],
              'catalogs':{'en':{'viewer.image_unavailable':'Image unavailable','viewer.external_iiif_notice':'Remote images: {count}'}}}}
html=make_html(data)
requested=[]
with sync_playwright() as pw:
    executable=shutil.which('chromium') or shutil.which('google-chrome')
    browser=pw.chromium.launch(executable_path=executable,headless=True,args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1440,'height':900})
    errors=[]
    page.on('pageerror',lambda exc:errors.append(str(exc)))
    def images(route):
        url=route.request.url
        requested.append(url)
        if '/info.json' in url:
            route.fulfill(status=403,body='{}',headers={'Content-Type':'application/json'})
        elif '/1/' in url and '/500,0,500,600/' in url:
            status=429 if len([x for x in requested if '/1/500,0,500,600/' in x])==1 else 403
            route.fulfill(status=status,body=b'',headers={'Content-Type':'image/jpeg'})
        elif '/1/' in url and '/full/' in url:
            route.fulfill(status=200,body=jpg,headers={'Content-Type':'image/jpeg'})
        elif '/2/' in url:
            tries=len([x for x in requested if '/2/' in x and '/info.json' not in x])
            code=404 if tries==1 else (500 if tries==2 else 200)
            route.fulfill(status=code,body=jpg if code==200 else b'',headers={'Content-Type':'image/jpeg'})
        elif url.endswith('/preview2.jpg'):
            route.fulfill(status=200,body=jpg,headers={'Content-Type':'image/jpeg'})
        else:
            route.fulfill(status=404,body=b'')
    page.route('https://synthetic.iiif.invalid/**',images)
    page.set_content(html,wait_until='domcontentloaded')
    page.wait_for_function("document.querySelector('.stage img')?.dataset.iiifQuality === 'full-reduced'",timeout=15000)
    state=page.evaluate('''() => {const img=document.querySelector('.stage img');return {
        quality:img.dataset.iiifQuality,natural:img.naturalWidth,
        crop:img.dataset.crop,position:getComputedStyle(img).position,
        fullWidth:img.dataset.fullWidth, svg:document.querySelector('.stage svg')?.getAttribute('viewBox')};}''')
    assert state['natural']>0 and state['quality']=='full-reduced',state
    assert state['crop']=='500,0,500,600' and state['position']=='absolute',state
    assert state['svg']=='500 0 500 600',state
    assert len([u for u in requested if '/1/500,0,500,600/' in u])>=2,requested
    page.locator('[data-folio]').select_option('surf2')
    page.wait_for_function("document.querySelector('.stage img')?.naturalWidth > 0 && document.querySelector('.stage img')?.src.includes('preview2.jpg')",timeout=15000)
    assert page.locator('.stage img').get_attribute('data-iiif-quality')=='preview'
    assert page.locator('.stage img').count()==1
    assert len([u for u in requested if '/2/' in u and '/info.json' not in u])==2 and any('preview2.jpg' in u for u in requested),requested
    assert not errors,errors
    # A disconnected/stale image must not replace the new selection on an
    # obsolete failure; rendering the new page actively cancels previous plans.
    current=page.locator('.stage img').get_attribute('src')
    page.wait_for_timeout(100)
    assert page.locator('.stage img').get_attribute('src')==current
    offline=browser.new_page(viewport={'width':1440,'height':900})
    offline_errors=[]
    offline.on('pageerror',lambda exc:offline_errors.append(str(exc)))
    offline.route('https://synthetic.iiif.invalid/**', lambda route:route.abort())
    offline.set_content(html,wait_until='domcontentloaded')
    offline.wait_for_selector('.iiif-failure',timeout=15000)
    assert 'Image unavailable' in offline.locator('.iiif-failure').first.inner_text()
    assert not offline_errors, offline_errors
    browser.close()
print('PASS chromium IIIF: 429/403/404/500, regional fallback, offline and image switch, no JavaScript errors',len(requested),'network requests')
