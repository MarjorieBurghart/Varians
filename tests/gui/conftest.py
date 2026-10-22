# -*- coding: utf-8 -*-
"""Infrastructure des tests pilotant la véritable interface Qt de Varians.

Ces tests construisent la vraie ``MainWindow`` (sans écran, via
``QT_QPA_PLATFORM=offscreen``) et vérifient le comportement observable de
l'application. Ils servent de filet de sécurité pendant la restructuration
de ``editeur_tei.py`` : ils doivent passer avant et après chaque étape.

Garanties apportées par les fixtures ci-dessous :

* les réglages QSettings et le cache des schémas sont écrits dans un
  dossier temporaire, jamais dans le profil de l'utilisateur (ni dans le
  registre Windows) ;
* tout accès réseau échoue immédiatement ;
* toute boîte de dialogue modale doit avoir été prévue par le test
  (fixture ``dialogs``) ; une boîte inattendue fait échouer le test au
  lieu de le bloquer.
"""
from __future__ import annotations

import gc
import os
import re
import shutil
import sys
import urllib.request
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
# Jeux de données partagés avec les tests sans Qt (corpus_data…).
if str(ROOT / "tests") not in sys.path:
    sys.path.append(str(ROOT / "tests"))

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import QEvent, QThreadPool  # noqa: E402
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox  # noqa: E402


# Schéma minimal : racine TEI, contenu libre, sauf l'élément <forbidden>
# (pour produire une erreur RELAX NG à un endroit choisi) ; l'élément
# <varianstest kind="…"> est déclaré explicitement (pour la complétion).
# Aucune dépendance au schéma TEI distant déclaré par le projet exemple.
TEST_RNG = """<?xml version="1.0" encoding="UTF-8"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0"
         ns="http://www.tei-c.org/ns/1.0">
  <start>
    <element name="TEI"><ref name="any"/></element>
  </start>
  <define name="any">
    <zeroOrMore>
      <choice>
        <attribute><anyName/></attribute>
        <text/>
        <element name="varianstest">
          <attribute name="kind"/>
          <text/>
        </element>
        <element>
          <anyName><except><name>forbidden</name><name>varianstest</name></except></anyName>
          <ref name="any"/>
        </element>
      </choice>
    </zeroOrMore>
  </define>
</grammar>
"""

_XML_MODEL_RE = re.compile(r"<\?xml-model\b.*?\?>", re.S)
_EXAMPLE_ITEMS = ("project.xml", "xml", "alignments", "rendering", "i18n", "resources")


class UnexpectedDialog(AssertionError):
    pass


class DialogScript:
    """Réponses programmées aux boîtes de dialogue modales.

    ``expect(kind, answer)`` empile une réponse : ``kind`` vaut
    « question », « warning », « critical », « information » (méthodes
    statiques de QMessageBox), « box » (QMessageBox construite puis
    ``exec()``) ou « dialog » (toute autre QDialog ``exec()``). Pour « box »,
    ``answer`` est le rôle du bouton à cliquer (``QMessageBox.ButtonRole``)
    ou ``None`` pour fermer sans choix. Pour « dialog », ``answer`` est une
    fonction qui reçoit la boîte et renvoie le code de retour de ``exec()``.
    Chaque boîte affichée est enregistrée dans ``seen``.
    """

    def __init__(self):
        self._queue = []
        self.seen = []

    def expect(self, kind, answer=None):
        self._queue.append((kind, answer))

    def pending(self):
        return list(self._queue)

    def _next(self, kind, title, text):
        self.seen.append((kind, str(title), str(text)))
        if not self._queue:
            raise UnexpectedDialog(f"Boîte de dialogue inattendue ({kind}) : {title!r} — {text!r}")
        expected_kind, answer = self._queue.pop(0)
        if expected_kind != kind:
            raise UnexpectedDialog(
                f"Boîte « {kind} » affichée alors que « {expected_kind} » était attendue : {title!r}")
        return answer

    # Méthodes statiques de QMessageBox ------------------------------------
    def static(self, kind):
        def _impl(parent, title, text, *args, **kwargs):
            answer = self._next(kind, title, text)
            if answer is None:
                return QMessageBox.StandardButton.Ok
            return answer
        return _impl

    # QMessageBox(self) … box.exec() --------------------------------------
    def box_exec(self, box):
        role = self._next("box", box.windowTitle(), box.text())
        if role is None:
            return 0
        for button in box.buttons():
            if box.buttonRole(button) == role:
                button.click()
                return 0
        raise UnexpectedDialog(f"Aucun bouton de rôle {role} dans « {box.windowTitle()} »")

    # QDialog(...) … dlg.exec() ---------------------------------------------
    def dialog_exec(self, dialog):
        answer = self._next("dialog", dialog.windowTitle(), type(dialog).__name__)
        return answer(dialog) if callable(answer) else 0


