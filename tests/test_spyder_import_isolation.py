# -*- coding: utf-8 -*-
"""Regression: Spyder keeps conflicting modules from an old installation."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SpyderImportIsolation(unittest.TestCase):
    def test_old_modules_cannot_shadow_current_version(self):
        with tempfile.TemporaryDirectory() as folder:
            old = Path(folder)
            for module in ("project_config", "project_management", "i18n", "xpath_search", "iiif_manifest", "alto_import"):
                (old / f"{module}.py").write_text("ORIGIN = 'OLD'\n", encoding="utf-8")
            (old / "web_viewer").mkdir()
            (old / "web_viewer" / "__init__.py").write_text("", encoding="utf-8")
            (old / "web_viewer" / "generator.py").write_text("ORIGIN = 'OLD'\n", encoding="utf-8")
            code = r"""
import sys, runpy
from pathlib import Path
old = Path(sys.argv[1]).resolve()
new = Path(sys.argv[2]).resolve()
sys.path.insert(0, str(old))
import project_config, project_management, i18n, xpath_search, iiif_manifest, alto_import, web_viewer.generator
assert getattr(project_management, 'ORIGIN') == 'OLD'
# Simulate Spyder running editeur_tei.py in a kernel already using V0.4.
try:
    runpy.run_path(str(new / 'editeur_tei.py'), run_name='__test_only__')
except ModuleNotFoundError as exc:
    if exc.name != 'PySide6':
        raise
except ImportError as exc:
    if 'PySide6' not in str(exc):
        raise
# The current release must be used even though an older release was cached.
assert Path(sys.modules['project_config'].__file__).resolve().parent == new
assert Path(sys.modules['project_management'].__file__).resolve().parent == new
import alto_import
assert Path(alto_import.__file__).resolve().parent == new
assert hasattr(sys.modules['project_management'], 'create_local_xslt_if_needed')
# The GUI can be unavailable during tests: i18n loads after project_dialogs.
import i18n
assert Path(i18n.__file__).resolve().parent == new
import xpath_search
assert Path(xpath_search.__file__).resolve().parent == new
from web_viewer import generator
assert Path(generator.__file__).resolve().parents[1] == new
print('PASS: imports from current release (including web_viewer)')
"""
            result = subprocess.run([sys.executable, "-c", code, str(old), str(ROOT)],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stdout + "\n" + result.stderr)
            self.assertIn("PASS: imports", result.stdout)


if __name__ == "__main__":
    unittest.main()
