#!/usr/bin/env python3
"""Contrôle hors ligne et en lecture seule du ZIP source majeur Varians.

Exécuter depuis n'importe quel répertoire :
    python OUTILS/verifier_archive_reference.py
ou bien :
    python verifier_archive_reference.py /chemin/vers/archive.zip

Aucune dépendance externe : bibliothèque standard Python uniquement.
"""
from __future__ import annotations
import hashlib
from pathlib import Path
import re
import sys
import zipfile

EXPECTED_NAME = "Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip"
EXPECTED_SHA256 = "1f5562ab3568aba11900316ccd81d19918859e4d238c4b30191a6d2bad8cf3c4"
EXPECTED_MEMBERS = 268
EXPECTED_VERSION = 'APP_VERSION = "0.8.5.26.2"'
EXPECTED_LANGS = {"fr", "en", "de", "ja", "cs", "it", "ru"}


def main(argv: list[str]) -> int:
    p = (Path(argv[1]).expanduser().resolve() if len(argv) > 1 else
         Path(__file__).resolve().parents[1] / "BASE_SOURCE" / EXPECTED_NAME)
    print("Archive :", p)
    if not p.is_file():
        print("ECHEC : fichier ZIP absent.")
        return 2
    digest = hashlib.sha256()
    with p.open("rb") as fh:
        for block in iter(lambda: fh.read(1024*1024), b""):
            digest.update(block)
    got = digest.hexdigest()
    print("SHA-256 :", got, "(OK)" if got == EXPECTED_SHA256 else "(INCORRECT)")
    errors = []
    if got != EXPECTED_SHA256:
        errors.append("Empreinte SHA-256 différente de la référence figée")
    try:
        with zipfile.ZipFile(p) as z:
            bad = z.testzip()
            if bad: errors.append("CRC non conforme : " + bad)
            names = z.namelist()
            print("Fichiers :", len(names))
            if len(names) != EXPECTED_MEMBERS:
                errors.append("Nombre de fichiers différent")
            if len(names) != len(set(names)):
                errors.append("Noms de fichiers ZIP en doublon")
            for required in ["editeur_tei.py", "project.xml", "requirements.txt",
                             "web_viewer/generator.py", "web_viewer/fulltext_search.js",
                             "web_viewer/iiif.js", "tests/test_v085262_rng_panel_refresh.py"]:
                if required not in names:
                    errors.append("Fichier obligatoire absent : " + required)
            if "editeur_tei.py" in names:
                src = z.read("editeur_tei.py").decode("utf-8-sig")
                if EXPECTED_VERSION not in src:
                    errors.append("Version de l'application inattendue")
            langs = {m.group(1) for n in names if (m:=re.fullmatch(r"i18n/([a-z]{2})\.xml",n))}
            helps = {m.group(1) for n in names if (m:=re.fullmatch(r"help/([a-z]{2})\.html",n))}
            print("Catalogues :", ", ".join(sorted(langs)))
            print("Aides :", ", ".join(sorted(helps)))
            if langs != EXPECTED_LANGS: errors.append("Catalogues i18n manquants")
            if helps != EXPECTED_LANGS: errors.append("Aides HTML manquantes")
    except (OSError,zipfile.BadZipFile,UnicodeError) as exc:
        errors.append(f"Archive illisible : {exc}")
    if errors:
        print("\nECHEC :")
        for e in errors: print("-",e)
        return 1
    print("\nOK : la base source majeure V0.8.5.26.2 est intègre.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
