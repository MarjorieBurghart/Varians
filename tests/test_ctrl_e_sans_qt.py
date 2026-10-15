"""Tests du contrat Ctrl+E sans PySide6.

Charge le corps de FormattedEditionWidget.wrap_selection_with_element depuis
l'AST réel, puis utilise un double de QTextCursor (offsets UTF-16 comme Qt).
Ne valide pas l'interface native Qt, mais contrôle le contenu produit, la
sélection conservée, les attributs, l'insertion vide et les erreurs.
"""
import ast
import html as html_lib
from pathlib import Path
import re
from types import SimpleNamespace
from varians_source import application_ast

CODE = Path(__file__).resolve().parents[1] / "editeur_tei.py"
code_ast = application_ast()
widget_ast = next(n for n in code_ast.body if isinstance(n, ast.ClassDef) and n.name == "FormattedEditionWidget")
method_ast = next(n for n in widget_ast.body if isinstance(n, ast.FunctionDef) and n.name == "wrap_selection_with_element")

def units(text):
    return len(text.encode("utf-16-le")) // 2

def index_at_units(text, target):
    for idx in range(len(text) + 1):
        if units(text[:idx]) == target:
            return idx
    raise AssertionError(f"Découpage UTF-16 impossible : {target}")

class FakeCursor:
    class MoveMode:
        KeepAnchor = object()

    def __init__(self, document, anchor=0, pos=0):
        self._doc = document
        self.anchor = anchor
        self.pos = pos

    def hasSelection(self):
        return self.anchor != self.pos

    def position(self):
        return self.pos

    def selectionStart(self):
        return min(self.anchor, self.pos)

    def selectedText(self):
        txt = self._doc.text
        a = index_at_units(txt, self.selectionStart())
        b = index_at_units(txt, max(self.anchor, self.pos))
        return txt[a:b].replace("\n", "\u2029")

    def beginEditBlock(self):
        pass

    def endEditBlock(self):
        pass

    def insertText(self, replacement):
        a = index_at_units(self._doc.text, self.selectionStart())
        b = index_at_units(self._doc.text, max(self.anchor, self.pos))
        self._doc.text = self._doc.text[:a] + replacement + self._doc.text[b:]
        self.anchor = self.pos = self.selectionStart() + units(replacement)

    def setPosition(self, pos, mode=None):
        if mode is not self.MoveMode.KeepAnchor:
            self.anchor = pos
        self.pos = pos

class FakeDocument:
    def __init__(self, txt):
        self.text = txt

class FakeEditor:
    def __init__(self, txt, start=0, end=None):
        self.doc = FakeDocument(txt)
        self.cursor = FakeCursor(self.doc, start, start if end is None else end)
        self.focus_count = 0

    def textCursor(self):
        return self.cursor

    def setTextCursor(self, cursor):
        self.cursor = cursor

    def document(self):
        return self.doc

    def setFocus(self):
        self.focus_count += 1

class FakeInput:
    values = []

    @classmethod
    def getText(cls, *args):
        return cls.values.pop(0)

class FakeMessages:
    warnings = []

    @classmethod
    def warning(cls, *args):
        cls.warnings.append(args)

class FakeStatus:
    def showMessage(self, *args):
        pass

class FakeController:
    def __init__(self, editor, attrs=None):
        self.fragment_editor = editor
        self.attrs = attrs or {}
        self.main = SimpleNamespace(
            project=SimpleNamespace(custom_elements=Path("custom-elements.xml")),
            statusBar=lambda: FakeStatus(),
        )

    def _is_simple_xml_qname(self, text):
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_.-]*(?::[A-Za-z_][A-Za-z0-9_.-]*)?", text))

    def _custom_attributes_for_element(self, name):
        return self.attrs.get(name, [])

ns = {
    "QTextCursor": FakeCursor, "QInputDialog": FakeInput,
    "QLineEdit": SimpleNamespace(EchoMode=SimpleNamespace(Normal="normal")),
    "QMessageBox": FakeMessages,
    "_t": lambda key, **kw: key, "html_lib": html_lib,
}
exec(compile(ast.Module(body=[method_ast], type_ignores=[]), str(CODE), "exec"), ns)
run = ns["wrap_selection_with_element"]

def act(controller, editor, name, ok=True):
    FakeInput.values.append((name, ok))
    run(controller, editor)

