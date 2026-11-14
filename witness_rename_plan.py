# -*- coding: utf-8 -*-
"""Plan d'un changement de sigle de témoin (V0.9.4.0 ; module à part depuis
la V0.9.4.7, extrait de witness_rename), sans Qt.

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

Le journal d'un changement interrompu (``journal_path``, ``read_journal``)
est lu ici : un nouveau plan est refusé tant qu'il existe. Son écriture,
l'application du plan et la reprise sont dans ``witness_rename``.
"""
from __future__ import annotations

import html
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from i18n import Message
from save_io import declared_encoding, is_utf8
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
        """Nombre total de remplacements du fichier, toutes rubriques confondues."""
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
    """Plan d'un changement de sigle, fait par :func:`plan_witness_rename` sans
    rien écrire : ``changes`` (``FileChange``), ``moves`` (``Move``), ``surfaces``
    (ancien identifiant de surface ou de zone → nouveau), ``mentions``
    (citations du sigle à vérifier), ``notes`` (ce qui ne change pas, et
    pourquoi) et ``problems`` (refus : le plan ne s'applique pas). Les notes
    et les refus sont des ``i18n.Message``."""
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
        """Vrai si le plan n'a aucun refus : « Appliquer » est alors possible."""
        return not self.problems

    @property
    def root(self) -> Path:
        """Dossier du projet (celui de project.xml)."""
        return self.project_path.parent

    def display_path(self, path) -> str:
        """Chemin ``path`` tel que l'aperçu le montre : relatif au dossier du
        projet, barres obliques ; un chemin hors du projet reste entier."""
        return _display(Path(self.project_path).parent, path)


def _display(root, path) -> str:
    """Chemin montré : relatif au dossier du projet, barres obliques."""
    path = Path(path)
    try:
        return path.resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return str(path)


def _key(path) -> str:
    """Identité d'un fichier : son inode s'il existe (un même fichier atteint
    par deux chemins, liens ou casse sous macOS, n'est changé qu'une fois)."""
    try:
        status = os.stat(path)
        if status.st_ino:
            return f"{status.st_dev}:{status.st_ino}"
    except (OSError, ValueError):
        pass
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _entry(path):
    """Identité de l'entrée de répertoire elle-même (un lien n'est pas suivi)."""
    try:
        status = os.lstat(path)
    except (OSError, ValueError):
        return None
    if not status.st_ino:
        return ("path", os.path.normcase(os.path.join(os.path.realpath(os.path.dirname(path)),
                                                      os.path.basename(path))))
    return (status.st_dev, status.st_ino)


def _within(root, path) -> bool:
    """``path`` (suivi de ses liens) est-il dans le dossier ``root`` ?"""
    root = os.path.realpath(root)
    try:
        return os.path.commonpath([root, os.path.realpath(path)]) == root
    except ValueError:
        return False


def _entry_path(path) -> Path:
    """Chemin d'une entrée : dossier parent résolu, nom gardé tel quel (un
    lien est renommé lui-même, jamais sa cible)."""
    path = Path(path)
    return Path(os.path.realpath(path.parent)) / path.name


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
        """Retient le remplacement de ``text[start:end]`` par ``value``, compté
        dans la rubrique ``category`` (``CATEGORIES``) ; un remplacement qui ne
        change rien est ignoré."""
        if self.text[start:end] != value:
            self.items.append((start, end, value, category))

    def __bool__(self):
        return bool(self.items)

    def touches(self, start, end) -> bool:
        """Un remplacement retenu recouvre-t-il ``text[start:end]`` ?"""
        return any(s < end and start < e for s, e, _v, _c in self.items)

    def counts(self) -> tuple:
        """``((rubrique, nombre), …)`` des remplacements retenus, dans l'ordre
        de ``CATEGORIES``."""
        found = {}
        for *_span, category in self.items:
            found[category] = found.get(category, 0) + 1
        return tuple((c, found[c]) for c in CATEGORIES if c in found)

    def apply(self) -> str:
        """Le texte, tous les remplacements faits ; deux remplacements qui se
        recouvrent lèvent ``AssertionError``."""
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


