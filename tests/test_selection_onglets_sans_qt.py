"""Tests hors Qt des règles textuelles du transfert de sélection XML <-> XSLT."""
import ast
import re
import html as html_lib
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'editeur_tei.py'
root = ast.parse(SOURCE.read_text(encoding='utf-8'))
names = {'_selection_xml_to_visible_text', '_xml_selection_pattern'}
funcs = [n for n in root.body if isinstance(n, ast.FunctionDef) and n.name in names]
ns = {'re': re, 'html_lib': html_lib}
exec(compile(ast.Module(body=funcs, type_ignores=[]), str(SOURCE), 'exec'), ns)
to_visible = ns['_selection_xml_to_visible_text']
to_xml_pattern = ns['_xml_selection_pattern']

assert to_visible('uerbum') == 'uerbum'
assert to_visible('<hi>uerbum</hi>') == 'uerbum'
assert to_visible('sim\n<lb edRef="#T1" break="no"/>plex') == 'simplex'
assert to_visible('prima<lb edRef="#T1"/>secunda') == 'prima secunda'

src = 'consilio et sim\n<lb edRef="#T1" break="no"/>plex, deinde'
pat = to_xml_pattern('simplex')
m = re.search(pat, src, flags=re.DOTALL)
assert m, pat
assert 'break="no"' in m.group(0)
assert m.group(0).startswith('sim') and m.group(0).endswith('plex')

src2 = 'prima<lb edRef="#T1"/>secunda'
pat2 = to_xml_pattern('prima secunda')
m2 = re.search(pat2, src2, flags=re.DOTALL)
assert m2, pat2

source_text = SOURCE.read_text(encoding='utf-8')
block = source_text.split('def _left_tab_changed(self, index):', 1)[1].split('def validate_text(', 1)[0]
assert '_selection_xml_to_visible_text' in block
assert 'select_visible_text_near_line' in block
assert '_select_xml_text_near_ordinal' in block
assert 'selectionStart()' in block
print('OK : sélection XML<->XSLT, break=no, lb normal et branchement sur changement d’onglet')
