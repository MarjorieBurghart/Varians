from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from rng_completion import load_completion_model, analyze_xml_context


def _schema(tmp_path):
    inc = tmp_path / "inline.rng"
    inc.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <define name="hi">
    <element name="hi">
      <optional><attribute name="rend"><text/></attribute></optional>
      <text/>
    </element>
  </define>
</grammar>''', encoding="utf-8")
    main = tmp_path / "schema.rng"
    main.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <include href="inline.rng"/>
  <start><ref name="TEI"/></start>
  <define name="TEI"><element name="TEI"><ref name="p"/></element></define>
  <define name="p">
    <element name="p">
      <optional><attribute name="xml:id"><text/></attribute></optional>
      <zeroOrMore><choice><ref name="hi"/><ref name="app"/></choice></zeroOrMore>
    </element>
  </define>
  <define name="app"><element name="app"><oneOrMore><ref name="rdg"/></oneOrMore></element></define>
  <define name="rdg"><element name="rdg"><attribute name="wit"><text/></attribute><text/></element></define>
</grammar>''', encoding="utf-8")
    return main


def test_model_children_attributes_and_include(tmp_path):
    model = load_completion_model(_schema(tmp_path))
    assert model.start_elements == ("TEI",)
    assert model.child_elements("TEI") == ("p",)
    assert model.child_elements("p") == ("app", "hi")
    assert model.child_elements("app") == ("rdg",)
    assert model.allowed_attributes("p") == ("xml:id",)
    assert model.allowed_attributes("hi") == ("rend",)
    assert model.allowed_attributes("rdg") == ("wit",)
    assert model.child_elements_at("app", ()) == ("rdg",)
    assert model.child_elements_at("app", ("rdg",)) == ("rdg",)


def test_context_element_content_and_partial_name():
    text = "<TEI><p>uerbum"
    ctx = analyze_xml_context(text, len(text))
    assert ctx.kind == "element"
    assert ctx.parent_element == "p"
    assert ctx.prefix == ""

    text = "<TEI><p><r"
    ctx = analyze_xml_context(text, len(text))
    assert ctx.kind == "element"
    assert ctx.parent_element == "p"
    assert ctx.prefix == "r"
    assert ctx.typed_lt is True
    assert text[ctx.replace_start:ctx.replace_end] == "r"


def test_context_attribute_and_existing_attributes():
    text = '<TEI><p xml:id="x" re'
    ctx = analyze_xml_context(text, len(text))
    assert ctx.kind == "attribute"
    assert ctx.current_element == "p"
    assert ctx.parent_element == "TEI"
    assert ctx.prefix == "re"
    assert ctx.existing_attributes == ("xml:id",)
    assert text[ctx.replace_start:ctx.replace_end] == "re"


def test_context_inside_attribute_value_is_detected():
    text = '<TEI><p xml:id="abc'
    ctx = analyze_xml_context(text, len(text))
    assert ctx.kind == "attribute_value"
    assert ctx.current_element == "p"
    assert ctx.current_attribute == "xml:id"
    assert ctx.prefix == "abc"


def test_context_survives_incomplete_document_after_cursor():
    text = "<TEI><p>abc<app><rdg>foo</rdg></app>"
    pos = text.index("abc") + 3
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == "element"
    assert ctx.parent_element == "p"


def test_context_cursor_after_complete_element_name_before_gt_is_attribute():
    text = '<TEI><app><rdg>'
    pos = text.index('>')  # wrong first >? explicitly locate rdg closing bracket below
    pos = text.rfind('>')
    ctx = analyze_xml_context(text, pos)  # <rdg|>
    assert ctx.kind == 'attribute'
    assert ctx.current_element == 'rdg'
    assert ctx.parent_element == 'app'
    assert ctx.prefix == ''


def test_context_attribute_after_space_before_gt():
    text = '<TEI><app><rdg >'
    pos = text.rfind('>')  # <rdg |>
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == 'attribute'
    assert ctx.current_element == 'rdg'
    assert ctx.parent_element == 'app'
    assert ctx.prefix == ''


def test_context_partial_attribute_before_gt():
    text = '<TEI><app><rdg wi>'
    pos = text.rfind('>')  # <rdg wi|>
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == 'attribute'
    assert ctx.current_element == 'rdg'
    assert ctx.parent_element == 'app'
    assert ctx.prefix == 'wi'
    assert text[ctx.replace_start:ctx.replace_end] == 'wi'


