# -*- coding: utf-8 -*-
"""Complétion des feuilles XSLT (V0.9.2.1), sans Qt.

Les propositions viennent du schéma RELAX NG d'XSLT 3.0 livré avec Varians
(``resources/schemas/xslt30``, voir son LISEZMOI), lu par le moteur de
complétion RNG (``rng_completion``). Ce moteur ne connaît pas les espaces de
noms : ce module tient compte de ceux de la feuille.

- **Préfixe** : les noms proposés portent le préfixe que la feuille lie à
  l'espace de noms XSLT (``xslt_scenarios.stylesheet_info``), souvent
  ``xsl:`` ; aucun s'il est l'espace de noms par défaut.
- **Élément résultat littéral** : un élément d'un autre espace de noms
  (``div``, ``tei:p``…), reconnu à son préfixe, contient un constructeur de
  séquence : on y propose les instructions XSLT, et ses attributs ``xsl:*``.
  Un ``<text>`` sans préfixe est donc un élément résultat, pas ``xsl:text``.
- **XSLT 1.0** (``version="1.0"``) : seuls les 35 éléments d'XSLT 1.0 et
  leurs attributs (``XSLT10_ATTRIBUTES``, d'après la recommandation) ;
  toute autre version reçoit le schéma 3.0 entier.
- Les attributs « fantômes » d'XSLT 3.0 (``_match``…) ne sont pas proposés.
"""
from __future__ import annotations

from functools import lru_cache

from project_config import APPLICATION_ROOT
from rng_completion import load_completion_model

XSLT_SCHEMA = APPLICATION_ROOT / "resources" / "schemas" / "xslt30" / "schema-for-xslt30.rng"

# Éléments d'XSLT 1.0 et leurs attributs (recommandation du 16 novembre 1999).
XSLT10_ATTRIBUTES = {
    "apply-imports": (),
    "apply-templates": ("select", "mode"),
    "attribute": ("name", "namespace"),
    "attribute-set": ("name", "use-attribute-sets"),
    "call-template": ("name",),
    "choose": (),
    "comment": (),
    "copy": ("use-attribute-sets",),
    "copy-of": ("select",),
    "decimal-format": ("name", "decimal-separator", "grouping-separator", "infinity", "minus-sign", "NaN",
                       "percent", "per-mille", "zero-digit", "digit", "pattern-separator"),
    "element": ("name", "namespace", "use-attribute-sets"),
    "fallback": (),
    "for-each": ("select",),
    "if": ("test",),
    "import": ("href",),
    "include": ("href",),
    "key": ("name", "match", "use"),
    "message": ("terminate",),
    "namespace-alias": ("stylesheet-prefix", "result-prefix"),
    "number": ("level", "count", "from", "value", "format", "lang", "letter-value", "grouping-separator",
               "grouping-size"),
    "otherwise": (),
    "output": ("method", "version", "encoding", "omit-xml-declaration", "standalone", "doctype-public",
               "doctype-system", "cdata-section-elements", "indent", "media-type"),
    "param": ("name", "select"),
    "preserve-space": ("elements",),
    "processing-instruction": ("name",),
    "sort": ("select", "lang", "data-type", "order", "case-order"),
    "strip-space": ("elements",),
    "stylesheet": ("id", "extension-element-prefixes", "exclude-result-prefixes", "version"),
    "template": ("match", "name", "priority", "mode"),
    "text": ("disable-output-escaping",),
    "transform": ("id", "extension-element-prefixes", "exclude-result-prefixes", "version"),
    "value-of": ("select", "disable-output-escaping"),
    "variable": ("name", "select"),
    "when": ("test",),
    "with-param": ("name", "select"),
}

# Attributs de l'espace de noms XSLT permis sur un élément résultat littéral.
LITERAL_RESULT_ATTRIBUTES = {
    "1.0": ("exclude-result-prefixes", "extension-element-prefixes", "use-attribute-sets", "version"),
    "3.0": ("default-collation", "default-mode", "default-validation", "exclude-result-prefixes", "expand-text",
            "extension-element-prefixes", "inherit-namespaces", "on-empty", "type", "use-attribute-sets",
            "use-when", "validation", "version", "xpath-default-namespace"),
}

# Le contenu d'un élément résultat littéral, un constructeur de séquence, est
# celui de xsl:if dans le schéma.
_SEQUENCE_CONSTRUCTOR = "if"


@lru_cache(maxsize=1)
def completion_model():
    """Le modèle de complétion du schéma XSLT 3.0 (chargé une fois)."""
    return load_completion_model(XSLT_SCHEMA)


def _version(info):
    return "1.0" if info.version.strip() == "1.0" else "3.0"


def _split(name):
    prefix, _colon, local = str(name or "").rpartition(":")
    return prefix, local


def _xslt_local(info, name):
    """Nom local de ``name`` s'il est dans l'espace de noms XSLT, sinon None."""
    prefix, local = _split(name)
    return local if prefix == info.prefix else None


def _qualified(info, local):
    return f"{info.prefix}:{local}" if info.prefix else local


def element_names(info, parent, before=(), after=(), model=None) -> tuple[str, ...]:
    """Éléments XSLT permis dans ``parent`` (son nom tel qu'il est écrit, None
    pour la racine), entre les frères ``before`` et ``after``."""
    model = model or completion_model()
    if parent is None:
        names = model.start_elements
    else:
        local = _xslt_local(info, parent)
        if local is None:                                   # élément résultat littéral
            names = model.child_elements_at(_SEQUENCE_CONSTRUCTOR, (), ())
        else:
            siblings = [tuple(n for n in (_xslt_local(info, s) for s in group) if n) for group in (before, after)]
            names = model.child_elements_at(local, *siblings)
    if _version(info) == "1.0":
        names = [name for name in names if name in XSLT10_ATTRIBUTES]
    return tuple(_qualified(info, name) for name in sorted(names))


def attribute_names(info, element, model=None) -> tuple[str, ...]:
    """Attributs permis sur ``element`` (son nom tel qu'il est écrit)."""
    local = _xslt_local(info, element)
    if local is None:                                       # élément résultat littéral
        if not info.prefix:
            return ()
        return tuple(f"{info.prefix}:{name}" for name in sorted(LITERAL_RESULT_ATTRIBUTES[_version(info)]))
    if _version(info) == "1.0":
        return tuple(sorted(XSLT10_ATTRIBUTES.get(local, ())))
    model = model or completion_model()
    return tuple(sorted(name for name in model.allowed_attributes(local) if not name.startswith("_")))


def attribute_values(info, element, attribute, model=None) -> tuple[str, ...]:
    """Valeurs permises de ``attribute`` sur ``element``, si le schéma en
    donne une liste finie (celle d'XSLT 3.0, même pour une feuille 1.0)."""
    local = _xslt_local(info, element)
    if local is None:
        return ()
    model = model or completion_model()
    return tuple(model.allowed_attribute_values(local, attribute))


class StylesheetCompletionModel:
    """Les propositions d'une feuille XSLT, avec l'interface du modèle de
    complétion RNG (``rng_completion.CompletionModel``) qu'emploie la
    complétion de Varians (``completion_ui``)."""

    def __init__(self, info, model=None):
        self.info = info
        self.model = model or completion_model()

    def child_elements_at(self, parent, before=(), after=()):
        return element_names(self.info, parent, before, after, self.model)

    def allowed_attributes(self, element):
        return attribute_names(self.info, element, self.model)

    def allowed_attribute_values(self, element, attribute):
        return attribute_values(self.info, element, attribute, self.model)
