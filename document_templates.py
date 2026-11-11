# -*- coding: utf-8 -*-
"""Modèles de « Nouveau document XML » (sans Qt).

- Modèles de la TEI : ceux qu'Oxygen propose sous « TEI P5 », les squelettes
  publiés avec TEI P5 (``resources/templates/tei``, voir son LISEZMOI), un
  par déclinaison de la TEI, livrés tels quels. Un document créé d'après l'un
  d'eux est le modèle octet pour octet, sauf ses déclarations
  ``<?xml-model?>``, dont l'adresse passe de ``http://www.tei-c.org/`` à
  ``https://www.tei-c.org/``.
- « Même schéma que l'édition » : le squelette « All » de la TEI, avec les
  déclarations ``<?xml-model?>`` de l'édition ; quand l'édition suit le
  schéma du projet, le document est déclaré avec lui dans project.xml.
- Modèles du projet : les fichiers ``.xml`` de son dossier ``modeles/``,
  copiés tels quels.
- Document vide : l'élément racine choisi, seul.

Une adresse de schéma relative est recalculée pour le dossier du nouveau
document.
"""
from __future__ import annotations

import html
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
from urllib.parse import quote, unquote, urlparse
from xml.sax.saxutils import escape

import tei_templates as tei_library
from project_config import DocumentConfig
from schema_resolution import detect_xml_models

HERE = Path(__file__).resolve().parent
# Modèles livrés avec Varians et leur version de TEI P5 ; une version plus
# récente peut être installée (tei_templates) : tei_templates_version().
TEI_TEMPLATES_DIR = tei_library.BUNDLED_DIR
TEI_TEMPLATES_VERSION = tei_library.BUNDLED_VERSION
# Dossier des modèles d'un projet, dans le dossier du projet.
PROJECT_TEMPLATES_FOLDER = "modeles"
# Squelette de « Même schéma que l'édition ».
EDITION_SKELETON = "All"
TEI_NS = "http://www.tei-c.org/ns/1.0"
# Caractères lus au début d'un modèle du projet pour trouver son schéma.
_PROLOG_READ = 65536

_XML_MODEL_RE = re.compile(r"<\?xml-model\s.*?\?>", re.S)
_TEI_HTTP_HREF = re.compile(r"""(\bhref\s*=\s*["'])http://(www\.)?tei-c\.org/""")
_HREF_RE = re.compile(r"""(\bhref\s*=\s*)(["'])(.*?)\2""", re.S)
# Le prologue : déclarations, instructions, commentaires et DOCTYPE, jusqu'à
# la balise de l'élément racine.
_PROLOG_RE = re.compile(r"<\?.*?\?>|<!--.*?-->|<!DOCTYPE(?:[^\[>]|\[.*?\])*>|<[^?!]", re.S)


@dataclass(frozen=True)
class DocumentTemplate:
    """Un modèle de la liste. ``kind`` : ``tei`` (modèle de la TEI),
    ``edition`` (« Même schéma que l'édition »), ``project`` (dossier
    ``modeles/``) ou ``empty`` (document vide). ``schema`` : nom du schéma
    RELAX NG déclaré (``tei_lite.rng``), vide s'il n'y en a pas. Pour
    ``edition``, ``schema_mode`` file et ``schema_file`` : l'édition suit le
    schéma du projet."""
    kind: str
    name: str
    path: Path | None = None
    schema: str = ""
    schema_mode: str = "auto"
    schema_file: Path | None = None


def _declared_rng(text):
    """Nom du fichier RELAX NG déclaré par le premier ``<?xml-model?>``, ou ""."""
    for model in detect_xml_models(text):
        if model.href:
            return model.href.rstrip("/").rsplit("/", 1)[-1]
    return ""


def tei_templates_version():
    """Version de TEI P5 des modèles qui servent (``tei_templates.current``)."""
    return tei_library.current().version


