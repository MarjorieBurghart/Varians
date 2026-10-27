# -*- coding: utf-8 -*-
"""Complétion des fichiers Schematron (V0.9.2.4), sans Qt.

Les propositions viennent du schéma ISO Schematron livré avec Varians
(``resources/schemas/schematron``, voir son LISEZMOI), lu par le moteur de
complétion RNG (``rng_completion``). Comme pour les feuilles XSLT
(``xslt_completion``), ce module tient compte des espaces de noms du
fichier :

- **Préfixe** : les noms proposés portent le préfixe que le fichier lie à
  l'espace de noms Schematron (``xml_roots.schematron_info``), souvent
  ``sch:`` ; aucun s'il est l'espace de noms par défaut.
- **Éléments étrangers** : un élément d'un autre espace de noms
  (``xsl:function``…) n'est pas complété, ni ses attributs.
- **Valeurs** : celles du schéma (``abstract``, ``xml:space``…), sinon des
  valeurs courantes pour ``severity``, ``role`` et ``queryBinding``
  (``SUGGESTED_VALUES``), que le schéma laisse libres.
"""
from __future__ import annotations

from functools import lru_cache

from project_config import APPLICATION_ROOT
from rng_completion import load_completion_model

SCHEMATRON_SCHEMA = APPLICATION_ROOT / "resources" / "schemas" / "schematron" / "iso-schematron.rng"
# Valeurs proposées pour des attributs libres : les niveaux que Varians
# distingue (schematron._level), et les langages de requête de la norme.
SUGGESTED_VALUES = {
    "severity": ("error", "fatal", "info", "warning"),
    "role": ("error", "fatal", "info", "warning"),
    "queryBinding": ("xpath2", "xpath3", "xpath31", "xslt2", "xslt3"),
}


@lru_cache(maxsize=1)
def completion_model():
    """Le modèle de complétion du schéma ISO Schematron (chargé une fois)."""
    return load_completion_model(SCHEMATRON_SCHEMA)


def _local(info, name):
    """Nom local de ``name`` s'il est dans l'espace de noms Schematron,
    sinon None."""
    prefix, _colon, local = str(name or "").rpartition(":")
    return local if prefix == info.prefix else None


def _qualified(info, local):
    return f"{info.prefix}:{local}" if info.prefix else local


def element_names(info, parent, before=(), after=(), model=None) -> tuple[str, ...]:
    """Éléments Schematron permis dans ``parent`` (son nom tel qu'il est
    écrit, None pour la racine), entre les frères ``before`` et ``after``."""
    model = model or completion_model()
    if parent is None:
        names = model.start_elements
    else:
        local = _local(info, parent)
        if local is None:                                   # élément étranger
            return ()
        siblings = [tuple(n for n in (_local(info, s) for s in group) if n) for group in (before, after)]
        names = model.child_elements_at(local, *siblings)
    return tuple(_qualified(info, name) for name in sorted(names))


def attribute_names(info, element, model=None) -> tuple[str, ...]:
    """Attributs permis sur ``element`` (son nom tel qu'il est écrit)."""
    local = _local(info, element)
    if local is None:
        return ()
    model = model or completion_model()
    return tuple(sorted(model.allowed_attributes(local)))


def attribute_values(info, element, attribute, model=None) -> tuple[str, ...]:
    """Valeurs de ``attribute`` sur ``element`` : la liste finie du schéma,
    sinon les valeurs proposées (``SUGGESTED_VALUES``)."""
    local = _local(info, element)
    if local is None:
        return ()
    model = model or completion_model()
    return tuple(model.allowed_attribute_values(local, attribute)) or SUGGESTED_VALUES.get(attribute, ())


class SchematronCompletionModel:
    """Les propositions d'un fichier Schematron, avec l'interface du modèle
    de complétion RNG (``rng_completion.CompletionModel``) qu'emploie la
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
