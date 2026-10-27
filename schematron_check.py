# -*- coding: utf-8 -*-
"""Vérification d'un fichier Schematron (V0.9.2.4), sans Qt.

``check(text, path)`` vérifie le texte *text* (celui de l'éditeur, même non
enregistré) du fichier Schematron *path* et rend un ``ValidationResult``,
comme la validation d'un document :

1. la bonne formation (erreurs du domaine ``PARSER``) ;
2. la structure, d'après le schéma ISO Schematron livré
   (``resources/schemas/schematron``, voir son LISEZMOI) : les erreurs
   RELAX NG à leur ligne. Une référence (``IDREF``) à un identifiant défini
   dans un fichier inclus n'est pas une erreur ; une référence inconnue est
   donnée à la ligne de l'élément qui la porte ;
3. les inclusions (``sch:include``) : un fichier absent est une erreur des
   règles (domaine ``SCHEMATRON_RULES``, code ``missing``) à la ligne de
   l'inclusion, et la compilation n'est pas tentée ;
4. la compilation par SchXslt2 et Saxon, toutes phases comprises
   (``schematron.check_compilation``) : l'assemblage des règles (code
   ``assembly`` : identifiant en double, phase qui cite un groupe absent…),
   puis chaque expression XPath (``xpath``), à sa ligne.

Sans Saxon, seules les étapes 1 à 3 sont faites et ``schematron_error``
vaut ``saxon_missing``. Le résultat est valide s'il n'a aucune erreur.
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from project_config import APPLICATION_ROOT
from relaxng_validation import ValidationResult, _checked, _dependency_path

ISO_SCHEMA = APPLICATION_ROOT / "resources" / "schemas" / "schematron" / "iso-schematron.rng"
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
_IDREF = re.compile(r'IDREFS? attribute (\S+) references an unknown ID "([^"]*)"')


def _included_ids(path, text):
    """Les identifiants définis dans les fichiers que *text* inclut."""
    from schematron import _rules_trees
    return {element.get("id") for _source, root in _rules_trees(path, text)[1:]
            for element in root.iter() if element.get("id")}


def _located(issues, root, path, text):
    """Les erreurs RELAX NG, sans les références à un identifiant d'un
    fichier inclus, et chaque référence inconnue à la ligne de son élément
    (libxml2 ne la situe pas)."""
    included = None
    for issue in issues:
        match = _IDREF.search(issue.message)
        if match is None:
            yield issue
            continue
        attribute, value = match.groups()
        if included is None:
            included = _included_ids(path, text)
        if value in included:
            continue
        if not issue.line:
            line = next((element.sourceline for element in root.iter()
                         if value in (element.get(attribute) or "").split()), 0)
            issue = replace(issue, line=line or 0)
        yield issue


def _missing_includes(root, path):
    """Une erreur des règles par ``sch:include`` dont le fichier manque."""
    from schematron import _rule_error
    for include in root.iter(f"{{{SCH_NS}}}include"):
        href = include.get("href") or ""
        dependency = _dependency_path(path.parent, href)
        if dependency is not None and not dependency.is_file():
            yield _rule_error("missing", href, path, include.sourceline or 0)


def check(text, path) -> ValidationResult:
    """Vérifie le texte *text* du fichier Schematron *path* (voir le
    module)."""
    path = Path(path).expanduser().resolve()
    result, root = _checked(text, ISO_SCHEMA, path)
    if root is None:                          # mal formé, ou schéma livré illisible
        return result
    issues = list(_located(result.issues, root, path, text))
    missing = list(_missing_includes(root, path))
    issues += missing
    saxon_error = ""
    if not missing:
        from schematron import check_compilation
        compiled = check_compilation(text, path)
        if compiled is None:
            saxon_error = "saxon_missing"
        else:
            issues += compiled
    return replace(result, valid=not any(issue.level == "ERROR" for issue in issues), issues=tuple(issues),
                   schematron_error=saxon_error)
