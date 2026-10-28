from pathlib import Path
import tempfile

from alto_import import parse_layout_file, build_alto_cache, overlay_alto
from iiif_manifest import write_cache, cache_path
from iiif_local import (apply_working_copy, download_witness_copy, _request_url,
                        store_dir)
from project_management import WitnessDraft, ProjectDraft, write_project_xml
from project_config import load_project
from image_sources import apply_witness_image_policy

PAGE = '''<?xml version="1.0"?>
<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">
<Page imageFilename="SCAN_A.jpg" imageWidth="1000" imageHeight="2000">
<TextRegion id="r1"><TextLine id="p-l1"><Coords points="10,20 120,19 118,42 12,46"/>
<Baseline points="12,40 110,37"/><TextEquiv><Unicode>In principio 日本語</Unicode></TextEquiv>
</TextLine><TextLine id="p-l2"><Coords points="10,60 180,60 180,78 10,80"/>
<Word><TextEquiv><Unicode>erat</Unicode></TextEquiv></Word>
<Word><TextEquiv><Unicode>verbum</Unicode></TextEquiv></Word>
</TextLine></TextRegion></Page></PcGts>'''

ALTO = '''<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#"><Layout>
<Page ID="A2" WIDTH="1000" HEIGHT="2000"><PrintSpace><TextBlock>
<TextLine ID="a-l1" HPOS="20" VPOS="30" WIDTH="40" HEIGHT="15"><String CONTENT="test"/></TextLine>
</TextBlock></PrintSpace></Page></Layout></alto>'''


def test_page_polygons_unicode_baseline_and_word_fallback(tmp_path):
    path = tmp_path/'folio.page.xml'; path.write_text(PAGE, encoding='utf-8')
    parsed = parse_layout_file(path)
    pg = parsed.pages[0]
    assert pg['alto_source_image'] == 'SCAN_A.jpg'
    assert (pg['alto_width'], pg['alto_height']) == (1000, 2000)
    l1, l2 = pg['lines']
    assert l1['alto_id'] == 'p-l1' and l1['alto'] == 'In principio 日本語'
    assert l1['bbox']['hpos'] == 10 and l1['bbox']['vpos'] == 19
    assert l1['polygon'] == [[10, 20], [120, 19], [118, 42], [12, 46]]
    assert l1['baseline'] == [[12, 40], [110, 37]]
    assert l2['alto'] == 'erat verbum'


def test_one_witness_mixes_page_and_alto_without_losing_existing_sync(tmp_path):
    p = tmp_path/'page.xml'; p.write_text(PAGE, encoding='utf-8')
    a = tmp_path/'alto.xml'; a.write_text(ALTO, encoding='utf-8')
    mixed = build_alto_cache([p, a], 'W')
    assert len(mixed['pages']) == 2
    assert mixed['pages'][0]['lines'][0]['polygon']
    assert mixed['pages'][1]['lines'][0]['alto_id'] == 'a-l1'
    existing = {'pages': [{'id': 'stable-page', 'label': 'SCAN_A', 'lines': [
        {'line': 1, 'alto_id': 'p-l1', 'base_keys': ['P1::4'], 'corrected': 'old'}]}]}
    output = overlay_alto(existing, mixed)
    assert output['pages'][0]['id'] == 'stable-page'
    assert output['pages'][0]['lines'][0]['base_keys'] == ['P1::4']
    assert output['pages'][0]['lines'][0]['polygon'] == mixed['pages'][0]['lines'][0]['polygon']


def test_unsupported_document_does_not_silently_parse(tmp_path):
    p = tmp_path/'unknown.xml'; p.write_text('<not-an-ocr-document/>')
    import pytest
    with pytest.raises(ValueError, match='Unsupported'):
        parse_layout_file(p)


def _manifest():
    return {'@context': 'http://iiif.io/api/presentation/2/context.json',
      'sequences': [{'canvases': [
         {'@id':'https://example.test/canvas/1','label':'1r','width':1000,'height':2000,
          'images':[{'resource': {'@id':'https://example.test/1.jpg',
            'width':1000,'height':2000,
            'service': {'@id':'https://example.test/iiif/1','profile':'http://iiif.io/api/image/2/level2.json'}}}]},
         {'@id':'https://example.test/canvas/2','label':'1v', 'width':1000,'height':2000,
          'images':[{'resource': {'@id':'https://example.test/2.jpg','width':1000,'height':2000}}]}
      ]}]}


def test_iiif_local_copy_resume_override_and_preserve_remote(tmp_path, monkeypatch):
    from iiif_manifest import read_cache
    src='https://example.test/manifest.json'
    write_cache(cache_path(tmp_path, 'W'), src, _manifest())
    m = read_cache(cache_path(tmp_path, 'W'), src)
    requests=[]
    def fake_fetch(url, stem):
        requests.append(url)
        destination=stem.with_suffix('.jpg')
        destination.write_bytes(b'\xff\xd8\xff\x00')
        return destination
    monkeypatch.setattr('iiif_local._fetch_image', fake_fetch)
    result=download_witness_copy(tmp_path, 'W', src)
    assert result['downloaded']==2 and not result['failed']
    assert requests==['https://example.test/iiif/1/full/full/0/default.jpg',
                      'https://example.test/2.jpg']
    second=download_witness_copy(tmp_path, 'W', src)
    assert second['skipped']==2 and len(requests)==2
    base={'pages': [dict(pg) for pg in m.pages]}
    copied=apply_working_copy(base, tmp_path, 'W')
    assert all(pg['image']['type']=='file' for pg in copied['pages'])
    assert base['pages'][0]['image']['type']=='iiif'
    assert copied['pages'][0]['image']['remote_iiif']['service'].endswith('/iiif/1')
    assert Path(copied['pages'][0]['image']['path']).is_file()
    assert copied['pages'][0]['lines']==[]
    assert len(list(store_dir(tmp_path, 'W').glob('*.jpg')))==2


