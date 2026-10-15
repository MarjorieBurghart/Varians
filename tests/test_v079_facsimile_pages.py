from pathlib import Path
import tempfile
import xml.etree.ElementTree as ET

from project_management import LocalImageDraft, WitnessDraft, ProjectDraft, write_project_xml
from project_config import load_project
from image_sources import apply_witness_image_policy, page_navigation_items, display_window_indices
from alto_import import build_alto_cache
from tei_facsimile import (
    FacsimilePage, default_surface_id, facsimile_ref_at_position,
    project_facsimile_pages, sync_facsimile_text, upsert_pb_at_position, position_inside_xml_markup,
)
from web_viewer.legacy_v11_core import extract_reading_document

TEI = 'http://www.tei-c.org/ns/1.0'
XML = 'http://www.w3.org/XML/1998/namespace'

ALTO_TMPL = '''<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description><sourceImageInformation><fileName>{image}</fileName></sourceImageInformation></Description>
  <Layout><Page ID="{page}" WIDTH="1000" HEIGHT="2000"><PrintSpace>
    <TextBlock><TextLine ID="{line}" HPOS="10" VPOS="20" WIDTH="300" HEIGHT="40">
      <String CONTENT="{word}"/>
    </TextLine></TextBlock>
  </PrintSpace></Page></Layout>
</alto>'''


def minimal_tei(body='<p>Texte</p>'):
    return f'''<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc></teiHeader><text><body>{body}</body></text></TEI>'''


def test_pb_insert_includes_n_and_facs():
    src = minimal_tei('<p>abc</p>')
    pos = src.index('abc')
    out, newpos, mode = upsert_pb_at_position(src, pos, 'f. 1v', 'A1-p0002')
    assert mode == 'inserted'
    assert '<pb n="f. 1v" facs="#A1-p0002"/>' in out
    assert newpos > pos
    ET.fromstring(out)


def test_cursor_immediately_after_pb_inserts_instead_of_replacing():
    src = minimal_tei('<p><pb n="1r" facs="#A1-p0001"/></p>')
    previous = '<pb n="1r" facs="#A1-p0001"/>'
    pos = src.index(previous) + len(previous)
    out, _, mode = upsert_pb_at_position(src, pos, '1r', 'B1-p0001')
    assert mode == 'inserted'
    assert previous in out
    assert previous + '<pb n="1r" facs="#B1-p0001"/>' in out
    ET.fromstring(out)


def test_cursor_immediately_before_pb_inserts_instead_of_replacing():
    previous = '<pb n="1r" facs="#A1-p0001"/>'
    src = minimal_tei(f'<p>{previous}</p>')
    pos = src.index(previous)
    out, _, mode = upsert_pb_at_position(src, pos, '1r', 'B1-p0001')
    assert mode == 'inserted'
    assert '<pb n="1r" facs="#B1-p0001"/>' + previous in out
    ET.fromstring(out)


def test_cursor_strictly_inside_pb_is_blocked_without_change():
    previous = '<pb n="1r" facs="#A1-p0001"/>'
    src = minimal_tei(f'<p>{previous}</p>')
    pos = src.index('facs="#A1-p0001"') + 3
    out, newpos, mode = upsert_pb_at_position(src, pos, '1v', 'B1-p0002')
    assert mode == 'blocked'
    assert out == src
    assert newpos == pos
    ET.fromstring(out)


def test_cursor_inside_any_opening_tag_is_blocked():
    src = minimal_tei('<p xml:id="p1">abc</p>')
    pos = src.index('xml:id') + 2
    assert position_inside_xml_markup(src, pos)
    out, _, mode = upsert_pb_at_position(src, pos, '1r', 'A1-p0001')
    assert mode == 'blocked'
    assert out == src


def test_cursor_inside_closing_tag_is_blocked():
    src = minimal_tei('<p>abc</p>')
    pos = src.index('</p>') + 2
    assert position_inside_xml_markup(src, pos)
    out, _, mode = upsert_pb_at_position(src, pos, '1r', 'A1-p0001')
    assert mode == 'blocked'
    assert out == src


def test_cursor_adjacent_to_other_tag_is_allowed():
    src = minimal_tei('<p><hi>abc</hi></p>')
    before = src.index('<hi>')
    after = src.index('</hi>') + len('</hi>')
    for pos in (before, after):
        assert not position_inside_xml_markup(src, pos)
        out, _, mode = upsert_pb_at_position(src, pos, '1r', 'A1-p0001')
        assert mode == 'inserted'
        ET.fromstring(out)


def test_cursor_page_comes_from_last_preceding_pb_facs():
    src = minimal_tei('<p><pb n="1r" facs="#A1-p0001"/>aaa<pb n="1v" facs="#A1-p0002"/>bbb</p>')
    assert facsimile_ref_at_position(src, src.index('aaa') + 2) == 'A1-p0001'
    assert facsimile_ref_at_position(src, src.index('bbb') + 2) == 'A1-p0002'


