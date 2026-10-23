# -*- coding: utf-8 -*-
"""Scénarios de transformation XSLT (V0.9.2.0), sans Qt.

Un scénario (``project_config.TransformScenario``) nomme une source, une
feuille XSLT, un moteur, une CSS facultative et un résultat. Ce module
résout ses chemins, relève ce qui l'empêche de s'exécuter
(``scenario_problems``) et prépare la requête qu'exécute le processus de
transformation (``scenario_request``, puis ``xslt_engines.run``). Il ne lit
ni n'écrit de résultat.

Sources : ``edition`` (l'édition, assemblée par XInclude), ``current`` (le
document affiché ; l'édition, assemblée, si c'est elle) et ``file`` (un
fichier, lu tel quel).

Garde-fou : ni le résultat ni la copie de la CSS à côté de lui ne remplacent
une source du projet (``project_sources``) ou du scénario.

Les chemins qui commencent par ``${varians}/`` désignent les feuilles
fournies avec Varians : ``stylesheet_path`` est la seule fonction qui trouve
la feuille d'un scénario, pour qu'une bibliothèque installée hors du projet
(les TEI Stylesheets) puisse s'y ajouter.
"""
from __future__ import annotations

import importlib.util
from dataclasses import dataclass
from pathlib import Path

from project_config import DEFAULT_APPLICATION_XSLT, TransformScenario
from project_management import portable_path
from xml_assembly import assemble, path_key

VARIANS_STYLESHEETS = DEFAULT_APPLICATION_XSLT.parent
VARIANS_PREFIX = "${varians}/"
SOURCES = ("edition", "current", "file")
ENGINES = ("lxml", "saxon")


@dataclass(frozen=True)
class ScenarioProblem:
    """Ce qui empêche un scénario de s'exécuter.

    ``code`` (message ``transform.problem.<code>``) : ``unknown_source``,
    ``no_file``, ``file_missing``, ``no_current``, ``unknown_engine``,
    ``saxon_missing``, ``no_xslt``, ``xslt_missing``, ``css_missing``,
    ``no_output``, ``output_is_folder``, ``output_is_source``,
    ``css_overwrites_source``. ``detail`` : la valeur ou le chemin en cause,
    tel qu'il est écrit dans le scénario ou relatif au projet."""
    code: str
    detail: str = ""


def saxon_available() -> bool:
    """Vrai si Saxon (paquet ``saxonche``) est installé ; il n'est pas chargé."""
    return importlib.util.find_spec("saxonche") is not None


def resolve_path(project, raw) -> Path | None:
    """Chemin absolu d'un chemin de scénario, ou None s'il est vide."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith(VARIANS_PREFIX):
        return (VARIANS_STYLESHEETS / raw[len(VARIANS_PREFIX):]).resolve()
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (project.root_dir / path).resolve()


def stylesheet_path(scenario, project) -> Path | None:
    """La feuille XSLT du scénario."""
    return resolve_path(project, scenario.xslt)


def predefined_scenarios(translate=None) -> tuple[TransformScenario, ...]:
    """Scénarios fournis par Varians, non écrits dans project.xml. ``translate``
    donne le nom affiché d'après la clé du scénario (sinon, la clé)."""
    key = "varians-html"
    return (TransformScenario(translate(key) if translate else key, VARIANS_PREFIX + "tei-to-html.xsl",
                              "publications/edition.html", css=VARIANS_PREFIX + "tei.css"),)


def project_sources(project) -> list[Path]:
    """Fichiers que le résultat d'un scénario ne doit jamais remplacer :
    project.xml, l'édition et ses parties enregistrées, les documents, les
    feuilles et la CSS de l'aperçu, les schémas, les JSON d'alignement."""
    paths = [project.path, project.edition, project.xslt, project.css, project.custom_elements, project.schema]
    paths += edition_parts(project.edition)
    for document in project.documents:
        paths += [document.path, document.schema]
    paths += [witness.alignment for witness in project.witnesses]
    alignments = project.root_dir / "alignments"
    if alignments.is_dir():
        paths += sorted(alignments.rglob("*.json"))
    return [Path(path) for path in paths if path]


