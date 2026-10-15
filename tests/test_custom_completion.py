from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from custom_completion import load_custom_completion, merge_suggestion_sources


def test_backward_compatible_attributes_and_defaults(tmp_path):
    p = tmp_path / "custom-elements.xml"
    p.write_text('''<customElements>
      <element name="rdg">
        <attribute name="wit"/>
        <attribute name="type" defaultValue="variant"/>
      </element>
    </customElements>''', encoding="utf-8")
    cfg = load_custom_completion(p)
    assert cfg.element_names() == ("rdg",)
    attrs = cfg.attributes_for("rdg")
    assert [(a.name, a.default_value, a.has_default) for a in attrs] == [
        ("wit", "", False), ("type", "variant", True)
    ]


def test_explicit_values_and_replace_mode(tmp_path):
    p = tmp_path / "custom-elements.xml"
    p.write_text('''<customElements>
      <element name="hi">
        <attribute name="rend" valuesMode="replace">
          <value>italic</value><value>bold</value><value>italic</value>
        </attribute>
      </element>
    </customElements>''', encoding="utf-8")
    cfg = load_custom_completion(p)
    values, mode = cfg.attribute_values("hi", "rend")
    assert values == ("italic", "bold")
    assert mode == "replace"


def test_dynamic_witness_values(tmp_path):
    p = tmp_path / "custom-elements.xml"
    p.write_text('''<customElements>
      <element name="rdg">
        <attribute name="wit" valuesMode="replace">
          <values source="witnesses" prefix="#"/>
        </attribute>
      </element>
    </customElements>''', encoding="utf-8")
    cfg = load_custom_completion(p)
    values, mode = cfg.attribute_values("rdg", "wit", ("T1", "T2", "P"))
    assert values == ("#T1", "#T2", "#P")
    assert mode == "replace"


def test_merge_sources_keeps_rng_and_project_distinct():
    assert merge_suggestion_sources(("a", "b"), ("b", "c")) == [
        ("a", "rng"), ("b", "both"), ("c", "custom")
    ]
    assert merge_suggestion_sources(("yes", "no"), ("maybe", "no"), "replace") == [
        ("maybe", "custom"), ("no", "both")
    ]


def test_prefixed_names_match_local_names(tmp_path):
    p = tmp_path / "custom-elements.xml"
    p.write_text('''<customElements>
      <element name="rdg"><attribute name="xml:id"><value>x</value></attribute></element>
    </customElements>''', encoding="utf-8")
    cfg = load_custom_completion(p)
    assert cfg.attribute_names("tei:rdg") == ("xml:id",)
    assert cfg.attribute_values("tei:rdg", "id")[0] == ("x",)
