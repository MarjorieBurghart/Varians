"""Regression: Varians-Synchro partial physical pages and unnumbered TEI lb."""
from pathlib import Path
import json
import xml.etree.ElementTree as ET

from project_management import WitnessDraft, LocalImageDraft
from tei_facsimile import FacsimilePage, sync_facsimile_text
from tei_pivot_scaffold import build_pivot_plan, render_pivot_scaffold
from project_management import minimal_tei_text

NS = {'t': 'http://www.tei-c.org/ns/1.0'}


def _setup(tmp_path, count=5):
    folios = ('2v', '3r', '3v', '4r', '4v')
    sizes = (28, 66, 66, 51, 0)
    rows = [
        {'id': f'opaque-{folio}', 'label':f'BSB Clm 14713 {folio}',
         'image': {'type':'file', 'path': str(tmp_path / f'BSB Clm 14713 {folio}.jpg')},
         'lines': [{'line':n,'alto_id':f'line-{folio}-{n}', 'order':n}
                   for n in (range(41,69) if folio=='2v' else range(1,size+1))]}
        for folio,size in zip(folios,sizes)
    ]
    source = tmp_path / 'Mu.json'
    source.write_text(json.dumps({'meta':{'witness':'Mu','source':'Varians-Synchro'},'pages':rows}), encoding='utf8')
    imagefiles = [LocalImageDraft(tmp_path / f'BSB Clm 14713 {folio}.jpg',
                                 f'BSB Clm 14713 {folio}', surface_id=f'Mu-p{i:04d}')
                  for i,folio in enumerate(folios[:count],1)]
    w = WitnessDraft('Mu', 'Pivot', image_source_type='files', image_files=imagefiles, alignment=source)
    facsimiles = [FacsimilePage('Mu',f'Mu-p{i:04d}',f'BSB Clm 14713 {folio}',
                                f'images/{folio}.jpg') for i,folio in enumerate(folios[:count],1)]
    doc = sync_facsimile_text(minimal_tei_text('Test',[w],'Mu'),facsimiles)[0]
    return w, doc


def test_mu_five_pages_partial_2v_and_empty_4v(tmp_path):
    witness, xml = _setup(tmp_path)
    plan = build_pivot_plan([witness],'Mu',tmp_path,tmp_path/'edition.xml')
    assert [p.line_count for p in plan.pages] == [28,66,66,51,0]
    assert [p.evidence for p in plan.pages] == ['JSON partiel','JSON','JSON','JSON','JSON sans lignes']
    assert len(plan.pages)==5 and plan.line_count==211
    assert any('exhaustivité' in w and '2v' in w for w in plan.warnings)
    output=render_pivot_scaffold(xml,plan)
    body=ET.fromstring(output).find('.//t:body/t:p',NS)
    pbs=[(i,c) for i,c in enumerate(body) if c.tag.endswith('}pb')]
    assert len(pbs)==5 and len([c for c in body if c.tag.endswith('}lb')])==211
    assert [b.get('n') for _,b in pbs]==[f'BSB Clm 14713 {folio}' for folio in ('2v','3r','3v','4r','4v')]
    # 28 line markers belong *between* the 2v and 3r page breaks.
    assert pbs[1][0] - pbs[0][0] - 1 == 28
    assert pbs[2][0] - pbs[1][0] - 1 == 66
    assert pbs[3][0] - pbs[2][0] - 1 == 66
    assert pbs[4][0] - pbs[3][0] - 1 == 51
    assert all(c.attrib=={'edRef':'#Mu'} for c in body if c.tag.endswith('}lb'))


def test_sync_empty_page_not_in_explicit_selection_never_materialized(tmp_path):
    witness, xml = _setup(tmp_path, count=4)
    plan=build_pivot_plan([witness],'Mu',tmp_path,tmp_path/'edition.xml')
    assert len(plan.pages)==4
    assert any('4v' in w and 'aucun pb' in w for w in plan.warnings)
    result=render_pivot_scaffold(xml,plan)
    assert result.count('<pb ') == 4
    assert 'facs="#Mu-p0005"' not in result


def test_gapped_numbers_do_not_generate_unobserved_lines(tmp_path):
    witness,xml=_setup(tmp_path, count=1)
    source=tmp_path/'Mu.json'
    content=json.loads(source.read_text(encoding='utf8'))
    content['pages'][0]['lines']=[{'line':41},{'line':43}]
    source.write_text(json.dumps(content),encoding='utf8')
    plan=build_pivot_plan([witness],'Mu',tmp_path,tmp_path/'edition.xml')
    assert plan.line_count==2 and plan.pages[0].evidence=='JSON partiel'
    assert any('lignes absentes non inventées' in w for w in plan.warnings)
    assert render_pivot_scaffold(xml,plan).count('<lb ') == 2


def test_duplicate_numbers_rejected_without_fabricating_lb(tmp_path):
    witness,xml=_setup(tmp_path, count=1)
    source=tmp_path/'Mu.json'
    content=json.loads(source.read_text(encoding='utf8'))
    content['pages'][0]['lines']=[{'line':41},{'line':41}]
    source.write_text(json.dumps(content),encoding='utf8')
    plan=build_pivot_plan([witness],'Mu',tmp_path,tmp_path/'edition.xml')
    assert plan.line_count==0 and plan.pages[0].evidence=='JSON ambigu'
    assert render_pivot_scaffold(xml,plan).count('<pb ')==1


def test_actual_uploaded_mu_json_when_available(tmp_path):
    import pytest
    raw = Path('/mnt/data/Mu.json')
    if not raw.is_file():
        pytest.skip('Original Mu.json not distributed')
    data=json.loads(raw.read_text(encoding='utf8'))
    assert [len(p['lines']) for p in data['pages']]==[28,66,66,51,0]
    assert [p['lines'][0]['line'] if p['lines'] else None for p in data['pages']] == [41,1,1,1,None]
    # Exactly the real JSON shape; only the image paths are replaced with
    # fixture paths so that the archive does not redistribute user material.
    for p in data['pages']:
        p['image']['path']=str(tmp_path / (p['label']+'.jpg'))
    j=tmp_path/'actual-mu.json'; j.write_text(json.dumps(data),encoding='utf8')
    files=[LocalImageDraft(tmp_path/(p['label']+'.jpg'),p['label'],surface_id=f'Mu-p{i:04d}')
           for i,p in enumerate(data['pages'],1)]
    w=WitnessDraft('Mu','Pivot',alignment=j,image_source_type='files',image_files=files)
    plan=build_pivot_plan([w],'Mu',tmp_path,tmp_path/'edition.xml')
    assert [p.line_count for p in plan.pages] == [28,66,66,51,0]