def test_facsimile_is_created_before_text_and_keeps_valid_tei():
    src = minimal_tei()
    pages = [
        FacsimilePage('A1','A1-p0001','f. 1r','../images/A1/001.jpg'),
        FacsimilePage('A1','A1-p0002','f. 1v','../images/A1/002.jpg'),
    ]
    out, report = sync_facsimile_text(src, pages)
    assert report.added == ['A1-p0001','A1-p0002']
    assert out.index('<facsimile>') < out.index('<text>')
    root = ET.fromstring(out)
    surfaces = root.findall(f'{{{TEI}}}facsimile/{{{TEI}}}surface')
    assert [s.get(f'{{{XML}}}id') for s in surfaces] == ['A1-p0001','A1-p0002']
    assert [s.get('n') for s in surfaces] == ['f. 1r','f. 1v']


def test_existing_facsimile_zone_is_never_rebuilt_or_deleted():
    src = f'''<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc></teiHeader><facsimile><surface xml:id="A1-p0001" n="manuellement enrichi"><graphic url="old.jpg"/><zone xml:id="z1" ulx="1"/></surface><surface xml:id="orphan"><graphic url="keep.jpg"/></surface></facsimile><text><body><p>x</p></body></text></TEI>'''
    pages = [
        FacsimilePage('A1','A1-p0001','f. 1r','new.jpg'),
        FacsimilePage('A1','A1-p0002','f. 1v','two.jpg'),
    ]
    out, report = sync_facsimile_text(src, pages, {'A1-p0001':'ancien libellé'})
    root = ET.fromstring(out)
    s1 = root.find(f'.//{{{TEI}}}surface[@{{{XML}}}id="A1-p0001"]')
    assert s1 is not None
    assert s1.get('n') == 'manuellement enrichi'  # édition manuelle préservée
    assert s1.find(f'{{{TEI}}}graphic').get('url') == 'old.jpg'  # URL manuelle préservée
    assert s1.find(f'{{{TEI}}}zone') is not None
    assert root.find(f'.//{{{TEI}}}surface[@{{{XML}}}id="orphan"]') is not None
    assert root.find(f'.//{{{TEI}}}surface[@{{{XML}}}id="A1-p0002"]') is not None
    assert 'A1-p0002' in report.added


def test_label_change_updates_only_untouched_generated_surface_and_pb():
    src = f'''<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc></teiHeader><facsimile><surface xml:id="A1-p0001" n="f. 1r"><graphic url="a.jpg"/></surface><surface xml:id="A1-p0002" n="custom surface"><graphic url="b.jpg"/></surface></facsimile><text><body><p><pb n="f. 1r" facs="#A1-p0001"/>a<pb n="custom pb" facs="#A1-p0002"/>b</p></body></text></TEI>'''
    pages = [
        FacsimilePage('A1','A1-p0001','fol. 1r','a.jpg'),
        FacsimilePage('A1','A1-p0002','fol. 1v','b.jpg'),
    ]
    out, report = sync_facsimile_text(src, pages, {'A1-p0001':'f. 1r','A1-p0002':'f. 1v'})
    assert 'xml:id="A1-p0001" n="fol. 1r"' in out
    assert '<pb n="fol. 1r" facs="#A1-p0001"/>' in out
    assert 'xml:id="A1-p0002" n="custom surface"' in out
    assert '<pb n="custom pb" facs="#A1-p0002"/>' in out
    assert 'A1-p0001' in report.labels_updated


def test_malformed_xml_is_never_modified():
    src = '<TEI><text><body><p>oops</body></text></TEI>'
    out, report = sync_facsimile_text(src, [FacsimilePage('A','A-p0001','1r','a.jpg')])
    assert out == src
    assert report.changed is False
    assert report.conflicts


def test_three_images_plus_three_alto_stay_in_full_page_navigation_mode():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        images=[]; altos=[]
        for i in range(3):
            img = root/f'IMG_{i+1}.jpg'; img.write_bytes(b'img')
            images.append(LocalImageDraft(img, f'f. {i+1}r', surface_id=f'A1-p{i+1:04d}'))
            alto = root/f'a{i+1}.xml'
            alto.write_text(ALTO_TMPL.format(image=img.name,page=f'P{i+1}',line=f'L{i+1}',word='x'),encoding='utf-8')
            altos.append(alto)
        cache = build_alto_cache(altos, 'A1', 'base')
        merged = apply_witness_image_policy(cache,'files',None,root,images,'A1')
        items = page_navigation_items(merged,root)
        assert len(items) == 3
        assert all(it['l']['_page_mode'] for it in items)
        assert [display_window_indices(items,i) for i in range(3)] == [[0],[1],[2]]
        assert [it['p']['tei_surface_id'] for it in items] == ['A1-p0001','A1-p0002','A1-p0003']
        assert all(len(it['p']['lines']) == 1 for it in items)  # ALTO conservé comme géométrie


