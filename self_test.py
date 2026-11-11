# -*- coding: utf-8 -*-
"""Vérification d'une installation de Varians (V0.9.4.0).

``Varians --self-test RAPPORT.json`` (ou ``python editeur_tei.py
--self-test RAPPORT.json``) contrôle, sans écran ni réseau :

- ``translations`` : les sept catalogues de l'interface, mêmes clés ;
- ``help`` : l'aide dans les sept langues ;
- ``resources`` : feuilles de rendu, schémas, SchXslt2, TEI Stylesheets,
  modèles, icônes, scripts du viewer web ;
- ``project`` : création d'un petit projet, comme « Nouveau projet » ;
- ``relaxng_worker`` : le processus de validation, lancé comme Varians le
  lance (l'exécutable lui-même dans une version autonome), sans
  l'interface Qt (``worker_problem``) ;
- ``transform_lxml``, ``transform_saxon`` : une transformation XSLT dans
  son processus, avec chacun des deux moteurs, de même sans l'interface ;
- ``preview_saxon`` : le processus d'aperçu des vues en XSLT 3.0
  (V0.9.4.4), qui reste ouvert, de même ;
- ``window`` : le projet ouvert dans la fenêtre de Varians, avec son icône,
  puis fermé.

Elle sert à vérifier, sur chaque système, la version prête à l'emploi
construite par PyInstaller (packaging/) : une application Windows sans
console n'a pas de sortie standard, d'où le rapport écrit dans un fichier.
Le code de sortie est 0 si tout va bien, 1 sinon. Les réglages de
l'utilisateur ne sont pas touchés (fichier de réglages provisoire)."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import traceback
from pathlib import Path

LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
CHECKS = ("translations", "help", "resources", "project", "relaxng_worker", "transform_lxml",
          "transform_saxon", "preview_saxon", "window")
# Ressources sans lesquelles une fonction de Varians ne marche pas.
RESOURCES = (
    "rendering/tei-to-html.xsl", "rendering/tei.css", "rendering/edition-critique.xsl",
    "rendering/apparat-en-notes.xsl", "rendering/custom-elements.xml",
    "resources/templates/project-template.xml", "resources/templates/tei/All.xml",
    "resources/schxslt2", "resources/schemas",
    "resources/tei-stylesheets/tei-xsl-7.61.0.zip", "resources/icons/feuilleter.svg",
    "resources/varians_logo.png", "resources/icons/varians.png",
    "web_viewer/geometry.js", "web_viewer/iiif.js", "web_viewer/fulltext_search.js",
    "web_viewer/sync_model.js", "web_viewer/plurals.js",
)
EDITION = """<?xml version="1.0" encoding="UTF-8"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0">
  <teiHeader><fileDesc><titleStmt><title>Vérification</title></titleStmt>
    <publicationStmt><p>Essai</p></publicationStmt>
    <sourceDesc><listWit><witness xml:id="A">Témoin A</witness><witness xml:id="B">Témoin B</witness></listWit>
    </sourceDesc></fileDesc></teiHeader>
  <text><body><div><p><lb edRef="#A"/>In principio <app><lem wit="#A">erat</lem><rdg wit="#B">est</rdg></app>
  verbum.</p></div></body></text>
