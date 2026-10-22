# Synchronisation facultative — V0.7.6

La synchronisation entre témoins est une ressource indépendante et facultative.
Un témoin peut être créé et utilisé sans fichier de synchronisation, puis recevoir
ce fichier plus tard depuis **Fichier > Paramètres du projet… > Témoin > Modifier…**.

## Ajouter une synchronisation

Choisir un fichier JSON conforme au format `tei-manuscript-alignment`. Varians
propose de le **copier dans le projet** ; dans ce cas il devient :

```text
alignments/<sigle>.json
```

Décochez la copie pour conserver une référence vers un fichier externe.

## Remplacer une synchronisation

Sélectionner un autre JSON dans la fiche du témoin. Si le fichier est copié dans
le projet et qu'un ancien `alignments/<sigle>.json` existe, Varians en conserve
une sauvegarde `alignments/<sigle>.json.bak` avant remplacement.

## Retirer une synchronisation

Effacer le chemin du fichier de synchronisation dans la fiche du témoin. Le
`project.xml` n'écrit alors plus d'attribut `alignment`. Un ancien fichier resté
dans `alignments/` n'est pas supprimé automatiquement : cette prudence évite une
perte de données accidentelle.

## Indépendance des ressources

Ajouter, remplacer ou retirer la synchronisation ne modifie pas :

- la source d'images (`none`, images locales ou IIIF) ;
- les fichiers ALTO séparés ;
- l'édition TEI.

Au chargement, Varians lit d'abord le JSON de synchronisation lorsqu'il existe,
puis applique les ALTO séparés et enfin la politique d'images du témoin. Les
`base_keys` du JSON restent donc la couche de correspondance inter-témoins.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.


## V0.8.5.9 — Limites des colonnes

La lecture des `base_keys` et la correspondance des lignes n'ont pas changé.
Une ligne dont la liaison est valide peut avoir semblé afficher une page entière
si les indices voisins appartenaient à deux colonnes différentes : la correction
porte exclusivement sur le **contexte graphique utilisé pour recadrer** la page.


## V0.8.5.11 — Deux niveaux de synchronisation dans la même édition
Un témoin sans JSON n'est pas un témoin erroné. Tant qu'il n'a aucune correspondance de ligne utilisable, il est piloté par les `<pb/>` qui lui appartiennent (`@edRef` et `@facs`; `@n` exact unique en repli). Les témoins correctement synchronisés conservent leurs `base_keys`. Ce comportement doit coexister pour plusieurs témoins dans les mêmes documents source et web.


## V0.8.5.17 — Diagnostic / actualisation

Voir `WITNESS_DIAGNOSTICS.md`. Le module `witness_resource_refresh.py` centralise le rapport indépendant de Qt et la préparation transactionnelle des ressources. L’éditeur conserve sa TEI, sa pile d’annulation et ses panneaux ; il ne commet le rechargement qu’après validation. La synchronisation n’est jamais déduite des seules données ALTO/PAGE.

## V0.9.1.0 — Édition assemblée par XInclude

Pour une édition qui inclut ses parties (`xi:include`), les lignes du pivot
sont comptées dans l'ordre de l'édition assemblée, d'une partie à l'autre :
le n-ième `<lb edRef="#pivot"/>` du document assemblé correspond, comme dans
un fichier unique, à la n-ième ligne du JSON du pivot. Les JSON ne changent
pas (un par témoin pour toute l'édition) ; le pivot doit contenir les textes
dans l'ordre de l'édition. Le curseur d'une partie fait suivre les témoins,
et un clic dans le pivot affiche la partie qui contient la ligne. Voir
`docs/DECISIONS_ASSEMBLAGE.md`.

## V0.9.1.1 — Textes synchronisés à part

Dans un corpus dont les textes ne sont pas transmis par les mêmes témoins,
un texte de l'édition (une partie incluse par `xi:include`) peut avoir ses
propres alignements : un JSON par témoin, au format habituel, rangé dans
`alignments/<nom du fichier du texte>/` (`alignments/s02/B.json` pour
`xml/sermons/s02.xml`). Un texte qui a son dossier est synchronisé à part ;
les autres suivent la numérotation continue, et les JSON globaux ne
contiennent que leurs lignes. Le pivot d'un texte est celui du projet, sauf
`<parts><part name="s02" base="B"/></parts>` dans `project.xml`.

Quand un tel texte est affiché, les panneaux prennent ses JSON et son pivot
(lus à la première visite, puis gardés) ; un témoin sans JSON pour le texte
garde son panneau, avec un message. « Actualiser les synchronisations » et
« État des témoins » portent sur le texte affiché. Les lacunes, les témoins
synchronisés par pages dans un texte à part et le parcours d'un manuscrit
dans son propre ordre viennent en V0.9.1.3.
