# -*- coding: utf-8 -*-
"""Geometry policy for Varians' vertically scrollable manuscript panels.

Kept independent of Qt to make the four-witness/minimize case testable on
machines without PySide6.  UI settings retain the user's individual splitter
sizes; this module only imposes a lower bound on the whole vertical stack.
"""


def minimum_witness_stack_height(visible_count, *, maximized=False,
                                 panel_height=290, handle_height=7):
    """Minimum stack height in pixels; no squeeze as witnesses are added."""
    visible = max(0, int(visible_count))
    if not visible:
        return 0
    if maximized:
        return int(panel_height)
    return visible * int(panel_height) + (visible - 1) * int(handle_height)


def normalized_witness_order(witness_ids, saved_ids=()):
    """Return a stable presentation order, without losing newly added witnesses.

    IDs are strictly scoped to the current project; duplicates and unknown
    IDs in persisted settings are ignored. The project order is used only
    for witnesses not mentioned in saved_ids. This never changes project.xml.
    """
    valid = list(dict.fromkeys(str(x) for x in witness_ids))
    valid_set = set(valid)
    result = []
    for x in saved_ids or ():
        wid = str(x)
        if wid in valid_set and wid not in result:
            result.append(wid)
    return result + [wid for wid in valid if wid not in result]


def ordered_visible_witnesses(order_ids, selected_ids, available_ids):
    """Keep visibility independent of order and ignore unavailable images."""
    selected, available = set(selected_ids or ()), set(available_ids or ())
    return [wid for wid in order_ids if wid in selected and wid in available]