</TEI>
"""
SCHEMA = """<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0"><start><element name="essai"><text/></element></start></grammar>
"""


def _installation():
    return Path(__file__).resolve().parent


def _translations(root):
    import xml.etree.ElementTree as ET
    keys = {}
    for language in LANGUAGES:
        tree = ET.parse(root / "i18n" / f"{language}.xml")
        keys[language] = {node.get("key") for node in tree.getroot().findall("string")}
    reference = keys["fr"]
    different = [language for language, found in keys.items() if found != reference]
    if different:
        raise AssertionError(f"catalogues différents du français : {', '.join(different)}")
    from i18n import I18nManager
    if not I18nManager(root / "i18n", "en", "en").tr("menu.file"):
        raise AssertionError("traduction vide")
    return f"{len(LANGUAGES)} langues, {len(reference)} messages"


def _help(root):
    missing = [f"help/{language}.html" for language in LANGUAGES if not (root / "help" / f"{language}.html").is_file()]
    if missing:
        raise AssertionError("absent : " + ", ".join(missing))
    return f"{len(LANGUAGES)} langues"


def _resources(root):
    missing = [name for name in RESOURCES if not (root / name).exists()]
    if missing:
        raise AssertionError("absent : " + ", ".join(missing))
    return f"{len(RESOURCES)} ressources"


def _project(root, folder):
    from project_management import WitnessDraft, create_portable_project
    source = folder / "source.xml"
    source.write_text(EDITION, encoding="utf-8")
    path = create_portable_project(folder / "projet", "Vérification", source,
                                   [WitnessDraft("A", "Témoin A", role="base"), WitnessDraft("B", "Témoin B")],
                                   "A", root)
    from project_config import load_project
    project = load_project(path)
    if [w.id for w in project.witnesses] != ["A", "B"]:
        raise AssertionError("témoins inattendus")
    return path


def worker_problem(answer, frozen):
    """Ce qui ne va pas dans la réponse d'un processus de validation ou de
    transformation quant à Qt (None si rien) : jamais l'interface (QtGui,
    QtWidgets) ; en mode source, pas du tout PySide6. Dans une version
    construite par PyInstaller, QtCore est chargé dans tout processus par
    le crochet d'exécution de PySide6 (environ 0,1 s au lancement)."""
    if answer.get("gui_loaded") is not False:
        return f"interface Qt chargée dans le processus : {answer}"
    if not frozen and answer.get("qt_loaded") is not False:
        return f"PySide6 chargé dans le processus : {answer}"
    return None


def _frozen():
    return bool(getattr(sys, "frozen", False))


