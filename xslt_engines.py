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
- **paramètres** : des chaînes ;
- **lecture** : tout fichier local, et ``http``/``https`` par un résolveur
  de Varians (délai ``NETWORK_TIMEOUT``, journal ``network_read``) ; une
  lecture réseau impossible arrête l'exécution ;
- **écriture** : le résultat, seulement si la transformation réussit, de
  façon atomique (un échec laisse le précédent intact), puis la CSS copiée
  à côté de lui ; jamais un fichier protégé (``request["protected"]`` : les
  sources du projet et du scénario). lxml refuse ``exsl:document``.

Journal : liste de ``[code, détail]`` (messages ``transform.journal.<code>``) :
``message`` (``xsl:message``), ``warning``, ``network_read``,
``css_copied``, ``write_refused``, ``assembly`` (problème d'assemblage).
Échec : ``error_code`` (message ``transform.error.<code>``) et ``error``,
le texte du moteur au format « fichier:ligne: message ».
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

NETWORK_TIMEOUT = 30
# Codes d'échec (``transform.error.<code>``) et du journal
# (``transform.journal.<code>``) ; cancelled et worker_failed viennent du
# client du processus (transform_runner).
ERROR_CODES = ("unknown_engine", "saxon_missing", "source_missing", "source_malformed", "xslt_missing",
               "xslt_invalid", "transform_failed", "network_failed", "write_refused", "output_failed", "internal",
               "worker_failed", "cancelled")
JOURNAL_CODES = ("message", "warning", "network_read", "css_copied", "write_refused", "assembly")


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

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        return cls(bool(data["ok"]), [str(path) for path in data.get("outputs", ())],
                   [[str(code), str(detail)] for code, detail in data.get("journal", ())],
                   str(data.get("error_code", "")), str(data.get("error", "")), str(data.get("engine", "")),
                   str(data.get("version", "")), float(data.get("seconds", 0.0)))


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
        data, extra = transform(request, result.journal)
        result.outputs = _write_outputs(request, data, extra, result.journal)
        result.ok = True
    except TransformError as exc:
        result.error_code, result.error = exc.code, exc.detail
    except Exception as exc:                      # le processus répond toujours
        result.error_code, result.error = "internal", f"{type(exc).__name__}: {exc}"
    result.seconds = round(time.perf_counter() - start, 3)
    return result


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


def _network_resolver(journal, failures):
    """Résolveur lxml des URL http(s) : lecture notée au journal ; un échec
    est gardé dans ``failures`` et arrête l'exécution."""
    from lxml import etree

    class NetworkResolver(etree.Resolver):
        def resolve(self, url, pubid, context):
            if not url.lower().startswith(("http://", "https://")):
                return None
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
# tous dans le dossier du résultat, un second passage laisse Saxon les écrire,
# avec leur mise en forme exacte, dans un dossier temporaire ; sinon,
# l'exécution est refusée. Le second passage n'a lieu que si la feuille
# produit d'autres fichiers.

_SAXON = None
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


def _uri_path(uri):
    parsed = urllib.parse.urlparse(uri)
    if parsed.scheme != "file":
        return None
    return Path(urllib.request.url2pathname(urllib.parse.unquote(parsed.path)))


def _run_saxon(request, journal):
    from saxonche import PySaxonApiError
    processor = _saxon_processor()
    xslt, output = request["xslt"], Path(request["output"])
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
        temp = Path(temp)

        def compiled():
            # Une feuille compilée par passage : SaxonC plante si l'on
            # réutilise pour le second celle qui a gardé les fichiers.
            try:
                executable = processor.new_xslt30_processor().compile_stylesheet(stylesheet_file=str(xslt))
            except PySaxonApiError as exc:
                raise _saxon_failure(exc, stderr(), xslt, "xslt_invalid") from exc
            for name, value in request.get("params", ()):
                executable.set_parameter(str(name), processor.make_string_value(str(value)))
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

        first = compiled()
        builder = processor.new_document_builder()
        builder.set_line_numbering(True)
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

        # 1er passage : les autres fichiers sont gardés en mémoire, avec
        # leurs chemins dans le dossier du résultat ; rien n'est écrit là.
        main = temp / "premier" / output.name
        transform(first, main, True, output)
        uris = list(first.get_result_documents() or {})
        _saxon_journal(first, stderr(), journal, xslt)
        if not uris:
            return main.read_bytes(), []
        wanted, refused = {}, []
        for uri in uris:
            path = _uri_path(uri)
            if path is not None and _inside(path, output.parent):
                wanted[_path_key(path)] = path
            else:
                refused.append(str(path or uri))
        if refused:
            raise TransformError("write_refused", " ; ".join(sorted(refused)))
        # 2e passage : Saxon écrit les fichiers, avec leur mise en forme,
        # dans un dossier temporaire.
        second = temp / "second"
        main = second / output.name
        executable = compiled()
        transform(executable, main, False, main)
        executable.clear_xsl_messages()
        extra = []
        for path in sorted(second.rglob("*")):
            if path.is_file() and path != main:
                target = output.parent / path.relative_to(second)
                if _path_key(target) in wanted:
                    extra.append((target, path.read_bytes()))
                else:
                    journal.append(["write_refused", str(target)])
        return main.read_bytes(), extra

_ENGINES = {"lxml": (_lxml_version, _run_lxml), "saxon": (_saxon_version, _run_saxon)}