def test_iiif_partial_copy_does_not_erase_cached_images(tmp_path, monkeypatch):
    src='https://example.test/manifest.json'
    write_cache(cache_path(tmp_path,'W'),src,_manifest())
    downloaded=[]
    def partial(url,stem):
        downloaded.append(url)
        if len(downloaded)>1:
            raise OSError('503 temporary outage')
        dest=stem.with_suffix('.png');dest.write_bytes(b'\x89PNG\r\n\x1a\n')
        return dest
    monkeypatch.setattr('iiif_local._fetch_image',partial)
    report=download_witness_copy(tmp_path,'W',src)
    assert report['downloaded']==1 and len(report['failed'])==1
    manifest=apply_witness_image_policy({'pages':[]},'iiif',src,tmp_path,[],'W')
    cached=apply_working_copy(manifest,tmp_path,'W')
    assert cached['pages'][0]['image']['type']=='file'
    assert cached['pages'][1]['image']['type']=='iiif'  # hybrid fallback
    more=download_witness_copy(tmp_path,'W',src,progress=lambda index,total,label:index==0)
    assert more['skipped']==1 and more['cancelled']
    assert cached['pages'][0]['image']['type']=='file'


def test_roundtrip_project_flags_by_witness(tmp_path):
    xml=tmp_path/'edition.xml';xml.write_text('<TEI/>')
    project=ProjectDraft('Test',xml,'fr','en',tmp_path/'i18n',tmp_path/'xsl',
        tmp_path/'css',tmp_path/'custom',tmp_path/'web','viewer.html',[
          WitnessDraft('A','A',role='base',image_source_type='iiif',
                       image_source_value='https://example.test/m.json',
                       iiif_local_copy=True,iiif_web_local_copy=False),
          WitnessDraft('B','B',image_source_type='iiif',
                       image_source_value='https://example.test/m2.json',
                       iiif_local_copy=False,iiif_web_local_copy=True)
        ],'A', xslt_mode='file',schema_mode='none')
    filename=write_project_xml(tmp_path/'project.xml',project)
    source=filename.read_text(encoding='utf-8')
    assert 'localCopy="true"' in source and 'webLocalCopy="true"' in source
    loaded=load_project(filename)
    assert (loaded.witness_by_id['A'].iiif_local_copy,loaded.witness_by_id['A'].iiif_web_local_copy)==(True,False)
    assert (loaded.witness_by_id['B'].iiif_local_copy,loaded.witness_by_id['B'].iiif_web_local_copy)==(False,True)


def test_web_export_option_overrides_desktop_choice_independently(tmp_path, monkeypatch):
    """The web generator must NOT inherit the Qt working-copy preference."""
    from dataclasses import replace
    from iiif_manifest import read_cache
    from web_viewer.generator import build_dataset, package_local_images
    from project_config import load_project
    from pathlib import Path

    package_root=Path(__file__).resolve().parents[1]
    original=load_project(package_root/'tests'/'data'/'exemple'/'project.xml')
    witness=original.base
    manifest_url='https://example.test/manifest.json'
    w=replace(witness, alignment=None, image_source_type='iiif',
              image_source_value=manifest_url, iiif_local_copy=True,
              iiif_web_local_copy=False, alto_source_type='auto', alto_files=())
    project=replace(original, path=tmp_path/'project.xml', witnesses=(w,),
                    base_witness=w.id, web_output_dir=tmp_path/'web_output')
    write_cache(cache_path(tmp_path, w.id),manifest_url,_manifest())
    def fake_fetch(url,stem):
        dest=stem.with_suffix('.jpg')
        dest.write_bytes(b'\xff\xd8\xff\x00')
        return dest
    monkeypatch.setattr('iiif_local._fetch_image',fake_fetch)
    download_witness_copy(tmp_path,w.id,manifest_url)

    remote_dataset,_=build_dataset(project)
    remote_pages=remote_dataset['witnesses'][0]['pages']
    assert remote_pages[0]['image']['type']=='iiif'  # despite desktop local

    local_project=replace(project,witnesses=(replace(w,iiif_local_copy=False,
                                                  iiif_web_local_copy=True),))
    local_dataset,_=build_dataset(local_project)
    local_pages=local_dataset['witnesses'][0]['pages']
    assert local_pages[0]['image']['type']=='file'  # despite desktop remote
    package_local_images(local_dataset,local_project,tmp_path/'export')
    local_path=tmp_path/'export'/local_pages[0]['image']['path']
    assert local_path.exists() and local_path.parent.name==w.id
    assert local_pages[0]['image']['path'].startswith('images/')
