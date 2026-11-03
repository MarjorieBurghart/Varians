"""V0.8.5.20: source pixel split, precise marking, toolbar UX and preview."""
from __future__ import annotations
import ast
from pathlib import Path
from types import SimpleNamespace
import sys
import xml.etree.ElementTree as ET

import pytest
from varians_source import application_source, application_ast

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from folio_navigation import folios_for_witness, markable_part_for_line, split_surface_into_folios
from tei_facsimile import upsert_pb_at_position, position_inside_xml_markup
from image_sources import page_image_source, page_image_dimensions
from text_search import Utf16Positions
from test_v08519_split_dialog import ui_method, Dialog, Widget, Input, Spin, DialogButtons, Messages, make_context, Hook

XML='''<TEI xmlns="http://www.tei-c.org/ns/1.0"><facsimile>
<surface xml:id="L-p0008" n="008 - f002v-003r"><graphic url="spread.jpg"/></surface>
</facsimile><text><body><p>fin du passage</p></body></text></TEI>'''
FULL,IDS=split_surface_into_folios(XML,'L-p0008','p. 12','p. 13',3924,2704,split_pixel=1973)
PARTS=folios_for_witness(FULL,'L',['L-p0008'])


def item(x,width=100,*,page_mode=False,altow=3924,imagew=3924,polygon_only=False):
    p={'tei_surface_id':'L-p0008','alto_width':altow,'alto_height':2704,
       'image':{'type':'file','path':'spread.jpg','width':imagew,'height':2704}}
    if polygon_only:
        line={'polygon':[[x,700],[x+width,700],[x+width,760],[x,760]]}
    else:
        line={'bbox':{'hpos':x,'vpos':700,'width':width,'height':60}}
    if page_mode:line['_page_mode']=True
    return {'p':p,'l':line}


def test_precise_split_pixel_not_rounded_by_percentage():
    assert IDS==('L-p0008-left','L-p0008-right')
    root=ET.fromstring(FULL)
    zones=[z for z in root.iter() if z.tag.endswith('zone')]
    assert [z.get('n') for z in zones]==['p. 12','p. 13']
    assert [z.get('lrx') for z in zones]==['1973','3924']
    assert zones[1].get('ulx')=='1973'
    assert sum(1 for e in root.iter() if e.tag.endswith('graphic'))==1


@pytest.mark.parametrize('x,width,expected',[
    (470,1400,'L-p0008-left'),
    (2010,1380,'L-p0008-right'),
    (1950,50,None),
    (1800,330,None),
    (0,200,'L-p0008-left'),
])
def test_geometric_side_selection_leiden(x,width,expected):
    result=markable_part_for_line(item(x,width),PARTS)
    assert (result.ref if result else None)==expected


def test_geometry_scales_from_alto_space_to_full_source_pixels():
    # Geometric 1000px x coordinate from a 1962px ALTO half-resolution image
    # corresponds to 2000px in the 3924px source coordinate system.
    found=markable_part_for_line(item(1005,680,altow=1962),PARTS)
    assert found and found.ref=='L-p0008-right'


def test_polygon_only_geometry_and_no_line_safe_fallback():
    assert markable_part_for_line(item(520,1200,polygon_only=True),PARTS).ref=='L-p0008-left'
    assert markable_part_for_line(item(520,1200,page_mode=True),PARTS) is None
    assert markable_part_for_line({'p':{'tei_surface_id':'L-p0008'},'l':{}},PARTS) is None
    assert markable_part_for_line(item(520),PARTS[:2]) is None


class Emitted:
    def __init__(self):self.events=[]
    def emit(self,*args):self.events.append(args)


class Choose:
    next=1
    calls=[]
    @classmethod
    def getItem(cls, *args):
        cls.calls.append(args)
        return args[3][cls.next], True


def mark_panel(sync=True, focus=None):
    current=focus or item(2010,1380)
    events=Emitted()
    selected=SimpleNamespace(ref='L-p0008-left',surface='L-p0008',label='p. 12',region=PARTS[1].region)
    panel=SimpleNamespace(siglum='L',sync_enabled=sync,folios=PARTS,project_root=ROOT,
                          current_item=lambda:current,markPageRequested=events,
                          _current_folio=lambda:selected)
    fn=ui_method('ManuscriptPanel','_request_mark_page',{
        'markable_part_for_line':markable_part_for_line,
        'image_page_label':lambda *a,**k:'008',
        'QInputDialog':Choose,
        '_t':lambda key,**kw:key,
    })
    return fn,panel,events


def test_synced_mark_uses_right_part_based_on_current_line_not_previous_selection():
    fn,panel,events=mark_panel(sync=True)
    fn(panel)
    assert events.events==[('L','L-p0008-right','p. 13')]


