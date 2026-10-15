"""V0.8.5.21: detached real panels, three layouts, local preferences.

Qt is not installed in CI; execute the actual controller methods with strict
QSplitter/QWidget doubles, not a reimplementation of their branching logic.
"""
import ast
import json
from pathlib import Path
from types import SimpleNamespace
import textwrap
import xml.etree.ElementTree as ET

from workspace_layout import (normalize_workspace_mode, workspace_slots,
                              normalized_detached_witnesses)

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT/'editeur_tei.py').read_text(encoding='utf-8')


def method(cls, name, globs=None):
    tree=ast.parse(SRC)
    klass=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name==cls)
    fn=next(n for n in klass.body if isinstance(n,ast.FunctionDef) and n.name==name)
    env={'json':json, **(globs or {})}
    exec(textwrap.dedent(ast.get_source_segment(SRC, fn)),env)
    return env[name]


class Settings:
    def __init__(self, initial=None): self.data=dict(initial or {})
    def value(self,k,default=None):return self.data.get(k,default)
    def setValue(self,k,v):self.data[k]=v


class Panel:
    def __init__(self, ident):
        self.siglum=ident; self.parent=None; self.zoom=234; self.frames=True
        self.page='2v'; self.visible=True;self.compact=False;self._detached=False
    def setParent(self,p):
        if isinstance(self.parent,Splitter):self.parent.remove(self)
        self.parent=p
    def isVisible(self):return self.visible
    def isHidden(self):return not self.visible
    def setVisible(self,v):self.visible=bool(v)
    def show(self):self.visible=True
    def set_compact_toolbar(self,compact):self.compact=bool(compact)
    def retranslate_ui(self):pass


class Splitter:
    def __init__(self, orientation=None):
        self.widgets=[];self.visible=True;self.sizes_now=[];self.minimum_height=None
        self.splitterMoved=SimpleNamespace(connect=lambda fn:None)
    def remove(self,w):
        i=self.widgets.index(w);self.widgets.pop(i);self.sizes_now.pop(i);w.parent=None
    def indexOf(self,w):return self.widgets.index(w) if w in self.widgets else -1
    def insertWidget(self,idx,w):
        if getattr(w,'parent',None) is not None and isinstance(w.parent,Splitter):w.parent.remove(w)
        self.widgets.insert(idx,w);self.sizes_now.insert(idx,300);w.parent=self
    def addWidget(self,w):self.insertWidget(len(self.widgets),w)
    def widget(self,i):return self.widgets[i]
    def count(self):return len(self.widgets)
    def setVisible(self,v):self.visible=bool(v)
    def show(self):self.visible=True
    def setMinimumHeight(self,v):self.minimum_height=v
    def setSizes(self,x):self.sizes_now=list(x)
    def sizes(self):return list(self.sizes_now)


class Action:
    def setChecked(self,value):self.checked=bool(value)
    def setEnabled(self,value):self.enabled=bool(value)


class FloatWindow:
    def __init__(self,main,wid,panel,always_on_top=False):
        self.main=main;self.id=wid;self.panel=panel
        panel.setParent(self)
        panel._detached=True
        self.on_top=always_on_top
        self.closed=False
    def restoreGeometry(self,geom):self.geom=geom
    def show(self):self.shown=True
    def close(self):
        self.closed=True
        self.main._dock_witness(self.id,from_window=True)
    def deleteLater(self):self.deleted=True


class Qt:
    Orientation=SimpleNamespace(Horizontal='horizontal')


class Timer:
    @staticmethod
    def singleShot(delay, callback): callback()


def make_workspace():
    ids=['Mu','F','L','A','N']
    panels={x:Panel(x) for x in ids}
    vert, horiz, grid=Splitter(),Splitter(),Splitter()
    rows=[Splitter(),Splitter()]
    for row in rows:grid.addWidget(row)
    for wid in ids:vert.addWidget(panels[wid])
    saved=Settings()
    win=SimpleNamespace(
        panels=panels,
        witness_configs=[SimpleNamespace(id=w) for w in ids],
        witness_splitter=vert,witness_horizontal_splitter=horiz,
        witness_grid_splitter=grid,_grid_rows=rows,
        workspace_root=object(),
        _witness_display_order=['L','Mu','N','A','F'],
        _visible_witness_ids=ids[:],_witness_maximized_id=None,
        _witness_sizes_before_maximize=None,
        _reordering_witness_panels=False,_changing_workspace=False,
        _closing_workspace=False,_detached_windows={},
        _workspace_mode='vertical',_workspace_before_maximize=None,
        workspace_mode_actions={x:Action() for x in ('vertical','horizontal','grid')},
        _view_settings_key=lambda suffix:'p/'+suffix,
        _load_witness_size_map=lambda:{},
        witness_scroll=SimpleNamespace(isHidden=lambda:False,setVisible=lambda visible:None),
        _update_witness_scroll_extent=lambda:None,
        _save_detached_witness_ids=lambda:None,
        _refresh_detach_actions=lambda:None,
        _refresh_workspace_visibility=lambda:None,
        _remember_workspace_sizes=lambda:None,
        _restore_workspace_sizes=lambda:None,
    )
    win._apply_witness_panel_order=lambda:method('MainWindow','_apply_witness_panel_order',{'QSplitter':Splitter,'Qt':Qt})(win)
    win._set_workspace_mode=lambda mode,persist=True:method('MainWindow','_set_workspace_mode',{
        'QTimer':Timer,'_settings':lambda:saved})(win,mode,persist=persist)
    win._detach_witness=lambda wid,persist=True:method('MainWindow','_detach_witness',{
        'QTimer':Timer,'_settings':lambda:saved,'DetachedWitnessWindow':FloatWindow})(win,wid,persist=persist)
    win._dock_witness=lambda wid,from_window=False:method('MainWindow','_dock_witness',{
        'QTimer':Timer})(win,wid,from_window=from_window)
    return win,saved


