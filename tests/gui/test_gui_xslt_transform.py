# -*- coding: utf-8 -*-
"""Transformation XSLT de l'aperçu (formatted_view.transform_with_xslt)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TEI = ('<TEI xmlns="http://www.tei-c.org/ns/1.0"><teiHeader/><text><body>'
       '<p><lb edRef="#T1"/>In principio</p></body></text></TEI>')
XSL_HEAD = ('<xsl:stylesheet version="1.0" xmlns:xsl="http://www.w3.org/1999/XSL/Transform" '
            'xmlns:exsl="http://exslt.org/common" extension-element-prefixes="exsl">')


@pytest.fixture
def fv(editor_module):
    import formatted_view
    return formatted_view


@pytest.fixture
def fake_powershell(monkeypatch, fv):
    """PowerShell « disponible » ; enregistre les appels au lieu de les exécuter."""
    calls = []

    def run(args, **kwargs):
        calls.append(args)
        Path(args[8]).write_text("<html>via PowerShell</html>", encoding="utf-8")   # fichier de sortie
        return subprocess.CompletedProcess(args, 0, "", "")

    monkeypatch.setattr(fv.shutil, "which", lambda name: "C:/Windows/powershell.exe")
    monkeypatch.setattr(fv.subprocess, "run", run)
    return calls


def _xsl(tmp_path, body, name="feuille.xsl"):
    path = tmp_path / name
    path.write_text(XSL_HEAD + body + "</xsl:stylesheet>", encoding="utf-8")
    return path


def test_builtin_stylesheet_still_transforms(fv):
    html, engine = fv.transform_with_xslt(TEI, ROOT / "rendering" / "tei-to-html.xsl", {"baseWitness": "T1"})
    assert "In principio" in html
    assert engine.startswith("lxml")


def test_broken_stylesheet_is_reported_without_powershell_fallback(tmp_path, fv, fake_powershell):
    xsl = _xsl(tmp_path, '<xsl:template match="/"><xsl:value-of select="///"/></xsl:template>')
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, xsl)
    message = str(info.value)
    assert "feuille.xsl" in message and "///" in message
    assert "PowerShell" not in message
    assert fake_powershell == []                     # aucun repli PowerShell


def test_runtime_error_of_stylesheet_is_reported(tmp_path, fv, fake_powershell):
    xsl = _xsl(tmp_path, '<xsl:template match="/"><xsl:message terminate="yes">arrêt voulu</xsl:message></xsl:template>')
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, xsl)
    assert "arrêt voulu" in str(info.value) or "feuille.xsl" in str(info.value)
    assert fake_powershell == []


def test_without_lxml_powershell_fallback_is_kept(tmp_path, fv, fake_powershell, monkeypatch):
    monkeypatch.setitem(sys.modules, "lxml", None)   # « import lxml » échoue
    html, engine = fv.transform_with_xslt(TEI, ROOT / "rendering" / "tei-to-html.xsl")
    assert html == "<html>via PowerShell</html>"
    assert engine == "PowerShell/.NET"
    assert len(fake_powershell) == 1


def test_without_lxml_nor_powershell_install_message(fv, monkeypatch):
    from app_context import tr

    monkeypatch.setitem(sys.modules, "lxml", None)
    monkeypatch.setattr(fv.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, ROOT / "rendering" / "tei-to-html.xsl")
    expected_prefix = tr("xslt.error.install", error="§").split("§")[0]
    assert str(info.value).startswith(expected_prefix)


def test_error_message_does_not_repeat_a_previous_error(tmp_path, fv):
    """Le journal d'erreurs global de lxml ne doit pas polluer le message suivant."""
    first = _xsl(tmp_path, '<xsl:template match="/"><xsl:value-of select="///"/></xsl:template>', "premiere.xsl")
    second = _xsl(tmp_path, '<xsl:template match="/"><p></xsl:template>', "seconde.xsl")   # XML mal formé
    with pytest.raises(RuntimeError):
        fv.transform_with_xslt(TEI, first)
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, second)
    message = str(info.value)
    assert "seconde.xsl" in message
    assert "premiere.xsl" not in message and "///" not in message


# --- Accès aux fichiers et au réseau pendant une transformation ---------------

def test_stylesheet_cannot_write_files(tmp_path, fv):
    target = tmp_path / "ecrit_par_la_feuille.txt"
    xsl = _xsl(tmp_path, f'<xsl:template match="/"><exsl:document href="{target.as_uri()}" '
                         'method="text">contenu</exsl:document><p/></xsl:template>')
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, xsl)
    assert not target.exists()
    assert "write" in str(info.value).lower()


def test_stylesheet_cannot_read_from_network(tmp_path, fv):
    xsl = _xsl(tmp_path, '<xsl:template match="/"><xsl:value-of '
                         'select="document(\'http://example.invalid/autorites.xml\')//p"/></xsl:template>')
    with pytest.raises(RuntimeError) as info:
        fv.transform_with_xslt(TEI, xsl)
    assert "example.invalid" in str(info.value)          # aucun accès réseau tenté


def test_stylesheet_can_still_read_local_files(tmp_path, fv):
    (tmp_path / "autorites.xml").write_text("<personnes><p>Abélard</p></personnes>", encoding="utf-8")
    xsl = _xsl(tmp_path, '<xsl:output method="text"/><xsl:template match="/">'
                         '<xsl:value-of select="document(\'autorites.xml\')//p"/></xsl:template>')
    html, _engine = fv.transform_with_xslt(TEI, xsl)
    assert html.strip() == "Abélard"
