# -*- coding: utf-8 -*-
"""Complétion des fichiers Schematron (V0.9.2.4), sans Qt : schéma ISO
Schematron livré avec Varians, noms préfixés comme dans le fichier, éléments
étrangers non complétés, valeurs proposées pour ``severity``, ``role`` et
``queryBinding``."""
from __future__ import annotations

from schematron_completion import (SCHEMATRON_SCHEMA, SUGGESTED_VALUES, SchematronCompletionModel,
                                   attribute_names, attribute_values, element_names)
from xml_roots import schematron_info

SCH_NS = "http://purl.oclc.org/dsdl/schematron"


def _info(prefix="sch"):
    if prefix:
        return schematron_info(f'<{prefix}:schema xmlns:{prefix}="{SCH_NS}">')
    return schematron_info(f'<schema xmlns="{SCH_NS}">')


def test_the_completion_reads_the_bundled_schema():
    assert SCHEMATRON_SCHEMA.name == "iso-schematron.rng" and SCHEMATRON_SCHEMA.is_file()


def test_the_root_is_a_schema_or_a_library():
    assert element_names(_info(), None) == ("sch:library", "sch:schema")
    assert element_names(_info(""), None) == ("library", "schema")


def test_the_novelties_of_2020_are_proposed():
    assert {"sch:group", "sch:rules", "sch:param"} <= set(element_names(_info(), "sch:schema"))
    assert "visit-each" in attribute_names(_info(), "sch:rule")
    assert {"from", "when"} <= set(attribute_names(_info(), "sch:phase"))
    assert "as" in attribute_names(_info(), "sch:let")
    assert "schematronEdition" in attribute_names(_info(), "sch:schema")
    assert "sch:rule" in element_names(_info(), "sch:group")


def test_the_children_follow_the_order_of_the_schema():
    names = element_names(_info(), "sch:schema")
    assert {"sch:ns", "sch:pattern", "sch:phase", "sch:let", "sch:title", "sch:include"} <= set(names)
    # Après un groupe de règles, plus de déclaration d'espace de noms.
    after = element_names(_info(), "sch:schema", ("sch:ns", "sch:pattern"))
    assert "sch:pattern" in after and "sch:diagnostics" in after and "sch:ns" not in after
    assert element_names(_info(), "sch:rule", ("sch:assert",)) == (
        "sch:assert", "sch:extends", "sch:include", "sch:p", "sch:report")
    assert element_names(_info(""), "rule") == ("assert", "extends", "include", "let", "p", "report")


def test_a_foreign_element_is_not_completed():
    assert element_names(_info(), "xsl:function") == ()
    assert element_names(_info(), "rule") == ()                     # sans préfixe : hors de Schematron
    assert attribute_names(_info(), "xsl:function") == ()
    assert attribute_values(_info(), "xsl:function", "as") == ()


def test_the_attributes_of_an_assertion():
    names = attribute_names(_info(), "sch:assert")
    assert {"test", "role", "severity", "id", "diagnostics", "flag"} <= set(names)
    assert "context" not in names
    assert "context" in attribute_names(_info(""), "rule")


def test_values_from_the_schema_and_suggested_values():
    assert attribute_values(_info(), "sch:pattern", "abstract") == ("false", "true")
    assert attribute_values(_info(), "sch:assert", "severity") == SUGGESTED_VALUES["severity"]
    assert attribute_values(_info(), "sch:report", "role") == SUGGESTED_VALUES["role"]
    assert attribute_values(_info(), "sch:schema", "queryBinding") == SUGGESTED_VALUES["queryBinding"]
    assert "xslt2" in SUGGESTED_VALUES["queryBinding"] and "warning" in SUGGESTED_VALUES["severity"]
    assert attribute_values(_info(), "sch:assert", "test") == ()


def test_the_model_has_the_interface_of_the_rng_completion():
    model = SchematronCompletionModel(_info())
    assert "sch:rule" in model.child_elements_at("sch:pattern")
    assert "context" in model.allowed_attributes("sch:rule")
    assert model.allowed_attribute_values("sch:assert", "severity") == SUGGESTED_VALUES["severity"]
