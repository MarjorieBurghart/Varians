"""Varians V0.8.5.17 — per-witness diagnostics and transactional resource reload."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
import xml.etree.ElementTree as ET

import pytest
from witness_resource_refresh import (assemble_resources, diagnostic_rows,
                                      changed_witnesses, read_alignment_json,
                                      sync_fingerprint)
from varians_source import application_source, application_ast, node_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def witness(wid, path=None, role='secondary', *, pictures=(), alto=()):
    return SimpleNamespace(
        id=wid, label='Manuscrit '+wid, alignment=path, role=role,
        is_base=(role=='base'), image_source_type='files' if pictures else 'none',
        image_source_value=None,
        image_files=tuple(SimpleNamespace(path=p, label=p.stem, width=None, height=None,
                                          surface_id=f'{wid}-{i}')
                          for i, p in enumerate(pictures)),
        alto_source_type='files' if alto else 'auto',
        alto_files=tuple(SimpleNamespace(path=p) for p in alto),
        iiif_local_copy=False, iiif_selection_mode='all',
        iiif_selected_canvases=(), iiif_ocr_links=(), iiif_page_links=(),
    )


def project(root, *witnesses):
    return SimpleNamespace(base_witness='Mu', witnesses=witnesses,
                           witness_by_id={w.id:w for w in witnesses}, root_dir=root)


def write(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False), encoding='utf-8')
    return path


def alignment(wid, *, role='secondary', pivot='Mu', lines=None):
    return {'meta': {'witness':wid, 'role':role, 'base_witness':pivot},
            'pages':[{'id':wid+'-p', 'label':'3r', 'lines':lines or []}]}


def test_live_sync_diagnostic_counts_only_raw_linked_lines_and_unmatched_keys(tmp_path):
    base = write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1},{'line':2}]))
    f = write(tmp_path/'F.json', alignment('F',lines=[
        {'line':5,'base_keys':['Mu-p::1']},
        {'line':6,'base_keys':['Mu-p::missing']},
        {'line':7,'base_keys':[]},
    ]))
    p=project(tmp_path, witness('Mu',base,'base'), witness('F',f))
    st=assemble_resources(p)
    rows={r.id:r for r in diagnostic_rows(p,st)}
    assert st.base_active
    assert rows['Mu'].active
    assert rows['F'].active
    assert rows['F'].linked_lines == 2
    assert rows['F'].usable_links == 1
    assert rows['F'].unknown_keys == 1
    assert 'some_keys_unknown' in rows['F'].issue_codes


def test_leiden_json_pivot_mismatch_and_absent_links_are_explained(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    secondary=write(tmp_path/'L.json',alignment('L',pivot='L',lines=[{'line':1}]))
    p=project(tmp_path,witness('Mu',base,'base'),witness('L',secondary))
    rows={r.id:r for r in diagnostic_rows(p,assemble_resources(p))}
    assert {'pivot_mismatch','no_base_keys'} <= set(rows['L'].issue_codes)
    assert not rows['L'].active


def test_reexport_changes_links_with_same_counts_and_has_no_edit_side_effect(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1},{'line':2}]))
    f=write(tmp_path/'F.json', alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']}]))
    p=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    before=assemble_resources(p)
    oldrows=diagnostic_rows(p,before)
    write(f,alignment('F',lines=[{'line':1,'base_keys':['Mu-p::2']}]))
    after=assemble_resources(p)
    newrows=diagnostic_rows(p,after)
    assert changed_witnesses(oldrows,newrows)==['F']
    assert before.base_maps['F']=={'Mu-p::1':[0]}
    assert after.base_maps['F']=={'Mu-p::2':[0]}
    assert read_alignment_json(f)['pages'][0]['lines'][0]['base_keys']==['Mu-p::2']


def test_bad_json_aborts_staging_without_mutating_previous_state(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':4,'base_keys':['Mu-p::1']}]))
    p=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    previous=assemble_resources(p)
    f.write_text('{"pages": [',encoding='utf-8')
    with pytest.raises((ValueError,json.JSONDecodeError)):
        assemble_resources(p)
    assert previous.base_maps['F']['Mu-p::1']==[0]
    assert previous.caches['F']['pages'][0]['lines'][0]['line']==4


def test_json_with_wrong_shape_rejected_before_commit(tmp_path):
    source=tmp_path/'wrong.json'
    for value in [[], {'pages':{}}, {'pages':[None]}, {'pages':[{'lines':{}}]}]:
        write(source,value)
        with pytest.raises(ValueError):
            read_alignment_json(source)


def test_image_only_witness_remains_valid_without_json(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    image=tmp_path/'3r.jpg'; image.write_bytes(b'fake')
    p=project(tmp_path,witness('Mu',base,'base'),witness('C',None,pictures=(image,)))
    state=assemble_resources(p)
    rows={r.id:r for r in diagnostic_rows(p,state)}
    assert rows['C'].pages==1
    assert rows['C'].images==1
    assert rows['C'].missing_images==0
    assert not rows['C'].active
    assert 'pages_only' in rows['C'].issue_codes


def test_deleted_local_image_is_reported_but_not_deleted_from_project(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    img=tmp_path/'missing.jpg'
    p=project(tmp_path,witness('Mu',base,'base'),witness('C',None,pictures=(img,)))
    rows={r.id:r for r in diagnostic_rows(p,assemble_resources(p))}
    assert rows['C'].missing_images == 1
    assert 'local_images_missing' in rows['C'].issue_codes


def test_missing_pivot_sync_does_not_turn_alto_geometry_into_sync(tmp_path):
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':2,'base_keys':['Mu-p::1']}]))
    p=project(tmp_path,witness('Mu',None,'base'),witness('F',f))
    rows={r.id:r for r in diagnostic_rows(p,assemble_resources(p))}
    assert not rows['F'].active
    assert 'pivot_unavailable' in rows['F'].issue_codes


def test_compatibility_legacy_keys816(tmp_path):
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':2,'keys816':['Mu-p::1']}]))
    p=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    rows={r.id:r for r in diagnostic_rows(p,assemble_resources(p))}
    assert rows['F'].usable_links==1 and rows['F'].active


def test_seven_locales_have_independent_diagnostic_strings():
    keys=None
    for lang in ('fr','en','de','ja','cs','it','ru'):
        tree=ET.parse(ROOT/'i18n'/f'{lang}.xml')
        children=list(tree.getroot().findall('string'))
        vals={node.attrib['key']:node.text for node in children}
        assert len(children)==len(vals)
        all_new={key for key in vals if key.startswith('diagnostics.')}
        assert len(all_new)>=33
        assert all(vals[key] for key in all_new)
        keys=all_new if keys is None else keys
        assert all_new==keys


def test_mainwindow_menu_preview_and_in_place_reload_are_wired_without_replacing_xml():
    text=application_source()
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in text
    assert 'self.action_diagnose_witnesses' in text
    assert 'self.action_refresh_synchronizations' in text
    reload_func=text.split('    def refresh_witness_synchronizations(self):')[1].split('    def reload_images(self):')[0]
    assert 'assemble_resources(' in reload_func
    assert 'QMessageBox.question(' in reload_func
    # V0.9.1.1 : l'application des données est commune avec le passage d'un
    # texte synchronisé à part à l'autre (_apply_runtime_state).
    assert 'self._apply_runtime_state(staged' in reload_func
    apply_func=text.split('    def _apply_runtime_state(self,')[1].split('\ndef ')[0]
    assert 'self._raw_alignment_caches = state.raw' in apply_func
    assert 'self.panels[w.id]' in apply_func
    for func in (reload_func, apply_func):
        assert 'self.editor.setPlainText(' not in func
        assert 'self._replace_with_project(' not in func


def _real_refresh_method(monkeypatch):
    """Execute the actual GUI controller method with lightweight Qt stand-ins.

    PySide6 is optional in CI; these stand-ins check the logic, not its pixels.
    """
    import ast
    import textwrap
    import witness_resource_refresh as refresh_mod
    source=application_source()
    cls=next(n for n in application_ast().body
             if isinstance(n,ast.ClassDef) and n.name=='MainWindow')
    func=next(n for n in cls.body
              if isinstance(n,ast.FunctionDef) and n.name=='refresh_witness_synchronizations')

    class Messages:
        StandardButton=SimpleNamespace(Yes=1,No=2)
        confirmed=[]
        warnings=[]
        @classmethod
        def question(cls,*args):
            cls.confirmed.append(args)
            return cls.StandardButton.Yes
        @classmethod
        def warning(cls,*args):
            cls.warnings.append(args)

    class Application:
        busy=False
        @classmethod
        def setOverrideCursor(cls, *_): cls.busy=True
        @classmethod
        def restoreOverrideCursor(cls): cls.busy=False

    globs={'assemble_resources':refresh_mod.assemble_resources,
           'diagnostic_rows':refresh_mod.diagnostic_rows,
           'changed_witnesses':refresh_mod.changed_witnesses,
           'QApplication':Application,'QMessageBox':Messages,
           'Qt':SimpleNamespace(CursorShape=SimpleNamespace(WaitCursor=1)),
           '_t':lambda key,**kwargs:key.format(**kwargs) if kwargs else key}
    exec(textwrap.dedent(node_source(func)),globs)
    # Méthode commune avec le passage d'un texte à l'autre (V0.9.1.1).
    import text_segments
    apply=next(n for n in cls.body
               if isinstance(n,ast.FunctionDef) and n.name=='_apply_runtime_state')
    globs.update(pivot_lb_pattern=text_segments.pivot_lb_pattern,
                 has_line_synchronization=text_segments.has_line_synchronization,
                 TEXT_ABSENT=text_segments.TEXT_ABSENT)
    exec(textwrap.dedent(node_source(apply)),globs)
    _APPLY[0]=globs['_apply_runtime_state']
    return globs[func.name],Messages,Application


_APPLY=[None]


class _FakeLabel:
    def __init__(self): self.value='';self.visible=False
    def setText(self,value): self.value=value
    def setToolTip(self,value): self.tip=value
    def hide(self): self.visible=False
    def show(self): self.visible=True


class _FakePanel:
    def __init__(self,items):
        self.items=items
        self.center_index=0
        self.reload_count=0
        self.is_base=False
        self.absent_key=None
        self.sync_issue=_FakeLabel()
        self.header=_FakeLabel()
        self.status=_FakeLabel()
        self.show_frames=True
        self.zoom=2.4
    def current_item(self): return self.items[self.center_index] if self.items else None
    def reload(self): self.reload_count+=1
    def set_base(self,is_base,label): self.is_base=is_base


class _FakeAction:
    def setEnabled(self,value): self.enabled=value


def _controller_for_project(proj):
    old=assemble_resources(proj)
    panels={wid:_FakePanel(items) for wid,items in old.display_items.items()}
    fake=SimpleNamespace(
        project=proj,
        witness_configs=proj.witnesses,
        panels=panels,
        editor=object(),
        _raw_alignment_caches=old.raw,
        alignment_caches=old.caches,
        witness_items=old.witness_items,
        witness_display_items=old.display_items,
        base_by_key=old.base_by_key,
        base_maps=old.base_maps,
        base_items=old.base_items,
        _base_sync_line_count=old.base_sync_count,
        base_alignment_available=old.base_active,
        _secondary_sync_link_counts=old.secondary_links,
        _witness_image_available=old.images_available,
        action_reload_images=_FakeAction(),
        action_choose_witnesses=_FakeAction(),
        expected_base_lines=old.base_sync_count,
        has_any_images=False,
        _witness_maximized_id=None,
        _update_witness_scroll_extent=lambda:None,
        _last_synced_ordinal=18,
        _last_synced_surface='#Mu-p',
        lb_spans=lambda:[(1,5),(10,15)],
        _set_lb_spans=lambda spans:None,
        _apply_witness_visibility=lambda initial:None,
        sync_panels_to_cursor=lambda force:None,
        statusBar=lambda:SimpleNamespace(showMessage=lambda *args:None),
        base_id=proj.base_witness,
        witness_labels={w.id:w.id for w in proj.witnesses},
        _text_witness_ids=lambda:set(),
        # Segment affiché (V0.9.1.1) : l'édition.
        _segment_project=lambda:proj,
        _refreshed_segment_project=lambda:proj,
        _store_segment_state=lambda state,project:None,
    )
    fake._apply_runtime_state=lambda state,project,images=None:_APPLY[0](fake,state,project,images)
    fake._witness_resource_snapshot=lambda: __import__('witness_resource_refresh').RuntimeState(
        fake._raw_alignment_caches,fake.alignment_caches,
        fake.witness_items,fake.witness_display_items,fake.base_by_key,
        fake.base_maps,fake.base_items,fake._base_sync_line_count,
        fake.base_alignment_available,fake._secondary_sync_link_counts,
        fake._witness_image_available)
    return fake


def test_gui_controller_refreshes_in_place_and_keeps_editor_panels_frames_and_zoom(tmp_path,monkeypatch):
    method,messages,application=_real_refresh_method(monkeypatch)
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1},{'line':2}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']}]))
    proj=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    controller=_controller_for_project(proj)
    xml_editor=controller.editor
    original_panel=controller.panels['F']
    write(f,alignment('F',lines=[{'line':1,'base_keys':['Mu-p::2']}]))
    assert method(controller) is True
    assert messages.confirmed and not messages.warnings
    assert application.busy is False
    assert controller.editor is xml_editor
    assert controller.panels['F'] is original_panel
    assert original_panel.show_frames is True and original_panel.zoom==2.4
    assert original_panel.reload_count>=1
    assert controller.base_maps['F']=={'Mu-p::2':[0]}
    assert controller._last_synced_ordinal is None


def test_gui_controller_bad_json_keeps_editor_and_old_index(tmp_path,monkeypatch):
    method,messages,application=_real_refresh_method(monkeypatch)
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']}]))
    proj=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    controller=_controller_for_project(proj)
    initial_editor=controller.editor
    initial_panel=controller.panels['F']
    initial_map=controller.base_maps
    f.write_text('{broken:',encoding='utf-8')
    assert method(controller) is False
    assert controller.editor is initial_editor
    assert controller.panels['F'] is initial_panel
    assert controller.base_maps is initial_map
    assert initial_panel.reload_count==0
    assert application.busy is False
    assert messages.warnings and not messages.confirmed


def test_rejects_bad_key_shapes_instead_of_claiming_synchronization(tmp_path):
    file=tmp_path/'bad.json'
    for invalid in ('Mu-p::1',[100],{'Mu-p::1':1}):
        write(file,alignment('F',lines=[{'line':1,'base_keys':invalid}]))
        with pytest.raises(ValueError):
            read_alignment_json(file)


def test_controller_keeps_maximized_panel_when_sync_reloaded(tmp_path,monkeypatch):
    method,messages,_application=_real_refresh_method(monkeypatch)
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']}]))
    proj=project(tmp_path,witness('Mu',base,'base'),witness('F',f))
    controller=_controller_for_project(proj)
    controller._witness_maximized_id='F'
    called=[]
    controller._apply_witness_visibility=lambda initial:called.append('reset')
    controller._update_witness_scroll_extent=lambda:called.append('size')
    write(f,alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']},{'line':2,'base_keys':['Mu-p::1']}]))
    assert method(controller)
    assert controller._witness_maximized_id=='F'
    # Here F has no images, so restoring visibility is correctly permitted.
    assert called==['reset']


def test_maximized_witness_with_image_is_not_resized_on_refresh(tmp_path,monkeypatch):
    method,_messages,_application=_real_refresh_method(monkeypatch)
    base=write(tmp_path/'Mu.json',alignment('Mu',role='base',lines=[{'line':1}]))
    f=write(tmp_path/'F.json',alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']}]))
    image=tmp_path/'folio.jpg'; image.write_bytes(b'test image bytes')
    proj=project(tmp_path,witness('Mu',base,'base'),witness('F',f,pictures=(image,)))
    controller=_controller_for_project(proj)
    controller._witness_maximized_id='F'
    events=[]
    controller._apply_witness_visibility=lambda initial:events.append('reset')
    controller._update_witness_scroll_extent=lambda:events.append('size')
    write(f,alignment('F',lines=[{'line':1,'base_keys':['Mu-p::1']},
                                 {'line':2,'base_keys':['Mu-p::1']}]))
    assert method(controller)
    assert controller._witness_maximized_id=='F'
    assert events==['size']
