# -*- coding: utf-8 -*-
"""Téléchargement d'image dont le destinataire a disparu entre-temps."""
from __future__ import annotations

import shiboken6


def test_finished_download_with_deleted_signal_source_is_silently_dropped(qapp):
    """Fenêtre fermée pendant un téléchargement : le résultat est abandonné.

    En V0.8.5.26.2, l'émission levait « RuntimeError: Signal source has been
    deleted », affichée dans la console.
    """
    import image_fetch

    worker = image_fetch.FetchWorker(1, "page", "https://example.invalid/image.jpg")
    shiboken6.delete(worker.signals)
    worker.run()                       # réseau coupé par conftest : échec, puis émission


def test_finished_download_still_reaches_a_living_receiver(qapp):
    import image_fetch

    received = []
    worker = image_fetch.FetchWorker(7, "page", "https://example.invalid/image.jpg")
    worker.signals.finished.connect(lambda token, key, data, error, mode: received.append((token, key, bool(error))))
    worker.run()
    assert received == [(7, "page", True)]