def test_policies_are_pure_and_reject_invalid_saved_ids():
    assert normalize_workspace_mode('grid')=='grid'
    assert normalize_workspace_mode('hax')=='vertical'
    assert workspace_slots(['Mu','F','L','A','N'])==[['Mu','F'],['L','A'],['N']]
    assert workspace_slots(['Mu','Mu','L'],2)==[['Mu','L']]
    assert normalized_detached_witnesses(['L','removed','L','F'],['Mu','F','L'])==['L','F']
    assert normalized_detached_witnesses('L',['L'])==[]


def test_switching_three_layouts_moves_same_objects_and_keeps_zoom_frames():
    w,settings=make_workspace();old=w.panels.copy()
    w._apply_witness_panel_order()
    assert [x.siglum for x in w.witness_splitter.widgets]==['L','Mu','N','A','F']
    w._set_workspace_mode('horizontal')
    assert w.witness_splitter.widgets==[]
    assert [x.siglum for x in w.witness_horizontal_splitter.widgets]==['L','Mu','N','A','F']
    assert all(p.compact for p in w.panels.values())
    w._set_workspace_mode('grid')
    assert w.witness_horizontal_splitter.widgets==[]
    assert [[p.siglum for p in row.widgets] for row in w._grid_rows]==[['L','Mu'],['N','A'],['F']]
    w._set_workspace_mode('vertical')
    assert [x.siglum for x in w.witness_splitter.widgets]==['L','Mu','N','A','F']
    assert all(w.panels[k] is v for k,v in old.items())
    assert all(p.zoom==234 and p.frames and p.page=='2v' and not p.compact for p in old.values())
    assert settings.data['p/workspaceMode']=='vertical'


def test_detached_witness_reuses_actual_panel_and_closing_redocks():
    w,settings=make_workspace();w._apply_witness_panel_order()
    assert w._detach_witness('L')
    assert 'L' in w._detached_windows
    assert w._detached_windows['L'].panel is w.panels['L']
    assert 'L' not in [p.siglum for p in w.witness_splitter.widgets]
    assert w.panels['L']._detached and not w.panels['L'].compact
    assert w.panels['L'].zoom==234
    # The window X button, not a separate duplicate attachment operation.
    detached=w._detached_windows['L'];detached.close()
    assert 'L' not in w._detached_windows
    assert [p.siglum for p in w.witness_splitter.widgets]==['L','Mu','N','A','F']
    assert detached.deleted and w.panels['L']._detached is False
    assert w.panels['L'].zoom==234 and w.panels['L'].frames
    assert not w._detach_witness('unknown')


def test_grid_retains_correct_order_with_one_detached():
    w,_=make_workspace();w._set_workspace_mode('grid')
    w._detach_witness('Mu')
    assert [[p.siglum for p in row.widgets] for row in w._grid_rows if row.widgets]==[['L','N'],['A','F']]
    w._dock_witness('Mu')
    assert [[p.siglum for p in row.widgets] for row in w._grid_rows]==[['L','Mu'],['N','A'],['F']]


def test_project_scoped_ratio_allows_20_percent_xml_editor():
    settings=Settings({'p/xmlColumnRatio':.2})
    sizes=[800,800]
    splitter=SimpleNamespace(sizes=lambda:list(sizes),width=lambda:1600,
                             setSizes=lambda vals:sizes.__setitem__(slice(None),list(vals)))
    win=SimpleNamespace(main_splitter=splitter,_restoring_main_splitter_ratio=False,
        _view_settings_key=lambda suffix:'p/'+suffix,
        witness_scroll=SimpleNamespace(isHidden=lambda:False))
    method('MainWindow','_restore_main_splitter_ratio',{'_settings':lambda:settings})(win)
    assert sizes==[320,1280]
    sizes[:]=[320,1280]
    method('MainWindow','_remember_main_splitter_ratio',{'_settings':lambda:settings})(win)
    assert settings.data['p/xmlColumnRatio']==.2


