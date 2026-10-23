# -*- coding: utf-8 -*-
"""Viewer web : les flèches de tout panneau mènent le texte (V0.9.1.6),
comme sur le bureau depuis la V0.9.1.4 (test_gui_witness_route.py,
test_gui_witness_pages_route.py), pilotées dans Chromium (ignorées sans
Playwright ni Chromium).

Le témoin avance dans son propre ordre (son parcours), d'un texte à l'autre ;
le texte va à la ligne du pivot que désigne sa ligne, ou à son <pb> ; les
autres panneaux suivent le pivot ; ⤺ ramène le panneau sur la ligne reliée.
Un témoin par pages mène par ses <pb>, sa liste de folios aussi, ou par le
<locus from> d'un texte ; un panneau absent va au texte suivant ou précédent
qui a ce témoin. Les messages sont ceux du bureau."""
from __future__ import annotations

import json
import re

import pytest

from corpus_data import add_text_pages, copy_example, move_to_part, split_alignments
from test_v0916_viewer_texts import Viewer, browser  # noqa: F401  (fixture)


def _open(browser, project):  # noqa: F811
    return Viewer(browser, project)


@pytest.fixture
def single(browser, tmp_path):  # noqa: F811
    viewer = _open(browser, copy_example(tmp_path / "exemple"))
    yield viewer
    assert not viewer.errors, viewer.errors
    viewer.page.close()


def _text_apart(tmp_path, *, rename_t2=False):
    project = copy_example(tmp_path / "exemple")
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    if rename_t2:
        path = project.parent / "alignments" / "rls185" / "T2.json"
        data = json.loads(path.read_text(encoding="utf-8"))
        for index, page in enumerate(data["pages"]):
            page["id"] = f"autre-{index}"
            for field in ("iiif", "image", "image_name", "label"):
                page.pop(field, None)
        path.write_text(json.dumps(data), encoding="utf-8")
    return project


@pytest.fixture
def text(browser, tmp_path):  # noqa: F811
    viewer = _open(browser, _text_apart(tmp_path))
    yield viewer
    assert not viewer.errors, viewer.errors
    viewer.page.close()


def _arrow(viewer, wid, act):
    viewer.card(wid).locator(f"[data-act={act}]").click()


def _notice(viewer):
    return viewer.page.locator("#syncNotice").inner_text()


def _message(viewer, key, **values):
    text = viewer.text(key)
    for name, value in values.items():
        text = text.replace("{" + name + "}", str(value))
    return text


def _set_center(viewer, wid, index):
    viewer("([id,i])=>{const s=states.get(id);s.center=i;s.origin=i;renderWitness(id)}", [wid, index])


def _linked(viewer, wid, index):
    """Ligne du pivot que désigne l'élément ``index`` du panneau (la première
    dans l'ordre du pivot), ou None."""
    return viewer("""([id,i])=>{const w=witnessMap.get(id),s=states.get(id),it=s.physical[i];if(!it)return null;
        const keys=w.role==='base'?[itemKey(w,it)]:(it.l.base_keys||[]);let best=null,r=Infinity;
        for(const k of keys){const j=lineOrder.indexOf(k);if(j>=0&&j<r){r=j;best=k}}return best}""", [wid, index])


def _center(viewer, wid):
    return viewer("id=>states.get(id).center", wid)


# --- Édition en un seul fichier -------------------------------------------------------

def test_the_arrows_of_a_secondary_witness_lead_the_text(single):
    order = single("()=>lineOrder")
    single.select(order[30])
    start = _center(single, "T2")
    while _linked(single, "T2", start + 1) in (None, order[30]):
        start += 1
    _set_center(single, "T2", start)
    expected = _linked(single, "T2", start + 1)
    _arrow(single, "T2", "next")
    assert _center(single, "T2") == start + 1                    # T2 garde sa ligne
    assert single("()=>selectedKey") == expected
    assert single.center_key("T1") == expected                    # le pivot et P suivent
    assert expected in single("()=>{const s=states.get('P');return s.physical[s.center].l.base_keys}")


