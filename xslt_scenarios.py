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
fournies avec Varians ; ``stylesheet_path`` est la seule fonction qui trouve
la feuille d'un scénario.

TEI Stylesheets (V0.9.2.2) : ``${tei}/…`` désigne un fichier de la version
active des feuilles du TEI-C (``tei_stylesheets``), installée au premier
usage depuis l'archive livrée (``tei_library``) ; sans elle, un scénario qui
l'emploie a le problème ``tei_missing``. Quatre scénarios prédéfinis
« TEI : … » publient l'édition avec Saxon. La requête d'un scénario Saxon,
comme celle de la vérification d'une feuille (``check_request``), porte le
catalogue de la bibliothèque (``catalogs``) : une feuille de
personnalisation qui importe l'adresse officielle des feuilles
(``tei_stylesheets.OFFICIAL_URI``) est lue sans réseau. Si la feuille
emploie la bibliothèque, ``library`` la nomme pour le journal.
``customization_name`` et ``customization_text`` font la feuille de
personnalisation que crée « Ouvrir la feuille » pour un scénario TEI.

Feuilles éditées dans Varians (V0.9.2.1) : ``stylesheet_info`` reconnaît une
feuille XSLT à sa racine ; ``check_engines`` donne les moteurs qui la
vérifient (``xslt_engines.check``).
"""
from __future__ import annotations

import importlib.util
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

import tei_stylesheets
from project_config import DEFAULT_APPLICATION_XSLT, TransformScenario
from project_management import portable_path
from xml_assembly import assemble, path_key
from xml_roots import root_tag

VARIANS_STYLESHEETS = DEFAULT_APPLICATION_XSLT.parent
VARIANS_PREFIX = "${varians}/"
TEI_PREFIX = "${tei}/"
SOURCES = ("edition", "current", "file")
ENGINES = ("lxml", "saxon")
PROBLEM_CODES = ("unknown_source", "no_file", "file_missing", "no_current", "unknown_engine", "saxon_missing",
                 "no_xslt", "xslt_missing", "css_missing", "no_output", "output_is_folder", "output_is_source",
                 "css_overwrites_source", "tei_missing")


@dataclass(frozen=True)
class ScenarioProblem:
    """Ce qui empêche un scénario de s'exécuter.

    ``code`` (message ``transform.problem.<code>``) : ``unknown_source``,
    ``no_file``, ``file_missing``, ``no_current``, ``unknown_engine``,
    ``saxon_missing``, ``no_xslt``, ``xslt_missing``, ``css_missing``,
    ``no_output``, ``output_is_folder``, ``output_is_source``,
    ``css_overwrites_source``, ``tei_missing`` (TEI Stylesheets non
    installées : le dossier de la bibliothèque). ``detail`` : la valeur ou le
    chemin en cause, tel qu'il est écrit dans le scénario ou relatif au
    projet."""
    code: str
    detail: str = ""


XSL_NAMESPACE = "http://www.w3.org/1999/XSL/Transform"
_XSLT_ROOTS = ("stylesheet", "transform", "package")


@dataclass(frozen=True)
class StylesheetInfo:
    """Ce qu'on lit à la racine d'une feuille XSLT : le préfixe lié à
    l'espace de noms XSLT (``""`` s'il est l'espace de noms par défaut), la
    version (``""`` si elle manque) et le nom de la racine."""
    prefix: str
    version: str
    root: str


def stylesheet_info(text) -> StylesheetInfo | None:
    """La racine de ``text`` si c'est une feuille XSLT, sinon None : un
    ``stylesheet``, ``transform`` ou ``package`` de l'espace de noms XSLT, ou
    un élément résultat littéral qui porte ``xsl:version``."""
    tag = root_tag(text)
    if tag is None:
        return None
    root, attributes = tag
    prefixes = [name[6:] if name.startswith("xmlns:") else "" for name, value in attributes.items()
                if value == XSL_NAMESPACE and (name == "xmlns" or name.startswith("xmlns:"))]
    prefix, _colon, local = root.rpartition(":")
    if prefix in prefixes and local in _XSLT_ROOTS:
        return StylesheetInfo(prefix, attributes.get("version", ""), root)
    for xsl in prefixes:
        if xsl and f"{xsl}:version" in attributes and prefix != xsl:
            return StylesheetInfo(xsl, attributes[f"{xsl}:version"], root)
    return None


def check_engines(path, project, text=None) -> tuple[str, ...]:
    """Moteurs qui vérifient la feuille ``path`` : ceux des scénarios du
    projet qui l'emploient, chacun une fois ; sinon d'après sa version
    (``1.0`` : lxml, une autre : Saxon)."""
    key = path_key(path)
    engines = []
    for scenario in project.transformations:
        stylesheet = stylesheet_path(scenario, project)
        if (stylesheet is not None and path_key(stylesheet) == key and scenario.engine in ENGINES
                and scenario.engine not in engines):
            engines.append(scenario.engine)
    if engines:
        return tuple(engines)
    if text is None:
        try:
            text = Path(path).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            text = ""
    info = stylesheet_info(text)
    return ("lxml",) if info is not None and info.version.strip() == "1.0" else ("saxon",)


def saxon_available() -> bool:
    """Vrai si Saxon (paquet ``saxonche``) est installé ; il n'est pas chargé."""
    return importlib.util.find_spec("saxonche") is not None


