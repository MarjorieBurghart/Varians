"""V0.8.5.11: simultaneous TEI pb-driven page witnesses and sync-driven line witnesses."""
from pathlib import Path
import ast
import json
import tempfile
import textwrap
from types import SimpleNamespace

from tei_facsimile import facsimile_ref_at_position
from image_sources import page_label as image_page_label
from project_management import ProjectDraft, WitnessDraft, LocalImageDraft, write_project_xml
from project_config import load_project
from web_viewer.generator import build_dataset
from varians_source import application_source, application_ast, node_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]
TEI = 'http://www.tei-c.org/ns/1.0'


def sample_xml():
    return f'''<TEI xmlns="{TEI}"><teiHeader><fileDesc><titleStmt><title>Test</title></titleStmt><publicationStmt><p>x</p></publicationStmt><sourceDesc><p>x</p></sourceDesc></fileDesc></teiHeader><text><body><p>
    <pb edRef="#Mu" n="2v" facs="#Mu-p0001"/>Mu line <lb edRef="#Mu"/>text
    <pb edRef="#C" n="2v" facs="#C-p0001"/>C opening
    <pb edRef="#F" n="16r" facs="#F-p0001"/>F opening
    <lb edRef="#Mu"/>continued
    <pb edRef="#C" n="3r" facs="#C-p0002"/>C next
    <lb edRef="#Mu"/>end
    </p></body></text></TEI>'''


def test_pb_resolves_independently_from_line_cursor_and_other_witnesses():
    src = sample_xml()
    pos = src.index('C next') + 1
    assert facsimile_ref_at_position(src, pos, 'C', {'C-p0001','C-p0002'}) == 'C-p0002'
    assert facsimile_ref_at_position(src, pos, 'F', {'F-p0001'}) == 'F-p0001'
    assert facsimile_ref_at_position(src, pos, 'Mu', {'Mu-p0001'}) == 'Mu-p0001'
    first = src.index('continued')
    assert facsimile_ref_at_position(src, first, 'C', {'C-p0001','C-p0002'}) == 'C-p0001'


def test_unique_pb_n_resolves_only_for_explicit_witness():
    s = '<p><pb edRef="#C" n="3r"/>abc<pb edRef="#F" n="3v" facs="#F-x"/>def</p>'
    lookup = {'C-1':'2v','C-2':'3r'}
    assert facsimile_ref_at_position(s, s.index('abc'), 'C', lookup, lookup) == 'C-2'
    assert facsimile_ref_at_position(s, len(s), 'C', lookup, lookup) == 'C-2'
    assert facsimile_ref_at_position(s, len(s), 'F', {'F-x'}, {'F-x':'3v'}) == 'F-x'
    assert facsimile_ref_at_position(s, len(s), 'Mu', {'Mu-x'}, {'Mu-x':'3r'}) is None


def test_pb_n_ambiguous_or_unknown_or_mismatched_facs_never_guessed():
    s = '<pb edRef="#C" n="3r"/>abc'
    assert facsimile_ref_at_position(s, len(s), 'C', {'C-1','C-2'}, {'C-1':'3r','C-2':'3r'}) is None
    assert facsimile_ref_at_position(s, len(s), 'C', {'C-1'}, {'C-1':'3v'}) is None
    s2 = '<pb edRef="#C" n="3r" facs="#unknown"/>abc'
    assert facsimile_ref_at_position(s2, len(s2), 'C', {'C-1'}, {'C-1':'3r'}) is None
    assert facsimile_ref_at_position('<pb n="3r"/>x', 100, 'C', {'C-1'}, {'C-1':'3r'}) is None


def _editor_method(name):
    """Extract a real MainWindow method for Qt-free behavioral tests."""
    src = application_source()
    module = application_ast()
    cls = next(x for x in module.body if isinstance(x, ast.ClassDef) and x.name == 'MainWindow')
    fn = next(x for x in cls.body if isinstance(x, ast.FunctionDef) and x.name == name)
    ns = {'facsimile_ref_at_position': facsimile_ref_at_position, 'image_page_label': image_page_label,
          '_t': lambda *args, **kwargs: ''}
    exec(textwrap.dedent(node_source(fn)), ns)
    return ns[name]


class StubPanel:
    def __init__(self, wid, sync_enabled, pages):
        self.sync_enabled = sync_enabled
        self.items = [{'p': {'tei_surface_id': sid, 'label': label,
                             'image': {'type': 'file', 'label': label}},
                       'l': {'_page_mode': not sync_enabled}}
                      for sid,label in pages]
        self._surface_indices = {sid:i for i,(sid,_) in enumerate(pages)}
        self.surface = None
        self.primary_calls = []
    def set_surface(self, sid):
        if sid not in self._surface_indices: return False
        self.surface = sid
        return True
    def set_primary(self, ordinal, key):
        self.primary_calls.append((ordinal, key))


class StubEditor:
    def __init__(self, text, pos):
        self.text = text
        self.pos = pos
    def textCursor(self):
        return SimpleNamespace(position=lambda: self.pos)
    def toPlainText(self):
        return self.text


