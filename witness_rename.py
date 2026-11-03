# -*- coding: utf-8 -*-
"""Changer le sigle d'un témoin (V0.9.4.0), sans Qt.

Le sigle P devient P2 : l'identifiant du témoin (``xml:id`` du
``<witness>``, cible de ``@wit`` et ``@edRef``) devient celui du nouveau
sigle (``witness_ids.witness_id_for_siglum``), partout où il est écrit.
:func:`plan_witness_rename` en fait le plan, sans rien écrire :

- **project.xml** : le témoin (``id``, ``siglum``, ``label`` quand il
  commence par le sigle), le pivot (``<witnesses base>``), les pivots des
  textes (``<part base>``), le texte du viewer web (``textWitness``), les
  paramètres des scénarios qui valent l'identifiant, les ``#P`` des
  requêtes XPath, les surfaces et les chemins de ses fichiers ;
- **les documents XML du projet** (l'édition, ses parties, les documents de
  ``<documents>``) : la déclaration du ``<witness>`` (``xml:id``, ``<idno
  type="siglum">``, nom commençant par le sigle), chaque pointeur ``#P`` ou
  ``fichier.xml#P`` vers un document du projet (``P`` seul dans ``@wit`` et
  ``@edRef``, que Varians lit aussi), les surfaces ``P-p0001`` et leurs
  zones, avec leurs pointeurs, et les chemins des ``<graphic>`` ;
- **les JSON d'alignement** : ``meta.witness`` et ``meta.base_witness``,
  ``pages[].tei_surface_id``, les chemins des images ;
- **les fichiers et dossiers nommés d'après le témoin** : ``alignments/P.json``,
  ``alignments/<texte>/P.json``, ``images/P/``, ``alto/P/``, le cache IIIF
  ``iiif/P.manifest.json`` et la copie locale ``iiif/local/P/``.

Les surfaces sont renommées parce que Varians tire de l'identifiant du
témoin celles qu'il ne garde pas dans project.xml (IIIF, dossier d'images) :
``P2-p0001`` est la surface que le témoin P2 cherchera.

Chaque changement est un remplacement à sa place exacte dans le texte du
fichier : le reste (commentaires, mise en forme, entités) ne change pas.
Un sigle cité dans le texte (une note, un commentaire) ou dans une
expression (``@wit='#P'`` d'une XSLT) n'est que signalé (``mentions``).

Refus (``problems``) : sigle vide ou inchangé, sigle ou identifiant d'un
autre témoin (sans tenir compte de la casse, qui ne distingue pas les
fichiers sous Windows et macOS), identifiant ou surface déjà employé dans un
document, fichier déjà présent sous le nouveau nom, document à changer mal
formé ou illisible. Un identifiant déjà employé ne gêne que dans l'édition
et ses parties (un seul document assemblé) ou dans un document que le
changement modifie.

:func:`apply_witness_rename` applique le plan d'un bloc : écritures
atomiques avec copie ``.bak``, puis renommages ; rien n'est fait si un
fichier a changé depuis le plan, et au moindre échec tout est remis dans
l'état d'avant. :func:`migrate_view_settings` reporte sur le nouvel
identifiant les réglages d'affichage du projet (ordre, hauteurs, fenêtres
détachées…)."""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from i18n import Message
from tei_facsimile import safe_id_component
from witness_ids import witness_id_for_siglum
from xml_tag_pairs import scan_xml_tags

# Ordre des rubriques du compte des changements.
CATEGORIES = ("declaration", "pointers", "surfaces", "paths", "settings")

_ATTRIBUTE_RE = re.compile(
    r"""(?<![\w:.-])([A-Za-z_][\w.-]*(?::[A-Za-z_][\w.-]*)?)\s*=\s*(["'])(.*?)\2""", re.S)
_SCHEME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")
# Caractères d'un nom XML après le premier (hors lettres et chiffres de \w).
_NAME_TAIL = r"[\w.\-·̀-ͯ‿⁀]"
# Ce qui peut suivre le sigle au début d'un nom affiché (« P · Paris »).
_LABEL_SEPARATORS = frozenset(" \t ·:,;–—-(/")
_INERT_RE = re.compile(r"<\?.*?(?:\?>|\Z)|<!DOCTYPE\b(?:[^\[>]|\[.*?\])*>?", re.S)
_XML_SUFFIXES = (".xml", ".tei", ".xsl", ".xslt", ".sch", ".rng", ".xsd", ".odd")


@dataclass(frozen=True)
class FileChange:
    """Nouveau texte d'un fichier ; ``counts`` : ``((rubrique, nombre), …)``."""
    path: Path
    original: str
    text: str
    counts: tuple = ()

    @property
    def count(self) -> int:
        return sum(n for _category, n in self.counts)


@dataclass(frozen=True)
class Move:
    """Fichier ou dossier renommé."""
    source: Path
    target: Path

    @property
    def case_only(self) -> bool:
        """Seule la casse change : deux étapes sous Windows et macOS."""
        return (self.source.parent == self.target.parent and self.source.name != self.target.name
                and self.source.name.casefold() == self.target.name.casefold())


