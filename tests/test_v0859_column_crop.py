"""Regressions for synchronization crop at folio/column boundaries (V0.8.5.9)."""
from image_sources import display_window_indices, page_image_request


def _line(page, number, x, y, width=390, height=42):
    return {'p': page, 'l': {'line':number, 'order':number,
                             'bbox':{'hpos':x,'vpos':y,'width':width,'height':height}}}


def _bbox_for_context(items, selected):
    # Matches editeur_tei.crop_for_items rectangle bounds without importing Qt.
    boxes = [items[i]['l']['bbox'] for i in selected]
    return (min(x['hpos'] for x in boxes), min(x['vpos'] for x in boxes),
            max(x['hpos']+x['width'] for x in boxes),
            max(x['vpos']+x['height'] for x in boxes))


def test_column_transition_keeps_accurate_line_but_discards_other_column_context():
    page = {'id':'F-16r','alto_width':1300,'alto_height':1900}
    lines = [_line(page, 26, 125, 1650), _line(page, 27, 125, 1710),
             _line(page, 28, 700, 210), _line(page, 29, 700, 260),
             _line(page, 30, 700, 310)]
    assert display_window_indices(lines, 1, 1) == [0, 1]
    assert display_window_indices(lines, 2, 1) == [2, 3]
    assert display_window_indices(lines, 3, 1) == [2, 3, 4]
    # With the old implementation, this crop had y=1710 and y=210 and
    # spanned both columns. The new crop is limited to the second column.
    x0,y0,x1,y1 = _bbox_for_context(lines, display_window_indices(lines, 2))
    assert x0 >= 650 and y0 >= 200 and y1 < 350


def test_page_transition_never_includes_a_line_from_another_leaf():
    p1 = {'id':'F-16r'}
    p2 = {'id':'F-16v'}
    items = [_line(p1,60,400,1550), _line(p1,61,400,1600),
             _line(p2,1,400,220), _line(p2,2,400,270)]
    assert display_window_indices(items,1,2) == [0,1]
    assert display_window_indices(items,2,2) == [2,3]


def test_horizontal_jump_can_mark_column_even_without_vertical_reset():
    p={'id':'f','alto_width':1300}
    items=[_line(p,10,100,400,400), _line(p,11,690,410,390)]
    assert display_window_indices(items,0,1)==[0]
    assert display_window_indices(items,1,1)==[1]


def test_indentation_slanted_lines_and_backward_window_remain_usable():
    p={'id':'f','alto_width':1300}
    items=[_line(p,4,200,370,350), _line(p,5,220,412,370),
           _line(p,6,190,451,380)]
    assert display_window_indices(items,0,1)==[0,1]
    assert display_window_indices(items,1,1)==[0,1,2]
    assert display_window_indices(items,2,1)==[1,2]


def test_page_navigation_and_missing_geometry_keep_their_semantics():
    p={'id':'f'}
    pseudo = {'p':p,'l':{'_page_mode':True}}
    assert display_window_indices([pseudo],0)==[0]
    items=[{'p':p,'l':{'line':1}}, {'p':p,'l':{'line':2}}]
    assert display_window_indices(items,1)==[0,1]
    assert display_window_indices([],0)==[]


def test_alignment_data_is_unchanged_by_presentation_only_window():
    p={'id':'page-uuid'}
    items=[_line(p,27,90,1600), _line(p,28,600,170)]
    before=[(i['p']['id'],i['l']['line']) for i in items]
    display_window_indices(items,1)
    assert [(i['p']['id'],i['l']['line']) for i in items]==before


def test_local_and_iiif_sources_do_not_depend_on_window_position():
    page={'image':{'type':'iiif','service':'https://example.org/iiif/F16r',
                   'width':1300,'height':1900,'iiif_version':2}}
    req=page_image_request(page,{'x':680,'y':188,'w':440,'h':130})
    assert '680,188,440,130' in req['url']
