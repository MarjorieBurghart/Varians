# -*- coding: utf-8 -*-
"""Téléchargement en arrière-plan des images de manuscrits (IIIF, Gallica, fichiers locaux), avec cache disque."""
from __future__ import annotations

import hashlib
import re
import threading
import time
import urllib.error
import urllib.request

from pathlib import Path

from PySide6.QtCore import QObject, QRunnable, Signal, Slot


DISK_CACHE = Path.home() / ".cache_tei_manuscript_editor"
DISK_CACHE.mkdir(parents=True, exist_ok=True)


class FetchSignals(QObject):
    # token, key, data, error, source_mode ("crop" ou "fallback")
    finished = Signal(int, str, bytes, str, str)


class FetchWorker(QRunnable):
    _gallica_lock = threading.Lock()

    def __init__(self, token, key, url, fallback_url=None):
        super().__init__(); self.token = token; self.key = key; self.url = url
        self.fallback_url = fallback_url
        self.signals = FetchSignals()

    @staticmethod
    def _cache_path(url):
        suffix = ".jpg"
        return DISK_CACHE / (hashlib.sha1(url.encode("utf-8")).hexdigest() + suffix)

    def _cached_or_download(self, url):
        if str(url).lower().startswith("file://"):
            from urllib.parse import urlparse, unquote
            parsed = urlparse(url)
            raw_path = unquote(parsed.path or "")
            if parsed.netloc and not raw_path.startswith("/"):
                raw_path = "/" + raw_path
            # Sous Windows, file:///C:/... produit /C:/... ; Path accepte mieux C:/...
            if re.match(r"^/[A-Za-z]:/", raw_path):
                raw_path = raw_path[1:]
            return Path(raw_path).read_bytes()
        path = self._cache_path(url)
        if path.exists() and path.stat().st_size > 0:
            return path.read_bytes()
        old_url = self.url
        try:
            self.url = url
            data = self._download_once()
        finally:
            self.url = old_url
        if data:
            try:
                path.write_bytes(data)
            except OSError:
                pass
        return data

    def _download_once(self):
        req = urllib.request.Request(
            self.url,
            headers={
                # User-Agent de navigateur volontairement banal : certains
                # frontaux HTTP ferment les connexions de clients atypiques.
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36",
                "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
                "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.7",
                "Accept-Encoding": "identity",
                "Connection": "close",
                "Referer": "https://gallica.bnf.fr/",
            },
        )
        with urllib.request.urlopen(req, timeout=45) as resp:
            return resp.read()

    @Slot()
    def run(self):
        urls = [(self.url, "crop")]
        if self.fallback_url and self.fallback_url != self.url:
            urls.append((self.fallback_url, "fallback"))
        last_exc = None

        for candidate_url, mode in urls:
            is_gallica = "gallica.bnf.fr" in candidate_url.lower()
            attempts = 4 if is_gallica else 2
            lock = self._gallica_lock if is_gallica else None
            for attempt in range(attempts):
                try:
                    if lock:
                        with lock:
                            if attempt:
                                time.sleep(min(4.0, 0.8 * (2 ** (attempt - 1))))
                            data = self._cached_or_download(candidate_url)
                            time.sleep(0.35)
                    else:
                        data = self._cached_or_download(candidate_url)
                    if not data:
                        raise RuntimeError("réponse vide")
                    self.signals.finished.emit(self.token, self.key, data, "", mode)
                    return
                except Exception as exc:
                    last_exc = exc
                    if not is_gallica:
                        break
            # Si le recadrage IIIF Gallica échoue, on tente le fallback highres.

        msg = str(last_exc) if last_exc else "échec réseau"
        if "429" in msg or "Too Many Requests" in msg:
            msg = "Gallica limite temporairement les requêtes (HTTP 429)."
        elif "10054" in msg or "forcibly closed" in msg.lower() or "reset" in msg.lower():
            msg = "Gallica a réinitialisé la connexion (WinError 10054), même après plusieurs nouvelles tentatives."
        self.signals.finished.emit(self.token, self.key, b"", msg, "")

