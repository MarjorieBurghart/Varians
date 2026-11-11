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


# --- Même schéma que l'édition ------------------------------------------------------------------

EDITION = """<?xml version="1.0" encoding="UTF-8"?>
<?xml-model href="../schema/edition.rng" type="application/xml" schematypens="http://relaxng.org/ns/structure/1.0"?>
<?xml-model href="https://example.org/regles.sch" schematypens="http://purl.oclc.org/dsdl/schematron"?>
<!-- <pas un élément> -->
<TEI xmlns="http://www.tei-c.org/ns/1.0"><text><body><p>texte</p></body></text></TEI>
"""


def _all_skeleton_after_models(text):
    """Le texte qui suit les déclarations <?xml-model?>."""
    return text[text.rindex("?>") + 2:].lstrip("\n")


def test_the_edition_schema_entry_uses_the_all_skeleton_and_the_edition_declarations(tmp_path):
    edition = tmp_path / "xml" / "edition.xml"
    template = document_templates.edition_template(EDITION)
    assert template.kind == "edition" and template.schema == "edition.rng"
    text = document_templates.document_text(template, tmp_path / "xml" / "personnes.xml",
                                             edition_text=EDITION, edition_path=edition)
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n'
                           '<?xml-model href="../schema/edition.rng" type="application/xml" '
                           'schematypens="http://relaxng.org/ns/structure/1.0"?>\n'
                           '<?xml-model href="https://example.org/regles.sch" '
                           'schematypens="http://purl.oclc.org/dsdl/schematron"?>\n<TEI ')
    all_text = document_templates.tei_template_text(document_templates.tei_template("All"))
    assert _all_skeleton_after_models(text) == _all_skeleton_after_models(all_text)
    ET.fromstring(text.encode("utf-8"))


@pytest.mark.parametrize("target, href", [
    ("xml/personnes.xml", "../schema/edition.rng"),
    ("personnes.xml", "schema/edition.rng"),
    ("xml/autorites/personnes.xml", "../../schema/edition.rng"),
    ("schema/personnes.xml", "edition.rng"),
])
def test_relative_schema_addresses_follow_the_new_document(tmp_path, target, href):
    text = document_templates.document_text(
        document_templates.edition_template(EDITION), tmp_path / target,
        edition_text=EDITION, edition_path=tmp_path / "xml" / "edition.xml")
    assert [model.href for model in detect_xml_models(text)] == [href, "https://example.org/regles.sch"]


def test_the_edition_schema_entry_needs_a_schema():
    bare = '<?xml version="1.0"?>\n<TEI xmlns="http://www.tei-c.org/ns/1.0"/>'
    assert document_templates.edition_template(bare) is None
    assert document_templates.edition_template(EDITION, schema_mode="none") is None
    # Une déclaration hors du prologue ne compte pas.
    inside = '<TEI xmlns="http://www.tei-c.org/ns/1.0"><?xml-model href="x.rng"?></TEI>'
    assert document_templates.edition_template(inside) is None


def test_with_the_project_schema_the_new_document_is_declared_with_it(tmp_path):
    schema = tmp_path / "schema" / "projet.rng"
    bare = '<?xml version="1.0"?>\n<TEI xmlns="http://www.tei-c.org/ns/1.0"/>'
    template = document_templates.edition_template(bare, schema_mode="file", project_schema=schema)
    assert template.schema == "projet.rng"
    target = tmp_path / "xml" / "personnes.xml"
    text = document_templates.document_text(template, target, edition_text=bare,
                                             edition_path=tmp_path / "xml" / "edition.xml")
    assert detect_xml_models(text) == ()
    assert text.startswith('<?xml version="1.0" encoding="UTF-8"?>\n<TEI ')
    config = document_templates.document_config(template, target)
    assert (config.path, config.schema_mode, config.schema) == (target, "file", schema)


def test_other_templates_are_declared_with_their_own_xml_model(tmp_path):
    target = tmp_path / "xml" / "lite.xml"
    config = document_templates.document_config(document_templates.tei_template("Lite"), target)
    assert (config.path, config.schema_mode, config.schema) == (target, "auto", None)
    config = document_templates.document_config(document_templates.edition_template(EDITION), target)
    assert (config.schema_mode, config.schema) == ("auto", None)


# --- Modèles du projet (dossier modeles/) -------------------------------------------------------

def _template(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


def test_the_project_templates_are_the_xml_files_of_its_modeles_folder(tmp_path):
    assert document_templates.PROJECT_TEMPLATES_FOLDER == "modeles"
    assert document_templates.project_templates(tmp_path) == []
    folder = tmp_path / "modeles"
    _template(folder, "lieux.xml", '<?xml-model href="../schema/lieux.rng"?>\n<listPlace/>')
    _template(folder, "Personnes.xml", "<listPerson/>")
    _template(folder, "notes.txt", "pas un modèle")
    _template(folder / "archives", "ancien.xml", "<ancien/>")
    templates = document_templates.project_templates(tmp_path)
    assert [(t.kind, t.name, t.schema) for t in templates] == [
        ("project", "lieux", "lieux.rng"), ("project", "Personnes", "")]
    assert templates[0].path == folder / "lieux.xml"


def test_a_project_template_is_copied_as_is_with_its_schema_address_recomputed(tmp_path):
    text = ('<?xml version="1.0" encoding="UTF-8"?>\n'
            "<?xml-model href='../schema/lieux.rng' type=\"application/xml\"?>\n"
            '<listPlace xmlns="http://www.tei-c.org/ns/1.0"><place xml:id="paris"/></listPlace>\n')
    _template(tmp_path / "modeles", "lieux.xml", text)
    template = document_templates.project_templates(tmp_path)[0]
    assert document_templates.document_text(template, tmp_path / "xml" / "lieux.xml") == text
    moved = document_templates.document_text(template, tmp_path / "xml" / "autorites" / "lieux.xml")
    assert moved == text.replace("'../schema/lieux.rng'", "'../../schema/lieux.rng'")


def test_absolute_schema_addresses_are_kept(tmp_path):
    for href in ("https://example.org/s.rng", "file:///srv/s.rng", str(tmp_path / "s.rng")):
        assert document_templates.rebase_href(href, tmp_path / "a", tmp_path / "b" / "c") == href


def test_an_empty_document_keeps_the_root_given(tmp_path):
    template = document_templates.empty_template()
    text = document_templates.document_text(template, tmp_path / "x.xml", root_name="listPlace")
    assert text == '<?xml version="1.0" encoding="UTF-8"?>\n<listPlace>\n</listPlace>\n'
    with pytest.raises(ValueError):
        document_templates.document_text(template, tmp_path / "x.xml", root_name="1 lieu")