class StubWindow:
    _sync_page_panels_to_cursor = _editor_method('_sync_page_panels_to_cursor')
    sync_panels_to_cursor = _editor_method('sync_panels_to_cursor')
    def __init__(self, text):
        self.editor = StubEditor(text, text.index('C opening'))
        self.project = SimpleNamespace(root_dir=Path('/tmp'))
        self.panels = {
            'Mu': StubPanel('Mu', True, [('Mu-p0001','2v')]),
            'F': StubPanel('F', True, [('F-p0001','16r')]),
            'C': StubPanel('C', False, [('C-p0001','2v'),('C-p0002','3r')]),
        }
        self.has_any_images = True
        self.base_alignment_available = True
        self.base_items = [{'key':'p1::1'}, {'key':'p1::2'}]
        self._last_synced_surface = None
        self._last_synced_ordinal = None
        self.ordinal = 0
        self.base_id = 'Mu'
    def ordinal_at_cursor(self):
        return self.ordinal
    def statusBar(self):
        return SimpleNamespace(showMessage=lambda *args: None)


def test_real_editor_methods_mix_modes_and_update_pages_even_on_same_line():
    src = sample_xml()
    win = StubWindow(src)
    win.sync_panels_to_cursor(True)
    assert win.panels['C'].surface == 'C-p0001'
    assert win.panels['Mu'].primary_calls == [(0, 'p1::1')]
    assert win.panels['F'].primary_calls == [(0, 'p1::1')]
    assert not win.panels['C'].primary_calls
    # TEI cursor crosses the page marker of C without crossing a pivot <lb>.
    win.editor.pos = src.index('C next') + 1
    win.sync_panels_to_cursor()
    assert win.panels['C'].surface == 'C-p0002'
    assert len(win.panels['Mu'].primary_calls) == 1  # no redundant line update
    assert len(win.panels['F'].primary_calls) == 1
    # Next pivot line changes both synced panels, but not the page-only surface.
    win.ordinal = 1
    win.sync_panels_to_cursor()
    assert win.panels['Mu'].primary_calls[-1] == (1, 'p1::2')
    assert win.panels['F'].primary_calls[-1] == (1, 'p1::2')
    assert win.panels['C'].surface == 'C-p0002'


def test_all_page_navigation_still_works_without_base_json():
    src = sample_xml()
    win = StubWindow(src)
    win.base_alignment_available = False
    win.panels['Mu'].sync_enabled = False
    win.panels['F'].sync_enabled = False
    win.editor.pos = src.index('F opening') + 1
    win.sync_panels_to_cursor(True)
    assert win.panels['C'].surface == 'C-p0001'
    assert win.panels['Mu'].surface == 'Mu-p0001'
    assert win.panels['F'].surface == 'F-p0001'
    assert not win.panels['Mu'].primary_calls


def test_three_witness_project_exposes_witness_local_line_sync_mode():
    with tempfile.TemporaryDirectory() as tmp:
        root=Path(tmp); (root/'xml').mkdir()
        edition=root/'xml'/'edition.xml'; edition.write_text(sample_xml(), encoding='utf-8')
        base=root/'Mu.json'; base.write_text(json.dumps({'meta': {'role':'base'}, 'pages': [
            {'id':'2v', 'lines':[{'line':1, 'alto_id':'a1', 'bbox':{'hpos':1,'vpos':1,'width':50,'height':20}}]}]}),encoding='utf-8')
        sec=root/'F.json'; sec.write_text(json.dumps({'meta': {'role':'secondary'}, 'pages': [
            {'id':'f1', 'lines':[{'line':28,'alto_id':'F28','base_keys':['2v::1'], 'bbox':{'hpos':1,'vpos':1,'width':50,'height':20}}]}]}),encoding='utf-8')
        images=[]
        for n in ('2v','3r'):
            f=root/f'C_{n}.jpg'; f.write_bytes(b'fake-image'); images.append(f)
        witnesses=[
            WitnessDraft('Mu','Mu',base,'base','none',None,[], 'keep',None,'auto',[],'keep','reference'),
            WitnessDraft('F','F',sec,'secondary','none',None,[], 'keep',None,'auto',[],'keep','reference'),
            WitnessDraft('C','C',None,'secondary','files',None,[
                LocalImageDraft(images[0], '2v', surface_id='C-p0001'),
                LocalImageDraft(images[1], '3r', surface_id='C-p0002')], 'reference',None,'auto',[],'keep','reference'),
        ]
        draft=ProjectDraft('Mixed',edition,'fr','en', ROOT/'i18n', ROOT/'rendering'/'tei-to-html.xsl',
                           ROOT/'rendering'/'tei.css', ROOT/'rendering'/'custom-elements.xml',
                           root/'web_output','viewer.html',witnesses,'Mu','builtin','none')
        cfg=load_project(write_project_xml(root/'project.xml',draft))
        data,missing=build_dataset(cfg)
        by={w['id']:w for w in data['witnesses']}
        assert by['Mu']['line_sync'] is True
        assert by['F']['line_sync'] is True
        assert by['C']['line_sync'] is False
        assert len(by['C']['pages'])==2
        assert {p['tei_surface_id'] for p in by['C']['pages']} == {'C-p0001','C-p0002'}
        assert missing == []


def test_navigation_entrypoints_and_browser_lines_update_independent_pages():
    editor=application_source()
    browser=(ROOT/'web_viewer'/'generator.py').read_text(encoding='utf-8')
    assert 'if panel.sync_enabled:\n                panel.set_primary' in editor
    assert 'self._sync_page_panels_to_cursor(force=True)' in editor
    assert 'if not self.base_alignment_available:\n            return' in editor
    assert 'if(Number.isFinite(docPos))syncPagesToDocPosition(docPos);' in browser
    assert 'syncAll(true);return true' in browser
    assert "document.querySelectorAll('.pb[data-doc-pos]')" in browser
    assert 'labelIndex' in browser and 'data-n=' in browser
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in editor