def edition_parts(edition) -> list[Path]:
    """Parties de l'édition enregistrée, dans l'ordre d'inclusion (aucune si
    elle ne peut pas être lue)."""
    try:
        text = Path(edition).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError):
        return []
    assembly = assemble(text, edition)
    return [] if assembly.root is None else list(assembly.parts)


def _source_path(scenario, project, current):
    """``(source, assembler)`` du scénario ; source None si elle manque."""
    if scenario.source == "edition":
        return project.edition, True
    if scenario.source == "current":
        if current is None:
            return None, False
        return Path(current), path_key(current) == path_key(project.edition)
    return resolve_path(project, scenario.file), False


def _protected(scenario, project, current, sources):
    source, _assemble = _source_path(scenario, project, current) if scenario.source in SOURCES else (None, False)
    paths = list(project_sources(project) if sources is None else sources)
    paths += [source, stylesheet_path(scenario, project), resolve_path(project, scenario.css)]
    return {path_key(path): Path(path) for path in paths if path}


def scenario_problems(scenario, project, current=None, sources=None) -> list[ScenarioProblem]:
    """Ce qui empêche le scénario de s'exécuter (liste vide : rien).
    ``current`` : le document affiché ; ``sources`` : ``project_sources``,
    s'il est déjà connu."""
    problems = []
    if scenario.source not in SOURCES:
        problems.append(ScenarioProblem("unknown_source", scenario.source))
    elif scenario.source == "file":
        if not scenario.file:
            problems.append(ScenarioProblem("no_file"))
        elif not resolve_path(project, scenario.file).is_file():
            problems.append(ScenarioProblem("file_missing", scenario.file))
    elif scenario.source == "current" and current is None:
        problems.append(ScenarioProblem("no_current"))
    if scenario.engine not in ENGINES:
        problems.append(ScenarioProblem("unknown_engine", scenario.engine))
    elif scenario.engine == "saxon" and not saxon_available():
        problems.append(ScenarioProblem("saxon_missing"))
    xslt = stylesheet_path(scenario, project)
    if xslt is None:
        problems.append(ScenarioProblem("no_xslt"))
    elif not xslt.is_file():
        problems.append(ScenarioProblem("xslt_missing", scenario.xslt))
    css = resolve_path(project, scenario.css)
    if css is not None and not css.is_file():
        problems.append(ScenarioProblem("css_missing", scenario.css))
    output = resolve_path(project, scenario.output)
    if output is None:
        problems.append(ScenarioProblem("no_output"))
    elif output.is_dir():
        problems.append(ScenarioProblem("output_is_folder", scenario.output))
    else:
        protected = _protected(scenario, project, current, sources)
        if path_key(output) in protected:
            problems.append(ScenarioProblem("output_is_source", scenario.output))
        elif css is not None and css.is_file():
            copy = output.parent / css.name
            if path_key(copy) != path_key(css) and path_key(copy) in protected:
                problems.append(ScenarioProblem("css_overwrites_source", portable_path(project.root_dir, copy)))
    return problems


def scenario_request(scenario, project, current=None, output_dir=None, sources=None) -> dict:
    """Requête d'exécution (sérialisable en JSON) d'un scénario sans
    problème : chemins absolus, paramètres (avec ``css``, le nom de la CSS,
    sauf si le scénario le fixe), fichiers protégés. ``output_dir`` :
    dossier où écrire le résultat à la place du sien (aperçu)."""
    source, assemble_source = _source_path(scenario, project, current)
    css = resolve_path(project, scenario.css)
    output = resolve_path(project, scenario.output)
    if output_dir is not None:
        output = Path(output_dir) / output.name
    params = [[name, value] for name, value in scenario.params]
    if css is not None and all(name != "css" for name, _value in scenario.params):
        params.append(["css", css.name])
    return {
        "name": scenario.name,
        "engine": scenario.engine,
        "source": str(source),
        "assemble": assemble_source,
        "xslt": str(stylesheet_path(scenario, project)),
        "css": str(css) if css is not None else None,
        "output": str(output),
        "params": params,
        "protected": sorted(str(path) for path in _protected(scenario, project, current, sources).values()),
    }
