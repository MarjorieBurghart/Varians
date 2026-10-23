# -*- coding: utf-8 -*-
"""Complétion des feuilles XSLT (V0.9.2.1), sans Qt : schéma XSLT 3.0 livré
avec Varians, noms préfixés comme dans la feuille, éléments résultats
littéraux, éléments et attributs d'XSLT 1.0 seuls pour une feuille 1.0."""
from __future__ import annotations

import pytest

from xslt_completion import (LITERAL_RESULT_ATTRIBUTES, XSLT10_ATTRIBUTES, XSLT_SCHEMA, attribute_names,
                             attribute_values, completion_model, element_names)
from xslt_scenarios import stylesheet_info

XSL = 'xmlns:xsl="http://www.w3.org/1999/XSL/Transform"'


def _info(version="3.0", prefix="xsl"):
    declaration = f'xmlns:{prefix}="http://www.w3.org/1999/XSL/Transform"' if prefix \
        else 'xmlns="http://www.w3.org/1999/XSL/Transform"'
    root = f"{prefix}:stylesheet" if prefix else "stylesheet"
    return stylesheet_info(f'<{root} version="{version}" {declaration}>')


V1, V3 = "1.0", "3.0"


# --- Schéma livré ------------------------------------------------------------------------------

def test_the_schema_comes_with_its_licence_and_its_source():
    text = XSLT_SCHEMA.read_text(encoding="utf-8")
    assert "Copyright (c) 2010-2016, Mohamed ZERGAOUI (Innovimax)" in text
    assert "THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS" in text
    source = XSLT_SCHEMA.with_suffix(".rnc").read_text(encoding="utf-8")
    assert source.startswith("# XSLT 3.0 Relax NG Schema")
    readme = (XSLT_SCHEMA.parent / "LISEZMOI.md").read_text(encoding="utf-8")
    assert "w3c/qtspecs" in readme and "rnc2rng" in readme


def test_the_schema_is_a_correct_relax_ng_schema():
    from lxml import etree
    etree.RelaxNG(etree.parse(str(XSLT_SCHEMA)))


def test_every_xslt_1_element_is_in_the_schema():
    model = completion_model()
    assert len(XSLT10_ATTRIBUTES) == 35
    known = set(model.start_elements) | {name for parent in XSLT10_ATTRIBUTES for name in model.child_elements(parent)}
    assert set(XSLT10_ATTRIBUTES) <= known | {"stylesheet", "transform"}
    for element, attributes in XSLT10_ATTRIBUTES.items():
        assert set(attributes) <= set(model.allowed_attributes(element)), element


# --- Éléments ----------------------------------------------------------------------------------

def test_the_root_is_a_stylesheet():
    assert element_names(_info(V3), None) == ("xsl:package", "xsl:stylesheet", "xsl:transform")
    assert element_names(_info(V1), None) == ("xsl:stylesheet", "xsl:transform")


def test_the_declarations_of_a_stylesheet():
    names = element_names(_info(V3), "xsl:stylesheet")
    assert {"xsl:template", "xsl:function", "xsl:mode", "xsl:output", "xsl:param"} <= set(names)
    assert element_names(_info(V1), "xsl:stylesheet") == tuple(f"xsl:{name}" for name in (
        "attribute-set", "decimal-format", "import", "include", "key", "namespace-alias", "output", "param",
        "preserve-space", "strip-space", "template", "variable"))


def test_the_instructions_of_a_template_follow_the_position():
    names = element_names(_info(V3), "xsl:template")
    assert {"xsl:param", "xsl:apply-templates", "xsl:value-of", "xsl:sequence", "xsl:for-each-group"} <= set(names)
    assert "xsl:template" not in names
    after = element_names(_info(V3), "xsl:template", before=("xsl:variable",))
    assert "xsl:param" not in after and "xsl:value-of" in after
    old = element_names(_info(V1), "xsl:template")
    assert {"xsl:param", "xsl:value-of", "xsl:apply-templates"} <= set(old)
    assert not {"xsl:sequence", "xsl:for-each-group", "xsl:try"} & set(old)
    assert element_names(_info(V3), "xsl:choose") == ("xsl:when",)                     # d'abord un xsl:when
    assert element_names(_info(V3), "xsl:choose", before=("xsl:when",)) == ("xsl:otherwise", "xsl:when")


@pytest.mark.parametrize("parent", ["div", "html:p", "text", "tei:text"])
def test_a_literal_result_element_contains_instructions(parent):
    # « text » sans préfixe est un élément résultat (TEI, HTML…), pas xsl:text.
    names = element_names(_info(V3), parent)
    assert {"xsl:value-of", "xsl:apply-templates", "xsl:if"} <= set(names)
    assert not {"xsl:template", "xsl:param", "xsl:when"} & set(names)
    assert "xsl:sequence" not in element_names(_info(V1), parent)


def test_the_prefix_is_that_of_the_stylesheet():
    assert "x:template" in element_names(_info(V3, "x"), "x:stylesheet")
    assert "template" in element_names(_info(V3, ""), "stylesheet")
    # Sans préfixe pour XSLT, un élément préfixé est un élément résultat.
    assert "value-of" in element_names(_info(V3, ""), "h:div")


# --- Attributs ---------------------------------------------------------------------------------

def test_the_attributes_of_an_xslt_element():
    names = attribute_names(_info(V3), "xsl:template")
    assert {"match", "mode", "name", "priority", "as", "visibility"} <= set(names)
    assert not [name for name in names if name.startswith("_")]          # attributs « fantômes » d'XSLT 3.0
    assert attribute_names(_info(V1), "xsl:template") == ("match", "mode", "name", "priority")
    assert "html-version" in attribute_names(_info(V3), "xsl:output")
    assert attribute_names(_info(V1), "xsl:output") == tuple(sorted(XSLT10_ATTRIBUTES["output"]))
    assert attribute_names(_info(V1), "xsl:sequence") == ()                # pas en XSLT 1.0


def test_the_xsl_attributes_of_a_literal_result_element():
    assert attribute_names(_info(V1), "div") == tuple(f"xsl:{name}" for name in sorted(LITERAL_RESULT_ATTRIBUTES[V1]))
    assert set(LITERAL_RESULT_ATTRIBUTES[V1]) == {"exclude-result-prefixes", "extension-element-prefixes",
                                                  "use-attribute-sets", "version"}
    names = attribute_names(_info(V3, "x"), "tei:p")
    assert {"x:use-attribute-sets", "x:expand-text", "x:use-when"} <= set(names)
    assert attribute_names(_info(V3, ""), "h:div") == ()                 # aucun préfixe pour les écrire


def test_the_finite_values_of_an_attribute():
    assert attribute_values(_info(V3), "xsl:mode", "on-no-match") == (
        "deep-copy", "deep-skip", "fail", "shallow-copy", "shallow-skip", "text-only-copy")
    assert attribute_values(_info(V3), "xsl:number", "level") == ("any", "multiple", "single")
    assert attribute_values(_info(V3), "xsl:sort", "order") == ()          # valeur calculée (AVT) : ouverte
    assert attribute_values(_info(V3), "div", "class") == ()
