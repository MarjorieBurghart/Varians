# -*- coding: utf-8 -*-
"""Internationalisation XML partagée par l'éditeur et le viewer web.

Les traductions résident dans ``i18n/*.xml``. Chaque fichier suit la forme :

    <translations lang="fr" label="Français">
      <string key="editor.save">Enregistrer</string>
    </translations>

Les clés manquantes retombent sur la langue de secours puis, en dernier recours,
sur la clé elle-même. Les variables utilisent ``str.format`` :
``{count}``, ``{path}``, etc.

Un nombre qui compte des choses prend la forme plurielle de la langue, en
syntaxe ICU (V0.9.3.4) : ``{count, plural, one {# ligne} other {# lignes}}``.
« # » est le nombre, « =0 {…} » vise une valeur exacte ; une catégorie
absente retombe sur ``other``. Les catégories sont celles de CLDR pour les
nombres entiers (``plural_category``) ; le viewer web suit les mêmes règles
(``web_viewer/plurals.js``).
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import string
import xml.etree.ElementTree as ET


def plural_category(language: str, number: int) -> str:
    """Catégorie plurielle CLDR d'un nombre entier dans ``language``."""
    code = (language or "").replace("_", "-").split("-")[0].lower()
    n = abs(int(number))
    if code == "ja":
        return "other"
    if code == "fr":
        return "one" if n in (0, 1) else "other"
    if code == "cs":
        return "one" if n == 1 else "few" if 2 <= n <= 4 else "other"
    if code == "ru":
        if n % 10 == 1 and n % 100 != 11:
            return "one"
        if 2 <= n % 10 <= 4 and not 12 <= n % 100 <= 14:
            return "few"
        return "many"
    return "one" if n == 1 else "other"


_PLURAL = re.compile(r"\{\s*([A-Za-z0-9_]+)\s*,\s*plural\s*,")
_SELECTOR = re.compile(r"\s*(=\d+|[a-z]+)\s*\{")


def _closing_brace(text: str, start: int) -> int:
    """Position de l'accolade qui ferme celle de ``start``, ou -1."""
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return -1


def _plural_at(text: str, start: int):
    """(fin, variable, branches) de la forme plurielle qui commence en
    ``start``, ou None si elle est mal formée."""
    match = _PLURAL.match(text, start)
    if not match:
        return None
    position, branches = match.end(), {}
    while True:
        while position < len(text) and text[position].isspace():
            position += 1
        if position >= len(text):
            return None
        if text[position] == "}":
            return position + 1, match.group(1), branches
        selector = _SELECTOR.match(text, position)
        if not selector:
            return None
        close = _closing_brace(text, selector.end() - 1)
        if close < 0:
            return None
        branches[selector.group(1)] = text[selector.end():close]
        position = close + 1


def _plurals(text: str):
    """Formes plurielles de premier niveau : (début, fin, variable, branches)."""
    position = 0
    while "plural" in text:
        match = _PLURAL.search(text, position)
        if not match:
            return
        found = _plural_at(text, match.start())
        if found is None:
            position = match.end()
            continue
        end, name, branches = found
        yield match.start(), end, name, branches
        position = end


def plural_constructs(text: str) -> list[tuple[str, dict[str, str]]]:
    """Toutes les formes plurielles du texte, imbriquées comprises :
    (variable, {catégorie ou =N: texte})."""
    result = []
    for _start, _end, name, branches in _plurals(text):
        result.append((name, branches))
        for branch in branches.values():
            result.extend(plural_constructs(branch))
    return result


def _number_sign(branch: str, number: str) -> str:
    """« # » remplacé par le nombre, hors des formes imbriquées."""
    out, depth = [], 0
    for char in branch:
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        out.append(number if char == "#" and depth == 0 else char)
    return "".join(out)


def expand_plurals(text: str, language: str, values: dict) -> str:
    """Chaque forme plurielle remplacée par sa branche pour la valeur de sa
    variable dans ``language`` ; les autres variables restent « {nom} »."""
    out, position = [], 0
    for start, end, name, branches in _plurals(text):
        out.append(text[position:start])
        position = end
        if name not in values:
            out.append(text[start:end])
            continue
        value = values[name]
        try:
            number = int(value) if not isinstance(value, bool) and str(value).strip().lstrip("-").isdigit() else None
        except (TypeError, ValueError):
            number = None
        category = plural_category(language, number) if number is not None else "other"
        branch = branches.get(f"={number}") if number is not None else None
        if branch is None:
            branch = branches.get(category, branches.get("other", next(iter(branches.values()), "")))
        out.append(expand_plurals(_number_sign(branch, str(value)), language, values))
    out.append(text[position:])
    return "".join(out)


def message_fields(text: str) -> set[str]:
    """Variables d'un message : celles des formes plurielles et les « {nom} »
    du texte et de chaque branche."""
    names, plain, position = set(), [], 0
    for start, end, name, branches in _plurals(text):
        plain.append(text[position:start])
        position = end
        names.add(name)
        for branch in branches.values():
            names |= message_fields(_number_sign(branch, ""))
    plain.append(text[position:])
    for part in plain:
        try:
            names |= {field.split(".", 1)[0].split("[", 1)[0]
                      for _, field, _, _ in string.Formatter().parse(part) if field}
        except ValueError:
            pass
    return names


def format_message(text: str, language: str, **values) -> str:
    """Le message, formes plurielles choisies et variables remplacées."""
    if not values:
        return text
    text = expand_plurals(text, language, values)
    try:
        return text.format(**values)
    except Exception:
        return text


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
        # Le pluriel suit la langue du texte trouvé, celle de secours comprise.
        language = self.language
        text = self._catalogs.get(self.language, {}).get(key)
        if text is None:
            language = self.fallback
            text = self._catalogs.get(self.fallback, {}).get(key)
        if text is None:
            language = self.language
            text = default if default is not None else key
        return format_message(text, language, **values)

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
