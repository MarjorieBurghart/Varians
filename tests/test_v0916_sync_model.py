# -*- coding: utf-8 -*-
"""Décisions de navigation du viewer (web_viewer/sync_model.js), testées avec
node (V0.9.1.6), et leur parité avec Python et le bureau :
- positions du texte de lecture : celles du rendu, de la recherche plein
  texte (VariansFullText.makeIndex) et de segment_views.doc_positions ;
- ligne du pivot ouverte à une position, texte d'une clé ;
- lacunes en cours à une position (règles de pivot_lines.lacunae_at) ;
- parcours d'un panneau d'un seul texte (witness_route) ;
- texte suivant ou précédent qui a le témoin (segment_model.present_stop)."""
from __future__ import annotations

import json
import shutil
import subprocess

import pytest

from corpus_data import (add_example_lacunae, add_text_pages, copy_example, insert_at, make_corpus,
                         move_to_part, split_alignments)
from pivot_lines import pivot_lb_pattern
from project_config import load_project
from web_viewer.generator import HTML_TEMPLATE, build_dataset, make_html
from web_viewer.segment_views import doc_positions

ROOT = __import__("pathlib").Path(__file__).resolve().parents[1]
MODULE = ROOT / "web_viewer" / "sync_model.js"
SEARCH = ROOT / "web_viewer" / "fulltext_search.js"


def _node(tmp_path, script, payload):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    data = tmp_path / "payload.json"
    data.write_text(json.dumps(payload), encoding="utf-8")
    js = (f"const S=require({json.dumps(str(MODULE))});const F=require({json.dumps(str(SEARCH))});"
          f"const D=JSON.parse(require('fs').readFileSync({json.dumps(str(data))},'utf8'));"
          f"const out=(()=>{{{script}}})();process.stdout.write(JSON.stringify(out));")
    run = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    return json.loads(run.stdout)


def _build(project, **options):
    data, _missing = build_dataset(load_project(project), **options)
    data.pop("i18n", None)
    return data


def _witness(data, wid):
    return next(w for w in data["witnesses"] if w["id"] == wid)


def _text_apart(root, *, lacunae=False):
    project = copy_example(root)
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    if lacunae:
        add_example_lacunae(project)
    else:
        add_text_pages(project, y_locus=True)
    return project


def _segments(data):
    return [seg for block in data["document"]["blocks"] for seg in block["segments"]]


def test_the_positions_are_those_of_the_render_the_search_and_python(tmp_path):
    data = _build(_text_apart(tmp_path / "exemple", lacunae=True))
    positions = doc_positions(data["document"])
    kinds = {pos: seg["kind"] for seg in _segments(data) for pos in [positions.get(id(seg))] if pos is not None}
    out = _node(tmp_path, """
      const index=S.docIndex(D.document.blocks), bad=[];
      for(const p of F.makeIndex(D.document.blocks))for(const loc of p.locations){
        const seg=index.items[loc.docPos];
        if(!seg||String(seg.text||'')[loc.offset]===undefined)bad.push(loc.docPos)}
      return {kinds:index.items.map(s=>s.kind),bad};""", data)
    assert out["bad"] == []
    assert out["kinds"] == [kinds[pos] for pos in range(len(kinds))]
    # Le rendu compte chaque segment d'un bloc rendu, et seulement eux (V0.9.3.0).
    assert "VariansSync.RENDERED.has(b.type)" in HTML_TEMPLATE


