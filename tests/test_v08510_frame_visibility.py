"""V0.8.5.10: frame selection at sync, page and column boundaries."""
from pathlib import Path
import ast
from image_sources import (
    matched_line_center, valid_matched_indices, visible_line_frame_indices,
    display_window_indices, effective_line_bbox,
)

ROOT = Path(__file__).resolve().parents[1]


def line(page, n, x, y):
    return {'p': page, 'l': {'line': n, 'order': n,
            'bbox': {'hpos': x, 'vpos': y, 'width': 380, 'height': 40}}}


def test_noncontiguous_matches_never_choose_unlinked_midpoint():
    # V0.8.5.9 rounded (10+14)/2 to 12, which had no link/frame.
    assert matched_line_center([10, 14], 12, 30) in {10, 14}
    assert matched_line_center([10, 14], 12, 30) == 10
    assert matched_line_center([10, 14], 13, 30) == 14
    assert matched_line_center([10], 29, 30) == 10


def test_match_normalization_refuses_invalid_or_out_of_range_indices():
    assert valid_matched_indices([-5, 8, 8, 21, None, '5', 'foo', 1.5], 15) == {5, 8}
    assert matched_line_center([-5, 21, None], 4, 15) is None


def test_drawn_frames_include_actual_sync_and_current_navigation():
    # Show linked targets, and a differently styled current line when the
    # reader navigates locally without changing the base sync.
    assert visible_line_frame_indices([9, 10, 11], 10, {10, 14}) == {10}
    assert visible_line_frame_indices([9, 10, 11], 11, {10, 14}) == {10, 11}
    assert visible_line_frame_indices([9, 10, 11], 11, set()) == {11}


def test_line_at_start_of_second_column_retains_visible_frame():
    p = {'id': 'F-16r', 'alto_width': 1300}
    items = [line(p, 26, 125, 1650), line(p, 27, 125, 1710),
             line(p, 28, 700, 210), line(p, 29, 700, 260)]
    inds = display_window_indices(items, 2, 1)
    assert inds == [2, 3]
    assert visible_line_frame_indices(inds, 2, {2}) == {2}


def test_secondary_center_and_drawing_are_wired_into_real_editor():
    src = (ROOT / 'editeur_tei.py').read_text(encoding='utf-8')
    ast.parse(src)
    assert 'center = matched_line_center(matches, self.center_index, len(self.items))' in src
    assert 'visible_line_frame_indices(' in src
    assert 'QGraphicsPolygonItem(vertices)' in src
    assert 'shape.setPen(frame_pen if is_linked else current_pen)' in src
    assert 'self.center_index = int(round((min(matches)+max(matches))/2))' not in src


def test_existing_page_and_polygon_importers_are_preserved():
    editor = (ROOT / 'editeur_tei.py').read_text(encoding='utf-8')
    importer = (ROOT / 'alto_import.py').read_text(encoding='utf-8')
    assert 'points = scaled_polygon(line_item, self.project_root)' in editor
    assert "row['polygon'] = polygon" in importer


def test_polygon_only_json_geometry_has_real_crop_bbox():
    line = {'polygon': [[147, 47], [497, 42], [497, 60], [148, 65]]}
    assert effective_line_bbox(line) == {'hpos': 147, 'vpos': 42, 'width': 350, 'height': 23}
    assert effective_line_bbox({'polygon': [[0, 0], [2, 0], [0, 3]],
                                'bbox': {'hpos': 4, 'vpos': 5, 'width': 6, 'height': 7}})['hpos'] == 4
    assert effective_line_bbox({'polygon': [[1, 1], [2, 2]]}) is None
    assert effective_line_bbox({'bbox': {'width': 5}}) is None


def test_page_polygon_col_continuity_is_safely_detected_without_bboxes():
    p = {'id':'folio16r','alto_width':1300}
    l1 = {'p':p,'l':{'polygon':[[100,1700],[400,1700],[400,1740],[100,1740]]}}
    l2 = {'p':p,'l':{'polygon':[[700,200],[1100,200],[1100,240],[700,240]]}}
    assert display_window_indices([l1,l2],0) == [0]
    assert display_window_indices([l1,l2],1) == [1]
