"""Regressions for export snapshot of Qt presentation and search group A03."""
from pathlib import Path
import re
from web_viewer.generator import build_dataset, generate, make_html
from project_config import load_project
from varians_source import application_source

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'project.xml'


def test_default_cli_exports_all_project_witnesses():
    p = load_project(PROJECT)
    data, _ = build_dataset(p)
    expected = [w.id for w in p.witnesses]
    assert data['meta']['display_witnesses'] == expected
    assert [w['id'] for w in data['witnesses']] == expected


def test_gui_snapshot_preserves_order_and_filters_hidden_secondaries():
    p = load_project(PROJECT)
    all_ids = [w.id for w in p.witnesses]
    assert len(all_ids) >= 3
    chosen = [all_ids[2], all_ids[0]]
    data, _ = build_dataset(p, display_witness_ids=chosen)
    assert data['meta']['display_witnesses'] == chosen
    assert [w['id'] for w in data['witnesses']] == chosen
    assert all_ids[1] not in [w['id'] for w in data['witnesses']]
    assert data['meta']['pivot_lb_index']['count_match']
    assert data['meta']['unresolvable_text_line_keys'] == 0


def test_hidden_pivot_still_indexes_text_but_does_not_publish_facsimile():
    p = load_project(PROJECT)
    ids = [w.id for w in p.witnesses]
    base = p.base_witness
    secondaries = [wid for wid in ids if wid != base]
    assert secondaries
    chosen = list(reversed(secondaries))
    data, _ = build_dataset(p, display_witness_ids=chosen)
    assert data['meta']['display_witnesses'] == chosen
    assert [w['id'] for w in data['witnesses']] == chosen + [base]
    pivot = data['witnesses'][-1]
    assert pivot['role'] == 'base'
    assert all(pg['image']['type'] == 'none' for pg in pivot['pages'])
    assert data['meta']['pivot_lb_index']['count_match']
    assert data['meta']['unresolvable_text_line_keys'] == 0
    assert data['meta']['line_sync']
    assert all(w['id'] not in chosen or w['pages'] for w in data['witnesses'])


def test_empty_selection_is_respected_and_leaves_no_image_assets():
    data, _ = build_dataset(load_project(PROJECT), display_witness_ids=[])
    assert data['meta']['display_witnesses'] == []
    assert [w['id'] for w in data['witnesses']] == [data['meta']['base_witness']]
    assert not data['meta']['has_images']
    assert all(pg['image']['type'] == 'none' for pg in data['witnesses'][0]['pages'])


def test_selection_deduplicates_and_discards_foreign_ids():
    p = load_project(PROJECT)
    a = [w.id for w in p.witnesses]
    selected = [a[1], '__foreign__', a[1], a[0]]
    data, _ = build_dataset(p, display_witness_ids=selected)
    assert data['meta']['display_witnesses'] == [a[1], a[0]]


def test_html_has_no_master_medieval_checkbox():
    data, _ = build_dataset(load_project(PROJECT))
    html = make_html(data)
    assert '<span class="search-option" id="searchModeLabel"></span>' in html
    assert 'id="searchMedieval"' not in html
    for key in ('searchUV', 'searchIJ', 'searchCT'):
        assert re.search(f'<input id="{key}" type="checkbox">', html)
    assert 'medieval:uv||ij||ct' in html
    assert 'displayWitnesses.map(cardHTML)' in html
    assert 'if(!card||!w||!st)return;' in html


def test_generator_writes_selected_only_and_keeps_cli_behavior(tmp_path):
    chosen = [w.id for w in load_project(PROJECT).witnesses][1:2]
    html_file = tmp_path / 'selected.html'
    out, _, data = generate(PROJECT, html_file, display_witness_ids=chosen)
    assert out == html_file
    assert data['meta']['display_witnesses'] == chosen
    assert [w['id'] for w in data['witnesses']] == chosen + [data['meta']['base_witness']]
    assert '"display_witnesses"' in out.read_text(encoding='utf-8')


def test_gui_passes_current_qsettings_snapshot_without_changing_project_xml():
    source = application_source()
    assert 'display_ids = [wid for wid in self._witness_display_order if wid in visible]' in source
    assert 'display_witness_ids=display_ids' in source
    assert 'self._view_settings_key("visibleWitnesses")' in source
    assert 'self._view_settings_key("witnessOrder")' in source