def test_the_text_and_the_line_open_at_a_position(tmp_path):
    data = _build(_text_apart(tmp_path / "exemple"))
    out = _node(tmp_path, """
      const index=S.docIndex(D.document.blocks), out={chips:[],texts:0,keys:[]};
      index.items.forEach((seg,pos)=>{
        if(seg.kind==='pb'&&seg.edref==='#X')out.chips.push([S.segAt(index,pos),S.lastLinked(index,pos)]);
        if(seg.kind==='text'&&seg.line_key&&S.lastLinked(index,pos)!==seg.line_key)out.texts++});
      for(const key of D.meta.line_order.filter((k,i)=>i%40===0))out.keys.push([key,S.segOfKey(key,D.meta.segments),S.segAt(index,S.positionOf(index,key))]);
      return out;""", data)
    route = _witness(data, "X")["route"]
    assert out["chips"] == [[1, stop["t"]] for stop in route]
    assert out["texts"] == 0
    assert out["keys"] and all(seg == (1 if key.startswith("~1~") else 0) == at for key, seg, at in out["keys"])


def _lacuna_project(root):
    """T2 en lacune de la ligne 101 à la ligne 131 de l'édition : la lacune
    entoure RLS_185, synchronisé à part (après la 116e ligne)."""
    project = _text_apart(root)
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    edition.write_text(insert_at(text, [(lbs[100][1], '<lacunaStart wit="#T2"/>'),
                                        (lbs[130][1], '<lacunaEnd wit="#T2"/>')]), encoding="utf-8")
    return project


def test_the_lacunae_at_a_position(tmp_path):
    data = _build(_lacuna_project(tmp_path / "exemple"))
    order = data["meta"]["line_order"]
    probes = {"before": order[99], "start": order[100], "edition": order[110], "text": order[116 + 50],
              "after_text": order[116 + 165 + 5], "end": order[116 + 165 + 14]}
    out = _node(tmp_path, """
      const index=S.docIndex(D.data.document.blocks), out={};
      for(const [name,key] of Object.entries(D.probes))out[name]=[...S.lacunaeAt(index,S.positionOf(index,key))];
      return out;""", {"data": data, "probes": probes})
    # La lacune court dans l'édition, d'une partie à l'autre ; le texte à part repart sans lacune.
    assert out == {"before": [], "start": ["T2"], "edition": ["T2"], "text": [], "after_text": ["T2"], "end": []}


def test_a_lacuna_without_end_runs_to_the_end_and_an_end_without_start_is_ignored(tmp_path):
    blocks = [{"type": "p", "segments": [
        {"kind": "lacuna", "start": False, "wit": ["B"]},
        {"kind": "text", "text": "a", "line_key": "p::1"},
        {"kind": "lacuna", "start": True, "wit": ["B", "C"]},
        {"kind": "text", "text": "b", "line_key": "p::2"},
        {"kind": "lacuna", "start": True, "wit": ["C"], "seg": 1},
        {"kind": "text", "text": "c", "line_key": "~1~q::1", "seg": 1},
        {"kind": "lacuna", "start": False, "wit": ["C"]},
        {"kind": "text", "text": "d", "line_key": "p::3"}]}]
    out = _node(tmp_path, """const index=S.docIndex(D);
      return {at:[1,3,5,7].map(p=>[...S.lacunaeAt(index,p)].sort()),
              starts:[3,7].map(p=>[...S.lacunaStarts(index,p).entries()].sort()),
              line:S.lastLinked(index,2)};""", blocks)
    assert out["at"] == [[], ["B", "C"], ["C"], ["B"]]
    # Le début de chaque lacune en cours (le premier, si elle recommence).
    assert out["starts"] == [[["B", 2], ["C", 2]], [["B", 2]]]
    assert out["line"] == "p::1"


def test_a_lacuna_marker_gives_the_line_open_at_its_place(tmp_path):
    blocks = [{"type": "p", "segments": [
        {"kind": "text", "text": "a", "line_key": "p::1"},
        {"kind": "lacuna", "start": True, "wit": ["B"], "line_key": "p::2"},
        {"kind": "text", "text": "b", "line_key": "p::2"}]}]
    assert _node(tmp_path, "return S.lastLinked(S.docIndex(D),1);", blocks) == "p::2"


