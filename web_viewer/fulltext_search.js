/* Varians A03 — Recherche de lecture hors ligne, sans modification de la TEI.
 * Index construit sur les seuls segments éditoriaux visibles, bloc par bloc
 * (RENDERED : les blocs affichés, comme VariansSync.RENDERED ; V0.9.3.0).
 * L'index normalisé porte les offsets de code UTF-16 d'origine pour un
 * surlignage fidèle.
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.VariansFullText = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  const RENDERED = new Set(['p', 'head', 'l', 'item', 'cell', 'caption', 'note', 'speaker', 'stage']);
  function normalize(value, options = {}) {
    const map = [], out = [];
    for (let i = 0; i < String(value ?? '').length;) {
      const char = String(value).codePointAt(i);
      const source = String.fromCodePoint(char), width = source.length;
      // U+2060 marque un mot coupé par une ligne du pivot (<lb break="no"/>) :
      // il n'est pas cherché (red team 2, D2).
      if (char === 0x2060) { i += width; continue; }
      let folded = source.toLowerCase();
      if (options.medieval) {
        folded = Array.from(folded).map(ch => {
          if (options.uv && ch === 'v') return 'u';
          if (options.ij && ch === 'j') return 'i';
          if (options.ct && ch === 't') return 'c';
          return ch;
        }).join('');
      }
      for (let j = 0; j < folded.length; j++) { out.push(folded[j]); map.push(i); }
      i += width;
    }
    return { text: out.join(''), positions: map };
  }
  function makeIndex(blocks) {
    const paragraphs = []; let docPos = 0;
    for (const block of blocks || []) {
      if (!RENDERED.has(block.type)) continue;
      let text = ''; const locations = [];
      for (const seg of block.segments || []) {
        const currentPos = docPos++;
        if (seg.kind !== 'text' && seg.kind !== 'editorial-ref') continue;
        for (let j = 0; j < String(seg.text || '').length; j++) {
          locations.push({docPos: currentPos, offset: j, lineKey: seg.line_key || ''});
        }
        text += String(seg.text || '');
      }
      paragraphs.push({text, locations});
    }
    return paragraphs;
  }
  function find(index, query, options={}, limit=5000) {
    const term = normalize(String(query || '').trim(), options).text;
    if (!term) return [];
    const hits = [];
    for (const p of index) {
      const normalized = normalize(p.text, options);
      let at=0;
      while ((at = normalized.text.indexOf(term, at)) !== -1) {
        const first=normalized.positions[at], last=normalized.positions[at+term.length-1];
        if (first == null || last == null) break;
        const pieces=[]; let previous;
        for (let i=first; i<=last; i++) {
          const loc=p.locations[i];if (!loc) continue;
          if (previous && previous.docPos===loc.docPos && previous.end===loc.offset) previous.end++;
          else {previous={docPos:loc.docPos,start:loc.offset,end:loc.offset+1};pieces.push(previous);}
        }
        const start=p.locations[first], anchor=pieces.length?p.locations[first]:null;
        hits.push({pieces, docPos:anchor?.docPos??null, lineKey:
          p.locations.slice(first,last+1).find(x=>x.lineKey)?.lineKey || '',
          excerpt:p.text.slice(Math.max(0,first-35),Math.min(p.text.length,last+36)).replace(/\s+/g,' ').trim()});
        if(hits.length>=limit)return hits;
        at += Math.max(1,term.length);
      }
    }
    return hits;
  }
  function spansByPosition(hits) {
    const byPos = new Map();
    for (let i=0; i<hits.length; i++) for (const piece of hits[i].pieces) {
      if (!byPos.has(piece.docPos)) byPos.set(piece.docPos, []);
      byPos.get(piece.docPos).push({start:piece.start, end:piece.end, id:i});
    }
    for (const parts of byPos.values()) parts.sort((a,b)=>a.start-b.start||a.end-b.end);
    return byPos;
  }
  function splitText(text, pos, hitsOrMap, escapeHtml) {
    const parts = hitsOrMap instanceof Map ? (hitsOrMap.get(pos)||[]) : (spansByPosition(hitsOrMap).get(pos)||[]);
    let cursor=0;
    parts.sort((a,b)=>a.start-b.start||a.end-b.end);
    let html='';
    for(const part of parts){
      if(part.start<cursor)continue;
      html+=escapeHtml(text.slice(cursor,part.start));
      html+='<mark class="search-hit" data-hit="'+part.id+'">'+escapeHtml(text.slice(part.start,part.end))+'</mark>';
      cursor=part.end;
    }
    return html+escapeHtml(text.slice(cursor));
  }
  return {RENDERED,normalize,makeIndex,find,spansByPosition,splitText};
});
