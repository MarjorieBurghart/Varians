"""V0.8.5.18 — folio navigation on a single image / TEI surface."""
from pathlib import Path
import sys
import xml.etree.ElementTree as ET
import pytest
from varians_source import application_source, CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from folio_navigation import Folio, folios_for_witness, folio_at_position, split_surface_into_folios

BASE = '''<TEI xmlns="http://www.tei-c.org/ns/1.0"><facsimile>
 <surface xml:id="L-p0008" n="008 - f002v-003r"><graphic url="spread.jpg"/></surface>
 <surface xml:id="Mu-p0008" n="008 - f002v-003r"><graphic url="different.jpg"/></surface>
</facsimile><text><body><p>abc</p></body></text></TEI>'''

def make_spread():
    xml, ids = split_surface_into_folios(BASE, 'L-p0008', 'f002v', 'f003r',3924,2704)
    return xml,ids

def test_split_is_only_two_new_zones_and_one_graphic():
    result,(l,r)=make_spread()
    assert l=='L-p0008-left' and r=='L-p0008-right'
    assert result.count('graphic url="spread.jpg"')==1
    assert result.count('xml:id="L-p0008"')==1
    assert result.count('xml:id="Mu-p0008"')==1
    assert 'lrx="1962" lry="2704"' in result
    assert 'ulx="1962" uly="0" lrx="3924" lry="2704"' in result
    ET.fromstring(result)

def test_folios_physical_sequence_with_two_logical_leaves():
    result,ids=make_spread()
    L=folios_for_witness(result,'L',['L-p0008'],{})
    assert [x.ref for x in L]==['L-p0008',*ids]
    assert L[1].region==(0,0,1962,2704)
    assert L[2].region==(1962,0,1962,2704)
    assert len(folios_for_witness(result,'Mu',['Mu-p0008'],{}))==1

def test_pb_explicit_facs_zone_changes_current_folio():
    xml,ids=make_spread()
    xml=xml.replace('<p>abc</p>',f'<p><pb edRef="#L" n="f002v" facs="#{ids[0]}"/>ab<pb edRef="#L" n="f003r" facs="#{ids[1]}"/>c</p>')
    folios=folios_for_witness(xml,'L',['L-p0008'])
    assert folio_at_position(xml,xml.index('ab')+1,'L',folios).ref==ids[0]
    assert folio_at_position(xml,xml.index('c</p>'),'L',folios).ref==ids[1]

def test_pb_parent_surface_plus_name_selects_corresponding_region():
    xml,ids=make_spread()
    xml=xml.replace('<p>abc</p>','<p><pb edRef="#L" n="f003r" facs="#L-p0008"/>abc</p>')
    assert folio_at_position(xml,xml.index('abc</p>'),'L',folios_for_witness(xml,'L',['L-p0008'])).ref==ids[1]

def test_pb_name_without_facs_uses_only_its_witness():
    xml,ids=make_spread()
    xml=xml.replace('<p>abc</p>','<p><pb edRef="#L" n="f003r"/>abc</p>')
    assert folio_at_position(xml,xml.index('abc</p>'),'L',folios_for_witness(xml,'L',['L-p0008'])).ref==ids[1]
    assert folio_at_position(xml,xml.index('abc</p>'),'Mu',folios_for_witness(xml,'Mu',['Mu-p0008'])) is None

def test_repeated_folio_n_across_witnesses_allowed():
    xml, ids = make_spread()
    # Same folio label in two witness maps, each resolves its own @edRef.
    xml=xml.replace('<p>abc</p>','<p><pb edRef="#L" n="008 - f002v-003r"/>abc</p>')
    assert folio_at_position(xml,xml.index('abc</p>'),'L',folios_for_witness(xml,'L',['L-p0008'])).ref=='L-p0008'
    assert folio_at_position(xml,xml.index('abc</p>'),'Mu',folios_for_witness(xml,'Mu',['Mu-p0008'])) is None

def test_repeated_n_within_witness_remains_ambiguous():
    refs=[Folio('l1','p1','3r'),Folio('l2','p2','3r')]
    xml='<p><pb edRef="#L" n="3r"/>x</p>'
    assert folio_at_position(xml,len(xml),'L',refs) is None

def test_ignored_pb_in_comment_and_cdata():
    xml, ids=make_spread()
    xml=xml.replace('<p>abc</p>',f'<p><!-- <pb edRef="#L" facs="#{ids[1]}"/> --><![CDATA[<pb edRef="#L" facs="#{ids[1]}"/>]]>abc</p>')
    assert folio_at_position(xml,xml.index('abc</p>'),'L',folios_for_witness(xml,'L',['L-p0008'])) is None

def test_folio_selection_returns_none_before_complete_pb():
    xml,ids=make_spread()
    xml=xml.replace('<p>abc</p>',f'<p><pb edRef="#L" facs="#{ids[0]}"/>abc</p>')
    pos=xml.index('facs="#')
    assert folio_at_position(xml,pos,'L',folios_for_witness(xml,'L',['L-p0008'])) is None

def test_malformed_editor_xml_falls_back_to_surface_level():
    xml,ids=make_spread()
    assert [f.ref for f in folios_for_witness(xml+'<p','L',['L-p0008'],{'L-p0008':'spread'})]==['L-p0008']

