from pathlib import Path
import tempfile

from iiif_manifest import parse_manifest, cache_path, import_manifest, read_cache, overlay_manifest
from image_sources import apply_witness_image_policy, page_image_source, image_only_items
from project_management import ProjectDraft, WitnessDraft, write_project_xml, prepare_iiif_manifests_for_project
from project_config import load_project

V2={
 '@context':'http://iiif.io/api/presentation/2/context.json','@id':'https://example.org/m2','@type':'sc:Manifest','label':'MS A',
 'sequences':[{'canvases':[{
   '@id':'https://example.org/c1','@type':'sc:Canvas','label':'f. 1r','width':2000,'height':3000,
   'images':[{'resource':{'@id':'https://example.org/iiif/a/full/full/0/default.jpg','@type':'dctypes:Image','service':{'@id':'https://example.org/iiif/a','profile':'http://iiif.io/api/image/2/level2.json'}}}]
 }]}]
}
V3={
 '@context':['http://iiif.io/api/presentation/3/context.json'],'id':'https://example.org/m3','type':'Manifest','label':{'fr':['Manuscrit B']},
 'items':[{'id':'https://example.org/canvas/1','type':'Canvas','label':{'none':['p. 1']},'width':2400,'height':3600,
   'items':[{'id':'https://example.org/ap/1','type':'AnnotationPage','items':[{'id':'https://example.org/a/1','type':'Annotation','motivation':'painting','body':{'id':'https://example.org/img.jpg','type':'Image','format':'image/jpeg','service':[{'id':'https://example.org/iiif/b','type':'ImageService3','profile':'level2'}]}}]}]
 }]
}

def test_parse_presentation_2_manifest():
    m=parse_manifest(V2,'https://example.org/m2')
    assert m.presentation_version==2 and len(m.pages)==1
    src=page_image_source(m.pages[0])
    assert src.kind=='iiif' and src.service=='https://example.org/iiif/a'
    assert src.iiif_version==2 and src.label=='f. 1r'


def test_parse_presentation_3_manifest_language_map_and_service3():
    m=parse_manifest(V3,'https://example.org/m3')
    assert m.presentation_version==3 and m.label=='Manuscrit B'
    src=page_image_source(m.pages[0])
    assert src.service=='https://example.org/iiif/b' and src.iiif_version==3
    assert src.label=='p. 1'


def test_manifest_cache_and_overlay_preserve_alignment_lines():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); cp=cache_path(root,'A')
        m=import_manifest('https://example.org/m2',cp,raw=V2)
        assert cp.is_file() and read_cache(cp,'https://example.org/m2') is not None
        aligned={'pages':[{'id':'page-X','alto_width':1000,'alto_height':1500,'lines':[{'line':1,'base_keys':['x']}]}]}
        out=overlay_manifest(aligned,m)
        assert out['pages'][0]['id']=='page-X'
        assert out['pages'][0]['lines'][0]['base_keys']==['x']
        assert page_image_source(out['pages'][0]).service=='https://example.org/iiif/a'


def test_project_iiif_manifest_roundtrip_and_policy_uses_local_cache():
    with tempfile.TemporaryDirectory() as td:
        root=Path(td); (root/'xml').mkdir(); (root/'i18n').mkdir(); (root/'rendering').mkdir(); (root/'web_output').mkdir()
        (root/'xml'/'edition.xml').write_text("<TEI xmlns='http://www.tei-c.org/ns/1.0'><text/></TEI>",encoding='utf-8')
        (root/'rendering'/'tei.css').write_text('',encoding='utf-8'); (root/'rendering'/'custom-elements.xml').write_text('<customElements/>',encoding='utf-8')
        w=WitnessDraft('A','A',None,'base','iiif','https://example.org/m3',[], 'keep', V3)
        prepared=prepare_iiif_manifests_for_project(root,[w])
        d=ProjectDraft('T',root/'xml'/'edition.xml','fr','en',root/'i18n',root/'rendering'/'tei-to-html.xsl',root/'rendering'/'tei.css',root/'rendering'/'custom-elements.xml',root/'web_output','viewer.html',prepared,'A',xslt_mode='builtin',schema_mode='none')
        pp=write_project_xml(root/'project.xml',d)
        cfg=load_project(pp)
        assert cfg.base.image_source_type=='iiif' and cfg.base.image_source_value=='https://example.org/m3'
        out=apply_witness_image_policy({'pages':[]},'iiif',cfg.base.image_source_value,root,(), 'A')
        assert len(out['pages'])==1 and page_image_source(out['pages'][0]).iiif_version==3
        assert len(image_only_items(out,root))==1
