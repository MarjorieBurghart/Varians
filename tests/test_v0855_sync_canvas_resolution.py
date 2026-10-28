"""No positional mapping: Varians-Synchro / IIIF subset integration regressions."""
from __future__ import annotations
import json
from dataclasses import replace
from pathlib import Path

import pytest

from iiif_manifest import parse_manifest, cache_path, write_cache
from iiif_page_selection import canvas_key
from iiif_resolution import resolve_pages, overlay_resolved_manifest
from image_sources import apply_witness_image_policy
from iiif_local import apply_working_copy, local_image_path, index_path, remote_key, _request_url
from project_config import load_project
from project_management import WitnessDraft, ProjectDraft, write_project_xml
from tei_facsimile import project_facsimile_pages


def v2_manifest(n=469, labels=None, domain='sample.test'):
    return parse_manifest({'sequences': [{'canvases': [
        {'@id': f'https://{domain}/canvas/{i}', 'label': (labels or {}).get(i, f'f. {i}v'),
         'images': [{'resource': {'@id': f'https://{domain}/image/{i}/full/full/0/default.jpg',
                    'service': {'@id': f'https://{domain}/image/{i}', 'profile': 'http://iiif.io/api/image/2/level2.json'},
                    'width': 4000, 'height': 6000}}]}
        for i in range(1, n + 1)
    ]}]}, f'https://{domain}/manifest')


def v3_manifest(n=469):
    return parse_manifest({'type': 'Manifest', 'items': [
        {'id': f'https://sample.test/v3/canvas/{i}', 'type': 'Canvas',
         'label': {'none': [f'folio {i}']}, 'items': [{
             'type': 'AnnotationPage', 'items': [{
                 'type': 'Annotation', 'motivation': 'painting',
                 'body': {'type': 'Image', 'id': f'https://sample.test/v3/im/{i}/full/max/0/default.jpg',
                          'service': [{'id': f'https://sample.test/v3/im/{i}', 'type': 'ImageService3'}]}
             }]
         }]}
        for i in range(1, n + 1)
    ]}, 'https://sample.test/v3/manifest')


def sync_five(m, mode='canvas'):
    indices = [115, 116, 117, 118, 119]
    pages = []
    for n, i in enumerate(indices):
        source = m.pages[i]['image']
        ref = {'id': source['canvas'], 'label': m.pages[i]['label'],
               'service': source.get('service'), 'image': source.get('image')}
        if mode == 'service': ref = {'service': source['service']}
        if mode == 'image':
            ref = {'image': source['service'] + '/full/1200,/0/default.jpg'}
        pages.append({'id': f'sync-id-{n}', 'image_name': f'unrelated{n}.jpg',
                      'iiif': ref, 'lines': [{'line': n+1,
                       'base_keys': ['pivot::1'], 'bbox': {'hpos': 3, 'vpos': 5, 'width': 30, 'height': 9}}]})
    return {'meta': {'format': 'tei-manuscript-alignment', 'witness': 'F'}, 'pages': pages}, indices


def test_469_canvases_five_sync_pages_keep_ids_and_lines():
    m = v2_manifest()
    cache, selected = sync_five(m)
    before = json.dumps(cache, sort_keys=True)
    out = overlay_resolved_manifest(cache, m, 'F')
    assert len(out['pages']) == 5
    assert [p['id'] for p in out['pages']] == [p['id'] for p in cache['pages']]
    assert [p['image']['canvas'] for p in out['pages']] == [m.pages[i]['image']['canvas'] for i in selected]
    assert [p['tei_surface_id'] for p in out['pages']] == [f'F-p{i+1:04d}' for i in selected]
    assert cache['pages'][0]['lines'][0]['base_keys'] == out['pages'][0]['lines'][0]['base_keys']
    assert json.dumps(cache, sort_keys=True) == before  # immutable source JSON


@pytest.mark.parametrize('version', [2, 3])
@pytest.mark.parametrize('evidence', ['canvas', 'service', 'image'])
def test_strong_evidence_for_both_presentation_versions(version, evidence):
    m = v2_manifest() if version == 2 else v3_manifest()
    cache, selected = sync_five(m, evidence)
    if evidence == 'image':
        # v2 and v3 both support Image API sizes (v3 uses max and v2 full)
        assert cache['pages'][0]['iiif']['image'].endswith('/default.jpg')
    resolutions = resolve_pages(cache['pages'], m)
    assert [resolutions[i].key for i in range(5)] == [canvas_key(m.pages[k]) for k in selected]
    assert all(r.status == 'resolved' for r in resolutions.values())


