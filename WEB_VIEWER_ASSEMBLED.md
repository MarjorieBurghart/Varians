# Viewer web d'une édition assemblée (V0.9.1.6)

L'export web lit l'édition assemblée par XInclude et offre dans le viewer les
continuités de la fenêtre : texte des parties, numérotation continue des
lignes, textes synchronisés à part, lacunes, parcours de chaque manuscrit
dans son propre ordre. Les règles sont celles du bureau, sans copie :
`segment_model.py`, `witness_route.py`, `pivot_lines.py`, `lacunae.py`.

## Ce qui ne change pas

- Une édition **en un seul fichier** est exportée avec exactement les mêmes
  données qu'avant : `tests/test_v0916_single_file_export.py` en fige
  l'empreinte.
- Une édition **en parties sans texte synchronisé à part** donne les mêmes
  données que si tout était dans un seul fichier, plus `meta.assembled` et
  `meta.assembly_problems` (`tests/test_v0916_export_parts.py`).

## Lecture de l'édition (`web_viewer/assembled_document.py`)

`load_assembled(project)` renvoie None pour une édition sans `xi:include`.
Sinon il assemble l'édition (`xml_assembly.assemble`), lit les textes à part
(`text_alignments.text_syncs`) et la numérotation du bureau
(`pivot_lines.pivot_lines`), marque chaque copie de partie de son texte par
un attribut technique (hors TEI, retiré ensuite), sérialise l'arbre et le
relit avec `xml.etree`. `AssembledDocument.segment(node)` et
`target(node)` donnent le texte et le pivot de chaque élément.

`tei_line_anchors.build_segment_lb_index` compte, dans chaque texte, les
`<lb edRef="#pivot"/>` de **son** pivot et les relie à **ses** JSON : la
n-ième ligne du texte est la n-ième ligne du JSON de son pivot. L'ordre des
`<lb>` du document donne l'ordre de lecture de toutes les lignes.

Les extracteurs (`legacy_v11_core.extract_reading_document`,
`extract_corrected_pages`) reçoivent l'arbre, la ligne de chaque `<lb>` et
le texte et le pivot de chaque nœud : dans un texte au pivot B, les leçons
de B sont choisies, les `<lb>` de B font les lignes, les `<pb>` de B sont
visibles. Les segments d'un texte à part portent `"seg": k`.

## Données exportées

### Texte de lecture (`document.blocks[].segments[]`)

- **Repère de lacune** (tout export qui a des lacunes) :
  `{"kind": "lacuna", "start": true|false, "wit": ["T2"], "line_key": …}`.
  Le témoin vient de `@wit`, sinon de la leçon (`<rdg>`, `<lem>`) qui
  contient la balise, comme sur le bureau ; les repères d'une leçon non
  retenue, d'une note ou d'une référence sont gardés. `line_key` : la ligne
  du pivot ouverte à cet endroit. Un repère hors d'un bloc `p` passe au
  début du bloc `p` suivant. Un paragraphe qui ne contient que des repères
  n'est pas montré (`.tei-p:empty`).
- **Saut de page** : dans une édition à textes à part, chaque `pb` porte
  aussi `line_key`, la ligne du pivot ouverte à sa place (un `<pb>` placé
  juste après un `<lb/>` précède le texte de cette ligne).

Positions (`docPos`) : chaque segment d'un bloc `p`, dans l'ordre ; ce sont
celles du rendu (`renderDocument`), de la recherche
(`VariansFullText.makeIndex`) et de Python (`segment_views.doc_positions`).

### `meta` (édition à textes à part)

- `assembled`, `assembly_problems` : `[{file, line, code, detail}]`, chemins
  relatifs au projet (aucun chemin absolu dans le viewer).
- `segments` : l'édition (`index` 0), puis chaque texte à part :
  `{index, name, file, pivot, prefix, anchor, line_sync, lines,
  pivot_lb_index}`. `prefix` (`~1~`, `~2~`…) préfixe les identifiants de
  page et les `base_keys` du texte, car son JSON peut reprendre les pages
  et les numéros du JSON global ; `anchor` est le nombre de lignes de
  l'édition avant le texte.
- `line_order` : toutes les lignes, dans l'ordre de lecture.
- `lines`, `line_sync` : sommés ou cumulés sur les textes.
- `text_sync_problems` : ceux de `text_syncs`.

### Témoins

Les champs du témoin restent sa vue dans l'édition. S'y ajoutent :

- `views["k"]` : sa vue dans le texte k :
  `{mode: "line"|"page", role, line_sync, sync_diagnostic, pages, folios,
  start?, lead?}`, ou `{mode: "page", same_pages: true, start, lead?}` pour
  un témoin par pages sans JSON pour ce texte (ses pages de l'édition, ses
  `<pb>` de ce texte). Sans vue : le témoin n'a pas ce texte (« Pas
  d'alignement de ce témoin pour ce texte. »).
