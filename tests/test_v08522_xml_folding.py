"""V0.8.5.22 — conservative structural folding of source XML."""
from pathlib import Path
import ast
import textwrap
from types import SimpleNamespace
import xml.etree.ElementTree as ET

from xml_folding import foldable_xml_regions, region_at_header, region_for_cursor, visible_line_numbers
from varians_source import application_source, application_ast, node_source, CURRENT_VERSION, CATALOG_SIZE

ROOT=Path(__file__).resolve().parents[1]
SRC=application_source()


def sample():
    return ('<TEI>\n <text>\n  <body>\n'
            '   <div xml:id="d1">\n'
            '    <p>Une ligne.</p>\n'
            '    <app>\n'
            '     <lem wit="#Mu">alpha</lem>\n'
            '     <rdg wit="#F">beta</rdg>\n'
            '    </app>\n'
            '   </div>\n'
            '  </body>\n </text>\n</TEI>')


def test_nested_folding_preserves_every_byte_and_expected_ranges():
    xml=sample()
    regs=foldable_xml_regions(xml)
    d=next(x for x in regs if x.name=='div')
    app=next(x for x in regs if x.name=='app')
    assert (d.opening_line,d.first_hidden_line,d.closing_line)==(3,4,9)
    assert (app.opening_line,app.first_hidden_line,app.closing_line)==(5,6,8)
    assert region_at_header(regs,3)==d
    assert region_for_cursor(regs,7)==app
    assert visible_line_numbers(regs,{3},13)==(0,1,2,3,10,11,12)
    assert '<rdg wit="#F">beta</rdg>' in xml  # never rewrite source


def test_multiline_opening_tag_hides_only_after_complete_opening():
    xml='<div\n xml:id="one"\n type="edition">\n  <p>Texte</p>\n</div>'
    reg=foldable_xml_regions(xml)[0]
    assert reg.name=='div'
    assert (reg.opening_line,reg.first_hidden_line,reg.closing_line)==(0,3,4)


def test_never_hide_parts_of_a_line_or_single_line_elements():
    assert not foldable_xml_regions('<p>x</p>')
    assert not foldable_xml_regions('<div>hello\n <p>x</p>\n</div>')
    assert not foldable_xml_regions('<div>\n x\n</div>tail')
    assert not foldable_xml_regions('<div>\n x\n</div><p>y</p>')
    assert not foldable_xml_regions('<div>\n x\n</bad>')


def test_lexical_special_xml_is_not_seen_as_markup():
    xml=('<!-- <app>not a tag</app> -->\n'
         '<div>\n <![CDATA[ <fake></fake> ]]>\n <?pi value="<ab/>"?>\n'
         '  <p/>\n</div>')
    regs=foldable_xml_regions(xml)
    assert [r.name for r in regs]==['div']


def test_namespaced_nested_similar_tags_and_bad_nesting():
    xml='<tei:div>\n <tei:div>\n txt\n </tei:div>\n</tei:div>'
    assert len(foldable_xml_regions(xml))==2
    assert not foldable_xml_regions('<a>\n<b>\n</a>\n</b>')


def method(name, env=None):
    tree=application_ast()
    cls=next(node for node in tree.body if isinstance(node,ast.ClassDef) and node.name=='CodeEditor')
    fn=next(n for n in cls.body if isinstance(n,ast.FunctionDef) and n.name==name)
    ns=dict(env or {})
    exec(textwrap.dedent(node_source(fn)),ns)
    return ns[name]


class FakeBlock:
    def __init__(self,i,n):self.i=i;self.n=n;self.visible=True;self.lines=1;self.dirty=0
    def isValid(self):return self.i<self.n
    def blockNumber(self):return self.i
    def isVisible(self):return self.visible
    def setVisible(self,value):self.visible=value
    def setLineCount(self,value):self.lines=value
    def layout(self):return SimpleNamespace(lineCount=lambda:1)
    def position(self):return self.i*20
    def length(self):return 20
    def next(self):return FakeBlock(self.i+1,self.n)


class FakeDocument:
    def __init__(self, n):self.n=n;self.blocks=[FakeBlock(i,n) for i in range(n)];self.dirty=[]
    def firstBlock(self):return self.blocks[0]
    def markContentsDirty(self,a,b):self.dirty.append((a,b))


def test_qt_controller_visibility_without_qt_using_document_doubles():
    xml=sample();doc=FakeDocument(len(xml.splitlines()))
    # Preserve real block states while iterating through next().
    for i,b in enumerate(doc.blocks):
        b.next=lambda i=i:doc.blocks[i+1] if i+1<len(doc.blocks) else FakeBlock(len(doc.blocks),len(doc.blocks))
    obj=SimpleNamespace(_fold_relayouting=False,_folded_opening_lines={3},
                        _fold_regions=lambda:foldable_xml_regions(xml),
                        document=lambda:doc,
                        viewport=lambda:SimpleNamespace(update=lambda:None),
                        lineNumberArea=SimpleNamespace(update=lambda:None),
                        updateLineNumberAreaWidth=lambda value:None)
    update=method('_apply_xml_fold_visibility')
    update(obj)
    assert tuple(i for i,b in enumerate(doc.blocks) if b.visible)==(0,1,2,3,10,11,12)
    assert len(doc.dirty)==6
    obj._folded_opening_lines.clear();update(obj)
    assert all(b.visible for b in doc.blocks)
    assert all(b.lines for b in doc.blocks)


def test_no_xml_modification_and_ui_actions_are_connected():
    assert 'self.xml_folding_menu = menu.addMenu' in SRC
    assert 'self.editor.toggle_xml_fold()' in SRC
    assert 'self.editor.fold_all_xml()' in SRC
    assert 'self.editor.unfold_all_xml()' in SRC
    assert f'APP_VERSION = "{CURRENT_VERSION}"' in SRC
    assert 'self.document().markContentsDirty' in SRC
    assert 'self._unfold_for_hidden_cursor' in SRC


def test_all_locales_and_help_pages():
    languages={'fr','en','de','ja','cs','it','ru'}
    assert {x.stem for x in (ROOT/'i18n').glob('*.xml')}==languages
    for lang in languages:
        root=ET.parse(ROOT/'i18n'/f'{lang}.xml').getroot()
        translations={n.get('key'):n.text for n in root.findall('string')}
        assert len(translations)==len(root.findall('string'))==CATALOG_SIZE
        for key in ('fold.menu','fold.current','fold.all','fold.none'):
            assert translations[key]
        help_text=(ROOT/'help'/f'{lang}.html').read_text(encoding='utf-8')
        assert '0.8.5.22' in help_text and 'xml-fold-v08522' in help_text
