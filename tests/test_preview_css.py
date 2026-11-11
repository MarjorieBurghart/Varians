# -*- coding: utf-8 -*-
"""CSS de l'aperçu (V0.9.4.4), sans fenêtre : variables CSS remplacées par
leur valeur, dans un fichier CSS comme dans le <style> produit par une
feuille XSLT (Qt ne comprend pas ``var()``) ; une feuille qui produit son
propre <style>."""
from __future__ import annotations

from formatted_view import has_own_style, resolve_css_variables, resolve_style_variables


def test_css_variables_are_replaced_by_their_value():
    css = (":root { --encre: #202d37; --papier:#fffefa; --ombre: 0 2px 4px rgba(0,0,0,.1) }\n"
           "body { color: var(--encre); background: var( --papier ); }\n"
           ".carte { box-shadow: var(--ombre); }")
    out = resolve_css_variables(css)
    assert "var(" not in out and ":root" not in out
    assert "color: #202d37" in out and "background: #fffefa" in out and "0 2px 4px rgba(0,0,0,.1)" in out


def test_variables_with_fallbacks_nesting_and_several_root_blocks():
    css = (":root{--base:#123456;--titre:var(--base)}\n"
           ":root{--fond:#eeeeee;}\n"
           "h1{color:var(--titre)} p{color:var(--absente, #654321)} div{background:var(--fond)}")
    out = resolve_css_variables(css)
    assert "h1{color:#123456}" in out and "p{color:#654321}" in out and "div{background:#eeeeee}" in out


def test_a_css_without_variables_is_unchanged():
    css = "p { color: red; }\n@media (max-width: 600px) { p { color: blue; } }"
    assert resolve_css_variables(css) == css


def test_variables_of_a_style_produced_by_the_stylesheet_are_replaced():
    html = ("<html><head><style>:root{--rouge:#cc0000}p.x{color:var(--rouge)}</style></head>"
            "<body><p class='x'>var(--rouge) reste dans le texte</p></body></html>")
    out = resolve_style_variables(html)
    assert "p.x{color:#cc0000}" in out and "var(--rouge) reste dans le texte" in out


def test_a_stylesheet_with_its_own_style_is_recognized():
    assert has_own_style("<html><head><STYLE type='text/css'>p{}</STYLE></head></html>")
    assert not has_own_style("<html><head><link rel='stylesheet' href='tei.css'/></head><body>style</body></html>")
