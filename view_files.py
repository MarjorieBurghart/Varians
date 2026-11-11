# -*- coding: utf-8 -*-
"""Fichiers et contrôles d'une vue nommée de la Vue XSLT / CSS (V0.9.4.4),
sans Qt.

Une vue (``project_config.ViewConfig``) associe une feuille XSLT, une CSS et,
en option, les éléments modifiables comme fragment. « Nouvelle vue… » peut
écrire une feuille XSLT 1.0 et une CSS de départ, nommées d'après la vue,
dans ``xslt/`` et ``rendering/`` du projet (``write_starter``), sans jamais
remplacer un fichier. La feuille de départ montre tout document : un élément
qui contient du texte est un paragraphe (ses éléments y restent en ligne), un
élément qui ne contient que des éléments est un bloc. Varians y ajoute
lui-même les crayons ✎, comme pour toute feuille.
"""
from __future__ import annotations

import re
import unicodedata
from html import escape
from pathlib import Path

from lxml import etree

STARTER_FOLDERS = ("xslt", "rendering")
DEFAULT_SLUG = "vue"
_UNIT_NAME = re.compile(r"[A-Za-z_][\w.-]*\Z")

_STYLESHEET = """<?xml version="1.0" encoding="UTF-8"?>
<!-- Vue « {name} » : feuille XSLT 1.0 de départ, à adapter.
     Varians ajoute lui-même un crayon devant chaque élément modifiable de
     la vue, quelle que soit cette feuille. Le texte de l'élément <h1> est le
     nom de la vue lors de sa création. -->
<xsl:stylesheet version="1.0"
  xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
  xmlns:tei="http://www.tei-c.org/ns/1.0"
  exclude-result-prefixes="tei">
  <xsl:output method="html" encoding="UTF-8"/>

  <xsl:template match="/">
    <html>
      <head><meta charset="UTF-8"/><title>{name}</title></head>
      <body>
        <h1>{name}</h1>
        <xsl:apply-templates select="/*"/>
      </body>
    </html>
  </xsl:template>

  <!-- L'en-tête TEI n'est pas montré. -->
  <xsl:template match="tei:teiHeader"/>

  <!-- Dans un paragraphe, un élément reste en ligne ; ailleurs, un élément
       qui contient du texte est un paragraphe, un autre un bloc. La classe
       est le nom de l'élément (p.persName, div.person…), pour la CSS. -->
  <xsl:template match="*">
    <xsl:choose>
      <xsl:when test="ancestor::*[text()[normalize-space()]]">
        <span class="{{local-name()}}"><xsl:apply-templates/></span>
      </xsl:when>
      <xsl:when test="text()[normalize-space()] or not(*)">
        <p class="{{local-name()}}"><xsl:apply-templates/></p>
      </xsl:when>
      <xsl:otherwise>
        <div class="{{local-name()}}"><xsl:apply-templates/></div>
      </xsl:otherwise>
    </xsl:choose>
  </xsl:template>
</xsl:stylesheet>
"""

_CSS = """/* Vue « {name} » : CSS de départ, à adapter. */
body {{ line-height: 1.6; }}
h1 {{ font-size: 1.3em; margin: 0 0 0.8em; }}
div {{ margin: 0 0 0.8em; }}
p {{ margin: 0 0 0.3em; }}
"""


def view_slug(name) -> str:
    """Nom de fichier tiré du nom d'une vue : lettres latines sans accents,
    chiffres et tirets, en minuscules ; ``vue`` s'il n'en reste rien."""
    text = unicodedata.normalize("NFKD", str(name or "")).encode("ascii", "ignore").decode("ascii")
    words = re.findall(r"[A-Za-z0-9]+", text)
    return "-".join(words).lower() or DEFAULT_SLUG


def _free(folder: Path, name: str) -> Path:
    candidate, stem, suffix = folder / name, Path(name).stem, Path(name).suffix
    number = 2
    while candidate.exists():
        candidate = folder / f"{stem}_{number}{suffix}"
        number += 1
    return candidate


