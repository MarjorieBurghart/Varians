# -*- coding: utf-8 -*-
"""Viewer web : les lignes du témoin pivot (``<lb/>``) qui n'ont pas de ligne
dans son alignement (JSON) sont comptées et signalées (compte rendu de
« Générer le viewer web », ligne de commande, ``meta``). Le n-ième ``<lb/>``
du pivot suit la n-ième ligne de son JSON (contrat V0.8.5.25.3) : un JSON
plus court que le texte (alignement en cours, page manquante) laisse les
dernières lignes du texte sans image. L'ancien avertissement « pages absentes
du cache » ne pouvait plus rien signaler sous ce contrat : il est remplacé."""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tests"))

from corpus_data import copy_example  # noqa: E402
from i18n import I18nManager  # noqa: E402
from project_config import load_project  # noqa: E402
from web_viewer import generator  # noqa: E402

REMOVED = "f272-f-267v-268"


def _project(tmp_path, remove=None):
    project_path = copy_example(tmp_path / "exemple")
    if remove:
        alignment = Path(load_project(project_path).base.alignment)
        data = json.loads(alignment.read_text(encoding="utf-8"))
        data["pages"] = [page for page in data["pages"] if page["id"] != remove]
        alignment.write_text(json.dumps(data), encoding="utf-8")
    return project_path


def test_pivot_lines_beyond_the_alignment_are_counted(tmp_path):
    data, unaligned = generator.build_dataset(load_project(_project(tmp_path, remove=REMOVED)))
    index = data["meta"]["pivot_lb_index"]
    assert unaligned == index["unmapped_lb_count"] == index["tei_lb_count"] - index["physical_line_count"] > 0
    assert data["meta"]["unaligned_pivot_lines"] == unaligned
    assert "unmatched_tei_pages" not in data["meta"]


def test_nothing_is_reported_when_the_alignment_covers_the_text(tmp_path):
    data, unaligned = generator.build_dataset(load_project(_project(tmp_path)))
    assert unaligned == 0 and data["meta"]["unaligned_pivot_lines"] == 0


def test_the_command_line_says_it(tmp_path, capsys):
    project_path = _project(tmp_path, remove=REMOVED)
    assert generator.main([str(project_path)]) in (0, None)
    data, unaligned = generator.build_dataset(load_project(project_path))
    index = data["meta"]["pivot_lb_index"]
    manager = I18nManager(ROOT / "i18n", load_project(project_path).language, "en")
    expected = manager.tr("console.unaligned_lines", count=unaligned, text=index["tei_lb_count"],
                          alignment=index["physical_line_count"])
    assert expected in capsys.readouterr().out


def test_the_message_reads_well_in_french():
    manager = I18nManager(ROOT / "i18n", "fr", "en")
    text = manager.tr("webgen.unaligned_lines", count=174, text=3790, alignment=3616)
    assert "174 lignes du témoin pivot ne sont pas synchronisées avec les images" in text
    assert "(texte : 3790, alignement : 3616)" in text
    assert "1 ligne du témoin pivot n'est pas synchronisée" in manager.tr(
        "webgen.unaligned_lines", count=1, text=10, alignment=9)
    for language in ("fr", "en", "de", "ja", "cs", "it", "ru"):
        catalog = (ROOT / "i18n" / f"{language}.xml").read_text(encoding="utf-8")
        assert 'key="webgen.missing"' not in catalog and 'key="console.missing_pages"' not in catalog
