# -*- coding: utf-8 -*-
"""Moteurs des scénarios de transformation XSLT (V0.9.2.0), sans Qt.

``run(request)`` exécute la requête préparée par
``xslt_scenarios.scenario_request`` et rend un ``TransformResult`` : c'est
ce que fait, dans un processus à part, ``transform_worker``. Les moteurs
suivent un même contrat :

- **moteur** : ``lxml`` (XSLT 1.0) ;
- **entrée** : le fichier source lu avec son URI de base, ou l'édition
  assemblée par XInclude (``xml_assembly``), chaque partie gardant la
  sienne ; les entités externes ne sont pas résolues ;
- **paramètres** : des chaînes ; Saxon les reçoit sans type
  (``xs:untypedAtomic``, V0.9.2.7), comme sur sa ligne de commande ;
- **lecture** : tout fichier local, et ``http``/``https`` par un résolveur
  de Varians (délai ``NETWORK_TIMEOUT``, journal ``network_read``) ; une
  lecture réseau impossible arrête l'exécution ;
- **écriture** : le résultat, seulement si la transformation réussit, de
  façon atomique (un échec laisse le précédent intact), puis la CSS copiée
  à côté de lui ; jamais un fichier protégé (``request["protected"]`` : les
  sources du projet et du scénario). lxml refuse ``exsl:document``.

Paquets (V0.9.2.7, Saxon, ``request["package"]``, voir ``xslt_packages``) :
``pages`` écrit ``index.html`` et ses pages dans le dossier du résultat ;
``docx``, ``odt`` et ``epub`` font l'archive d'un dossier de travail
temporaire, préparé avant (``package_template``, ``package_fixstyle``,
images), où seule la feuille écrit, et qui devient le résultat. Un
pré-passage (``request["prepare"]``, Saxon) transforme d'abord la source
(TEI → TEI) avec les mêmes paramètres.

Journal : liste de ``[code, détail]`` (messages ``transform.journal.<code>``) :
``library`` (la bibliothèque employée, ``request["library"]`` : « TEI
Stylesheets 7.61.0 »), ``message`` (``xsl:message``), ``warning``,
``network_read``, ``css_copied``, ``write_refused``, ``assembly`` (problème
d'assemblage), ``image_skipped`` (image distante ou absente d'un paquet).

Catalogues (V0.9.2.2) : Saxon lit les adresses de ``request["catalogs"]``
(catalogues XML, celui des TEI Stylesheets) à la compilation, pour exécuter
comme pour vérifier : une feuille qui importe l'adresse officielle des TEI
Stylesheets les lit dans la bibliothèque installée, sans réseau.
Échec : ``error_code`` (message ``transform.error.<code>``) et ``error``,
le texte du moteur au format « fichier:ligne: message ».

``check(request)`` (V0.9.2.1, ``request["op"] == "check"``) compile la
feuille ``xslt`` sans l'exécuter : le texte ``text`` s'il est donné (celui
de l'éditeur, même non enregistré), lu avec l'URI de base du fichier, sinon
le fichier. Le compte rendu donne toutes les erreurs et tous les
avertissements dans ``issues`` : ``[fichier, ligne, niveau, message]``
(niveau ``error`` ou ``warning``, ligne 0 si elle est inconnue) ; une
feuille qui n'est pas un XML bien formé a le code ``xslt_malformed``.
"""
from __future__ import annotations

import contextlib
import os
import re
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field
from pathlib import Path

import xslt_packages

NETWORK_TIMEOUT = 30
# Codes d'échec (``transform.error.<code>``) et du journal
# (``transform.journal.<code>``) ; cancelled et worker_failed viennent du
# client du processus (transform_runner).
ERROR_CODES = ("unknown_engine", "saxon_missing", "source_missing", "source_malformed", "xslt_missing",
               "xslt_malformed", "xslt_invalid", "transform_failed", "network_failed", "write_refused",
               "output_failed", "internal", "worker_failed", "cancelled")
JOURNAL_CODES = ("library", "message", "warning", "network_read", "css_copied", "write_refused", "assembly",
                 "image_skipped")


@dataclass
class TransformResult:
    """Compte rendu d'une exécution : fichiers écrits (le résultat d'abord),
    journal, erreur éventuelle, moteur et sa version, durée en secondes."""
    ok: bool
    outputs: list = field(default_factory=list)
    journal: list = field(default_factory=list)
    error_code: str = ""
    error: str = ""
    engine: str = ""
    version: str = ""
    seconds: float = 0.0
    # Vérification d'une feuille (check) : [fichier, ligne, niveau, message].
    issues: list = field(default_factory=list)

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(bool(data["ok"]), [str(path) for path in data.get("outputs", ())],
                   [[str(code), str(detail)] for code, detail in data.get("journal", ())],
                   str(data.get("error_code", "")), str(data.get("error", "")), str(data.get("engine", "")),
                   str(data.get("version", "")), float(data.get("seconds", 0.0)),
                   [[str(file), int(line), str(level), str(message)]
                    for file, line, level, message in data.get("issues", ())])