def test_a_line_anchor_gives_the_place_of_a_line_omitted_by_the_text_shown(tmp_path):
    # V0.9.3.0 : quand le témoin affiché omet un passage, la ligne du pivot
    # ouverte dans ce passage n'a pas de texte ; son repère donne sa place.
    blocks = [{"type": "p", "segments": [
        {"kind": "text", "text": "a", "line_key": "p::1"},
        {"kind": "line-anchor", "line_key": "p::2"},
        {"kind": "text", "text": "b", "line_key": "p::3"}]}]
    assert _node(tmp_path, "const i=S.docIndex(D);return [S.positionOf(i,'p::2'),S.lastLinked(i,1)];",
                 blocks) == [1, "p::2"]


def test_the_route_of_a_panel_of_one_text_is_that_of_witness_route(tmp_path):
    from witness_resource_refresh import flatten_primary, flatten_secondary
    from witness_route import Source, witness_route
    project = copy_example(tmp_path / "exemple")
    path = project.parent / "alignments" / "T2.json"
    t2 = json.loads(path.read_text(encoding="utf-8"))
    lines = sorted((line for page in t2["pages"] for line in page["lines"]), key=lambda line: int(line["order"]))
    lines[0]["base_keys"] = []          # non reliée, en tête : mène à la ligne reliée qui la suit
    lines[41]["base_keys"] = []
    t1 = json.loads((project.parent / "alignments" / "T1.json").read_text(encoding="utf-8"))
    pivot, by_key = flatten_primary(t1)
    keys = [item["key"] for item in pivot]
    expected = {}
    for wid, cache, is_base in (("T1", t1, True), ("T2", t2, False)):
        route = witness_route(wid, [Source(None, cache, is_base, by_key)])
        expected[wid] = [[stop.key, keys[stop.ordinal], 0 if stop.linked else 1] for stop in route.stops]
    items = {"T1": [{"key": item["key"]} for item in pivot],
             "T2": [{"key": item["key"], "base_keys": item["l"].get("base_keys") or []}
                    for item in flatten_secondary(t2)[0]]}
    out = _node(tmp_path, """
      const rank=new Map(D.keys.map((k,i)=>[k,i])),rankOf=k=>rank.get(k),out={};
      for(const wid of ['T1','T2'])out[wid]=S.lineStops(D.items[wid],wid==='T1',rankOf).map(s=>[s.k,s.t,s.u?1:0]);
      const stop=S.panelStop(D.items.T2,42,false,rankOf);out.panel=[stop.k,stop.t,stop.u?1:0];
      out.none=S.panelStop(D.items.T2,99999,false,rankOf);
      return out;""", {"keys": keys, "items": items})
    assert out["T1"] == expected["T1"]
    assert out["T2"] == expected["T2"]
    assert out["panel"] == expected["T2"][42] and out["none"] is None


def test_the_steps_of_a_route(tmp_path):
    data = _build(_text_apart(tmp_path / "exemple"))
    route = _witness(data, "T1")["route"]
    out = _node(tmp_path, """
      const map=S.routeIndex(D);
      const r=k=>{const x=S.step(D,map,D[k].s,D[k].k,1);return x&&[x.index,x.stop.s]};
      return {into:r(115),back:r(116+164),end:S.step(D,map,D[D.length-1].s,D[D.length-1].k,1),
              start:S.step(D,map,0,D[0].k,-1),outside:S.step(D,map,0,'inconnu',1)};""", route)
    # De la dernière ligne de l'édition avant RLS_185 à sa première ; de sa dernière à la 117e ligne.
    assert out == {"into": [116, 1], "back": [116 + 165, 0], "end": None, "start": None, "outside": None}


