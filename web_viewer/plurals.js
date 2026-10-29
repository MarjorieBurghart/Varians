/* Varians V0.9.3.4 — Formes plurielles des textes du viewer, sans DOM.
 * Mêmes règles que l'éditeur (i18n.py : plural_category, expand_plurals) :
 * syntaxe ICU « {count, plural, one {# ligne} other {# lignes}} », « # » pour
 * le nombre, « =0 {…} » pour une valeur exacte, catégories CLDR des nombres
 * entiers ; une catégorie absente retombe sur « other ».
 */
(function(root, factory) {
  const api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  root.VariansPlural = api;
})(typeof globalThis !== 'undefined' ? globalThis : this, function() {
  'use strict';
  function category(language, number) {
    const code = String(language || '').replace('_', '-').split('-')[0].toLowerCase();
    const n = Math.abs(Math.trunc(Number(number)));
    if (code === 'ja') return 'other';
    if (code === 'fr') return n === 0 || n === 1 ? 'one' : 'other';
    if (code === 'cs') return n === 1 ? 'one' : (n >= 2 && n <= 4 ? 'few' : 'other');
    if (code === 'ru') {
      if (n % 10 === 1 && n % 100 !== 11) return 'one';
      if (n % 10 >= 2 && n % 10 <= 4 && !(n % 100 >= 12 && n % 100 <= 14)) return 'few';
      return 'many';
    }
    return n === 1 ? 'one' : 'other';
  }
  const START = /\{\s*([A-Za-z0-9_]+)\s*,\s*plural\s*,/g;
  const SELECTOR = /\s*(=\d+|[a-z]+)\s*\{/y;
  function closing(text, start) {
    let depth = 0;
    for (let i = start; i < text.length; i++) {
      if (text[i] === '{') depth++;
      else if (text[i] === '}' && --depth === 0) return i;
    }
    return -1;
  }
  // [fin, variable, branches] de la forme qui commence en start, ou null.
  function pluralAt(text, start, name, position) {
    const branches = new Map();
    for (;;) {
      while (position < text.length && /\s/.test(text[position])) position++;
      if (position >= text.length) return null;
      if (text[position] === '}') return [position + 1, name, branches];
      SELECTOR.lastIndex = position;
      const sel = SELECTOR.exec(text);
      if (!sel) return null;
      const close = closing(text, SELECTOR.lastIndex - 1);
      if (close < 0) return null;
      branches.set(sel[1], text.slice(SELECTOR.lastIndex, close));
      position = close + 1;
    }
  }
  function numberSign(branch, number) {
    let out = '', depth = 0;
    for (const ch of branch) {
      if (ch === '{') depth++;
      else if (ch === '}') depth--;
      out += ch === '#' && depth === 0 ? number : ch;
    }
    return out;
  }
  function expand(text, language, vars) {
    text = String(text);
    if (!text.includes('plural')) return text;
    vars = vars || {};
    let out = '', position = 0;
    const re = new RegExp(START.source, 'g');
    let match;
    while ((match = re.exec(text))) {
      const found = pluralAt(text, match.index, match[1], re.lastIndex);
      if (!found) continue;
      const [end, name, branches] = found;
      out += text.slice(position, match.index);
      position = end;
      re.lastIndex = end;
      if (!Object.prototype.hasOwnProperty.call(vars, name)) { out += text.slice(match.index, end); continue; }
      const value = vars[name];
      const digits = typeof value !== 'boolean' && /^-?\d+$/.test(String(value).trim());
      const number = digits ? parseInt(String(value).trim(), 10) : null;
      const cat = number === null ? 'other' : category(language, number);
      let branch = number === null ? undefined : branches.get('=' + number);
      if (branch === undefined) branch = branches.has(cat) ? branches.get(cat)
        : branches.has('other') ? branches.get('other') : (branches.values().next().value || '');
      out += expand(numberSign(branch, String(value)), language, vars);
    }
    return out + text.slice(position);
  }
  return { category, expand };
});
