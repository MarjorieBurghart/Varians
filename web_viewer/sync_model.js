/* Varians V0.9.1.6 — Décisions de navigation du viewer, sans DOM.
 * Textes d'une édition assemblée, lacunes et parcours d'un témoin, selon les
 * règles du bureau (witness_route, segment_model, lacunae). Les positions sont
 * celles du rendu (renderDocument), de la recherche (VariansFullText.makeIndex)
 * et de Python (segment_views.doc_positions) : chaque segment d'un bloc p.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.VariansSync = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  // Index du texte de lecture : pour chaque position, le texte (seg) et la
  // ligne du pivot de ce texte ouverte à cet endroit ; les repères de lacune.
  // La ligne courante est propre à chaque texte et suit aussi les blocs non
  // rendus, comme l'extracteur.
  function docIndex(blocks) {
    const segs = [], lines = [], items = [], lacunae = [], firstPos = new Map(), current = new Map();
    for (const block of blocks || []) {
      const rendered = block.type === 'p';
      for (const seg of block.segments || []) {
        const k = Number(seg.seg || 0);
        if ((seg.kind === 'text' || seg.kind === 'pb' || seg.kind === 'lacuna') && seg.line_key) current.set(k, String(seg.line_key));
        if (!rendered) continue;
        const pos = segs.length;
        segs.push(k); lines.push(current.has(k) ? current.get(k) : null); items.push(seg);
        if (seg.kind === 'text' && seg.line_key && !firstPos.has(String(seg.line_key))) firstPos.set(String(seg.line_key), pos);
        if (seg.kind === 'lacuna') lacunae.push({pos, seg: k, start: !!seg.start, wit: (seg.wit || []).map(String)});
      }
    }
    return {segs, lines, items, lacunae, firstPos};
  }
  function clamp(index, pos) {
    const n = index.segs.length;
    return n ? Math.max(0, Math.min(n - 1, Number(pos) || 0)) : -1;
  }
  // Texte et ligne du pivot ouverte à une position (null avant la première).
  function segAt(index, pos) { const p = clamp(index, pos); return p < 0 ? 0 : index.segs[p]; }
  function lastLinked(index, pos) { const p = clamp(index, pos); return p < 0 ? null : index.lines[p]; }
  function positionOf(index, key) { return index.firstPos.has(String(key)) ? index.firstPos.get(String(key)) : -1; }
  // Texte d'une clé de ligne : celui dont elle porte le préfixe (~1~…), sinon l'édition.
  function segOfKey(key, segments) {
    for (const s of segments || []) if (s.prefix && String(key ?? '').startsWith(s.prefix)) return Number(s.index);
    return 0;
  }
  // Lacunes en cours à une position : {témoin: position de son début}, d'après
  // les repères de son texte jusqu'à elle (pivot_lines.lacunae_at). Une lacune
  // sans fin court jusqu'à la fin du texte ; une fin sans début est ignorée ;
  // un début dans une lacune déjà ouverte n'en change pas le début ; dans
  // l'édition, elle continue d'une partie à l'autre et après un texte à part ;
  // un texte à part repart sans lacune.
  function lacunaStarts(index, pos) {
    const p = clamp(index, pos), state = new Map();
    if (p < 0) return state;
    const k = index.segs[p];
    for (const e of index.lacunae) {
      if (e.pos > p) break;
      if (e.seg !== k) continue;
      for (const w of e.wit) { if (!e.start) state.delete(w); else if (!state.has(w)) state.set(w, e.pos); }
    }
    return state;
  }
  function lacunaeAt(index, pos) { return new Set(lacunaStarts(index, pos).keys()); }
  // Parcours d'un panneau par lignes d'un seul texte, dans l'ordre du panneau :
  // chaque élément mène à la ligne du pivot qu'il désigne (la première dans
  // l'ordre du pivot) ; une ligne non reliée mène à la ligne reliée qui la
  // précède (à défaut, à celle qui la suit) : witness_route._carry_ordinals.
  // items : [{key, base_keys}] ; rankOf(clé du pivot) : son rang, ou undefined.
  function lineStops(items, isBase, rankOf, seg = 0) {
    const stops = (items || []).map(it => {
      let target = null, best = Infinity;
      for (const key of (isBase ? [it.key] : (it.base_keys || []))) {
        const r = rankOf(String(key));
        if (r !== undefined && r !== null && r < best) { best = r; target = String(key); }
      }
      return {s: seg, k: String(it.key), t: target};
    });
    let previous = null;
    for (const stop of stops) {
      if (stop.t !== null) previous = stop.t;
      else { stop.u = 1; stop.t = previous; }
    }
    let following = null;
    for (let i = stops.length - 1; i >= 0; i--) {
      const stop = stops[i];
      if (!stop.u) following = stop.t;
      else if (stop.t === null) stop.t = following;
    }
    return stops;
  }
  // Parcours d'un témoin par pages d'un seul texte : ses <pb>, dans l'ordre du
  // texte ; resolve(segment pb) donne le folio, ou null s'il ne le concerne pas.
  function pageStops(index, resolve) {
    const stops = [];
    index.items.forEach((seg, pos) => {
      if (seg.kind !== 'pb') return;
      const ref = resolve(seg, pos);
      if (ref) stops.push({s: index.segs[pos], k: String(ref), p: pos, t: index.lines[pos]});
    });
    return stops;
  }
  function routeIndex(route) {
    const map = new Map();
    (route || []).forEach((stop, i) => { const id = stop.s + '\u0001' + stop.k; if (!map.has(id)) map.set(id, i); });
    return map;
  }
  // Arrêt à delta pas de l'élément (s, k) : {stop, index}, ou null hors du
  // parcours ou au-delà de ses bouts.
  function step(route, map, s, k, delta) {
    const i = map.get(s + '\u0001' + k);
    if (i === undefined) return null;
    const j = i + Number(delta);
    return j >= 0 && j < route.length ? {stop: route[j], index: j} : null;
  }
  // Arrêt d'un élément hors du parcours (witness_sync._panel_stop) : la ligne
  // du pivot qu'il désigne, ou celle de la ligne reliée qui le précède.
  function panelStop(items, i, isBase, rankOf, seg = 0) {
    if (!items || i < 0 || i >= items.length) return null;
    const stops = lineStops(items.slice(0, i + 1), isBase, rankOf, seg), stop = stops[i];
    if (stop.u && stop.t === null) return null;
    return stop;
  }
  // Premier arrêt du témoin dans le texte suivant (step > 0), ou dernier dans le
  // texte précédent, où il est présent, dans l'ordre de l'édition
  // (segment_model.present_stop) ; -1 s'il n'y en a pas. hereSeg : le texte
  // affiché ; hereRank : la ligne du pivot de l'édition, s'il s'agit d'elle.
  // rankOf(clé) : rang d'une ligne du pivot de l'édition.
  function presentStop(route, segments, hereSeg, hereRank, delta, rankOf) {
    const texts = (segments || []).map(s => Number(s.index)).filter(k => k > 0).sort((a, b) => a - b);
    const anchors = new Map((segments || []).map(s => [Number(s.index), Number(s.anchor || 0)]));
    const after = texts.length + 1;
    const place = (s, rank) => s ? [anchors.get(s) || 0, texts.includes(s) ? texts.indexOf(s) : after]
      : [rank === undefined || rank === null ? -1 : rank, after];
    const cmp = (a, b) => a[0] - b[0] || a[1] - b[1];
    const here = place(Number(hereSeg || 0), hereRank || 0);
    let found = null;
    (route || []).forEach((stop, i) => {
      const key = place(stop.s, stop.s ? null : (stop.t === null || stop.t === undefined ? undefined : rankOf(stop.t)));
      const beyond = delta > 0 ? cmp(key, here) > 0 : cmp(key, here) < 0;
      if (beyond && (found === null || (delta > 0 ? cmp(key, found.key) < 0 : cmp(key, found.key) >= 0))) found = {key, i};
    });
    if (found === null) return -1;
    const s = route[found.i].s;
    if (!s) return found.i;
    if (delta > 0) return route.findIndex(stop => stop.s === s);
    for (let i = route.length - 1; i >= 0; i--) if (route[i].s === s) return i;
    return -1;
  }
  return {docIndex, segAt, lastLinked, positionOf, segOfKey, lacunaStarts, lacunaeAt, lineStops, pageStops,
          routeIndex, step, panelStop, presentStop};
});
