"""Regression: a manifest is a catalogue, not an automatic TEI facsimile."""
from pathlib import Path
import pytest
from iiif_manifest import cache_path, write_cache, read_cache
from iiif_page_selection import canvas_key, natural_key, selected_page_overlay
from iiif_local import plan_witness_copy, download_witness_copy
from project_management import (WitnessDraft, AltoFileDraft, ProjectDraft,
                                write_project_xml, prepare_alto_files_for_project)
from project_config import load_project
from tei_facsimile import project_facsimile_pages, sync_facsimile_text
from alto_import import build_alto_cache
from image_sources import apply_witness_image_policy


def manifest():
    return {'sequences': [{'canvases': [
        {'@id': f'https://example.test/canvas/{i}', 'label': label,
         'images': [{'resource': {'@id': f'https://example.test/image/{i}.jpg'}}]}
        for i, label in enumerate(('Cover', 'f. 1r', 'f. 1v', 'f. 2r', 'f. 2v', 'Back'), 1)
    ]}]}


def ocr(path, image):
    path.write_text(f'''<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
      <Page imageFilename="{image}" imageWidth="600" imageHeight="800">
        <TextRegion id="region"><TextLine id="first">
          <Coords points="1,1 300,1 300,20 1,20"/>
          <TextEquiv><Unicode>Some text</Unicode></TextEquiv>
        </TextLine></TextRegion></Page></PcGts>''', encoding='utf8')
    return path


def setup(tmp_path):
    src='https://example.test/manifest'
    write_cache(cache_path(tmp_path,'W'),src,manifest())
    m=read_cache(cache_path(tmp_path,'W'),src)
    keys=[canvas_key(p) for p in m.pages]
    # Different local names from IIIF deliberately (inverted filenames!).
    p1=ocr(tmp_path/'scan_x18.xml','offline-page-777.jpg')
    p2=ocr(tmp_path/'scan_y20.xml','offline-page-888.jpg')
    selected=[keys[2],keys[4]]  # 1v, 2v
    links=[(str(p1),keys[4]), (str(p2),keys[2])]
    return src,m,p1,p2,selected,links


def test_natural_sort_for_recto_verso_and_multiple_digit_numbers():
    values=['img_10v.xml','img_1v.xml','img_2r.xml','img_10r.xml','img_1r.xml','img_2v.xml']
    assert sorted(values, key=natural_key)==[
        'img_1r.xml','img_1v.xml','img_2r.xml','img_2v.xml','img_10r.xml','img_10v.xml']


def test_only_selected_surfaces_and_unlinked_do_not_gain_surfaces(tmp_path):
    src,m,p1,p2,selected,links=setup(tmp_path)
    w=WitnessDraft('W','W',role='base',image_source_type='iiif',image_source_value=src,
                   iiif_selection_mode='selected',iiif_selected_canvases=selected,
                   iiif_ocr_links=links)
    pages=project_facsimile_pages([w],tmp_path,tmp_path/'edition.xml')
    assert len(pages)==2
    assert [p.surface_id for p in pages]==['W-p0003','W-p0005']
    tei='<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body/></text></TEI>'
    updated,report=sync_facsimile_text(tei,pages)
    assert len(report.added)==2
    assert '<surface xml:id="W-p0001"' not in updated
    # Facsimile sync never removes older surfaces (important data ownership).
    updated_again,report=sync_facsimile_text(updated,pages[:1])
    assert 'W-p0005' in updated_again


def test_explicit_links_override_unrelated_names_and_order(tmp_path):
    src,m,p1,p2,selected,links=setup(tmp_path)
    cache=build_alto_cache([p1,p2], 'W','base')
    out=apply_witness_image_policy(cache,'iiif',src,tmp_path,(), 'W',
                                   'selected',selected,links)
    assert [p['image']['type'] for p in out['pages']]==['iiif','iiif']
    assert [p['label'] for p in out['pages']]==['f. 1v','f. 2v']
    assert out['pages'][0]['alto_source_file']==str(p2)
    assert out['pages'][1]['alto_source_file']==str(p1)
    assert len(out['pages'][0]['lines'])==1
    assert out['pages'][0]['tei_surface_id']=='W-p0003'


def test_no_guess_or_ordinal_fallback_for_unknown_link(tmp_path):
    src,m,p1,p2,selected,links=setup(tmp_path)
    cache=build_alto_cache([p1,p2], 'W','base')
    missing=[(str(tmp_path/'missing.xml'),selected[0])]
    with pytest.raises(ValueError,match='exactly one'):
        selected_page_overlay(cache,m,selected,missing,'W',tmp_path)
    # Without links, OCR remains intact but unassociated, never silently 1v/2v.
    out=selected_page_overlay(cache,m,selected,[],'W',tmp_path)
    assert [p['image']['type'] for p in out['pages']]==['iiif','iiif','none','none']


