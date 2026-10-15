from pathlib import Path
import tempfile

from project_management import (
    WitnessDraft, LocalImageDraft, ProjectDraft,
    write_project_xml, prepare_local_images_for_project, create_new_transcription_project,
)
from project_config import load_project
from image_sources import apply_witness_image_policy, page_image_source, page_image_request, image_only_items


def _tiny_png(path: Path):
    # PNG 1x1 transparent
    path.write_bytes(bytes.fromhex(
        '89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489'
        '0000000d49444154789c6360000000020001e221bc330000000049454e44ae426082'
    ))


def test_project_xml_roundtrip_local_images():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for d in ('xml','rendering','i18n','web_output'):
            (root/d).mkdir()
        (root/'xml'/'edition.xml').write_text('<TEI/>', encoding='utf-8')
        (root/'rendering'/'tei.css').write_text('', encoding='utf-8')
        (root/'rendering'/'custom-elements.xml').write_text('<customElements/>', encoding='utf-8')
        i1 = root/'images'/'A'/'0001_a.jpg'; i1.parent.mkdir(parents=True); i1.write_bytes(b'x')
        i2 = root/'images'/'A'/'0002_b.jpg'; i2.write_bytes(b'y')
        w = WitnessDraft('A','Witness A',None,'base','files',None,[
            LocalImageDraft(i1,'f. 1r'), LocalImageDraft(i2,'f. 1v')
        ])
        draft = ProjectDraft(
            title='Test', edition=root/'xml'/'edition.xml', language='fr', fallback_language='en',
            translations_dir=root/'i18n', xslt=root/'rendering'/'tei-to-html.xsl',
            css=root/'rendering'/'tei.css', custom_elements=root/'rendering'/'custom-elements.xml',
            web_output_dir=root/'web_output', web_filename='viewer.html', witnesses=[w], base_witness='A',
            xslt_mode='builtin', schema_mode='none',
        )
        pp = write_project_xml(root/'project.xml', draft)
        text = pp.read_text(encoding='utf-8')
        assert '<images type="files">' in text
        assert 'file="images/A/0001_a.jpg"' in text
        cfg = load_project(pp)
        assert cfg.base.image_source_type == 'files'
        assert [x.label for x in cfg.base.image_files] == ['f. 1r','f. 1v']
        assert [x.path for x in cfg.base.image_files] == [i1.resolve(), i2.resolve()]


def test_prepare_local_images_copy_and_reference():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); project = root/'project'; project.mkdir()
        src = root/'photos'; src.mkdir()
        a = src/'IMG 001.jpg'; b = src/'IMG 002.jpg'; a.write_bytes(b'a'); b.write_bytes(b'b')
        witness = WitnessDraft('T1','T1',None,'base','files',None,[
            LocalImageDraft(a,'1r'), LocalImageDraft(b,'1v')
        ],'copy')
        out = prepare_local_images_for_project(project,[witness])[0]
        assert all(x.path.is_file() for x in out.image_files)
        assert all((project/'images'/'T1') in x.path.parents for x in out.image_files)
        assert [x.label for x in out.image_files] == ['1r','1v']
        ref = WitnessDraft('T2','T2',None,'secondary','files',None,[LocalImageDraft(a,'x')],'reference')
        out2 = prepare_local_images_for_project(project,[ref])[0]
        assert out2.image_files[0].path == a.resolve()


def test_apply_local_images_without_alignment_creates_browsable_pages():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        a = root/'a.jpg'; b = root/'b.jpg'; a.write_bytes(b'a'); b.write_bytes(b'b')
        entries = [LocalImageDraft(a,'f. 1r'), LocalImageDraft(b,'f. 1v')]
        cache = {'meta': {'witness':'A'}, 'pages': []}
        out = apply_witness_image_policy(cache,'files',None,root,entries)
        assert len(out['pages']) == 2
        assert out['pages'][0]['image']['type'] == 'file'
        assert out['pages'][0]['image']['label'] == 'f. 1r'
        items = image_only_items(out, root)
        assert len(items) == 2
        assert items[0]['l']['_image_only'] is True
        src = page_image_source(out['pages'][0], root)
        assert src.file_path == a.resolve()
        req = page_image_request(out['pages'][0], None, root)
        assert req['source_type'] == 'file'
        assert req['local_crop'] is False


def test_apply_local_images_overlays_alignment_and_preserves_lines():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); image = root/'p1.jpg'; image.write_bytes(b'x')
        cache = {'pages':[{
            'id':'p1','alto_width':1000,'alto_height':2000,
            'iiif': {'service':'https://example/iiif','label':'old'},
            'lines':[{'line':1,'bbox':{'hpos':1,'vpos':2,'width':3,'height':4},'base_keys':['x']}]
        }]}
        out = apply_witness_image_policy(cache,'files',None,root,[LocalImageDraft(image,'new')])
        p = out['pages'][0]
        assert 'iiif' not in p
        assert p['image']['type'] == 'file'
        assert p['lines'][0]['base_keys'] == ['x']
        assert image_only_items(out,root) == []


def test_new_transcription_project_can_copy_local_images():
    # Exercise the real creation path with a minimal template tree copied from the application root is
    # covered elsewhere; this test only asserts the draft structure remains accepted.
    with tempfile.TemporaryDirectory() as td:
        root = Path(td); src = root/'src.jpg'; src.write_bytes(b'x')
        w = WitnessDraft('A','A',None,'base','files',None,[LocalImageDraft(src,'f.1r')],'copy')
        prepared = prepare_local_images_for_project(root/'dest',[w])
        assert prepared[0].image_source_type == 'files'
        assert prepared[0].image_files[0].path.is_file()