def test_ambiguous_label_never_guessed():
    m = v2_manifest(4, {1:'f. 14v', 2:'f. 14v', 3:'f. 15r', 4:'f. 15v'})
    sync = [{'id': 'different-json-id', 'label': 'f. 14v', 'lines': [{'line':1}]}]
    resolved = resolve_pages(sync, m)
    assert resolved[0].status == 'ambiguous'
    assert len(resolved[0].candidates) == 2
    out = overlay_resolved_manifest({'pages':sync}, m, 'F', [canvas_key(p) for p in m.pages])
    assert out['pages'][0]['image']['type'] == 'none'
    assert len(out['pages']) == 1


def test_explicit_link_succeeds_and_survives_reordered_manifest():
    m = v2_manifest(10)
    src = {'pages':[{'id':'json-page-14v', 'lines':[{'line': 1, 'base_keys':['Mu::1']}]}]}
    key = canvas_key(m.pages[8])
    a = overlay_resolved_manifest(src, m, 'F', [key], [('json-page-14v', key)])
    assert a['pages'][0]['image']['canvas'] == key
    reordered = replace(m, pages=tuple(reversed(m.pages)))
    b = overlay_resolved_manifest(src, reordered, 'F', [key], [('json-page-14v', key)])
    assert b['pages'][0]['image']['canvas'] == key
    assert b['pages'][0]['id'] == a['pages'][0]['id']
    with pytest.raises(ValueError, match='Two synchronized pages'):
        resolve_pages([{'id':'A'},{'id':'B'}],m,explicit_links=[('A', key),('B',key)])


def test_local_copy_and_missing_copy_fallback(tmp_path):
    m = v2_manifest(8)
    raw, _ = sync_five(v2_manifest())
    raw['pages'] = [{'id':'P1', 'iiif': {'id':m.pages[4]['image']['canvas']}, 'lines':[{'line':1}]}]
    page = overlay_resolved_manifest(raw,m,'F')['pages'][0]
    image = page['image']
    directory = index_path(tmp_path,'F').parent
    directory.mkdir(parents=True)
    file = directory / ('a'*32 + '.jpg')
    file.write_bytes(b'\xff\xd8\xffimage')
    index_path(tmp_path,'F').write_text(json.dumps({'format':'varians-iiif-local-1',
        'images': {remote_key(image): {'file':file.name,'source':_request_url(image)}}}),encoding='utf8')
    cache = {'pages':[page]}
    local = apply_working_copy(cache,tmp_path,'F')['pages'][0]
    assert local['image']['type'] == 'file'
    assert local['image']['remote_iiif']['canvas'] == image['canvas']
    assert local['id'] == 'P1' and local['lines'] == page['lines']
    # Manifest reloaded with different size still recognizes the same download.
    changed = dict(image, width=999)
    assert local_image_path(tmp_path,'F',changed) == file
    file.unlink()
    missing = apply_working_copy(cache,tmp_path,'F')['pages'][0]
    assert missing['image']['type'] == 'iiif' and missing['id'] == 'P1'


def test_save_reopen_and_no_extra_tei_surfaces(tmp_path):
    m = v2_manifest()
    cache, indices = sync_five(m)
    selected = [canvas_key(m.pages[i]) for i in indices]
    w = WitnessDraft('F','Fribourg',image_source_type='iiif',image_source_value=m.source,
                     iiif_selection_mode='selected',iiif_selected_canvases=selected,
                     iiif_page_links=[(p['id'], key) for p,key in zip(cache['pages'],selected)])
    edition = tmp_path/'edition.xml'; edition.write_text('<TEI/>',encoding='utf8')
    draft = ProjectDraft('Test',edition,'fr','en',tmp_path/'i18n',tmp_path/'a.xsl',
             tmp_path/'a.css',tmp_path/'custom.xml',tmp_path/'web','view.html',[w],'F')
    from iiif_manifest import write_cache
    write_cache(cache_path(tmp_path,'F'),m.source,m.raw)
    config = load_project(write_project_xml(tmp_path/'project.xml', draft))
    loaded = config.witness_by_id['F']
    assert loaded.iiif_page_links == tuple(w.iiif_page_links)
    out = apply_witness_image_policy(cache,'iiif',m.source,tmp_path,(), 'F',
                loaded.iiif_selection_mode,loaded.iiif_selected_canvases,
                loaded.iiif_ocr_links,loaded.iiif_page_links)
    assert len(out['pages']) == 5
    assert [p['iiif_canvas_key'] for p in out['pages']] == selected
    tei = project_facsimile_pages([loaded],tmp_path,edition)
    assert len(tei) == 5 and all(p.surface_id.startswith('F-') for p in tei)