def test_selected_download_but_not_full_manifest_even_if_names_differ(tmp_path,monkeypatch):
    src,m,p1,p2,selected,links=setup(tmp_path)
    plan=plan_witness_copy(tmp_path,'W',src,scope='ocr',layout_files=[AltoFileDraft(p1),AltoFileDraft(p2)],
            selection_mode='selected',selected_canvases=selected,ocr_links=links)
    assert plan['indices']==[2,4]
    collected=[]
    def fake(url,dest):
        collected.append(url)
        p=dest.with_suffix('.jpg'); p.write_bytes(b'\xff\xd8\xffok');return p
    monkeypatch.setattr('iiif_local._fetch_image',fake)
    result=download_witness_copy(tmp_path,'W',src,scope='ocr',
             layout_files=[AltoFileDraft(p1),AltoFileDraft(p2)],
             selection_mode='selected',selected_canvases=selected,ocr_links=links)
    assert result['downloaded']==2 and result['excluded']==4
    assert collected==['https://example.test/image/3.jpg','https://example.test/image/5.jpg']
    full=plan_witness_copy(tmp_path,'W',src,scope='all',selection_mode='selected',selected_canvases=selected)
    assert full['total']==2 and full['cached']==2


def test_project_roundtrip_and_link_rebase_on_copy(tmp_path):
    src,m,p1,p2,selected,links=setup(tmp_path)
    w=WitnessDraft('W','Witness',role='base',image_source_type='iiif',image_source_value=src,
                   alto_source_type='files',alto_files=[AltoFileDraft(p1),AltoFileDraft(p2)],
                   alto_import_mode='copy',iiif_selection_mode='selected',
                   iiif_selected_canvases=selected,iiif_ocr_links=links)
    migrated=prepare_alto_files_for_project(tmp_path,[w])[0]
    assert all(Path(a.path).is_file() for a in migrated.alto_files)
    assert migrated.iiif_ocr_links[0][0]==str(migrated.alto_files[0].path)
    xml=tmp_path/'edition.xml';xml.write_text('<TEI/>')
    draft=ProjectDraft('T',xml,'fr','en',tmp_path/'i18n',tmp_path/'xsl',tmp_path/'css',
        tmp_path/'custom',tmp_path/'web','viewer.html',[migrated],'W',schema_mode='none')
    conf=load_project(write_project_xml(tmp_path/'project.xml',draft))
    loaded=conf.witness_by_id['W']
    assert loaded.iiif_selection_mode=='selected'
    assert loaded.iiif_selected_canvases==tuple(selected)
    assert [(str(a),b) for a,b in loaded.iiif_ocr_links]==migrated.iiif_ocr_links
    cache=build_alto_cache([x.path for x in loaded.alto_files],'W','base')
    overlaid=apply_witness_image_policy(cache,'iiif',src,tmp_path,(), 'W',
        loaded.iiif_selection_mode,loaded.iiif_selected_canvases,loaded.iiif_ocr_links)
    assert [p['label'] for p in overlaid['pages']]==['f. 1v','f. 2v']


def test_unused_auto_surfaces_only_removed_by_explicit_opt_in(tmp_path):
    from tei_facsimile import removable_generated_iiif_surfaces
    src,m,p1,p2,selected,links=setup(tmp_path)
    w=WitnessDraft('W','W',role='base',image_source_type='iiif',image_source_value=src)
    all_surfaces=project_facsimile_pages([w],tmp_path,tmp_path/'edition.xml')
    tei='<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body/></text></TEI>'
    text,_=sync_facsimile_text(tei,all_surfaces)
    # A user reference to page 1, and an annotated surface for page 4, are protected.
    text=text.replace('<body/>','<body><pb facs="#W-p0001"/></body>')
    text=text.replace('<surface xml:id="W-p0004" n="f. 2r">',
                      '<surface xml:id="W-p0004" n="f. 2r" resp="#editor">')
    new_text,removed=removable_generated_iiif_surfaces(text,m,'W',selected)
    assert removed==('W-p0002','W-p0006')
    assert 'W-p0001' in new_text and 'W-p0004' in new_text
    assert 'W-p0003' in new_text and 'W-p0005' in new_text
    assert '<pb facs="#W-p0001"/>' in new_text
    # The function leaves the original immutable; an app should ask first.
    assert 'W-p0006' in text