- `route` (témoins affichés) : son parcours dans l'ordre du manuscrit,
  calculé par `witness_route` sur les JSON après les règles d'ALTO,
  d'images et d'IIIF, sans préfixe (l'identité des pages est celle du
  bureau). Chaque arrêt : `{s, k, t, u?, p?}` : `s` le texte, `k` la clé de
  l'élément du panneau dans la vue de ce texte (préfixée) ou le folio d'un
  `<pb>`, `t` la ligne du pivot du texte que désigne l'arrêt, `u: 1` pour
  une ligne non reliée (elle mène à la ligne reliée qui la précède), `p` la
  position du `<pb>` dans le texte de lecture.
- `route_uncertain` : les textes placés par l'ordre de l'édition, faute de
  page commune, de `<locus from>` ou de foliotation.
- `lead` (vue par pages, dans le témoin pour l'édition et dans `views["k"]`
  pour un texte) : `{folio: rang de l'arrêt}`, la page qui mène le texte
  (`segment_model.page_stop`).
- `lead_locus` : `{folio: texte}`, la page qui est le `<locus from>` du
  témoin pour un texte (`segment_model.locus_segment`).

Le pivot d'un texte à part qui n'est pas affiché est exporté, sans images,
comme témoin technique, comme le pivot du projet. Une image n'est copiée
qu'une fois, même si plusieurs vues l'utilisent.

## Le viewer

`web_viewer/sync_model.js` (`VariansSync`, sans DOM, testé avec node) prend
les décisions : index du texte de lecture (`docIndex` : texte et ligne
ouverte à chaque position, repères de lacune), texte d'une clé
(`segOfKey`), lacunes en cours (`lacunaStarts`, `lacunaeAt`), parcours
d'un panneau d'un seul texte (`lineStops`, `pageStops` : ceux de
`witness_route`), pas d'un parcours (`routeIndex`, `step`, `panelStop`),
texte suivant ou précédent qui a un témoin (`presentStop` : celui de
`segment_model.present_stop` ; le viewer le calcule, car il dépend de la
ligne affichée).

Dans le gabarit (`generator.HTML_TEMPLATE`) :

- **Textes** : chaque témoin a un état par texte (`buildState`) ; le texte
  de la ligne ou de la position choisie devient actif (`activateSegment`) :
  les panneaux prennent la vue de leur témoin dans ce texte, gardent leur
  zoom et leurs cadres, et un témoin absent le dit. Les témoins par pages
  d'un texte à part ne suivent que les `<pb>` de ce texte, depuis leur page
  de départ. Les boutons de l'en-tête parcourent `line_order`.
- **Lacunes** (`updateLacunae`) : règles du bureau ; la lacune continue
  d'une partie à l'autre, un texte à part repart sans lacune. La position
  retenue est celle du fragment cliqué.
- **Flèches de tout panneau** (`leadFrom`, `goToStop`, `leadToPage`) : le
  témoin suit son parcours (exporté, ou calculé pour un seul texte) ; un
  témoin par pages mène par ses `<pb>`, sa liste de folios aussi, ou par
  `lead_locus` ; un panneau absent va au texte suivant ou précédent qui a le
  témoin. Messages du bureau (`status.*`), sous le titre.

## Depuis Varians

`project_actions.generate_web_viewer` enregistre l'édition, ses parties
modifiées et le fragment non appliqué d'une partie avant l'export ; un
échec l'annule. Le compte rendu liste les problèmes d'assemblage
(`webgen.assembly_problems`).

## Limites

- Précision des positions : celle des fragments de texte affichés, et non
  du caractère.
- Un `<pb>` ou un `<lb>` placé dans une leçon non retenue ou dans une note
  n'est pas vu par le viewer (comme avant).
- « État des témoins… », « Actualiser les synchronisations… », « Marquer la
  page » et « Double page… » restent propres au bureau.
- `parse="text"` et `xi:fallback` ne sont pas pris en charge : ils sont
  signalés, et le texte concerné manque.
- Taille : le parcours de chaque témoin affiché ajoute environ 60 octets par
  ligne (jeu d'essai « corpus » de 3785 lignes et 4 témoins par lignes :
  environ 1,1 Mo sur 7,2 Mo).

## Tests

`tests/test_v0916_*.py` : empreinte de l'export en un seul fichier, règles
communes (`test_segment_model.py`), lecture de l'édition assemblée,
extracteurs, repères de lacune, parties, textes à part, parcours ;
`test_v0916_sync_model.py` (node) ; `test_v0916_viewer_texts.py`,
`test_v0916_viewer_lacunae.py`, `test_v0916_viewer_arrows.py` (Chromium par
Playwright, ignorés sans lui) ; `tests/manual_v0916_assembled_chromium.py`
(captures d'écran).
