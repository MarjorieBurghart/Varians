"""Essai dans Chromium : masquer les marqueurs de variantes et de notes du viewer.

Lancer à la main (Playwright requis) : python tests/manual_viewer_marker_toggles_chromium.py
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from test_viewer_marker_toggles import marker_data  # noqa: E402
from web_viewer.generator import make_html  # noqa: E402


def main():
    with tempfile.TemporaryDirectory() as folder:
        page_path = Path(folder) / "viewer.html"
        page_path.write_text(make_html(marker_data()), encoding="utf-8")
        with sync_playwright() as p:
            # CHROMIUM : chemin d'un Chromium déjà installé, si Playwright n'a pas le sien.
            executable = os.environ.get("CHROMIUM") or None
            browser = p.chromium.launch(headless=True, executable_path=executable, args=["--no-sandbox"])
            page = browser.new_page()
            errors = []
            page.on("pageerror", lambda err: errors.append(str(err)))
            page.goto(page_path.as_uri())
            variant, note = page.locator(".ann-marker.v"), page.locator(".ann-marker.n")
            assert variant.is_visible() and note.is_visible()
            assert page.locator("#showVariantsLabel").inner_text() == "Variantes"

            page.locator("#showVariants").uncheck()
            assert not variant.is_visible() and note.is_visible()
            page.locator("#showNotes").uncheck()
            assert not note.is_visible()
            assert "In principio" in page.locator("#document").inner_text()

            page.reload()                                   # préférence mémorisée
            assert not page.locator("#showVariants").is_checked()
            assert not page.locator(".ann-marker.v").is_visible()
            page.locator("#showVariants").check()
            page.locator("#showNotes").check()
            assert page.locator(".ann-marker.v").is_visible() and page.locator(".ann-marker.n").is_visible()
            assert not errors, errors
            browser.close()
    print("Chromium : variantes et notes masquables séparément, choix conservé au rechargement")


if __name__ == "__main__":
    main()
