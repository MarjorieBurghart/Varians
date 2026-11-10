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


def _history_entry(version):
    handoff = _read("DEVELOPER_HANDOFF.md")
    history = handoff[handoff.index("## Historique des versions"):]
    entry = history[history.index(f"VARIANS V{version}"):]
    return entry[:entry.index("\nVARIANS V", 1)]


def test_the_version_history_tells_what_the_current_version_brings():
    """0.9.4.3 : le projet sans témoin, en tête."""
    entry = _history_entry(CURRENT_VERSION)
    for words in ("sans témoin", "<listWit>", "<bibl>", "<sourceDesc>", "Paramètres du projet",
                  "texte seul", "commentaire", "curseur"):
        assert words in entry, words


def test_the_version_history_keeps_the_previous_versions():
    entry = _history_entry("0.9.4.2")
    for words in ("20 Mo", "Annuler", "démarrage", "Réouvrir un projet récent"):
        assert words in entry, words
    entry = _history_entry("0.9.4.1")
    for words in ("Ctrl+Espace", "didascalie", "XTDE0540", "Cache IIIF", "« Page n »", "lignes du pivot",
                  "Nouveau projet"):
        assert words in entry, words
    entry = _history_entry("0.9.4.0")
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
