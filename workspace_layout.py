# -*- coding: utf-8 -*-
"""View-only arrangement policy, independent from Qt and from TEI science."""

VALID_WORKSPACE_MODES = ('vertical', 'horizontal', 'grid')


def normalize_workspace_mode(mode):
    """Disposition des témoins valable : ``mode`` s'il vaut ``vertical``,
    ``horizontal`` ou ``grid``, sinon ``vertical`` (réglage absent ou
    inconnu)."""
    return str(mode) if mode in VALID_WORKSPACE_MODES else 'vertical'


def workspace_slots(witness_ids, columns=2):
    """Stable non-overlapping rows; handles 1, 4, 5+ witnesses gracefully."""
    columns = max(1, int(columns))
    ids = list(dict.fromkeys(str(w) for w in witness_ids))
    return [ids[i:i+columns] for i in range(0, len(ids), columns)]


def normalized_detached_witnesses(saved_ids, visible_ids):
    """Témoins à détacher de nouveau à l'ouverture : ceux de ``saved_ids``
    (liste mémorisée) qui sont encore affichés (``visible_ids``), sans
    doublon, dans l'ordre mémorisé ; rien si ``saved_ids`` n'est ni une
    liste ni un tuple."""
    visible = set(str(x) for x in visible_ids)
    result = []
    for wid in saved_ids if isinstance(saved_ids, (tuple, list)) else ():
        wid = str(wid)
        if wid in visible and wid not in result:
            result.append(wid)
    return result