def test_settings_and_menu_are_local_not_written_to_scientific_sources():
    assert "self._view_settings_key('workspaceMode')" in SRC
    assert "self._view_settings_key('detachedWitnesses')" in SRC
    assert "f'floatingAlwaysOnTop/{self.witness_id}'" in SRC
    assert "f'floatingGeometry/{self.witness_id}'" in SRC
    assert "self.main_splitter.setSizes([round(total * ratio)" in SRC
    assert 'self.witness_splitter.setMinimumWidth(0)' in SRC
    assert 'self.witness_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)' in SRC
    assert 'self.witness_scroll.setWidget(self.workspace_root)' in SRC
    assert 'self.workspace_root' in SRC and 'self.workspace_layout_menu' in SRC
    assert 'Qt.WindowType.WindowStaysOnTopHint' in SRC
    assert 'self.main._dock_witness(self.witness_id, from_window=True)' in SRC
    assert 'self.set_compact_toolbar' in SRC


def test_all_seven_locales_have_identical_and_complete_workspace_translations():
    keys=set()
    for lang in ('fr','en','de','ja','cs','it','ru'):
        root=ET.parse(ROOT/'i18n'/f'{lang}.xml').getroot()
        values={x.get('key'):x.text for x in root.findall('string')}
        new={k for k in values if k.startswith('workspace.')}
        assert len(values)==len(root.findall('string'))==629
        assert len(new)==11 and all(values[k] for k in new)
        assert '{witness}' in values['workspace.detached.title']
        assert '0.8.5.24' in (ROOT/'help'/f'{lang}.html').read_text(encoding='utf-8')
        if not keys:keys=new
        else:assert new==keys


def test_horizontal_and_grid_sizes_persist_by_witness_id_not_old_position():
    w,settings=make_workspace()
    w._set_workspace_mode('horizontal')
    w.witness_horizontal_splitter.setSizes([210,220,230,240,250])
    method('MainWindow','_remember_workspace_sizes',{'_settings':lambda:settings})(w)
    recorded=json.loads(settings.data['p/horizontalSizes'])
    assert recorded=={'L':210,'Mu':220,'N':230,'A':240,'F':250}
    w.witness_horizontal_splitter.setSizes([3,3,3,3,3])
    method('MainWindow','_restore_workspace_sizes',{'_settings':lambda:settings})(w)
    assert w.witness_horizontal_splitter.sizes()==[210,220,230,240,250]
    w._set_workspace_mode('grid')
    w._grid_rows[0].setSizes([451,452]);w._grid_rows[1].setSizes([453,454])
    w._grid_rows[2].setSizes([455])
    method('MainWindow','_remember_workspace_sizes',{'_settings':lambda:settings})(w)
    widths=json.loads(settings.data['p/gridSizes'])
    assert [widths[k] for k in ['L','Mu','N','A','F']]==[451,452,453,454,455]
    for row in w._grid_rows:row.setSizes([4]*row.count())
    method('MainWindow','_restore_workspace_sizes',{'_settings':lambda:settings})(w)
    assert [[row.sizes()[i] for i in range(row.count())] for row in w._grid_rows]==[[451,452],[453,454],[455]]


def test_reopened_detached_windows_only_for_visible_existing_witnesses():
    w,settings=make_workspace()
    w._visible_witness_ids=['Mu','F','L']
    settings.setValue('p/detachedWitnesses',json.dumps(['L','ghost','Mu','L','N']))
    method('MainWindow','_restore_detached_witnesses',{'_settings':lambda:settings})(w)
    assert list(w._detached_windows)==['L','Mu']
    assert w.panels['L'].parent is w._detached_windows['L']
    assert w.panels['L']._detached
    assert not w.panels['F']._detached


def test_individual_window_always_on_top_is_independent_per_witness():
    w,settings=make_workspace()
    settings.setValue('p/floatingAlwaysOnTop/L','true')
    settings.setValue('p/floatingAlwaysOnTop/Mu','false')
    w._detach_witness('L');w._detach_witness('Mu')
    assert w._detached_windows['L'].on_top is True
    assert w._detached_windows['Mu'].on_top is False


def test_documentation_does_not_promise_converted_synchronization():
    doc=(ROOT/'WORKSPACE_LAYOUT.md').read_text(encoding='utf-8')
    assert 'project.xml' in doc and 'base_keys' in doc
    assert 'PySide6' in doc and '20 %' in doc
    assert 'Toujours au premier plan' in doc