def _same_place(a, b) -> bool:
    """Même entrée de répertoire (si elles existent), sinon même chemin."""
    first, second = _entry(a), _entry(b)
    if first is not None and second is not None:
        return first == second
    return os.path.normcase(os.fspath(a)) == os.path.normcase(os.fspath(b))


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
        self.project_text = ""
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
        """Lit l'édition, ses parties et les documents XML de ``<documents>``,
        avec leurs identifiants (``xml_references.collect_ids``). Un document
        où l'ancien identifiant désigne autre chose qu'un ``<witness>`` est
        noté : les pointeurs vers lui ne changeront pas. Un document illisible
        est un refus."""
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
        """Remplit ``surfaces`` : les surfaces du témoin (``<image surface>`` de
        project.xml, ``<surface xml:id="P-p0001">`` des documents,
        ``tei_surface_id`` de ses JSON) et leurs zones prennent le nouveau
        préfixe, quand elles commencent par l'ancien (préfixe tiré de
        l'identifiant par ``safe_id_component``). Rien à faire si le préfixe ne
        change pas ; refus si un autre témoin a l'ancien ou le nouveau préfixe."""
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
        for other in self.project.witnesses:
            if other.id == self.old_id:
                continue
            for image in other.image_files:
                if image.surface_id in wanted:
                    position = self.project_text.find(f'"{image.surface_id}"')
                    self.problems.append(Message(
                        "witness_rename.id_used", id=image.surface_id, element="image", file="project.xml",
                        line=self.project_text.count("\n", 0, max(position, 0)) + 1))
                    return
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

    def _shared_with(self, source, target, mapping):
        """Autre témoin dont le fichier ou dossier porte le même nom (noms
        ASCII des caches IIIF : α et β ; « P » et « P* »), ou None."""
        if mapping is None:
            return None
        for other in self.project.witnesses:
            if other.id == self.old_id:
                continue
            path = _entry_path(mapping(other.id))
            if _same_place(path, source) or _same_place(path, target):
                return other
        return None

    def _move(self, source, target, *, required=False, mapping=None):
        source, target = _entry_path(source), _entry_path(target)
        # Comparaison exacte : sous Windows, deux Path qui ne diffèrent que par
        # la casse sont égaux, alors que P → p est bien un renommage.
        if str(source) == str(target):
            return
        exists = os.path.lexists(source)
        other = self._shared_with(source, target, mapping)
        if other is not None:
            if exists:
                self.notes.append(Message("witness_rename.shared_kept", file=_display(self.root, source),
                                          witness=other.display_siglum))
            return
        if exists and not _within(self.root, source.parent):
            self.problems.append(Message("witness_rename.external_file", file=str(source)))
            return
        if os.path.lexists(target):
            same = (exists and source.parent == target.parent
                    and source.name.casefold() == target.name.casefold() and _entry(source) == _entry(target))
            if not same and (exists or required):
                self.problems.append(Message("witness_rename.target_exists", file=_display(self.root, target)))
                return
        if exists:
            self.moves.append(Move(source, target))

    def plan_moves(self, alignment_attribute):
        """Prévoit les renommages (``moves``) : le JSON d'alignement du témoin
        quand il est dans ``alignments/`` sous son identifiant (nouveau nom :
        celui que Varians donne en copiant le fichier si project.xml l'écrit
        dans ``@alignment``, ``alignment_attribute`` ; sinon le nom
        conventionnel), ``alignments/<texte>/P.json``, le cache et la copie
        locale IIIF, ``images/P/`` et ``alto/P/``. Une entrée absente est
        ignorée ; une entrée qui sert aussi à un autre témoin reste en place
        (note). Refus : entrée hors du dossier du projet, ou nouveau nom déjà
        pris (pour les JSON d'alignement, même sans ancien fichier)."""
        from iiif_local import store_dir
        from iiif_manifest import cache_path
        old, new = self.old_id, self.new_id
        if old == new:
            return
        root = self.root
        alignments = root / "alignments"
        if self.witness.alignment is not None:
            path = _entry_path(self.witness.alignment)
            if path.parent == _entry_path(alignments) and path.suffix == ".json" and path.stem in (
                    old, _safe_filename(old)):
                # Avec @alignment, le nom que Varians donne en copiant le
                # fichier ; sans lui, le nom conventionnel que lit project.xml.
                name = _safe_filename(new) if alignment_attribute else new
                others = {w.id: w.alignment for w in self.project.witnesses if w.alignment is not None}
                self._move(path, alignments / f"{name}.json", required=True,
                           mapping=lambda wid: others.get(wid) or alignments / f"{wid}\0.json")
        if alignments.is_dir():
            for folder in sorted(p for p in alignments.iterdir() if p.is_dir()):
                self._move(folder / f"{old}.json", folder / f"{new}.json", required=True)
        self._move(cache_path(root, old), cache_path(root, new), mapping=lambda wid: cache_path(root, wid))
        self._move(store_dir(root, old), store_dir(root, new), mapping=lambda wid: store_dir(root, wid))
        for folder in ("images", "alto"):
            self._move(root / folder / _safe_filename(old), root / folder / _safe_filename(new),
                       mapping=lambda wid, folder=folder: root / folder / _safe_filename(wid))

    def rebase(self, raw, base_dir):
        """Chemin ``raw`` (relatif à ``base_dir`` ou absolu) qui passe par un
        fichier ou dossier renommé : le même texte, ce seul nom changé ;
        sinon None. Chaque étape du chemin est comparée à l'entrée renommée
        sur le disque (casse, liens, lecteurs réseau compris)."""
        if not self.moves:
            return None
        value = raw.strip()
        if not value or (_SCHEME_RE.match(value) and not _DRIVE_RE.match(value)):
            return None
        offset = raw.index(value)
        absolute = value.startswith(("/", "\\")) or bool(_DRIVE_RE.match(value))
        targets = {}
        for move in self.moves:
            key = _entry(move.source)
            if key is not None:
                targets[key] = move.target.name
        names = {move.source.name.casefold() for move in self.moves}
        for match in re.finditer(r"[^\\/]+", value):
            part = match.group(0)
            if part in (".", ".."):
                continue
            prefix = value[:match.end()]
            candidate = prefix if absolute else os.path.join(base_dir, prefix)
            if absolute and _DRIVE_RE.match(value) is None and len(prefix) == 2 and prefix.endswith(":"):
                continue
            if not os.path.lexists(candidate):
                return None
            if part.casefold() in names:
                name = targets.get(_entry(candidate))
                if name is not None:
                    start = offset + match.start()
                    return raw[:start] + name + raw[offset + match.end():]
        return None

    # -- pointeurs ------------------------------------------------------------------------

    def _declares_witness(self, key) -> bool:
        return any(target.element == "witness" for target in (self.ids.get(key) or {}).get(self.old_id, ()))

    def _pointer(self, token, attribute, path, line, element=""):
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
            if attribute not in ("wit", "edRef"):
                # persName/@ref vise une personne, @who aussi : jamais le témoin.
                from xml_references import target_elements
                expected = target_elements(element, attribute)
                if expected is not None and "witness" not in expected:
                    return None
                # « #P » d'un document qui ne déclare pas P, quand P est ailleurs
                # autre chose qu'un témoin : on ne sait pas lequel il vise.
                if (self.other_target and not self._declares_witness(target)
                        and not (target in self.group and any(self._declares_witness(k) for k in self.group))):
                    self.notes.append(Message("witness_rename.ambiguous", file=_display(self.root, path),
                                              line=line, token=token))
                    return None
            return f"{file}#{self.new_id}", "pointers"
        if attribute in ("wit", "edRef") and token == self.old_id and self.old_id != self.new_id:
            return self.new_id, "pointers"
        if attribute == "facs" and token in self.surfaces:
            return self.surfaces[token], "surfaces"
        return None

    def _expression_re(self):
        # « &#xa; » est un caractère, pas le pointeur « #xa ».
        return re.compile("(?<!&)#" + re.escape(self.old_id) + "(?!" + _NAME_TAIL + ")")

    # -- documents XML --------------------------------------------------------------------

    def plan_document(self, path, text):
        """Prévoit les changements d'un document XML : déclaration du
        ``<witness>`` (``xml:id``, ``<idno type="siglum">``, nom), pointeurs
        vers le témoin (``#P``, ``fichier.xml#P``, ``P`` seul dans ``@wit`` et
        ``@edRef``), surfaces et zones, chemins qui passent par un fichier
        renommé ; relève les citations du sigle (``mentions``). Un document à
        changer doit être dans le projet, ne pas déclarer d'autre encodage
        qu'UTF-8 et être bien formé, sinon c'est un refus ; ses changements
        s'ajoutent à ``changes``."""
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
                if attribute in ("url", "href"):
                    new = self.rebase(value, path.parent)
                    if new is not None:
                        edits.add(start, end, _escape(new, quote), "paths")
                        continue
                for piece in re.finditer(r"\S+", raw):
                    token_text = html.unescape(piece.group(0))
                    if "#" not in token_text and ("/" in token_text or "\\" in token_text):
                        new = self.rebase(token_text, path.parent)
                        if new is not None:
                            edits.add(start + piece.start(), start + piece.end(), _escape(new, quote), "paths")
                        continue
                    found = self._pointer(token_text, attribute, path, _line(starts, start + piece.start()), local)
                    if found is not None:
                        edits.add(start + piece.start(), start + piece.end(), _escape(found[0], quote), found[1])
                    elif (self.old_id != self.new_id and expression.search(token_text)
                          and token_text.partition("#")[2] != self.old_id):
                        self.mentions.append(self._mention(path, text, starts, start + piece.start()))
        for index in witnesses:
            self._declaration(text, tokens, index, edits)
        self._text_mentions(path, text, starts, tokens, edits)
        if edits:
            if not _within(self.root, path):
                self.problems.append(Message("witness_rename.external_file", file=str(path)))
                return
            if not self._utf8(path, text):
                return
            error = _parse_error(text)
            if error is not None:
                self.problems.append(Message("witness_rename.malformed", file=_display(self.root, path),
                                             line=error[0]))
                return
            self.changes.append(FileChange(path, text, edits.apply(), edits.counts()))

    def _declaration(self, text, tokens, index, edits):
        """``<idno type="siglum">`` et nom du ``<witness>`` déclaré. Sa fin est
        trouvée par profondeur (un groupe de témoins contient d'autres
        ``<witness>``) ; l'``<idno>`` est un de ses enfants directs."""
        opening = tokens[index]
        prefix = _prefix(opening.name)
        idno_needed = self.new_siglum != self.new_id
        if opening.kind == "self":
            if idno_needed:
                slash = text.rindex("/", opening.start, opening.end)
                edits.add(slash, opening.end, f'><{prefix}idno type="siglum">{_escape(self.new_siglum)}'
                          f"</{prefix}idno></{opening.name}>", "declaration")
            return
        level, close, idno, idno_close, first_child = 0, None, None, None, None
        for token in tokens[index + 1:]:
            if token.kind == "close":
                if level == 0:
                    close = token if token.name == opening.name else None
                    break
                level -= 1
                if level == 0 and idno is not None and idno_close is None and token.name == idno.name:
                    idno_close = token
                continue
            if level == 0:
                first_child = first_child or token
                if idno is None and _local(token.name) == "idno" and any(
                        _local(n) == "type" and html.unescape(v).strip() == "siglum"
                        for n, _q, v, _s, _e in _attributes(text, token)):
                    idno = token
            if token.kind == "open":
                level += 1
        if close is None:
            return
        label_start = opening.end
        if idno is not None and idno.kind == "self":
            tag = text[idno.start:idno.end]
            edits.add(idno.start, idno.end, tag[:tag.rindex("/")].rstrip() + ">" + _escape(self.new_siglum)
                      + f"</{idno.name}>", "declaration")
            if first_child is idno and not text[opening.end:idno.start].strip():
                label_start = idno.end
        elif idno is not None and idno_close is not None:
            if html.unescape(text[idno.end:idno_close.start]).strip() != self.new_siglum:
                edits.add(idno.end, idno_close.start, _escape(self.new_siglum), "declaration")
            if first_child is idno and not text[opening.end:idno.start].strip():
                label_start = idno_close.end
        elif idno is None and idno_needed:
            edits.add(opening.end, opening.end, f'<{prefix}idno type="siglum">{_escape(self.new_siglum)}'
                      f"</{prefix}idno>", "declaration")
        label_end = text.find("<", label_start, close.end)
        label_end = close.start if label_end < 0 else label_end
        label = text[label_start:label_end]
        for old, new in ((self.old_siglum, self.new_siglum), (self.old_id, self.new_siglum)):
            # Texte brut : un sigle écrit avec une entité (« &#80; ») n'est pas
            # retouché, les positions ne seraient pas les siennes.
            new_label = relabel(label, old, new)
            if new_label is not None:
                lead = len(label) - len(label.lstrip())
                edits.add(label_start + lead, label_start + lead + len(old), _escape(new), "declaration")
                break

    def _utf8(self, path, text) -> bool:
        """Un fichier qui déclare un autre encodage qu'UTF-8 est refusé :
        Varians écrit en UTF-8, et la déclaration mentirait."""
        declared = declared_encoding(text)
        if declared is not None and not is_utf8(declared.name):
            self.problems.append(Message("witness_rename.encoding", file=_display(self.root, path),
                                         encoding=declared.name))
            return False
        return True

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
        """Remplacements à faire dans le texte de project.xml, rendus sans être
        appliqués (``_Edits``) : le ``<witness>`` du témoin (``id``,
        ``siglum``, ``label``, ``alignment``), ``<witnesses base>``, ``<part
        base>``, ``<webViewer textWitness>``, les ``<param value>`` des
        scénarios et les ``#P`` des ``<query>``, les chemins (``file``,
        ``path``, ``alignment``) qui passent par un fichier renommé, les
        ``<image surface>``."""
        edits = _Edits(text)
        tokens = scan_xml_tags(text)
        root = self.root
        query_start = None
        expression = self._expression_re()
        for token in tokens:
            local = _local(token.name)
            if token.kind == "close":
                if local == "query" and query_start is not None and self.old_id != self.new_id:
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
                elif name in ("file", "path", "alignment"):
                    new = self.rebase(value, root)
                    if new is not None:
                        edits.add(start, end, _escape(new, quote), "paths")
                elif (local, name) == ("image", "surface") and stripped in self.surfaces:
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
        """Prévoit les changements d'un JSON d'alignement : ``meta.witness``
        (dans un JSON du témoin seulement, ``own``), ``meta.base_witness``,
        ``pages[].tei_surface_id`` et les chemins ``pages[].image.path`` ou
        ``.file``. L'ancien identifiant y devient le nouveau, l'ancien sigle le
        nouveau sigle. Refus : JSON illisible ; JSON abîmé, s'il est au témoin
        ou devrait changer ; JSON hors du projet, sauf si seul son ``meta``
        changerait (simple note : il n'est pas modifié)."""
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            self.problems.append(Message("witness_rename.unreadable", file=_display(self.root, path),
                                         error=str(error)))
            return
        try:
            json.loads(text.lstrip("\ufeff"))
            damaged = None
        except ValueError as error:
            damaged = getattr(error, "lineno", 0)
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
        if damaged is not None:
            # JSON abîmé : sa lecture n'est pas sûre. Celui du témoin, ou un
            # autre qui devrait changer, est à réparer d'abord.
            if edits or own:
                self.problems.append(Message("witness_rename.malformed", file=_display(self.root, path),
                                             line=damaged))
            return
        if not edits:
            return
        try:
            json.loads(edits.apply().lstrip("\ufeff"))
        except ValueError:                                  # pragma: no cover - garde-fou
            raise AssertionError(f"{path} : le changement de sigle le rendrait illisible")
        if not _within(self.root, path):
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

    interrupted = read_journal(project_path.parent)
    if interrupted is not None:
        return _replace(plan, problems=(Message("witness_rename.interrupted", old=interrupted.get("old", "?"),
                                                new=interrupted.get("new", "?")),))
    planner = _Planner(project, witness, new_id, new_siglum)
    project_text = planner.project_text = planner._read(project_path)
    if project_text is None:
        return _replace(plan, problems=tuple(planner.problems))
    for ident, siglum in _declared_witnesses(project_text):
        if ident == witness.id:
            continue
        if ident.casefold() == new_id.casefold() or (siglum or ident).casefold() == new_siglum.casefold():
            return _replace(plan, problems=(Message("witness_rename.taken", siglum=new_siglum,
                                                    witness=siglum or ident),))
    if not planner._utf8(project_path, project_text):
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