def tei_library():
    """La version active des TEI Stylesheets (``tei_stylesheets.Installed``),
    installée au premier usage depuis l'archive livrée ; None si elles
    manquent."""
    return tei_stylesheets.ensure_installed()


def _uses_tei(raw) -> bool:
    return (raw or "").strip().startswith(TEI_PREFIX)


def resolve_path(project, raw) -> Path | None:
    """Chemin absolu d'un chemin de scénario, ou None s'il est vide. Sans TEI
    Stylesheets, un chemin ``${tei}/…`` désigne un fichier absent."""
    raw = (raw or "").strip()
    if not raw:
        return None
    if raw.startswith(VARIANS_PREFIX):
        return (VARIANS_STYLESHEETS / raw[len(VARIANS_PREFIX):]).resolve()
    if raw.startswith(TEI_PREFIX):
        library = tei_library()
        folder = library.folder if library is not None else tei_stylesheets.library_dir()
        return (folder / raw[len(TEI_PREFIX):]).resolve()
    path = Path(raw).expanduser()
    return path.resolve() if path.is_absolute() else (project.root_dir / path).resolve()


def scenario_path(project, path) -> str:
    """Chemin à écrire dans un scénario pour le fichier ``path`` : relatif au
    projet, sinon ``${varians}/…`` pour une feuille de Varians, ``${tei}/…``
    pour un fichier d'une version installée des TEI Stylesheets, sinon
    absolu."""
    path = Path(path).expanduser().resolve()
    for folder, prefix in ((project.root_dir, ""), (VARIANS_STYLESHEETS, VARIANS_PREFIX)):
        try:
            return prefix + path.relative_to(Path(folder).resolve()).as_posix()
        except ValueError:
            continue
    try:
        version, *rest = path.relative_to(tei_stylesheets.library_dir().resolve()).parts
    except ValueError:
        version, rest = "", []
    if rest and tei_stylesheets.parse_version(version) is not None:
        return TEI_PREFIX + "/".join(rest)
    return path.as_posix()


def stylesheet_path(scenario, project) -> Path | None:
    """La feuille XSLT du scénario."""
    return resolve_path(project, scenario.xslt)


# Scénarios TEI : clé, dossier du profil des TEI Stylesheets, extension du résultat.
TEI_SCENARIOS = (("tei-html", "html", "html"), ("tei-txt", "txt", "txt"), ("tei-markdown", "markdown", "md"),
                 ("tei-latex", "latex", "tex"))


def predefined_scenarios(translate=None, language=None) -> tuple[TransformScenario, ...]:
    """Scénarios fournis par Varians, non écrits dans project.xml : l'édition
    HTML de Varians, puis les scénarios « TEI : … » (``TEI_SCENARIOS``).
    ``translate`` donne, dans la langue de l'interface, le nom d'après la clé
    du scénario, et le titre du sommaire d'après la clé ``toc`` (sinon : la
    clé, et « Contents » comme la feuille de Varians). ``language`` : code
    de la langue de l'interface, pour les textes qu'ajoutent les TEI
    Stylesheets (paramètres ``lang`` et ``documentationLanguage``)."""
    def name(key):
        return translate(key) if translate else key

    key = "varians-html"
    scenarios = [TransformScenario(name(key), VARIANS_PREFIX + "tei-to-html.xsl", "publications/edition.html",
                                   css=VARIANS_PREFIX + "tei.css",
                                   params=(("tocTitle", translate("toc") if translate else "Contents"),))]
    languages = (("lang", language), ("documentationLanguage", language)) if language else ()
    for key, profile, extension in TEI_SCENARIOS:
        css, params = "", languages
        if profile == "html":
            # La CSS des TEI Stylesheets, copiée à côté du résultat : aucun
            # lien vers tei-c.org, ni vers « / » (lien « Home »).
            css = TEI_PREFIX + "tei.css"
            params = (("cssFile", "tei.css"), ("cssPrintFile", ""), ("homeURL", "")) + languages
        scenarios.append(TransformScenario(name(key), f"{TEI_PREFIX}profiles/default/{profile}/to.xsl",
                                           f"publications/tei/edition.{extension}", engine="saxon", css=css,
                                           params=params))
    return tuple(scenarios)


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


