# -*- coding: utf-8 -*-
"""Navigation philologique non destructive d'une image à plusieurs folios.

Une surface TEI correspond à UNE image (canvas IIIF ou fichier local), mais
peut décrire plusieurs zones de folio. Les identifiants de zones restent les
cibles stables de pb/@facs, avec @edRef pour lever les homonymies entre témoins.
Aucune relation de ligne ALTO/JSON n'est inférée ici.
"""
from __future__ import annotations
import bisect
from dataclasses import dataclass
import html
import re
import xml.etree.ElementTree as ET

from xml_tag_pairs import element_tag_pattern, element_tags
from tei_facsimile import _ATTR_RE_TEMPLATE, _attr, _pointer_tokens, _PB_RE, valid_xml_id, _set_or_add_attr
from image_sources import effective_line_bbox, page_image_dimensions


@dataclass(frozen=True)
class Folio:
    ref: str               # xml:id de surface ou de zone
    surface: str           # xml:id de l'image physique
    label: str             # foliotation éditoriale, non unique globalement
    region: tuple[float, float, float, float] | None = None


def _local(tag):
    return str(tag).split('}')[-1].split(':')[-1]


# Les éléments <facsimile> du document, hors commentaires et sections CDATA
# (V0.9.3.2) : les deux premières branches les sautent.
_FACSIMILE_RE = re.compile(
    r'<!--.*?(?:-->|$)|<!\[CDATA\[.*?(?:\]\]>|$)'
    r'|<(?:[\w.-]+:)?facsimile\b[^>]*?(?:/>|>.*?</(?:[\w.-]+:)?facsimile\s*>)', re.S)


def facsimile_markup(xml_text: str) -> str:
    """Les éléments ``<facsimile>`` du document, tels qu'écrits (V0.9.3.2) :
    la partie qui décrit les surfaces et leurs zones. Taper dans le texte ne
    la change pas."""
    return ''.join(m.group() for m in _FACSIMILE_RE.finditer(str(xml_text or ''))
                   if not m.group().startswith('<!'))


def facsimile_surfaces(xml_text: str, markup: str | None = None) -> dict | None:
    """``{xml:id: <surface>}`` du document (V0.9.3.2), ou None si rien ne
    s'analyse.

    Le ``<facsimile>`` (``markup``) est analysé seul : un texte
    momentanément mal formé ailleurs, pendant la frappe d'une balise, ne
    fait pas perdre les zones. S'il ne s'analyse pas seul (préfixe déclaré
    plus haut), le document entier. Un ``<facsimile>`` mal formé donne None :
    les folios reviennent aux surfaces, sans zone, plutôt que de donner une
    fausse zone."""
    markup = facsimile_markup(xml_text) if markup is None else markup
    for source in ((f'<r>{markup}</r>',) if markup else ()) + (str(xml_text or ''),):
        try:
            root = ET.fromstring(source)
        except ET.ParseError:
            continue
        surfaces = {}
        for surface in root.iter():
            sid = surface.get('{http://www.w3.org/XML/1998/namespace}id')
            if _local(surface.tag) == 'surface' and sid and sid not in surfaces:
                surfaces[sid] = surface
        return surfaces
    return None


def folios_for_witness(xml_text: str, witness_id: str, surface_ids,
                       default_labels=None, surfaces=None) -> list[Folio]:
    """Parcours dans l'ordre physique des surfaces configurées pour CE témoin.

    Les surfaces et leurs zones viennent du ``<facsimile>`` (voir
    ``facsimile_surfaces`` ; ``surfaces`` : déjà lues, pour plusieurs
    témoins).
    """
    ids = [str(s) for s in surface_ids if s]
    labels = default_labels or {}
    if surfaces is None:
        surfaces = facsimile_surfaces(xml_text) or {}
    out = []
    for sid in ids:
        surface = surfaces.get(sid)
        label = (surface.get('n') if surface is not None else None) or labels.get(sid) or sid
        zones = []
        if surface is not None:
            # Only direct zones describe a folio here: nested layout zones are
            # not mistaken for pages. The coordinates are in source pixels.
            for zone in surface:
                if _local(zone.tag) != 'zone':
                    continue
                zid = zone.get('{http://www.w3.org/XML/1998/namespace}id')
                name = zone.get('n')
                if not zid or not name:
                    continue
                try:
                    x1, y1, x2, y2 = (float(zone.attrib[k]) for k in ('ulx','uly','lrx','lry'))
                    if not (0 <= x1 < x2 and 0 <= y1 < y2):
                        continue
                except (ValueError, KeyError, OverflowError):
                    continue
                zones.append(Folio(zid, sid, name, (x1, y1, x2-x1, y2-y1)))
        if zones:
            # A physical image has two logical folios; it remains available
            # separately as a full-page preview, not an extra physical image.
            out.append(Folio(sid, sid, label))
            out.extend(zones)
        else:
            out.append(Folio(sid, sid, label))
    return out


