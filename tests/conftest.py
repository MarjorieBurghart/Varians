# -*- coding: utf-8 -*-
"""Réglages communs aux tests.

Les TEI Stylesheets (V0.9.2.2) s'installent au premier usage dans le dossier
de données de l'utilisateur : pendant les tests, ce dossier est remplacé par
un dossier temporaire commun à la session (``VARIANS_TEI_STYLESHEETS``), où
l'archive livrée n'est extraite qu'une fois. Les tests de l'interface
(tests/gui/conftest.py) font de même.
"""
from __future__ import annotations

import os

import pytest


@pytest.fixture(autouse=True, scope="session")
def tei_stylesheets_library(tmp_path_factory):
    folder = tmp_path_factory.mktemp("tei-stylesheets")
    previous = os.environ.get("VARIANS_TEI_STYLESHEETS")
    os.environ["VARIANS_TEI_STYLESHEETS"] = str(folder)
    yield folder
    if previous is None:
        os.environ.pop("VARIANS_TEI_STYLESHEETS", None)
    else:
        os.environ["VARIANS_TEI_STYLESHEETS"] = previous
