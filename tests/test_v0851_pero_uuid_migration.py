"""Regression tests motivated by a PERO OCR ALTO/PAGE same-image comparison.

Synthetic fixture: no manuscript image or externally supplied source included.
"""
from alto_import import overlay_alto


UUID_A = 'f328d105-63f2-4658-af78-41ac736be124'
UUID_B = '73496133-dc28-4d53-bd48-2618e118b221'
UUID_C = '422d8ae3-c103-4cd9-b519-698b3525476e'


def line(prefix, uuid, number):
    return dict(line=number, alto_id=prefix + uuid, alto=f'line {number}',
                bbox=dict(hpos=10, vpos=number*20, width=200, height=18))


def old_cache():
    rows = [line('line_', uuid, i) for i, uuid in enumerate((UUID_A, UUID_B, UUID_C), 1)]
    for row in rows:
        row['base_keys'] = [f'primary::line-{row["line"]}']
        row['corrected'] = f'editorial note {row["line"]}'
    return {'pages': [{'id': 'old-page', 'label': 'source-image', 'lines': rows}]}


def new_cache(uuids):
    rows = [line('id_', uuid, i) for i, uuid in enumerate(uuids, 1)]
    for row in rows:
        row['polygon'] = [[10, 20], [200, 20], [190, 40], [10, 40]]
        row['baseline'] = [[10, 38], [190, 38]]
    return {'pages': [{'id': 'new-page', 'label': 'source-image', 'lines': rows}]}


def test_page_reordered_preserves_synchronization_by_pero_uuid():
    result = overlay_alto(old_cache(), new_cache((UUID_B, UUID_A, UUID_C)))
    assert result['pages'][0]['id'] == 'old-page'
    rows = result['pages'][0]['lines']
    assert [r['alto_id'] for r in rows] == ['id_'+UUID_B, 'id_'+UUID_A, 'id_'+UUID_C]
    assert [r['base_keys'] for r in rows] == [
        ['primary::line-2'], ['primary::line-1'], ['primary::line-3']]
    assert [r['corrected'] for r in rows] == [
        'editorial note 2', 'editorial note 1', 'editorial note 3']
    assert [r['line'] for r in rows] == [2, 1, 3]
    assert all('polygon' in r and 'baseline' in r for r in rows)


def test_new_line_does_not_steal_sync_of_another_uuid():
    unknown = 'f5555555-5555-4555-8555-555555555555'
    result = overlay_alto(old_cache(), new_cache((unknown, UUID_A, UUID_C)))
    rows = result['pages'][0]['lines']
    assert rows[0]['alto_id'] == 'id_'+unknown
    assert 'base_keys' not in rows[0]
    assert rows[1]['base_keys'] == ['primary::line-1']
    assert rows[2]['base_keys'] == ['primary::line-3']
    assert any(r['alto_id'] == 'line_'+UUID_B for r in rows[3:])


def test_pero_uuid_match_is_case_insensitive():
    newer = new_cache((UUID_A.upper(), UUID_B, UUID_C))
    rows = overlay_alto(old_cache(), newer)['pages'][0]['lines']
    assert rows[0]['base_keys'] == ['primary::line-1']