def test_page_mode_mark_uses_selected_left_part():
    fn,panel,events=mark_panel(sync=False,focus=item(2010,1380,page_mode=True))
    fn(panel)
    assert events.events==[('L','L-p0008-left','p. 12')]


def test_ambiguous_synced_line_prompts_explicit_choice_not_surface_marker():
    Choose.calls=[];Choose.next=1
    fn,panel,events=mark_panel(sync=True,focus=item(1950,50))
    fn(panel)
    assert Choose.calls
    assert events.events==[('L','L-p0008-right','p. 13')]


def test_generated_pb_targets_zone_and_preserves_witness():
    pos=FULL.index('fin du passage')
    out,_,mode=upsert_pb_at_position(FULL,pos,'p. 13','L-p0008-right',witness_id='L')
    assert mode=='inserted'
    assert '<pb n="p. 13" edRef="#L" facs="#L-p0008-right"/>' in out
    ET.fromstring(out)


def test_real_mark_handler_checks_target_before_adding_pb():
    src=application_source()
    assert 'target.label != label' in src
    assert "folio.mark.stale_target" in src
    # Verify the validation code occurs before synchronizing the facsimile.
    callback=src[src.index('    def _mark_page_in_tei('):src.index('    def sync_panels_to_cursor(')]
    assert callback.index('target.label != label') < callback.index('sync_facsimile_text(')


def test_no_additional_toolbar_row_and_thumbnail_preview_full_page():
    src=application_source()
    constructor=src[src.index('class ManuscriptPanel('):src.index('    def retranslate_ui(',src.index('class ManuscriptPanel('))]
    assert 'bar.addWidget(self.split_folio_btn)' in constructor
    assert 'root.addLayout(folio_bar)' not in constructor
    assert 'self.folio_combo.hide()' in constructor
    callback=src[src.index('    def _split_double_folio('):src.index('    def _mark_page_in_tei(')]
    assert "load_split_thumbnail(preview, current['p'], self.project.root_dir)" in callback
    assert 'split_pixel=preview.split_px' in callback
    assert "ratio.valueChanged.connect" in callback
    assert "preview.splitChanged.connect" in callback
    assert "QDoubleSpinBox" in callback
    assert "#e32124" in src
    assert "def mouseMoveEvent(self, event)" in src


def test_preview_iiif_uses_reduced_full_canvas_not_current_line_crop():
    source=application_source()
    tree=application_ast()
    fun=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_iiif_split_preview_request')
    namespace={'page_image_source':page_image_source,'generic_image_request':lambda *a,**k:None}
    exec(compile(ast.fix_missing_locations(ast.Module(body=[fun],type_ignores=[])),'<test>','exec'),namespace)
    url,_=namespace['_iiif_split_preview_request']({'image':{'type':'iiif','service':'https://example.org/iiif/id','iiif_version':2}},ROOT)
    assert url=='https://example.org/iiif/id/full/800,/0/default.jpg'


def test_new_labels_available_in_all_seven_locales():
    for language in ('fr','en','de','it','ru','ja','cs'):
        data={x.get('key'):x.text for x in ET.parse(ROOT/'i18n'/f'{language}.xml').getroot()}
        for key in ('folio.split.left','folio.split.right','folio.split.loading','folio.split.drag_tip',
                    'folio.mark.choose_title','folio.mark.choose_prompt','folio.mark.stale_target'):
            assert data.get(key), (language,key)
        # V0.9.3.1 : l'aide n'annonce plus les versions ; elle explique la double page.
        assert data['folio.split.button'] in (ROOT/'help'/f'{language}.html').read_text(encoding='utf-8')

from folio_navigation import inspect_surface_part_split, configure_surface_parts


def test_existing_two_zones_can_reopen_adjust_without_duplicate_or_changing_ids():
    previous=inspect_surface_part_split(FULL,'L-p0008',3924,2704)
    assert previous['split_pixel']==1973
    updated, ids=configure_surface_parts(FULL,'L-p0008','p. 12','p. 13',3924,2704,split_pixel=1888)
    assert ids==IDS
    root=ET.fromstring(updated)
    zones=[e for e in root.iter() if e.tag.endswith('zone')]
    assert len(zones)==2
    assert [e.get('lrx') for e in zones]==['1888','3924']
    assert zones[1].get('ulx')=='1888'
    assert updated.count('<graphic')==FULL.count('<graphic')==1


def test_existing_pb_references_are_preserved_on_split_adjustment():
    source=FULL.replace('fin du passage','<pb n="p. 13" edRef="#L" facs="#L-p0008-right"/>fin du passage')
    updated,ids=configure_surface_parts(source,'L-p0008','p. 12','p. 13',3924,2704,split_pixel=2101)
    assert '<pb n="p. 13" edRef="#L" facs="#L-p0008-right"/>' in updated
    assert updated.count('xml:id="L-p0008-right"')==1
    with pytest.raises(ValueError,match='libellé'):
        configure_surface_parts(source,'L-p0008','p. 12','p. 14',3924,2704,split_pixel=2101)


