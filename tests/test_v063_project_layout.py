from pathlib import Path
import tempfile

from project_config import load_project
from project_management import create_portable_project, WitnessDraft


ROOT = Path(__file__).resolve().parents[1]


def test_new_project_places_edition_in_xml_subdirectory():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        source = td / "source.xml"
        source.write_text("<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>", encoding="utf-8")
        alignment = td / "A.json"
        alignment.write_text('{"meta":{"witness":"A"},"pages":[]}', encoding="utf-8")
        target = td / "project"

        project_xml = create_portable_project(
            target_dir=target,
            title="Test",
            edition_source=source,
            witnesses=[WitnessDraft("A", "A", alignment, "base")],
            base_witness="A",
            template_root=ROOT,
            language="fr",
            fallback_language="en",
            xslt_mode="builtin",
            schema_mode="none",
        )

        assert project_xml == target / "project.xml"
        assert (target / "xml" / "edition.xml").is_file()
        assert not (target / "edition.xml").exists()
        text = project_xml.read_text(encoding="utf-8")
        assert 'file="xml/edition.xml"' in text
        cfg = load_project(project_xml)
        assert cfg.edition == (target / "xml" / "edition.xml").resolve()


def test_legacy_project_with_root_edition_still_opens():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "edition.xml").write_text("<TEI/>", encoding="utf-8")
        (td / "A.json").write_text('{"pages":[]}', encoding="utf-8")
        (td / "project.xml").write_text(
            """<?xml version='1.0' encoding='utf-8'?>
<teiManuscriptProject version='1'>
  <title>Legacy</title>
  <edition file='edition.xml'/>
  <schema type='relaxng' source='none'/>
  <interface language='fr' translationsDir='i18n' fallbackLanguage='en'/>
  <rendering xsltMode='builtin' css='rendering/tei.css' customElements='rendering/custom-elements.xml'/>
  <webViewer outputDir='web_output' filename='viewer.html'/>
  <witnesses base='A'><witness id='A' role='base' alignment='A.json'/></witnesses>
</teiManuscriptProject>""",
            encoding="utf-8",
        )
        cfg = load_project(td / "project.xml")
        assert cfg.edition == (td / "edition.xml").resolve()


def test_missing_edition_file_attribute_prefers_legacy_then_modern():
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        (td / "xml").mkdir()
        (td / "xml" / "edition.xml").write_text("<TEI/>", encoding="utf-8")
        (td / "A.json").write_text('{"pages":[]}', encoding="utf-8")
        project = td / "project.xml"
        project.write_text(
            """<teiManuscriptProject version='1'>
<title>No file attr</title><edition/><schema type='relaxng' source='none'/>
<interface language='fr' translationsDir='i18n' fallbackLanguage='en'/>
<rendering xsltMode='builtin' css='rendering/tei.css' customElements='rendering/custom-elements.xml'/>
<webViewer outputDir='web_output' filename='viewer.html'/>
<witnesses base='A'><witness id='A' role='base' alignment='A.json'/></witnesses>
</teiManuscriptProject>""",
            encoding="utf-8",
        )
        assert load_project(project).edition == (td / "xml" / "edition.xml").resolve()
        (td / "edition.xml").write_text("<TEI/>", encoding="utf-8")
        assert load_project(project).edition == (td / "edition.xml").resolve()
