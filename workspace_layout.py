# -*- coding: utf-8 -*-
"""View-only arrangement policy, independent from Qt and from TEI science."""

VALID_WORKSPACE_MODES = ('vertical', 'horizontal', 'grid')


def normalize_workspace_mode(mode):
    return str(mode) if mode in VALID_WORKSPACE_MODES else 'vertical'


def workspace_slots(witness_ids, columns=2):
    """Stable non-overlapping rows; handles 1, 4, 5+ witnesses gracefully."""
    columns = max(1, int(columns))
    ids = list(dict.fromkeys(str(w) for w in witness_ids))
    return [ids[i:i+columns] for i in range(0, len(ids), columns)]


def normalized_detached_witnesses(saved_ids, visible_ids):
    visible = set(str(x) for x in visible_ids)
    result = []
    for wid in saved_ids if isinstance(saved_ids, (tuple, list)) else ():
        wid = str(wid)
        if wid in visible and wid not in result:
            result.append(wid)
    return result
