"""V0.8.5.17: GUI ordering is view-only, independent of line synchronisation."""
from __future__ import annotations

import ast
import json
from pathlib import Path
from types import SimpleNamespace
import textwrap
import xml.etree.ElementTree as ET

from witness_layout import normalized_witness_order, ordered_visible_witnesses
from varians_source import application_source, application_ast, node_source, CURRENT_VERSION, CATALOG_SIZE

ROOT = Path(__file__).resolve().parents[1]
SOURCE = application_source()


def method(classname, name, more_globals=None):
    cls = next(n for n in application_ast().body if isinstance(n, ast.ClassDef) and n.name == classname)
    fn = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    globs = {'json': json, **(more_globals or {})}
    exec(textwrap.dedent(node_source(fn)), globs)
    return globs[name]


class Settings:
    def __init__(self, mapping=None):
        self.mapping = dict(mapping or {})

    def value(self, key, default=None):
        return self.mapping.get(key, default)

    def setValue(self, key, value):
        self.mapping[key] = value


class Panel:
    def __init__(self, ident):
        self.ident = ident
        self.zoom = 124
        self.frames = True
        self.current_page = '3r'
        self.visible = True

    def set_compact_toolbar(self, compact):
        self.compact = bool(compact)

    def isVisible(self):
        return self.visible

    def isHidden(self):
        return not self.visible

    def setVisible(self, value):
        self.visible = bool(value)


class Splitter:
    def __init__(self, panels):
        self.widgets = list(panels)
        self.current_sizes = [200 + 11*i for i in range(len(panels))]

    def indexOf(self, widget):
        return self.widgets.index(widget)

    def insertWidget(self, index, widget):
        # Mirrors QSplitter semantics for an already-parented widget.
        old = self.widgets.index(widget)
        size = self.current_sizes.pop(old)
        self.widgets.pop(old)
        self.widgets.insert(index, widget)
        self.current_sizes.insert(index, size)

    def sizes(self):
        return list(self.current_sizes)

    def setSizes(self, sizes):
        self.current_sizes = list(sizes)


class Scroll:
    def __init__(self):
        self.visible = True
    def isHidden(self):
        return not self.visible
    def setVisible(self, value):
        self.visible = bool(value)


def make_window():
    ids = ['Mu', 'F', 'L', 'A']
    panels = {k: Panel(k) for k in ids}
    split = Splitter([panels[k] for k in ids])
    win = SimpleNamespace(
        panels=panels,
        witness_configs=[SimpleNamespace(id=k) for k in ids],
        witness_splitter=split,
        witness_scroll=Scroll(),
        _witness_display_order=['L', 'Mu', 'A', 'F'],
        _visible_witness_ids=['Mu', 'F', 'L', 'A'],
        _witness_maximized_id=None,
        _witness_sizes_before_maximize=None,
        _reordering_witness_panels=False,
        _witness_image_available={k: True for k in ids},
        _load_witness_size_map=lambda: {'Mu': 310, 'F': 430, 'L': 540, 'A': 290},
        _update_witness_scroll_extent=lambda: None,
        _save_visible_witness_ids=lambda: None,
        _view_settings_key=lambda suffix: 'project-x/' + suffix,
    )
    win._available_image_witness_ids = lambda: list(win._witness_image_available)
    win._apply_witness_panel_order = lambda: method('MainWindow', '_apply_witness_panel_order')(win)
    win._restore_witness_splitter_sizes = lambda: method('MainWindow', '_restore_witness_splitter_sizes')(win)
    win._restore_workspace_sizes = win._restore_witness_splitter_sizes
    win._refresh_detach_actions = lambda: None
    return win


def test_order_normalization_recovers_deleted_corrupt_and_new_witnesses():
    assert normalized_witness_order(['Mu', 'F', 'L', 'A'], ['L', 'Mu', 'deleted', 'L', 'F']) == ['L', 'Mu', 'F', 'A']
    assert normalized_witness_order(['Mu', 'F', 'L'], None) == ['Mu', 'F', 'L']
    assert normalized_witness_order(['Mu', 'F', 'Mu'], ['F']) == ['F', 'Mu']
    assert normalized_witness_order([], ['F', 'Mu']) == []


def test_order_keeps_hidden_positions_and_filters_no_image():
    assert ordered_visible_witnesses(['L', 'Mu', 'A', 'F'], ['F', 'Mu', 'L'], ['Mu', 'F', 'A']) == ['Mu', 'F']
    assert ordered_visible_witnesses(['A', 'Mu', 'F'], [], ['A', 'Mu', 'F']) == []


def test_reordering_reuses_original_panel_objects_and_state():
    win = make_window()
    original = win.panels.copy()
    win._apply_witness_panel_order()
    assert [p.ident for p in win.witness_splitter.widgets] == ['L', 'Mu', 'A', 'F']
    assert all(win.panels[k] is original[k] for k in original)
    assert win.panels['L'].current_page == '3r'
    assert win.panels['L'].frames and win.panels['L'].zoom == 124
    assert win._reordering_witness_panels is False


def test_sizes_are_restored_by_id_not_old_splitter_position():
    win = make_window()
    win._apply_witness_panel_order()
    win._restore_witness_splitter_sizes()
    assert win.witness_splitter.sizes() == [540, 310, 290, 430]


def test_heights_are_saved_by_reordered_widget_not_project_rank():
    win = make_window()
    settings = Settings()
    win._apply_witness_panel_order()
    win.witness_splitter.current_sizes = [150, 250, 350, 450]
    save = method('MainWindow', '_remember_witness_splitter_sizes', {'_settings': lambda: settings})
    save(win)
    assert json.loads(settings.mapping['project-x/witnessHeights']) == {
        'L': 150, 'Mu': 250, 'A': 350, 'F': 450,
    }
    win._reordering_witness_panels = True
    win.witness_splitter.current_sizes = [2, 2, 2, 2]
    save(win)
    assert json.loads(settings.mapping['project-x/witnessHeights'])['L'] == 150