def tei_templates():
    """Les modèles de la TEI, dans l'ordre d'Oxygen : alphabétique, sans
    tenir compte de la casse."""
    templates = []
    folder = tei_library.current().folder
    for path in sorted(folder.glob("*.xml"), key=lambda path: path.stem.casefold()):
        schema = _declared_rng(path.read_text(encoding="utf-8"))
        templates.append(DocumentTemplate("tei", path.stem, path, schema))
    return templates


def tei_template(name):
    """Le modèle de la TEI nommé ``name`` (« Lite », « All »…) ; KeyError
    s'il n'existe pas."""
    for template in tei_templates():
        if template.name == name:
            return template
    raise KeyError(name)


def https_tei_models(text):
    """``text`` dont les déclarations ``<?xml-model?>`` vers le site de la
    TEI passent de http à https ; rien d'autre ne change."""
    return _XML_MODEL_RE.sub(lambda match: _TEI_HTTP_HREF.sub(r"\1https://\2tei-c.org/", match.group(0)), text)


def tei_template_text(template):
    """Texte d'un nouveau document d'après le modèle de la TEI ``template`` :
    le fichier du modèle, ses déclarations de schéma en https."""
    return https_tei_models(template.path.read_text(encoding="utf-8"))


# --- Même schéma que l'édition, modèles du projet, document vide -----------------------------

def _prolog_models(text):
    """Les déclarations ``<?xml-model?>`` du prologue de ``text`` (avant
    l'élément racine), dans l'ordre : objets ``re.Match``."""
    models = []
    for match in _PROLOG_RE.finditer(text or ""):
        if match.group(0).startswith("<?xml-model"):
            models.append(match)
        elif not match.group(0).startswith(("<?", "<!")):
            break
    return models


def rebase_href(href, source_dir, target_dir):
    """Adresse ``href``, relative au dossier ``source_dir``, réécrite pour un
    document du dossier ``target_dir`` ; une adresse absolue (URL, chemin)
    reste telle quelle."""
    parsed = urlparse(href)
    if (len(parsed.scheme) > 1 or Path(href).is_absolute() or PureWindowsPath(href).is_absolute()
            or href.startswith(("/", "\\"))):
        return href
    target = os.path.normpath(Path(source_dir) / unquote(href))
    try:
        relative = os.path.relpath(target, Path(target_dir)).replace(os.sep, "/")
    except ValueError:  # autre lecteur (Windows)
        return Path(target).as_uri()
    return quote(relative, safe="/._-~") if "%" in href else relative


def rebased_models(text, source_dir, target_dir):
    """``text`` dont les déclarations ``<?xml-model?>`` à adresse relative
    sont réécrites pour un document du dossier ``target_dir`` (voir
    :func:`rebase_href`) ; rien d'autre ne change."""
    def rebase(match):
        def new_href(href_match):
            href = html.unescape(href_match.group(3))
            value = rebase_href(href, source_dir, target_dir)
            if value == href:
                return href_match.group(0)
            return href_match.group(1) + href_match.group(2) + escape(value, {'"': "&quot;", "'": "&apos;"}) \
                + href_match.group(2)
        return _HREF_RE.sub(new_href, match.group(0), count=1)
    pieces, last = [], 0
    for match in _prolog_models(text):
        pieces += [text[last:match.start()], rebase(match)]
        last = match.end()
    return "".join(pieces) + text[last:]


def edition_template(edition_text, schema_mode="auto", project_schema=None):
    """Entrée « Même schéma que l'édition », ou None si l'édition n'a pas de
    schéma : schéma du projet (``schema_mode`` file, ``project_schema``), ou
    déclarations ``<?xml-model?>`` dans le prologue de ``edition_text``
    (mode auto)."""
    if schema_mode == "file" and project_schema is not None:
        return DocumentTemplate("edition", "", None, Path(project_schema).name, "file", Path(project_schema))
    if schema_mode != "auto":
        return None
    models = _prolog_models(edition_text)
    if not models:
        return None
    return DocumentTemplate("edition", "", None, _declared_rng("\n".join(m.group(0) for m in models)))