def test_existing_custom_tei_zones_are_never_rewritten():
    xml=FULL.replace('L-p0008-right','custom-right')
    with pytest.raises(ValueError,match='identifiants'):
        configure_surface_parts(xml,'L-p0008','p. 12','p. 13',3924,2704,split_pixel=1888)


def test_existing_zone_attributes_not_replaced():
    xml=FULL.replace('n="p. 12" ulx=', 'n="p. 12" rend="verso" ulx=')
    out,_=configure_surface_parts(xml,'L-p0008','p. 12','p. 13',3924,2704,split_pixel=1888)
    assert 'rend="verso"' in out
    ET.fromstring(out)


def test_existing_split_works_through_real_dialog_controller_stubs():
    from test_v08519_split_dialog import make_context
    existing_xml,_=split_surface_into_folios(XML,'L-p0008','f002v','f003r',3924,2704,split_pixel=1962)
    method,host,edits,moves,_=make_context(xml=existing_xml,sync=True)
    method(host,'L','L-p0008')
    assert len(edits)==1
    assert edits[0].count('xml:id="L-p0008-left"')==1
    assert edits[0].count('xml:id="L-p0008-right"')==1
    assert moves==[]


def test_actual_marker_controller_inserts_zone_pb_not_canvas_pb():
    from tei_facsimile import upsert_pb_at_position, position_inside_xml_markup
    editor_text=FULL
    cursor_pos=editor_text.index('fin du passage')
    outputs=[];status=[]
    editor=SimpleNamespace(toPlainText=lambda:editor_text,
                           textCursor=lambda:SimpleNamespace(position=lambda:cursor_pos),
                           positions=lambda text=None:Utf16Positions(editor_text if text is None else text))
    panel=SimpleNamespace(_surface_indices={'L-p0008':0})
    host=SimpleNamespace(editor=editor,panels={'L':panel},witness_configs=[],
           _edition_displayed=lambda:True,_edition_text=lambda:editor_text,
           project=SimpleNamespace(root_dir=ROOT,edition=ROOT/'edition.xml'),
           _replace_editor_text_minimally=lambda old,new,pos:outputs.append((old,new,pos)),
           _sync_page_panels_to_cursor=lambda force=False:None,
           statusBar=lambda:SimpleNamespace(showMessage=lambda *a:status.append(a)),
           _last_synced_surface='cached')
    ns={
        'position_inside_xml_markup':position_inside_xml_markup,
        'folios_for_witness':folios_for_witness,
        'QMessageBox':Messages,
        '_t':lambda key,**kw:key,
        'project_facsimile_pages':lambda *args:[],
        'sync_facsimile_text':lambda old,*args:(old,SimpleNamespace(conflicts=[])),
        'previous_surface_labels':lambda *args:{},
        'upsert_pb_at_position':upsert_pb_at_position,
    }
    callback=ui_method('MainWindow','_mark_page_in_tei',ns)
    callback(host,'L','L-p0008-right','p. 13')
    assert len(outputs)==1
    assert '<pb n="p. 13" edRef="#L" facs="#L-p0008-right"/>' in outputs[0][1]
    assert 'facs="#L-p0008"' not in outputs[0][1]
    assert host._last_synced_surface is None
    ET.fromstring(outputs[0][1])


def test_marker_controller_rejects_removed_zone_without_edit():
    from tei_facsimile import position_inside_xml_markup
    outputs=[]
    editor=SimpleNamespace(toPlainText=lambda:XML,
                           textCursor=lambda:SimpleNamespace(position=lambda:XML.index('texte') if 'texte' in XML else XML.index('fin du passage')),
                           positions=lambda text=None:Utf16Positions(XML if text is None else text))
    panel=SimpleNamespace(_surface_indices={'L-p0008':0})
    host=SimpleNamespace(editor=editor,panels={'L':panel},
                         _edition_displayed=lambda:True,_edition_text=lambda:XML,
                         _replace_editor_text_minimally=lambda *args:outputs.append(args))
    Messages.warnings=[]
    callback=ui_method('MainWindow','_mark_page_in_tei',{
       'position_inside_xml_markup':position_inside_xml_markup,
       'folios_for_witness':folios_for_witness,
       'QMessageBox':Messages, '_t':lambda key,**kw:key,
    })
    callback(host,'L','L-p0008-right','p. 13')
    assert Messages.warnings
    assert Messages.warnings[-1][-1]=='folio.mark.stale_target'
    assert not outputs
