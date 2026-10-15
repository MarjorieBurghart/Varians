# Varians V0.8.3 — Affichage et navigation de travail

## Témoins affichés

Le menu **Affichage > Choisir les témoins affichés…** présente les témoins du
projet. Les témoins disposant d'images peuvent être cochés ou décochés. Les
témoins sans image restent visibles dans la liste mais sont désactivés afin de
ne pas créer un panneau vide.

Le choix est une préférence locale d'interface : il est enregistré avec
`QSettings` sous une clé dérivée du chemin du `project.xml`. Il n'est jamais
écrit dans `project.xml`. Une liste vide est valide et masque entièrement la
colonne des images.

Lors de la première ouverture d'un projet, tous les témoins qui possèdent déjà
une image sont affichés. Une fois une préférence enregistrée, l'ajout ultérieur
d'un nouveau témoin ne le coche pas automatiquement.

## Hauteur des panneaux

La colonne des images est un `QSplitter` vertical. L'utilisateur peut donc
redimensionner librement chaque témoin. Les hauteurs sont mémorisées localement
par projet. Un double-clic sur l'en-tête d'un témoin maximise temporairement ce
panneau ; un second double-clic restaure la répartition précédente.

## Menu Affichage

Le menu contient :

- **Recharger les images** (`F5`) ;
- **Choisir les témoins affichés…** ;
- **Langue** en dernière position.

`Recharger les images` n'occupe plus la barre d'outils.

## Synchronisation des sélections XML ↔ XSLT/CSS

Une chaîne sélectionnée n'est plus retrouvée par une recherche globale du
premier texte identique. Varians identifie :

1. le paragraphe TEI `<p>` contenant la sélection ;
2. le rang de cette occurrence du texte sélectionné dans ce paragraphe ;
3. un offset relatif servant de repli.

Les marqueurs `tei-edit://p/N` déjà injectés dans l'aperçu permettent de
retrouver le même paragraphe dans le `QTextDocument`. Le même descripteur est
utilisé dans le sens XSLT/CSS → XML. Si une XSLT personnalisée réordonne ou
supprime profondément le texte, Varians conserve l'ancien mécanisme ligne/par
proximité comme repli.


## Recadrage aux limites de colonnes et de pages — V0.8.5.9

`display_window_indices()` (dans `image_sources.py`) détermine le petit contexte
visuel autour d'une ligne synchronisée. Historiquement, il retenait ±1 indice
de la liste des lignes OCR, sans contrôle de la position spatiale. Au passage
d'une colonne à l'autre, ce contexte pouvait juxtaposer le bas de la première
colonne et le haut de la seconde : `crop_for_items()` produisait alors un
rectangle proche de la page entière.

`_adjacent_line_continuity()` vérifie maintenant, entre deux items consécutifs :
(1) même page physique ; (2) absence de retour vertical important vers le haut ;
(3) absence de discontinuité horizontale manifeste. L'algorithme interrompt
l'extension du contexte au premier franchissement de limite. Si la géométrie
de lignes est indisponible, le voisinage *sur la même page* est conservé ; il
reste alors prudent de vérifier visuellement la zone OCR.

Le modèle des alignements, les `base_keys`, les indices de lignes, le curseur XML,
la navigation et le manifeste IIIF ne sont **pas modifiés**. Le recadrage et le
mode `Page` restent indépendants : `Page` ouvre toujours la ressource complète.

Tests : `tests/test_v0859_column_crop.py` (première ligne de colonne, dernière
ligne de colonne, fin de page, discontinuité horizontale, continuité ordinaire,
mode page, invariance des lignes et URL IIIF).


## Affichage des cadres — V0.8.5.10

- `image_sources.valid_matched_indices()` assainit les indices du JSON.
- `image_sources.matched_line_center()` choisit une ligne *effectivement appariée*
  (proche du centre précédent) ; l'ancien calcul `round((min+max)/2)` pouvait
  désigner une ligne sans `base_keys`, particulièrement entre deux colonnes.