def test_two_witness_manifests_do_not_cross_link(tmp_path):
    m1 = v2_manifest(6, domain='mss-a.test')
    m2 = v2_manifest(6, domain='mss-b.test')
    a = {'pages':[{'id':'shared', 'iiif': {'id':m1.pages[2]['image']['canvas']}, 'lines':[{'line':1}]}]}
    b = {'pages':[{'id':'shared', 'iiif': {'id':m2.pages[4]['image']['canvas']}, 'lines':[{'line':1, 'base_keys':['shared::1']}]}]}
    assert overlay_resolved_manifest(a,m1,'Mu')['pages'][0]['image']['canvas'] == m1.pages[2]['image']['canvas']
    assert overlay_resolved_manifest(b,m2,'F')['pages'][0]['image']['canvas'] == m2.pages[4]['image']['canvas']
    assert overlay_resolved_manifest(a,m2,'F')['pages'][0]['image']['type'] == 'none'


def test_orphan_canvas_does_not_use_index():
    m = v2_manifest(469)
    p = {'id':'synchronization-page', 'lines':[{'line':1}]}
    data = overlay_resolved_manifest({'pages':[p]},m,'F', [canvas_key(m.pages[149])])
    assert len(data['pages']) == 1 and data['pages'][0]['image']['type'] == 'none'
    assert data['pages'][0]['id'] == p['id']


def test_web_dataset_preserves_secondary_json_links_with_469_canvas_subset(tmp_path):
    from web_viewer.generator import build_dataset
    from dataclasses import replace
    template = load_project(Path(__file__).resolve().parent / 'data' / 'exemple' / 'project.xml')
    m = v2_manifest()
    raw, indices = sync_five(m)
    # Give all secondary lines a real base key as Varians-Synchro would.
    first_base = json.loads(template.base.alignment.read_text('utf8'))['pages'][0]
    base_key = f"{first_base['id']}::{first_base['lines'][0]['line']}"
    for p in raw['pages']:
        p['lines'][0]['base_keys'] = [base_key]
    align = tmp_path / 'F.json'
    align.write_text(json.dumps(raw, ensure_ascii=False),encoding='utf8')
    selected = [canvas_key(m.pages[i]) for i in indices]
    write_cache(cache_path(tmp_path,'F'),m.source,m.raw)
    f = replace(template.witnesses[1], id='F', label='Fribourg', alignment=align,
                image_source_type='iiif', image_source_value=m.source,
                alto_source_type='auto', alto_files=(),
                iiif_selection_mode='selected', iiif_selected_canvases=tuple(selected),
                iiif_page_links=())
    project = replace(template, path=tmp_path/'project.xml',
                      witnesses=(template.base, f), base_witness=template.base.id)
    dataset, _missing = build_dataset(project)
    secondary = next(w for w in dataset['witnesses'] if w['id']=='F')
    assert secondary['line_sync']
    assert len(secondary['pages'])==5
    assert [p['image']['canvas'] for p in secondary['pages']] == selected if all('canvas' in p['image'] for p in secondary['pages']) else [p['iiif_canvas_key'] for p in secondary['pages']]==selected
    assert all(p['lines'][0]['base_keys']==[base_key] for p in secondary['pages'])
    assert all(p['id'].startswith('sync-id-') for p in secondary['pages'])


