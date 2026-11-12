"""Tests hors Qt des règles textuelles du transfert de sélection XML <-> XSLT."""
import ast
import re
import html as html_lib
from pathlib import Path
from varians_source import application_ast, application_source

SOURCE = Path(__file__).resolve().parents[1] / 'editeur_tei.py'
root = application_ast()
names = {'_selection_xml_to_visible_text'}
funcs = [n for n in root.body if isinstance(n, ast.FunctionDef) and n.name in names]
ns = {'re': re, 'html_lib': html_lib}
exec(compile(ast.Module(body=funcs, type_ignores=[]), str(SOURCE), 'exec'), ns)
to_visible = ns['_selection_xml_to_visible_text']

assert to_visible('uerbum') == 'uerbum'
assert to_visible('<hi>uerbum</hi>') == 'uerbum'
assert to_visible('sim\n<lb edRef="#T1" break="no"/>plex') == 'simplex'
assert to_visible('prima<lb edRef="#T1"/>secunda') == 'prima secunda'

source_text = application_source()
block = source_text.split('def _left_tab_changed(self, index):', 1)[1].split('def validate_text(', 1)[0]
assert '_source_selection_context' in block
assert 'selection_context()' in block
assert 'select_quote' in block
assert '_select_source_quote' in block
assert 'selectionStart()' in block
print('OK : texte visible d’une sélection XML et branchement sur changement d’onglet')
