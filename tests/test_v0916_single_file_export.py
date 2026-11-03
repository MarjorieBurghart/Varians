# -*- coding: utf-8 -*-
"""Export web d'une édition en un seul fichier (V0.9.1.6) : les données
exportées ne changent pas.

La V0.9.1.6 apprend à l'export les éditions en parties (XInclude), les textes
synchronisés à part, les lacunes et l'ordre propre des manuscrits. Pour une
édition en un seul fichier, sans lacunes, rien ne doit changer : l'empreinte
des données du projet exemple a été relevée avant ces changements. Elle ne
change que par une décision explicite.

V0.9.3.0 : les blocs « sermon » deviennent des blocs « div » (identifiant,
niveau, titre tiré du premier <head>, sinon de @n) ; la division englobante
<div n="pr"> en a un. Le texte et les positions ne changent pas. Puis,
comme « Édition critique », le <ref> d'une <cit> sans @type « bible » est
un repère de note (les 34 citations du projet exemple). Puis le document
compte les passages où le témoin choisi n'a pas de leçon
(``missing_readings`` : 0 ici, le texte ne change pas). Puis, par décision
explicite, le texte exporté par défaut est le texte établi, comme
« Édition critique » : le <lem>, à défaut la leçon du pivot (et non plus
la leçon du pivot d'abord) ; ``meta.text`` dit ce choix.

V0.9.3.1 : dans le texte établi, les segments d'une leçon qui ne vient pas
d'un <lem> portent ``nonlem`` (surlignage au choix du lecteur) ; le document
les compte (``nonlem_readings``), ``meta.text`` aussi, avec l'état de départ
du surlignage (``highlight``). Ces marques retirées, l'empreinte est celle
d'avant : le texte ne change pas. Les blancs au bord d'une telle leçon sont
détachés dans leur propre segment, non marqué : le texte affiché et les mots
marqués restent les mêmes.

V0.9.3.4 (red team 2, décision explicite) : un <lb/> d'un autre témoin que
le pivot suit la règle TEI, comme dans « Édition critique » et l'aperçu :
sans break="no", une fin de mot. Les 30 « XX<lb edRef="#T2"/>II » du projet
exemple (sans doute des break="no" oubliés) deviennent « XX II », comme
ailleurs. L'en-tête compte les variantes et les notes de l'apparat du texte
de lecture (366 notes au lieu des 333 rattachées aux lignes du pivot).
Puis la fenêtre d'une variante dit les leçons comme l'apparat de « Édition
critique » : chaque leçon porte ses parties (``parts`` : om., [lacune],
notes entre parenthèses…) et le @wit de son <rdgGrp> ; le document porte
les sigles de <listWit> (``sigla``). Dans le projet exemple, 50 leçons
non affichées perdent une espace parasite (un <lb break="no"/> ou un <pb/>
dans un mot : « Magna tes » devient « Magnates ») et 64 omissions sont
dites « om. » ; le texte de lecture ne change pas (seul le ``tooltip``
des repères de variante, que le viewer n'affiche pas, suit ces leçons).
Une note suit les mêmes règles (``parts``) : l'apparat de la note
« stellarum ????nalia… » donne sa leçon, puis son entrée entre crochets,
au lieu de toutes ses leçons collées (« ????naliamagnalia »).

V0.9.4.0 (décision explicite) : ``meta.unmatched_tei_pages``, toujours
vide depuis le contrat des <lb> du pivot (V0.8.5.25.3), est remplacé par
le nombre de lignes du pivot sans ligne dans son alignement
(``unaligned_pivot_lines`` : 0 ici) et ses totaux
(``unaligned_pivot_line_totals`` : 3790 lignes dans le texte comme dans
l'alignement). Ces clés remises comme avant, l'empreinte est celle d'avant :
le texte ne change pas."""
from __future__ import annotations

import hashlib
import json

from corpus_data import copy_example
from project_config import load_project
from web_viewer.generator import build_dataset

DIGEST = "b4260c9a2f866a9403bf71008dbf95ebb4ba00622349df463bb45df3fe385ff0"


def _digest(data):
    data = dict(data)
    data.pop("i18n", None)          # catalogues de l'interface, hors du sujet
    text = json.dumps(data, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_a_single_file_edition_is_exported_as_before(tmp_path):
    project = copy_example(tmp_path / "exemple")
    data, _unaligned = build_dataset(load_project(project))
    assert str(project.parent) not in json.dumps(data, ensure_ascii=False)
    assert _digest(data) == DIGEST


def test_the_digest_sees_a_change_of_the_edition(tmp_path):
    project = copy_example(tmp_path / "exemple")
    edition = project.parent / "xml" / "edition.xml"
    text = edition.read_text(encoding="utf-8")
    edition.write_text(text.replace("Uos estis", "Vos estis", 1), encoding="utf-8")
    data, _unaligned = build_dataset(load_project(project))
    assert _digest(data) != DIGEST
