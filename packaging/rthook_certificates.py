# -*- coding: utf-8 -*-
"""Certificats HTTPS de la version prête à l'emploi (crochet d'exécution
PyInstaller, lancé avant Varians).

Sous Windows, Python lit les certificats du système : rien à faire. Sous
macOS et Linux, la bibliothèque OpenSSL embarquée cherche les certificats là
où ils étaient sur la machine de construction ; s'ils n'y sont pas (macOS,
Linux autre que Debian/Ubuntu), ceux de certifi, livrés avec Varians, sont
utilisés (manifestes et images IIIF, schémas TEI, TEI Stylesheets). Un
``SSL_CERT_FILE`` déjà défini par l'utilisateur est respecté."""


def _use_bundled_certificates():
    import os
    import sys
    if sys.platform == "win32" or os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return
    try:
        import ssl
        paths = ssl.get_default_verify_paths()
        if paths.cafile and os.path.isfile(paths.cafile):
            return
        if paths.capath and os.path.isdir(paths.capath):
            with os.scandir(paths.capath) as entries:
                if any(entries):
                    return
        import certifi
        os.environ["SSL_CERT_FILE"] = certifi.where()
    except Exception:                           # jamais bloquant au démarrage
        pass


_use_bundled_certificates()
