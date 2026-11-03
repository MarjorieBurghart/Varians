# -*- coding: utf-8 -*-
"""Red team 2 (robustesse).

- A10 : un document très imbriqué. L'aperçu le refusait (« Excessive depth
  in document: 256 »), l'export web levait RecursionError (dès ~400
  niveaux), la copie des images d'un paquet DOCX/ODT/EPUB le refusait.
- A8 : l'actualisation automatique de l'aperçu, après une pause de la
  frappe, figeait la fenêtre le temps de la transformation (0,85 s par Mo) :
  elle se fait hors du fil de la fenêtre ; seul l'affichage y reste, et un
  résultat dépassé par une nouvelle frappe est jeté."""
from __future__ import annotations

import shutil
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEI_NS = "http://www.tei-c.org/ns/1.0"


def _deep(depth):
    return (f'<TEI xmlns="{TEI_NS}"><teiHeader><fileDesc><titleStmt><title>T</title></titleStmt></fileDesc>'
            f'</teiHeader><text><body><p>a {"<hi>" * depth}x{"</hi>" * depth} b</p></body></text></TEI>')


def test_the_preview_shows_a_very_deep_document(qapp):
    import formatted_view
    html, _engine = formatted_view.transform_with_xslt(_deep(400), ROOT / "rendering" / "tei-to-html.xsl", {})
    assert "x" in html


def test_the_web_export_of_a_very_deep_document(qapp, tmp_path):
    from web_viewer.generator import generate
    root = tmp_path / "projet"
    (root / "xml").mkdir(parents=True)
    (root / "web_output").mkdir()
    shutil.copytree(ROOT / "rendering", root / "rendering")
    (root / "project.xml").write_text(
        "<?xml version='1.0' encoding='utf-8'?>\n<teiManuscriptProject version=\"1\"><title>Essai</title>"
        '<edition file="xml/edition.xml"/><interface language="fr"/>'
        '<rendering xsltMode="builtin" css="rendering/tei.css" customElements="rendering/custom-elements.xml"/>'
        '<webViewer outputDir="web_output" filename="viewer.html"/><witnesses base="A">'
        '<witness id="A" label="A" role="base"><images type="none"/></witness></witnesses></teiManuscriptProject>',
        encoding="utf-8")
    (root / "xml" / "edition.xml").write_text(_deep(1500), encoding="utf-8")
    limit = sys.getrecursionlimit()
    output, _missing, data = generate(root / "project.xml")
    assert output.exists() and "x" in output.read_text(encoding="utf-8")
    assert sys.getrecursionlimit() == limit


def test_the_images_of_a_package_are_read_from_a_very_deep_document(tmp_path):
    import xslt_engines
    source = tmp_path / "edition.xml"
    source.write_text(_deep(400), encoding="utf-8")
    tree = xslt_engines.source_tree(source)
    assert tree.getroot().tag == f"{{{TEI_NS}}}TEI"


def test_the_automatic_preview_is_made_outside_the_window_thread(open_window, example_project, qtbot, monkeypatch):
    import formatted_view
    window = open_window(example_project)
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: not view.dirty_preview, timeout=20000)
    qtbot.wait(300)                 # le recentrage qui suit le changement d'onglet
    threads = []
    original = formatted_view.transform_with_xslt

    def recorded(*args, **kwargs):
        threads.append(threading.current_thread() is threading.main_thread())
        return original(*args, **kwargs)

    monkeypatch.setattr(formatted_view, "transform_with_xslt", recorded)
    view.preview_timer.setInterval(50)
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.positions().qt(text.index(" et ", text.index("<body")) + 3))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("QUIDAMNOVUM")
    qtbot.waitUntil(lambda: "QUIDAMNOVUM" in view.preview.toPlainText(), timeout=30000)
    assert threads and not any(threads)
    assert not view.dirty_preview


def test_a_result_overtaken_by_new_typing_is_discarded(open_window, example_project, qtbot, monkeypatch):
    import formatted_view
    window = open_window(example_project)
    view = window.formatted_view
    window.left_tabs.setCurrentWidget(view)
    qtbot.waitUntil(lambda: not view.dirty_preview, timeout=20000)
    qtbot.wait(300)                 # le recentrage qui suit le changement d'onglet
    gate = threading.Event()
    original = formatted_view.transform_with_xslt
    calls = []

    def slow(*args, **kwargs):
        calls.append(1)
        if len(calls) == 1:
            gate.wait(10)
        return original(*args, **kwargs)

    monkeypatch.setattr(formatted_view, "transform_with_xslt", slow)
    view.preview_timer.setInterval(50)
    text = window.editor.toPlainText()
    cursor = window.editor.textCursor()
    cursor.setPosition(window.editor.positions().qt(text.index(" et ", text.index("<body")) + 3))
    window.editor.setTextCursor(cursor)
    window.editor.insertPlainText("PRIMUM")
    qtbot.waitUntil(lambda: len(calls) == 1, timeout=10000)
    window.editor.insertPlainText("SECUNDUM")          # pendant la première transformation
    gate.set()
    qtbot.waitUntil(lambda: "PRIMUMSECUNDUM" in view.preview.toPlainText(), timeout=30000)
    qtbot.wait(300)
    assert "PRIMUMSECUNDUM" in view.preview.toPlainText()
