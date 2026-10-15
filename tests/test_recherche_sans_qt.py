"""Test hors Qt du contrat de navigation de la recherche source.

Extrait la fonction find_in_plain_editor (sans exécuter les imports GUI)
et utilise un double minimal de QTextCursor pour vérifier que la recherche
ne sélectionne jamais de texte éditable ni ne force le focus sur l'éditeur.
"""
import ast
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / 'editeur_tei.py'
root = ast.parse(SOURCE.read_text(encoding='utf-8'))
func = next(n for n in root.body if isinstance(n, ast.FunctionDef) and n.name == 'find_in_plain_editor')

class MockCursor:
    def __init__(self, document):
        self.document = document
        self.position_value = 0
        self.selected = False
    def position(self):
        return self.position_value
    def hasSelection(self):
        return self.selected
    def selectionStart(self):
        return self.position_value
    def selectionEnd(self):
        return self.position_value
    def setPosition(self, position, moveMode=None):
        if moveMode is not None:
            self.selected = True
        self.position_value = position

class MockEditor:
    def __init__(self, txt):
        self.txt = txt
        self.cursor = MockCursor(self)
        self._search_last = None
        self.match = None
        self.focus_changes = 0
        self.centered = 0
    def toPlainText(self):
        return self.txt
    def textCursor(self):
        return self.cursor
    def document(self):
        return self
    def setTextCursor(self, cursor):
        self.cursor = cursor
    def centerCursor(self):
        self.centered += 1
    def setFocus(self):
        self.focus_changes += 1
    def setSearchMatch(self, start, end, query):
        self._search_last = (start, end, query.casefold())
        self.match = (start, end)
    def clearSearchMatch(self):
        self._search_last = None
        self.match = None

ns = {'QTextCursor': MockCursor}
exec(compile(ast.Module(body=[func], type_ignores=[]), str(SOURCE), 'exec'), ns)
search = ns['find_in_plain_editor']
editor = MockEditor('alpha BETA beta beta end')
results = []
for _ in range(4):
    found, num, total = search(editor, 'beta')
    assert found and total == 3
    results.append((num, editor.match, editor.cursor.hasSelection()))
    assert not editor.cursor.hasSelection(), 'La recherche ne doit jamais sélectionner du texte éditable'
assert [x[0] for x in results] == [1, 2, 3, 1], results
assert search(editor, 'beta', backwards=True)[:2] == (True, 3)
assert search(editor, 'beta', backwards=True)[:2] == (True, 2)
assert editor.focus_changes == 0, 'La recherche ne doit jamais envoyer le focus dans le XML'
assert search(editor, 'absent') == (False, 0, 0)
assert editor.match is None
# Même si un match est surligné, il n'existe pas de sélection textuelle active.
print('OK : 1→2→3→1, précédent 3→2, pas de sélection, pas de focus XML, absence efface le surlignage')

# Contrôles structurels du menu et du rappel d'entrée.
source = SOURCE.read_text(encoding='utf-8')
assert 'menu = QMenu(_t("menu.file"), self)' in source
assert 'self.file_menu_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)' in source
assert 'self.find_box.returnPressed.connect(self.find_source_next)' in source
assert 'self.find_box.setFocus()' in source.split('def _find_source(', 1)[1].split('def find_source_next(', 1)[0]
assert 'self.fragment_find_box.setFocus()' in source.split('def _find_fragment(', 1)[1].split('def find_fragment_next(', 1)[0]
assert 'self.menuBar().addMenu(' not in source
print('OK : Fichier dans la toolbar, Entrée vers Suivant, focus sur champ de recherche XML et fragment')