def scenario_source(scenario, project, current=None):
    """``(source, assembler)`` du scénario ; source None si elle manque.
    ``current`` : le fichier du document affiché."""
    if scenario.source == "edition":
        return project.edition, True
    if scenario.source == "current":
        if current is None:
            return None, False
        return Path(current), path_key(current) == path_key(project.edition)
    return resolve_path(project, scenario.file), False


def _protected(scenario, project, current, sources):
    source, _assemble = scenario_source(scenario, project, current) if scenario.source in SOURCES else (None, False)
    paths = list(project_sources(project) if sources is None else sources)
    paths += [source, stylesheet_path(scenario, project), resolve_path(project, scenario.css)]
    return {path_key(path): Path(path) for path in paths if path}


def scenario_problems(scenario, project, current=None, sources=None) -> list[ScenarioProblem]:
    """Ce qui empêche le scénario de s'exécuter (liste vide : rien).
    ``current`` : le document affiché ; ``sources`` : ``project_sources``,
    s'il est déjà connu."""
    problems = []
    tei_missing = (_uses_tei(scenario.xslt) or _uses_tei(scenario.css)) and tei_library() is None
    if tei_missing:
        problems.append(ScenarioProblem("tei_missing", str(tei_stylesheets.library_dir())))
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
    elif not xslt.is_file() and not (tei_missing and _uses_tei(scenario.xslt)):
        problems.append(ScenarioProblem("xslt_missing", scenario.xslt))
    css = resolve_path(project, scenario.css)
    if css is not None and not css.is_file() and not (tei_missing and _uses_tei(scenario.css)):
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


PIVOT = "${pivot}"


def substitute(value, project) -> str:
    """*value*, la valeur d'un paramètre, où ``${pivot}`` (V0.9.2.7) devient
    l'identifiant du témoin pivot du projet."""
    return str(value).replace(PIVOT, project.base_witness or "")


def scenario_request(scenario, project, current=None, output_dir=None, sources=None) -> dict:
    """Requête d'exécution (sérialisable en JSON) d'un scénario sans
    problème : chemins absolus, paramètres (avec ``css``, le nom de la CSS,
    sauf si le scénario le fixe, et ``${pivot}`` remplacé par le témoin
    pivot, voir ``substitute``), fichiers protégés. ``output_dir`` :
    dossier où écrire le résultat à la place du sien (aperçu)."""
    source, assemble_source = scenario_source(scenario, project, current)
    css = resolve_path(project, scenario.css)
    output = resolve_path(project, scenario.output)
    if output_dir is not None:
        output = Path(output_dir) / output.name
    params = [[name, substitute(value, project)] for name, value in scenario.params]
    if css is not None and all(name != "css" for name, _value in scenario.params):
        params.append(["css", css.name])
    xslt = stylesheet_path(scenario, project)
    request = {
        "name": scenario.name,
        "engine": scenario.engine,
        "source": str(source),
        "assemble": assemble_source,
        "xslt": str(xslt),
        "css": str(css) if css is not None else None,
        "output": str(output),
        "params": params,
        "protected": sorted(str(path) for path in _protected(scenario, project, current, sources).values()),
    }
    if scenario.engine == "saxon":
        library = tei_library()
        if library is not None:
            request["catalogs"] = [str(library.catalog)]
            if _employs(xslt, library):
                request["library"] = f"TEI Stylesheets {library.version}"
    return request


def _employs(xslt, library) -> bool:
    """La feuille ``xslt`` est-elle une des TEI Stylesheets, ou en importe-t-elle
    une par leur adresse officielle ?"""
    if xslt is None:
        return False
    try:
        Path(xslt).resolve().relative_to(library.folder.resolve())
        return True
    except ValueError:
        pass
    try:
        return tei_stylesheets.OFFICIAL_URI in Path(xslt).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False


def check_request(engine, path, text=None) -> dict:
    """Requête de vérification de la feuille ``path`` par ``engine``
    (``xslt_engines.check``) ; ``text`` : son texte dans l'éditeur. Pour
    Saxon, le catalogue des TEI Stylesheets."""
    request = {"op": "check", "engine": engine, "xslt": str(path), "text": text}
    if engine == "saxon":
        library = tei_library()
        if library is not None:
            request["catalogs"] = [str(library.catalog)]
    return request


