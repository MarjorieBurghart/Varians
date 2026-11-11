# -*- coding: utf-8 -*-
"""Schémas sur lesquels libxml2 (lxml) tournait sans fin (relaxng_validation).

À la simplification du schéma (``xmlRelaxNGSimplify``), libxml2 retombe sur
un élément qui se contient lui-même (``oneOrMore(ref state)``) pendant qu'il
le simplifie ; la passe imbriquée déroule le ``<group>`` à un seul enfant du
contenu et déplace les références d'attributs, puis la première passe les
déplace de nouveau : la liste des attributs devient circulaire. C'est le cas
de ``state`` et ``trait`` dans les déclinaisons TEI sans le module
*certainty* (tei_ms, tei_corpus, tei_speech, tei_enrich). Varians déroule
lui-même ces motifs à un seul enfant avant la compilation : même langage.
"""
from __future__ import annotations

import subprocess
import sys
import textwrap
from pathlib import Path

from lxml import etree

import relaxng_validation
from relaxng_validation import clear_relaxng_cache, single_patterns_unwrapped, validate_relaxng

ROOT = Path(__file__).resolve().parents[1]
RNG = "http://relaxng.org/ns/structure/1.0"
# Le plus petit schéma trouvé qui fait tourner libxml2 sans fin.
LOOPING_SCHEMA = """<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><ref name="state"/></start>
  <define name="state">
    <element name="state">
      <group>
        <choice>
          <oneOrMore><ref name="state"/></oneOrMore>
          <ref name="p"/>
        </choice>
      </group>
      <ref name="att.a"/>
      <ref name="att.b"/>
      <empty/>
    </element>
  </define>
  <define name="p"><element name="p"><text/></element></define>
  <define name="att.a"><optional><attribute name="a"/></optional></define>
  <define name="att.b"><optional><attribute name="b"/></optional></define>
</grammar>
"""


def test_the_looping_schema_is_compiled_and_validates_correctly(tmp_path):
    # Dans un processus à part : une régression bloquerait sinon les tests.
    schema = tmp_path / "state.rng"
    schema.write_text(LOOPING_SCHEMA, encoding="utf-8")
    script = textwrap.dedent(f"""
        import sys
        sys.path.insert(0, {str(ROOT)!r})
        from relaxng_validation import validate_relaxng
        schema = {str(schema)!r}
        results = [validate_relaxng(xml, schema).valid for xml in (
            '<state><p>x</p></state>',
            '<state a="1" b="2"><state><p>x</p></state><state><p>y</p></state></state>',
            '<state/>',
            '<state c="1"><p>x</p></state>',
            '<state><p>x</p><state><p>y</p></state></state>',
        )]
        print(results)
    """)
    completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True, timeout=60)
    assert completed.returncode == 0, completed.stderr
    assert completed.stdout.strip() == "[True, True, False, False, False]"


def _patterns(text):
    tree = etree.ElementTree(etree.fromstring(text))
    single_patterns_unwrapped(tree)
    return etree.tostring(tree.getroot(), encoding="unicode")


def test_single_child_patterns_are_unwrapped():
    text = (f'<grammar xmlns="{RNG}"><start><element name="a">'
            '<group><choice><group><ref name="b"/></group></choice></group>'
            '<interleave><text/></interleave></element></start></grammar>')
    assert _patterns(text) == (f'<grammar xmlns="{RNG}"><start><element name="a">'
                               '<ref name="b"/><text/></element></start></grammar>')


def test_patterns_with_several_children_are_kept():
    text = (f'<grammar xmlns="{RNG}"><start><element name="a">'
            '<group><ref name="b"/><ref name="c"/></group>'
            '<choice><ref name="b"/><empty/></choice></element></start></grammar>')
    assert _patterns(text) == text


def test_annotations_of_an_unwrapped_pattern_are_kept():
    # Documentation et règles Schematron intégrées restent dans le schéma.
    text = (f'<grammar xmlns="{RNG}" xmlns:a="http://relaxng.org/ns/compatibility/annotations/1.0" '
            'xmlns:sch="http://purl.oclc.org/dsdl/schematron"><start><element name="a">'
            '<group><a:documentation>doc</a:documentation><ref name="b"/>'
            '<sch:pattern><sch:rule context="a"/></sch:pattern></group></element></start></grammar>')
    result = _patterns(text)
    assert "<group" not in result
    assert result.index("<ref") < result.index("<a:documentation>") < result.index("<sch:pattern>")


def test_the_schema_file_is_not_modified(tmp_path):
    schema = tmp_path / "state.rng"
    schema.write_text(LOOPING_SCHEMA.replace('<ref name="state"/></oneOrMore>', '<ref name="p"/></oneOrMore>'),
                      encoding="utf-8")
    before = schema.read_bytes()
    clear_relaxng_cache()
    assert validate_relaxng("<state><p>x</p></state>", schema).valid
    assert schema.read_bytes() == before
    assert relaxng_validation.relaxng_cache_info()["compilations"] >= 1
