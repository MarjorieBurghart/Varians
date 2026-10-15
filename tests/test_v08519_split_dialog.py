"""V0.8.5.19: 'Double page…' must work in page and synchronized-line modes.

Qt is unavailable in the CI environment. Extract and execute the REAL GUI
callbacks with small PySide6-compatible stubs so click -> handler -> edit can
be regression-tested, not only checked by source-string presence.
"""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import xml.etree.ElementTree as ET

import pytest
from varians_source import application_source, application_ast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from folio_navigation import split_surface_into_folios, inspect_surface_part_split, configure_surface_parts
from image_sources import page_image_dimensions

SRC = application_source()
ROOT_AST = application_ast()


def ui_method(cls, name, namespace):
    obj = next(c for c in ROOT_AST.body if isinstance(c,ast.ClassDef) and c.name==cls)
    fun = next(n for n in obj.body if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==name)
    fn = ast.FunctionDef(name=fun.name, args=fun.args, body=fun.body,
                         decorator_list=[], returns=fun.returns, type_comment=None)
    context = dict(namespace)
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])), '<GUI callback>', 'exec'),context)
    return context[name]


class SignalLog:
    def __init__(self): self.calls=[]
    def emit(self,*args): self.calls.append(args)


class Button:
    def __init__(self): self.enabled=None
    def setEnabled(self,value): self.enabled=bool(value)


@pytest.mark.parametrize('sync_enabled',[False,True])
def test_click_dispatches_even_when_witness_has_line_synchronization(sync_enabled):
    fn=ui_method('ManuscriptPanel','_request_split_folio',{})
    panel=SimpleNamespace(siglum='L',sync_enabled=sync_enabled,
       splitFolioRequested=SignalLog(),current_item=lambda:{'p':{'tei_surface_id':'L-p0008'}})
    fn(panel)
    assert panel.splitFolioRequested.calls==[('L','L-p0008')]


def test_missing_surface_id_is_dispatched_instead_of_silently_ignored():
    fn=ui_method('ManuscriptPanel','_request_split_folio',{})
    panel=SimpleNamespace(siglum='L',sync_enabled=True,
       splitFolioRequested=SignalLog(),current_item=lambda:{'p':{}})
    fn(panel)
    assert panel.splitFolioRequested.calls==[('L','')]


@pytest.mark.parametrize('sync_enabled',[True,False])
def test_button_is_not_disabled_by_line_mode(sync_enabled):
    fn=ui_method('ManuscriptPanel','_update_mark_page_button',{})
    panel=SimpleNamespace(sync_enabled=sync_enabled,current_item=lambda:{'p':{'tei_surface_id':'L-p0008'}},
                          mark_page_btn=Button(),split_folio_btn=Button())
    fn(panel)
    assert panel.split_folio_btn.enabled and panel.mark_page_btn.enabled


class Widget:
    instances=[]
    def __init__(self,*args,**kwargs):self.instances.append(self)
    def __getattr__(self,_):return lambda *a,**kw:None


class Dialog(Widget):
    class DialogCode:
        Accepted=1
    def exec(self):return self.DialogCode.Accepted
    def accept(self):return None
    def reject(self):return None


class Input(Widget):
    _idx=0
    def __init__(self,*args,**kw):super().__init__(*args,**kw);self.idx=Input._idx;Input._idx+=1
    def text(self):return ('f002v','f003r')[self.idx%2]


class Spin(Widget):
    def value(self):return 50
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.valueChanged=Hook()


class Hook:
    def connect(self,fn):self.fn=fn


class DialogButtons(Widget):
    class StandardButton:
        Ok=1
        Cancel=2
    def __init__(self,*a,**kw):super().__init__(*a,**kw);self.accepted=Hook();self.rejected=Hook()


class Preview(Widget):
    def __init__(self,*a,**kw):
        super().__init__(*a,**kw)
        self.splitChanged=Hook()
        self.split_px=1962

class Messages:
    warnings=[];infos=[]
    @classmethod
    def warning(cls,*args):cls.warnings.append(args)
    @classmethod
    def information(cls,*args):cls.infos.append(args)


XML='''<TEI xmlns="http://www.tei-c.org/ns/1.0"><facsimile>
 <surface xml:id="L-p0008" n="008 - f002v-003r"><graphic url="spread.jpg"/></surface>
</facsimile><text><body><p>texte</p></body></text></TEI>'''


