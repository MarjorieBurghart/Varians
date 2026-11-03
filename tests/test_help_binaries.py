# -*- coding: utf-8 -*-
"""Aide × 7 (V0.9.4.0) : la version prête à l'emploi (sans Python) dans le
démarrage rapide, avant l'installation avec Python, avec la page des
versions et le LISEZMOI de l'archive, dans la langue de l'aide."""
from __future__ import annotations

from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = {"fr": "LISEZMOI.txt", "en": "README.txt", "de": "LIESMICH.txt", "ja": "README-ja.txt",
          "cs": "README-cs.txt", "it": "LEGGIMI.txt", "ru": "README-ru.txt"}


def _install_step(language):
    page = (ROOT / "help" / f"{language}.html").read_text(encoding="utf-8")
    start = page.index('<h2 id="quickstart">')
    first = page.index("<li>", start)
    return page[first:page.index("</li>", first)]


@pytest.mark.parametrize("language", sorted(README))
def test_the_quickstart_offers_the_ready_to_use_version_first(language):
    step = _install_step(language)
    releases = step.find("https://github.com/MarjorieBurghart/Varians/releases")
    assert releases != -1, language
    assert f"<code>{README[language]}</code>" in step, language
    assert (ROOT / "packaging" / "readme" / README[language]).is_file()
    # Puis, comme avant, avec Python.
    assert releases < step.index("installer_dependances.bat") < step.index("python editeur_tei.py"), language