def page_folios(folios: list[Folio]) -> list[Folio]:
    """Pages d'un témoin, dans son ordre : les folios d'une surface divisée
    (ses zones), sinon la surface entière. C'est le parcours des flèches
    d'un panneau en mode page."""
    return [f for f in folios if f.region is not None or not any(
        x.region is not None and x.surface == f.surface for x in folios)]


@dataclass(frozen=True)
class Locus:
    """``<locus from to target>`` d'un ``<witness>`` : folios, dans ce
    témoin, du texte que vise ``@target`` (V0.9.1.3). ``targets`` : les
    identifiants visés, sans « # »."""
    witness: str
    start: str | None
    end: str | None
    targets: frozenset


def witness_loci(xml_text: str) -> dict:
    """``{témoin: (Locus, …)}`` des ``<locus @target>`` placés dans les
    ``<witness xml:id>`` d'un ``<listWit>`` ; {} si le XML est mal formé."""
    try:
        from lxml import etree
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
        root = etree.fromstring(str(xml_text or "").encode("utf-8"), parser)
    except Exception:
        return {}
    namespaces = {"tei": "http://www.tei-c.org/ns/1.0"}
    found = {}
    for witness in root.xpath("//tei:listWit//tei:witness[@xml:id]", namespaces=namespaces):
        wid = witness.get("{http://www.w3.org/XML/1998/namespace}id")
        loci = tuple(Locus(wid, locus.get("from"), locus.get("to"), frozenset(_pointer_tokens(locus.get("target"))))
                     for locus in witness.xpath(".//tei:locus[@target]", namespaces=namespaces))
        if loci:
            found[wid] = loci
    return found


def text_start_folio(witness_id: str, folios: list[Folio], loci=(), text_ids=(), first: Folio | None = None):
    """Page de départ d'un texte dans un témoin (V0.9.1.3), avant son
    premier ``<pb>`` dans ce texte : le ``@from`` d'un ``<locus>`` du témoin
    qui vise un des ``text_ids`` (rapproché des folios comme ``pb/@n``),
    sinon la page qui précède ``first`` (le folio de ce premier ``<pb>``)
    dans l'ordre des pages du témoin ; None sans l'un ni l'autre."""
    lookup = folio_lookup(folios)
    text_ids = set(text_ids)
    for locus in loci:
        if locus.start and locus.targets & text_ids:
            folio = pb_folio(None, f"#{witness_id}", locus.start, witness_id, lookup)
            if folio is not None:
                return folio
    if first is None:
        return None
    pages = page_folios(folios)
    index = next((i for i, f in enumerate(pages) if f.ref == first.ref), None)
    if index is None:
        index = next((i for i, f in enumerate(pages) if f.surface == first.surface), None)
    if index is None:
        return first
    return pages[max(0, index - 1)]


def folio_lookup(folios: list[Folio]):
    """Tables de ``pb_folio`` pour les folios d'un témoin."""
    id_map = {f.ref: f for f in folios}
    by_name = {}
    for f in folios:
        by_name.setdefault(f.label.strip().casefold(), []).append(f)
    return id_map, by_name


def pb_folio(facs, ed_ref, n, witness_id: str, lookup) -> Folio | None:
    """Folio que désigne, pour le témoin, un pb de valeurs @facs, @edRef et
    @n ; None s'il ne le concerne pas ou reste ambigu.

    Si pb/@facs désigne la surface entière et pb/@n un de ses folios,
    choisir sa zone.
    """
    return _folio_of_pb(_pointer_tokens(facs), _pointer_tokens(ed_ref), (n or '').strip().casefold(),
                        witness_id, lookup)


