"""Chromium smoke test for V0.8.5.26.1 (standalone, synthetic no network)."""
from web_viewer.generator import make_html
from playwright.sync_api import sync_playwright


def witness(wid, role, n, links=None):
    line = {"line": n, "bbox": [2, 2, 12, 10], "order": n}
    if links is not None:
        line["base_keys"] = links
    return {"id": wid, "label": wid, "role": role, "line_sync": True,
            "folios": [], "meta": {}, "pages": [{"id": wid+"-p1", "image": {"type": "none"},
            "alto_width": 40,"alto_height": 30,"lines": [line]}]}


def main():
    k = 'Mu-p1::1'
    data = {"meta": {"title": "Smoke 085261", "base_witness": "Mu", "display_witnesses": ["F", "A"],
            "has_images": True, "line_sync": True, "lines": 1, "variants": 0,
            "pages": 1, "external_iiif_images": 0,"pivot_lb_index": {"count_match":True}},
            "witnesses": [witness("F", "secondary", 2, [k]), witness("A", "secondary", 3, [k]), witness("Mu", "base", 1)],
            "document": {"blocks": [{"type": "p", "segments": [{"kind": "text", "text": "seruus iusticia gracia", "line_key": k}]}]},
            "i18n": {"default":"en", "fallback":"en", "languages":[{"code":"en","label":"English"}],
                     "catalogs":{"en":{"viewer.search.medieval":"Medieval spellings", "viewer.search.count":"{count} results", "viewer.stats":"{witnesses} witnesses"}}}}
    html=make_html(data)
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True,executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        page=browser.new_page()
        errors=[]
        page.on('pageerror', lambda err: errors.append(str(err)))
        page.set_content(html,wait_until='load',timeout=25000)
        assert page.locator('.card').count()==2
        assert page.locator('.card').first.get_attribute('data-w')=='F'
        assert page.locator('.card').last.get_attribute('data-w')=='A'
        assert page.locator('#searchMedieval').count()==0
        assert page.locator('#searchModeLabel').inner_text()=='Medieval spellings'
        assert not page.locator('#searchUV').is_checked()
        page.locator('#search').fill('servvs')
        page.locator('#searchButton').click()
        assert page.locator('.search-hit').count()==0
        page.locator('#searchUV').check()
        page.locator('#searchButton').click()
        assert page.locator('.search-hit').count()==1
        page.locator('#searchNext').click()
        assert page.evaluate('selectedKey')==k
        assert page.locator('[data-w="Mu"]').count()==0
        assert not errors, errors
        browser.close()
    print('Chromium 0.8.5.26.1: OK, 2 visible cards in F/A order, pivot hidden, medieval search with UV check only, text key selected')

if __name__=='__main__': main()
