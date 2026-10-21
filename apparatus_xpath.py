# -*- coding: utf-8 -*-
"""Requêtes XPath de contrôle de l'apparat critique, sans Qt.

L'apparat est supposé encodé en *parallel segmentation* : chaque ``<app>``
réunit ses leçons (``<lem>``, ``<rdg>``, y compris dans un ``<rdgGrp>``),
dont ``@wit`` cite les témoins sous la forme ``#A``. Les témoins sont les
``<witness xml:id>`` du ``<listWit>``.

Les requêtes produites sont en XPath 1.0 ordinaire, avec le préfixe ``tei:``,
pour rester utilisables telles quelles dans les autres outils XML. Elles
sont longues (une condition par témoin), XPath 1.0 ne sachant pas découper
``@wit`` en jetons.

Un ``<lem>`` sans ``@wit`` est réputé couvrir les témoins absents des
``<rdg>`` de son ``<app>``.
"""
from __future__ import annotations

import re

TEI_NS = "http://www.tei-c.org/ns/1.0"
XML_NS = "http://www.w3.org/XML/1998/namespace"

# Leçons d'un <app> : ses <lem> et <rdg>, y compris dans un <rdgGrp>.
_READINGS = "(tei:lem|tei:rdg|tei:rdgGrp/tei:lem|tei:rdgGrp/tei:rdg)"
_RDGS = "(tei:rdg|tei:rdgGrp/tei:rdg)"
_LEMS_WITHOUT_WIT = "(tei:lem|tei:rdgGrp/tei:lem)[not(@wit)]"
# Leçon qui contient un <app> imbriqué.
_ENCLOSING = "ancestor::*[self::tei:lem or self::tei:rdg][1]"
# Nom XML sans deux-points (xml:id) : ni espace, ni guillemet, ni « # ».
_NCNAME = re.compile(r"^[^\W\d][\w.\-]*$")


def witness_ids(xml_text):
    """Identifiants des ``<witness>`` des ``<listWit>``, dans l'ordre du
    document ; liste vide si le XML est mal formé."""
    try:
        from lxml import etree
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
        root = etree.fromstring((xml_text or "").encode("utf-8"), parser=parser)
    except Exception:
        return []
    ids = root.xpath("//tei:listWit//tei:witness/@xml:id", namespaces={"tei": TEI_NS, "xml": XML_NS})
    return [str(value) for value in ids]


def _cites(witness_id):
    """La leçon courante cite ``witness_id`` dans ``@wit`` (jeton exact)."""
    if not _NCNAME.match(witness_id or ""):
        raise ValueError(witness_id)
    return f"contains(concat(' ', normalize-space(@wit), ' '), ' #{witness_id} ')"


def _cites_twice(witness_id):
    """``@wit`` de la leçon courante cite deux fois ``witness_id``."""
    _cites(witness_id)
    return (f"contains(substring-after(concat(' ', normalize-space(@wit), ' '), ' #{witness_id} '), "
            f"'#{witness_id} ')")


def _app_cites(witness_id):
    """L'``<app>`` courant donne une leçon à ``witness_id`` : citation
    explicite, ou ``<lem>`` sans ``@wit`` si aucun ``<rdg>`` ne le cite."""
    return (f"({_READINGS}[{_cites(witness_id)}] or "
            f"({_LEMS_WITHOUT_WIT} and not({_RDGS}[{_cites(witness_id)}])))")


def repeated_witness_xpath(ids):
    """``<app>`` où un témoin est cité plusieurs fois : dans deux leçons, ou
    deux fois dans le même ``@wit`` ; sa leçon est alors ambiguë."""
    conditions = [f"count({_READINGS}[{_cites(w)}]) > 1 or {_READINGS}[{_cites_twice(w)}]" for w in ids]
    return "//tei:app[" + " or ".join(conditions) + "]"


def incomplete_app_xpath(ids):
    """``<app>`` où un témoin attendu n'a pas de leçon.

    Les témoins attendus sont ceux du ``<listWit>`` pour un ``<app>`` de
    premier niveau, ceux de la leçon englobante pour un ``<app>`` imbriqué.
    Un ``<app>`` dont un ``<lem>`` n'a pas de ``@wit`` n'est pas signalé ; un
    ``<app>`` imbriqué dans une leçon sans ``@wit`` n'est pas contrôlé."""
    missing = [f"((not({_ENCLOSING}) or {_ENCLOSING}[{_cites(w)}]) and not({_READINGS}[{_cites(w)}]))"
               for w in ids]
    return (f"//tei:app[not({_LEMS_WITHOUT_WIT}) and not({_ENCLOSING}[not(@wit)])"
            " and (" + " or ".join(missing) + ")]")


def witness_xpath(witness_id, present, rdg_only):
    """``<app>`` où ``witness_id`` est cité (``present``) ou non. Dans les
    ``<rdg>`` seulement si ``rdg_only`` (citation explicite) ; sinon dans
    une leçon quelconque, ``<lem>`` sans ``@wit`` compris."""
    condition = f"{_RDGS}[{_cites(witness_id)}]" if rdg_only else _app_cites(witness_id)
    return f"//tei:app[{condition}]" if present else f"//tei:app[not({condition})]"