def test_an_unlinked_line_keeps_the_text_on_the_previous_linked_line(browser, tmp_path):  # noqa: F811
    project = copy_example(tmp_path / "exemple")
    path = project.parent / "alignments" / "T2.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    lines = sorted((line for page in data["pages"] for line in page["lines"]), key=lambda line: int(line["order"]))
    lines[41]["base_keys"] = []
    path.write_text(json.dumps(data), encoding="utf-8")
    viewer = _open(browser, project)
    try:
        index = viewer("o=>states.get('T2').physical.findIndex(it=>Number(it.l.order)===o)", int(lines[41]["order"]))
        previous = _linked(viewer, "T2", index - 1)
        viewer.select(previous)
        _set_center(viewer, "T2", index - 1)
        _arrow(viewer, "T2", "next")
        assert _center(viewer, "T2") == index
        assert viewer("()=>selectedKey") == previous
        line = viewer("()=>lineOrder").index(previous) + 1
        assert _notice(viewer) == _message(viewer, "status.witness_unlinked", witness="T2", line=line)
        # ⤺ ramène T2 sur la ligne reliée à la ligne de l'édition.
        _arrow(viewer, "T2", "home")
        assert _center(viewer, "T2") != index and previous in (_linked(viewer, "T2", _center(viewer, "T2")),
                                                                viewer("()=>{const s=states.get('T2');return (s.physical[s.center].l.base_keys||[])[0]}"))
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


def test_the_ends_of_the_manuscript(single):
    order = single("()=>lineOrder")
    single.select(order[0])
    _arrow(single, "T1", "prev")
    assert single("()=>selectedKey") == order[0]
    assert _notice(single) == _message(single, "status.witness_start", witness="T1")
    single.select(order[-1])
    _arrow(single, "T1", "next")
    assert _notice(single) == _message(single, "status.witness_end", witness="T1")


def test_the_pivot_arrows_still_go_line_by_line(single):
    order = single("()=>lineOrder")
    single.select(order[10])
    _arrow(single, "T1", "next")
    assert single("()=>selectedKey") == order[11] and single.center_key("T1") == order[11]
    _arrow(single, "T1", "prev")
    assert single("()=>selectedKey") == order[10]


# --- D'un texte à l'autre -------------------------------------------------------------

def test_the_pivot_crosses_into_a_text_synchronized_apart_and_back(text):
    order = text.data["meta"]["line_order"]
    text.select(order[115])
    _arrow(text, "T1", "next")
    assert text("()=>[activeSeg,selectedKey]") == [1, order[116]]
    text.select(order[116 + 164])
    _arrow(text, "T1", "next")
    assert text("()=>[activeSeg,selectedKey]") == [0, order[116 + 165]]
    _arrow(text, "T1", "prev")
    assert text("()=>[activeSeg,selectedKey]") == [1, order[116 + 164]]


def _to_last_line_before_the_text(viewer):
    order = viewer.data["meta"]["line_order"]
    viewer.select(order[115])
    for _ in range(400):
        following = _linked(viewer, "T2", _center(viewer, "T2") + 1)
        if following is None or order.index(following) > 115:
            return
        _arrow(viewer, "T2", "next")
    raise AssertionError("T2 n'atteint pas la fin de l'édition avant RLS_185")


def test_a_secondary_witness_crosses_into_the_text_in_its_own_order(text):
    _to_last_line_before_the_text(text)
    _arrow(text, "T2", "next")
    assert text("()=>activeSeg") == 1 and text.center_key("T2").startswith("~1~")
    assert text("()=>selectedKey").startswith("~1~")
    assert text.text("manuscript.text_absent") in text.card("P").inner_text()


def test_an_uncertain_place_is_said(browser, tmp_path):  # noqa: F811
    viewer = _open(browser, _text_apart(tmp_path, rename_t2=True))
    try:
        assert _linked(viewer, "T2", 0) is not None
        _to_last_line_before_the_text(viewer)
        _arrow(viewer, "T2", "next")
        assert viewer("()=>activeSeg") == 1
        assert _notice(viewer) == _message(viewer, "status.route_uncertain", witness="T2", text="rls185")
        assert not viewer.errors, viewer.errors
    finally:
        viewer.page.close()


# --- Témoins par pages et panneaux absents --------------------------------------------