def _folio_of_pb(refs, edrefs, label, witness_id: str, lookup) -> Folio | None:
    """``pb_folio`` sur les valeurs déjà découpées : pointeurs de @facs et
    de @edRef, @n normalisé."""
    wid = str(witness_id).lstrip('#')
    id_map, by_name = lookup
    if edrefs and wid not in edrefs:
        return None
    if not edrefs and not any(ref in id_map for ref in refs):
        return None
    direct = next((id_map[r] for r in refs if r in id_map), None)
    if direct:
        # If @facs identifies the physical surface, @n may identify one
        # of its subdivisions, but ONLY within this very surface.
        if direct.region is None and label:
            children = [f for f in by_name.get(label, []) if f.surface == direct.surface and f.region]
            if len(children) == 1:
                direct = children[0]
        return direct
    if edrefs and not refs and label:
        matches = by_name.get(label, [])
        if len(matches) == 1:
            return matches[0]
    return None


def folio_at_position(xml_text: str, position: int, witness_id: str,
                      folios: list[Folio]) -> Folio | None:
    """Résout le dernier pb correspondant dans la TEI, sans index global @n.

    Si pb/@facs désigne la surface entière et pb/@n un de ses folios,
    choisir sa zone. Les balises placées dans les commentaires/CDATA et les
    pb de l'en-tête facsimilé ne doivent pas provoquer de navigation.
    """
    found = last_folio_mark(xml_text, position, witness_id, folios)
    return found[0] if found else None


def last_folio_mark(xml_text: str, position: int, witness_id: str,
                    folios: list[Folio]) -> tuple[Folio, int] | None:
    """Comme ``folio_at_position``, avec la fin du pb trouvé :
    ``(folio, fin)``, ou None."""
    marks = folio_marks(xml_text, witness_id, folios, stop=position)
    return marks[-1] if marks else None


class _TextMemo:
    """Valeurs calculées pour les derniers textes lus (V0.9.3.2) : quelques
    textes, car la synchronisation alterne entre une partie affichée et
    l'édition."""

    def __init__(self, size=4):
        self.size, self.entries = size, []

    def get(self, text):
        for cached, value in self.entries:
            if cached is text or cached == text:
                return value
        return None

    def put(self, text, value):
        self.entries = [(text, value)] + [e for e in self.entries if e[0] is not text][:self.size - 1]
        return value


# Pb de chaque témoin, par texte puis par (témoin, folios).
_marks_memo = _TextMemo()


def folio_marks(xml_text: str, witness_id: str, folios: list[Folio],
                stop: int | None = None) -> list[tuple[Folio, int]]:
    """``(folio, fin)`` de chaque pb du témoin dans ``xml_text``, dans
    l'ordre ; ceux qui finissent après ``stop`` sont ignorés.

    Les pb d'un témoin sont lus une fois par texte (V0.9.3.2) : déplacer le
    curseur sans modifier le texte ne relit pas le document."""
    text = str(xml_text or '')
    entries = _marks_memo.get(text)
    if entries is None:
        entries = _marks_memo.put(text, {})
    key = (str(witness_id), tuple(folios))
    marks = entries.get(key)
    if marks is None:
        marks = entries[key] = _scan_folio_marks(text, witness_id, folios)
    if stop is None:
        return list(marks)
    stop = max(0, min(int(stop), len(text)))
    return [mark for mark in marks if mark[1] <= stop]


def _scan_folio_marks(xml_text: str, witness_id: str, folios: list[Folio],
                      stop: int | None = None) -> list[tuple[Folio, int]]:
    """Pb d'un témoin pour ``folio_marks``, d'après les pb du texte."""
    lookup = folio_lookup(folios)
    text = str(xml_text or '')
    stop = len(text) if stop is None else max(0, min(int(stop), len(text)))
    marks = []
    for end, refs, edrefs, label in _pb_tags(text):
        if end > stop:
            break
        folio = _folio_of_pb(refs, edrefs, label, witness_id, lookup)
        if folio is not None:
            marks.append((folio, end))
    return marks


# Balises <pb> hors commentaires, CDATA, instructions et DOCTYPE : un exemple
# textuel n'est pas un vrai pb.
_PB_TAGS = element_tag_pattern("pb")
# Pb des derniers textes lus, partagés par tous les témoins (V0.9.3.2).
_pb_memo = _TextMemo()
# Les expressions de ``_attr`` pour les attributs d'un pb, compilées une fois.
_PB_ATTR_RES = {name: re.compile(_ATTR_RE_TEMPLATE.format(name=re.escape(name)), re.I | re.S)
                for name in ('facs', 'edRef', 'n')}


