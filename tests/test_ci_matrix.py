# -*- coding: utf-8 -*-
"""Systèmes et versions de Python des tests de GitHub Actions (V0.9.4.6).

La suite des tests passe sous Ubuntu, Windows et macOS avec Python 3.12
(version de référence des archives), et sous Ubuntu avec Python 3.13. Un
test bloqué ne retient pas le job ; les tests en échec sont nommés.

macOS (V0.9.4.6) : titres des boîtes de message (mac_message_boxes),
Entrée dans la liste de Ctrl+E, et fin des transformations attendue sans
QProcess (transform_runner) ; la passe y est environ trois fois plus
longue, et le dossier temporaire est pris hors de /var/folders."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = (ROOT / ".github" / "workflows" / "tests.yml").read_text(encoding="utf-8")


def test_the_tests_run_on_ubuntu_windows_and_macos():
    assert "os: [ubuntu-latest, windows-latest, macos-latest]" in WORKFLOW


def test_macos_takes_its_temporary_folder_outside_var_folders():
    """/var/folders/… est un lien vers /private/var/…, que Varians résout :
    les comparaisons de chemins des tests seraient faussées."""
    step = WORKFLOW[WORKFLOW.index("      - name: Dossier temporaire sans lien symbolique (macOS)\n"):]
    step = step[:step.index("\n\n")]
    assert "if: runner.os == 'macOS'" in step and 'echo "TMPDIR=$RUNNER_TEMP" >> "$GITHUB_ENV"' in step


def test_the_tests_run_with_python_3_12_and_3_13():
    assert 'python: ["3.12"]' in WORKFLOW
    assert '- os: ubuntu-latest\n            python: "3.13"' in WORKFLOW


def test_a_blocked_test_cannot_hold_the_job_and_failures_are_named():
    """Un test bloqué ne retient pas le job jusqu'à la limite de GitHub
    (6 heures) : durée maximale du job ; au-delà de 10 minutes, pytest
    affiche la pile d'appels du test (faulthandler, sans dépendance de plus).
    Les tests en échec sont nommés en fin de passe (-rfE)."""
    job = WORKFLOW[WORKFLOW.index("  tests:"):]
    # macOS : une passe environ trois fois plus longue.
    assert "    timeout-minutes: ${{ matrix.os == 'macos-latest' && 90 || 45 }}\n" in job
    command = WORKFLOW[WORKFLOW.index("      - name: Tests\n"):]
    for option in ("python -m pytest -q", "-rfE", "-o faulthandler_timeout=600"):
        assert option in command, option


def test_the_development_guide_names_the_tested_systems():
    guide = (ROOT / "docs" / "DEVELOPPEMENT.md").read_text(encoding="utf-8")
    part = guide[guide.index("## Tests automatiques sur GitHub"):]
    part = part[:part.index("\n## ")]
    for words in ("Ubuntu", "Windows", "3.12", "3.13", "constraints.txt", "macOS", "TMPDIR"):
        assert words in part, words
    assert "n'y est pas encore" not in part