def test_explicit_mapping_disables_unsafe_positional_alignment_fallback(tmp_path):
    from alto_import import overlay_alto
    prev={'pages':[{'id':'original-page','label':'unrelated',
                   'lines':[{'line':1,'base_keys':['base::1'],'alto_id':'old'}]}]}
    new={'pages':[{'id':'new-page','label':'different',
                  'alto_source_file':'abc.xml',
                  'lines':[{'line':1,'alto_id':'new'}]}]}
    old=overlay_alto(prev,new)
    assert old['pages'][0]['lines'][0].get('base_keys')==['base::1']
    safe=overlay_alto(prev,new,strict_no_ordinal=True)
    assert len(safe['pages'])==2
    assert safe['pages'][0]['lines'][0].get('base_keys')==['base::1']
    assert safe['pages'][1]['lines'][0].get('base_keys') is None


def test_web_export_respects_exact_selected_canvases_and_local_choice(tmp_path,monkeypatch):
    from dataclasses import replace
    from project_config import load_project
    from web_viewer.generator import build_dataset
    from iiif_local import download_witness_copy
    source_project=load_project(Path(__file__).resolve().parents[1]/'project.xml')
    src,m,p1,p2,selected,links=setup(tmp_path)
    w=replace(source_project.base, alignment=None, image_source_type='iiif',
        image_source_value=src, alto_source_type='files',
        alto_files=tuple([AltoFileDraft(p1),AltoFileDraft(p2)]),
        iiif_selection_mode='selected', iiif_selected_canvases=tuple(selected),
        iiif_ocr_links=tuple(links), iiif_local_copy=False,
        iiif_web_local_copy=False)
    project=replace(source_project,path=tmp_path/'project.xml',witnesses=(w,),
        base_witness=w.id,web_output_dir=tmp_path/'web_output')
    # setup() cached the manifest for witness W; selected config uses same ID.
    if w.id != 'W':
        write_cache(cache_path(tmp_path,w.id),src,manifest())
    remote,_=build_dataset(project)
    pages=remote['witnesses'][0]['pages']
    assert len(pages)==2
    assert [p['image']['type'] for p in pages]==['iiif','iiif']
    collected=[]
    def fake(url,stem):
        collected.append(url)
        path=stem.with_suffix('.jpg');path.write_bytes(b'\xff\xd8\xffok');return path
    monkeypatch.setattr('iiif_local._fetch_image',fake)
    download_witness_copy(tmp_path,w.id,src,scope='all',selection_mode='selected',selected_canvases=selected)
    localproject=replace(project,witnesses=(replace(w,iiif_web_local_copy=True),))
    local,_=build_dataset(localproject)
    assert len(local['witnesses'][0]['pages'])==2
    assert [p['image']['type'] for p in local['witnesses'][0]['pages']]==['file','file']
    assert len(collected)==2


def test_large_manifest_500_canvases_only_six_editorial_pages(tmp_path):
    src='https://example.test/long-manifest'
    data={'sequences':[{'canvases':[
        {'@id':f'https://example.test/canvas/{i}', 'label':f'f. {i}r',
         'images':[{'resource':{'@id':f'https://example.test/image/{i}.jpg'}}]}
        for i in range(1,501)]}]}
    write_cache(cache_path(tmp_path,'W'),src,data)
    m=read_cache(cache_path(tmp_path,'W'),src)
    chosen_positions=(0,12,57,301,407,499)
    selection=[canvas_key(m.pages[i]) for i in chosen_positions]
    w=WitnessDraft('W','W',role='base',image_source_type='iiif',
        image_source_value=src,iiif_selection_mode='selected',
        iiif_selected_canvases=selection)
    pages=project_facsimile_pages([w],tmp_path,tmp_path/'edition.xml')
    plan=plan_witness_copy(tmp_path,'W',src,scope='all',
        selection_mode='selected',selected_canvases=selection)
    assert len(pages)==6 and plan['total']==6 and plan['excluded']==494
    assert plan['indices']==list(chosen_positions)
    assert [p.surface_id for p in pages]==[
        'W-p0001','W-p0013','W-p0058','W-p0302','W-p0408','W-p0500']


def test_a_surface_cited_only_in_a_part_of_the_edition_is_kept(tmp_path):
    # V0.9.0.0 : une édition assemblée par XInclude ; le <pb> qui cite la
    # surface est dans une partie (autre fichier).
    from tei_facsimile import removable_generated_iiif_surfaces
    src,m,p1,p2,selected,links=setup(tmp_path)
    w=WitnessDraft('W','W',role='base',image_source_type='iiif',image_source_value=src)
    all_surfaces=project_facsimile_pages([w],tmp_path,tmp_path/'edition.xml')
    tei='<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body/></text></TEI>'
    text,_=sync_facsimile_text(tei,all_surfaces)
    part='<div xmlns="http://www.tei-c.org/ns/1.0"><pb facs="#W-p0002"/></div>'
    _new_text,removed=removable_generated_iiif_surfaces(text,m,'W',selected,other_texts=[part])
    assert 'W-p0002' not in removed and 'W-p0006' in removed
