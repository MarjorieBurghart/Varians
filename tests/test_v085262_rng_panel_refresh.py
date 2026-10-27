"""A01 V0.8.5.26.2 : états de validation sur révisions (sans Qt installé).

Les méthodes testées sont les méthodes réelles, extraites sans modification du
code source puis exécutées contre de petits substituts des widgets Qt.
"""
from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from varians_source import application_source, application_ast

ROOT = Path(__file__).resolve().parents[1]
CODE = application_source()


def _method(name):
    tree = application_ast()
    cls = next(n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == 'MainWindow')
    method = next(n for n in cls.body if isinstance(n, ast.FunctionDef) and n.name == name)
    # No PySide6 import, no source edits: execute precisely the production body.
    ns = {'_t': lambda key, **kw: key}
    exec(compile(ast.Module(body=[method], type_ignores=[]), str(ROOT / 'editeur_tei.py'), 'exec'), ns)
    return ns[name]


class DummyTimer:
    def __init__(self):
        self.start_args = []
        self.stops = 0
    def start(self, *a):
        self.start_args.append(a)
    def stop(self):
        self.stops += 1


class DummyLabel:
    def __init__(self):
        self.text = ''
    def setText(self, value):
        self.text = value
    def setStyleSheet(self, value):
        pass


class DummyDoc:
    rev = 5
    def revision(self):
        return self.rev


class DummyMain:
    _text_changed = _method('_text_changed')
    _auto_refresh_rng = _method('_auto_refresh_rng')
    show_validation_panel = _method('show_validation_panel')

    # Édition assemblée par XInclude (V0.9.0.0) : aucune ici.
    def _assembly_context(self):
        return None

    # Feuille XSLT affichée (V0.9.2.1) : aucune ici.
    def _displayed_stylesheet(self):
        return None

    # Fichier Schematron affiché (V0.9.2.4) : aucun ici.
    def _displayed_schematron(self):
        return None

    def __init__(self):
        self.doc = DummyDoc()
        self.editor = SimpleNamespace(document=lambda: self.doc)
        self.project = SimpleNamespace(schema_mode='project')
        # Schéma du document affiché (MainWindow._schema_mode).
        self._schema_mode = 'project'
        self._schema_file = None
        self.validation_panel = SimpleNamespace(isVisible=lambda: self.visible)
        self.visible = False
        self._rng_watch_enabled = False
        self._last_processed_edit_revision = 5
        self._last_rng_result = SimpleNamespace(valid=False)
        self._last_rng_revision = 5
        self._last_rng_schema_token = ('my-schema',)
        self._loading_editor_document = False
        self.modified = False
        self.formatted_view = SimpleNamespace(source_changed=lambda: None)
        self.validate_timer = DummyTimer()
        self.rng_refresh_timer = DummyTimer()
        self.validation_summary = DummyLabel()
        self.rng_status = DummyLabel()
        self.validation_table = object()
        self.clears = 0
        self.validation_calls = []
    def _set_title(self):
        pass
    def _clear_validation_table(self):
        self.clears += 1
    def _show_bottom_panel(self, panel, size):
        self.visible = True
    def validate_relaxng_document(self, **kwargs):
        self.validation_calls.append(kwargs)
        self._last_rng_result = SimpleNamespace(valid=True)
        self._last_rng_revision = self.doc.rev


def test_hidden_panel_edits_do_not_lose_auto_refresh():
    ui = DummyMain()
    ui.show_validation_panel()
    # Already validated revision 5: no pointless automatic second pass.
    assert ui.validation_calls == []
    ui.visible = False  # XPath tab or hidden validation panel
    ui.doc.rev = 6
    ui._text_changed()
    assert ui.clears == 1
    assert ui._last_rng_result is None
    assert ui._last_rng_revision == -1
    assert ui.rng_refresh_timer.start_args
    ui._auto_refresh_rng()
    assert ui.validation_calls[-1]['document_revision'] == 6
    assert ui._last_rng_revision == 6
    ui.visible = True
    ui.show_validation_panel()
    assert len(ui.validation_calls) == 1


def test_reopening_panel_with_outdated_revision_forces_validation():
    ui = DummyMain()
    ui.visible = False
    ui.doc.rev = 7  # correction while panel was closed
    ui.show_validation_panel()
    assert ui.validation_calls[-1]['document_revision'] == 7
    assert ui._last_rng_revision == 7


def test_new_revision_invalidates_once_even_if_both_qt_signals_fire():
    ui = DummyMain()
    ui._rng_watch_enabled = True
    ui.doc.rev = 6
    ui._text_changed()  # QTextDocument.contentsChanged
    ui._text_changed()  # QPlainTextEdit.textChanged, same revision
    assert ui.clears == 1
    assert len(ui.rng_refresh_timer.start_args) == 1
    assert ui.modified


def test_validation_work_is_deferred_until_panel_first_opened():
    ui = DummyMain()
    ui.doc.rev = 6
    ui._text_changed()
    assert not ui.rng_refresh_timer.start_args
    ui._auto_refresh_rng()
    assert not ui.validation_calls
    ui.show_validation_panel()
    assert len(ui.validation_calls) == 1


def test_real_relaxng_cache_discards_old_error_log(tmp_path):
    from relaxng_validation import validate_relaxng, clear_relaxng_cache
    schema = tmp_path / 'test.rng'
    schema.write_text('''<grammar xmlns="http://relaxng.org/ns/structure/1.0">
      <start><element name="root"><element name="p"><text/></element></element></start>
    </grammar>''', encoding='utf-8')
    clear_relaxng_cache()
    bad = validate_relaxng('<root><wrong/></root>', schema)
    assert not bad.valid and bad.issues
    good = validate_relaxng('<root><p>fixed</p></root>', schema)
    assert good.valid and not good.issues
    bad_again = validate_relaxng('<root><wrong/></root>', schema)
    assert not bad_again.valid and bad_again.issues
    good_again = validate_relaxng('<root><p>fixed again</p></root>', schema)
    assert good_again.valid and not good_again.issues


def test_outdated_schema_resolution_is_not_published(monkeypatch):
    """A late completion must not repopulate errors from an earlier revision."""
    import builtins
    method = _method('_validate_relaxng_document_impl')
    ui = DummyMain()
    ui._rng_watch_enabled = True
    ui._last_rng_result = None
    ui._last_schema_resolution = None
    ui._completion_resolution_key = None
    ui._completion_resolution = None
    ui._schema_resolution_cache_key = lambda text: ('schema',)
    ui.editor.toPlainText = lambda: '<root/>'
    ui.current_path = None
    ui.project.edition = Path('example.xml')
    ui.project.schema = None

    def delayed_resolution(**kwargs):
        # Change the editor during an unusually long schema resolution.
        ui.doc.rev += 1
        return SimpleNamespace(schema_path=Path('test.rng'), error=None)

    method.__globals__['resolve_schema'] = delayed_resolution
    result = method(ui, show_panel=False, document_revision=5, automatic=True)
    assert result is None
    assert ui._last_rng_result is None
    assert ui._last_rng_revision == 5
    assert ui.rng_refresh_timer.start_args[-1] == (180,)