- `visible_line_frame_indices()` inclut toutes les lignes appariées présentes
  dans le recadrage et la ligne naviguée courante. La première est tracée en
  orange, la seconde en bleu lorsqu'elle n'est pas synchronisée.
- Le bouton `Cadres` est indépendant pour chaque panneau, avec un état coché
  visuellement marqué et une infobulle traduite. Sans géométrie exploitable,
  aucun cadre fictif en `(0, 0)` n'est dessiné ; un message explique l'absence.
- Les polygones PAGE continuent d'être dessinés par `QGraphicsPolygonItem`,
  transformés selon la zone recadrée et la taille de l'image. Sinon rectangle
  `QGraphicsRectItem`. Le web viewer actuel marque par rectangles (fonction
  `stageMarkup`), point à distinguer de la vue intégrée.
- Aucun changement des JSON, de `base_keys`, des `<pb/>`, `<lb/>`, surfaces,
  des téléchargements IIIF ou du système de recadrage V0.8.5.9.

Tests : `tests/test_v08510_frame_visibility.py` + suite historique.


## V0.8.5.11 — Mélange des modes dans une édition
Chaque témoin exploite sa propre ressource de navigation : JSON/base_keys pour les lignes, `pb/@edRef/@facs` pour les pages (repli `@n` exact, unique). L'absence de JSON pour un troisième témoin n'empêche plus ce témoin de suivre les changements de folio de la transcription lorsque le pivot est en mode ligne. Le web applique aussi les `pb` antérieurs à la ligne affichée. Voir `MIXED_NAVIGATION.md`.


## V0.8.5.12 — Colonne d'images défilable, quatre témoins ou plus

Le panneau central droit est maintenant une `QScrollArea` (`witness_scroll`,
ancien alias `manuscript_scroll`), contenant le même `QSplitter` vertical
(`witness_splitter`) et tous ses `ManuscriptPanel`. La `QScrollArea` a un
ascenseur vertical automatique et un défilement horizontal désactivé.

`witness_layout.minimum_witness_stack_height()` impose une hauteur minimale
de **290 px par témoin visible + 7 px par poignée**, sans dépendre de la
hauteur de la fenêtre. Au-delà de la hauteur disponible, la colonne défile :
il ne faut plus compresser le dernier panneau en quelques pixels.

`_update_witness_scroll_extent()` est appelé lorsque la sélection des
panneaux change et lors d'une maximisation/restauration. Une maximisation
réduit l'étendue minimale à un seul panneau ; le retour rétablit l'étendue de
l'ensemble. Les dimensions de l'utilisateur restent mémorisées par témoin,
`witnessHeights`; la visibilité par `visibleWitnesses`, comme avant.

La partie « image » conserve ses propres contrôles de zoom et ses scènes
`QGraphicsView` : le défilement ici concerne la colonne de **panneaux**,
non le déplacement à l'intérieur du zoom d'une image. Des tests sans Qt
vérifient le calcul de hauteur, la prise en compte des témoins cachés et de
la maximisation. Le rendu réel sous PySide6 doit être vérifié.

## V0.8.5.15 — Cadres et image IIIF réduite ; diagnostic des JSON secondaires

Une image IIIF peut être représentée par une ressource de dimensions inférieures
à celles du Canvas (ex. aperçu 490 px pour un Canvas de 3924 px). Avant 0.8.5.15,
le mode page utilisait les dimensions de ce bitmap comme coordonnées physiques
pour dessiner les contours ALTO/PAGE calculés dans les dimensions du Canvas.
Les contours pouvaient alors étendre les bornes de la scène et rendre le zoom
« 100 % » anormalement petit. `image_scene_reference_crop` dans
`image_sources.py` restitue le repère d'origine à `ManuscriptPanel._redraw_scene` ;
les coordonnées source et les fichiers sont conservés. Pour les demandes IIIF
sans crop, l'URL de service Image API pleine résolution est prioritaire,
avec le champ `image` du manifest en repli.

