# -*- coding: utf-8 -*-
"""Documentation à jour de la version courante : en-têtes de
DEVELOPER_HANDOFF.md et CODE_MAP.md, entrée de l'historique des versions,
guide de développement (construction de la version prête à l'emploi,
procédure d'une nouvelle version), README (signaler un problème)."""
from __future__ import annotations

from pathlib import Path

from varians_source import CURRENT_VERSION

ROOT = Path(__file__).resolve().parents[1]


def _read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_the_developer_documents_name_the_current_version():
    handoff = _read("DEVELOPER_HANDOFF.md")
    assert handoff.startswith("# Varians — dossier de transmission développeur\n")
    assert f"**Version de référence : {CURRENT_VERSION}**" in handoff[:1000]
    assert _read("CODE_MAP.md").splitlines()[0] == f"# Varians — carte rapide du code (V{CURRENT_VERSION})"


def test_the_version_history_tells_what_the_current_version_brings():
    handoff = _read("DEVELOPER_HANDOFF.md")
    history = handoff[handoff.index("## Historique des versions"):]
    entry = history[history.index(f"VARIANS V{CURRENT_VERSION}"):]
    entry = entry[:entry.index("\nVARIANS V", 1)]
    for words in ("Changer le sigle", "prête à l'emploi", "--self-test", "icône", "Signaler un problème"):
        assert words in entry, words


def test_the_development_guide_covers_the_ready_to_use_version_and_new_versions():
    guide = _read("docs/DEVELOPPEMENT.md")
    for words in ("packaging/build.py", ".github/workflows/binaries.yml", "--self-test", "packaging/LISEZMOI.md"):
        assert words in guide, words
    procedure = guide[guide.index("## Historique et versions"):]
    procedure = procedure[:procedure.index("\n## ", 1)]
    for words in ("APP_VERSION", "CURRENT_VERSION", "Historique des versions", "CODE_MAP.md", "DEVELOPER_HANDOFF.md"):
        assert words in procedure, words


def test_the_readme_says_how_to_report_a_problem():
    readme = _read("README.txt")
    assert "SIGNALER UN PROBLÈME" in readme
    assert "https://github.com/MarjorieBurghart/Varians/issues" in readme and "--self-test" in readme