class TransformError(Exception):
    """Échec d'une exécution : ``code`` et texte du moteur."""

    def __init__(self, code, detail=""):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def xslt_error_text(exc, xsl_path, log=()):
    """Message d'erreur lxml au format « fichier:ligne: message »."""
    default_name = Path(xsl_path).name
    parts = [f"{default_name}: {str(exc).strip() or type(exc).__name__}"]
    for entry in list(log or [])[:3]:
        filename = str(entry.filename or "")
        name = Path(filename).name if filename and not filename.startswith("<") else default_name
        detail = f"{name}:{entry.line}: {entry.message}" if entry.line else f"{name}: {entry.message}"
        if entry.message and detail not in parts and entry.message not in parts[0]:
            parts.append(detail)
    return " ; ".join(parts)


def source_tree(path):
    """L'arbre lxml du fichier source d'un scénario : sans résoudre les
    entités ni lire le réseau ; un document très imbriqué est lu (huge_tree,
    red team 2, A10)."""
    from lxml import etree
    return etree.parse(str(path), etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True))


def run(request) -> TransformResult:
    """Exécute une requête de ``xslt_scenarios.scenario_request``."""
    start = time.perf_counter()
    engine = request.get("engine")
    result = TransformResult(False, engine=str(engine))
    try:
        if engine not in _ENGINES:
            raise TransformError("unknown_engine", str(engine))
        version, transform = _ENGINES[engine]
        result.version = version()
        if request.get("library"):
            result.journal.append(["library", str(request["library"])])
        data, extra = transform(request, result.journal)
        result.outputs = _write_outputs(request, data, extra, result.journal)
        result.ok = True
    except TransformError as exc:
        result.error_code, result.error = exc.code, exc.detail
    except Exception as exc:                      # le processus répond toujours
        result.error_code, result.error = "internal", f"{type(exc).__name__}: {exc}"
    result.seconds = round(time.perf_counter() - start, 3)
    return result


def check(request) -> TransformResult:
    """Compile la feuille de ``request`` sans l'exécuter (voir la docstring
    du module)."""
    start = time.perf_counter()
    engine = request.get("engine")
    result = TransformResult(False, engine=str(engine))
    try:
        if engine not in _CHECKS:
            raise TransformError("unknown_engine", str(engine))
        version, compile_only = _CHECKS[engine]
        result.version = version()
        compile_only(request, result.issues)
        errors = [issue for issue in result.issues if issue[2] == "error"]
        if errors:
            file, line, _level, message = errors[0]
            result.error_code = "xslt_invalid"
            result.error = f"{Path(file).name}:{line}: {message}" if line else f"{Path(file).name}: {message}"
        else:
            result.ok = True
    except TransformError as exc:                 # les erreurs déjà relevées restent
        result.error_code, result.error = exc.code, exc.detail
    except Exception as exc:                      # le processus répond toujours
        result.error_code, result.error = "internal", f"{type(exc).__name__}: {exc}"
    result.seconds = round(time.perf_counter() - start, 3)
    return result


def _issue(issues, file, line, level, message):
    """Ajoute ``[fichier, ligne, niveau, message]`` à ``issues``, sauf doublon
    (le même message sans lieu, quand il est déjà là avec le sien)."""
    issue = [str(file), int(line or 0), level, " ".join(str(message).split())]
    if not issue[3] or issue in issues:
        return
    same = [other for other in issues if other[2:] == issue[2:]]
    if issue[1] == 0 and any(other[1] for other in same):
        return
    for other in same:
        if other[1] == 0:
            issues.remove(other)
    issues.append(issue)


# --- Écriture -------------------------------------------------------------------------------

def _path_key(path):
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _inside(path, folder):
    path, folder = _path_key(path), _path_key(folder)
    return path.startswith(folder.rstrip(os.sep) + os.sep)