@dataclass(frozen=True)
class Mention:
    """Sigle cité dans le texte, ou ``#P`` dans une expression : signalé."""
    path: Path
    line: int
    excerpt: str


@dataclass(frozen=True)
class RenamePlan:
    project_path: Path
    old_id: str
    old_siglum: str
    new_id: str
    new_siglum: str
    changes: tuple = ()
    moves: tuple = ()
    surfaces: dict = field(default_factory=dict)
    mentions: tuple = ()
    notes: tuple = ()
    problems: tuple = ()

    @property
    def ok(self) -> bool:
        return not self.problems

    @property
    def root(self) -> Path:
        return self.project_path.parent

    def display_path(self, path) -> str:
        return _display(Path(self.project_path).parent, path)


def _display(root, path) -> str:
    """Chemin montré : relatif au dossier du projet, barres obliques."""
    path = Path(path)
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def _key(path) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _local(name: str) -> str:
    return name.rsplit(":", 1)[-1]


def _prefix(name: str) -> str:
    return name.rsplit(":", 1)[0] + ":" if ":" in name else ""


def _escape(value: str, quote: str = '"') -> str:
    value = html.escape(value, quote=False)
    return value.replace('"', "&quot;") if quote == '"' else value.replace("'", "&apos;")


def _safe_filename(name: str) -> str:
    from project_management import _safe_filename as safe
    return safe(name)


def _line_starts(text):
    starts = [0]
    starts.extend(m.end() for m in re.finditer("\n", text))
    return starts


def _line(starts, position) -> int:
    import bisect
    return bisect.bisect_right(starts, position)


_TAGS_AFTER = re.compile(r"(?:<[^<>]*>)+(?=\w)")
_TAGS_BEFORE = re.compile(r"\w(?:<[^<>]*>)+\Z")


def _inside_word(text, start, end) -> bool:
    """Le sigle trouvé touche-t-il, à travers des balises, une autre partie
    du mot (« P<lb break="no"/>raue ») ?"""
    return bool(_TAGS_AFTER.match(text, end) or _TAGS_BEFORE.search(text, max(0, start - 200), start))


def relabel(value: str, old: str, new: str):
    """Nom affiché qui commence par le sigle ``old`` (« P · Paris », ou
    « P » seul), avec ``new`` à sa place ; None s'il ne commence pas par lui."""
    if not old or old == new:
        return None
    lead = len(value) - len(value.lstrip())
    rest = value[lead:]
    if not rest.startswith(old):
        return None
    after = rest[len(old):]
    if after.strip() and after[0] not in _LABEL_SEPARATORS:
        return None
    return value[:lead] + new + after


class _Edits:
    """Remplacements à faire dans un texte, à leurs positions d'origine."""

    def __init__(self, text: str):
        self.text = text
        self.items = []

    def add(self, start, end, value, category):
        if self.text[start:end] != value:
            self.items.append((start, end, value, category))

    def __bool__(self):
        return bool(self.items)

    def touches(self, start, end) -> bool:
        return any(s < end and start < e for s, e, _v, _c in self.items)

    def counts(self) -> tuple:
        found = {}
        for *_span, category in self.items:
            found[category] = found.get(category, 0) + 1
        return tuple((c, found[c]) for c in CATEGORIES if c in found)

    def apply(self) -> str:
        pieces, position = [], 0
        for start, end, value, _category in sorted(self.items, key=lambda item: (item[0], item[1])):
            if start < position:
                raise AssertionError(f"remplacements qui se recouvrent à {start}")
            pieces += [self.text[position:start], value]
            position = end
        pieces.append(self.text[position:])
        return "".join(pieces)


def _attributes(text, token):
    """``(nom, guillemet, valeur brute, début, fin)`` des attributs d'une balise."""
    for match in _ATTRIBUTE_RE.finditer(text, token.name_end, token.end):
        yield match.group(1), match.group(2), match.group(3), match.start(3), match.end(3)


def _parse_error(text):
    """None si le texte est bien formé, sinon ``(ligne, message)``."""
    from lxml import etree
    parser = etree.XMLParser(resolve_entities=False, no_network=True, recover=False, huge_tree=True)
    try:
        etree.fromstring(text.lstrip("﻿").encode("utf-8"), parser)
    except etree.XMLSyntaxError as error:
        return (error.lineno or 0, str(error))
    return None


def _collect_ids(text):
    from xml_references import collect_ids
    return collect_ids(text)


# --- Lecture lexicale d'un JSON ----------------------------------------------------------

