"""V0.8.5.6 pivot witness: safe, non-positional, opt-in TEI scaffolding."""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

import pytest

from project_management import (WitnessDraft, LocalImageDraft, AltoFileDraft,
                                minimal_tei_text)
from tei_facsimile import FacsimilePage, sync_facsimile_text
from tei_pivot_scaffold import (PivotPage, PivotScaffoldPlan, build_pivot_plan,
                                render_pivot_scaffold, scaffold_is_empty,
                                write_pivot_scaffold)


def alto_file(path, image='img_1r.jpg', n=3):
    lines = ''.join(f'<TextLine ID="l{i}" HPOS="5" VPOS="{i*20}" WIDTH="100" HEIGHT="15"><String CONTENT="foo"/></TextLine>' for i in range(n))
    path.write_text(f'<alto><Description><sourceImageInformation><fileName>{image}</fileName></sourceImageInformation></Description><Layout><Page WIDTH="600" HEIGHT="800"><PrintSpace><TextBlock>{lines}</TextBlock></PrintSpace></Page></Layout></alto>', encoding='utf-8')


def empty_with_surfaces(wid='Mu', pages=None):
    pages = pages or [('Mu-p0001','1r')]
    xml = minimal_tei_text('Test', [WitnessDraft(wid, wid)],wid)
    return sync_facsimile_text(xml,[FacsimilePage(wid,sid,label,f'images/{label}.jpg') for sid,label in pages])[0]


def test_blank_scaffold_exact_pb_lb_edref_no_zones():
    xml = empty_with_surfaces()
    plan = PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-p0001',3,'ALTO')])
    result = render_pivot_scaffold(xml,plan)
    root = ET.fromstring(result)
    ns={'t':'http://www.tei-c.org/ns/1.0'}
    para = root.find('./t:text/t:body/t:p',ns)
    assert [child.tag.rsplit('}',1)[-1] for child in para] == ['pb','lb','lb','lb']
    assert para[0].attrib == {'n':'1r','edRef':'#Mu','facs':'#Mu-p0001'}
    assert all(child.get('n') is None for child in para[1:])
    assert all(child.get('edRef') == '#Mu' and child.get('facs') is None for child in para[1:])
    assert result[:result.index('<facsimile>')] == xml[:xml.index('<facsimile>')]
    assert not scaffold_is_empty(result)
    with pytest.raises(ValueError,match='TEI_NOT_EMPTY'):
        render_pivot_scaffold(result,plan)


