from pathlib import Path
import tempfile

from project_management import WitnessDraft, prepare_alignment_files_for_project, write_project_xml, ProjectDraft
from project_config import load_project
from varians_source import application_source


def _draft(root: Path, witnesses):
    (root/'xml').mkdir(parents=True, exist_ok=True)
    (root/'rendering').mkdir(exist_ok=True)
    (root/'i18n').mkdir(exist_ok=True)
    (root/'web_output').mkdir(exist_ok=True)
    for p in [root/'xml'/'edition.xml', root/'rendering'/'tei.css', root/'rendering'/'custom-elements.xml']:
        p.write_text('<x/>', encoding='utf-8')
    return ProjectDraft(
        title='x', edition=root/'xml'/'edition.xml', language='fr', fallback_language='en',
        translations_dir=root/'i18n', xslt=root/'rendering'/'tei-to-html.xsl',
        css=root/'rendering'/'tei.css', custom_elements=root/'rendering'/'custom-elements.xml',
        web_output_dir=root/'web_output', web_filename='viewer.html', witnesses=witnesses,
        base_witness=witnesses[0].id, xslt_mode='builtin', schema_mode='none'
    )


def test_sync_can_be_added_later_and_copied_into_project():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project'; root.mkdir()
        ext=Path(td)/'sync.json'; ext.write_text('{"meta":{"witness":"A"},"pages":[]}', encoding='utf-8')
        w=WitnessDraft('A','A',ext,'base',alignment_import_mode='copy')
        prepared=prepare_alignment_files_for_project(root,[w])
        assert prepared[0].alignment == (root/'alignments'/'A.json').resolve()
        assert prepared[0].alignment.read_text(encoding='utf-8').startswith('{')
        assert prepared[0].alignment_import_mode == 'keep'



def test_replacing_copied_sync_keeps_backup():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project'; root.mkdir(); (root/'alignments').mkdir()
        dest=root/'alignments'/'A.json'; dest.write_text('old',encoding='utf-8')
        ext=Path(td)/'new.json'; ext.write_text('new',encoding='utf-8')
        w=WitnessDraft('A','A',ext,'base',alignment_import_mode='copy')
        prepared=prepare_alignment_files_for_project(root,[w])[0]
        assert prepared.alignment.read_text(encoding='utf-8') == 'new'
        assert (root/'alignments'/'A.json.bak').read_text(encoding='utf-8') == 'old'


def test_sync_reference_mode_keeps_external_path():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project'; root.mkdir()
        ext=Path(td)/'sync.json'; ext.write_text('{}', encoding='utf-8')
        w=WitnessDraft('A','A',ext,'base',alignment_import_mode='reference')
        prepared=prepare_alignment_files_for_project(root,[w])
        assert prepared[0].alignment == ext.resolve()
        assert not (root/'alignments'/'A.json').exists()


def test_sync_can_be_removed_without_touching_other_resources():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project'; root.mkdir()
        w=WitnessDraft('A','A',None,'base',image_source_type='none',alto_source_type='auto')
        prepared=prepare_alignment_files_for_project(root,[w])[0]
        assert prepared.alignment is None
        assert prepared.image_source_type == 'none'
        assert prepared.alto_source_type == 'auto'


def test_project_roundtrip_without_sync_then_with_sync():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td)/'project'; root.mkdir()
        w=WitnessDraft('A','A',None,'base',image_source_type='none')
        draft=_draft(root,[w])
        path=write_project_xml(root/'project.xml',draft)
        assert load_project(path).base.alignment is None
        sync=root/'alignments'/'A.json'; sync.parent.mkdir(exist_ok=True); sync.write_text('{}',encoding='utf-8')
        draft.witnesses=[WitnessDraft('A','A',sync,'base',image_source_type='none')]
        write_project_xml(path,draft)
        cfg=load_project(path)
        assert cfg.base.alignment == sync.resolve()
        assert cfg.base.image_source_type == 'none'


def test_v076_editor_applies_alignment_before_independent_alto_and_images():
    source=application_source()
    # Red team 2 (B5) : l'alignement est lu par read_alignment_json, qui décrit
    # un fichier abîmé au lieu d'empêcher d'ouvrir le projet.
    assert 'read_alignment_json(w.alignment)' in source
    section=source[source.index('self.alignment_caches = {}'):source.index('self.witness_display_items = {}')]
    assert section.index('read_alignment_json(w.alignment)') < section.index('apply_witness_alto_policy') < section.index('apply_witness_image_policy')
    assert 'prepare_alignment_files_for_project' in source