def _pb_attr(tag: str, name: str) -> str | None:
    """``_attr(tag, name)`` pour @facs, @edRef et @n."""
    m = _PB_ATTR_RES[name].search(tag)
    return html.unescape(m.group(2)) if m else None


def _pb_tags(text: str) -> tuple:
    """``(fin, pointeurs de @facs, de @edRef, @n normalisé)`` de chaque pb du
    texte, dans l'ordre, hors commentaires, CDATA et instructions ; lus une
    fois par texte."""
    tags = _pb_memo.get(text)
    if tags is not None:
        return tags
    found = []
    # Hors commentaires, CDATA, instructions et DOCTYPE, lus dans l'ordre
    # (red team 2, B6) ; guillemets des attributs respectés.
    for m in element_tags(_PB_TAGS, text):
        if m.group("close"):
            continue
        tag = m.group()
        found.append((m.end(), tuple(_pointer_tokens(_pb_attr(tag, 'facs'))),
                      tuple(_pointer_tokens(_pb_attr(tag, 'edRef'))), (_pb_attr(tag, 'n') or '').strip().casefold()))
    return _pb_memo.put(text, tuple(found))


def split_surface_into_folios(xml_text: str, surface_id: str, left: str, right: str,
                              width: int, height: int, split_percent: int = 50, *, split_pixel: int | None = None):
    """Ajoute exactement deux zones de folio dans une surface existante.

    N'écrit aucun autre élément TEI, ne réécrit pas le XML via ElementTree,
    ne remplace jamais des zones existantes et refuse les collisions de xml:id.
    """
    if (split_pixel is None and not (1 <= int(split_percent) <= 99)) or width <= 0 or height <= 0:
        raise ValueError('Dimensions ou position de séparation invalides.')
    if not left.strip() or not right.strip() or left.strip() == right.strip():
        raise ValueError('Les parties gauche et droite doivent avoir des libellés différents et non vides.')
    if not valid_xml_id(surface_id):
        raise ValueError('Identifiant de surface invalide.')
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f'XML non bien formé : {exc}') from exc
    sid_key = '{http://www.w3.org/XML/1998/namespace}id'
    surfaces = [e for e in root.iter() if _local(e.tag)=='surface' and e.get(sid_key)==surface_id]
    if len(surfaces) != 1:
        raise ValueError('La surface doit exister une seule fois dans le fac-similé TEI.')
    if any(_local(e.tag)=='zone' for e in surfaces[0].iter() if e is not surfaces[0]):
        raise ValueError('Cette surface contient déjà des zones : aucune modification automatique.')
    left_id, right_id = f'{surface_id}-left', f'{surface_id}-right'
    ids = [e.get(sid_key) for e in root.iter() if e.get(sid_key)]
    if any(ids.count(v)>1 for v in (surface_id,)) or left_id in ids or right_id in ids:
        raise ValueError('Conflit xml:id : la création automatique est annulée.')
    # Restrict to the actual opening surface tag, then find its matching
    # closing tag; fail closed for nested surface constructs.
    rx = re.compile(r'<(?P<prefix>[A-Za-z_][\w.-]*:)?surface\b[^>]*>', re.I|re.S)
    matches = [m for m in rx.finditer(xml_text) if _attr(m.group(), 'xml:id') == surface_id]
    if len(matches) != 1:
        raise ValueError('Ouverture de surface non identifiable dans le texte source.')
    m = matches[0]
    if m.group().rstrip().endswith('/>'):
        raise ValueError('Une surface autofermante ne peut pas recevoir ces zones.')
    prefix = m.group('prefix') or ''
    close_rx = re.compile(rf'</{re.escape(prefix)}surface\s*>', re.I)
    end = close_rx.search(xml_text, m.end())
    if end is None or rx.search(xml_text, m.end(), end.start()):
        raise ValueError('Surface imbriquée ou fermeture introuvable : modification annulée.')
    split_x = int(split_pixel) if split_pixel is not None else round(width * int(split_percent) / 100)
    if split_x <= 0 or split_x >= width:
        raise ValueError('Séparation hors de l’image.')
    line_start = xml_text.rfind('\n', 0, end.start()) + 1
    indent = re.match(r'[ \t]*', xml_text[line_start:end.start()]).group(0)
    child = indent + '  '
    z1 = f'{child}<{prefix}zone xml:id="{left_id}" n="{html.escape(left.strip(),quote=True)}" ulx="0" uly="0" lrx="{split_x}" lry="{height}"/>'
    z2 = f'{child}<{prefix}zone xml:id="{right_id}" n="{html.escape(right.strip(),quote=True)}" ulx="{split_x}" uly="0" lrx="{width}" lry="{height}"/>'
    block = z1 + '\n' + z2 + '\n'
    # Insert at start of closing tag's line (not after its indentation).
    if xml_text[line_start:end.start()].strip() == '':
        updated = xml_text[:line_start] + block + xml_text[line_start:]
    else:
        updated = xml_text[:end.start()] + '\n' + block + indent + xml_text[end.start():]
    ET.fromstring(updated)
    return updated, (left_id, right_id)