def test_can_disable_lb():
    result = render_pivot_scaffold(empty_with_surfaces(),PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-p0001',7,'OCR')]),include_lb=False)
    assert result.count('<pb ') == 1 and '<lb ' not in result


def test_existing_transcription_never_replaced():
    doc=empty_with_surfaces().replace('<p></p>','<p>Edited Latin text</p>')
    assert not scaffold_is_empty(doc)
    with pytest.raises(ValueError,match='TEI_NOT_EMPTY'):
        render_pivot_scaffold(doc,PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-p0001',3,'OCR')]))


def test_declared_surface_required():
    with pytest.raises(ValueError,match='MISSING_TEI_SURFACE'):
        render_pivot_scaffold(empty_with_surfaces(),PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-p9999',3,'OCR')]))


def test_actual_ocr_local_files_natural_order_preserved(tmp_path):
    first=tmp_path/'img_1r.xml'; second=tmp_path/'img_2r.xml'
    alto_file(first,'img_1r.jpg',3); alto_file(second,'img_2r.jpg',5)
    w=WitnessDraft('Mu','Pivot',image_source_type='files',image_files=[
        LocalImageDraft(tmp_path/'img_1r.jpg','1r',surface_id='Mu-one'),
        LocalImageDraft(tmp_path/'img_2r.jpg','2r',surface_id='Mu-two')],
        alto_source_type='files',alto_files=[AltoFileDraft(second),AltoFileDraft(first)])
    edition=tmp_path/'edition.xml'
    plan=build_pivot_plan([w],'Mu',tmp_path,edition)
    assert [(p.label,p.surface_id,p.line_count) for p in plan.pages] == [('1r','Mu-one',3),('2r','Mu-two',5)]
    doc=empty_with_surfaces(pages=[('Mu-one','1r'),('Mu-two','2r')])
    result=render_pivot_scaffold(doc,plan)
    assert result.count('<pb ') == 2 and result.count('<lb ') == 8
    assert result.index('facs="#Mu-one"') < result.index('facs="#Mu-two"')


def test_conservative_no_guess_if_layout_name_mismatch(tmp_path):
    source=tmp_path/'ocr_unrelated.xml'; alto_file(source,'foo.jpg',8)
    w=WitnessDraft('Mu','Pivot',image_source_type='files',
      image_files=[LocalImageDraft(tmp_path/'img_1r.jpg','1r',surface_id='Mu-one')],
      alto_source_type='files',alto_files=[AltoFileDraft(source)])
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert plan.pages[0].line_count == 0 and plan.warnings


def test_json_only_contiguous_line_numbers_and_gaps(tmp_path):
    filename=tmp_path/'alignment.json'
    data={'pages':[{'id':'one','label':'1r','lines':[{'line':1},{'line':2},{'line':3}]},
                   {'id':'two','label':'2r','lines':[{'line':1},{'line':3}]}]}
    filename.write_text(json.dumps(data),encoding='utf8')
    w=WitnessDraft('Mu','Pivot',alignment=filename,image_source_type='files',image_files=[
        LocalImageDraft(tmp_path/'img_1r.jpg','1r',surface_id='Mu-one'),
        LocalImageDraft(tmp_path/'img_2r.jpg','2r',surface_id='Mu-two')])
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert [p.line_count for p in plan.pages] == [3,2]
    assert any('lignes absentes non inventées' in w for w in plan.warnings)


def test_write_atomic_backup_and_second_attempt_unchanged(tmp_path):
    edition=tmp_path/'edition.xml'; edition.write_text(empty_with_surfaces(),encoding='utf8')
    plan=PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-p0001',2,'ALTO')])
    backup=write_pivot_scaffold(edition,plan)
    assert backup and backup.is_file() and backup.read_text(encoding='utf8').count('<lb ') == 0
    current=edition.read_bytes()
    with pytest.raises(ValueError,match='TEI_NOT_EMPTY'):
        write_pivot_scaffold(edition,plan)
    assert edition.read_bytes() == current


def make_iiif_manifest(n=469):
    from iiif_manifest import parse_manifest
    return parse_manifest({'sequences':[{'canvases':[
      {'@id':f'https://example.test/canvas/{i}', 'label':f'folio {i}',
       'images':[{'resource':{'@id':f'https://example.test/images/{i}/full/full/0/default.jpg',
        'service':{'@id':f'https://example.test/images/{i}'}}}]}
      for i in range(1,n+1)]}]},'https://example.test/manifest')


def test_469_canvases_only_five_pivot_pages(tmp_path):
    from iiif_manifest import write_cache,cache_path
    from iiif_page_selection import canvas_key
    m=make_iiif_manifest()
    write_cache(cache_path(tmp_path,'Mu'),m.source,m.raw)
    selected=[canvas_key(m.pages[i]) for i in (115,116,117,118,119)]
    jsonfile=tmp_path/'sync.json'
    pages=[{'id':f'opaque-{k}', 'iiif':{'id':url}, 'lines':[{'line':i} for i in range(1,k+2)]}
           for k,url in enumerate(selected)]
    jsonfile.write_text(json.dumps({'pages':pages}),encoding='utf8')
    w=WitnessDraft('Mu','Pivot',alignment=jsonfile,image_source_type='iiif',
       image_source_value=m.source,iiif_selection_mode='selected',iiif_selected_canvases=selected)
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert len(plan.pages) == 5
    assert [p.surface_id for p in plan.pages] == [f'Mu-p{i+1:04d}' for i in (115,116,117,118,119)]
    assert [p.line_count for p in plan.pages] == [1,2,3,4,5]
    assert plan.line_count == 15


def test_page_and_alto_source_image_metadata_can_link_exact_name(tmp_path):
    xml=tmp_path/'renamed.xml'; alto_file(xml,'img_1r.jpg',9)
    w=WitnessDraft('Mu','pivot',image_source_type='files',
       image_files=[LocalImageDraft(tmp_path/'img_1r.jpg','1r',surface_id='Mu-one')],
       alto_source_type='files',alto_files=[AltoFileDraft(xml)])
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert plan.pages[0].line_count == 9


def test_user_supplied_page_sample_counted_without_copy(tmp_path):
    path=Path('/mnt/data/Assisi541-test-1r-PAGE.xml')
    if not path.is_file():
        pytest.skip('Optional original PERO test fixture not distributed')
    w=WitnessDraft('Mu','pivot',image_source_type='files',
       image_files=[LocalImageDraft(tmp_path/'Assisi541-test-1r.jpg','1r',surface_id='Mu-one')],
       alto_source_type='files',alto_files=[AltoFileDraft(path)])
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert plan.pages[0].line_count == 39


def test_real_new_project_import_copy_and_reload(tmp_path):
    from project_management import create_new_transcription_project
    from project_config import load_project
    source=tmp_path/'input'; source.mkdir()
    alto_file(source/'img_1r.xml','img_1r.jpg',4)
    (source/'img_1r.jpg').write_bytes(b'example')
    template=Path(__file__).resolve().parents[1]
    target=tmp_path/'created'
    w=WitnessDraft('Mu','Pivot',image_source_type='files',
       image_files=[LocalImageDraft(source/'img_1r.jpg','1r',surface_id='Mu-one')],
       image_import_mode='copy',alto_source_type='files',
       alto_files=[AltoFileDraft(source/'img_1r.xml')],alto_import_mode='copy')
    project_path=create_new_transcription_project(target,'New',[w],'Mu',template,
                                                  language='fr',xslt_mode='builtin')
    project=load_project(project_path)
    assert project.base_witness == 'Mu'
    plan=build_pivot_plan(project.witnesses,project.base_witness,project.root_dir,project.edition)
    assert plan.pages[0].line_count == 4, (plan.pages,plan.warnings)
    write_pivot_scaffold(project.edition,plan)
    doc=ET.parse(project.edition).getroot()
    namespace={'t':'http://www.tei-c.org/ns/1.0'}
    p=doc.find('./t:text/t:body/t:p',namespace)
    assert len(p) == 5 and p[0].get('facs') == '#Mu-one'
    assert load_project(project_path).witnesses[0].image_files[0].surface_id == 'Mu-one'


def test_sync_json_owns_iiif_without_separate_image_source(tmp_path):
    source=tmp_path/'pivot.json'
    source.write_text(json.dumps({'pages':[
      {'id':'folio14v', 'image_name':'local-scan-14v.jpg',
       'iiif':{'id':'https://example.test/canvas/999','label':'14v',
               'image':'https://example.test/image/999/full/max/0/default.jpg'},
       'lines':[{'line':1},{'line':2}]},
      {'id':'folio15r','iiif':{'id':'https://example.test/canvas/1000','label':'15r',
               'image':'https://example.test/image/1000/full/max/0/default.jpg'},
       'lines':[{'line':1}]}]}),encoding='utf8')
    w=WitnessDraft('Mu','pivot',alignment=source,image_source_type='auto')
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert len(plan.pages) == 2 and len(plan.missing_surfaces) == 2
    assert [p.line_count for p in plan.pages] == [2,1]
    xml=minimal_tei_text('Edition',[w],'Mu')
    result=render_pivot_scaffold(xml,plan)
    doc=ET.fromstring(result)
    ns={'t':'http://www.tei-c.org/ns/1.0'}
    assert len(doc.findall('./t:facsimile/t:surface',ns)) == 2
    assert len(doc.findall('./t:text/t:body/t:p/t:pb',ns)) == 2
    assert len(doc.findall('./t:text/t:body/t:p/t:lb',ns)) == 3
    assert 'https://example.test/image/999/full/max/0/default.jpg' in result


def test_prefixed_tei_keeps_prefix_and_valid_namespace():
    xml='''<?xml version="1.0"?><tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:teiHeader><tei:fileDesc><tei:titleStmt><tei:title>Test</tei:title></tei:titleStmt><tei:publicationStmt><tei:p>x</tei:p></tei:publicationStmt><tei:sourceDesc><tei:listWit><tei:witness xml:id="Mu">Mu</tei:witness></tei:listWit></tei:sourceDesc></tei:fileDesc></tei:teiHeader><tei:facsimile><tei:surface xml:id="Mu-s1" n="1r"><tei:graphic url="a.jpg"/></tei:surface></tei:facsimile><tei:text><tei:body><tei:p/></tei:body></tei:text></tei:TEI>'''
    result=render_pivot_scaffold(xml,PivotScaffoldPlan('Mu',[PivotPage('1r','Mu-s1',2,'ALTO')]))
    assert '<tei:pb ' in result and '<tei:lb ' in result
    assert len(ET.fromstring(result).findall('.//{http://www.tei-c.org/ns/1.0}lb'))==2


def test_unknown_json_page_never_assigned_by_manifest_position(tmp_path):
    from iiif_manifest import write_cache,cache_path
    from iiif_page_selection import canvas_key
    m=make_iiif_manifest(10); write_cache(cache_path(tmp_path,'Mu'),m.source,m.raw)
    selected=[canvas_key(m.pages[5])]
    p=tmp_path/'unmatched.json';p.write_text(json.dumps({'pages':[{'id':'unclear','lines':[{'line':1}]}]}),encoding='utf8')
    w=WitnessDraft('Mu','Pivot',alignment=p,image_source_type='iiif',
       image_source_value=m.source,iiif_selection_mode='selected',iiif_selected_canvases=selected)
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert len(plan.pages)==1 and plan.pages[0].line_count==0
    assert plan.warnings


def test_local_ocr_conflicting_source_metadata_not_guessed(tmp_path):
    xml=tmp_path/'img_1r.xml';alto_file(xml,'img_2r.jpg',4)
    w=WitnessDraft('Mu','pivot',image_source_type='files',
       image_files=[LocalImageDraft(tmp_path/'img_1r.jpg','1r',surface_id='Mu-one')],
       alto_source_type='files',alto_files=[AltoFileDraft(xml)])
    assert build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml').pages[0].line_count == 0
