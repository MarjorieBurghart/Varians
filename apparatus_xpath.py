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
``<rdg>`` de son ``<app>``. Un témoin en lacune (``<lacunaStart/>`` …
``<lacunaEnd/>``, V0.9.1.3) n'a pas de leçon dans le passage.
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


def _parse(xml_text):
    """Racine du document, ou None s'il est mal formé."""
    try:
        from lxml import etree
        parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
        return etree.fromstring((xml_text or "").encode("utf-8"), parser=parser)
    except Exception:
        return None


def witness_ids(xml_text):
    """Identifiants des ``<witness>`` des ``<listWit>``, dans l'ordre du
    document ; liste vide si le XML est mal formé."""
    root = _parse(xml_text)
    if root is None:
        return []
    ids = root.xpath("//tei:listWit//tei:witness/@xml:id", namespaces={"tei": TEI_NS, "xml": XML_NS})
    return [str(value) for value in ids]


def part_witnesses(part_text, edition_text):
    """``(identifiants, provenance)`` des témoins d'une partie d'une édition
    assemblée (XInclude), dans cet ordre de préférence :

    - ``part`` : le ``<listWit>`` de la partie (son en-tête) ;
    - ``locus`` : les témoins de l'édition dont un ``<locus target>`` vise un
      élément de la partie ;
    - ``wit`` : les témoins cités dans les ``@wit`` de la partie, dans l'ordre
      du ``<listWit>`` de l'édition, puis dans l'ordre de citation.
    """
    own = witness_ids(part_text)
    if own:
        return own, "part"
    part = _parse(part_text)
    if part is None:
        return [], "part"
    namespaces = {"tei": TEI_NS, "xml": XML_NS}
    part_ids = {str(value) for value in part.xpath("//@xml:id", namespaces=namespaces)}
    edition = _parse(edition_text)
    order = []
    if edition is not None:
        located = []
        for witness in edition.xpath("//tei:listWit//tei:witness[@xml:id]", namespaces=namespaces):
            ident = witness.get(f"{{{XML_NS}}}id")
            order.append(ident)
            for locus in witness.xpath(".//tei:locus[@target]", namespaces=namespaces):
                if {token[1:] for token in locus.get("target").split() if token.startswith("#")} & part_ids:
                    located.append(ident)
                    break
        if located:
            return located, "locus"
    cited = []
    for value in part.xpath("//@wit"):
        for token in str(value).split():
            if token.startswith("#") and token[1:] not in cited:
                cited.append(token[1:])
    rank = {ident: index for index, ident in enumerate(order)}
    return sorted(cited, key=lambda ident: rank.get(ident, len(order))), "wit"


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


def _lacuna_marks(name, witness_id):
    """``<lacunaStart/>`` ou ``<lacunaEnd/>`` (``name``) qui précèdent le nœud
    courant et concernent ``witness_id`` : par leur ``@wit``, ou par la leçon
    (``<rdg>``, ``<lem>``) qui les contient."""
    return (f"preceding::tei:{name}[{_cites(witness_id)} or (not(@wit) and "
            f"ancestor::*[self::tei:rdg or self::tei:lem][1][{_cites(witness_id)}])]")


def _in_lacuna(witness_id):
    """Le nœud courant est dans une lacune de ``witness_id`` : plus de débuts
    que de fins de lacune le précèdent."""
    return (f"count({_lacuna_marks('lacunaStart', witness_id)}) > "
            f"count({_lacuna_marks('lacunaEnd', witness_id)})")


def incomplete_app_xpath(ids, lacunose=()):
    """``<app>`` où un témoin attendu n'a pas de leçon.

    Les témoins attendus sont ceux du ``<listWit>`` pour un ``<app>`` de
    premier niveau, ceux de la leçon englobante pour un ``<app>`` imbriqué.
    Un ``<app>`` dont un ``<lem>`` n'a pas de ``@wit`` n'est pas signalé ; un
    ``<app>`` imbriqué dans une leçon sans ``@wit`` n'est pas contrôlé.

    ``lacunose`` : témoins qui ont des lacunes dans le document (V0.9.1.3) ;
    un ``<app>`` placé dans l'une d'elles n'attend pas de leçon de ce témoin.
    La condition, coûteuse (axe ``preceding``), n'est ajoutée que pour eux."""
    lacunose = set(lacunose)
    missing = [f"((not({_ENCLOSING}) or {_ENCLOSING}[{_cites(w)}]) and not({_READINGS}[{_cites(w)}])"
               + (f" and not({_in_lacuna(w)})" if w in lacunose else "") + ")"
               for w in ids]
    return (f"//tei:app[not({_LEMS_WITHOUT_WIT}) and not({_ENCLOSING}[not(@wit)])"
            " and (" + " or ".join(missing) + ")]")


def witness_xpath(witness_id, present, rdg_only):
    """``<app>`` où ``witness_id`` est cité (``present``) ou non. Dans les
    ``<rdg>`` seulement si ``rdg_only`` (citation explicite) ; sinon dans
    une leçon quelconque, ``<lem>`` sans ``@wit`` compris."""
    condition = f"{_RDGS}[{_cites(witness_id)}]" if rdg_only else _app_cites(witness_id)
    return f"//tei:app[{condition}]" if present else f"//tei:app[not({condition})]"
