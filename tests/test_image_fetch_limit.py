# -*- coding: utf-8 -*-
"""Taille d'une image de témoin téléchargée (V0.9.4.6).

Une image téléchargée en arrière-plan pour un témoin est limitée en taille
(``image_fetch.MAX_IMAGE_BYTES``, comme une copie IIIF locale) : un serveur
qui annonce une image énorme, ou répond sans fin, ne remplit pas la mémoire ;
le panneau du témoin le dit dans la langue de l'interface."""
from __future__ import annotations

import io
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


class _Endless(io.RawIOBase):
    """Réponse HTTP qui ne finit jamais (ou très grande)."""

    def __init__(self, length=None):
        self.headers = {} if length is None else {"Content-Length": str(length)}

    def readable(self):
        return True

    def readinto(self, buffer):
        buffer[:] = b"x" * len(buffer)
        return len(buffer)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


@pytest.fixture
def small_limit(monkeypatch):
    import image_fetch
    monkeypatch.setattr(image_fetch, "MAX_IMAGE_BYTES", 2 * 1024 * 1024)
    return image_fetch


def test_a_witness_image_without_end_is_stopped(small_limit, monkeypatch):
    monkeypatch.setattr(small_limit.urllib.request, "urlopen", lambda *a, **k: _Endless())
    worker = small_limit.FetchWorker(1, "page", "https://example.org/f1.jpg")
    with pytest.raises(small_limit.ImageTooLarge):
        worker._download_once()


def test_a_witness_image_announced_too_large_is_not_read(small_limit, monkeypatch):
    reply = _Endless(length=10 ** 9)
    reply.readinto = None                                # rien n'est lu
    monkeypatch.setattr(small_limit.urllib.request, "urlopen", lambda *a, **k: reply)
    worker = small_limit.FetchWorker(1, "page", "https://example.org/f1.jpg")
    with pytest.raises(small_limit.ImageTooLarge):
        worker._download_once()


def test_a_witness_image_too_large_is_reported_in_the_panel_language(small_limit, monkeypatch, qapp):
    import app_context
    from i18n import I18nManager
    monkeypatch.setattr(app_context, "_i18n", I18nManager(ROOT / "i18n", "de", "en"))
    tr = app_context.tr
    monkeypatch.setattr(small_limit.urllib.request, "urlopen", lambda *a, **k: _Endless())
    received = []
    worker = small_limit.FetchWorker(1, "page", "https://example.org/f1.jpg")
    worker.signals.finished.connect(lambda token, key, data, error, mode: received.append((data, error)))
    worker.run()
    assert received == [(b"", tr("manuscript.image_too_large", size=2))]


def test_a_witness_image_within_the_limit_is_read(monkeypatch):
    import image_fetch

    class Reply(io.BytesIO):
        headers = {"Content-Length": "5"}

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(image_fetch.urllib.request, "urlopen", lambda *a, **k: Reply(b"\xff\xd8\xff\xe0J"))
    assert image_fetch.FetchWorker(1, "page", "https://example.org/f1.jpg")._download_once() == b"\xff\xd8\xff\xe0J"
    assert image_fetch.MAX_IMAGE_BYTES >= 100 * 1024 * 1024