def scene_rect_for_folio(region, image_reference_crop, pix_width, pix_height, y_offset=0):
    """Source-pixel zone -> displayed Qt scene, even for small IIIF derivatives.

    The reference crop and region share a source coordinate system; do not
    apply the displayed-pixel resolution twice or enlarge the scene footprint.
    """
    x,y,w,h = map(float, region)
    rc=image_reference_crop
    sx=float(pix_width)/max(1.0,float(rc['w']))
    sy=float(pix_height)/max(1.0,float(rc['h']))
    return ((x-float(rc['x']))*sx, float(y_offset)+(y-float(rc['y']))*sy,
            w*sx,h*sy)


def markable_part_for_line(item, folios, project_root=None):
    """Determine the unique double-page part containing a physical OCR line.

    Only the current physical line is examined, not adjacent displayed lines.
    Geometry and TEI zone regions both use full-image pixel coordinates.
    No identification is inferred from folio numbers, page order or OCR text.
    Return None for nonexistent/ambiguous geometry (including a split-crossing
    line or an item representing an entire page).
    """
    if not item or not isinstance(item, dict):
        return None
    page, line = item.get('p') or {}, item.get('l') or {}
    if line.get('_page_mode') or line.get('_image_only'):
        return None
    sid = str(page.get('tei_surface_id') or '')
    parts = [f for f in folios if f.surface == sid and f.region is not None]
    if len(parts) != 2 or not effective_line_bbox(line):
        return None
    rect = effective_line_bbox(line)
    try:
        aw = float(page.get('alto_width') or 0)
        iw, ih = page_image_dimensions(page, project_root)
        if aw <= 0 or iw <= 0 or ih <= 0:
            return None
        x = float(rect['hpos']) * iw / aw
        width = float(rect['width']) * iw / aw
        if width <= 0:
            return None
    except (ValueError, TypeError, OverflowError):
        return None
    scores = []
    for part in parts:
        zx, _, zw, _ = part.region
        overlap = max(0.0, min(x + width, zx + zw) - max(x, zx))
        scores.append(overlap / width)
    best = max(range(len(parts)), key=lambda i: scores[i])
    if scores[best] < .85 or scores[1-best] > .15:
        return None
    return parts[best]


