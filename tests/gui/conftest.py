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

PySide6 = pytest.importorskip("PySide6")
from PySide6.QtCore import QThreadPool  # noqa: E402
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
def editor_module(qapp):
    import editeur_tei
    return editeur_tei


@pytest.fixture
def open_window(qtbot, editor_module, dialogs):
    """Fabrique de MainWindow ; les fenêtres sont fermées proprement à la fin."""
    windows = []

    def _open(project_path):
        window = editor_module.MainWindow(Path(project_path))
        window.show()
        qtbot.waitExposed(window)
        # Laisser passer les minuteries de démarrage (synchronisation à
        # 50 ms, validation RELAX NG à 120 ms).
        qtbot.wait(250)
        windows.append(window)
        return window

    yield _open

    # Laisser les chargements d'images en cours se terminer et livrer leur
    # résultat tant que les fenêtres existent encore.
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
    for window in windows:
        window._force_close = True
        window.close()
    QThreadPool.globalInstance().waitForDone(5000)
    QApplication.processEvents()
