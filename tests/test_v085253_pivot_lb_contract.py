"""V0.8.5.25.3: the web viewer MUST use the desktop pivot lb ordinal.

In particular, TEI pb/@n and @facs are NOT the primary-line key and
secondary synchronisation is authorized only by existing base_keys.
"""
from __future__ import annotations

import json
from pathlib import Path
import xml.etree.ElementTree as ET

from test_v08526_web_page_anchor_resolution import create_project
from web_viewer.generator import build_dataset
from web_viewer.tei_line_anchors import build_pivot_lb_index


def _text_keys(data):
    return [((s.get('text') or '').strip(), s['line_key'])
            for b in data['document']['blocks'] for s in b.get('segments', [])
            if s.get('kind') == 'text' and (s.get('text') or '').strip()]


def _change_alignment(project, pages, secondary):
    # The data source remains an actual, explicit JSON alignment file.
    root = project.root_dir
    (root / 'Mu.json').write_text(json.dumps({
        'meta': {'witness': 'Mu', 'role': 'base'}, 'pages': pages
    }), encoding='utf-8')
    (root / 'F.json').write_text(json.dumps({
        'meta': {'witness': 'F', 'role': 'secondary'}, 'pages': secondary
    }), encoding='utf-8')


def test_same_as_desktop_despite_unrelated_folios_and_nonconsecutive_numbers(tmp_path):
    project = create_project(tmp_path,
        '<pb edRef="#Mu" n="folio IX" facs="#unresolvable"/>'
        '<lb edRef="#Mu"/>première'
        '<pb edRef="#F" n="autre témoin" facs="#F-p0003"/>'
        '<lb edRef="#Mu"/>deuxième'
        '<pb edRef="#Mu" n="folio X"/>'
        '<lb edRef="#Mu"/>troisième')
    box = {'hpos': 50, 'vpos': 50, 'width': 200, 'height': 30}
    _change_alignment(project,
        [{'id':'physical-A', 'lines':[{'line':4,'bbox':box}, {'line':9,'bbox':box}]},
         {'id':'physical-B', 'lines':[{'line':3,'bbox':box}]}],
        [{'id':'other-F','lines':[
            {'line':1,'order':1,'base_keys':['physical-A::4'],'bbox':box},
            {'line':2,'order':2,'base_keys':['physical-A::9'],'bbox':box},
            {'line':3,'order':3,'base_keys':['physical-B::3'],'bbox':box}]}])
    data, missing = build_dataset(project)
    assert not missing
    assert data['meta']['line_sync']
    assert data['witnesses'][1]['line_sync']
    assert data['meta']['tei_page_resolution']['unresolved'] >= 1
    assert [k for _, k in _text_keys(data)] == [
        'physical-A::4', 'physical-A::9', 'physical-B::3']
    assert [(p['id'], [l['line'] for l in p['lines']])
            for p in data['witnesses'][0]['pages']] == [
                ('physical-A',[4,9]),('physical-B',[3])]
    assert [l.get('corrected') for p in data['witnesses'][0]['pages']
            for l in p['lines']] == ['première','deuxième','troisième']
    assert data['meta']['pivot_lb_index']['count_match']
    assert data['meta']['unresolvable_text_line_keys'] == 0


def test_no_pb_needed_for_lb_link_as_in_desktop(tmp_path):
    project = create_project(tmp_path,
       '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta', include_image=False)
    data, missing = build_dataset(project)
    assert not missing
    assert data['witnesses'][1]['line_sync']
    assert _text_keys(data) == [('alpha','physical-A::1'),('beta','physical-A::2')]


def test_missing_physical_lines_do_not_create_fictitious_link(tmp_path):
    project = create_project(tmp_path,
       '<lb edRef="#Mu"/>alpha<lb edRef="#Mu"/>beta'
       '<lb edRef="#Mu"/>orphan', include_image=False)
    data, missing = build_dataset(project)
    assert not missing
    assert data['meta']['pivot_lb_index']['mapped_lb_count'] == 2
    assert data['meta']['pivot_lb_index']['unmapped_lb_count'] == 1
    assert data['meta']['pivot_lb_index']['count_match'] is False
    assert _text_keys(data)[:2] == [('alpha','physical-A::1'),('beta','physical-A::2')]
    assert not any(key == 'physical-A::3' for _, key in _text_keys(data))
    assert data['meta']['unanchored_text_segments'] >= 1


def test_source_ordinal_includes_lb_inside_notes_even_when_hidden(tmp_path):
    project = create_project(tmp_path,
       '<lb edRef="#Mu"/>alpha<note><lb edRef="#Mu"/>commentaire</note>'
       '<lb edRef="#Mu"/>gamma', include_image=False)
    box = {'hpos': 5, 'vpos': 10, 'width': 60, 'height': 10}
    _change_alignment(project,
      [{'id':'physical-A','lines':[{'line':1,'bbox':box},
                                  {'line':2,'bbox':box}, {'line':3,'bbox':box}]}],
      [{'id':'physical-F','lines':[{'line':1,'base_keys':['physical-A::1']},
                                  {'line':2,'base_keys':['physical-A::3']}]}])
    data, _ = build_dataset(project)
    assert ('gamma','physical-A::3') in _text_keys(data)
    assert ('gamma','physical-A::2') not in _text_keys(data)
    assert data['meta']['pivot_lb_index']['tei_lb_count'] == 3


def test_anchor_index_excludes_other_witness_and_keeps_source_order():
    root=ET.fromstring('<root><lb edRef="#F"/><lb edRef="#Mu"/><note>'
                       '<lb edRef="#Mu"/></note><lb edRef="#Mu"/></root>')
    mapping, stats = build_pivot_lb_index(root,'Mu',['page::1','page::3'])
    lbs=[x for x in root.iter() if x.tag=='lb']
    assert id(lbs[0]) not in mapping
    assert mapping[id(lbs[1])] == 'page::1'
    assert mapping[id(lbs[2])] == 'page::3'
    assert id(lbs[3]) not in mapping
    assert stats.unmapped_lb_count == 1