def _write_atomically(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    handle, temp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(handle, "wb") as stream:
            stream.write(data)
        os.replace(temp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(temp)
        raise


def _write_outputs(request, data, extra, journal):
    """Écrit le résultat, les autres fichiers du moteur (dans le dossier du
    résultat seulement) et la copie de la CSS ; rend les chemins écrits."""
    protected = {_path_key(path) for path in request.get("protected", ())}
    output = Path(request["output"])
    if _path_key(output) in protected:
        raise TransformError("write_refused", str(output))
    written = []
    try:
        _write_atomically(output, data)
        written.append(str(output))
        for path, content in extra:
            path = Path(path)
            if not _inside(path, output.parent) or _path_key(path) in protected:
                journal.append(["write_refused", str(path)])
                continue
            _write_atomically(path, content)
            written.append(str(path))
        css = Path(request["css"]) if request.get("css") else None
        if css is not None:
            copy = output.parent / css.name
            if _path_key(copy) in protected and _path_key(copy) != _path_key(css):
                journal.append(["write_refused", str(copy)])
            elif _path_key(copy) != _path_key(css):
                _write_atomically(copy, css.read_bytes())
                written.append(str(copy))
                journal.append(["css_copied", str(copy)])
    except OSError as exc:
        raise TransformError("output_failed", f"{exc.filename or output}: {exc.strerror or exc}") from exc
    return written


# --- lxml (XSLT 1.0) ------------------------------------------------------------------------

def _lxml_version():
    from lxml import etree
    lxml = ".".join(map(str, etree.LXML_VERSION[:3]))
    return f"lxml {lxml} (libxslt {'.'.join(map(str, etree.LIBXSLT_VERSION))})"


class _NetworkReadError(Exception):
    pass


def _network_resolver(journal, failures, allowed=True):
    """Résolveur lxml des URL http(s) : lecture notée au journal ; un échec
    est gardé dans ``failures`` et arrête l'exécution. Sans *allowed*
    (vérification d'une feuille, red team B5), toute lecture réseau est
    refusée."""
    from lxml import etree

    class NetworkResolver(etree.Resolver):
        def resolve(self, url, pubid, context):
            if not url.lower().startswith(("http://", "https://")):
                return None
            if not allowed:
                failures.append(f"{url}: réseau non consulté pendant la vérification")
                raise _NetworkReadError(url)
            journal.append(["network_read", url])
            try:
                with urllib.request.urlopen(url, timeout=NETWORK_TIMEOUT) as response:
                    data = response.read()
            except Exception as exc:
                failures.append(f"{url}: {getattr(exc, 'reason', None) or exc}")
                raise _NetworkReadError(url) from exc
            return self.resolve_string(data, context, base_url=url)

    return NetworkResolver()


def _syntax_text(exc, path):
    name = Path(exc.filename or path).name
    return f"{name}:{exc.lineno}: {exc.msg}" if exc.lineno else f"{name}: {exc.msg}"


def _assembled_tree(path, journal):
    """L'édition ``path`` assemblée par XInclude (arbre lxml) ; chaque partie
    garde son URI de base. Les problèmes d'assemblage vont au journal."""
    from xml_assembly import assemble
    try:
        text = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        raise TransformError("source_missing", f"{path}: {exc}") from exc
    assembly = assemble(text, path)
    problems = [f"{Path(p.file).name}:{p.line}: {p.code}" + (f" ({p.detail})" if p.detail else "")
                for p in assembly.problems]
    if assembly.root is None:
        raise TransformError("source_malformed", " ; ".join(problems))
    journal.extend(["assembly", problem] for problem in problems)
    return assembly.root.getroottree()


def _lxml_source(request, parser, journal):
    from lxml import etree
    path = request["source"]
    if request.get("assemble"):
        return _assembled_tree(path, journal)
    try:
        return etree.parse(path, parser)
    except etree.XMLSyntaxError as exc:
        raise TransformError("source_malformed", _syntax_text(exc, path)) from exc
    except OSError as exc:
        raise TransformError("source_missing", f"{path}: {exc}") from exc


def _located(entry):
    """Vrai pour une entrée du journal lxml qui nomme un fichier et une ligne
    (erreur ou avertissement) ; un ``xsl:message`` n'en nomme pas."""
    return bool(entry.filename and not entry.filename.startswith("<") and entry.line)


def _journal_log(log, journal, skip=""):
    """``xsl:message`` et avertissements d'une exécution lxml ; ``skip`` :
    le message de l'erreur, déjà dans son texte."""
    for entry in log:
        if not entry.message or entry.message.strip() == skip:
            continue
        if _located(entry):
            journal.append(["warning", f"{Path(entry.filename).name}:{entry.line}: {entry.message}"])
        else:
            journal.append(["message", entry.message])


def _run_lxml(request, journal):
    from lxml import etree
    failures = []
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    parser.resolvers.add(_network_resolver(journal, failures))
    xslt = request["xslt"]
    try:
        source = _lxml_source(request, parser, journal)
        try:
            stylesheet = etree.parse(xslt, parser)
        except etree.XMLSyntaxError as exc:
            raise TransformError("xslt_invalid", _syntax_text(exc, xslt)) from exc
        except OSError as exc:
            raise TransformError("xslt_missing", f"{xslt}: {exc}") from exc
        # Lire partout, réseau compris (par le résolveur) ; n'écrire nulle part.
        access = etree.XSLTAccessControl(read_file=True, write_file=False, create_dir=False,
                                         read_network=True, write_network=False)
        try:
            transform = etree.XSLT(stylesheet, access_control=access)
        except etree.XSLTParseError as exc:
            raise TransformError("xslt_invalid", xslt_error_text(exc, xslt, exc.error_log)) from exc
        params = {str(name): etree.XSLT.strparam(str(value)) for name, value in request.get("params", ())}
        try:
            result = transform(source, **params)
        except etree.XSLTApplyError as exc:
            # Le texte de l'erreur garde ses lieux (fichier:ligne) ; les
            # xsl:message qui l'ont précédée vont au journal.
            located = [entry for entry in exc.error_log if _located(entry)]
            _journal_log([entry for entry in exc.error_log if not _located(entry)], journal, str(exc).strip())
            text = xslt_error_text(exc, xslt, located)
            refused = "write rights" in str(exc) or any("refused" in (e.message or "") for e in exc.error_log)
            raise TransformError("write_refused" if refused else "transform_failed", text) from exc
        _journal_log(transform.error_log, journal)
        return bytes(result), []
    except TransformError:
        if failures:
            raise TransformError("network_failed", failures[0]) from None
        raise
    except Exception:
        if failures:
            raise TransformError("network_failed", failures[0]) from None
        raise


def _lxml_file(entry, xslt):
    """Fichier d'une entrée du journal lxml (la feuille si elle n'en a pas)."""
    filename = str(entry.filename or "")
    if not filename or filename.startswith("<"):
        return str(xslt)
    if filename.startswith("file:"):
        return str(_uri_path(filename) or filename)
    return filename


def _check_lxml(request, issues):
    from lxml import etree
    failures = []
    parser = etree.XMLParser(resolve_entities=False, no_network=True, huge_tree=True)
    parser.resolvers.add(_network_resolver([], failures, allowed=False))
    xslt = Path(request["xslt"])
    text = request.get("text")
    # Le journal d'erreurs de libxslt garde celles des compilations
    # précédentes du même fil.
    etree.clear_error_log()
    try:
        if text is None:
            tree = etree.parse(str(xslt), parser)
        else:
            tree = etree.fromstring(text.encode("utf-8"), parser, base_url=str(xslt)).getroottree()
    except etree.XMLSyntaxError as exc:
        _issue(issues, xslt, exc.lineno, "error", exc.msg)
        raise TransformError("xslt_malformed", _syntax_text(exc, xslt)) from exc
    except OSError as exc:
        raise TransformError("xslt_missing", f"{xslt}: {exc}") from exc
    access = etree.XSLTAccessControl(read_file=True, write_file=False, create_dir=False,
                                     read_network=False, write_network=False)
    try:
        transform = etree.XSLT(tree, access_control=access)
    except _NetworkReadError:
        _issue(issues, xslt, 0, "error", failures[0])
        return
    except etree.XSLTParseError as exc:
        _lxml_issues(exc.error_log, xslt, issues)
        if not any(issue[2] == "error" for issue in issues):
            _issue(issues, xslt, 0, "error", failures[0] if failures else (str(exc) or type(exc).__name__))
        return
    _lxml_issues(transform.error_log, xslt, issues, failed=False)


def _lxml_issues(log, xslt, issues, failed=True):
    """Erreurs et avertissements d'une compilation lxml. libxslt écrit pour
    chaque erreur une entrée qui la situe (« compilation error, element
    'value-of' », avec fichier et ligne), suivie d'entrées sans lieu qui la
    décrivent : celles-ci forment le message. Après une compilation réussie
    (``failed`` faux), ce ne sont que des avertissements."""
    entries = list(log)
    compiled = not failed
    located = [index for index, entry in enumerate(entries) if _located(entry)]
    for rank, index in enumerate(located):
        entry = entries[index]
        end = located[rank + 1] if rank + 1 < len(located) else len(entries)
        details = [e.message.strip() for e in entries[index + 1:end]
                   if e.domain_name == "XSLT" and (e.message or "").strip() not in ("", "error")]
        level = "warning" if compiled or entry.level_name == "WARNING" else "error"
        _issue(issues, _lxml_file(entry, xslt), entry.line, level, " ; ".join(details) or entry.message)
    if not located:
        for entry in entries:
            message = (entry.message or "").strip()
            if message and message != "error":
                _issue(issues, _lxml_file(entry, xslt), 0,
                       "warning" if compiled or entry.level_name == "WARNING" else "error", message)


# --- Saxon (XSLT 3.0) -----------------------------------------------------------------------
#
# Saxon lit lui-même le réseau (sans journal des URL lues) ; les entités
# externes et la DTD externe ne sont pas lues. Il écrit ses messages d'erreur,
# avec leur lieu, sur la sortie d'erreur du processus : le processus de
# transformation la reçoit dans un fichier dès sa création
# (``request["stderr_log"]``, voir transform_worker), seule façon sûre de la
# lire sous Windows. Sans ce fichier, l'erreur garde le message de Saxon, sans
# son lieu.
#
# Les fichiers supplémentaires (xsl:result-document) : un premier passage les
# garde en mémoire, sans rien écrire, pour connaître leurs chemins. S'ils sont
# tous dans le dossier du résultat, un second passage les obtient mis en forme
# (fn:transform, résultats « serialized »), toujours en mémoire, et Varians
# écrit ceux qui sont dans ce dossier ; sinon, l'exécution est refusée. Saxon
# n'écrit jamais lui-même : une feuille qui changerait de comportement au
# second passage n'écrirait pas ailleurs pour autant (red team, B3). Le second
# passage n'a lieu que si la feuille produit d'autres fichiers.

_SAXON = None
_SAXON_LOCAL_ONLY = False         # saxon_without_network
# Processus de vérification d'une feuille (transform_worker, op « check ») :
# Saxon n'y lit que des fichiers locaux (red team, B5). Réglé par le
# processus, la restriction de Saxon valant pour tout le processus.
CHECKS_LOCAL_ONLY = False
_SAXON_PARSER_FEATURES = (
    "http%3A//xml.org/sax/features/external-general-entities",
    "http%3A//xml.org/sax/features/external-parameter-entities",
    "http%3A//apache.org/xml/features/nonvalidating/load-external-dtd",
)
_SAXON_LOCATION = re.compile(r"on line (\d+)(?: column \d+)? of (.+?):?\s*$")
_SAXON_NETWORK = re.compile(r"processing (https?://\S+)")


def _saxon_processor():
    """Le processeur Saxon du processus (un seul, comme le veut SaxonC)."""
    global _SAXON
    if _SAXON is None:
        try:
            from saxonche import PySaxonProcessor
        except ImportError as exc:
            raise TransformError("saxon_missing") from exc
        processor = PySaxonProcessor(license=False)
        for feature in _SAXON_PARSER_FEATURES:
            processor.set_configuration_property("http://saxon.sf.net/feature/parserFeature?uri=" + feature, "false")
        _SAXON = processor
    return _SAXON


def _saxon_version():
    return _saxon_processor().version.replace(" from Saxonica", "")


def saxon_without_network(processor):
    """Saxon ne lit plus que des fichiers locaux, pour tout le processus
    (red team, B5) : la vérification d'une feuille et les règles Schematron.
    Saxon évalue à la compilation les paramètres statiques et ``use-when`` :
    une feuille reçue pouvait y lire un fichier et l'envoyer dans une
    adresse web. La propriété reste acquise au processus : chaque
    vérification a le sien, les exécutions aussi ; ce sont ces processus qui
    la demandent (``CHECKS_LOCAL_ONLY``, ``schematron.LOCAL_ONLY``)."""
    global _SAXON_LOCAL_ONLY
    if not _SAXON_LOCAL_ONLY:
        processor.set_configuration_property("http://saxon.sf.net/feature/allowedProtocols", "file")
        _SAXON_LOCAL_ONLY = True


def _saxon_catalogs(processor, request):
    """Donne à Saxon les catalogues de la requête (ceux qui existent). Le
    processeur les garde : chaque exécution a son propre processus."""
    catalogs = [str(path) for path in request.get("catalogs") or () if Path(path).is_file()]
    if catalogs:
        processor.set_catalog_files(catalogs)


def _saxon_blocks(text):
    """Messages de Saxon : une ligne d'en-tête, puis des lignes en retrait."""
    blocks = []
    for line in text.splitlines():
        if line.strip() and not line[0].isspace():
            blocks.append([line.strip()])
        elif line.strip() and blocks:
            blocks[-1].append(line.strip())
    return blocks


def _saxon_block_text(block, default_name):
    """« fichier:ligne: CODE message » d'un message de Saxon."""
    header, detail = block[0], []
    for line in block[1:]:
        if detail and line.startswith(("In ", "at ")):
            break
        detail.append(line)
    message = " ".join(" ".join(detail).split()) or header
    match = _SAXON_LOCATION.search(header)
    if match:
        return f"{match.group(2).rsplit('/', 1)[-1]}:{match.group(1)}: {message}"
    return f"{default_name}: {message}"


def _saxon_failure(exc, stderr, xslt, code):
    """Erreur de Saxon : texte localisé (sortie d'erreur, sinon message de
    l'exception) ; une lecture réseau impossible a son propre code."""
    errors = [block for block in _saxon_blocks(stderr) if not block[0].startswith("Warning")]
    errors = errors or _saxon_blocks(str(exc).strip())
    text = (_saxon_block_text(errors[0], Path(xslt).name) if errors
            else f"{Path(xslt).name}: {' '.join(str(exc).split()) or type(exc).__name__}")
    network = _SAXON_NETWORK.search(stderr + " " + str(exc))
    return TransformError("network_failed" if network else code, text)


def _saxon_journal(executable, stderr, journal, xslt):
    messages = executable.get_xsl_messages()
    if messages is not None:
        journal.extend(["message", str(message)] for message in messages)
    executable.clear_xsl_messages()
    for block in _saxon_blocks(stderr):
        if block[0].startswith("Warning"):
            journal.append(["warning", _saxon_block_text(block, Path(xslt).name)])


# Encodage déclaré d'un fichier mis en forme : déclaration XML, sinon
# <meta charset> d'une page HTML ; UTF-8 par défaut.
_DECLARED_ENCODING = re.compile(r"""^\ufeff?<\?xml[^>]*?\bencoding\s*=\s*["']([A-Za-z0-9._-]+)""")
_META_CHARSET = re.compile(r"""<meta\b[^>]*?\bcharset\s*=\s*["']?([A-Za-z0-9._-]+)""", re.I)


def _encoded(text):
    """Les octets d'un fichier mis en forme par Saxon, dans l'encodage qu'il
    déclare ; un caractère que cet encodage n'a pas devient une référence."""
    match = _DECLARED_ENCODING.match(text) or _META_CHARSET.search(text[:4096])
    try:
        return text.encode(match.group(1) if match else "utf-8", errors="xmlcharrefreplace")
    except LookupError:
        return text.encode("utf-8")


def _serialized_results(processor, xslt, source, params, base):
    """Second passage : ``{uri: octets}`` des fichiers de la feuille, mis en
    forme comme Saxon les écrirait, sans rien écrire (``fn:transform``)."""
    xpath = processor.new_xpath_processor()
    xpath.declare_namespace("map", "http://www.w3.org/2005/xpath-functions/map")
    xpath.declare_namespace("xs", "http://www.w3.org/2001/XMLSchema")
    values = {"xslt": Path(xslt).as_uri(), "base": base.as_uri()}
    entries = []
    for number, (name, value) in enumerate(params.items()):
        namespace, _brace, local = name[1:].partition("}") if name.startswith("{") else ("", "", name)
        values.update({f"u{number}": namespace, f"n{number}": local, f"v{number}": value})
        entries.append(f"map{{QName($u{number}, $n{number}): xs:untypedAtomic($v{number})}}")
    for name, value in values.items():
        xpath.declare_variable(name)
        xpath.set_parameter(name, processor.make_string_value(value))
    xpath.declare_variable("source")
    xpath.set_parameter("source", source)
    results = xpath.evaluate_single(
        "transform(map{'stylesheet-location': $xslt, 'source-node': $source, 'base-output-uri': $base,"
        " 'delivery-format': 'serialized', 'stylesheet-params': map:merge((" + ", ".join(entries) + "))})")
    return {str(key.string_value): _encoded(results.get(key).head.string_value) for key in results.keys()}


def _refuse_result_documents(executable, journal):
    """Les fichiers qu'une feuille sans fichiers à écrire (pré-passage, styles
    d'un DOCX) a produits, gardés en mémoire : signalés, jamais écrits
    (red team, B4)."""
    for uri in executable.get_result_documents() or {}:
        journal.append(["write_refused", str(_uri_path(uri) or uri)])


def _uri_path(uri):
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(urllib.request.url2pathname(urllib.parse.unquote(parsed.path)))


def _run_saxon(request, journal):
    from saxonche import PySaxonApiError
    processor = _saxon_processor()
    _saxon_catalogs(processor, request)
    xslt, output = request["xslt"], Path(request["output"])
    package = request.get("package") or ""
    log = Path(request["stderr_log"]) if request.get("stderr_log") else None
    start = log.stat().st_size if log is not None and log.exists() else 0

    def stderr():
        """Ce que Saxon a écrit sur la sortie d'erreur depuis le début de l'exécution."""
        if log is None or not log.exists():
            return ""
        with open(log, "rb") as stream:
            stream.seek(start)
            return stream.read().decode("utf-8", errors="replace")

    with tempfile.TemporaryDirectory(prefix="varians-saxon-") as temp:
        temp = Path(temp).resolve()
        # Paquet (V0.9.2.7, ``xslt_packages``) : une archive est faite d'un
        # dossier de travail, dont la feuille reçoit l'adresse ; les pages
        # sont écrites dans le dossier du résultat, et le résultat principal,
        # sous un autre nom, ne gêne pas index.html.
        folder = temp / "paquet" if package in xslt_packages.ARCHIVES else None
        params = dict(xslt_packages.DEFAULT_PARAMS.get(package, ()))
        params.update((str(name), str(value)) for name, value in request.get("params", ()))
        if folder is not None:
            params[xslt_packages.FOLDER_PARAMS[package]] = folder.as_uri()
        allowed = folder if folder is not None else output.parent
        base = (folder / ".varians-principal.xml" if folder is not None
                else output.parent / f".varians-principal{output.suffix}" if package == "pages" else output)

        def compiled():
            # Une feuille compilée par passage : SaxonC plante si l'on
            # réutilise pour le second celle qui a gardé les fichiers.
            try:
                executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(xslt))
            except PySaxonApiError as exc:
                raise _saxon_failure(exc, stderr(), xslt, "xslt_invalid") from exc
            # Sans type (xs:untypedAtomic, V0.9.2.7), comme la ligne de
            # commande de Saxon : « false » convient à un paramètre
            # xs:boolean, « 3 » à un xs:integer, et reste une chaîne ailleurs.
            for name, value in params.items():
                executable.set_parameter(name, processor.make_atomic_value("untypedAtomic", value))
            executable.set_save_xsl_message(True)
            return executable

        def transform(executable, written, capture, base):
            executable.set_capture_result_documents(capture)
            executable.set_base_output_uri(base.as_uri())
            written.parent.mkdir(exist_ok=True)
            try:
                executable.transform_to_file(xdm_node=source, output_file=str(written))
            except PySaxonApiError as exc:
                _saxon_journal(executable, "", journal, xslt)
                raise _saxon_failure(exc, stderr(), xslt, "transform_failed") from exc

        def apply_xslt(stylesheet, document):
            """``stylesheet`` appliquée au fichier ``document`` (styles du DOCX)."""
            try:
                executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(stylesheet))
                executable.set_capture_result_documents(True)
                data = executable.transform_to_string(source_file=str(document)).encode("utf-8")
            except PySaxonApiError as exc:
                raise _saxon_failure(exc, stderr(), stylesheet, "transform_failed") from exc
            _refuse_result_documents(executable, journal)
            return data

        first = compiled()
        builder = processor.new_document_builder()
        builder.set_line_numbering(True)
        tree = None
        try:
            if request.get("assemble"):
                from lxml import etree
                tree = _assembled_tree(request["source"], journal)
                builder.set_base_uri(Path(request["source"]).as_uri())
                source = builder.parse_xml(xml_text=etree.tostring(tree, encoding="unicode"))
            else:
                source = builder.parse_xml(xml_file_name=str(request["source"]))
        except PySaxonApiError as exc:
            raise _saxon_failure(exc, stderr(), request["source"], "source_malformed") from exc
        if request.get("prepare"):
            # Pré-passage (V0.9.2.7) : une feuille TEI → TEI, avec les mêmes
            # paramètres ; son résultat garde l'URI de base de la source.
            prepare = request["prepare"]
            try:
                executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(prepare))
            except PySaxonApiError as exc:
                raise _saxon_failure(exc, stderr(), prepare, "xslt_invalid") from exc
            for name, value in params.items():
                executable.set_parameter(name, processor.make_atomic_value("untypedAtomic", value))
            executable.set_save_xsl_message(True)
            executable.set_capture_result_documents(True)
            try:
                prepared = executable.transform_to_string(xdm_node=source)
            except PySaxonApiError as exc:
                _saxon_journal(executable, "", journal, prepare)
                raise _saxon_failure(exc, stderr(), prepare, "transform_failed") from exc
            _saxon_journal(executable, "", journal, prepare)
            _refuse_result_documents(executable, journal)
            builder.set_base_uri(Path(request["source"]).as_uri())
            try:
                source = builder.parse_xml(xml_text=prepared)
            except PySaxonApiError as exc:
                raise _saxon_failure(exc, stderr(), prepare, "transform_failed") from exc
        if folder is not None:
            try:
                xslt_packages.prepare(package, folder, request.get("package_template"),
                                      request.get("package_fixstyle"), apply_xslt)
                if tree is None:
                    tree = source_tree(request["source"])
                xslt_packages.copy_images(package, tree.getroot(), request["source"], folder, journal)
            except xslt_packages.PackageError as exc:
                raise TransformError(exc.code, exc.detail) from exc
            except OSError as exc:
                raise TransformError("output_failed", f"{exc.filename or folder}: {exc.strerror or exc}") from exc

        # 1er passage : les autres fichiers sont gardés en mémoire, avec
        # leurs chemins dans le dossier du résultat (d'une archive : son
        # dossier de travail) ; rien n'est écrit là.
        main = temp / "premier" / output.name
        transform(first, main, True, base)
        uris = list(first.get_result_documents() or {})
        _saxon_journal(first, stderr(), journal, xslt)
        if not uris and folder is None:
            return main.read_bytes(), []
        wanted, refused = {}, []
        for uri in uris:
            path = _uri_path(uri)
            if path is not None and _inside(path, allowed):
                wanted[_path_key(path)] = path
            else:
                refused.append(str(path or uri))
        if refused:
            raise TransformError("write_refused", " ; ".join(sorted(refused)))
        # 2e passage : les fichiers mis en forme, en mémoire. Seuls ceux que
        # le premier passage a annoncés, dans le dossier permis, sont gardés.
        try:
            results = _serialized_results(processor, xslt, source, params, base)
        except PySaxonApiError as exc:
            raise _saxon_failure(exc, stderr(), xslt, "transform_failed") from exc
        data, extra = main.read_bytes(), []
        for uri, content in sorted(results.items()):
            path = _uri_path(uri)
            if path is not None and _path_key(path) == _path_key(base):
                continue                              # le résultat principal, déjà là
            if path is None or _path_key(path) not in wanted:
                journal.append(["write_refused", str(path or uri)])
            elif package == "pages" and _path_key(path) == _path_key(output):
                data = content                        # index.html, le résultat du scénario
            else:
                extra.append((path, content))
        if folder is not None:
            # Une archive : les fichiers vont dans son dossier de travail.
            try:
                for path, content in extra:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(content)
                return xslt_packages.finish(package, folder, data), []
            except OSError as exc:
                raise TransformError("output_failed", f"{exc.filename or folder}: {exc.strerror or exc}") from exc
        return data, extra

