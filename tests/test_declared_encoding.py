# -*- coding: utf-8 -*-
"""Red team (intégrité, A4) : Varians lit et enregistre toujours en UTF-8.
Un fichier qui déclare un autre encodage (``encoding="ISO-8859-1"``) était
enregistré en UTF-8 sous cette déclaration : d'autres logiciels le lisaient
mal. L'enregistrement propose de corriger la déclaration
(``save_io.declared_encoding``)."""
from __future__ import annotations

import pytest

from save_io import declared_encoding, is_utf8


@pytest.mark.parametrize("text, name", [
    ('<?xml version="1.0" encoding="ISO-8859-1"?>\n<TEI/>', "ISO-8859-1"),
    ("<?xml version='1.0' encoding='windows-1252' standalone='yes'?><TEI/>", "windows-1252"),
    ('﻿<?xml version="1.0"\n      encoding = "UTF-16"?><TEI/>', "UTF-16"),
    ('<?xml version="1.0" encoding="utf-8"?><TEI/>', "utf-8"),
])
def test_the_declared_encoding_is_found_where_it_is(text, name):
    found = declared_encoding(text)
    assert found is not None and found.name == name and text[found.start:found.end] == name


@pytest.mark.parametrize("text", [
    '<TEI/>',
    '<?xml version="1.0"?><TEI/>',
    '<?xml-model href="x.rng" encoding="ISO-8859-1"?><TEI/>',
    '<!-- <?xml version="1.0" encoding="ISO-8859-1"?> --><TEI/>',
    ' <?xml version="1.0" encoding="ISO-8859-1"?><TEI/>',
])
def test_without_an_xml_declaration_giving_one_there_is_none(text):
    assert declared_encoding(text) is None


@pytest.mark.parametrize("name, utf8", [
    ("UTF-8", True), ("utf-8", True), ("utf8", True), (" UTF_8 ", True),
    ("ISO-8859-1", False), ("UTF-16", False), ("latin1", False), ("", False),
])
def test_utf8_names(name, utf8):
    assert is_utf8(name) is utf8
