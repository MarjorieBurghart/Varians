# -*- coding: utf-8 -*-
"""Régression sans PySide6 : recherche de mots traversant l'ancre invisible U+2060.

On extrait la vraie fonction de l'éditeur et simulons QTextDocument.find
(QRegularExpression). Le test graphique de Qt demeure à faire sous Windows.
"""
import ast
from pathlib import Path
import re
from types import SimpleNamespace

SOURCE = Path(__file__).resolve().parents[1] / 'editeur_tei.py'
code = ast.parse(SOURCE.read_text(encoding='utf-8'))
func = next(n for n in code.body if isinstance(n, ast.FunctionDef) and n.name == 'find_in_rich_editor')

class MockRegex:
    PatternOption = SimpleNamespace(CaseInsensitiveOption=re.IGNORECASE)
    def __init__(self, pattern, flags=0):
        self.compiled = re.compile(pattern, flags)
    @staticmethod
    def escape(value):
        return re.escape(value)

class MockDocument:
    def __init__(self, text):
        self.text = text
    def find(self, expr, cursor, flags=0):
        matches = list(expr.compiled.finditer(self.text))
        pos = cursor.position()
        if flags:
            choices = [m for m in matches if m.end() <= pos]
            match = choices[-1] if choices else None
        else:
            match = next((m for m in matches if m.start() >= pos), None)
        return MockCursor(self, match.start(), match.end()) if match else MockCursor(self, null=True)

class MockCursor:
    MoveOperation = SimpleNamespace(Start=1, End=2)
    def __init__(self, doc, start=0, end=None, null=False):
        self.doc = doc
        self.anchor = start
        self.pos = start if end is None else end
        self.null = null
    def isNull(self):
        return self.null
    def position(self):
        return self.pos
    def setPosition(self, value):
        self.pos = value
        self.anchor = value
    def movePosition(self, operation):
        self.setPosition(0 if operation == self.MoveOperation.Start else len(self.doc.text))
    def hasSelection(self):
        return self.pos != self.anchor
    def selectionStart(self):
        return min(self.pos, self.anchor)
    def selectionEnd(self):
        return max(self.pos, self.anchor)

class MockEditor:
    def __init__(self, text):
        self.doc = MockDocument(text)
        self.cursor = MockCursor(self.doc)
        self.focussed = False
        self.scrolled = 0
    def document(self):
        return self.doc
    def textCursor(self):
        return self.cursor
    def setTextCursor(self, cursor):
        self.cursor = cursor
    def ensureCursorVisible(self):
        self.scrolled += 1
    def setFocus(self):
        self.focussed = True

class MockDocumentFlags:
    class FindFlag(int):
        FindBackward = 1

ns = {'QRegularExpression': MockRegex, 'QTextDocument': MockDocumentFlags, 'QTextCursor': MockCursor}
exec(compile(ast.Module(body=[func], type_ignores=[]), str(SOURCE), 'exec'), ns)
find = ns['find_in_rich_editor']

# Exemple utilisateur : un <lb edRef="#T1" break="no"/> marque la position
# avec U+2060, sans faire apparaître de blanc dans l'édition XSLT.
text = 'Timeat igitur animus effe\u2060minatus ...'
ed = MockEditor(text)
assert find(ed, 'effeminatus') == (True, 1, 1)
assert not ed.cursor.hasSelection()
assert text[ed._search_match[0]:ed._search_match[1]] == 'effe\u2060minatus'
assert find(ed, 'EFFEMINATUS') == (True, 1, 1)
assert not ed.focussed, 'La recherche doit laisser le focus au champ de saisie'
print('OK recherche effeminatus avec U+2060 : highlight séparé, casse ignorée, pas de vol du focus')

# Plusieurs marqueurs invisibles au sein du mot et ailleurs dans le document.
ed = MockEditor('effe\u2060minatus / effeminatus / e\u2060ff\u2060eminatus')
for expected_n in (1, 2, 3, 1):
    found, n, total = find(ed, 'effeminatus')
    assert (found, n, total) == (True, expected_n, 3), (found, n, total)
assert find(ed, 'effeminatus', backwards=True) == (True, 3, 3)
assert find(ed, 'effeminatus', backwards=True) == (True, 2, 3)
assert find(ed, 'absent') == (False, 0, 0)
print('OK trois occurrences mixtes, retour début/fin, navigation arrière, mot absent')

# Les caractères qui sont réellement des espaces restent des séparateurs :
# la recherche ne fusionne jamais « effe minatus » en « effeminatus ».
ed = MockEditor('effe minatus / effeminatus')
assert find(ed, 'effeminatus') == (True, 1, 1)
assert not ed.cursor.hasSelection()
assert ed.doc.text[ed._search_match[0]:ed._search_match[1]] == 'effeminatus'
print('OK espaces réels respectés : seule la jonction invisible est ignorée')
