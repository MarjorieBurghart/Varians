# -*- coding: utf-8 -*-
"""Modèles de « Nouveau document XML » (sans Qt).

Les modèles de la TEI sont ceux qu'Oxygen propose sous « TEI P5 » : les
squelettes publiés avec TEI P5 (``resources/templates/tei``, voir son
LISEZMOI), un par déclinaison de la TEI, livrés tels quels. Un document créé
d'après l'un d'eux est le modèle octet pour octet, sauf ses déclarations
``<?xml-model?>``, dont l'adresse passe de ``http://www.tei-c.org/`` à
``https://www.tei-c.org/``.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from schema_resolution import detect_xml_models

HERE = Path(__file__).resolve().parent
TEI_TEMPLATES_DIR = HERE / "resources" / "templates" / "tei"
# Version de TEI P5 dont viennent les modèles livrés.
TEI_TEMPLATES_VERSION = "4.12.0"

_XML_MODEL_RE = re.compile(r"<\?xml-model\s.*?\?>", re.S)
_TEI_HTTP_HREF = re.compile(r"""(\bhref\s*=\s*["'])http://(www\.)?tei-c\.org/""")


@dataclass(frozen=True)
class DocumentTemplate:
    """Un modèle de la liste : ``kind`` vaut ``tei`` (modèle de la TEI) ;
    ``schema`` est le nom du schéma RELAX NG qu'il déclare
    (``tei_lite.rng``), vide s'il n'en déclare pas."""
    kind: str
    name: str
    path: Path | None = None
    schema: str = ""


def _declared_rng(text):
    """Nom du fichier RELAX NG déclaré par le premier ``<?xml-model?>``, ou ""."""
    for model in detect_xml_models(text):
        if model.href:
            return model.href.rstrip("/").rsplit("/", 1)[-1]
    return ""


def tei_templates():
    """Les modèles de la TEI, dans l'ordre d'Oxygen : alphabétique, sans
    tenir compte de la casse."""
    templates = []
    for path in sorted(TEI_TEMPLATES_DIR.glob("*.xml"), key=lambda path: path.stem.casefold()):
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