@pytest.fixture(autouse=True)
def isolated_environment(tmp_path, monkeypatch):
    """Réglages, cache et réseau isolés pour chaque test."""
    settings_dir = tmp_path / "_settings"
    settings_dir.mkdir()
    # Tous les réglages de Varians passent par app_context._settings() : ils
    # sont redirigés vers un fichier INI temporaire, jamais vers le registre
    # Windows ni ~/.config.
    import app_context
    monkeypatch.setattr(app_context, "SETTINGS_FILE_OVERRIDE", settings_dir / "varians.ini")
    home = tmp_path / "_home"
    home.mkdir()
    for var in ("HOME", "USERPROFILE", "LOCALAPPDATA", "APPDATA"):
        monkeypatch.setenv(var, str(home))

    def _no_network(*args, **kwargs):
        raise OSError("Accès réseau interdit pendant les tests")

    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    import iiif_local
    import iiif_manifest
    import schema_resolution
    for module in (iiif_local, iiif_manifest, schema_resolution):
        monkeypatch.setattr(module, "urlopen", _no_network)

    # Images distantes (IIIF/Gallica) : échec immédiat et explicite, sans les
    # nouvelles tentatives temporisées du chargeur réel. Les images locales
    # (file://) continuent d'être lues normalement.
    import image_fetch
    original = image_fetch.FetchWorker._cached_or_download

    def _local_only(self, url):
        if str(url).lower().startswith("file://"):
            return original(self, url)
        raise OSError("Accès réseau interdit pendant les tests")

    monkeypatch.setattr(image_fetch.FetchWorker, "_cached_or_download", _local_only)
    monkeypatch.setattr(image_fetch.FetchWorker, "_gallica_lock", None, raising=False)
    yield


@pytest.fixture
def dialogs(monkeypatch):
    script = DialogScript()
    for kind in ("question", "warning", "critical", "information"):
        monkeypatch.setattr(QMessageBox, kind, staticmethod(script.static(kind)))
    monkeypatch.setattr(QMessageBox, "exec", lambda box: script.box_exec(box))
    monkeypatch.setattr(QDialog, "exec", lambda dialog: script.dialog_exec(dialog))
    yield script
    assert not script.pending(), f"Boîtes de dialogue attendues mais jamais affichées : {script.pending()}"


@pytest.fixture
def example_project(tmp_path):
    """Copie du projet exemple, avec un petit schéma RELAX NG local."""
    root = tmp_path / "exemple"
    root.mkdir()
    for name in _EXAMPLE_ITEMS:
        src = ROOT / name
        if src.is_dir():
            shutil.copytree(src, root / name)
        else:
            shutil.copy2(src, root / name)
    (root / "web_output").mkdir(exist_ok=True)
    (root / "xml" / "test.rng").write_text(TEST_RNG, encoding="utf-8")
    edition = root / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    local_model = ('<?xml-model href="test.rng" type="application/xml" '
                   'schematypens="http://relaxng.org/ns/structure/1.0"?>')
    text = _XML_MODEL_RE.sub("", text, count=0)
    text = text.replace("?>", "?>\n" + local_model, 1)
    edition.write_text(text, encoding="utf-8")
    return root / "project.xml"


