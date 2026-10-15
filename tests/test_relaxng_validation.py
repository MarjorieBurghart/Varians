from pathlib import Path
from tempfile import TemporaryDirectory
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from relaxng_validation import (
    validate_relaxng, lxml_available, clear_relaxng_cache, relaxng_cache_info,
)
from project_management import ProjectDraft, WitnessDraft, write_project_xml
from project_config import load_project
from schema_resolution import detect_xml_models, resolve_schema, RELAXNG_NS, SCHEMATRON_NS

assert lxml_available(), "lxml doit être installé pour ce test"

with TemporaryDirectory() as td:
    td = Path(td)
    # Schéma modulaire : vérifie la résolution des include relatifs.
    (td / "content.rng").write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <define name="content"><text/></define>
</grammar>
''', encoding="utf-8")
    (td / "edition.rng").write_text('''<?xml version="1.0"?>
<grammar xmlns="http://relaxng.org/ns/structure/1.0">
  <include href="content.rng"/>
  <start>
    <element name="root">
      <element name="p"><ref name="content"/></element>
    </element>
  </start>
</grammar>
''', encoding="utf-8")

    ok = validate_relaxng("<root><p>texte</p></root>", td / "edition.rng")
    assert ok.schema_loaded and ok.well_formed and ok.valid and not ok.issues

    bad = validate_relaxng("<root><note>texte</note></root>", td / "edition.rng")
    assert bad.schema_loaded and bad.well_formed and not bad.valid and bad.issues
    assert any(issue.line == 1 for issue in bad.issues)

    malformed = validate_relaxng("<root><p></root>", td / "edition.rng")
    assert malformed.schema_loaded and not malformed.well_formed and not malformed.valid
    assert malformed.issues

    # V0.5.6 : le RNG compilé est réutilisé entre validations.
    clear_relaxng_cache()
    cached_ok = validate_relaxng("<root><p>texte</p></root>", td / "edition.rng")
    assert cached_ok.valid
    assert relaxng_cache_info()["compilations"] == 1
    cached_bad = validate_relaxng("<root><note>texte</note></root>", td / "edition.rng")
    assert not cached_bad.valid
    assert relaxng_cache_info()["compilations"] == 1

    # Modifier un include doit invalider automatiquement le cache.
    changed_include = (
        '<?xml version="1.0"?>\n'
        '<grammar xmlns="http://relaxng.org/ns/structure/1.0">\n'
        '  <define name="content"><empty/></define>\n'
        '</grammar>\n'
    )
    (td / "content.rng").write_text(changed_include, encoding="utf-8")
    changed = validate_relaxng("<root><p/></root>", td / "edition.rng")
    assert changed.valid
    assert relaxng_cache_info()["compilations"] == 2

    # xml-model : détection RNG + Schematron, même si le corps est cassé.
    xml_model_text = f'''<?xml-model href="edition.rng" type="application/xml" schematypens="{RELAXNG_NS}"?>
<?xml-model href="rules.sch" type="application/xml" schematypens="{SCHEMATRON_NS}"?>
<root><p></root>'''
    declarations = detect_xml_models(xml_model_text)
    assert len(declarations) == 2
    assert declarations[0].is_relaxng and declarations[1].is_schematron
    edition_path = td / "edition.xml"
    edition_path.write_text(xml_model_text, encoding="utf-8")
    resolved = resolve_schema(mode="auto", xml_text=xml_model_text, xml_path=edition_path)
    assert resolved.schema_path == (td / "edition.rng").resolve()
    assert len(resolved.schematron) == 1

    # Contrat project.xml : modes file / auto / none.
    project_dir = td / "project"
    project_dir.mkdir()
    edition = project_dir / "edition.xml"; edition.write_text("<root><p>texte</p></root>", encoding="utf-8")
    schema_dir = project_dir / "schema"; schema_dir.mkdir()
    schema = schema_dir / "edition.rng"; schema.write_text((td / "edition.rng").read_text(encoding="utf-8"), encoding="utf-8")
    alignment = project_dir / "A.json"; alignment.write_text("{}", encoding="utf-8")
    css = project_dir / "tei.css"; css.write_text("", encoding="utf-8")
    custom = project_dir / "custom-elements.xml"; custom.write_text("<customElements/>", encoding="utf-8")
    i18n = project_dir / "i18n"; i18n.mkdir()
    out = project_dir / "web_output"; out.mkdir()

    common = dict(
        title="Test RNG", edition=edition, language="fr", fallback_language="en",
        translations_dir=i18n, xslt=ROOT / "rendering" / "tei-to-html.xsl",
        css=css, custom_elements=custom, web_output_dir=out, web_filename="viewer.html",
        witnesses=[WitnessDraft("A", "A", alignment, "base")], base_witness="A",
        xslt_mode="builtin", schema_type="relaxng",
    )
    draft = ProjectDraft(**common, schema_mode="file", schema=schema)
    project_xml = write_project_xml(project_dir / "project.xml", draft)
    cfg = load_project(project_xml)
    assert cfg.schema_mode == "file"
    assert cfg.schema == schema.resolve()
    assert cfg.schema_type == "relaxng"

    draft_auto = ProjectDraft(**common, schema_mode="auto", schema=None)
    auto_xml = write_project_xml(project_dir / "project-auto.xml", draft_auto)
    cfg_auto = load_project(auto_xml)
    assert cfg_auto.schema_mode == "auto" and cfg_auto.schema is None

    draft_none = ProjectDraft(**common, schema_mode="none", schema=None)
    none_xml = write_project_xml(project_dir / "project-none.xml", draft_none)
    cfg_none = load_project(none_xml)
    assert cfg_none.schema_mode == "none" and cfg_none.schema is None

print("OK RELAX NG + xml-model")