def _python_present_stops(data, wid, cases):
    """Indices de segment_model.present_stop sur le parcours exporté."""
    import segment_model
    from witness_route import Stop, WitnessRoute
    meta = data["meta"]
    edition_keys = [key for key in meta["line_order"] if not key.startswith("~")]
    rank = {key: i for i, key in enumerate(edition_keys)}
    exported = _witness(data, wid)["route"]
    stops = tuple(Stop(None if stop["s"] == 0 else stop["s"], stop["k"], "",
                       rank.get(stop["t"]) if stop["s"] == 0 else 0, not stop.get("u"),
                       (stop["p"],) if "p" in stop else None) for stop in exported)
    route = WitnessRoute(wid, stops, (), ())
    anchors = {s["index"]: s["anchor"] for s in meta["segments"]}
    order = [s["index"] for s in meta["segments"] if s["index"]]
    found = []
    for here, ordinal, delta in cases:
        stop = segment_model.present_stop(route, anchors.get, order, here or None, ordinal, delta)
        found.append(-1 if stop is None else route.index(stop.segment, stop.key))
    return edition_keys, found


@pytest.mark.parametrize("corpus,wid", [("exemple", "P"), ("exemple", "T2"), ("corpus", "B"), ("corpus", "D"),
                                        ("corpus", "A")])
def test_the_next_text_that_has_the_witness_is_that_of_the_desktop(tmp_path, corpus, wid):
    data = _build(_text_apart(tmp_path / "exemple") if corpus == "exemple" else make_corpus(tmp_path / "corpus"))
    texts = [s["index"] for s in data["meta"]["segments"] if s["index"]]
    cases = [(k, 0, delta) for k in texts for delta in (1, -1)]
    cases += [(0, ordinal, delta) for ordinal in (0, 3, 10, 115, 116, 200, 10_000) for delta in (1, -1)]
    edition_keys, expected = _python_present_stops(data, wid, cases)
    out = _node(tmp_path, """
      const rank=new Map(D.keys.map((k,i)=>[k,i])),rankOf=k=>rank.get(k);
      return D.cases.map(([here,ordinal,delta])=>S.presentStop(D.route,D.segments,here,ordinal,delta,rankOf));""",
                {"keys": edition_keys, "cases": cases, "route": _witness(data, wid)["route"],
                 "segments": data["meta"]["segments"]})
    assert out == expected
    if wid == "P":
        # P n'a pas RLS_185 : au-delà, l'édition après la 116e ligne ; en deçà, avant.
        route = _witness(data, "P")["route"]
        after, before = out[0], out[1]
        assert edition_keys.index(route[after]["t"]) >= 116 and edition_keys.index(route[before]["t"]) <= 115


def test_the_page_stops_of_a_text_are_those_of_python(tmp_path):
    from folio_navigation import Folio, folio_lookup, pb_folio
    from web_viewer.segment_views import page_marks
    project = copy_example(tmp_path / "exemple")
    add_example_lacunae(project)
    data = _build(project)
    x = _witness(data, "X")
    folios = [Folio(**f) for f in x["folios"]]
    expected = [[0, mark.folio, mark.location[0]] for mark in page_marks(data["document"], "X", {0: folios}, {})[0]]
    lookup = folio_lookup(folios)
    refs = {}
    for seg in _segments(data):
        if seg["kind"] == "pb":
            folio = pb_folio(seg.get("facs"), seg.get("edref"), seg.get("label"), "X", lookup)
            refs[f"{seg.get('edref')}|{seg.get('label')}"] = folio.ref if folio else None
    out = _node(tmp_path, """
      const index=S.docIndex(D.data.document.blocks);
      return S.pageStops(index,seg=>D.refs[seg.edref+'|'+seg.label]).map(s=>[s.s,s.k,s.p]);""",
                {"data": data, "refs": refs})
    assert out == expected and len(out) == 2


def test_the_module_is_in_the_viewer():
    assert "__SYNC_JS__" in HTML_TEMPLATE
    html = make_html({"meta": {"title": "Démo", "has_images": False, "base_witness": "A"}, "witnesses": [],
                      "document": {"blocks": []},
                      "i18n": {"default": "fr", "fallback": "en", "catalogs": {"fr": {}}, "languages": []}})
    assert "root.VariansSync = api" in html and "__SYNC_JS__" not in html