# Document auxiliaire : fichier d'autorités sans <?xml-model?>.
PERSONNES_XML = """<?xml version="1.0" encoding="UTF-8"?>
<listPerson xmlns="http://www.tei-c.org/ns/1.0">
  <person xml:id="bernard"><persName>Bernardus</persName></person>
  <person xml:id="petrus"><persName>Petrus</persName></person>
</listPerson>
"""


@pytest.fixture
def project_with_documents(example_project):
    """Projet exemple déclarant le document auxiliaire xml/personnes.xml."""
    from project_config import DocumentConfig
    from project_management import update_project_documents

    personnes = example_project.parent / "xml" / "personnes.xml"
    personnes.write_text(PERSONNES_XML, encoding="utf-8")
    update_project_documents(example_project, [DocumentConfig(personnes, "Personnes")])
    return example_project


@pytest.fixture
def example_with_part(example_project):
    """Projet exemple dont le sermon RLS_185 est passé dans une partie,
    xml/rls185.xml, incluse par l'édition."""
    edition = example_project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    start = text.index('<div xml:id="RLS_185">')
    end = text.index('<div xml:id="RLS_186">')
    part = text[start:end].rstrip()
    assert part.endswith("</div>")
    part = part.replace('<div xml:id="RLS_185">', '<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="RLS_185">', 1)
    (edition.parent / "rls185.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + part + "\n",
                                               encoding="utf-8")
    text = text[:start] + '<xi:include href="rls185.xml"/>\n' + text[end:]
    text = re.sub(r"<TEI\b", '<TEI xmlns:xi="http://www.w3.org/2001/XInclude"', text, count=1)
    edition.write_text(text, encoding="utf-8")
    return example_project


@pytest.fixture
def example_with_text(example_with_part):
    """Projet exemple dont RLS_185, passé dans une partie, est synchronisé à
    part (V0.9.1.1) : ses lignes de T1 et de T2 passent des JSON globaux à
    alignments/rls185/T1.json et T2.json ; P, sans JSON pour ce texte, n'y a
    plus de lignes."""
    from corpus_data import split_alignments
    split_alignments(example_with_part.parent, "rls185", "T1", 116, 165, ("T2",))
    return example_with_part


@pytest.fixture
def corpus_project(tmp_path):
    """Jeu « corpus » (tests/corpus_data.py), avec le petit schéma local."""
    from corpus_data import make_corpus
    project = make_corpus(tmp_path / "corpus")
    _use_local_schema(project.parent)
    return project


SERMONS_DATA = ROOT / "tests" / "data" / "sermons"


@pytest.fixture
def sermons_project(tmp_path):
    """Copie du projet d'essai « sermons » : une édition qui inclut ses
    sermons par XInclude (tests/data/sermons), avec le petit schéma local à
    la place de TEI_ALL. Le <?xml-model?> remplacé tient sur la même ligne :
    les numéros de ligne des fichiers ne changent pas."""
    root = tmp_path / "sermons"
    shutil.copytree(SERMONS_DATA, root)
    _use_local_schema(root)
    return root / "project.xml"


def _use_local_schema(root):
    """Petit schéma local à la place de TEI_ALL dans un projet « sermons »."""
    (root / "web_output").mkdir(exist_ok=True)
    (root / "xml" / "test.rng").write_text(TEST_RNG, encoding="utf-8")
    for path in (root / "xml").rglob("*.xml"):
        text = path.read_text(encoding="utf-8")
        href = "test.rng" if path.parent.name == "xml" else "../test.rng"
        local_model = (f'<?xml-model href="{href}" type="application/xml" '
                       'schematypens="http://relaxng.org/ns/structure/1.0"?>')
        path.write_text(_XML_MODEL_RE.sub(local_model, text, count=1), encoding="utf-8")