def test_project_xml_roundtrip_preserves_stable_surface_ids():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        for d in ('xml','rendering','i18n','web_output'): (root/d).mkdir()
        (root/'xml'/'edition.xml').write_text(minimal_tei(),encoding='utf-8')
        (root/'rendering'/'tei.css').write_text('',encoding='utf-8')
        (root/'rendering'/'custom-elements.xml').write_text('<customElements/>',encoding='utf-8')
        img=root/'a.jpg'; img.write_bytes(b'x')
        w=WitnessDraft('A1','A1',None,'base','files',None,[LocalImageDraft(img,'f. 1r',surface_id='A1-p0042')])
        draft=ProjectDraft('T',root/'xml'/'edition.xml','fr','en',root/'i18n',root/'rendering'/'tei-to-html.xsl',root/'rendering'/'tei.css',root/'rendering'/'custom-elements.xml',root/'web_output','viewer.html',[w],'A1',xslt_mode='builtin',schema_mode='none')
        path=write_project_xml(root/'project.xml',draft)
        cfg=load_project(path)
        assert cfg.base.image_files[0].surface_id == 'A1-p0042'
        assert 'surface="A1-p0042"' in path.read_text(encoding='utf-8')


def test_project_facsimile_pages_uses_saved_surface_and_relative_graphic():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/'xml').mkdir(); (root/'images'/'A1').mkdir(parents=True)
        edition=root/'xml'/'edition.xml'; edition.write_text(minimal_tei(),encoding='utf-8')
        img=root/'images'/'A1'/'001.jpg'; img.write_bytes(b'x')
        w=WitnessDraft('A1','A1',None,'base','files',None,[LocalImageDraft(img,'f. 1r',surface_id='A1-p0001')])
        pages=project_facsimile_pages([w],root,edition)
        assert len(pages)==1
        assert pages[0].surface_id=='A1-p0001'
        assert pages[0].label=='f. 1r'
        assert pages[0].graphic_url=='../images/A1/001.jpg'


def test_web_reading_document_keeps_pb_facs():
    with tempfile.TemporaryDirectory() as td:
        p=Path(td)/'edition.xml'
        p.write_text(minimal_tei('<p><pb n="f. 1r" facs="#A1-p0001"/>abc</p>'),encoding='utf-8')
        doc=extract_reading_document(p,'#A1')
        pbs=[s for b in doc['blocks'] for s in b.get('segments',[]) if s.get('kind')=='pb']
        assert pbs and pbs[0]['facs']=='#A1-p0001'
        assert pbs[0]['label']=='f. 1r'


def test_static_editor_and_web_viewer_have_page_mode_hooks():
    root=Path(__file__).resolve().parents[1]
    editor=(root/'editeur_tei.py').read_text(encoding='utf-8')
    web=(root/'web_viewer'/'generator.py').read_text(encoding='utf-8')
    dialogs=(root/'project_dialogs.py').read_text(encoding='utf-8')
    assert 'markPageRequested = Signal(str, str, str)' in editor
    assert 'page_navigation_items(cache, self.project.root_dir)' in editor
    assert '_sync_page_panels_to_cursor' in editor
    assert 'project.witness.local_images.surface' in dialogs
    assert 'data-facs' in web
    assert 'pageMode=!lineMode||!w.line_sync' in web
    assert 'if(pageMode)' in web and 'VariansIIIF.plan(source,r,full' in web

def test_existing_prefixed_facsimile_is_reused_not_duplicated():
    src = f'''<TEI xmlns="{TEI}" xmlns:t="{TEI}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc></teiHeader><t:facsimile><t:surface xml:id="A1-p0001" n="1r"><t:graphic url="a.jpg"/></t:surface></t:facsimile><text><body><p>x</p></body></text></TEI>'''
    out, report = sync_facsimile_text(src, [
        FacsimilePage('A1','A1-p0001','1r','a.jpg'),
        FacsimilePage('A1','A1-p0002','1v','b.jpg'),
    ])
    root = ET.fromstring(out)
    facs = root.findall(f'{{{TEI}}}facsimile')
    assert len(facs) == 1
    assert root.find(f'.//{{{TEI}}}surface[@{{{XML}}}id="A1-p0002"]') is not None
    assert out.count('facsimile>') == 2  # one opening + one closing, no duplicate block
    assert 'A1-p0002' in report.added


def test_mark_page_ui_blocks_inside_markup_before_facsimile_sync():
    root=Path(__file__).resolve().parents[1]
    editor=(root/'editeur_tei.py').read_text(encoding='utf-8')
    start=editor.index('def _mark_page_in_tei')
    chunk=editor[start:start+2600]
    assert 'position_inside_xml_markup(old, original_pos)' in chunk
    assert chunk.index('position_inside_xml_markup(old, original_pos)') < chunk.index('sync_facsimile_text')
    assert 'manuscript.mark_page.inside_tag' in chunk
