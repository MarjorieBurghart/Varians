# -*- coding: utf-8 -*-
"""Internationalisation XML partagée par l'éditeur et le viewer web.

Les traductions résident dans ``i18n/*.xml``. Chaque fichier suit la forme :

    <translations lang="fr" label="Français">
      <string key="editor.save">Enregistrer</string>
    </translations>

Les clés manquantes retombent sur la langue de secours puis, en dernier recours,
sur la clé elle-même. Les variables utilisent ``str.format`` :
``{count}``, ``{path}``, etc.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class LanguageInfo:
    code: str
    label: str
    path: Path


class I18nManager:
    def __init__(self, directory: str | Path, language: str = "fr", fallback: str = "en"):
        self.directory = Path(directory).resolve()
        self.language = language or "fr"
        self.fallback = fallback or "en"
        self._catalogs: dict[str, dict[str, str]] = {}
        self._labels: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self._catalogs.clear()
        self._labels.clear()
        # Le catalogue installé fournit les nouvelles clés ajoutées après la
        # création d'un projet ; celui du projet reste prioritaire pour chaque
        # valeur traduite ou personnalisée. Aucun fichier utilisateur réécrit.
        installed_dir = Path(__file__).resolve().parent / "i18n"
        for directory in (installed_dir, self.directory):
            if not directory.exists():
                continue
            for path in sorted(directory.glob("*.xml")):
                try:
                    root = ET.parse(path).getroot()
                except Exception:
                    continue
                if root.tag != "translations":
                    continue
                code = (root.get("lang") or path.stem).strip()
                if not code:
                    continue
                label = (root.get("label") or code).strip()
                catalog = self._catalogs.setdefault(code, {})
                for node in root.findall("string"):
                    key = (node.get("key") or "").strip()
                    if key:
                        catalog[key] = "".join(node.itertext()).replace("\\n", "\n").replace("\\t", "\t")
                self._labels[code] = label

    def available_languages(self) -> list[LanguageInfo]:
        return [
            LanguageInfo(code, self._labels.get(code, code), self.directory / f"{code}.xml")
            for code in sorted(self._catalogs)
        ]

    def set_language(self, code: str) -> bool:
        if code not in self._catalogs:
            return False
        self.language = code
        return True

    def tr(self, key: str, default: str | None = None, **values) -> str:
        text = self._catalogs.get(self.language, {}).get(key)
        if text is None:
            text = self._catalogs.get(self.fallback, {}).get(key)
        if text is None:
            text = default if default is not None else key
        if values:
            try:
                return text.format(**values)
            except Exception:
                return text
        return text

    def export_catalogs(self) -> dict:
        return {
            "default": self.language,
            "fallback": self.fallback,
            "languages": [
                {"code": x.code, "label": x.label}
                for x in self.available_languages()
            ],
            "catalogs": self._catalogs,
        }


def load_i18n(directory: str | Path, language: str = "fr", fallback: str = "en") -> I18nManager:
    return I18nManager(directory, language, fallback)