def _relaxng_worker(folder):
    import subprocess
    from validation_worker import default_worker_command
    schema = folder / "essai.rng"
    schema.write_text(SCHEMA, encoding="utf-8")
    requests = (json.dumps({"id": 1, "op": "ping"}) + "\n"
                + json.dumps({"id": 2, "op": "validate", "xml": "<essai>ok</essai>", "schema": str(schema)}) + "\n"
                + json.dumps({"id": 3, "op": "validate", "xml": "<autre/>", "schema": str(schema)}) + "\n")
    completed = subprocess.run(default_worker_command(), input=requests.encode("utf-8"), capture_output=True,
                               timeout=120, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
    lines = [json.loads(line) for line in completed.stdout.decode("utf-8").splitlines() if line.strip()]
    # Les annonces de compilation du schéma ne sont pas des réponses.
    lines = [line for line in lines if "compiling" not in line and "compiled" not in line]
    if completed.returncode != 0 or len(lines) != 3:
        raise AssertionError(f"code {completed.returncode} : {completed.stderr.decode('utf-8', 'replace')[-800:]}")
    ping, valid, invalid = lines
    if not ping.get("ok"):
        raise AssertionError(f"réponse inattendue : {ping}")
    problem = worker_problem(ping, _frozen())
    if problem:
        raise AssertionError(problem)
    if not valid["result"]["valid"] or invalid["result"]["valid"]:
        raise AssertionError("validation RELAX NG inexacte")
    return f"processus {ping['pid']}"


def _transform(project_path, engine):
    """Comme transform_worker.run_in_process, en gardant la réponse brute
    du processus (``qt_loaded``, ``gui_loaded``)."""
    import subprocess
    from project_config import TransformScenario, load_project
    from transform_worker import new_stderr_log, read_answer, worker_command
    from xslt_scenarios import scenario_request
    project = load_project(project_path)
    output = f"publications/edition-{engine}.html"
    request = scenario_request(TransformScenario(engine, "${varians}/tei-to-html.xsl", output, engine=engine), project)
    stderr_log = new_stderr_log()
    try:
        with open(stderr_log, "wb") as errors:
            data = json.dumps(dict(request, stderr_log=stderr_log)).encode("utf-8")
            completed = subprocess.run(worker_command(), input=data, stdout=subprocess.PIPE, stderr=errors, timeout=180,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        result = read_answer(completed.stdout, stderr_log)
    finally:
        os.unlink(stderr_log)
    if not result.ok:
        raise AssertionError(f"{result.error_code} : {result.error}")
    problem = worker_problem(json.loads(completed.stdout.decode("utf-8")), _frozen())
    if problem:
        raise AssertionError(problem)
    text = (project.root_dir / output).read_text(encoding="utf-8")
    if "principio" not in text:
        raise AssertionError("résultat sans le texte de l'édition")
    return f"{engine} : {output}"


def _preview_saxon(root):
    """Le processus d'aperçu des vues en XSLT 3.0 (saxon_preview), lancé
    comme Varians le fait : l'édition d'essai, mise en forme par « Édition
    critique » comme vue de l'édition, avec ses crayons et le repère de
    ligne du témoin pivot."""
    from fragment_units import mark_units, place_edit_markers
    from saxon_preview import SaxonPreviewClient
    worker = SaxonPreviewClient()
    try:
        problem = worker_problem(worker.ping(timeout=180), _frozen())
        if problem:
            raise AssertionError(problem)
        marked, spans = mark_units(EDITION)
        result = worker.transform(marked, Path(root) / "rendering" / "edition-critique.xsl",
                                  {"temoin-de-base": "A", "reperes-lignes": "true"}, timeout=180)
    finally:
        worker.close()
    html, pencils = place_edit_markers(result.html)
    lines = html.count("tei-line://base/INDEX")
    if "principio" not in html or pencils != len(spans) or lines != 1:
        raise AssertionError(f"aperçu inexact : {pencils} crayon(s) pour {len(spans)} élément(s), "
                             f"{lines} repère(s) de ligne pour 1")
    return f"{result.engine} : {pencils} crayon(s), {lines} repère de ligne"


def _window(project_path, window_class):
    from PySide6.QtWidgets import QApplication
    from app_context import apply_application_icon
    app = QApplication.instance() or QApplication([sys.argv[0]])
    apply_application_icon(app)
    window = window_class(project_path)
    try:
        window.show()
        for _ in range(20):
            app.processEvents()
        if window.project.title != "Vérification" or "principio" not in window.editor.toPlainText():
            raise AssertionError("projet mal ouvert")
        if window.windowIcon().isNull() or not window.windowIcon().availableSizes():
            raise AssertionError("icône de Varians non chargée")
        return f"{len(window.project.witnesses)} témoins, {window.editor.document().blockCount()} lignes"
    finally:
        window._force_close = True
        window.close()
        app.processEvents()


def run(report_path=None, *, root=None, window_class=None, only=CHECKS) -> int:
    """Vérifie l'installation ``root`` (celle de ce module par défaut) et
    écrit le rapport JSON dans ``report_path`` ; 0 si tout va bien."""
    import app_context
    root = Path(root) if root else _installation()
    checks = []
    with tempfile.TemporaryDirectory(prefix="varians-self-test-") as temporary:
        folder = Path(temporary)
        # Réglages provisoires : ni projets récents ni fenêtres de
        # l'utilisateur ne sont touchés.
        app_context.SETTINGS_FILE_OVERRIDE = folder / "reglages.ini"
        state = {}

        def check(name, function):
            if name not in only:
                return
            try:
                detail = function()
                if name == "project":
                    state["project"] = detail
                    detail = "projet créé"
                checks.append({"name": name, "ok": True, "detail": str(detail)})
            except Exception as error:
                checks.append({"name": name, "ok": False, "detail": f"{error}\n{traceback.format_exc()[-2000:]}"})

        def needs_project(function):
            def checked():
                if "project" not in state:
                    raise AssertionError("pas de projet (vérification « project » en échec)")
                return function(state["project"])
            return checked

        check("translations", lambda: _translations(root))
        check("help", lambda: _help(root))
        check("resources", lambda: _resources(root))
        check("project", lambda: _project(root, folder))
        check("relaxng_worker", lambda: _relaxng_worker(folder))
        check("transform_lxml", needs_project(lambda path: _transform(path, "lxml")))
        check("transform_saxon", needs_project(lambda path: _transform(path, "saxon")))
        check("preview_saxon", lambda: _preview_saxon(root))
        if window_class is not None:
            check("window", needs_project(lambda path: _window(path, window_class)))
    ok = bool(checks) and all(item["ok"] for item in checks)
    report = {"ok": ok, "version": app_context.APP_VERSION, "frozen": _frozen(),
              "executable": sys.executable, "platform": sys.platform, "checks": checks}
    text = json.dumps(report, ensure_ascii=False, indent=1)
    if report_path:
        Path(report_path).write_text(text, encoding="utf-8")
    elif sys.stdout is not None:
        print(text)
    return 0 if ok else 1
