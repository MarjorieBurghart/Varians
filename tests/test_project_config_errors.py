# -*- coding: utf-8 -*-
"""Erreurs de project.xml traduisibles : l'erreur porte une clé des
catalogues et ses paramètres ; l'interface affiche le message dans sa langue,
l'export en ligne de commande garde le texte français."""
from __future__ import annotations

import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from project_config import ProjectConfigError, load_project

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")


def _project_with_pivot(tmp_path, pivot):
    path = tmp_path / "project.xml"
    shutil.copy2(ROOT / "project.xml", path)
    path.write_text(path.read_text(encoding="utf-8").replace('<witnesses base="T1">', f'<witnesses base="{pivot}">'),
                    encoding="utf-8")
    return path


def test_unknown_pivot_witness_is_a_translatable_error(tmp_path):
    with pytest.raises(ProjectConfigError) as caught:
        load_project(_project_with_pivot(tmp_path, "Z"))
    error = caught.value
    assert isinstance(error, ValueError)                     # appels existants inchangés
    assert error.key == "project.error.unknown_pivot"
    assert error.values == {"witness": "Z", "witnesses": "T1, T2, P"}
    assert str(error).startswith("Témoin pivot inconnu")
    assert "de base" not in str(error)


def test_unknown_pivot_message_exists_in_the_seven_catalogs():
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        text = next(s.text for s in root.findall("string") if s.get("key") == "project.error.unknown_pivot")
        assert "{witness}" in text and "{witnesses}" in text, language


# --- Toutes les erreurs de project.xml --------------------------------------

VALID = ('<teiManuscriptProject version="1"><title>Essai</title>'
         '<edition file="xml/edition.xml"/><rendering xsltMode="builtin"/>'
         '<witnesses base="A"><witness id="A"/><witness id="B"/></witnesses>'
         '</teiManuscriptProject>')
WITNESSES = '<witnesses base="A"><witness id="A"/><witness id="B"/></witnesses>'
SCHEMA_SOURCES = "xml-model, project, none"


def _with(old, new):
    assert old in VALID
    return VALID.replace(old, new)


def _unknown(attribute, value, expected):
    return "project.error.unknown_value", {"attribute": attribute, "value": value, "expected": expected}


def _missing(element, attribute):
    return "project.error.missing_attribute", {"element": element, "attribute": attribute}


CASES = {
    "root": ("<autre/>", ("project.error.root", {})),
    "missing_elements": (_with(WITNESSES, ""), ("project.error.missing_elements", {})),
    "xslt_mode": (_with('xsltMode="builtin"', 'xsltMode="autre"'),
                  _unknown('<rendering xsltMode="…">', "autre", "builtin, file")),
    "schema_type": (_with("<rendering", '<schema type="xsd"/><rendering'),
                    _unknown('<schema type="…">', "xsd", "relaxng")),
    "schema_source": (_with("<rendering", '<schema source="ailleurs"/><rendering'),
                      _unknown('<schema source="…">', "ailleurs", SCHEMA_SOURCES)),
    "schema_file": (_with("<rendering", '<schema source="project"/><rendering'),
                    _missing('<schema source="project">', 'file="…"')),
    "document_schema": (_with("</teiManuscriptProject>",
                              '<documents><document file="xml/a.xml" schema="ailleurs"/></documents>'
                              "</teiManuscriptProject>"),
                        _unknown('<document file="xml/a.xml" schema="…">', "ailleurs", SCHEMA_SOURCES)),
    "document_schema_file": (_with("</teiManuscriptProject>",
                                   '<documents><document file="xml/a.xml" schema="file"/></documents>'
                                   "</teiManuscriptProject>"),
                             _missing('<document file="xml/a.xml" schema="file">', 'schemaFile="…"')),
    "witness_id": (_with('<witness id="A"/>', '<witness label="x"/><witness id="A"/>'),
                   _missing("<witness>", 'id="…"')),
    "image_source": (_with('<witness id="A"/>', '<witness id="A"><images type="autre"/></witness>'),
                     _unknown('<witness id="A"> <images type="…">', "autre", "auto, none, files, iiif")),
    "iiif_scope": (_with('<witness id="A"/>',
                         '<witness id="A"><images type="iiif" downloadScope="autre"/></witness>'),
                   _unknown('<witness id="A"> <images downloadScope="…">', "autre", "all, ocr")),
    "iiif_selection": (_with('<witness id="A"/>',
                             '<witness id="A"><images type="iiif" selectionMode="autre"/></witness>'),
                       _unknown('<witness id="A"> <images selectionMode="…">', "autre", "all, selected")),
    "alto_source": (_with('<witness id="A"/>', '<witness id="A"><alto type="autre"/></witness>'),
                    _unknown('<witness id="A"> <alto type="…">', "autre", "auto, files")),
    "no_witness": (_with(WITNESSES, '<witnesses base="A"/>'), ("project.error.no_witness", {})),
    "no_pivot": (_with(WITNESSES, '<witnesses><witness id="A"/><witness id="B"/></witnesses>'),
                 ("project.error.no_pivot", {})),
}


def _catalog(language):
    from i18n import I18nManager
    return I18nManager(ROOT / "i18n", language)


@pytest.mark.parametrize("name", sorted(CASES))
def test_every_project_error_is_translatable(tmp_path, name):
    text, (key, values) = CASES[name]
    path = tmp_path / "project.xml"
    path.write_text(text, encoding="utf-8")
    with pytest.raises(ProjectConfigError) as caught:
        load_project(path)
    error = caught.value
    assert (error.key, error.values) == (key, values)
    # Le texte français du code est celui du catalogue français.
    assert str(error) == _catalog("fr").tr(key, **values)
    assert _catalog("en").tr(key, **values) != str(error)


def test_missing_default_xslt_stays_a_file_not_found_error(tmp_path, monkeypatch):
    import project_config

    missing = tmp_path / "absente.xsl"
    monkeypatch.setattr(project_config, "DEFAULT_APPLICATION_XSLT", missing)
    path = tmp_path / "project.xml"
    path.write_text(VALID, encoding="utf-8")
    with pytest.raises(FileNotFoundError) as caught:
        load_project(path)
    error = caught.value
    assert (error.key, error.values) == ("project.error.default_xslt_missing", {"path": str(missing)})
    assert str(error) == _catalog("fr").tr(error.key, **error.values)


def test_no_untranslated_error_remains_in_project_config():
    source = (ROOT / "project_config.py").read_text(encoding="utf-8")
    assert "raise ValueError(" not in source and "raise FileNotFoundError(" not in source
