import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from web_viewer.generator import make_html
from playwright.sync_api import sync_playwright
sample={
 'meta':{'title':'Test','has_images':False,'line_sync':True,'base_witness':'Mu', 'lines':1,'variants':0,'pivot_lb_index':{'count_match':True},'external_iiif_images':0},
 'witnesses':[{'id':'Mu','label':'Mu','role':'base','line_sync':True,'folios':[], 'pages':[{'id':'p','tei_surface_id':None, 'lines':[{'line':1,'bbox':{'hpos':3,'vpos':3,'width':20,'height':6}}],'image':{'type':'none'}}]}],
 'document':{'annotations':{},'blocks':[{'type':'p','segments':[{'kind':'text','text':'ser','line_key':'p::1','styles':[]},{'kind':'text','text':'uus iusticia gracia','line_key':'p::1','styles':[]}]}]},
 'i18n':{'default':'fr','fallback':'fr','catalogs':{'fr':{'viewer.search.count':'{count} résultat(s)','viewer.search.medieval':'Graphies médiévales'}},'languages':[{'code':'fr','label':'Français'}]}}
html=make_html(sample)
print('html-size',len(html))
with sync_playwright() as pw:
 b=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox','--disable-gpu'])
 page=b.new_page()
 errs=[];page.on('pageerror',lambda e:errs.append(str(e)))
 page.set_content(html,wait_until='domcontentloaded',timeout=30000)
 print('loaded',page.locator('.line-frag').count())
 page.locator('#search').fill('servvs')
 page.wait_for_timeout(350)
 exact=page.locator('#searchSummary').inner_text()
 page.locator('#searchMedieval').check()
 page.wait_for_timeout(250)
 med=page.locator('#searchSummary').inner_text()
 marks=page.locator('.search-hit').count()
 print('counts',exact,med,marks)
 assert '0 ' in exact and '1 ' in med and marks==2
 page.locator('#searchResults .search-result').first.click()
 assert page.locator('.search-hit.active-hit').count()==2
 assert page.locator('.selected-line').count()>0
 print('success browser',errs)
 assert not errs
 b.close()
