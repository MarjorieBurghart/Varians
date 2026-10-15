from pathlib import Path
import tempfile

from alto_import import parse_alto_file, build_alto_cache, overlay_alto, apply_witness_alto_policy
from project_management import (
    WitnessDraft, AltoFileDraft, ProjectDraft, write_project_xml,
    prepare_alto_files_for_project,
)
from project_config import load_project

ALTO = '''<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description><sourceImageInformation><fileName>IMG_0001.jpg</fileName></sourceImageInformation></Description>
  <Layout><Page ID="P1" WIDTH="1000" HEIGHT="2000"><PrintSpace>
    <TextBlock><TextLine ID="L1" HPOS="10" VPOS="20" WIDTH="300" HEIGHT="40">
      <String CONTENT="In"/><SP/><String CONTENT="principio"/>
    </TextLine>
    <TextLine ID="L2" HPOS="10" VPOS="70" WIDTH="330" HEIGHT="40">
      <String CONTENT="erat"/><SP/><String CONTENT="verbum"/>
    </TextLine></TextBlock>
  </PrintSpace></Page></Layout>
</alto>'''


def _write_alto(path: Path, text=ALTO):
    path.write_text(text, encoding='utf-8')
    return path


def test_parse_alto_page_lines_bbox_and_text():
    with tempfile.TemporaryDirectory() as td:
        p = _write_alto(Path(td)/'p1.xml')
        parsed = parse_alto_file(p)
        assert parsed.source_image == 'IMG_0001.jpg'
        assert len(parsed.pages) == 1
        page = parsed.pages[0]
        assert page['id'] == 'P1'
        assert page['alto_width'] == 1000 and page['alto_height'] == 2000
        assert page['lines'][0]['alto_id'] == 'L1'
        assert page['lines'][0]['alto'] == 'In principio'
        assert page['lines'][1]['bbox']['vpos'] == 70


def test_overlay_alto_preserves_page_id_and_base_keys():
    with tempfile.TemporaryDirectory() as td:
        p = _write_alto(Path(td)/'p1.xml')
        imported = build_alto_cache([p], 'B')
        existing = {'meta': {'witness':'B'}, 'pages':[{
            'id':'page-001', 'label':'IMG_0001',
            'lines':[
                {'line':12,'alto_id':'L1','base_keys':['base::1'],'score':0.9,'bbox':{'hpos':0,'vpos':0,'width':1,'height':1}},
                {'line':13,'alto_id':'L2','base_keys':['base::2']},
            ]
        }]}
        out = overlay_alto(existing, imported)
        page = out['pages'][0]
        assert page['id'] == 'page-001'
        assert page['alto_width'] == 1000
        assert page['lines'][0]['line'] == 12
        assert page['lines'][0]['alto'] == 'In principio'
        assert page['lines'][0]['base_keys'] == ['base::1']
        assert page['lines'][0]['score'] == 0.9


def test_project_xml_roundtrip_separate_alto_files():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        for d in ('xml','rendering','i18n','web_output'): (root/d).mkdir()
        (root/'xml'/'edition.xml').write_text('<TEI/>',encoding='utf-8')
        (root/'rendering'/'tei.css').write_text('',encoding='utf-8')
        (root/'rendering'/'custom-elements.xml').write_text('<customElements/>',encoding='utf-8')
        alto_dir=root/'alto'/'A'; alto_dir.mkdir(parents=True)
        a=_write_alto(alto_dir/'001.xml')
        w=WitnessDraft('A','A',None,'base',alto_source_type='files',alto_files=[AltoFileDraft(a,'f. 1r')])
        d=ProjectDraft('T',root/'xml'/'edition.xml','fr','en',root/'i18n',root/'rendering'/'tei-to-html.xsl',root/'rendering'/'tei.css',root/'rendering'/'custom-elements.xml',root/'web_output','viewer.html',[w],'A',xslt_mode='builtin',schema_mode='none')
        pp=write_project_xml(root/'project.xml',d)
        txt=pp.read_text(encoding='utf-8')
        assert '<alto type="files">' in txt
        assert 'file="alto/A/001.xml"' in txt
        cfg=load_project(pp)
        assert cfg.base.alto_source_type == 'files'
        assert cfg.base.alto_files[0].path == a.resolve()
        assert cfg.base.alto_files[0].label == 'f. 1r'


def test_prepare_alto_copy_and_reference():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); project=root/'project'; project.mkdir(); srcdir=root/'src'; srcdir.mkdir()
        a=_write_alto(srcdir/'a.xml')
        w=WitnessDraft('A','A',None,'base',alto_source_type='files',alto_files=[AltoFileDraft(a,'1r')],alto_import_mode='copy')
        out=prepare_alto_files_for_project(project,[w])[0]
        assert out.alto_files[0].path.is_file()
        assert project/'alto'/'A' in out.alto_files[0].path.parents
        ref=WitnessDraft('B','B',None,'secondary',alto_source_type='files',alto_files=[AltoFileDraft(a,'x')],alto_import_mode='reference')
        out2=prepare_alto_files_for_project(project,[ref])[0]
        assert out2.alto_files[0].path == a.resolve()


def test_alto_without_alignment_creates_line_cache():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); p=_write_alto(root/'p1.xml')
        out=apply_witness_alto_policy({'meta':{'witness':'A'},'pages':[]},'files',[p],root,'A','base')
        assert len(out['pages']) == 1
        assert len(out['pages'][0]['lines']) == 2
        assert out['pages'][0]['lines'][1]['alto'] == 'erat verbum'


def test_alto_and_local_images_are_matched_by_source_filename_before_order():
    from image_sources import apply_witness_image_policy
    from project_management import LocalImageDraft
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        a1=_write_alto(root/'a1.xml', ALTO.replace('IMG_0001.jpg','IMG_A.jpg').replace('ID="P1"','ID="PA"'))
        a2=_write_alto(root/'a2.xml', ALTO.replace('IMG_0001.jpg','IMG_B.jpg').replace('ID="P1"','ID="PB"').replace('ID="L1"','ID="L1B"').replace('ID="L2"','ID="L2B"'))
        cache=build_alto_cache([a1,a2],'A','base')
        img_a=root/'IMG_A.jpg'; img_b=root/'IMG_B.jpg'; img_a.write_bytes(b'a'); img_b.write_bytes(b'b')
        # Intentionally reversed: filename matching must beat list order.
        out=apply_witness_image_policy(cache,'files',None,root,[LocalImageDraft(img_b,'IMG_B'),LocalImageDraft(img_a,'IMG_A')])
        assert Path(out['pages'][0]['image']['path']).name == 'IMG_A.jpg'
        assert Path(out['pages'][1]['image']['path']).name == 'IMG_B.jpg'
