# -*- coding: utf-8 -*-
"""Red team (sécurité, B2) dans la fenêtre : un schéma déclaré sur un autre
site que celui de la TEI n'est téléchargé qu'avec l'accord de
l'utilisatrice, demandé une fois par site et mémorisé ; un site refusé
n'est plus demandé par la validation automatique, mais Valider (F8)
repose la question."""
from __future__ import annotations

from PySide6.QtWidgets import QMessageBox

import schema_resolution
from app_context import site_choice, tr

SCHEMA = "https://example.org/schemas/edition.rng"
TEI_ALL = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/tei_all.rng"
# Un schéma qui accepte tout document.
OPEN_RNG = ('<grammar xmlns="http://relaxng.org/ns/structure/1.0"><start><ref name="any"/></start>'
            '<define name="any"><element><anyName/><zeroOrMore><choice><attribute><anyName/></attribute>'
            '<text/><ref name="any"/></choice></zeroOrMore></element></define></grammar>')


class _Response:
    def __init__(self, url, data):
        self.url, self.data = url, data

    def read(self):
        return self.data

    def geturl(self):
        return self.url

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _declare(project, href, monkeypatch):
    """L'édition déclare *href* ; le « site » sert OPEN_RNG et note les
    adresses demandées."""
    edition = project.parent / "xml" / "edition.xml"
    edition.write_text(edition.read_text(encoding="utf-8").replace('href="test.rng"', f'href="{href}"'),
                       encoding="utf-8")
    requested = []

    def fake(request, timeout=None):
        requested.append(request.full_url)
        return _Response(request.full_url, OPEN_RNG.encode("utf-8"))

    monkeypatch.setattr(schema_resolution, "urlopen", fake)
    return requested


def _boxes(dialogs):
    return [seen for seen in dialogs.seen if seen[0] == "box"]


def test_a_schema_on_another_site_is_downloaded_only_once_allowed(open_window, example_project, dialogs,
                                                                  monkeypatch):
    requested = _declare(example_project, SCHEMA, monkeypatch)
    dialogs.expect("box", QMessageBox.ButtonRole.RejectRole)
    window = open_window(example_project)
    [(_kind, title, text)] = _boxes(dialogs)
    assert title == tr("schemas.site.title") and "example.org" in text and SCHEMA in text
    assert requested == [] and site_choice("example.org") is False
    assert window.rng_status.text() == tr("rng.status.site_refused")
    assert "example.org" in window.validation_summary.text()

    # Refusé : la validation automatique ne redemande pas.
    window.validate_relaxng_document(automatic=True)
    assert len(_boxes(dialogs)) == 1 and requested == []

    # F8 repose la question ; autorisé, le schéma est téléchargé et employé.
    dialogs.expect("box", QMessageBox.ButtonRole.AcceptRole)
    window.validate_relaxng_manual()
    assert len(_boxes(dialogs)) == 2 and site_choice("example.org") is True
    assert requested == [SCHEMA]
    assert window._last_rng_result is not None and window._last_rng_result.schema_loaded

    # Mémorisé : plus de question.
    window.validate_relaxng_manual()
    assert len(_boxes(dialogs)) == 2


def test_the_tei_schema_is_downloaded_without_a_question(open_window, example_project, dialogs, monkeypatch):
    requested = _declare(example_project, TEI_ALL, monkeypatch)
    window = open_window(example_project)
    window.validate_relaxng_manual()
    assert not _boxes(dialogs) and requested == [TEI_ALL]
    assert window._last_rng_result is not None and window._last_rng_result.schema_loaded