def _declared_witnesses(project_text):
    """``(id, sigle)`` des ``<witness>`` de project.xml, lus dans son texte."""
    for token in scan_xml_tags(project_text):
        if token.kind != "close" and _local(token.name) == "witness":
            values = {name: html.unescape(raw).strip() for name, _q, raw, _s, _e in _attributes(project_text, token)}
            if values.get("id"):
                yield values["id"], values.get("siglum", "")


def _has_alignment_attribute(project_text, witness_id) -> bool:
    for token in scan_xml_tags(project_text):
        if token.kind != "close" and _local(token.name) == "witness":
            values = {name: html.unescape(raw).strip() for name, _q, raw, _s, _e in _attributes(project_text, token)}
            if values.get("id") == witness_id:
                return bool(values.get("alignment"))
    return False


# --- Journal d'un changement interrompu : lecture (écriture : witness_rename) -------------

JOURNAL = Path(".varians") / "witness-rename.json"


def journal_path(root) -> Path:
    """Journal d'un changement de sigle en cours, dans le dossier du projet."""
    return Path(root) / JOURNAL


def read_journal(root):
    """Le journal d'un changement interrompu (dict), ou None."""
    path = journal_path(root)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"old": "?", "new": "?", "damaged": True}
    return data if isinstance(data, dict) else {"old": "?", "new": "?", "damaged": True}