def test_context_after_closed_opening_tag_is_element_content():
    text = '<TEI><app><rdg>'
    pos = len(text)  # <rdg>| : maintenant dans le contenu de rdg
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == 'element'
    assert ctx.parent_element == 'rdg'


def _sequence_schema(tmp_path):
    path = tmp_path / "sequence.rng"
    path.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><ref name="root"/></start>
  <define name="root">
    <element name="root">
      <group>
        <element name="a"><empty/></element>
        <optional><element name="b"><empty/></element></optional>
        <choice>
          <element name="c"><empty/></element>
          <element name="d"><empty/></element>
        </choice>
        <zeroOrMore><element name="e"><empty/></element></zeroOrMore>
        <element name="f"><empty/></element>
      </group>
    </element>
  </define>
</grammar>''', encoding="utf-8")
    return path


def _advanced_schema(tmp_path):
    path = tmp_path / "advanced.rng"
    path.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><ref name="root"/></start>
  <define name="root">
    <element name="root">
      <choice>
        <element name="seq">
          <group>
            <element name="a"><empty/></element>
            <element name="b"><empty/></element>
          </group>
        </element>
        <element name="inter">
          <interleave>
            <element name="a"><empty/></element>
            <element name="b"><empty/></element>
          </interleave>
        </element>
        <element name="repeat">
          <group>
            <oneOrMore><element name="a"><empty/></element></oneOrMore>
            <element name="b"><empty/></element>
          </group>
        </element>
        <element name="branch">
          <choice>
            <group><element name="a"><empty/></element><element name="b"><empty/></element></group>
            <group><element name="a"><empty/></element><element name="c"><empty/></element></group>
          </choice>
        </element>
        <element name="refseq"><ref name="model.seq"/></element>
      </choice>
    </element>
  </define>
  <define name="model.seq"><ref name="ref.a"/><ref name="ref.b"/></define>
  <define name="ref.a"><element name="a"><empty/></element></define>
  <define name="ref.b"><element name="b"><empty/></element></define>
</grammar>''', encoding="utf-8")
    return path


def test_position_sensitive_group_optional_choice_and_repeat(tmp_path):
    model = load_completion_model(_sequence_schema(tmp_path))

    # La liste historique reste volontairement large pour compatibilité.
    assert model.child_elements("root") == ("a", "b", "c", "d", "e", "f")

    assert model.child_elements_at("root", ()) == ("a",)
    assert model.child_elements_at("root", ("a",)) == ("b", "c", "d")
    assert model.child_elements_at("root", ("a", "b")) == ("c", "d")
    assert model.child_elements_at("root", ("a", "c")) == ("e", "f")
    assert model.child_elements_at("root", ("a", "c", "e")) == ("e", "f")
    assert model.child_elements_at("root", ("a", "c", "f")) == ()


def test_position_sensitive_interleave_one_or_more_and_choice_prefix(tmp_path):
    model = load_completion_model(_advanced_schema(tmp_path))

    assert model.child_elements_at("seq", ()) == ("a",)
    assert model.child_elements_at("seq", ("a",)) == ("b",)
    assert model.child_elements_at("seq", ("a", "b")) == ()

    assert model.child_elements_at("inter", ()) == ("a", "b")
    assert model.child_elements_at("inter", ("a",)) == ("b",)
    assert model.child_elements_at("inter", ("b",)) == ("a",)

    assert model.child_elements_at("repeat", ()) == ("a",)
    assert model.child_elements_at("repeat", ("a",)) == ("a", "b")
    assert model.child_elements_at("repeat", ("a", "a")) == ("a", "b")
    assert model.child_elements_at("repeat", ("a", "b")) == ()

    assert model.child_elements_at("branch", ()) == ("a",)
    assert model.child_elements_at("branch", ("a",)) == ("b", "c")

    # RELAX NG autorise pattern+ : plusieurs <ref> frères valent une séquence,
    # forme très utilisée dans les schémas TEI générés.
    assert model.child_elements_at("refseq", ()) == ("a",)
    assert model.child_elements_at("refseq", ("a",)) == ("b",)
    assert model.child_elements_at("refseq", ("a", "b")) == ()


def test_context_collects_direct_siblings_around_cursor():
    text = '<root><a></a>TEXT<c></c><f></f></root>'
    pos = text.index('TEXT') + len('TEXT')
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == 'element'
    assert ctx.parent_element == 'root'
    assert ctx.preceding_siblings == ('a',)
    assert ctx.following_siblings == ('c', 'f')