# 1. Deux imbrications enchaînées sans re-sélectionner : on garde le texte,
# jamais les balises insérées. Contrat demandé, compatible avec Oxygen.
e = FakeEditor("avant uerbum après", 6, 12)
c = FakeController(e)
act(c, e, "app")
assert e.doc.text == "avant <app>uerbum</app> après", e.doc.text
assert e.cursor.selectedText() == "uerbum"
assert e.cursor.selectionStart() == units("avant <app>")
act(c, e, "rdg")
assert e.doc.text == "avant <app><rdg>uerbum</rdg></app> après", e.doc.text
assert e.cursor.selectedText() == "uerbum"
assert e.cursor.selectionStart() == units("avant <app><rdg>")
assert e.focus_count == 2
print("OK : Ctrl+E app puis rdg -> <app><rdg>[uerbum]</rdg></app>")

# 2. Attribut configuré vide AVEC sélection : seules les lettres restent
# sélectionnées (même si la balise ouvrante contient des attributs).
e = FakeEditor("text", 0, 4)
c = FakeController(e, {"rdg": [("wit", "", False)]})
act(c, e, "rdg")
assert e.doc.text == '<rdg wit="">text</rdg>'
assert e.cursor.selectedText() == "text"
assert e.cursor.selectionStart() == units('<rdg wit="">')
print("OK : sélection du seul contenu avec attribut vide")

# 2b. Sélection à rebours : conserver aussi l'orientation initiale.
e = FakeEditor("abc", 3, 0)
c = FakeController(e)
act(c, e, "seg")
assert e.doc.text == "<seg>abc</seg>"
assert e.cursor.selectedText() == "abc"
assert e.cursor.position() == units("<seg>")
act(c, e, "hi")
assert e.doc.text == "<seg><hi>abc</hi></seg>"
assert e.cursor.selectedText() == "abc"
assert e.cursor.position() == units("<seg><hi>")
print("OK : sélection inverse conservée au fil de deux Ctrl+E")

# 3. Aucun texte sélectionné, élément pair : curseur entre les balises.
e = FakeEditor("abcdef", 3)
c = FakeController(e)
act(c, e, "note")
assert e.doc.text == "abc<note></note>def"
assert not e.cursor.hasSelection()
assert e.cursor.pos == units("abc<note>")
print("OK : sans sélection, insertion de <note>|</note>")

# 4. Aucun texte sélectionné, attribut sans valeur par défaut : saisie de l'attribut.
e = FakeEditor("texte", 0)
c = FakeController(e, {"rdg": [("wit", "", False), ("type", "var", True)]})
act(c, e, "rdg")
assert e.doc.text == '<rdg wit="" type="var"></rdg>texte'
assert e.cursor.pos == units('<rdg wit="')
print("OK : sans sélection, priorité à l'attribut sans defaultValue")

# 5. Attribut avec valeur par défaut : curseur dans l'élément.
e = FakeEditor("", 0)
c = FakeController(e, {"hi": [("rend", "italic", True)]})
act(c, e, "hi")
assert e.doc.text == '<hi rend="italic"></hi>'
assert e.cursor.pos == units('<hi rend="italic">')
print("OK : attribut par défaut, curseur dans le contenu")

# 6. Notation abrégée pour une vraie balise vide XML (<lb/>).
e = FakeEditor("abc", 1)
c = FakeController(e)
act(c, e, "lb/")
assert e.doc.text == "a<lb/>bc"
assert not e.cursor.hasSelection()
assert e.cursor.pos == units("a<lb/>")
print("OK : notation lb/ → <lb/> et curseur après la balise")

# 7. Entrée invalide / insertion autoconfermante avec sélection : jamais de modification.
e = FakeEditor("texte", 0, 5)
c = FakeController(e)
warnings_before = len(FakeMessages.warnings)
act(c, e, "lb/")
assert e.doc.text == "texte" and e.cursor.hasSelection()
act(c, e, "nom avec espace")
assert e.doc.text == "texte" and e.cursor.hasSelection()
assert len(FakeMessages.warnings) == warnings_before + 2
act(c, e, "note", ok=False)
assert e.doc.text == "texte"
print("OK : sélection protégée, rejet de syntaxe invalide, annulation")

# 8. Sélection multiline et offsets UTF-16 (un emoji occupe deux unités).
e = FakeEditor("X😀\nY", 1, units("X😀\nY"))
c = FakeController(e)
act(c, e, "seg")
assert e.doc.text == "X<seg>😀\nY</seg>"
assert e.cursor.selectedText() == "😀\u2029Y"
assert e.cursor.selectionStart() == units("X<seg>")
assert e.cursor.pos == units("X<seg>😀\nY")
print("OK : sélection du contenu multiligne et positions UTF-16 correctes")

# 9. Le comportement est commun aux deux éditeurs, car un même corps de méthode
# est invoqué avec le target_editor concerné.
assert "target_editor.setTextCursor(new_cursor)" in CODE.read_text(encoding="utf-8")
print("Tous les tests Ctrl+E hors Qt sont passés.")
