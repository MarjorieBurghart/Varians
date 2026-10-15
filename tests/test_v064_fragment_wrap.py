from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_fragment_editor_has_visual_wrap_checkbox_and_persistence():
    source = (ROOT / "editeur_tei.py").read_text(encoding="utf-8")
    assert 'self.fragment_visual_wrap = QCheckBox(_t("source.visual_wrap")' in source
    assert '"fragmentVisualWrap"' in source
    assert 'self.fragment_editor.set_visual_wrap(bool(_fragment_wrap_setting))' in source
    assert 'self.fragment_visual_wrap.toggled.connect(self._set_fragment_visual_wrap)' in source
    assert 'self.fragment_visual_wrap.setText(_t("source.visual_wrap"))' in source


def test_v064_feature_survives_later_versions():
    source = (ROOT / "editeur_tei.py").read_text(encoding="utf-8")
    assert 'fragmentVisualWrap' in source
