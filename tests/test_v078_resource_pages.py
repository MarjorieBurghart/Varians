from pathlib import Path
import tempfile

from project_config import WitnessConfig, has_line_synchronization
from project_management import LocalImageDraft
from image_sources import (
    apply_witness_image_policy, image_only_items, display_window_indices,
    page_image_source,
)
from varians_source import application_source
from alto_import import build_alto_cache, overlay_alto

ALTO_TMPL = '''<?xml version="1.0" encoding="UTF-8"?>
<alto xmlns="http://www.loc.gov/standards/alto/ns-v4#">
  <Description><sourceImageInformation><fileName>{image}</fileName></sourceImageInformation></Description>
  <Layout><Page ID="{page}" WIDTH="1000" HEIGHT="2000"><PrintSpace>
    <TextBlock><TextLine ID="{line}" HPOS="10" VPOS="20" WIDTH="300" HEIGHT="40">
      <String CONTENT="{word}"/>
    </TextLine></TextBlock>
  </PrintSpace></Page></Layout>
</alto>'''


def _write_alto(path: Path, image: str, page: str, line: str, word: str):
    path.write_text(ALTO_TMPL.format(image=image, page=page, line=line, word=word), encoding='utf-8')
    return path


def test_image_only_navigation_is_one_page_at_a_time():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        entries = []
        for i in range(4):
            p = root / f'IMG_{i+1}.jpg'; p.write_bytes(b'x')
            entries.append(LocalImageDraft(p, f'f. {i+1}r'))
        out = apply_witness_image_policy({'pages': []}, 'files', None, root, entries)
        items = image_only_items(out, root)
        assert len(items) == 4
        assert [display_window_indices(items, i) for i in range(4)] == [[0], [1], [2], [3]]


def test_four_local_images_survive_four_alto_pages():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        altos=[]; images=[]
        for i in range(4):
            img_name=f'IMG_{i+1}.jpg'
            img=root/img_name; img.write_bytes(b'img')
            images.append(LocalImageDraft(img, f'f. {i+1}r'))
            altos.append(_write_alto(root/f'a{i+1}.xml', img_name, f'P{i+1}', f'L{i+1}', f'w{i+1}'))
        cache = build_alto_cache(altos, 'A1', 'base')
        out = apply_witness_image_policy(cache, 'files', None, root, images)
        assert len(out['pages']) == 4
        assert [len(p['lines']) for p in out['pages']] == [1,1,1,1]
        assert [Path(page_image_source(p, root).file_path).name for p in out['pages']] == [
            'IMG_1.jpg','IMG_2.jpg','IMG_3.jpg','IMG_4.jpg'
        ]


def test_alignment_plus_alto_plus_images_keeps_union_and_sync_metadata():
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        alignment = {'meta': {'witness': 'A1', 'role': 'base'}, 'pages': [
            {'id':'sync-1','label':'IMG_1','lines':[{'line':1,'alto_id':'L1','base_keys':['sync-1::1']}]},
            {'id':'sync-2','label':'IMG_2','lines':[{'line':2,'alto_id':'L2','base_keys':['sync-2::2']}]},
        ]}
        altos=[]; images=[]
        for i in range(4):
            img_name=f'IMG_{i+1}.jpg'; img=root/img_name; img.write_bytes(b'img')
            images.append(LocalImageDraft(img, f'IMG_{i+1}'))
            altos.append(_write_alto(root/f'a{i+1}.xml', img_name, f'P{i+1}', f'L{i+1}', f'w{i+1}'))
        imported=build_alto_cache(altos,'A1','base')
        merged=overlay_alto(alignment, imported)
        out=apply_witness_image_policy(merged,'files',None,root,images)
        assert len(out['pages']) == 4
        assert out['pages'][0]['id'] == 'sync-1'
        assert out['pages'][1]['id'] == 'sync-2'
        assert out['pages'][0]['lines'][0]['base_keys'] == ['sync-1::1']
        assert out['pages'][1]['lines'][0]['base_keys'] == ['sync-2::2']
        assert all(page_image_source(p, root).available for p in out['pages'])


def test_alto_is_not_line_synchronization():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)
        alto=root/'a.xml'; alto.write_text('<alto/>',encoding='utf-8')
        w=WitnessConfig('A','A',None,'base',alto_source_type='files')
        assert has_line_synchronization(w) is False
        sync=root/'sync.json'; sync.write_text('{}',encoding='utf-8')
        w2=WitnessConfig('A','A',sync,'base',alto_source_type='files')
        assert has_line_synchronization(w2) is True


def test_editor_uses_explicit_sync_not_alto_for_expected_line_count():
    root=Path(__file__).resolve().parents[1]
    source=application_source()
    assert 'self._base_sync_line_count = None' in source
    assert 'self.base_alignment_available = bool(' in source
    assert '(self._base_sync_line_count or 0) > 0' in source
    assert 'self.expected_base_lines = self._base_sync_line_count if self.base_alignment_available else None' in source
    assert 'sync_enabled=((self.base_alignment_available and bool(self.base_items))' in source
    assert 'APP_VERSION = "0.8.5.26.2"' in source
