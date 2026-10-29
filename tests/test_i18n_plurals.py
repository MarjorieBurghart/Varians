# -*- coding: utf-8 -*-
"""Red team 2 (cohérence des textes, D8) : formes plurielles par langue.

Un nombre était suivi de « (s) », « /i », « (en) »… ou d'un pluriel fixe
(« 1 lignes », « 1 chyb », « 21 строк »). Les catalogues écrivent désormais
les deux (ou quatre) formes, dans la syntaxe ICU :

    {count, plural, one {# ligne} other {# lignes}}

« # » est le nombre ; « =0 {…} » vise une valeur exacte. Les catégories
sont celles de la langue (CLDR, nombres entiers) : français 0 et 1 au
singulier ; anglais, allemand, italien 1 seul ; tchèque one, few (2–4),
other ; russe one (21, 101…), few (2–4, 22…), many (5–20, 11–14…) ; japonais
other. L'éditeur (I18nManager.tr) et le viewer web (plurals.js) suivent les
mêmes règles. Les feuilles livrées n'ont pas de pluriel."""
from __future__ import annotations

import json
import re
import shutil
import string
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from i18n import I18nManager, expand_plurals, message_fields, plural_category, plural_constructs

ROOT = Path(__file__).resolve().parents[1]
PLURALS_JS = ROOT / "web_viewer" / "plurals.js"
LANGUAGES = ("fr", "en", "de", "it", "cs", "ru", "ja")
CATEGORIES = {"fr": {"one", "other"}, "en": {"one", "other"}, "de": {"one", "other"}, "it": {"one", "other"},
              "cs": {"one", "few", "other"}, "ru": {"one", "few", "many", "other"}, "ja": {"other"}}
NUMBERS = (0, 1, 2, 3, 4, 5, 11, 12, 14, 21, 22, 25, 101, 111, 1000)
# Variables qui comptent des choses (et non un sigle, un nom ou une durée).
COUNTS = {"count", "lines", "witnesses", "variants", "documents", "sections", "problems", "downloaded",
          "paragraphs", "selected", "total", "pages", "marked", "eligible", "cached", "missing", "excluded",
          "skipped", "failed", "index", "expected"}


def _catalog(language):
    root = ET.parse(ROOT / "i18n" / f"{language}.xml").getroot()
    return {node.get("key"): "".join(node.itertext()) for node in root.findall("string")}


@pytest.mark.parametrize("language, expected", [
    ("fr", {0: "one", 1: "one", 2: "other", 5: "other", 21: "other"}),
    ("en", {0: "other", 1: "one", 2: "other", 21: "other"}),
    ("de", {0: "other", 1: "one", 2: "other"}),
    ("it", {0: "other", 1: "one", 2: "other"}),
    ("cs", {0: "other", 1: "one", 2: "few", 4: "few", 5: "other", 21: "other", 22: "other"}),
    ("ru", {0: "many", 1: "one", 2: "few", 4: "few", 5: "many", 11: "many", 12: "many", 14: "many",
            21: "one", 22: "few", 25: "many", 101: "one", 111: "many"}),
    ("ja", {0: "other", 1: "other", 2: "other"}),
])
def test_the_plural_category_of_each_language(language, expected):
    assert {n: plural_category(language, n) for n in expected} == expected


@pytest.mark.parametrize("language, values, expected", [
    ("fr", {"count": 0}, "0 ligne"),
    ("fr", {"count": 1}, "1 ligne"),
    ("fr", {"count": 2}, "2 lignes"),
    ("en", {"count": 0}, "0 lignes"),
    ("ru", {"count": 5}, "5 lignes"),          # « many » absent : « other »
    ("ja", {"count": 1}, "1 lignes"),
    ("fr", {"count": "x"}, "x lignes"),        # pas un nombre : « other »
])
def test_a_plural_is_expanded_with_the_number(language, values, expected):
    assert expand_plurals("{count, plural, one {# ligne} other {# lignes}}", language, values) == expected