def _text_keys(viewer):
    return [key for key in viewer.data["meta"]["line_order"] if key.startswith("~1~")]


def test_a_page_witness_leads_the_text_to_its_pb(text):
    keys = _text_keys(text)
    text.select(keys[1])
    assert text.folio("X") == "X-p0001"
    _arrow(text, "X", "next")
    assert text.folio("X") == "X-p0002"
    assert text("()=>[activeSeg,selectedKey]") == [1, keys[3]]       # les autres suivent le pivot
    _arrow(text, "X", "next")
    assert text.folio("X") == "X-p0003" and text("()=>selectedKey") == keys[20]


def test_a_page_witness_leads_from_the_edition_into_the_text(text):
    text.select(text.data["meta"]["line_order"][3])
    assert text("()=>activeSeg") == 0
    text("()=>{const s=states.get('X'),i=s.surfaceIndex.get('X-p0001');s.center=i;s.folioRef='X-p0001';renderWitness('X')}")
    _arrow(text, "X", "next")
    assert text("()=>[activeSeg,selectedKey]") == [1, _text_keys(text)[3]]
    assert text.folio("X") == "X-p0002"


def test_choosing_a_folio_in_the_list_leads_the_text(text):
    keys = _text_keys(text)
    text.select(keys[1])
    text.card("X").locator("select[data-folio]").select_option("X-p0003")
    assert text("()=>selectedKey") == keys[20] and text.folio("X") == "X-p0003"


def test_a_page_without_pb_leaves_the_text_with_a_message(text):
    keys = _text_keys(text)
    text.select(keys[30])
    text.card("X").locator("select[data-folio]").select_option("X-p0003")
    text.select(keys[30])
    text("()=>{const s=states.get('X'),i=s.surfaceIndex.get('X-p0003');s.center=i;s.folioRef='X-p0003';renderWitness('X')}")
    _arrow(text, "X", "next")
    assert text.folio("X") == "X-p0004" and text("()=>selectedKey") == keys[30]
    assert _notice(text) == _message(text, "status.page_unmarked", witness="X", folio="13v")


def test_the_locus_of_a_page_leads_to_the_start_of_the_text(text):
    text.select(text.data["meta"]["line_order"][3])
    text("()=>{const s=states.get('Y'),i=s.surfaceIndex.get('Y-p0001');s.center=i;s.folioRef='Y-p0001';renderWitness('Y')}")
    _arrow(text, "Y", "next")
    assert text("()=>[activeSeg,selectedKey]") == [1, _text_keys(text)[0]]
    assert text.folio("Y") == "Y-p0002"


def test_the_arrows_of_an_absent_panel_go_to_the_next_text_that_has_the_witness(text):
    edition = [key for key in text.data["meta"]["line_order"] if not key.startswith("~")]
    keys = _text_keys(text)
    text.select(keys[10])
    assert text.text("manuscript.text_absent") in text.card("P").inner_text()
    _arrow(text, "P", "next")
    assert text("()=>activeSeg") == 0 and edition.index(text("()=>selectedKey")) >= 116
    assert text.text("manuscript.text_absent") not in text.card("P").inner_text()
    text.select(keys[10])
    _arrow(text, "P", "prev")
    assert text("()=>activeSeg") == 0 and edition.index(text("()=>selectedKey")) <= 115


# --- Messages du viewer ---------------------------------------------------------------

def test_every_message_of_the_viewer_exists_in_the_seven_languages():
    from pathlib import Path

    from web_viewer.generator import HTML_TEMPLATE
    root = Path(__file__).resolve().parents[1] / "i18n"
    catalogs = {path.stem: set(re.findall(r'<string key="([^"]+)"', path.read_text(encoding="utf-8")))
                for path in root.glob("*.xml")}
    assert len(catalogs) == 7
    keys = set(re.findall(r"'((?:viewer|manuscript|status|folio|common)\.[A-Za-z0-9_.]+)'", HTML_TEMPLATE))
    assert {"status.witness_end", "status.route_uncertain", "status.page_unmarked", "manuscript.text_absent"} <= keys
    for language, found in catalogs.items():
        assert not keys - found, (language, sorted(keys - found))
