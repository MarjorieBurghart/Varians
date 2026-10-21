# -*- coding: utf-8 -*-
"""Liaison non destructive entre les pages d'un projet Varians et la TEI.

V0.8.2 conserve un marquage de page sûr et conserve le niveau de synchronisation *page* : ``<facsimile>`` décrit
les images et ``<pb facs>`` indique la page courante dans la transcription.
Ce module est volontairement indépendant de Qt et privilégie des modifications
textuelles ciblées afin de ne jamais resérialiser/reformater tout le document.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import html
import os
import re
import shutil
import xml.etree.ElementTree as ET

XML_NS = "http://www.w3.org/XML/1998/namespace"
TEI_NS = "http://www.tei-c.org/ns/1.0"

_XML_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9._-]*$")
_PB_RE = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?pb\b[^>]*?/?>", re.I | re.S)
_ATTR_RE_TEMPLATE = r"(?<![\w:.-]){name}\s*=\s*(['\"])(.*?)\1"
_XML_ID_ATTR_RE = re.compile(r"(?<![\w:.-])xml:id\s*=\s*(['\"])(.*?)\1", re.I | re.S)
_N_ATTR_RE = re.compile(r"(?<![\w:.-])n\s*=\s*(['\"])(.*?)\1", re.I | re.S)
_FACS_ATTR_RE = re.compile(r"(?<![\w:.-])facs\s*=\s*(['\"])(.*?)\1", re.I | re.S)
_SURFACE_OPEN_RE = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?surface\b[^>]*>", re.I | re.S)
_XML_ID_ANY_RE = re.compile(r"(?<![\w:.-])xml:id\s*=\s*(['\"])(.*?)\1", re.I | re.S)


def valid_xml_id(value: str) -> bool:
    return bool(_XML_ID_RE.match(str(value or "").strip()))


def safe_id_component(value: str) -> str:
    value = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip(".-")
    if not value:
        value = "W"
    if not re.match(r"[A-Za-z_]", value[0]):
        value = "W-" + value
    return value


def default_surface_id(witness_id: str, index: int) -> str:
    return f"{safe_id_component(witness_id)}-p{int(index):04d}"


def _attr(tag: str, name: str) -> str | None:
    rx = re.compile(_ATTR_RE_TEMPLATE.format(name=re.escape(name)), re.I | re.S)
    m = rx.search(tag or "")
    return html.unescape(m.group(2)) if m else None


def _pointer_tokens(value: str | None) -> list[str]:
    return [x[1:] if x.startswith("#") else x for x in re.split(r"\s+", str(value or "").strip()) if x]


def facsimile_ref_at_position(
    xml_text: str, position: int, witness_id: str | None = None,
    surface_ids=None, surface_labels=None,
) -> str | None:
    """Retourne la surface courante au point d'édition.

    Sans ``witness_id``, le comportement historique est conservé : le dernier
    ``pb/@facs`` précédent gagne. Avec un témoin, ``@edRef`` est prioritaire ;
    pour les anciens ``pb`` sans ``@edRef``, l'appartenance peut être déduite
    d'un ensemble de ``surface_ids`` connu par l'interface. Sans ``@facs``,
    un ``pb`` portant explicitement ``@edRef`` peut employer ``@n`` si son
    libellé correspond à une *seule* surface connue ; aucune inférence par
    rang, suffixe approximatif ou folio étranger. Le parse reste lexical et
    fonctionne donc pendant une édition XML momentanément invalide.
    """
    text = str(xml_text or "")
    pos = max(0, min(len(text), int(position)))
    wid = str(witness_id or "").lstrip("#").strip() or None
    known = {str(x) for x in (surface_ids or ()) if str(x)}
    # @n is allowed only as a strict, unique page-label fallback, and only
    # for a pb with an explicit witness. Never infer folios by page ordinal.
    label_to_surfaces = {}
    if wid and surface_labels:
        for surface, label in surface_labels.items():
            sid = str(surface or '').lstrip('#').strip()
            text_label = str(label or '').strip().casefold()
            if sid and text_label and (not known or sid in known):
                label_to_surfaces.setdefault(text_label, set()).add(sid)
    current = None
    for m in _PB_RE.finditer(text):
        if m.start() > pos:
            break
        tag = m.group(0)
        facs_refs = _pointer_tokens(_attr(tag, "facs"))
        if wid is None:
            if facs_refs:
                current = facs_refs[0]
            continue
        edrefs = _pointer_tokens(_attr(tag, "edRef"))
        if edrefs:
            if wid not in edrefs:
                continue
            if facs_refs:
                local = next((sid for sid in facs_refs if not known or sid in known), None)
                if local:
                    current = local
            else:
                label = str(_attr(tag, 'n') or '').strip().casefold()
                matches = label_to_surfaces.get(label, set())
                if len(matches) == 1:
                    current = next(iter(matches))
            continue
        if not facs_refs:
            continue
        # Compatibilité avec les <pb facs> créés avant V0.8.2 : ne les
        # attribuer à un témoin que si leur surface lui appartient sans ambiguïté.
        local = next((sid for sid in facs_refs if sid in known), None) if known else None
        if local:
            current = local
    return current


def _xml_escape_attr(value: str) -> str:
    return html.escape(str(value or ""), quote=True)


def _set_or_add_attr(tag: str, name: str, value: str) -> str:
    rx = re.compile(_ATTR_RE_TEMPLATE.format(name=re.escape(name)), re.I | re.S)
    escaped = _xml_escape_attr(value)
    m = rx.search(tag)
    if m:
        return tag[:m.start()] + f'{name}="{escaped}"' + tag[m.end():]
    close = "/>" if tag.rstrip().endswith("/>") else ">"
    cut = tag.rfind(close)
    if cut < 0:
        return tag
    return tag[:cut].rstrip() + f' {name}="{escaped}"' + tag[cut:]


def _markup_spans(xml_text: str):
    """Yield lexical XML markup spans as ``(start, end)``.

    ``end`` is exclusive. The scanner deliberately works on temporarily
    malformed editor text and respects quotes when looking for ``>``. It also
    recognises comments, CDATA and processing instructions so that the page
    marker can never be inserted *inside* markup.
    """
    text = str(xml_text or "")
    n = len(text)
    i = 0
    while i < n:
        start = text.find("<", i)
        if start < 0:
            return
        if text.startswith("<!--", start):
            stop = text.find("-->", start + 4)
            end = n if stop < 0 else stop + 3
            yield start, end
            i = max(end, start + 1)
            continue
        if text.startswith("<![CDATA[", start):
            stop = text.find("]]>", start + 9)
            end = n if stop < 0 else stop + 3
            yield start, end
            i = max(end, start + 1)
            continue
        if text.startswith("<?", start):
            stop = text.find("?>", start + 2)
            end = n if stop < 0 else stop + 2
            yield start, end
            i = max(end, start + 1)
            continue

        quote = None
        j = start + 1
        while j < n:
            ch = text[j]
            if quote:
                if ch == quote:
                    quote = None
            elif ch in ("'", '\"'):
                quote = ch
            elif ch == ">":
                j += 1
                break
            j += 1
        end = min(j, n)
        yield start, end
        i = max(end, start + 1)


def position_inside_xml_markup(xml_text: str, position: int) -> bool:
    """True only when the caret is strictly inside XML markup.

    A caret immediately before ``<`` or immediately after the closing delimiter
    is considered *between* nodes and is therefore a valid insertion point.
    """
    text = str(xml_text or "")
    pos = max(0, min(len(text), int(position)))
    return any(start < pos < end for start, end in _markup_spans(text))


def upsert_pb_at_position(
    xml_text: str, position: int, label: str, surface_id: str, witness_id: str | None = None
) -> tuple[str, int, str]:
    """Insert a page marker only at a safe text/between-tags position.

    V0.7.9.2 intentionally never edits existing markup. If the caret lies
    strictly inside any XML markup — including an existing ``<pb/>`` — the
    text is returned unchanged with mode ``"blocked"``. This conservative
    behaviour avoids accidental reassignment of page markers.
    """
    if not valid_xml_id(surface_id):
        raise ValueError(f"xml:id de surface invalide : {surface_id!r}")
    text = str(xml_text or "")
    pos = max(0, min(len(text), int(position)))
    if position_inside_xml_markup(text, pos):
        return text, pos, "blocked"
    wid = str(witness_id or "").lstrip("#").strip()
    if wid and not valid_xml_id(wid):
        raise ValueError(f"xml:id de témoin invalide : {wid!r}")
    edref = f' edRef="#{_xml_escape_attr(wid)}"' if wid else ""
    tag = f'<pb n="{_xml_escape_attr(label)}"{edref} facs="#{_xml_escape_attr(surface_id)}"/>'
    out = text[:pos] + tag + text[pos:]
    return out, pos + len(tag), "inserted"


@dataclass(frozen=True)
class FacsimilePage:
    witness_id: str
    surface_id: str
    label: str
    graphic_url: str


@dataclass
class FacsimileSyncReport:
    added: list[str] = field(default_factory=list)
    labels_updated: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)
    conflicts: list[str] = field(default_factory=list)
    changed: bool = False


def _graphic_url(path: Path, edition_path: Path) -> str:
    path = Path(path).expanduser().resolve()
    try:
        rel = os.path.relpath(path, edition_path.parent.resolve()).replace("\\", "/")
        return rel
    except (ValueError, OSError):
        try:
            return path.as_uri()
        except ValueError:
            return str(path).replace("\\", "/")


def project_facsimile_pages(witnesses, project_root: str | Path, edition_path: str | Path) -> list[FacsimilePage]:
    """Construit les surfaces souhaitées depuis les sources d'images du projet.

    Les images locales utilisent l'identifiant stable enregistré dans
    ``project.xml``. Les manifests IIIF utilisent un identifiant déterministe
    par position ; leur label vient du Canvas et leur URL de l'image/service.
    Les sources historiques ``auto`` ne sont jamais converties implicitement.
    """
    root = Path(project_root).resolve()
    edition = Path(edition_path).resolve()
    out: list[FacsimilePage] = []
    for witness in witnesses or []:
        wid = str(getattr(witness, "id", "") or "").strip()
        kind = str(getattr(witness, "image_source_type", "auto") or "auto").strip().lower()
        if kind == "files":
            for i, item in enumerate(getattr(witness, "image_files", ()) or (), 1):
                path = Path(getattr(item, "path", "")).expanduser()
                if not path.is_absolute():
                    path = root / path
                sid = str(getattr(item, "surface_id", "") or default_surface_id(wid, i)).strip()
                if not valid_xml_id(sid):
                    continue
                label = str(getattr(item, "label", "") or path.stem)
                out.append(FacsimilePage(wid, sid, label, _graphic_url(path, edition)))
        elif kind == "iiif":
            try:
                from iiif_manifest import cache_path, read_cache
                manifest = read_cache(cache_path(root, wid), getattr(witness, "image_source_value", None))
            except Exception:
                manifest = None
            if manifest:
                from iiif_page_selection import selected_manifest_pages, canvas_key
                selected = selected_manifest_pages(
                    manifest, getattr(witness, 'iiif_selected_canvases', ()),
                    getattr(witness, 'iiif_selection_mode', 'all'))
                # Legacy 'all' must not materialize hundreds of surfaces when
                # the witness uses a five-page Varians-Synchro JSON. Only
                # demonstrably linked canvases are editorial in that case.
                alignment = getattr(witness, 'alignment', None)
                if alignment is not None and getattr(witness, 'iiif_selection_mode', 'all') == 'all':
                    try:
                        import json
                        from iiif_resolution import resolve_pages
                        raw_sync = json.loads(Path(alignment).read_text(encoding='utf-8'))
                        raw_pages = raw_sync.get('pages') or []
                        if raw_pages:
                            matches = resolve_pages(raw_pages, manifest,
                                explicit_links=getattr(witness, 'iiif_page_links', ()))
                            linked = {match.key for match in matches.values() if match.key}
                            selected = [(i, page) for i, page in selected if canvas_key(page) in linked]
                    except (OSError, ValueError, TypeError) as exc:
                        # Fail closed: an unreadable JSON is not justification
                        # to add the entire manifest to the scholar's TEI.
                        selected = []
                for i, page in selected:
                    block = page.get("image") or {}
                    graphic = str(block.get("image") or block.get("service") or "").strip()
                    if not graphic:
                        continue
                    out.append(FacsimilePage(
                        wid, default_surface_id(wid, i + 1),
                        str(page.get("label") or block.get("label") or f"Page {i}"), graphic,
                    ))
    return out


def _surface_open_tags(xml_text: str):
    result = {}
    for m in _SURFACE_OPEN_RE.finditer(xml_text):
        sid = _attr(m.group(0), "xml:id")
        if sid:
            result[sid] = (m.start(), m.end(), m.group(0), _attr(m.group(0), "n"))
    return result


def _tei_prefix(xml_text: str) -> str:
    m = re.search(r"<([A-Za-z_][\w.-]*:)?TEI\b", xml_text, re.I)
    return (m.group(1) or "") if m else ""


def _indent_before(xml_text: str, position: int) -> str:
    start = xml_text.rfind("\n", 0, position) + 1
    m = re.match(r"[ \t]*", xml_text[start:position])
    return m.group(0) if m else ""


def sync_facsimile_text(xml_text: str, pages: list[FacsimilePage], previous_labels: dict[str, str] | None = None) -> tuple[str, FacsimileSyncReport]:
    """Fusionne les surfaces manquantes sans jamais supprimer de contenu TEI.

    Garde-fous :
    - aucune modification si le document n'est pas bien formé ;
    - aucune surface existante n'est remplacée ;
    - aucun ``graphic`` existant n'est modifié ;
    - ``@n`` n'est actualisé que si sa valeur est encore exactement l'ancienne
      valeur connue du projet ; une édition manuelle est donc préservée ;
    - les surfaces devenues orphelines ne sont jamais supprimées automatiquement.
    """
    report = FacsimileSyncReport()
    try:
        ET.fromstring(xml_text)
    except ET.ParseError as exc:
        report.conflicts.append(f"XML non bien formé : {exc}")
        return xml_text, report

    previous_labels = dict(previous_labels or {})
    text = xml_text
    all_ids = {html.unescape(m.group(2)) for m in _XML_ID_ANY_RE.finditer(text)}
    surfaces = _surface_open_tags(text)

    # Mise à jour prudente des seuls @n encore identiques à la valeur connue.
    replacements = []
    for page in pages:
        existing = surfaces.get(page.surface_id)
        if not existing:
            continue
        start, end, tag, current_n = existing
        old_n = previous_labels.get(page.surface_id)
        if old_n is not None and current_n == old_n and page.label != old_n:
            new_tag = _set_or_add_attr(tag, "n", page.label)
            replacements.append((start, end, new_tag, page.surface_id))
        else:
            report.preserved.append(page.surface_id)
    for start, end, new_tag, sid in reversed(replacements):
        text = text[:start] + new_tag + text[end:]
        report.labels_updated.append(sid)
        report.changed = True

    # Les <pb> générés par Varians portent le même @n que la surface. Si le
    # libellé change dans le projet, ne mettre à jour que les <pb> dont @n est
    # encore exactement l'ancienne valeur connue. Toute personnalisation
    # éditoriale est ainsi laissée intacte.
    label_changes = {
        p.surface_id: (previous_labels.get(p.surface_id), p.label)
        for p in pages
        if previous_labels.get(p.surface_id) is not None
        and previous_labels.get(p.surface_id) != p.label
    }
    pb_replacements = []
    for m in _PB_RE.finditer(text):
        tag = m.group(0)
        facs = _attr(tag, "facs") or ""
        refs = {x[1:] for x in re.split(r"\s+", facs.strip()) if x.startswith("#") and len(x) > 1}
        current_n = _attr(tag, "n")
        for sid, (old_n, new_n) in label_changes.items():
            if sid in refs and current_n == old_n:
                pb_replacements.append((m.start(), m.end(), _set_or_add_attr(tag, "n", new_n)))
                break
    for start, end, new_tag in reversed(pb_replacements):
        text = text[:start] + new_tag + text[end:]
        report.changed = True

    surfaces = _surface_open_tags(text)
    missing = []
    for page in pages:
        if page.surface_id in surfaces:
            continue
        if page.surface_id in all_ids:
            report.conflicts.append(
                f"{page.surface_id}: cet xml:id existe déjà sur un autre élément ; surface non ajoutée."
            )
            continue
        missing.append(page)
        all_ids.add(page.surface_id)
    if not missing:
        return text, report

    prefix = _tei_prefix(text)
    def surface_xml(page: FacsimilePage, indent: str) -> str:
        sid = _xml_escape_attr(page.surface_id)
        n = _xml_escape_attr(page.label)
        url = _xml_escape_attr(page.graphic_url)
        return (
            f'{indent}<{prefix}surface xml:id="{sid}" n="{n}">\n'
            f'{indent}  <{prefix}graphic url="{url}"/>\n'
            f'{indent}</{prefix}surface>'
        )

    # 1) facsimile existant normal : insérer juste avant sa fermeture. On
    # accepte qu'il utilise un préfixe différent de la racine (XML valide),
    # afin de ne surtout pas créer un second <facsimile> par erreur.
    fac_open_re = re.compile(r"<([A-Za-z_][\w.-]*:)?facsimile\b[^>]*>", re.I | re.S)
    fac_open = next((m for m in fac_open_re.finditer(text) if not m.group(0).rstrip().endswith("/>")), None)
    if fac_open:
        fac_prefix = fac_open.group(1) or ""
        close_re = re.compile(rf"</{re.escape(fac_prefix)}facsimile\s*>", re.I)
        close = close_re.search(text, fac_open.end())
    else:
        close = None
    if close:
        indent = _indent_before(text, close.start())
        child_indent = indent + "  "
        old_prefix = prefix
        prefix = fac_prefix
        block = "\n" + "\n".join(surface_xml(p, child_indent) for p in missing)
        prefix = old_prefix
        # Conserver la fermeture sur sa ligne si possible.
        block += "\n" + indent
        text = text[:close.start()] + block + text[close.start():]
    else:
        # 2) facsimile auto-fermant : l'ouvrir sans perdre ses attributs ni
        # son éventuel préfixe de namespace.
        self_re = re.compile(r"<([A-Za-z_][\w.-]*:)?facsimile\b([^>]*)/>", re.I | re.S)
        self_m = self_re.search(text)
        if self_m:
            fac_prefix = self_m.group(1) or ""
            indent = _indent_before(text, self_m.start())
            attrs = self_m.group(2).rstrip()
            child_indent = indent + "  "
            old_prefix = prefix
            prefix = fac_prefix
            block = (
                f'<{fac_prefix}facsimile{attrs}>\n'
                + "\n".join(surface_xml(p, child_indent) for p in missing)
                + f'\n{indent}</{fac_prefix}facsimile>'
            )
            prefix = old_prefix
            text = text[:self_m.start()] + block + text[self_m.end():]
        else:
            # 3) aucun facsimile : créer un bloc avant <text>, emplacement TEI naturel.
            text_re = re.compile(rf"<{re.escape(prefix)}text\b", re.I)
            tm = text_re.search(text)
            if not tm:
                report.conflicts.append("Aucun élément <text> trouvé ; <facsimile> non créé.")
                return xml_text, report
            indent = _indent_before(text, tm.start())
            child_indent = indent + "  "
            block = (
                f'{indent}<{prefix}facsimile>\n'
                + "\n".join(surface_xml(p, child_indent) for p in missing)
                + f'\n{indent}</{prefix}facsimile>\n'
            )
            text = text[:tm.start()] + block + text[tm.start():]

    report.added.extend(p.surface_id for p in missing)
    report.changed = True
    return text, report


def sync_facsimile_file(edition_path: str | Path, pages: list[FacsimilePage], previous_labels: dict[str, str] | None = None) -> FacsimileSyncReport:
    path = Path(edition_path).expanduser().resolve()
    source = path.read_text(encoding="utf-8")
    updated, report = sync_facsimile_text(source, pages, previous_labels)
    if report.changed and updated != source:
        backup = path.with_suffix(path.suffix + ".bak")
        shutil.copy2(path, backup)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(updated, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    return report


def previous_surface_labels(witnesses) -> dict[str, str]:
    out = {}
    for witness in witnesses or []:
        for item in getattr(witness, "image_files", ()) or ():
            sid = str(getattr(item, "surface_id", "") or "").strip()
            if sid:
                out[sid] = str(getattr(item, "label", "") or "")
    return out


def removable_generated_iiif_surfaces(xml_text: str, manifest, witness_id: str,
                                      selected_canvas_ids=(), other_texts=()) -> tuple[str, tuple[str, ...]]:
    """Preview-only, conservative removal of abandoned Varians-generated surfaces.

    REQUIREMENTS: exact generated (id,n,graphic url) triple for an unselected
    canvas, no other attributes or child elements, and no ``#id`` reference
    elsewhere in the TEI. Keep all changed, annotated or referenced surfaces.
    ``other_texts``: the other files of an edition assembled by XInclude
    (V0.9.0.0); a reference in one of them also keeps the surface.
    This function does not modify any file; callers MUST request confirmation.
    """
    from iiif_page_selection import canvas_key
    original = str(xml_text or '')
    ET.fromstring(original)  # never modify malformed editor text
    used = set(selected_canvas_ids or ())
    expected = {}
    for i, page in enumerate(manifest.pages, 1):
        if canvas_key(page) in used:
            continue
        image = page.get('image') or {}
        graphic_url = str(image.get('image') or image.get('service') or '').strip()
        if graphic_url:
            expected[default_surface_id(witness_id, i)] = (
                str(page.get('label') or image.get('label') or f'Page {i}'), graphic_url)
    if not expected:
        return original, ()

    # Only simple surface+graphic blocks generated by Varians. Unlike an XML
    # serializer, the lexical patch preserves all other TEI bytes and prefixes.
    surface = re.compile(
        r'(?P<indent>^[ \t]*)<(?P<prefix>(?:[A-Za-z_][\w.-]*:)?)surface\b(?P<attrs>[^>]*)>'
        r'(?P<body>.*?)</(?P=prefix)surface>[ \t]*(?:\r?\n)?', re.M | re.S)
    graphic = re.compile(r'^\s*<(?P<prefix>(?:[A-Za-z_][\w.-]*:)?)graphic\b(?P<attrs>[^>]*)/>\s*$', re.S)
    candidates = []
    for m in surface.finditer(original):
        attrs = m.group('attrs')
        sid = _attr(attrs, 'xml:id')
        if sid not in expected:
            continue
        # Exactly the two attributes generated by Varians; manual additions
        # (facs, sameAs, xml:lang, etc.) disqualify the element.
        if len(re.findall(r'(?<![\w:.-])[\w:.-]+\s*=\s*[\'\"][^\'\"]*[\'\"]', attrs)) != 2:
            continue
        gr = graphic.fullmatch(m.group('body'))
        if not gr or gr.group('prefix') != m.group('prefix'):
            continue
        if len(re.findall(r'(?<![\w:.-])[\w:.-]+\s*=\s*[\'\"][^\'\"]*[\'\"]', gr.group('attrs'))) != 1:
            continue
        if (_attr(attrs,'n'), _attr(gr.group('attrs'),'url')) != expected[sid]:
            continue
        outside = original[:m.start()] + original[m.end():]
        cited = re.compile(r'#' + re.escape(sid) + r'(?![\w.-])')
        if cited.search(outside) or any(cited.search(str(text or '')) for text in other_texts):
            continue
        candidates.append((m.start(), m.end(), sid))
    revised = original
    for start, end, _ in reversed(candidates):
        revised = revised[:start] + revised[end:]
    if candidates:
        ET.fromstring(revised)
    return revised, tuple(sid for _, _, sid in candidates)