def test_suffix_filters_insertions_at_middle_of_existing_sequence(tmp_path):
    model = load_completion_model(_sequence_schema(tmp_path))

    # Schéma: a, b?, (c|d), e*, f
    # Contenu existant: a | c f. Sans regarder à droite, b/c/d sont possibles
    # après a ; en tenant compte du suffixe c,f, seul b est une insertion valide.
    assert model.child_elements_at("root", ("a",), ("c", "f")) == ("b",)

    # Après c, juste avant le f déjà présent, un e répétable peut être inséré,
    # mais pas un second f.
    assert model.child_elements_at("root", ("a", "c"), ("f",)) == ("e",)


def test_suffix_can_make_insertion_impossible_in_complete_sequence(tmp_path):
    model = load_completion_model(_advanced_schema(tmp_path))
    # Dans a,b, placé entre a et le b déjà existant, aucun nouvel élément n'est
    # insérable : proposer b ici créerait a,b,b.
    assert model.child_elements_at("seq", ("a",), ("b",)) == ()


def test_invalid_existing_prefix_falls_back_to_broad_parent_list(tmp_path):
    model = load_completion_model(_sequence_schema(tmp_path))
    # Pendant la réparation d'un XML déjà invalide, conserver une complétion
    # utile plutôt que de ne rien proposer.
    assert model.child_elements_at("root", ("z",)) == ("a", "b", "c", "d", "e", "f")


def _attribute_values_schema(tmp_path):
    path = tmp_path / "attribute-values.rng"
    path.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <start><ref name="root"/></start>
  <define name="yes.no">
    <choice><value>yes</value><value>no</value></choice>
  </define>
  <define name="root">
    <element name="root">
      <optional><attribute name="break"><ref name="yes.no"/></attribute></optional>
      <optional><attribute name="place"><choice><value>above</value><value>below</value><value>margin</value></choice></attribute></optional>
      <optional><attribute name="free"><text/></attribute></optional>
      <optional><attribute name="mixed"><choice><value>a</value><data type="token"/></choice></attribute></optional>
      <empty/>
    </element>
  </define>
</grammar>''', encoding="utf-8")
    return path


def test_finite_attribute_values_are_indexed_conservatively(tmp_path):
    model = load_completion_model(_attribute_values_schema(tmp_path))
    assert model.allowed_attribute_values("root", "break") == ("no", "yes")
    assert model.allowed_attribute_values("root", "place") == ("above", "below", "margin")
    assert model.allowed_attribute_values("root", "free") == ()
    # Une branche ouverte ne doit pas transformer la seule valeur littérale en
    # pseudo-liste exhaustive.
    assert model.allowed_attribute_values("root", "mixed") == ()


def test_context_inside_quoted_attribute_value_is_completed():
    text = '<root break="y">'
    pos = text.index('y') + 1
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == "attribute_value"
    assert ctx.current_element == "root"
    assert ctx.current_attribute == "break"
    assert ctx.prefix == "y"
    assert text[ctx.replace_start:ctx.replace_end] == "y"
    assert ctx.quote_char == '"'


def test_context_attribute_value_replaces_whole_existing_value():
    text = "<root place='above'>"
    pos = text.index("b") + 1
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == "attribute_value"
    assert ctx.current_attribute == "place"
    assert ctx.prefix == "ab"
    assert text[ctx.replace_start:ctx.replace_end] == "above"
    assert ctx.quote_char == "'"


def test_finite_values_ignore_foreign_annotations(tmp_path):
    path = tmp_path / "annotated.rng"
    path.write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0" xmlns:a="http://relaxng.org/ns/compatibility/annotations/1.0">
  <start><element name="lb"><attribute name="break"><a:documentation>TEI breaking</a:documentation><choice><value>yes</value><value>no</value></choice></attribute><empty/></element></start>
</grammar>''', encoding="utf-8")
    model = load_completion_model(path)
    assert model.allowed_attribute_values("lb", "break") == ("no", "yes")


def test_context_after_complete_attribute_before_self_closing_gt_is_attribute():
    text = '<TEI><lb edRef="#T1"/>'
    pos = text.index('/>')  # <lb edRef="#T1"|/>
    ctx = analyze_xml_context(text, pos)
    assert ctx.kind == 'attribute'
    assert ctx.current_element == 'lb'
    assert ctx.parent_element == 'TEI'
    assert ctx.prefix == ''
    assert ctx.existing_attributes == ('edRef',)
