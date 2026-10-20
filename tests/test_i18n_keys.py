# -*- coding: utf-8 -*-
"""Chaque clé de traduction écrite en clair dans le code existe dans les sept
catalogues i18n (sinon l'interface afficherait la clé elle-même)."""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("fr", "en", "de", "ja", "cs", "it", "ru")
# _t("clé", …), tr("clé", …) ou self.tr("clé", …)
KEY_CALL = re.compile(r"""\b(?:_t|tr|self\.tr)\(\s*(['"])([A-Za-z0-9_.\-]+)\1""")


def _used_keys():
    used = {}
    for path in sorted(ROOT.glob("*.py")) + sorted((ROOT / "web_viewer").glob("*.py")):
        for match in KEY_CALL.finditer(path.read_text(encoding="utf-8")):
            key = match.group(2)
            if key.endswith("."):          # préfixe d'une clé complétée à l'exécution
                continue
            used.setdefault(key, path.name)
    return used


def test_every_literal_translation_key_exists_in_the_seven_catalogs():
    used = _used_keys()
    assert len(used) > 500
    assert "documents.unsaved.text" in used
    for language in LANGUAGES:
        root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
        catalog = {string.get("key") for string in root.findall("string")}
        missing = sorted(f"{key} ({used[key]})" for key in used if key not in catalog)
        assert not missing, (language, missing)
