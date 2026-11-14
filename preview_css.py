# -*- coding: utf-8 -*-
"""CSS de l'aperçu de la vue XSLT / CSS, sans Qt (V0.9.4.7, extrait de
formatted_view) : règles de Varians (``PREVIEW_BASE_CSS``), variables CSS
résolues (``resolve_css_variables``, ``resolve_style_variables``), feuille
qui a son propre ``<style>`` (``has_own_style``)."""
from __future__ import annotations

import re


_ROOT_BLOCK = re.compile(r":root\s*\{(.*?)\}", re.I | re.S)
_CSS_DECLARATION = re.compile(r"(--[\w-]+)\s*:\s*([^;]+)")
_CSS_VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(?:,\s*([^()]*(?:\([^()]*\)[^()]*)*))?\)")
_STYLE_BLOCK = re.compile(r"(<style\b[^>]*>)(.*?)(</style\s*>)", re.I | re.S)


def resolve_css_variables(css_text):
    """Résout les variables CSS des blocs ``:root`` pour le moteur HTML
    simplifié de Qt, qui ne comprend pas ``var()`` : chaque ``var(--x)`` prend
    la valeur de ``--x`` ; une variable peut en citer une autre ; une
    variable inconnue prend sa valeur de repli (``var(--x, repli)``)."""
    blocks = list(_ROOT_BLOCK.finditer(css_text))
    if not blocks:
        return css_text
    variables = {}
    for block in blocks:
        variables.update((name, value.strip()) for name, value in _CSS_DECLARATION.findall(block.group(1)))
    out = _ROOT_BLOCK.sub("", css_text)

    def value(match):
        name, fallback = match.group(1), match.group(2)
        if name in variables:
            return variables[name]
        return fallback.strip() if fallback is not None else match.group(0)

    for _ in range(8):                       # variables qui en citent d'autres
        resolved = _CSS_VAR.sub(value, out)
        if resolved == out:
            break
        out = resolved
    return out


def resolve_style_variables(html_text):
    """Les variables CSS des ``<style>`` d'une page produite par une feuille
    XSLT, remplacées par leur valeur (V0.9.4.4) ; le reste de la page ne
    change pas."""
    return _STYLE_BLOCK.sub(lambda m: m.group(1) + resolve_css_variables(m.group(2)) + m.group(3), html_text)


def has_own_style(html_text):
    """La page produite par la feuille a son propre ``<style>`` (V0.9.4.4) :
    une vue sans fichier CSS laisse alors de côté la CSS du projet, sauf
    ``projectCss="always"``."""
    return _STYLE_BLOCK.search(html_text) is not None


# Règles de base de l'aperçu (V0.9.3.0), placées avant la CSS du projet, qui
# les remplace si elle en a : une strophe de la feuille livrée (un seul bloc,
# vers séparés par des <br/>) en retrait, même avec la CSS d'un projet créé
# par une version antérieure. Qt ignore toute règle placée après un @media :
# celles du crayon ✎ et des repères de ligne, autrefois ajoutées à la fin,
# n'étaient pas appliquées (le crayon était un lien bleu souligné).
PREVIEW_BASE_CSS = (
    ".lg { margin-top: 0.5em; margin-bottom: 1em; margin-left: 2em; line-height: 150%; }\n"
    ".ref { color: #8a8177; }\n"
    ".rature { text-decoration: line-through; }\n"
    ".ajout { text-decoration: underline; }\n"
    ".sic { font-style: italic; }\n"
    ".lacune { color: #8a8177; }\n"
    ".petites-capitales { font-variant: small-caps; }\n"
    ".speaker { font-variant: small-caps; font-weight: 600; letter-spacing: 0.04em; margin-top: 0.6em; }\n"
    ".stage { font-style: italic; color: #5d554c; }\n"
    "div.stage { margin-left: 1.6em; margin-bottom: 0.4em; }\n"
    "a.tei-edit-marker { color:#8a8177; text-decoration:none; font-family:sans-serif; font-size:0.75em;"
    " padding-right:0.35em; }\n"
    "a.tei-line-marker { color: transparent; text-decoration:none; font-size:0; line-height:0; margin:0;"
    " padding:0; white-space:nowrap; }\n"
)