def test_split_respects_custom_ratio():
    xml, ids=split_surface_into_folios(BASE,'L-p0008','1v','2r',4000,2000,45)
    assert 'lrx="1800"' in xml and 'ulx="1800"' in xml

@pytest.mark.parametrize('left,right', [('', '2r'),('1v',''),('x','x')])
def test_invalid_folio_labels_leave_source_untouched(left,right):
    with pytest.raises(ValueError):split_surface_into_folios(BASE,'L-p0008',left,right,100,100)

@pytest.mark.parametrize('ratio',[-1,0,100,101])
def test_invalid_ratios_rejected(ratio):
    with pytest.raises(ValueError):split_surface_into_folios(BASE,'L-p0008','1v','2r',100,100,ratio)

def test_existing_zone_cannot_be_overwritten():
    xml,ids=make_spread()
    with pytest.raises(ValueError,match='déjà des zones'):split_surface_into_folios(xml,'L-p0008','a','b',100,100)

def test_nonexistent_surface_or_malformed_source_rejected():
    with pytest.raises(ValueError):split_surface_into_folios(BASE,'missing','a','b',100,100)
    with pytest.raises(ValueError):split_surface_into_folios(BASE+'<bad','L-p0008','a','b',100,100)

def test_namespace_prefixed_tei_does_not_get_rewritten():
    xml='''<tei:TEI xmlns:tei="http://www.tei-c.org/ns/1.0"><tei:facsimile><tei:surface xml:id="X-p0001"><tei:graphic url="file.jpg"/></tei:surface></tei:facsimile></tei:TEI>'''
    out,_=split_surface_into_folios(xml,'X-p0001','1v','2r',200,100)
    assert '<tei:zone' in out and '<tei:graphic url="file.jpg"/>' in out
    ET.fromstring(out)

def test_7_translations_have_all_folio_keys():
    fr=ET.parse(ROOT/'i18n'/'fr.xml').getroot()
    keys={x.attrib['key'] for x in fr.findall('string') if x.attrib['key'].startswith('folio.')}
    assert len(keys)==23
    for lang in ('en','de','ja','cs','it','ru'):
        values={x.attrib['key']:x.text for x in ET.parse(ROOT/'i18n'/f'{lang}.xml').getroot().findall('string')}
        assert keys <= values.keys()
        assert all(values[x] for x in keys)

def test_editor_hooks_present_and_distinguish_page_line():
    s=application_source()
    for name in ('set_folios','set_folio','_split_double_folio','folio_at_position','_refresh_folio_navigation','folio_focus_rect','panel.sync_enabled'):
        assert name in s
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in s


def test_web_dataset_includes_one_image_two_folio_regions(tmp_path):
    from types import SimpleNamespace
    from project_config import WitnessConfig, LocalImageConfig
    from web_viewer.generator import build_dataset, make_html
    xml, (lref,rref)=make_spread()
    xml=xml.replace('<p>abc</p>',f'<p><pb edRef="#L" n="f002v" facs="#{lref}"/>ab<pb edRef="#L" n="f003r" facs="#{rref}"/>c</p>')
    edition=tmp_path/'edition.xml';edition.write_text(xml,encoding='utf-8')
    image=tmp_path/'spread.jpg';image.write_bytes(b'fake-jpg-for-data-only')
    base=tmp_path/'mu.jpg';base.write_bytes(b'fake')
    w1=WitnessConfig('Mu','Mu',None,'base',image_source_type='files',image_files=(LocalImageConfig(base,'008',3924,2704,'Mu-p0008'),))
    w2=WitnessConfig('L','L',None,'secondary',image_source_type='files',image_files=(LocalImageConfig(image,'008 - f002v-003r',3924,2704,'L-p0008'),))
    p=SimpleNamespace(base_witness='Mu',witnesses=(w1,w2),witness_by_id={'Mu':w1,'L':w2},root_dir=tmp_path,
                      edition=edition,translations_dir=ROOT/'i18n',language='fr',fallback_language='en',title='Folio test')
    dataset,missing=build_dataset(p)
    L=next(w for w in dataset['witnesses'] if w['id']=='L')
    assert len(L['pages'])==1
    assert [f['ref'] for f in L['folios']]==['L-p0008',lref,rref]
    assert L['folios'][1]['region']==(0,0,1962,2704)
    output=make_html(dataset)
    assert 'folioChoices' in output and 'folioByRef' in output
    assert 'L-p0008-left' in output and 'L-p0008-right' in output
    assert 'select[data-folio]' in output


def test_folio_viewport_crop_is_scaled_from_original_to_lowres_bitmap():
    from folio_navigation import scene_rect_for_folio
    left=scene_rect_for_folio((0,0,1962,2704),{'x':0,'y':0,'w':3924,'h':2704},490,338)
    right=scene_rect_for_folio((1962,0,1962,2704),{'x':0,'y':0,'w':3924,'h':2704},490,338)
    assert left == (0,0,245,338)
    assert right == (245,0,245,338)
    assert scene_rect_for_folio((1962,0,1962,2704),{'x':0,'y':0,'w':3924,'h':2704},490,338,340)==(245,340,245,338)
