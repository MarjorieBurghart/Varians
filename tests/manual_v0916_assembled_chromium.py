"""Essai dans Chromium : viewer web d'une édition assemblée (V0.9.1.6), avec
captures d'écran.

Lancer à la main (Playwright requis) : python tests/manual_v0916_assembled_chromium.py
CHROMIUM : chemin d'un Chromium déjà installé, si Playwright n'a pas le sien.
Les images IIIF ne sont pas chargées (réseau coupé) : les captures montrent
le texte, les panneaux, les bandeaux et les messages.

Trois jeux d'essai (tests/corpus_data.py) :
1. le projet exemple, RLS_185 synchronisé à part, T2 en lacune autour de lui,
   les témoins par pages X et Y ;
2. le jeu « corpus » (s02 au pivot B, s04 au pivot A, l'exemplum) ;
3. le projet exemple en un seul fichier.
"""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from playwright.sync_api import sync_playwright  # noqa: E402

from corpus_data import (add_text_pages, copy_example, insert_at, make_corpus, move_to_part,  # noqa: E402
                         split_alignments)
from pivot_lines import pivot_lb_pattern  # noqa: E402
from web_viewer.generator import generate  # noqa: E402


def example_with_text(root):
    project = copy_example(root)
    move_to_part(project)
    split_alignments(project.parent, "rls185", "T1", 116, 165, ("T2",))
    add_text_pages(project, y_locus=True)
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    lbs = [match.span() for match in pivot_lb_pattern("T1").finditer(text)]
    edition.write_text(insert_at(text, [(lbs[100][1], '<lacunaStart wit="#T2"/>'),
                                        (lbs[130][1], '<lacunaEnd wit="#T2"/>')]), encoding="utf-8")
    return project


class Session:
    def __init__(self, browser, project, shots, name):
        self.output, _missing, self.data = generate(project)
        self.page = browser.new_page(viewport={"width": 1500, "height": 950})
        self.errors = []
        self.page.on("pageerror", lambda error: self.errors.append(str(error)))
        self.page.route("http://**", lambda route: route.abort())
        self.page.route("https://**", lambda route: route.abort())
        self.page.goto(self.output.as_uri())
        self.shots, self.name, self.count = shots, name, 0

    def js(self, expression, arg=None):
        return self.page.evaluate(expression, arg)

    def select(self, key):
        assert self.js("k=>selectLine(k,true)", key) is True

    def arrow(self, wid, act):
        button = self.page.locator(f'[data-w="{wid}"] [data-act={act}]')
        if button.is_visible():
            button.click()
        else:                       # sans images, la colonne des témoins est masquée
            self.js("([id,a])=>action(id,a)", [wid, act])

    def shot(self, label):
        self.count += 1
        self.page.wait_for_timeout(700)          # défilement doux du texte
        path = self.shots / f"{self.name}-{self.count:02d}-{label}.png"
        self.page.screenshot(path=str(path))
        return path

    def card(self, wid):
        return self.page.locator(f'[data-w="{wid}"]').inner_text()

    def close(self):
        assert not self.errors, self.errors
        self.page.close()


def main():
    shots = Path(tempfile.mkdtemp(prefix="varians-v0916-"))
    with tempfile.TemporaryDirectory() as folder, sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=os.environ.get("CHROMIUM") or None,
                                    args=["--no-sandbox"])
        # 1. Projet exemple, RLS_185 à part.
        s = Session(browser, example_with_text(Path(folder) / "exemple"), shots, "exemple")
        catalog = s.data["i18n"]["catalogs"]["fr"]
        order = s.data["meta"]["line_order"]
        s.select(order[110])
        assert catalog["manuscript.lacuna"] in s.card("T2")
        s.shot("lacune-T2-edition")
        s.select(order[115])
        s.arrow("T1", "next")
        assert s.js("()=>[activeSeg,selectedKey]") == [1, order[116]]
        assert catalog["manuscript.text_absent"] in s.card("P")
        assert catalog["manuscript.lacuna"] not in s.card("T2")       # le texte à part repart sans lacune
        assert s.js("()=>[states.get('X').folioRef,states.get('Y').folioRef]") == ["X-p0001", "Y-p0002"]
        s.shot("texte-a-part-P-absent")
        s.arrow("X", "next")
        assert s.js("()=>states.get('X').folioRef") == "X-p0002"
        s.shot("X-mene-a-12v")
        s.arrow("P", "next")
        assert s.js("()=>activeSeg") == 0
        assert catalog["manuscript.lacuna"] in s.card("T2")           # la lacune reprend dans l'édition
        s.shot("P-mene-a-l-edition")
        s.close()
        # 2. Corpus « sermons ».
        s = Session(browser, make_corpus(Path(folder) / "corpus"), shots, "corpus")
        catalog = s.data["i18n"]["catalogs"]["fr"]
        order = s.data["meta"]["line_order"]
        first_b = next(key for key in order if key.startswith("~1~"))
        s.select(first_b)
        s.arrow("B", "next")
        assert s.js("()=>selectedKey") == order[order.index(first_b) + 1]
        assert catalog["manuscript.text_absent"] in s.card("A")
        s.shot("B-mene-s02")
        s.select(order[0])
        for _ in range(len(order) - 1):
            s.page.locator("#nextBase").click()
        assert s.js("()=>selectedKey") == order[-1]
        s.shot("en-tete-jusqu-a-la-fin")
        s.close()
        # 3. Projet exemple en un seul fichier.
        s = Session(browser, copy_example(Path(folder) / "simple"), shots, "simple")
        lines = s.js("()=>lineOrder")
        s.select(lines[30])
        start = s.js("()=>states.get('T2').center")
        s.arrow("T2", "next")
        assert s.js("()=>states.get('T2').center") == start + 1            # T2 a mené le texte
        s.shot("T2-mene-le-texte")
        s.arrow("T2", "home")
        s.shot("T2-retour")
        s.close()
        browser.close()
    print(f"Chromium : édition assemblée, textes à part, lacunes, flèches de tout panneau — OK ; captures : {shots}")


if __name__ == "__main__":
    main()
