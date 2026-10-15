"""Optional real-browser QA for Varians V0.8.5.24.

Development-only dependencies: Pillow and playwright; Chromium binary.
Run: python tests/manual_v08524_chromium.py
The offline fixture uses an inline data URL because some sandboxes block file://.
No user manuscripts or remote IIIF servers are contacted.
"""
from pathlib import Path
import base64
import tempfile
import sys
from PIL import Image, ImageDraw
from playwright.sync_api import sync_playwright
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
from web_viewer.generator import make_html
out=Path(tempfile.mkdtemp(prefix='varians-v08524-browser-'))
out.mkdir(parents=True,exist_ok=True)
im=Image.new('RGB',(490,338),'#e3e3e3');d=ImageDraw.Draw(im)
d.rectangle((0,0,244,338),fill='#9dc1df');d.rectangle((245,0,489,337),fill='#d9b28c')
d.line((245,0,245,338),fill='red',width=2)
im.save(out/'spread.png')
page={'id':'Mu008','label':'008 - f002v-003r','tei_surface_id':'Mu-p0008',
      'alto_width':1962,'alto_height':1352,
      'image':{'type':'file','path':'spread.png','width':3924,'height':2704},
      'lines':[{'line':1,'alto_id':'line-R','polygon':[[1100,700],[1400,680],[1360,770],[1250,750],[1120,790],[1080,725]],
                'bbox':{'hpos':1100,'vpos':700,'width':275,'height':65}}]}
data={'meta':{'title':'Varians geometric QA','base_witness':'Mu','has_images':True,'line_sync':False,'lines':0,'variants':0,'notes':0},
      'document':{'blocks':[{'type':'p','segments':[{'kind':'pb','facs':'#Mu-p0008-right','page':'f003r','edref':'#Mu','label':'f003r'}]}]},
      'witnesses':[{'id':'Mu','label':'Mu', 'role':'base','line_sync':False,'pages':[page],
                    'folios':[{'ref':'Mu-p0008','surface':'Mu-p0008','label':'f002v-003r','region':None},
                              {'ref':'Mu-p0008-left','surface':'Mu-p0008','label':'f002v','region':[0,0,1962,2704]},
                              {'ref':'Mu-p0008-right','surface':'Mu-p0008','label':'f003r','region':[1962,0,1962,2704]}]}],
      'i18n':{'default':'fr','fallback':'fr','languages':[{'code':'fr','label':'Français'}],'catalogs':{'fr':{}}}}
page['image']['path']='data:image/png;base64,'+base64.b64encode((out/'spread.png').read_bytes()).decode('ascii')
(out/'viewer.html').write_text(make_html(data),encoding='utf8')
with sync_playwright() as pw:
    browser=pw.chromium.launch(executable_path=__import__('shutil').which('chromium') or __import__('shutil').which('google-chrome'), headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
    page=browser.new_page(viewport={'width':1440,'height':900},device_scale_factor=1)
    errors=[]
    page.on('pageerror',lambda error:errors.append(str(error)))
    page.set_content((out/'viewer.html').read_text(encoding='utf8'),wait_until='load')
    page.locator('[data-act="frames"]').click(timeout=2000)
    info=page.evaluate('''() => {let stage=document.querySelector('.stage');let image=stage.querySelector('img');let svg=stage.querySelector('svg');return {html:stage.innerHTML.slice(0,1800), imageNatural:[image.naturalWidth,image.naturalHeight],imgWidth:getComputedStyle(image).width,crop:image.dataset.crop,viewBox:svg?.getAttribute('viewBox'),poly:svg?.querySelector('polygon')?.getAttribute('points'),errors:[]};}''')
    print('RIGHT', {k:v for k,v in info.items() if k!='html'})
    assert info['imageNatural']==[490,338]
    assert info['crop']=='1962,0,1962,2704'
    assert info['viewBox']=='1962 0 1962 2704'
    assert info['poly'].split(' ')[0]=='2200,1400'
    page.screenshot(path=str(out/'v08524-right-crop.png'))
    page.locator('[data-folio]').select_option('Mu-p0008-left')
    left=page.evaluate('''() => {const im=document.querySelector('.stage img');return {crop:im.dataset.crop,full:im.dataset.fullWidth,viewBox:document.querySelector('.stage svg')?.getAttribute('viewBox')}}''')
    print('LEFT',left)
    assert left['crop']=='0,0,1962,2704'
    assert left['viewBox']=='0 0 1962 2704'
    page.screenshot(path=str(out/'v08524-left-crop.png'))
    assert not errors, errors
    browser.close()
print('Browser Chromium: OK, screenshots:',out)