def test_exact_values_nesting_and_other_placeholders():
    text = "{n, plural, =0 {aucun passage} one {# passage de {witness}} other {# passages de {witness}}}"
    assert expand_plurals(text, "fr", {"n": 0}) == "aucun passage"
    assert expand_plurals(text, "fr", {"n": 1}) == "1 passage de {witness}"
    assert expand_plurals(text, "fr", {"n": 3}) == "3 passages de {witness}"
    twice = "{a, plural, one {# erreur} other {# erreurs}}, {b, plural, one {# avertissement} other {# avertissements}}"
    assert expand_plurals(twice, "fr", {"a": 2, "b": 1}) == "2 erreurs, 1 avertissement"
    nested = "{a, plural, one {# texte, {b, plural, one {# page} other {# pages}}} other {# textes}}"
    assert expand_plurals(nested, "fr", {"a": 1, "b": 4}) == "1 texte, 4 pages"
    assert expand_plurals("Rien {ici}", "fr", {"ici": 1}) == "Rien {ici}"
    assert expand_plurals(text, "fr", {}) == text          # valeur absente : texte laissé tel quel
    assert message_fields(text) == {"n", "witness"}
    assert message_fields("{base} : {count, plural, one {# ligne} other {# lignes}}") == {"base", "count"}


def test_the_editor_uses_the_language_where_the_text_was_found(tmp_path):
    folder = tmp_path / "i18n"
    folder.mkdir()
    (folder / "fr.xml").write_text('<translations lang="fr" label="Français">'
                                   '<string key="essai.a">{n, plural, one {# fichier} other {# fichiers}}</string>'
                                   '</translations>', encoding="utf-8")
    (folder / "en.xml").write_text('<translations lang="en" label="English">'
                                   '<string key="essai.b">{n, plural, one {# file} other {# files}}</string>'
                                   '</translations>', encoding="utf-8")
    manager = I18nManager(folder, "fr", "en")
    assert manager.tr("essai.a", n=0) == "0 fichier"
    assert manager.tr("essai.b", n=0) == "0 files"          # texte anglais : règle anglaise
    assert manager.tr("essai.a", n=12) == "12 fichiers"


def test_the_viewer_expands_plurals_like_the_editor(tmp_path):
    node = shutil.which("node")
    if not node:
        pytest.skip("Node.js unavailable")
    cases = []
    for language in LANGUAGES:
        catalog = _catalog(language)
        for key, text in catalog.items():
            if plural_constructs(text):
                names = message_fields(text)
                cases.extend({"lang": language, "text": text, "vars": {name: n for name in names}} for n in NUMBERS)
    cases.append({"lang": "ru", "text": "{n, plural, =0 {нет} one {# строка} few {# строки} many {# строк} "
                                        "other {# строки}}", "vars": {"n": 0}})
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases, ensure_ascii=False), encoding="utf-8")
    js = (f"const P=require({json.dumps(str(PLURALS_JS))});"
          f"const C=JSON.parse(require('fs').readFileSync({json.dumps(str(data))},'utf8'));"
          "process.stdout.write(JSON.stringify({cats:[0,1,2,5,11,21,22,101,111].map(n=>"
          "['fr','en','de','it','cs','ru','ja'].map(l=>P.category(l,n))),"
          "texts:C.map(c=>P.expand(c.text,c.lang,c.vars))}));")
    run = subprocess.run([node, "-e", js], capture_output=True, text=True, timeout=60)
    assert run.returncode == 0, run.stderr
    result = json.loads(run.stdout)
    assert result["cats"] == [[plural_category(language, n) for language in ("fr", "en", "de", "it", "cs", "ru", "ja")]
                              for n in (0, 1, 2, 5, 11, 21, 22, 101, 111)]
    assert len(cases) > 100
    assert result["texts"] == [expand_plurals(c["text"], c["lang"], c["vars"]) for c in cases]


def test_the_viewer_translation_function_expands_plurals():
    from web_viewer.generator import HTML_TEMPLATE
    assert "__PLURAL_JS__" in HTML_TEMPLATE
    function = HTML_TEMPLATE.split("function t(key,vars={}){", 1)[1].split("\n", 1)[0]
    assert "VariansPlural.expand(" in function