def starter_paths(root, name) -> tuple[Path, Path]:
    """Chemins libres de la feuille et de la CSS de départ de la vue
    ``name`` : ``xslt/<nom>.xsl`` et ``rendering/<nom>.css``, suffixés
    ``_2``, ``_3``… si le nom est pris."""
    root, slug = Path(root), view_slug(name)
    return _free(root / STARTER_FOLDERS[0], slug + ".xsl"), _free(root / STARTER_FOLDERS[1], slug + ".css")


def starter_stylesheet(name) -> str:
    """Feuille XSLT 1.0 de départ de la vue ``name``."""
    return _STYLESHEET.format(name=escape(str(name), quote=False).replace("--", "- -"))


def starter_css(name) -> str:
    """CSS de départ de la vue ``name`` (sans ``@media`` : Qt ignore les
    règles qui suivent)."""
    return _CSS.format(name=str(name).replace("*/", "* /").replace("/*", "/ *"))


def write_starter(root, name) -> tuple[str, str]:
    """Écrit la feuille et la CSS de départ de la vue ``name`` dans le
    projet ``root`` (jamais par-dessus un fichier) ; renvoie leurs chemins
    relatifs au projet, tels que project.xml les écrit."""
    root = Path(root)
    written = []
    for path, text in zip(starter_paths(root, name), (starter_stylesheet(name), starter_css(name))):
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "x", encoding="utf-8", newline="\n") as output:
            output.write(text)
        written.append(path.relative_to(root).as_posix())
    return tuple(written)


def _local(element) -> str:
    tag = element.tag
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else ""


def suggested_units(xml_text) -> tuple[str, ...]:
    """Éléments modifiables proposés pour une nouvelle vue d'un document :
    les noms des entrées de sa première liste (``listPerson``,
    ``listPlace``, ``listBibl``, ``list``…) hors de l'en-tête TEI. Rien pour
    un document qui a un ``<body>`` (la règle de l'édition y convient), ni
    pour un document mal formé."""
    try:
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
        root = etree.fromstring(xml_text.encode("utf-8"), parser)
    except (etree.XMLSyntaxError, ValueError):
        return ()
    elements = [e for e in root.iter() if isinstance(e.tag, str)]
    if any(_local(e) == "body" for e in elements):
        return ()
    for element in elements:
        if _local(element).startswith("list") and not any(_local(a) == "teiHeader" for a in element.iterancestors()):
            names = []
            for child in element:
                name = _local(child)
                if name and name not in names:
                    names.append(name)
            if names:
                return tuple(names)
    return ()


def parse_units(text) -> tuple[str, ...] | None:
    """Noms d'éléments séparés par des blancs ; None si l'un d'eux n'est pas
    un nom d'élément simple (sans préfixe)."""
    names = tuple(dict.fromkeys((text or "").split()))
    return names if all(_UNIT_NAME.match(name) for name in names) else None


def check_view(name, xslt_path, css_path, units_text, taken, *, starter=False) -> str | None:
    """Clé du message d'erreur d'une vue, ou None si elle peut être écrite :
    un nom non vide, différent (sans tenir compte de la casse) des vues
    ``taken`` ; une feuille XSLT existante ; une CSS existante si elle est
    donnée ; des noms d'éléments simples. Avec ``starter``, la feuille et la
    CSS sont celles de départ, à écrire : elles ne sont pas vérifiées."""
    name = (name or "").strip()
    if not name:
        return "views.error.name"
    if name.casefold() in {other.strip().casefold() for other in taken}:
        return "views.error.taken"
    if not starter and (xslt_path is None or not Path(xslt_path).is_file()):
        return "views.error.xslt"
    if not starter and css_path is not None and not Path(css_path).is_file():
        return "views.error.css"
    if parse_units(units_text) is None:
        return "views.error.units"
    return None