def test_legacy_all_sync_generates_only_matched_surfaces(tmp_path):
    m=v2_manifest(469)
    cache,indices=sync_five(m)
    alignment=tmp_path/'F.json'
    alignment.write_text(json.dumps(cache),encoding='utf8')
    write_cache(cache_path(tmp_path,'F'),m.source,m.raw)
    w=WitnessDraft('F','Fribourg',alignment=alignment,image_source_type='iiif',image_source_value=m.source,
                   iiif_selection_mode='all')
    generated=project_facsimile_pages([w],tmp_path,tmp_path/'edition.xml')
    assert len(generated)==5
    assert [p.surface_id for p in generated]==[f'F-p{i+1:04d}' for i in indices]


def test_remote_fallback_at_render_time_when_working_copy_removed(tmp_path):
    from image_sources import page_image_request, normalized_image_block, full_page_target
    m=v2_manifest(8)
    page={'id':'P','image':dict(m.pages[3]['image'])}
    local_path=tmp_path/'cached.jpg'
    local_path.write_bytes(b'\xff\xd8\xff')
    original=page['image']
    local={'id':'P','image':{'type':'file','path':str(local_path),'remote_iiif':original,
                           'width':4000,'height':6000}}
    request=page_image_request(local,{'x':10,'y':30,'w':50,'h':15},tmp_path)
    assert request['source_type']=='file'
    assert request['fallback_url'].startswith(original['service']+'/10,30,50,15/')
    normalized=normalized_image_block(local,tmp_path)
    assert normalized['remote_iiif']['canvas']==original['canvas']
    local_path.unlink()
    backup=page_image_request(local,None,tmp_path)
    assert backup['source_type']=='iiif' and backup['url'].startswith('https://')
    assert full_page_target(local,tmp_path)[0]=='url'


def test_manual_mapping_beats_conflicting_embedded_iiif_reference():
    m=v2_manifest(6)
    page={'id':'F-14v','iiif':{'id':m.pages[1]['image']['canvas']},'lines':[{'line':1}]}
    explicit=[('F-14v',m.pages[4]['image']['canvas'])]
    assert resolve_pages([page],m,explicit_links=explicit)[0].key==m.pages[4]['image']['canvas']


def test_duplicate_image_service_is_ambiguous_even_with_unique_label():
    m=v2_manifest(3)
    pages=list(m.pages)
    pages[1]=dict(pages[1],image=dict(pages[1]['image'],service=pages[0]['image']['service']))
    m=replace(m,pages=tuple(pages))
    p={'id':'sync-p','iiif':{'service':pages[0]['image']['service']},'label':pages[0]['label']}
    r=resolve_pages([p],m)[0]
    assert r.status=='ambiguous' and len(r.candidates)==2


def test_ocr_and_sync_same_canvas_are_one_physical_page(tmp_path):
    from alto_import import apply_witness_alto_policy
    m=v2_manifest(8)
    key=canvas_key(m.pages[4])
    p={'id':'synchro-14v', 'iiif': {'id':key},
       'lines':[{'line':1,'alto_id':'same-line', 'base_keys':['Mu::1'],
                 'bbox':{'hpos':20,'vpos':30,'width':50,'height':12}}]}
    raw={'meta':{'format':'tei-manuscript-alignment','witness':'F'}, 'pages':[p]}
    ocr=tmp_path/'image-with-other-name.xml'
    ocr.write_text('''<PcGts><Page imageFilename="old-local-copy.jpg" imageWidth="600" imageHeight="800">
      <TextRegion><TextLine id="same-line"><Coords points="20,30 80,30 80,40 20,40"/>
      <TextEquiv><Unicode>autre texte</Unicode></TextEquiv>
      </TextLine></TextRegion></Page></PcGts>''',encoding='utf8')
    overlay=apply_witness_alto_policy(raw,'files',[ocr],tmp_path,'F','secondary',strict_no_ordinal=True)
    assert len(overlay['pages'])==2
    resolved=overlay_resolved_manifest(overlay,m,'F',[key],ocr_links=[(str(ocr),key)],project_root=tmp_path)
    assert len(resolved['pages'])==1
    page=resolved['pages'][0]
    assert page['id']=='synchro-14v'
    assert page['image']['canvas']==key
    assert page['lines'][0]['line']==1 and page['lines'][0]['base_keys']==['Mu::1']
    assert page['alto_source_file']==str(ocr)