# V0.9.3.0 : tous les blocs rendus (titres, vers, entrées de liste, cellules,
# légendes, notes entre deux blocs) ont leurs positions, les mêmes pour le
# rendu, la recherche et Python.
STRUCTURED = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
              '<div><head><lb edRef="#A"/>Titulus</head><p>prosa <note>nota</note></p>'
              '<lg><l n="1"><lb edRef="#A"/>uersus primus</l><pb n="2r" facs="#f2r"/><l n="2">uersus secundus</l></lg>'
              '<list><item>primum<list><item>sub</item></list></item></list><note>inter</note>'
              '<table><head>Tabula</head><row><cell role="label">Folium</cell><cell>12r</cell></row></table>'
              '<figure><figDesc>Imago</figDesc></figure>'
              '<sp><speaker>Petrus</speaker><p>dixit</p><stage>Exit.</stage></sp></div></body></text></TEI>')


def test_every_rendered_block_has_the_same_positions_in_the_render_the_search_and_python(tmp_path):
    import xml.etree.ElementTree as ET
    from folio_navigation import Folio
    from web_viewer.legacy_v11_core import RENDERED_BLOCKS, extract_reading_document
    from web_viewer.segment_views import RENDERED_BLOCKS as VIEWS_RENDERED, page_marks
    reading = extract_reading_document(None, "#A", root=ET.fromstring(STRUCTURED), base_line_keys=["P::1", "P::2"])
    flat = [seg for block in reading["blocks"] if block["type"] in RENDERED_BLOCKS for seg in block["segments"]]
    positions = doc_positions(reading)
    assert [positions[id(seg)] for seg in flat] == list(range(len(flat))) and len(positions) == len(flat)
    assert VIEWS_RENDERED == RENDERED_BLOCKS
    out = _node(tmp_path, """
      const index=S.docIndex(D.blocks), search=F.makeIndex(D.blocks), bad=[];
      for(const p of search)for(const loc of p.locations){const seg=index.items[loc.docPos];
        if(!seg||String(seg.text||'')[loc.offset]===undefined)bad.push(loc.docPos)}
      const hits=q=>F.find(search,q).map(h=>h.docPos);
      return {kinds:index.items.map(s=>s.kind), bad, rendered:[...S.RENDERED].sort(), search:[...F.RENDERED].sort(),
              title:hits('Titulus'), verse:hits('secundus'), item:hits('sub'), cell:hits('Folium'), caption:hits('Imago'),
              speaker:hits('Petrus'), stage:hits('Exit'),
              lines:index.lines};""", reading)
    assert out["rendered"] == out["search"] == sorted(RENDERED_BLOCKS)
    assert out["kinds"] == [seg["kind"] for seg in flat] and out["bad"] == []
    texts = {seg.get("text", "").strip(): positions[id(seg)] for seg in flat if seg["kind"] == "text"}
    assert out["title"] == [texts["Titulus"]] and out["verse"] == [texts["uersus secundus"]]
    assert out["item"] == [texts["sub"]] and out["cell"] == [texts["Folium"]] and out["caption"] == [texts["Imago"]]
    assert out["speaker"] == [texts["Petrus"]] and out["stage"] == [texts["(Exit.)"]]
    # La ligne ouverte à chaque position : celle du titre, puis celle des vers.
    assert out["lines"][texts["Titulus"]] == "P::1" and out["lines"][texts["uersus secundus"]] == "P::2"
    # Un <pb/> entre deux vers : sa position est entre eux.
    pb = next(seg for seg in flat if seg["kind"] == "pb")
    assert texts["uersus primus"] < positions[id(pb)] < texts["uersus secundus"]
    marks = page_marks(reading, "A", {0: [Folio("f2r", "f2r", "2r")]}, {})
    assert [mark.location[0] for mark in marks[0]] == [positions[id(pb)]]
