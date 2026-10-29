"""Check dialog wiring statically where the CI runner has no PySide6."""
from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]
DIALOGS = (ROOT / "project_dialogs.py").read_text(encoding="utf-8")


def _init_source(cls):
    module=ast.parse(DIALOGS)
    node=next(n for n in module.body if isinstance(n, ast.ClassDef) and n.name==cls)
    init=next(n for n in node.body if isinstance(n,ast.FunctionDef) and n.name=='__init__')
    return ast.get_source_segment(DIALOGS,init)


def test_new_project_pivot_options_visible_next_to_starting_point():
    code=_init_source('NewProjectDialog')
    assert code.index('self.pivot_section = QGroupBox') < code.index('self.edition = PathRow')
    assert code.index('form.addRow(tr("project.new.mode"), self.creation_mode)') < code.index("form.addRow('', self.pivot_section)") < code.index('form.addRow(tr("project.edition"), self.edition)')
    assert 'self.pivot_prepare = QCheckBox' in code and 'self.pivot_lines = QCheckBox' in code
    assert 'self.pivot_lines.setChecked(True)' in code
    assert 'self.pivot_prepare.toggled.connect(self._pivot_enabled)' in code
    assert 'scroll = QScrollArea(self)' in code and 'scroll.setWidgetResizable(True)' in code
    assert 'outer.addWidget(buttons)' in code
    assert 'Varians 0.8.5.10' in code


def test_project_settings_pivot_before_large_witness_table():
    code=_init_source('ProjectSettingsDialog')
    assert code.index('root.addWidget(self.pivot_section)') < code.index('self.witnesses_table = WitnessTable')
    assert 'self.pivot_prepare = QCheckBox' in code and 'self.pivot_lines = QCheckBox' in code
    assert 'scroll = QScrollArea(self)' in code and 'scroll.setWidgetResizable(True)' in code
    assert 'outer.addWidget(buttons)' in code
    assert 'Varians 0.8.5.10' in code


def test_scaffold_confirmation_and_opt_in_are_preserved():
    assert chr(34) + "prepare_pivot" + chr(34) + ": self.pivot_prepare.isChecked()" in DIALOGS
    assert 'QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No' in DIALOGS
    assert 'message.setDefaultButton(QMessageBox.StandardButton.No)' in DIALOGS
    assert 'include_lb=include_lb' in DIALOGS


def test_help_pages_explain_new_location_in_all_languages():
    for lang in ('fr','en','de','ja','cs','it','ru'):
        help_text=(ROOT/'help'/f'{lang}.html').read_text(encoding='utf8')
        # V0.9.3.1 : l'aide n'annonce plus les versions.
        assert '<h3' in help_text and '&lt;lb/&gt;' in help_text