def make_context(xml=XML, sync=True, sid='L-p0008', page_id='L-p0008'):
    Messages.warnings=[];Messages.infos=[];Input._idx=0
    edits=[]; folio_moves=[]; refreshed=[]
    img={'tei_surface_id':page_id,'alto_width':3924,'alto_height':2704}
    panel=SimpleNamespace(items=[{'p':img}],sync_enabled=sync,
              set_folio=lambda ref:folio_moves.append(ref))
    obj=SimpleNamespace(panels={'L':panel}, project=SimpleNamespace(root_dir=ROOT),
                        editor=SimpleNamespace(toPlainText=lambda:xml),
                        _replace_editor_text_minimally=lambda old,new:edits.append(new),
                        _refresh_folio_navigation=lambda new,force=False:refreshed.append((new,force)),
                        _last_synced_surface=('original',))
    ns={'QMessageBox':Messages,'_t':lambda key,**kw:key.format(**kw),
        'ET':ET,'page_image_dimensions':page_image_dimensions,
        'QDialog':Dialog,'QVBoxLayout':Widget,'QLabel':Widget,
        'QFormLayout':Widget,'QLineEdit':Input,'QSpinBox':Spin,'QDoubleSpinBox':Spin,
        'SplitImagePreview':Preview,'load_split_thumbnail':lambda *a,**kw:None,
        'QDialogButtonBox':DialogButtons,
        'split_surface_into_folios':split_surface_into_folios,
        'inspect_surface_part_split':inspect_surface_part_split,
        'configure_surface_parts':configure_surface_parts}
    return ui_method('MainWindow','_split_double_folio',ns),obj,edits,folio_moves,refreshed


def test_synced_witness_dialog_opens_edits_tei_without_changing_line_focus():
    method,host,edits,moves,refreshed=make_context(sync=True)
    method(host,'L','L-p0008')
    assert len(edits)==1 and 'xml:id="L-p0008-left"' in edits[0]
    assert '<zone xml:id="L-p0008-right"' in edits[0]
    assert XML.count('<graphic')==edits[0].count('<graphic')==1
    assert moves==[]
    assert refreshed[0][1] is True
    assert host._last_synced_surface is None
    assert Messages.infos[-1][-1]=='folio.split.created_synced'
    ET.fromstring(edits[0])


def test_page_only_witness_still_chooses_first_folio_after_dialog():
    method,host,edits,moves,refreshed=make_context(sync=False)
    method(host,'L','L-p0008')
    assert moves==['L-p0008-left']
    assert Messages.infos[-1][-1]=='folio.split.created'


@pytest.mark.parametrize('case,xml,sid,pageid,error',[
    ('no-reference', XML, '', 'L-p0008','folio.split.no_surface_ref'),
    ('unmatched-image', XML, 'L-p0009','L-p0008','folio.split.page_not_found'),
    ('no-tei-surface', XML.replace('L-p0008','L-p0099'),'L-p0008','L-p0008','folio.split.missing_surface'),
    ('broken-xml',XML+'<bad','L-p0008','L-p0008','folio.split.xml_invalid'),
    ('existing-zone',XML.replace('</surface>','<zone xml:id="z" n="1v" ulx="0" uly="0" lrx="20" lry="20"/></surface>'),'L-p0008','L-p0008','folio.split.existing_zones'),
])
def test_preflight_failures_explain_the_issue_without_editing(case,xml,sid,pageid,error):
    method,host,edits,moves,_=make_context(xml=xml,page_id=pageid)
    method(host,'L',sid)
    assert not edits,case
    assert not moves,case
    assert Messages.warnings,case
    assert error in Messages.warnings[-1][-1],case


def test_refresh_path_preserves_double_page_button_on_synced_witness():
    assert 'panel.split_folio_btn.setEnabled(bool(panel.items))' in SRC
    assert 'self.split_folio_btn.setEnabled(bool(self.items))' in SRC
    assert 'panel is None or panel.sync_enabled' not in SRC[SRC.index('def _split_double_folio'):SRC.index('def _mark_page_in_tei')]


def test_all_seven_translations_and_help_include_fix():
    for lang in ('fr','en','de','ja','cs','it','ru'):
        root=ET.parse(ROOT/'i18n'/f'{lang}.xml').getroot()
        strings={x.get('key'):x.text for x in root.findall('string')}
        for name in ('no_surface_ref','page_not_found','xml_invalid','missing_surface','existing_zones','created_synced'):
            assert strings[f'folio.split.{name}']
        assert '0.8.5.19' in (ROOT/'help'/f'{lang}.html').read_text(encoding='utf-8')