# --- Feuille de personnalisation des TEI Stylesheets (V0.9.2.2) --------------------------------

XHTML_NAMESPACE = "http://www.w3.org/1999/xhtml"
_PARAMETER_EXAMPLE = '<xsl:param name="numberHeadings">false</xsl:param>'
_TEMPLATE_EXAMPLES = {
    True: '<xsl:template match="tei:persName"><b><xsl:apply-templates/></b></xsl:template>',
    False: '<xsl:template match="tei:persName">[<xsl:apply-templates/>]</xsl:template>',
}


def _tei_parts(raw):
    raw = (raw or "").strip()
    return PurePosixPath(raw[len(TEI_PREFIX):] if raw.startswith(TEI_PREFIX) else Path(raw).name).parts


def customization_name(raw) -> str:
    """Nom de la feuille de personnalisation d'une feuille ``${tei}/…`` :
    ``tei-html.xsl`` pour ``profiles/default/html/to.xsl``,
    ``tei-<profil>-<format>.xsl`` pour un autre profil, sinon
    ``tei-<nom>.xsl``."""
    parts = _tei_parts(raw)
    if len(parts) == 4 and parts[0] == "profiles" and parts[3] == "to.xsl":
        words = parts[2:3] if parts[1] == "default" else parts[1:3]
    else:
        words = [PurePosixPath(*parts).stem] if parts else ["stylesheet"]
    return "tei-" + "-".join(words) + ".xsl"


_NO_LINE_START = "、。，．）」』：；！？"


def _width(text) -> int:
    return sum(2 if unicodedata.east_asian_width(char) in "WF" else 1 for char in text)


def _wrap(paragraph, width=76, indent="  ") -> list[str]:
    """Lignes d'au plus ``width`` colonnes (un caractère large en occupe
    deux) : coupure aux espaces, ou entre deux caractères larges, jamais
    avant une ponctuation comme « 。 »."""
    tokens = []
    for word in re.findall(r"\s+|\S+", " ".join(str(paragraph).split())):
        tokens += re.findall(r"[^\s\u1100-\uffff]+|.", word) if any(_width(c) == 2 for c in word) else [word]
    lines, line = [], ""
    for token in tokens:
        if line and not token.isspace() and _width(line + token) > width - len(indent) \
                and token[0] not in _NO_LINE_START:
            lines.append(line.rstrip())
            line = ""
        if line or not token.isspace():
            line += token
    if line.strip():
        lines.append(line.rstrip())
    return [indent + line for line in lines]


def _html_output(parts) -> bool:
    return "html" in parts[2:3] if len(parts) > 2 and parts[0] == "profiles" else "html" in parts[:1]


def customization_text(raw, comment="", examples="") -> str:
    """Texte d'une feuille de personnalisation de la feuille ``raw``
    (``${tei}/…``) : elle importe la feuille par l'adresse officielle des TEI
    Stylesheets, que le catalogue renvoie vers la bibliothèque installée.
    ``comment`` (paragraphes séparés par une ligne vide) et ``examples``
    (l'intitulé des exemples) : dans la langue de l'interface. Une sortie
    HTML a pour espace de noms par défaut celui du XHTML, comme les TEI
    Stylesheets : les éléments qu'on y ajoute sont du XHTML."""
    parts = _tei_parts(raw)
    html = _html_output(parts)
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', "<!--"]
    paragraphs = [p for p in str(comment or "").replace("--", "- -").split("\n\n") if p.strip()]
    for paragraph in paragraphs:
        lines += _wrap(paragraph)
        lines.append("")
    if examples:
        lines.append("  " + " ".join(str(examples).replace("--", "- -").split()))
    lines += ["    " + _PARAMETER_EXAMPLE, "    " + _TEMPLATE_EXAMPLES[html], "-->"]
    namespaces = f'\n    xmlns:tei="http://www.tei-c.org/ns/1.0"' + (f' xmlns="{XHTML_NAMESPACE}"' if html else "")
    lines += [f'<xsl:stylesheet version="3.0" xmlns:xsl="{XSL_NAMESPACE}"{namespaces}',
              '    exclude-result-prefixes="#all">',
              f'  <xsl:import href="{tei_stylesheets.OFFICIAL_URI}{"/".join(parts)}"/>',
              "</xsl:stylesheet>", ""]
    return "\n".join(lines)