@pytest.mark.parametrize("language", LANGUAGES)
def test_every_plural_of_the_catalogs_is_well_formed(language):
    catalog = _catalog(language)
    found = 0
    for key, text in catalog.items():
        for name, branches in plural_constructs(text):
            found += 1
            assert "other" in branches, (language, key)
            assert set(b for b in branches if not b.startswith("=")) <= CATEGORIES[language], (language, key)
            assert name in COUNTS, (language, key, name)
        values = {name: 7 for name in message_fields(text)}
        for n in NUMBERS:
            values.update({name: n for name in values if name in COUNTS})
            shown = expand_plurals(text, language, values)
            assert "plural," not in shown, (language, key)
            assert {f for _, f, _, _ in string.Formatter().parse(shown) if f} <= set(values), (language, key)
    if language != "ja":
        assert found >= 10, language


MARKERS = {
    "fr": r"\(s\)|\(e\)s?|\(es\)",
    "en": r"\((s|es)\)",
    "de": r"\w\((n|e|en|se|r|s)\)",
    "it": r"\w/[ie]\b",
    "cs": r"\w\((a|u|i|y|ů)\)",
}
# Ne comptent rien : « attribut(s) configuré(s) : {attrs} », « {witnesses} »
# (liste de sigles) ; « (n) » est la marque affichée.
NOT_COUNTED = {"ctrl_e.inserted_attrs", "viewer.show_notes.tip", "project.listwit.id_used",
               "project.listwit.no_listwit"}
# Mots qui ne varient pas avec le nombre : prépositions, participes anglais et
# allemands, noms allemands invariables (« 1 Fehler », « 3 Fehler »).
INVARIANT = {
    "fr": {"à", "en"},
    "en": {"of", "to", "already", "cached", "selected", "excluded", "downloaded", "failed"},
    "de": {"von", "ausgewählt", "lokal", "ausstehend", "ausgeschlossen", "heruntergeladen", "vorhanden",
           "fehlgeschlagen", "Treffer", "Fehler", "Validierungsfehler"},
    "it": {"in", "da"},
    "cs": {"ke", "z", "za"},
    "ru": {"из", "за"},
}


@pytest.mark.parametrize("language", sorted(MARKERS))
def test_no_number_is_followed_by_a_makeshift_plural(language):
    found = [key for key, text in _catalog(language).items()
             if key not in NOT_COUNTED and re.search(MARKERS[language], text)]
    assert found == []


def _outside_plurals(text):
    for _name, branches in plural_constructs(text):
        for branch in branches.values():
            text = text.replace(branch, "")
    return text


@pytest.mark.parametrize("language", ["fr", "en", "de", "it", "cs", "ru"])
def test_a_counted_noun_agrees_with_its_number(language):
    """Un nombre suivi d'un mot (« {count} lignes », « {total} изображений »)
    est dans un pluriel ; sinon il suit un intitulé (« Замен : {count} »)."""
    found = []
    for key, text in _catalog(language).items():
        if key in NOT_COUNTED:
            continue
        for name, word in re.findall(r"\{([a-z]+)\} ([^\W\d_]+)", _outside_plurals(text)):
            if name in COUNTS and not word[:2].isupper() and word not in INVARIANT[language]:
                found.append((key, name, word))
    assert found == []


def test_the_delivered_stylesheets_use_no_plural():
    """Les feuilles livrées remplacent seulement « {nom} » : leurs textes
    n'ont pas de pluriel."""
    used = set()
    for sheet in (ROOT / "rendering").glob("*.xsl"):
        text = sheet.read_text(encoding="utf-8")
        used |= set(re.findall(r"f:libelle\('([^']+)'", text))
        used |= set(re.findall(r'<string key="([^"]+)"', text))
    assert "publication.error.no_lemma" in used
    for language in LANGUAGES:
        catalog = _catalog(language)
        assert [key for key in used if key in catalog and plural_constructs(catalog[key])] == [], language