def inspect_surface_part_split(xml_text: str, surface_id: str, width: int, height: int):
    """Return the editable existing left/right split, or None when none exists.

    Only our two self-closing zones are editable in place. Existing complex TEI
    facsimile zoning is intentionally not guessed at or overwritten.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        raise ValueError(f'XML non bien formé : {exc}') from exc
    sid_key = '{http://www.w3.org/XML/1998/namespace}id'
    surfaces = [e for e in root.iter() if _local(e.tag) == 'surface' and e.get(sid_key) == surface_id]
    if len(surfaces) != 1:
        raise ValueError('Surface absente ou non unique.')
    zones = [e for e in surfaces[0].iter() if e is not surfaces[0] and _local(e.tag) == 'zone']
    if not zones:
        return None
    direct = [e for e in surfaces[0] if _local(e.tag) == 'zone']
    if len(zones) != 2 or len(direct) != 2:
        raise ValueError('Cette surface possède d’autres zones non modifiables automatiquement.')
    lookup = {e.get(sid_key): e for e in direct}
    lid, rid = surface_id + '-left', surface_id + '-right'
    if set(lookup) != {lid, rid}:
        raise ValueError('Ces zones n’ont pas les identifiants automatiques attendus.')
    left, right = lookup[lid], lookup[rid]
    try:
        x0 = float(left.get('ulx')); lx = float(left.get('lrx'))
        rx = float(right.get('ulx')); x1 = float(right.get('lrx'))
        top1 = float(left.get('uly')); top2 = float(right.get('uly'))
        bottom1 = float(left.get('lry')); bottom2 = float(right.get('lry'))
    except (ValueError, TypeError, OverflowError):
        raise ValueError('Les limites géométriques des deux zones sont invalides.')
    if (abs(x0) > 0.5 or abs(lx-rx) > 0.5 or abs(x1-width) > 0.5 or
        abs(top1) > 0.5 or abs(top2) > 0.5 or
        abs(bottom1-height) > 0.5 or abs(bottom2-height) > 0.5 or
        not (0 < lx < width) or not left.get('n') or not right.get('n')):
        raise ValueError('Les deux zones ne forment pas une séparation verticale simple.')
    return {'left':left.get('n'), 'right':right.get('n'),
            'split_pixel': round(lx), 'left_id':lid, 'right_id':rid}


def configure_surface_parts(xml_text: str, surface_id: str, left: str, right: str,
                            width: int, height: int, *, split_pixel: int):
    """Create a split or non-destructively adjust its two existing TEI zones.

    Changing a label referenced by an existing pb could invalidate @n: refuse
    that case rather than silently rewriting or invalidating critical TEI.
    """
    info = inspect_surface_part_split(xml_text, surface_id, width, height)
    if info is None:
        return split_surface_into_folios(
            xml_text, surface_id, left, right, width, height,
            split_pixel=split_pixel)
    if not left.strip() or not right.strip() or left.strip() == right.strip():
        raise ValueError('Les deux parties doivent avoir des libellés distincts et non vides.')
    if not (0 < int(split_pixel) < width):
        raise ValueError('Séparation en dehors de l’image.')
    # Check existing pb references; a label change is not safe without a
    # coordinated editorial decision about those references.
    if left.strip() != info['left'] or right.strip() != info['right']:
        for m in _PB_RE.finditer(xml_text):
            refs = _pointer_tokens(_attr(m.group(), 'facs'))
            if (info['left_id'] in refs and left.strip() != info['left'] or
                info['right_id'] in refs and right.strip() != info['right']):
                raise ValueError('Ce libellé est utilisé par un <pb/> existant. '
                                 'Modifiez le libellé et le <pb/> manuellement.')
    rx_surface = re.compile(r'<(?P<prefix>[A-Za-z_][\w.-]*:)?surface\b[^>]*>', re.I|re.S)
    starts = [m for m in rx_surface.finditer(xml_text)
              if _attr(m.group(), 'xml:id') == surface_id]
    if len(starts) != 1:
        raise ValueError('Balise de surface non identifiable dans la source.')
    opening = starts[0]
    prefix = opening.group('prefix') or ''
    closing = re.search(rf'</{re.escape(prefix)}surface\s*>', xml_text[opening.end():], re.I)
    if closing is None:
        raise ValueError('Fermeture de surface introuvable.')
    end = opening.end() + closing.start()
    inner = xml_text[opening.end():end]
    rx_zone = re.compile(r'<(?:[A-Za-z_][\w.-]*:)?zone\b[^>]*?/>', re.I|re.S)
    replacements = {}
    for match in rx_zone.finditer(inner):
        zid = _attr(match.group(), 'xml:id')
        if zid in (info['left_id'], info['right_id']):
            if zid in replacements:
                raise ValueError('Identifiant de zone répété dans la source.')
            if zid == info['left_id']:
                vals = dict(n=left.strip(),ulx='0',uly='0',lrx=str(int(split_pixel)),lry=str(height))
            else:
                vals = dict(n=right.strip(),ulx=str(int(split_pixel)),uly='0',lrx=str(width),lry=str(height))
            tag = match.group()
            for name,value in vals.items():
                tag = _set_or_add_attr(tag,name,value)
            replacements[zid] = (match.start(),match.end(),tag)
    if set(replacements) != {info['left_id'],info['right_id']}:
        raise ValueError('Balises de zone non identifiables ; modification annulée.')
    for i,j,tag in sorted(replacements.values(), reverse=True):
        inner = inner[:i]+tag+inner[j:]
    updated = xml_text[:opening.end()] + inner + xml_text[end:]
    ET.fromstring(updated)
    return updated, (info['left_id'],info['right_id'])
