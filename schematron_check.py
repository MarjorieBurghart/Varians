# -*- coding: utf-8 -*-
"""Vérification d'un fichier Schematron (V0.9.2.4), sans Qt.

``check(text, path)`` vérifie le texte *text* (celui de l'éditeur, même non
enregistré) du fichier Schematron *path* et rend un ``ValidationResult``,
comme la validation d'un document :

1. la bonne formation (erreurs du domaine ``PARSER``) ;
2. la structure, d'après le schéma ISO Schematron livré
   (``resources/schemas/schematron``, voir son LISEZMOI). Son modèle de
   complétion (``schematron_completion``) donne une erreur par élément
   non permis à sa place (code ``element``), attribut inconnu
   (``attribute``) ou attribut obligatoire absent (``required``), à sa
   ligne ; le message est « nom, tabulation, parent », tels qu'écrits dans
   le fichier. Les messages de libxml2, nombreux et en cascade pour ce
   schéma fait d'``interleave``, ne servent qu'en repli (domaine
   ``RELAXNGV``) : une référence (``IDREF``) à un identifiant d'un fichier
   inclus y est retirée, une référence inconnue donnée à la ligne de
   l'élément qui la porte. Un fichier inclus (racine ``sch:pattern``,
   ``sch:rule``…) n'est vérifié que de la première façon ;
3. les inclusions (``sch:include``) : un fichier absent est une erreur des
   règles (domaine ``SCHEMATRON_RULES``, code ``missing``) à la ligne de
   l'inclusion ;
4. la compilation par SchXslt2 et Saxon, toutes phases comprises
   (``schematron.check_compilation``), si les étapes précédentes n'ont
   trouvé aucune erreur et que la racine est ``sch:schema`` :
   l'assemblage des règles (code ``assembly`` : identifiant en double,
   phase qui cite un groupe absent…), puis chaque expression XPath
   (``xpath``), à sa ligne.

Sans Saxon, seules les étapes 1 à 3 sont faites et ``schematron_error``
vaut ``saxon_missing``. Le résultat est valide s'il n'a aucune erreur.
"""
from __future__ import annotations

import re
from dataclasses import replace
from pathlib import Path

from lxml import etree

from project_config import APPLICATION_ROOT
from relaxng_validation import ValidationResult, _checked, _dependency_path

ISO_SCHEMA = APPLICATION_ROOT / "resources" / "schemas" / "schematron" / "iso-schematron.rng"
SCH_NS = "http://purl.oclc.org/dsdl/schematron"
_IDREF = re.compile(r'IDREFS? attribute (\S+) references an unknown ID "([^"]*)"')
# Attributs obligatoires d'après le schéma ISO (le modèle de complétion ne
# les distingue pas) ; ``rule`` et ``extends`` sont traités à part.
_REQUIRED = {"active": ("pattern",), "assert": ("test",), "report": ("test",), "diagnostic": ("id",),
             "include": ("href",), "let": ("name",), "ns": ("prefix", "uri"), "param": ("name", "value"),
             "phase": ("id",), "property": ("id",), "span": ("class",), "value-of": ("select",)}


def _written(node):
    """Nom d'un élément tel qu'il est écrit (avec son préfixe)."""
    local = etree.QName(node).localname
    return f"{node.prefix}:{local}" if node.prefix else local


def _structure_errors(root, path):
    """Les erreurs de structure de l'arbre *root* (voir le module, étape 2)."""
    from schematron import _rule_error
    from schematron_completion import completion_model
    model = completion_model()
    errors = []

    def error(code, name, node, parent_name):
        errors.append(_rule_error(code, f"{name}\t{parent_name}", path, node.sourceline or 0))

    def check_attributes(node, local):
        written = _written(node)
        allowed = set(model.allowed_attributes(local))
        for name in node.attrib:
            qname = etree.QName(name)
            if qname.namespace == "http://www.w3.org/XML/1998/namespace":
                name = f"xml:{qname.localname}"
            elif qname.namespace:
                continue                                    # attribut étranger : permis
            if name not in allowed:
                error("attribute", name, node, written)
        if local == "rule":
            required = ("id",) if node.get("abstract") == "true" else ("context",)
        elif local == "extends":
            required = () if node.get("rule") is not None or node.get("href") is not None else ("rule",)
        else:
            required = _REQUIRED.get(local, ())
        for name in required:
            if node.get(name) is None:
                error("required", name, node, written)

    def visit(node):
        local = etree.QName(node).localname
        check_attributes(node, local)
        before = []
        for child in node:
            if not isinstance(child.tag, str) or etree.QName(child).namespace != SCH_NS:
                continue                                    # commentaire, élément étranger
            name = etree.QName(child).localname
            if name not in model.child_elements_at(local, tuple(before), ()):
                error("element", _written(child), child, _written(node))
                continue
            before.append(name)
            visit(child)

    if etree.QName(root).namespace != SCH_NS or etree.QName(root).localname not in model.children:
        namespace = etree.QName(root).namespace or "—"
        error("element", f"{_written(root)} ({namespace})", root, "/")          # racine inconnue
    else:
        visit(root)
    return errors


def _included_ids(path, text, texts=None):
    """Les identifiants définis dans les fichiers que *text* inclut (lus
    dans leur texte non enregistré si *texts* le donne)."""
    from schematron import _rules_trees
    return {element.get("id") for _source, root in _rules_trees(path, text, texts)[1:]
            for element in root.iter() if element.get("id")}


def _located(issues, root, path, text, texts=None):
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
            included = _included_ids(path, text, texts)
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


def check(text, path, texts=None) -> ValidationResult:
    """Vérifie le texte *text* du fichier Schematron *path* (voir le
    module) ; *texts* (V0.9.2.6) : ``{chemin: texte}`` des fichiers inclus
    ouverts et non enregistrés, lus à la place du disque."""
    from schematron import _unsaved, _unsaved_malformed
    path = Path(path).expanduser().resolve()
    result, root = _checked(text, None, path)
    if root is None:                          # mal formé
        return result
    issues = _structure_errors(root, path)
    whole = etree.QName(root).localname == "schema"
    if whole and not issues:
        relaxng, _tree = _checked(text, ISO_SCHEMA, path)
        issues = list(_located(relaxng.issues, root, path, text, texts))
    issues += _missing_includes(root, path)
    malformed = _unsaved_malformed(path, _unsaved(path, text, texts))
    if malformed is not None:
        issues.append(malformed)
    saxon_error = ""
    if whole and not issues:
        from schematron import check_compilation
        compiled = check_compilation(text, path, texts)
        if compiled is None:
            saxon_error = "saxon_missing"
        else:
            issues += compiled
    return replace(result, valid=not any(issue.level == "ERROR" for issue in issues), issues=tuple(issues),
                   schematron_error=saxon_error)
