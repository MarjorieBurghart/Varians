"""Regression tests for selective, resumable IIIF downloads without Qt/network."""
import threading
from pathlib import Path

from iiif_manifest import cache_path, write_cache, read_cache
from iiif_local import plan_witness_copy, download_witness_copy, apply_working_copy
from iiif_selection import select_ocr_pages
from project_management import WitnessDraft, ProjectDraft, write_project_xml
from project_config import load_project


def manifest(*labels):
    return {'sequences': [{'canvases': [{
        '@id': f'https://iiif.example/canvas/{i}',
        'label': label,
        'images': [{'resource': {'@id': f'https://iiif.example/img/{i}.jpg'}}],
        'width': 400, 'height': 600,
    } for i, label in enumerate(labels, 1)]}]}


def page(path, image):
    path.write_text(f'''<?xml version="1.0"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
<Page imageFilename="{image}" imageWidth="400" imageHeight="600">
<TextRegion id="r"><TextLine id="l"><Coords points="1,1 2,1 2,3 1,3"/></TextLine></TextRegion>
</Page></PcGts>''', encoding='utf-8')
    return path


def alto(path, image):
    path.write_text(f'''<alto><Description><sourceImageInformation><fileName>{image}</fileName>
</sourceImageInformation></Description><Layout><Page WIDTH="400" HEIGHT="600"/>
</Layout></alto>''', encoding='utf-8')
    return path


def test_select_only_pages_matching_page_and_alto_without_ordinal_guess(tmp_path):
    from project_management import AltoFileDraft
    src = 'https://iiif.example/manifest.json'
    write_cache(cache_path(tmp_path,'W'), src, manifest('Cover','f. 1r', 'f. 1v','f. 2r','Back cover'))
    layouts = [AltoFileDraft(page(tmp_path/'P.xml','Assisi541-test-1r.jpg'), ''),
               AltoFileDraft(alto(tmp_path/'A.xml','Assisi541-test-2r.jpg'), '')]
    plan=plan_witness_copy(tmp_path,'W',src,scope='ocr',layout_files=layouts)
    assert plan['total_pages']==5 and plan['indices']==[1,3]
    assert plan['excluded']==3 and plan['cached']==0
    urls=[]
    def fake(url, dest):
        urls.append(url)
        path=dest.with_suffix('.jpg');path.write_bytes(b'\xff\xd8\xffx')
        return path
    import iiif_local
    old=iiif_local._fetch_image
    iiif_local._fetch_image=fake
    try:
        stats=download_witness_copy(tmp_path,'W',src,scope='ocr',layout_files=layouts)
        assert stats['downloaded']==2 and stats['total']==2
        assert urls==['https://iiif.example/img/2.jpg','https://iiif.example/img/4.jpg']
        cached=apply_working_copy({'pages':list(read_cache(cache_path(tmp_path,'W'),src).pages)},tmp_path,'W')
        assert [x['image']['type'] for x in cached['pages']]==['iiif','file','iiif','file','iiif']
        second=download_witness_copy(tmp_path,'W',src,scope='ocr',layout_files=layouts)
        assert second['skipped']==2 and len(urls)==2
    finally:
        iiif_local._fetch_image=old


def test_missing_ocr_never_downloads_all_pages(tmp_path, monkeypatch):
    src='https://iiif.example/manifest.json'
    write_cache(cache_path(tmp_path,'W'),src,manifest('1r','1v'))
    monkeypatch.setattr('iiif_local._fetch_image', lambda *_: (_ for _ in ()).throw(AssertionError('network')))
    plan=plan_witness_copy(tmp_path,'W',src,scope='ocr')
    assert plan['total']==0 and plan['excluded']==2
    assert download_witness_copy(tmp_path,'W',src,scope='ocr')['downloaded']==0


def test_ambiguous_labels_and_unknown_pages_are_skipped(tmp_path):
    from project_management import AltoFileDraft
    layouts=[AltoFileDraft(page(tmp_path/'1r.xml','P-1r.jpg'),''),
             AltoFileDraft(page(tmp_path/'2r.xml','P-2r.jpg'),'')]
    pages=list(read_cache(_write(tmp_path,manifest('1r','1r','2v')), 'source').pages)
    matches,warnings=select_ocr_pages(pages,layouts)
    assert matches==set() and len(warnings)==2
    assert any('ambiguous' in s or 'multiple' in s for s in warnings)


def _write(tmp_path, raw):
    dest=cache_path(tmp_path,'W')
    write_cache(dest,'source',raw)
    return dest


def test_cancel_before_first_image_keeps_manifest_and_existing_cache(tmp_path, monkeypatch):
    src='https://iiif.example/m.json'
    write_cache(cache_path(tmp_path,'W'),src,manifest('1r','1v'))
    stop=threading.Event();stop.set()
    monkeypatch.setattr('iiif_local._fetch_image',lambda *_: (_ for _ in ()).throw(AssertionError('network')))
    result=download_witness_copy(tmp_path,'W',src,cancel_event=stop)
    assert result['cancelled'] and result['downloaded']==0


def test_scope_is_persistent_and_backward_compatible(tmp_path):
    xml=tmp_path/'edition.xml';xml.write_text('<TEI/>')
    drafts=[WitnessDraft('A','A',role='base',image_source_type='iiif',
                 image_source_value='https://iiif.example/a',iiif_local_copy=True,
                 iiif_download_scope='ocr'),
            WitnessDraft('B','B',image_source_type='iiif',
                 image_source_value='https://iiif.example/b')]
    draft=ProjectDraft('Test',xml,'fr','en',tmp_path/'i18n',tmp_path/'xsl',
        tmp_path/'css',tmp_path/'custom',tmp_path/'web','viewer.html',drafts,'A',
        xslt_mode='file',schema_mode='none')
    path=write_project_xml(tmp_path/'project.xml',draft)
    assert 'downloadScope="ocr"' in path.read_text()
    project=load_project(path)
    assert project.witness_by_id['A'].iiif_download_scope=='ocr'
    assert project.witness_by_id['B'].iiif_download_scope=='all'
    # Older 0.8.5.1 projects contain no downloadScope attribute.
    assert project.witness_by_id['B'].iiif_local_copy is False


def test_explicit_full_mode_retains_existing_behavior(tmp_path,monkeypatch):
    src='https://iiif.example/m.json'
    write_cache(cache_path(tmp_path,'W'),src,manifest('cover','1r'))
    downloaded=[]
    def fake(url,stem):
        downloaded.append(url)
        p=stem.with_suffix('.png');p.write_bytes(b'\x89PNG\r\n\x1a\n');return p
    monkeypatch.setattr('iiif_local._fetch_image',fake)
    result=download_witness_copy(tmp_path,'W',src,scope='all')
    assert result['downloaded']==2 and result['excluded']==0
    assert len(downloaded)==2
