# -*- coding: utf-8 -*-
"""Red team 2 (robustesse, B3 ; D1) dans la fenêtre : un <lb edRef="#T1"/>
mis en commentaire (un passage retiré, par exemple) ne compte plus comme une
ligne du pivot. La barre d'état annonçait « 3791 lignes — attendu 3790 » et
toutes les lignes suivantes étaient décalées d'une dans les panneaux des
témoins, alors que le viewer web et les feuilles XSLT l'ignorent."""
from __future__ import annotations

from app_context import tr

COMMENTED = '<!-- <lb edRef="#T1"/> passage retiré -->'


def _cursor_at(window, position):
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.positions().qt(position))
    window.editor.setTextCursor(cursor)


def test_a_commented_pivot_lb_is_not_a_line(open_window, example_project):
    window = open_window(example_project)
    spans = window.lb_spans()
    count = len(spans)
    assert window.expected_base_lines == count
    _cursor_at(window, spans[10][1])
    window.editor.insertPlainText(COMMENTED)
    assert len(window.lb_spans()) == count
    window.validate_text(False)
    assert window.structure_status.text() == tr("status.structure.ok", base=window.witness_siglum(window.base_id),
                                                count=count)
    # La fin de la 21e ligne réelle est la 21e ligne du pivot (rang 20).
    _cursor_at(window, window.lb_spans()[20][1])
    assert window.ordinal_at_cursor() == 20
    # Le commentaire défait (« <!-- » effacé) : le <lb/> redevient une ligne.
    text = window.editor.toPlainText()
    start = text.index("<!--")
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.positions().qt(start))
    cursor.setPosition(window.editor.positions().qt(start + 4), cursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    text = window.editor.toPlainText()
    closing = text.index("-->", start)
    cursor.setPosition(window.editor.positions().qt(closing))
    cursor.setPosition(window.editor.positions().qt(closing + 3), cursor.MoveMode.KeepAnchor)
    cursor.removeSelectedText()
    assert len(window.lb_spans()) == count + 1