Un JSON configuré sans `base_keys` demeure volontairement en mode page. Une
alerte localisée dans `ManuscriptPanel.sync_issue` l'explique ; une autre alerte
signale des liens ne correspondant à aucune clé du pivot. Les cadres ALTO
sont indépendants de ce diagnostic. Sans le fichier de synchronisation L.json
réel, on ne doit pas affirmer que ses liens sont présents ou corrects.


## Ordre des panneaux de témoins — V0.8.5.16

La boîte **Affichage > Choisir les témoins affichés…** comporte désormais deux
dimensions indépendantes : la case à cocher (visibilité) et la position de la
ligne (ordre vertical). Sélectionner un témoin puis utiliser **Monter** /
**Descendre**. Les témoins non cochés restent dans la liste et dans l'ordre,
pour une éventuelle réactivation. Les témoins sans image ne peuvent pas être
activés ; ils restent néanmoins présents dans l'ordre enregistré.

L'ordre d'affichage est enregistré sous `projectView/<sha1>/witnessOrder`,
dans `QSettings`, à côté de `visibleWitnesses` et `witnessHeights`. Le hash
dépend du chemin absolu du `project.xml`, comme pour les autres préférences.
La première ouverture respecte l'ordre des témoins du projet ; un témoin
ajouté ensuite est placé en fin de liste. Les identifiants supprimés sont
ignorés, les doublons éliminés et une préférence locale corrompue n'empêche
pas le démarrage. Les réglages `project.xml` et JSON restent intacts.

La méthode `_apply_witness_panel_order()` déplace les `ManuscriptPanel`
existants avec `QSplitter.insertWidget()` au lieu de les reconstruire : la
page courante, le zoom, les cadres et les signaux de synchronisation restent
liés à l'identifiant du témoin. La répartition des hauteurs est indexée par
identifiant de témoin, jamais par son ancien index de splitter. Lors du
déplacement, `_reordering_witness_panels` suspend l'enregistrement transitoire
des hauteurs ; la restauration est appliquée après modification. La
maximisation temporaire continue de fonctionner selon l'ordre actuel.

Ce réglage est **strictement local à l'éditeur** : il ne change pas le manuscrit
pivot et ne définit pas l'ordre des témoins du viewer web exporté.

Tests : `tests/test_v08516_witness_order.py`.


## V0.8.5.17 — Diagnostic / actualisation

Voir `WITNESS_DIAGNOSTICS.md`. Le module `witness_resource_refresh.py` centralise le rapport indépendant de Qt et la préparation transactionnelle des ressources. L’éditeur conserve sa TEI, sa pile d’annulation et ses panneaux ; il ne commet le rechargement qu’après validation. La synchronisation n’est jamais déduite des seules données ALTO/PAGE.


Varians V0.8.5.18 — Navigation par folios et images doubles
Voir FOLIO_NAVIGATION.md. Une surface peut contenir deux zones de folio ; aucun changement des JSON/ALTO ou des images source.


## Varians V0.8.5.19 — Correction du dialogue « Double page… »

Le bouton « Double page… » est utilisable pour les témoins en mode page ET en mode lignes ; seul le sélecteur de folios reste limité au mode page. En synchronisation par lignes, créer deux zones n’altère pas le cadrage courant. Les erreurs d’association de `tei_surface_id` sont affichées.


## Extension 0.8.5.21 : dispositions de travail

Voir [`WORKSPACE_LAYOUT.md`](WORKSPACE_LAYOUT.md). Les vues verticale, horizontale, grille, les fenêtres individuelles et le mode « Toujours au premier plan » ne changent que les préférences d’affichage `QSettings`. Le même `ManuscriptPanel` est transféré entre parents Qt ; `workspace_layout.py` ne contient pas de logique de synchronisation. Le ratio XML/manuscrits est librement redimensionnable, y compris vers 20 % XML.
