"""V0.8.5.25.2: conservative navigation from TEI text into manuscript lines."""
from pathlib import Path
import xml.etree.ElementTree as ET
from project_config import load_project
from web_viewer.generator import build_dataset, make_html

ROOT = Path(__file__).resolve().parents[1]


def test_exported_reading_click_keys_resolve_in_pivot():
    project = load_project(ROOT / 'tests' / 'data' / 'exemple' / 'project.xml')
    data, _ = build_dataset(project)
    w = next(w for w in data['witnesses'] if w['id'] == data['meta']['base_witness'])
    keys = {f"{p['id']}::{l['line']}" for p in w['pages'] for l in p['lines']}
    document_keys = {str(seg['line_key']) for b in data['document']['blocks']
                     for seg in b.get('segments', []) if seg.get('line_key')}
    assert keys
    assert document_keys <= keys
    assert data['meta']['unresolvable_text_line_keys'] == 0
    assert data['meta']['unanchored_text_segments'] >= 0


def test_markup_and_event_handler_keep_trustworthy_keys():
    data, _ = build_dataset(load_project(ROOT / 'tests' / 'data' / 'exemple' / 'project.xml'))
    html = make_html(data)
    assert 'function selectLine(k,scroll=false)' in html
    assert 'data-no-line' in html
    assert 'const f=e.target.closest(\'[data-line]\')' in html
    assert 'if(f&&lineMode){selectLine(f.dataset.line,false)}' in html
    assert 'if(a)showAnnotation(a.dataset.ann,e)' in html
    assert 'if(!lineMode||!lineMap.has(k))' in html
    assert 'class="poly-overlay${isCurrent?' in html
    assert 'current-poly' in html and 'current-box' in html
    assert 'syncAll(true)' in html
    assert 'data-line="${esc(s.line_key)}"' in html
    assert 'viewer.line_no_anchor' in html
    assert 'viewer.line_unresolved' in html


def test_all_catalogues_have_navigation_warnings():
    for lang in ('fr','en','de','ja','cs','it','ru'):
        xml = ET.parse(ROOT / 'i18n' / (lang+'.xml')).getroot()
        for key in ('viewer.line_no_anchor','viewer.line_unresolved'):
            node = next((x for x in xml if x.attrib.get('key') == key), None)
            assert node is not None and node.text
            if key == 'viewer.line_unresolved':
                assert '{key}' in node.text
        html = (ROOT / 'help' / (lang+'.html')).read_text(encoding='utf-8')
        assert '<h2 id="viewer">' in html                   # V0.9.3.1 : l'aide sans versions
