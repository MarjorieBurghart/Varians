"""V0.8.5.12: 4+ image witnesses and unambiguous pivot manuscript semantics."""
from pathlib import Path
import ast
from types import SimpleNamespace
import textwrap
import xml.etree.ElementTree as ET

from tei_facsimile import facsimile_ref_at_position
from witness_layout import minimum_witness_stack_height
from varians_source import application_source, application_ast, node_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def test_four_panels_have_scroll_extent_instead_of_compressed_heights():
    assert minimum_witness_stack_height(1) == 290
    assert minimum_witness_stack_height(2) == 587
    assert minimum_witness_stack_height(4) == 1181
    assert minimum_witness_stack_height(5) > minimum_witness_stack_height(4)
    assert minimum_witness_stack_height(4, maximized=True) == 290
    assert minimum_witness_stack_height(0) == 0


def _real_method(name):
    source = application_source()
    cls = next(n for n in application_ast().body if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
    f = next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
    ns = {}
    exec(textwrap.dedent(node_source(f)), ns)
    return ns[name]


def test_real_scroll_extent_reacts_to_visibility_and_maximize_without_qt():
    win = SimpleNamespace(
        witness_configs=[SimpleNamespace(id=x) for x in ('Mu','F','C','D')],
        panels={x:SimpleNamespace(isHidden=lambda: False) for x in ('Mu','F','C','D')},
        witness_splitter=SimpleNamespace(setMinimumHeight=lambda h: setattr(win,'height',h)),
        _witness_maximized_id=None,
    )
    method = _real_method('_update_witness_scroll_extent')
    method(win)
    assert win.height == 1181
    win._witness_maximized_id = 'D'
    method(win)
    assert win.height == 290
    win._witness_maximized_id = None
    win.panels['F'].isHidden=lambda: True
    method(win)
    assert win.height == minimum_witness_stack_height(3)


def test_editor_uses_real_vertical_scroll_area_around_existing_splitter():
    code=application_source()
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in code
    for fragment in (
        'self.witness_scroll = QScrollArea(self)',
        'self.witness_scroll.setWidgetResizable(True)',
        'self.witness_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)',
        'self.witness_scroll.setWidget(self.workspace_root)',
        'splitter.addWidget(self.witness_scroll)',
        'self.witness_scroll.setVisible(has_visible)',
        'self._update_witness_scroll_extent()',
        'self.witness_splitter.setSizes(sizes)',
        'self._view_settings_key("witnessHeights")',
        'self.manuscript_scroll = self.witness_scroll',
    ):
        assert fragment in code


def test_same_folio_label_in_different_manuscripts_is_not_ambiguous():
    xml = '''<p>
      <pb edRef="#C" n="3r"/>Some text
      <pb edRef="#D" n="3r"/>More text
      <pb edRef="#C" n="3v"/>Third
    </p>'''
    pos = xml.index('More text')
    assert facsimile_ref_at_position(xml,pos,'C',{'C-3r','C-3v'},
                                    {'C-3r':'3r','C-3v':'3v'})=='C-3r'
    assert facsimile_ref_at_position(xml,pos,'D',{'D-3r'},
                                    {'D-3r':'3r'})=='D-3r'
    assert facsimile_ref_at_position(xml,len(xml),'C',{'C-3r','C-3v'},
                                    {'C-3r':'3r','C-3v':'3v'})=='C-3v'
    assert facsimile_ref_at_position(xml,len(xml),'D',{'D-3r'},
                                    {'D-3r':'3r'})=='D-3r'


def test_duplicate_n_inside_same_witness_still_requires_facs():
    xml='<pb edRef="#C" n="3r"/>Text'
    assert facsimile_ref_at_position(xml,len(xml),'C',{'C-a','C-b'},
                                    {'C-a':'3r','C-b':'3r'}) is None
    xml='<pb edRef="#C" n="3r" facs="#C-b"/>Text'
    assert facsimile_ref_at_position(xml,len(xml),'C',{'C-a','C-b'},
                                    {'C-a':'3r','C-b':'3r'})=='C-b'


def test_browser_folio_matching_is_scoped_by_edref_witness():
    js=(ROOT/'web_viewer'/'generator.py').read_text(encoding='utf-8')
    assert 'function pbWitnessIds(pb,sids)' in js
    assert 'const explicit=ptrs(pb.dataset.edref)' in js
    assert 'const st=states.get(wid)' in js
    assert 'st.labelIndex.get(label)' in js
    assert 'labelIndex=new Map()' in js


def test_seven_locales_use_pivot_not_base_witness_in_project_creation():
    files=list((ROOT/'i18n').glob('*.xml'))
    assert {f.stem for f in files}=={'fr','en','de','it','cs','ja','ru'}
    for file in files:
        strings={x.attrib['key']:x.text for x in ET.parse(file).getroot().findall('string')}
        assert len(strings)==629
        assert strings['project.witness.base']
        assert 'pivot_tip' in 'project.witness.pivot_tip'
        assert len(strings['project.witness.pivot_tip']) > 40
        assert (ROOT/'help'/f'{file.stem}.html').exists()
    fr={x.attrib['key']:x.text for x in ET.parse(ROOT/'i18n'/'fr.xml').getroot().findall('string')}
    assert fr['project.witness.base']=='Manuscrit pivot'
    assert fr['project.witness.set_base']=='Définir comme manuscrit pivot'
    assert 'manuscrit de base' not in fr['project.witness.set_base']
    en={x.attrib['key']:x.text for x in ET.parse(ROOT/'i18n'/'en.xml').getroot().findall('string')}
    assert en['project.witness.base']=='Pivot manuscript'
