"""V0.8.5.26 — invariants des fonctions A01, A02, A03 (hors GUI native)."""
from pathlib import Path
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
import pytest

ROOT=Path(__file__).resolve().parents[1]


def test_attribute_context_and_rng_names(tmp_path):
    from test_rng_completion import _schema
    from rng_completion import load_completion_model, analyze_xml_context
    model=load_completion_model(_schema(tmp_path))
    for source, name in [('<rdg wi', 'wit'), ('<p xml:', 'xml:id'), ('<hi re', 'rend')]:
        ctx=analyze_xml_context(source,len(source))
        assert ctx.kind=='attribute'
        assert ctx.current_element==source[1:].split()[0]
        assert name in model.allowed_attributes(ctx.current_element)
        assert name.casefold().startswith(ctx.prefix.casefold())
    value=analyze_xml_context('<rdg wit="t" re',len('<rdg wit="t" re'))
    assert value.kind=='attribute' and 'wit' in value.existing_attributes
    quoted=analyze_xml_context('<rdg wit="t',len('<rdg wit="t'))
    assert quoted.kind=='attribute_value'


def test_schema_refresh_is_debounced_and_has_document_revision_guard():
    s=(ROOT/'editeur_tei.py').read_text(encoding='utf8')
    assert 'self.rng_refresh_timer.setInterval(1250)' in s
    assert 'self.rng_refresh_timer.timeout.connect(self._auto_refresh_rng)' in s
    assert "self._rng_watch_enabled and hasattr(self, 'rng_refresh_timer')" in s
    assert "self.editor.document().contentsChanged.connect(self._text_changed)" in s
    assert 'self.validate_relaxng_document(show_panel=False, automatic=True' in s
    assert 'self._clear_validation_table()' in s
    assert 'if not automatic:' in s
    assert 'self._auto_attribute_choices' in s
    assert 'self._accept_attribute_completion' in s


def test_fulltext_normalization_and_positions():
    node=shutil.which('node')
    if not node:pytest.skip('Node.js unavailable')
    module=json.dumps(str(ROOT/'web_viewer'/'fulltext_search.js'))
    js=f'''const s=require({module});
const blocks=[{{type:'p',segments:[{{kind:'text',text:'ser',line_key:'A::1'}},{{kind:'text',text:'uus iustitia gracia',line_key:'A::2'}}]}}];
const idx=s.makeIndex(blocks);
const opts={{medieval:true,uv:true,ij:true,ct:true}};
const hits=s.find(idx,'servvs',opts);
if(hits.length!==1||hits[0].pieces.length!==2||hits[0].lineKey!=='A::1')throw Error('split segment search');
if(s.find(idx,'servvs',{{medieval:false}}).length)throw Error('exact should not match');
if(s.find(idx,'justitia',opts).length!==1)throw Error('i/j mismatch');
if(s.find(idx,'gratia',opts).length!==1)throw Error('c/t mismatch');
if(s.find(idx,'gratia',{{...opts,ct:false}}).length!==0)throw Error('c/t option ignored');
let one=s.splitText('ser',0,hits,x=>x);let two=s.splitText('uus iustitia gracia',1,hits,x=>x);
if(!one.includes('search-hit')||!two.includes('search-hit'))throw Error('mark positions');
let emoji=s.find(s.makeIndex([{{type:'p',segments:[{{kind:'text',text:'🌿 servus'}}]}}]),'servus',{{medieval:true,uv:true}});
if(emoji.length!==1||emoji[0].pieces[0].start!==3)throw Error('utf16 offset');
'''
    run=subprocess.run([node,'-e',js],capture_output=True,text=True,timeout=15)
    assert run.returncode==0,run.stderr


def test_export_preserves_lb_links_and_bundles_search_module(tmp_path):
    from web_viewer.generator import make_html
    sample={'meta':{'title':'Démo','has_images':False,'line_sync':True,
                    'base_witness':'Mu','pivot_lb_index':{'count_match':True}},
            'witnesses':[],'document':{'blocks':[{'type':'p','segments':[
                    {'kind':'text','text':'seruus','line_key':'p::1'}]}]},
            'i18n':{'default':'fr','fallback':'en','catalogs':{'fr':{}},'languages':[]}}
    html=make_html(sample)
    assert 'VariansFullText' in html and 'id="searchModeLabel"' in html
    assert 'id="searchMedieval"' not in html
    assert 'medieval:uv||ij||ct' in html
    assert 'searchHits' in html and 'selectLine(hit.lineKey,false)' in html
    assert 'baseId=DATA.meta.base_witness' in html
    assert 'pivot_lb_index' in html


def test_languages_and_help_maintained():
    keys=None
    for lang in ('fr','en','de','ja','cs','it','ru'):
        strings=ET.parse(ROOT/'i18n'/f'{lang}.xml').getroot().findall('string')
        mapping={x.get('key'):x.text for x in strings}
        assert len(strings)==len(mapping)==629
        assert all(mapping.get('viewer.search.'+k) for k in ('medieval','run','close','count'))
        assert '{count}' in mapping['viewer.search.count']
        page=(ROOT/'help'/f'{lang}.html').read_text(encoding='utf8')
        assert 'id="interim-08526"' in page