_CATALOG_NS = "{urn:oasis:names:tc:entity:xmlns:xml:catalog}"


def _catalog_rewrites(catalogs):
    """``(début d'adresse, préfixe local)`` des ``rewriteURI`` des catalogues :
    l'adresse officielle des TEI Stylesheets et leur dossier installé."""
    import xml.etree.ElementTree as ET
    rewrites = []
    for catalog in catalogs or ():
        try:
            root = ET.parse(catalog).getroot()
        except (OSError, ET.ParseError):
            continue
        for entry in root.iter(f"{_CATALOG_NS}rewriteURI"):
            start, prefix = entry.get("uriStartString"), entry.get("rewritePrefix")
            if start and prefix is not None:
                local = (Path(catalog).parent / prefix).resolve().as_uri()
                rewrites.append((start, local if local.endswith("/") or not start.endswith("/") else local + "/"))
    return rewrites


def _check_saxon(request, issues):
    from saxonche import PySaxonApiError
    processor = _saxon_processor()
    # Sans réseau (red team, B5) : les adresses que les catalogues renvoient
    # vers des fichiers installés (TEI Stylesheets) sont écrites directement
    # en fichiers, Saxon jugeant l'accès sur l'adresse d'origine. Le
    # catalogue est chargé avant : son chargement a besoin d'autres protocoles.
    _saxon_catalogs(processor, request)
    if CHECKS_LOCAL_ONLY:
        saxon_without_network(processor)
    xslt = Path(request["xslt"])
    log = Path(request["stderr_log"]) if request.get("stderr_log") else None
    start = log.stat().st_size if log is not None and log.exists() else 0

    def report(failure):
        # Sous Windows, les erreurs et leur lieu ne sont que sur la sortie
        # d'erreur ; ailleurs, aussi dans le message de l'exception.
        stderr = ""
        if log is not None and log.exists():
            with open(log, "rb") as stream:
                stream.seek(start)
                stderr = stream.read().decode("utf-8", errors="replace")
        for block in _saxon_blocks(stderr) + _saxon_blocks(failure):
            _saxon_issue(block, xslt, issues)
        if failure and not any(issue[2] == "error" for issue in issues):
            _issue(issues, xslt, 0, "error", failure)

    compiler = processor.new_xslt30_processor()
    node = None
    text = request.get("text")
    rewrites = _catalog_rewrites(request.get("catalogs"))
    if text is None and rewrites:
        try:
            text = xslt.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            text = None
    if text is not None:
        for official, local in rewrites:
            text = text.replace(official, local)
        builder = processor.new_document_builder()
        builder.set_line_numbering(True)
        builder.set_base_uri(xslt.resolve().as_uri())
        try:
            node = builder.parse_xml(xml_text=text)
        except PySaxonApiError as exc:
            report(str(exc).strip())
            raise TransformError("xslt_malformed", issues[0][3] if issues else str(exc)) from exc
    try:
        if node is None:
            compiler.compile_stylesheet(stylesheet_file=str(xslt))
        else:
            compiler.compile_stylesheet(stylesheet_node=node)
        report("")
    except PySaxonApiError as exc:
        report(str(exc).strip())


def _saxon_issue(block, xslt, issues):
    """Une erreur ou un avertissement de Saxon : fichier, ligne, message."""
    header = block[0]
    level = "warning" if header.startswith("Warning") else "error"
    detail = []
    for line in block[1:]:
        if detail and line.startswith(("In ", "at ")):
            break
        detail.append(line)
    message = " ".join(detail) or header
    match = _SAXON_LOCATION.search(header)
    if match is None:
        _issue(issues, xslt, 0, level, message)
        return
    # Saxon nomme le fichier par la fin de son URI.
    name = match.group(2)
    path = _uri_path(name) if name.startswith("file:") else None
    if path is None:
        name = name.rsplit("/", 1)[-1]
        sibling = xslt.parent / name
        path = xslt if name == xslt.name else (sibling if sibling.is_file() else name)
    _issue(issues, path, int(match.group(1)), level, message)


_ENGINES = {"lxml": (_lxml_version, _run_lxml), "saxon": (_saxon_version, _run_saxon)}
_CHECKS = {"lxml": (_lxml_version, _check_lxml), "saxon": (_saxon_version, _check_saxon)}