def test_preferences_roundtrip_and_unknown_ids_do_not_break_reopening():
    settings = Settings({'project-x/witnessOrder': json.dumps(['L', 'Mu', 'removed', 'F'])})
    win = make_window()
    load = method('MainWindow', '_load_witness_display_order', {'_settings': lambda: settings})
    save = method('MainWindow', '_save_witness_display_order', {'_settings': lambda: settings})
    assert load(win) == ['L', 'Mu', 'F', 'A']
    win._witness_display_order = ['A', 'L', 'Mu', 'F']
    save(win)
    assert load(win) == ['A', 'L', 'Mu', 'F']
    settings.mapping['project-x/witnessOrder'] = 'invalid-json'
    assert load(win) == ['Mu', 'F', 'L', 'A']


def test_visibility_applies_new_order_with_hidden_witnesses_intact():
    win = make_window()
    win._visible_witness_ids = ['Mu', 'A']
    # In the real window the delayed size restoration runs after layout.
    win._main_splitter_last_visible_sizes = [760, 530]
    win.main_splitter = SimpleNamespace(sizes=lambda: [760, 530], setSizes=lambda sizes: None)
    timer = SimpleNamespace(singleShot=lambda _delay, callback: callback())
    method('MainWindow', '_apply_witness_visibility', {'QTimer': timer})(win, initial=True)
    assert [p.ident for p in win.witness_splitter.widgets] == ['L', 'Mu', 'A', 'F']
    assert [k for k, v in win.panels.items() if v.visible] == ['Mu', 'A']
    assert win._visible_witness_ids == ['Mu', 'A']
    assert win.witness_splitter.sizes() == [0, 310, 290, 0]
    assert win.witness_scroll.visible is True


def test_dialog_move_up_down_and_boundaries_without_qt_runtime():
    class FakeList:
        def __init__(self, names):
            self.items = list(names)
            self.row = 1
        def currentRow(self):
            return self.row
        def count(self):
            return len(self.items)
        def takeItem(self, i):
            return self.items.pop(i)
        def insertItem(self, i, item):
            self.items.insert(i, item)
        def setCurrentRow(self, i):
            self.row = i
    class FakeBtn:
        def setEnabled(self, v):
            self.enabled = v
    fake = SimpleNamespace(list=FakeList(['Mu','F','L']), up_btn=FakeBtn(), down_btn=FakeBtn())
    fake._update_move_buttons = lambda: method('WitnessVisibilityDialog','_update_move_buttons')(fake)
    move=method('WitnessVisibilityDialog','_move_selected')
    move(fake, -1)
    assert fake.list.items == ['F','Mu','L']
    assert fake.list.row == 0
    assert not fake.up_btn.enabled and fake.down_btn.enabled
    move(fake, -1)
    assert fake.list.items == ['F','Mu','L']
    move(fake, 1)
    assert fake.list.items == ['Mu','F','L']


def test_existing_view_menu_reuses_witness_dialog_not_project_editor():
    assert 'self._witness_display_order = dlg.ordered_ids()' in SOURCE
    assert 'self._save_witness_display_order()' in SOURCE
    assert 'self.witness_splitter.insertWidget(index, panel)' in SOURCE
    assert '_t("view.witnesses.choose")' in SOURCE
    assert 'projectView/' in SOURCE
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in SOURCE


def test_translations_7_languages_all_present_and_unambiguous():
    expected={'fr','en','de','ja','cs','it','ru'}
    assert {p.stem for p in (ROOT/'i18n').glob('*.xml')} == expected
    for language in expected:
        root=ET.parse(ROOT/'i18n'/f'{language}.xml').getroot()
        keys=[e.attrib['key'] for e in root.findall('string')]
        assert len(keys) == len(set(keys)) == CATALOG_SIZE
        trans={e.attrib['key']:e.text for e in root.findall('string')}
        for key in ('view.witnesses.hint','view.witnesses.move_up','view.witnesses.move_down'):
            assert trans[key] and len(trans[key])>1
        assert (ROOT/'help'/f'{language}.html').exists()
        assert '0.8.5.19' in (ROOT/'help'/f'{language}.html').read_text(encoding='utf-8')


def test_hidden_panel_height_survives_other_panels_being_resized():
    win = make_window()
    win._apply_witness_panel_order()
    win.panels['L'].visible = False
    win._load_witness_size_map = lambda: {'L': 875, 'Mu': 220}
    win.witness_splitter.current_sizes = [0, 300, 380, 490]
    settings = Settings()
    save = method('MainWindow', '_remember_witness_splitter_sizes', {'_settings': lambda: settings})
    save(win)
    heights = json.loads(settings.mapping['project-x/witnessHeights'])
    assert heights == {'L': 875, 'Mu': 300, 'A': 380, 'F': 490}


def test_maximize_restore_targets_correct_witness_after_reordering():
    win = make_window()
    win._apply_witness_panel_order()
    win._restore_witness_splitter_sizes()
    original = win.witness_splitter.sizes()
    win._remember_witness_splitter_sizes = lambda: None
    win.witness_scroll.verticalScrollBar = lambda: SimpleNamespace(setValue=lambda value: None)
    toggle = method('MainWindow', '_toggle_witness_panel_maximize')
    toggle(win, 'F')
    assert win._witness_maximized_id == 'F'
    assert win.witness_splitter.sizes() == [0, 0, 0, sum(original)]
    toggle(win, 'F')
    assert win._witness_maximized_id is None
    assert win.witness_splitter.sizes() == original