_JSON_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[{}\[\]:,]|[^\s{}\[\]:,"]+', re.S)


def _json_strings(text):
    """``(chemin, début, fin, valeur)`` de chaque chaîne valeur du JSON ;
    chemin : clés et rangs depuis la racine (``("pages", 0, "image", "path")``)."""
    stack = []          # [type, clé ou rang, attend une clé]
    for match in _JSON_TOKEN.finditer(text):
        token = match.group(0)
        top = stack[-1] if stack else None
        if token == "{":
            stack.append(["object", None, True])
        elif token == "[":
            stack.append(["array", 0, False])
        elif token in "}]":
            if stack:
                stack.pop()
        elif token == ":":
            if top and top[0] == "object":
                top[2] = False
        elif token == ",":
            if top and top[0] == "object":
                top[2] = True
            elif top:
                top[1] += 1
        elif token.startswith('"'):
            value = json.loads(token)
            if top and top[0] == "object" and top[2]:
                top[1] = value
            elif top:
                yield tuple(frame[1] for frame in stack), match.start(), match.end(), value


# --- Plan --------------------------------------------------------------------------------

class _Planner:
    def __init__(self, project, witness, new_id, new_siglum):
        self.project = project
        self.witness = witness
        self.root = Path(project.root_dir).resolve()
        self.old_id = witness.id
        self.old_siglum = witness.display_siglum
        self.new_id = new_id
        self.new_siglum = new_siglum
        self.problems = []
        self.notes = []
        self.mentions = []
        self.moves = []
        self.surfaces = {}
        self.documents = []          # (chemin, texte)
        self.ids = {}                # clé de chemin -> collect_ids
        self.other_target = set()    # documents où P désigne autre chose qu'un témoin
        self.group = set()           # l'édition et ses parties
        self.changes = []

    # -- documents ------------------------------------------------------------------------

    def _document_paths(self):
        from xslt_scenarios import edition_parts
        paths = [Path(self.project.edition)]
        paths += edition_parts(self.project.edition)
        self.group = {_key(Path(path).resolve()) for path in paths}
        paths += [document.path for document in getattr(self.project, "documents", ())]
        seen, result = set(), []
        for path in paths:
            path = Path(path).resolve()
            if _key(path) in seen or not path.is_file():
                continue
            if path.suffix.lower() not in _XML_SUFFIXES and path != Path(self.project.edition).resolve():
                continue
            seen.add(_key(path))
            result.append(path)
        return result

    def _read(self, path):
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self.problems.append(Message("witness_rename.unreadable", file=_display(self.root, path),
                                         error=str(error)))
            return None

    def load_documents(self):
        for path in self._document_paths():
            text = self._read(path)
            if text is None:
                continue
            self.documents.append((path, text))
            ids = self.ids[_key(path)] = _collect_ids(text)
            targets = ids.get(self.old_id, ())
            elements = {target.element for target in targets}
            if targets and "witness" not in elements:
                self.other_target.add(_key(path))
                self.notes.append(Message("witness_rename.other_target", file=_display(self.root, path),
                                          id=self.old_id, element=sorted(elements)[0]))

    # -- surfaces -------------------------------------------------------------------------

    def _witness_jsons(self):
        """JSON propres au témoin : son alignement, ceux de ses textes à part."""
        found = []
        if self.witness.alignment is not None:
            found.append(Path(self.witness.alignment).resolve())
        alignments = self.root / "alignments"
        if alignments.is_dir():
            for folder in sorted(p for p in alignments.iterdir() if p.is_dir()):
                path = folder / f"{self.old_id}.json"
                if path.is_file():
                    found.append(path.resolve())
        return [path for path in found if path.is_file()]

    def plan_surfaces(self):
        old, new = safe_id_component(self.old_id), safe_id_component(self.new_id)
        if old == new:
            return
        for other in self.project.witnesses:
            if other.id != self.old_id and safe_id_component(other.id) in (old, new):
                self.problems.append(Message("witness_rename.shared_surfaces", witness=other.display_siglum,
                                             prefix=safe_id_component(other.id)))
                return
        pattern = re.compile(re.escape(old) + r"-p\d+$")
        owned = {image.surface_id for image in self.witness.image_files if image.surface_id}
        for ids in self.ids.values():
            for ident, targets in ids.items():
                if pattern.match(ident) and any(t.element == "surface" for t in targets):
                    owned.add(ident)
        for path in self._witness_jsons():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for page in (data.get("pages") or []) if isinstance(data, dict) else []:
                if isinstance(page, dict) and isinstance(page.get("tei_surface_id"), str):
                    owned.add(page["tei_surface_id"])
        zones = set()
        for ids in self.ids.values():
            for ident, targets in ids.items():
                if any(t.element == "zone" for t in targets) and any(ident.startswith(s + "-") for s in owned):
                    zones.add(ident)
        for ident in sorted(owned | zones):
            if ident.startswith(old + "-"):
                self.surfaces[ident] = new + ident[len(old):]

    # -- identifiants déjà employés -------------------------------------------------------

    def check_ids(self):
        """Un identifiant visé ne doit pas déjà exister dans l'édition et ses
        parties (un seul document assemblé), ni dans un document que le
        changement modifie (ses pointeurs viseraient l'autre élément). Ailleurs,
        un même identifiant ne gêne pas : il ne vaut que dans son document."""
        wanted = set(self.surfaces.values())
        if self.new_id != self.old_id:
            wanted.add(self.new_id)
        relevant = set(self.group) | {_key(change.path) for change in self.changes}
        for path, _text in self.documents:
            if _key(path) not in relevant:
                continue
            for ident in sorted(wanted):
                for target in self.ids[_key(path)].get(ident, ()):
                    self.problems.append(Message(
                        "witness_rename.id_used", id=ident, element=target.element,
                        file=_display(self.root, path), line=target.line))
                    return

    # -- fichiers renommés ----------------------------------------------------------------

    def _move(self, source, target, *, required=False):
        source, target = Path(source), Path(target)
        if _key(source) == _key(target) and source.name == target.name:
            return
        exists = source.exists()
        if target.exists():
            same = exists and os.path.samefile(source, target)
            if not same and (exists or required):
                self.problems.append(Message("witness_rename.target_exists", file=_display(self.root, target)))
                return
        if exists:
            self.moves.append(Move(source.resolve(), target.parent.resolve() / target.name))

    def plan_moves(self, alignment_attribute):
        from iiif_local import store_dir
        from iiif_manifest import cache_path
        old, new = self.old_id, self.new_id
        if old == new:
            return
        alignments = self.root / "alignments"
        if self.witness.alignment is not None:
            path = Path(self.witness.alignment).resolve()
            if path.parent == alignments.resolve() and path.suffix == ".json" and path.stem in (
                    old, _safe_filename(old)):
                # Avec @alignment, le nom que Varians donne en copiant le
                # fichier ; sans lui, le nom conventionnel que lit project.xml.
                name = _safe_filename(new) if alignment_attribute else new
                self._move(path, alignments / f"{name}.json", required=True)
        if alignments.is_dir():
            for folder in sorted(p for p in alignments.iterdir() if p.is_dir()):
                self._move(folder / f"{old}.json", folder / f"{new}.json", required=True)
        self._move(cache_path(self.root, old), cache_path(self.root, new))
        self._move(store_dir(self.root, old), store_dir(self.root, new))
        for folder in ("images", "alto"):
            self._move(self.root / folder / _safe_filename(old), self.root / folder / _safe_filename(new))

    def rebase(self, raw, base_dir):
        """Chemin ``raw`` (relatif à ``base_dir`` ou absolu) qui mène dans un
        fichier ou dossier renommé, écrit vers le nouveau nom ; sinon None."""
        value = raw.strip()
        if not value or (_SCHEME_RE.match(value) and not _DRIVE_RE.match(value)):
            return None
        absolute = os.path.isabs(value) or bool(_DRIVE_RE.match(value))
        path = os.path.normpath(value if absolute else os.path.join(base_dir, value))
        for move in self.moves:
            source = os.path.normpath(str(move.source))
            if os.path.normcase(path) == os.path.normcase(source):
                target = str(move.target)
            elif os.path.normcase(path).startswith(os.path.normcase(source) + os.sep):
                target = os.path.join(str(move.target), path[len(source) + 1:])
            else:
                continue
            if absolute:
                return target
            new = os.path.relpath(target, base_dir)
            return new if "\\" in value else new.replace(os.sep, "/")
        return None

    # -- pointeurs ------------------------------------------------------------------------

    def _pointer(self, token, attribute, path, line):
        """``(nouveau jeton, rubrique)`` ou None."""
        if "#" in token:
            if _SCHEME_RE.match(token) and not _DRIVE_RE.match(token):
                return None
            file, _sep, fragment = token.partition("#")
            if fragment in self.surfaces:
                return f"{file}#{self.surfaces[fragment]}", "surfaces"
            if fragment != self.old_id or self.old_id == self.new_id:
                return None
            target = _key(os.path.join(path.parent, file)) if file else _key(path)
            if target not in self.ids:
                self.notes.append(Message("witness_rename.outside_pointer", file=_display(self.root, path),
                                          line=line, token=token))
                return None
            if target in self.other_target:
                return None
            return f"{file}#{self.new_id}", "pointers"
        if attribute in ("wit", "edRef") and token == self.old_id and self.old_id != self.new_id:
            return self.new_id, "pointers"
        if attribute == "facs" and token in self.surfaces:
            return self.surfaces[token], "surfaces"
        return None

    def _expression_re(self):
        return re.compile("#" + re.escape(self.old_id) + "(?!" + _NAME_TAIL + ")")

    # -- documents XML --------------------------------------------------------------------

    def plan_document(self, path, text):
        edits = _Edits(text)
        starts = _line_starts(text)
        tokens = scan_xml_tags(text)
        expression = self._expression_re()
        witnesses = []
        for index, token in enumerate(tokens):
            if token.kind == "close":
                continue
            local = _local(token.name)
            for name, quote, raw, start, end in _attributes(text, token):
                value = html.unescape(raw)
                attribute = _local(name)
                if name == "xml:id":
                    ident = value.strip()
                    if local == "witness" and ident == self.old_id:
                        witnesses.append(index)
                        if self.new_id != self.old_id:
                            edits.add(start, end, _escape(self.new_id, quote), "declaration")
                    elif ident in self.surfaces and local in ("surface", "zone"):
                        edits.add(start, end, _escape(self.surfaces[ident], quote), "surfaces")
                    continue
                if local == "graphic" and attribute == "url":
                    new = self.rebase(value, path.parent)
                    if new is not None:
                        edits.add(start, end, _escape(new, quote), "paths")
                    continue
                for piece in re.finditer(r"\S+", raw):
                    token_text = html.unescape(piece.group(0))
                    found = self._pointer(token_text, attribute, path, _line(starts, start + piece.start()))
                    if found is not None:
                        edits.add(start + piece.start(), start + piece.end(), _escape(found[0], quote), found[1])
                    elif (self.old_id != self.new_id and expression.search(token_text)
                          and token_text.partition("#")[2] != self.old_id):
                        self.mentions.append(self._mention(path, text, starts, start + piece.start()))
        for index in witnesses:
            self._declaration(text, tokens, index, edits)
        self._text_mentions(path, text, starts, tokens, edits)
        if edits:
            error = _parse_error(text)
            if error is not None:
                self.problems.append(Message("witness_rename.malformed", file=_display(self.root, path),
                                             line=error[0]))
                return
            self.changes.append(FileChange(path, text, edits.apply(), edits.counts()))

    def _declaration(self, text, tokens, index, edits):
        """``<idno type="siglum">`` et nom du ``<witness>`` déclaré."""
        opening = tokens[index]
        prefix = _prefix(opening.name)
        idno_needed = self.new_siglum != self.new_id
        if opening.kind == "self":
            if idno_needed:
                slash = text.rindex("/", opening.start, opening.end)
                edits.add(slash, opening.end, f'><{prefix}idno type="siglum">{_escape(self.new_siglum)}'
                          f"</{prefix}idno></{opening.name}>", "declaration")
            return
        close = next((t for t in tokens[index + 1:] if t.kind == "close" and t.name == opening.name), None)
        if close is None:
            return
        inner = [t for t in tokens[index + 1:] if t.start < close.start]
        idno = next((t for t in inner if t.kind == "open" and _local(t.name) == "idno"
                     and any(_local(n) == "type" and html.unescape(v).strip() == "siglum"
                             for n, _q, v, _s, _e in _attributes(text, t))), None)
        label_start = opening.end
        if idno is not None:
            idno_close = next((t for t in inner if t.kind == "close" and t.name == idno.name
                               and t.start >= idno.end), None)
            if idno_close is not None:
                if html.unescape(text[idno.end:idno_close.start]).strip() != self.new_siglum:
                    edits.add(idno.end, idno_close.start, _escape(self.new_siglum), "declaration")
                if not text[opening.end:idno.start].strip():
                    label_start = idno_close.end
        elif idno_needed:
            edits.add(opening.end, opening.end, f'<{prefix}idno type="siglum">{_escape(self.new_siglum)}'
                      f"</{prefix}idno>", "declaration")
        label_end = text.find("<", label_start, close.end)
        label_end = close.start if label_end < 0 else label_end
        label = text[label_start:label_end]
        for old, new in ((self.old_siglum, self.new_siglum), (self.old_id, self.new_siglum)):
            new_label = relabel(html.unescape(label), old, new)
            if new_label is not None:
                lead = len(label) - len(label.lstrip())
                edits.add(label_start + lead, label_start + lead + len(old), _escape(new), "declaration")
                break

    def _mention_words(self):
        words = []
        if self.old_siglum != self.new_siglum:
            words.append(self.old_siglum)
        if self.old_id != self.new_id and self.old_id not in words:
            words.append(self.old_id)
        return words

    def _mention(self, path, text, starts, position):
        line = _line(starts, position)
        begin = starts[line - 1]
        end = text.find("\n", begin)
        excerpt = " ".join(text[begin:len(text) if end < 0 else end].split())
        if len(excerpt) > 120:
            excerpt = "…" + " ".join(text[max(begin, position - 50):position + 60].split()) + "…"
        return Mention(path, line, excerpt)

    def _text_mentions(self, path, text, starts, tokens, edits):
        words = self._mention_words()
        if not words:
            return
        spans = [(t.start, t.end) for t in tokens]
        spans += [(m.start(), m.end()) for m in _INERT_RE.finditer(text)]
        spans.sort()
        import bisect
        begins = [s for s, _e in spans]
        pattern = re.compile("|".join(r"(?<!\w)" + re.escape(word) + r"(?!\w)" for word in words))
        for match in pattern.finditer(text):
            i = bisect.bisect_right(begins, match.start()) - 1
            if i >= 0 and spans[i][0] <= match.start() < spans[i][1]:
                continue
            if edits.touches(match.start(), match.end()) or _inside_word(text, match.start(), match.end()):
                continue
            self.mentions.append(self._mention(path, text, starts, match.start()))

    # -- project.xml ----------------------------------------------------------------------

    def plan_project(self, text):
        edits = _Edits(text)
        tokens = scan_xml_tags(text)
        root = self.root
        inside = False
        query_start = None
        expression = self._expression_re()
        for token in tokens:
            local = _local(token.name)
            if token.kind == "close":
                if local == "witness":
                    inside = False
                elif local == "query" and query_start is not None and self.old_id != self.new_id:
                    content = text[query_start:token.start]
                    for match in expression.finditer(content):
                        edits.add(query_start + match.start(), query_start + match.end(),
                                  "#" + _escape(self.new_id), "settings")
                    query_start = None
                continue
            if local == "query":
                query_start = token.end if token.kind == "open" else None
                continue
            attributes = list(_attributes(text, token))
            values = {name: html.unescape(raw).strip() for name, _q, raw, _s, _e in attributes}
            ours = local == "witness" and values.get("id") == self.old_id
            if ours:
                inside = token.kind == "open"
                self._project_witness(text, token, attributes, edits)
                continue
            for name, quote, raw, start, end in attributes:
                value = html.unescape(raw)
                stripped = value.strip()
                if (local, name) in {("witnesses", "base"), ("part", "base"), ("webViewer", "textWitness")}:
                    if stripped == self.old_id != self.new_id:
                        edits.add(start, end, _escape(self.new_id, quote), "settings")
                elif (local, name) == ("param", "value"):
                    if stripped == self.old_id != self.new_id:
                        edits.add(start, end, _escape(self.new_id, quote), "settings")
                    elif self.old_id != self.new_id:
                        for match in expression.finditer(raw):
                            edits.add(start + match.start(), start + match.end(),
                                      "#" + _escape(self.new_id, quote), "settings")
                elif name in ("file", "path", "alignment") and local not in ("edition", "document"):
                    new = self.rebase(value, root)
                    if new is not None:
                        edits.add(start, end, _escape(new, quote), "paths")
                elif inside and (local, name) == ("image", "surface") and stripped in self.surfaces:
                    edits.add(start, end, _escape(self.surfaces[stripped], quote), "surfaces")
        return edits

    def _project_witness(self, text, token, attributes, edits):
        siglum = self.new_siglum if self.new_siglum != self.new_id else None
        seen = set()
        for name, quote, raw, start, end in attributes:
            seen.add(name)
            value = html.unescape(raw)
            if name == "id" and self.new_id != self.old_id:
                edits.add(start, end, _escape(self.new_id, quote), "declaration")
            elif name == "siglum":
                if siglum is None:
                    # Attribut retiré, avec les blancs qui le précèdent.
                    name_start = text.rindex(name, token.name_end, start)
                    blank = name_start
                    while blank > token.name_end and text[blank - 1].isspace():
                        blank -= 1
                    edits.add(blank, end + 1, "", "declaration")
                elif value.strip() != siglum:
                    edits.add(start, end, _escape(siglum, quote), "declaration")
            elif name == "label":
                for old in (self.old_siglum, self.old_id):
                    new_label = relabel(value, old, self.new_siglum)
                    if new_label is not None:
                        edits.add(start, end, _escape(new_label, quote), "declaration")
                        break
            elif name == "alignment":
                new = self.rebase(value, self.root)
                if new is not None:
                    edits.add(start, end, _escape(new, quote), "paths")
        if siglum is not None and "siglum" not in seen:
            id_end = next(end for name, _q, _r, _s, end in attributes if name == "id")
            edits.add(id_end + 1, id_end + 1, f' siglum="{_escape(siglum)}"', "declaration")

    # -- JSON -----------------------------------------------------------------------------

    def _json_paths(self):
        paths = {}
        alignments = self.root / "alignments"
        if alignments.is_dir():
            for path in sorted(alignments.rglob("*.json")):
                paths[_key(path)] = path.resolve()
        for witness in self.project.witnesses:
            if witness.alignment is not None and Path(witness.alignment).is_file():
                paths.setdefault(_key(witness.alignment), Path(witness.alignment).resolve())
        return list(paths.values())

    def plan_json(self, path, own):
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self.problems.append(Message("witness_rename.unreadable", file=_display(self.root, path),
                                         error=str(error)))
            return
        edits = _Edits(text)
        names = {self.old_id: self.new_id, self.old_siglum: self.new_siglum}
        for key, start, end, value in _json_strings(text):
            new, category = None, None
            if key in (("meta", "witness"),) and own and value in names:
                new, category = names[value], "declaration"
            elif key == ("meta", "base_witness") and value in names:
                new, category = names[value], "declaration"
            elif len(key) == 3 and key[0] == "pages" and key[2] == "tei_surface_id" and value in self.surfaces:
                new, category = self.surfaces[value], "surfaces"
            elif len(key) == 4 and key[0] == "pages" and key[2] == "image" and key[3] in ("path", "file"):
                new, category = self.rebase(value, self.root), "paths"
            if new is not None and new != value:
                edits.add(start, end, json.dumps(new, ensure_ascii="\\u" in text[start:end]), category)
        if not edits:
            return
        try:
            json.loads(edits.apply())
        except ValueError:                                  # pragma: no cover - garde-fou
            raise AssertionError(f"{path} : le changement de sigle le rendrait illisible")
        inside = True
        try:
            path.relative_to(self.root)
        except ValueError:
            inside = False
        if not inside:
            categories = {category for category, _n in edits.counts()}
            if categories - {"declaration"}:
                self.problems.append(Message("witness_rename.external_file", file=str(path)))
            else:
                self.notes.append(Message("witness_rename.external_meta", file=str(path)))
            return
        self.changes.append(FileChange(path, text, edits.apply(), edits.counts()))


def plan_witness_rename(project, witness_id: str, new_siglum: str) -> RenamePlan:
    """Plan du changement de sigle du témoin ``witness_id`` en ``new_siglum``
    (voir la docstring du module). Rien n'est écrit."""
    new_siglum = (new_siglum or "").strip()
    new_id = witness_id_for_siglum(new_siglum)
    witness = project.witness_by_id.get(witness_id)
    project_path = Path(project.path).resolve()
    if witness is None:
        return RenamePlan(project_path, witness_id, witness_id, new_id, new_siglum,
                          problems=(Message("witness_rename.unknown", witness=witness_id),))
    plan = RenamePlan(project_path, witness.id, witness.display_siglum, new_id, new_siglum)
    problem = None
    if not new_siglum:
        problem = Message("witness_rename.empty")
    elif new_id == witness.id and new_siglum == witness.display_siglum:
        problem = Message("witness_rename.same", siglum=new_siglum)
    else:
        for other in project.witnesses:
            if other.id == witness.id:
                continue
            if (other.id.casefold() == new_id.casefold() or other.display_siglum.casefold() == new_siglum.casefold()):
                problem = Message("witness_rename.taken", siglum=new_siglum, witness=other.display_siglum)
                break
    if problem is not None:
        return _replace(plan, problems=(problem,))

    planner = _Planner(project, witness, new_id, new_siglum)
    project_text = planner._read(project_path)
    if project_text is None:
        return _replace(plan, problems=tuple(planner.problems))
    planner.load_documents()
    planner.plan_surfaces()
    planner.plan_moves(_has_alignment_attribute(project_text, witness.id))
    if planner.problems:
        return _replace(plan, problems=tuple(planner.problems), notes=tuple(planner.notes))
    project_edits = planner.plan_project(project_text)
    if project_edits:
        error = _parse_error(project_text)
        if error is not None:
            planner.problems.append(Message("witness_rename.malformed", file=project_path.name, line=error[0]))
        else:
            planner.changes.append(FileChange(project_path, project_text, project_edits.apply(),
                                              project_edits.counts()))
    for path, text in planner.documents:
        planner.plan_document(path, text)
    planner.check_ids()
    if not planner.problems:
        for change in planner.changes:
            if change.path.suffix != ".json" and _parse_error(change.text) is not None:
                raise AssertionError(f"{change.path} : le changement de sigle le rendrait mal formé")
    own = {_key(path) for path in planner._witness_jsons()}
    for path in planner._json_paths():
        planner.plan_json(path, _key(path) in own)
    return _replace(plan, changes=tuple(planner.changes), moves=tuple(planner.moves),
                    surfaces=dict(planner.surfaces), mentions=tuple(planner.mentions),
                    notes=tuple(planner.notes), problems=tuple(planner.problems))


def _replace(plan, **values):
    from dataclasses import replace
    return replace(plan, **values)


def _has_alignment_attribute(project_text, witness_id) -> bool:
    for token in scan_xml_tags(project_text):
        if token.kind != "close" and _local(token.name) == "witness":
            values = {name: html.unescape(raw).strip() for name, _q, raw, _s, _e in _attributes(project_text, token)}
            if values.get("id") == witness_id:
                return bool(values.get("alignment"))
    return False


# --- Application : tout ou rien -------------------------------------------------------------

class RenameError(Exception):
    """Le changement n'a pas pu se faire ; ``message`` (i18n.Message) dit
    pourquoi, et si les fichiers ont été remis dans leur état d'avant."""

    def __init__(self, message):
        super().__init__(str(message))
        self.message = message


@dataclass(frozen=True)
class RenameResult:
    written: tuple = ()          # fichiers réécrits (à leur place d'avant les renommages)
    backups: tuple = ()          # leurs copies .bak
    moved: tuple = ()            # Move faits


def _rename(move: Move) -> None:
    """Renomme un fichier ou un dossier ; jamais par-dessus un autre. Un
    changement de casse seule passe par un nom provisoire (Windows, macOS)."""
    source, target = move.source, move.target
    if target.exists() and not (move.case_only and os.path.samefile(source, target)):
        raise FileExistsError(17, "Le fichier existe déjà", str(target))
    if not move.case_only:
        os.rename(source, target)
        return
    temporary = source.with_name(f".{source.name}.varians-rename")
    os.rename(source, temporary)
    try:
        os.rename(temporary, target)
    except OSError:
        os.rename(temporary, source)
        raise


def _rollback(written, moved):
    """Remet les fichiers dans leur état d'avant ; renvoie ceux qui n'ont pas
    pu l'être."""
    failed = []
    for move in reversed(moved):
        try:
            _rename(Move(move.target, move.source))
        except OSError:
            failed.append(move.target)
    for path, backup in reversed(written):
        try:
            os.replace(backup, path)
        except OSError:
            failed.append(path)
    return failed


def apply_witness_rename(plan: RenamePlan) -> RenameResult:
    """Applique le plan d'un bloc : chaque fichier réécrit (écriture
    atomique, copie ``.bak`` de l'ancien), puis les fichiers et dossiers
    renommés. Rien n'est fait si un fichier a changé depuis le plan ; au
    moindre échec, tout est remis dans l'état d'avant (``RenameError``)."""
    from save_io import atomic_write_text_with_backup
    if not plan.ok:
        raise ValueError("Plan refusé : " + "; ".join(plan.problems))
    for change in plan.changes:
        try:
            current = change.path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            current = None
        if current != change.original:
            raise RenameError(Message("witness_rename.changed", file=plan.display_path(change.path)))
    for move in plan.moves:
        if not move.source.exists():
            raise RenameError(Message("witness_rename.changed", file=plan.display_path(move.source)))
        if move.target.exists() and not (move.case_only and os.path.samefile(move.source, move.target)):
            raise RenameError(Message("witness_rename.target_exists", file=plan.display_path(move.target)))
    written, moved = [], []
    current = None
    try:
        for change in plan.changes:
            current = change.path
            written.append((change.path, atomic_write_text_with_backup(change.path, change.text)))
        for move in plan.moves:
            current = move.source
            _rename(move)
            moved.append(move)
    except Exception as error:
        failed = _rollback(written, moved)
        detail = getattr(error, "strerror", None) or str(error)
        if failed:
            raise RenameError(Message("witness_rename.rollback_failed", file=plan.display_path(current),
                                      error=detail, files=", ".join(plan.display_path(p) for p in failed))) from error
        raise RenameError(Message("witness_rename.failed", file=plan.display_path(current), error=detail)) from error
    return RenameResult(tuple(path for path, _backup in written), tuple(backup for _path, backup in written),
                        tuple(moved))


# --- Réglages d'affichage -----------------------------------------------------------------

_SETTING_LISTS = ("witnessOrder", "visibleWitnesses", "detachedWitnesses")
_SETTING_MAPS = ("witnessLeadsEdition", "witnessHeights", "horizontalSizes", "gridSizes")
_SETTING_PER_WITNESS = ("floatingGeometry", "floatingAlwaysOnTop")


def _decoded(raw, kind):
    """``(valeur, enregistrée en JSON)`` d'un réglage, ou ``(None, False)``."""
    if isinstance(raw, str):
        try:
            value = json.loads(raw) if raw else None
        except ValueError:
            return None, False
        return (value, True) if isinstance(value, kind) else (None, False)
    if isinstance(raw, kind) or (kind is list and isinstance(raw, tuple)):
        return (list(raw) if kind is list else dict(raw)), False
    return None, False


def migrate_view_settings(settings, prefix: str, old: str, new: str) -> None:
    """Reporte sur ``new`` les réglages d'affichage du témoin ``old`` sous
    ``prefix`` (``projectView/<empreinte du projet>/``) : ordre, témoins
    visibles et détachés, bouton au livre, hauteurs et largeurs, position et
    « toujours au premier plan » des fenêtres détachées. ``settings`` :
    QSettings, ou tout objet de mêmes méthodes (``value``, ``setValue``,
    ``remove``, ``contains``)."""
    if old == new:
        return
    for name in _SETTING_LISTS:
        key = prefix + name
        items, encoded = _decoded(settings.value(key, None), list)
        if items and old in items:
            items = [new if item == old else item for item in items]
            settings.setValue(key, json.dumps(items, ensure_ascii=False) if encoded else items)
    for name in _SETTING_MAPS:
        key = prefix + name
        values, encoded = _decoded(settings.value(key, None), dict)
        if values and old in values:
            values = {new if item == old else item: value for item, value in values.items()}
            settings.setValue(key, json.dumps(values, ensure_ascii=False) if encoded else values)
    for name in _SETTING_PER_WITNESS:
        before, after = f"{prefix}{name}/{old}", f"{prefix}{name}/{new}"
        if settings.contains(before):
            value = settings.value(before)
            settings.remove(before)
            settings.setValue(after, value)
