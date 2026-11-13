# -*- coding: utf-8 -*-
"""Systèmes et versions de Python des tests de GitHub Actions (V0.9.4.6).

Les archives sont livrées pour Windows, macOS et Linux : la suite des tests
passe sur les trois, avec Python 3.12 (version de référence des archives)
et aussi 3.13. Sous macOS, le dossier temporaire est pris hors de
/var/folders, lien symbolique vers /private/var que Varians résout, comme le
nom court 8.3 sous Windows."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def test_the_tests_run_on_every_system_of_the_archives():
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in WORKFLOW


def test_the_tests_run_with_python_3_12_and_3_13():
    assert 'python: ["3.12"]' in WORKFLOW
    assert '- os: ubuntu-latest\n            python: "3.13"' in WORKFLOW


def test_the_temporary_folder_of_macos_is_not_a_symbolic_link():
    step = WORKFLOW[WORKFLOW.index("(macOS)"):]
    step = step[:step.index("\n\n")]
    assert "if: runner.os == 'macOS'" in step and 'TMPDIR=$RUNNER_TEMP' in step


def test_the_development_guide_names_the_tested_systems():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    part = guide[guide.index("## Tests automatiques sur GitHub"):]
    part = part[:part.index("\n## ")]
    for words in ("Ubuntu", "Windows", "macOS", "3.12", "3.13", "constraints.txt"):
        assert words in part, words


def test_a_blocked_test_cannot_hold_the_job_and_failures_are_named():
    """Un test bloqué ne retient pas le job jusqu'à la limite de GitHub
    (6 heures) : durée maximale du job ; au-delà de 10 minutes, pytest
    affiche la pile d'appels du test (faulthandler, sans dépendance de plus).
    Les tests en échec sont nommés en fin de passe (-rfE), et un à un sous
    macOS (-v)."""
    job = WORKFLOW[WORKFLOW.index("  tests:"):]
    assert "    timeout-minutes: 90\n" in job
    command = WORKFLOW[WORKFLOW.index("      - name: Tests\n"):]
    command = command[:command.index("\n\n") if "\n\n" in command else len(command)]
    for option in ("-rfE", "-o faulthandler_timeout=600", "runner.os == 'macOS' && '-v' || '-q'"):
        assert option in command, option