# Petite collection : une édition qui inclut trois courts sermons. Schéma
# explicite : libxml2 signale une erreur à l'élément fautif, sans erreurs en
# cascade sur ses ancêtres (comme avec TEI_ALL).
COLLECTION_RNG = """<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" ns="http://www.tei-c.org/ns/1.0">
  <start>
    <element name="TEI">
      <element name="text"><element name="body"><oneOrMore><ref name="div"/></oneOrMore></element></element>
    </element>
  </start>
  <define name="div">
    <element name="div">
      <optional><attribute name="xml:id" ns="http://www.w3.org/XML/1998/namespace"/></optional>
      <optional><attribute name="xml:base" ns="http://www.w3.org/XML/1998/namespace"/></optional>
      <optional><element name="head"><text/></element></optional>
      <zeroOrMore><element name="p"><mixed><zeroOrMore><element name="hi"><text/></element></zeroOrMore></mixed></element></zeroOrMore>
    </element>
  </define>
</grammar>
"""
COLLECTION_EDITION = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="collection.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">
  <text>
    <body>
      <div xml:id="intro"><p>Introductio</p></div>
      <xi:include href="sermons/s01.xml"/>
      <xi:include href="sermons/s02.xml"/>
      <xi:include href="sermons/s03.xml"/>
    </body>
  </text>
</TEI>
"""


def _collection_part(number):
    """Texte d'un sermon de la collection ; son paragraphe, « Sermo
    <hi>breuis</hi>. », est à la ligne 3."""
    return (f'<div xmlns="http://www.tei-c.org/ns/1.0" xml:id="s0{number}">\n'
            f'  <head>Sermo {number}</head>\n'
            '  <p>Sermo <hi>breuis</hi>.</p>\n'
            '</div>\n')


@pytest.fixture
def collection_project(sermons_project):
    """Le projet « sermons » réduit à une édition qui inclut trois courts
    sermons (fragments s01 à s03), validée par COLLECTION_RNG."""
    xml = sermons_project.parent / "xml"
    (xml / "collection.rng").write_text(COLLECTION_RNG, encoding="utf-8")
    (xml / "edition.xml").write_text(COLLECTION_EDITION, encoding="utf-8")
    for number in (1, 2, 3):
        (xml / "sermons" / f"s0{number}.xml").write_text(_collection_part(number), encoding="utf-8")
    return sermons_project


@pytest.fixture
def editor_module(qapp):
    import editeur_tei
    return editeur_tei


@pytest.fixture
def open_window(qtbot, editor_module, dialogs):
    """Fabrique de MainWindow ; les fenêtres sont fermées proprement à la fin."""
    windows = []

    def _open(project_path, wait_validation=True):
        window = editor_module.MainWindow(Path(project_path))
        window.show()
        qtbot.waitExposed(window)
        windows.append(window)
        # Laisser passer les minuteries de démarrage (synchronisation à
        # 50 ms, validation RELAX NG à 120 ms), puis la réponse du processus
        # de validation, qui arrive sans bloquer la fenêtre.
        qtbot.wait(250)
        if wait_validation:
            import validation_worker
            qtbot.waitUntil(lambda: not validation_worker.worker_client().busy, timeout=60000)
        return window

    yield _open

    # Laisser les chargements d'images en cours se terminer et livrer leur
    # résultat tant que les fenêtres existent encore.
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    for window in windows:
        window._force_close = True
        window.close()
        # Fermer ne suffit pas : la fenêtre (son édition, ses témoins, ses
        # images) resterait en mémoire jusqu'à la fin de la session de tests,
        # et la mémoire des serveurs de CI s'épuiserait.
        window.deleteLater()
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    windows.clear()
    gc.collect()
