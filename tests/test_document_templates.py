# -*- coding: utf-8 -*-
"""Modèles de « Nouveau document XML » (document_templates, sans Qt).

Les modèles de la TEI sont ceux qu'Oxygen propose sous « TEI P5 » : les
fichiers de l'archive TEI P5 publiée (``xml/tei/custom/templates``), livrés
tels quels. À la création, seules leurs déclarations ``<?xml-model?>`` passent
de http à https.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET

import pytest

import document_templates
from schema_resolution import RELAXNG_NS, SCHEMATRON_NS, detect_xml_models

TEI = "{http://www.tei-c.org/ns/1.0}"
RELEASE = "https://www.tei-c.org/release/xml/tei/custom/schema/relaxng/"

# Ordre d'Oxygen : alphabétique, sans tenir compte de la casse.
OXYGEN_TEI_P5 = [
    "All", "All plus SVG and MathML", "Bare", "Basic", "Corpus", "Drama", "ENRICH Manuscript description",
    "Feature Structures", "jTEI Article", "Lite", "Manuscript description", "Minimal",
    "Minimal with XInclude", "ODD customization", "simplePrint", "Speech",
    "TEI for writing TEI Customizations", "TEI with MathML", "TEI with SVG",
    "TEI with W3C ITS for internationalization", "Tite",
]


def test_the_tei_templates_are_those_of_oxygen():
    assert document_templates.TEI_TEMPLATES_VERSION == "4.12.0"
    templates = document_templates.tei_templates()
    assert [template.name for template in templates] == OXYGEN_TEI_P5
    assert {template.kind for template in templates} == {"tei"}
    # Rien d'autre dans le dossier livré que les modèles et leurs notices.
    shipped = sorted(path.name for path in document_templates.TEI_TEMPLATES_DIR.iterdir())
    assert shipped == sorted([f"{name}.xml" for name in OXYGEN_TEI_P5] + ["LICENCE.txt", "LISEZMOI.md"])


def test_the_shipped_files_are_those_of_the_tei_release():
    for template in document_templates.tei_templates():
        raw = template.path.read_text(encoding="utf-8")
        assert raw.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<?xml-model href="http://www.tei-c.org/')
        assert raw.count('<?xml-model href="http://www.tei-c.org/release/xml/tei/custom/schema/relaxng/') == 2


def test_the_origin_and_licence_are_shipped():
    readme = (document_templates.TEI_TEMPLATES_DIR / "LISEZMOI.md").read_text(encoding="utf-8")
    assert "4.12.0" in readme and "TEI Consortium" in readme and "BSD" in readme
    licence = (document_templates.TEI_TEMPLATES_DIR / "LICENCE.txt").read_text(encoding="utf-8")
    assert "Creative Commons Attribution 3.0" in licence and "BSD 2-Clause" in licence


def test_a_tei_template_declares_its_schema_over_https():
    lite = document_templates.tei_template("Lite")
    raw = lite.path.read_text(encoding="utf-8")
    text = document_templates.tei_template_text(lite)
    models = detect_xml_models(text)
    assert [(model.href, model.schematypens) for model in models] == [
        (RELEASE + "tei_lite.rng", RELAXNG_NS), (RELEASE + "tei_lite.rng", SCHEMATRON_NS)]
    # Le reste est le fichier de la TEI, octet pour octet : l'image de
    # l'exemple garde son adresse.
    assert text.replace('href="https://www.tei-c.org/', 'href="http://www.tei-c.org/') == raw
    assert '<graphic url="http://www.tei-c.org/logos/TEI-glow.png"/>' in text


@pytest.mark.parametrize("name, root, schema", [
    ("All", "TEI", "tei_all.rng"),
    ("Corpus", "teiCorpus", "tei_corpus.rng"),
    ("Feature Structures", "fLib", "isofs.rng"),
    ("Tite", "text", "tei_tite.rng"),
    ("Manuscript description", "TEI", "tei_ms.rng"),
    ("ODD customization", "TEI", "tei_odds.rng"),
    ("TEI for writing TEI Customizations", "TEI", "tei_customization.rng"),
])
def test_each_template_has_its_root_and_its_schema(name, root, schema):
    template = document_templates.tei_template(name)
    assert template.schema == schema
    assert ET.fromstring(document_templates.tei_template_text(template).encode("utf-8")).tag == TEI + root


def test_every_tei_template_is_well_formed_and_declares_its_rng():
    for template in document_templates.tei_templates():
        text = document_templates.tei_template_text(template)
        ET.fromstring(text.encode("utf-8"))
        assert [model.href for model in detect_xml_models(text)] == [RELEASE + template.schema] * 2


def test_an_unknown_template_name_is_refused():
    with pytest.raises(KeyError):
        document_templates.tei_template("TEI Inconnue")