def project_templates(project_root):
    """Les modèles du projet : les fichiers ``.xml`` du dossier ``modeles/``
    du projet (pas de ses sous-dossiers), par nom, sans tenir compte de la
    casse. Un fichier illisible y figure sans schéma ; sa lecture échouera à
    la création."""
    folder = Path(project_root) / PROJECT_TEMPLATES_FOLDER
    if not folder.is_dir():
        return []
    templates = []
    for path in sorted(folder.glob("*.xml"), key=lambda path: path.stem.casefold()):
        if not path.is_file():
            continue
        try:
            # Le prologue suffit : un gros fichier n'est pas lu en entier.
            with path.open(encoding="utf-8") as stream:
                schema = _declared_rng(stream.read(_PROLOG_READ))
        except (OSError, UnicodeError):
            schema = ""
        templates.append(DocumentTemplate("project", path.stem, path, schema))
    return templates


def empty_template():
    """Entrée « Document XML vide (élément racine au choix) »."""
    return DocumentTemplate("empty", "")


def empty_document_text(root_name):
    """Document XML vide d'élément racine ``root_name`` (dans l'espace de
    noms TEI pour ``TEI``). ValueError si ce n'est pas un nom d'élément."""
    namespace = f' xmlns="{TEI_NS}"' if root_name == "TEI" else ""
    text = f'<?xml version="1.0" encoding="UTF-8"?>\n<{root_name}{namespace}>\n</{root_name}>\n'
    try:
        ET.fromstring(text)
    except ET.ParseError:
        raise ValueError(root_name) from None
    return text


def _edition_schema_text(edition_text, edition_path, target):
    """Le squelette « All » de la TEI, avec les déclarations
    ``<?xml-model?>`` de l'édition à la place des siennes."""
    skeleton = tei_template_text(tei_template(EDITION_SKELETON))
    own = _prolog_models(skeleton)
    head, tail = skeleton[:own[0].start()], skeleton[own[-1].end():].lstrip("\r\n")
    declarations = [rebased_models(match.group(0), Path(edition_path).parent, Path(target).parent)
                    for match in _prolog_models(edition_text)]
    return head + "".join(declaration + "\n" for declaration in declarations) + tail


def document_text(template, target, *, edition_text="", edition_path=None, root_name=""):
    """Texte du nouveau document ``target`` d'après ``template`` :

    - modèle de la TEI : le modèle, déclarations de schéma en https ;
    - « Même schéma que l'édition » : le squelette « All » de la TEI avec
      les déclarations ``<?xml-model?>`` de ``edition_text`` (édition
      ``edition_path``) ;
    - modèle du projet : le fichier tel quel ;
    - document vide : l'élément ``root_name`` (ValueError s'il est invalide).

    Une adresse de schéma relative est recalculée depuis le dossier de
    ``target`` (:func:`rebase_href`)."""
    if template.kind == "tei":
        return tei_template_text(template)
    if template.kind == "edition":
        return _edition_schema_text(edition_text, edition_path, target)
    if template.kind == "project":
        return rebased_models(template.path.read_text(encoding="utf-8"), template.path.parent, Path(target).parent)
    if template.kind == "empty":
        return empty_document_text(root_name)
    raise ValueError(template.kind)


def document_config(template, target):
    """Déclaration du nouveau document ``target`` dans project.xml : avec le
    schéma du projet pour « Même schéma que l'édition » quand l'édition
    l'emploie, sinon d'après ses déclarations ``<?xml-model?>``."""
    if template.kind == "edition" and template.schema_mode == "file":
        return DocumentConfig(Path(target), schema_mode="file", schema=template.schema_file)
    return DocumentConfig(Path(target))
