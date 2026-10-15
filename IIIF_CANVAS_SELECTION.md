# Varians 0.8.5.4 — Pages éditoriales et associations IIIF ↔ ALTO/PAGE

## Problème corrigé

Un Manifest IIIF peut décrire plusieurs centaines de canvases alors que seuls
quelques feuillets sont utilisés. Les noms des fichiers ALTO/PAGE locaux ne
sont pas obligatoirement les noms des images du IIIF. La création automatique
d'une surface pour chaque canvas était donc excessive et la recherche automatique
à partir des noms ne pouvait pas résoudre toutes les associations.

## Interface

Paramètres du projet → Témoins → Modifier → Images IIIF :

1. Charger le manifest (ou utiliser son cache déjà présent dans le projet).
2. Choisir « Uniquement les images choisies pour l'édition ».
3. Cliquer sur « Choisir les images et associer les OCR… ».
4. Filtrer les canvases par label/URI, puis cocher les images à utiliser.
5. Varians propose d'emblée les fichiers ALTO/PAGE dont les noms d'image
   correspondent exactement à l'image IIIF (même base, extension ignorée).
   Les autres peuvent être associés manuellement dans la dernière colonne.
   Le bouton « Associer automatiquement (noms exacts) » complète les cases vides.
6. Valider, enregistrer les paramètres, ouvrir le gestionnaire IIIF.

Le bouton Aperçu ouvre une ressource IIIF dans le navigateur externe. Il ne
prétend pas fournir un aperçu hors ligne si l'image n'est pas encore en cache.
Une liaison manuelle concerne actuellement une seule page OCR par fichier ;
les XML multi-pages exigent une segmentation préalable par image.

Le mode « Toute la sélection » télécharge les canvases retenus ; « avec
ALTO/PAGE » restreint aux correspondances OCR (manuelles ou non ambiguës).
Il est possible de choisir une image sans OCR, notamment pour une page de garde.
La copie de travail et l'export web continuent de bénéficier de réglages
indépendants.

## Architecture et stockage

La politique `selectionMode="all"` reste la valeur implicite des anciens
projets et maintient leur comportement. Le nouveau mode explicite est stocké
comme suit dans `project.xml` :

```xml
<witness id="A" label="Assisi">
  <images type="iiif" manifest="https://example.org/manifest.json"
          selectionMode="selected" localCopy="true" downloadScope="ocr">
    <canvas ref="https://example.org/canvas/1r"/>
    <canvas ref="https://example.org/canvas/2v"/>
    <ocrLink file="alto/A/Assisi541-test-1r-PAGE.xml"
             canvas="https://example.org/canvas/1r"/>
  </images>
  <alto type="files">
    <file file="alto/A/Assisi541-test-1r-PAGE.xml"/>
  </alto>
</witness>
```

Les valeurs de `<canvas ref>` sont les URI `Canvas` lorsqu'elles existent.
Les identifiants internes numérotés `iiif-0001` constituent un repli lorsque
le manifeste ne fournit pas d'URI de canvas. Toute mise à jour modifiant les
URI nécessite une vérification explicite des associations.

Le dossier `iiif/<témoin>.manifest.json` conserve le **manifest complet**.
Aucun fichier IIIF distant n'est modifié. Le gestionnaire ne télécharge que
les canvases autorisés par l'intersection de la sélection et du périmètre OCR.
La liste des pages dessinées par Varians dans le cache de visualisation
n'inclut que les images sélectionnées, plus les pages OCR non associées
représentées sans image (conservation des données, jamais d'alignement forcé).

Les `tei:surface` nouvellement générées correspondent aux canvases retenus.
Leur xml:id `A-pNNNN` conserve l'index **original** du canvas dans le manifeste,
non son rang dans la sélection, pour stabiliser les références existantes.

En mode de sélection explicite, l'association du cache de synchronisation à
une page de géométrie ne peut plus reposer sur la position ordinale : une telle
association non démontrée serait dangereuse pour les `base_keys`.

### Sauvegarde et suppression contrôlée

Le TEI éditorial n'est jamais régénéré à partir du manifeste. Si l'ancien
projet contient déjà des centaines de `<surface>` créées par la version
précédente, elles restent intactes après la réduction de la sélection.
À l'enregistrement des paramètres, Varians peut proposer de supprimer les
surfaces **strictement identiques** à celles générées automatiquement par
Varians pour des canvases non sélectionnés, sans enrichissement ni référence
`#id` dans cette TEI. Les zones, annotations, liens et éléments personnalisés
sont toujours conservés. La réponse par défaut est « Non ». Sur confirmation,
une copie `edition.xml.pre-iiif-cleanup-<date>.bak` est produite avant la
modification textuelle ciblée. Les références provenant d'autres documents
externes ne sont pas inspectées ; la relecture humaine demeure indispensable.

### Tri naturel

`iiif_page_selection.natural_key()` classe les parties numériques des noms
comme entiers, afin d'obtenir 1r, 1v, 2r, 2v, 10r. L'import initial des
images et des fichiers ALTO/PAGE trie avant insertion ; un bouton permet
également le reclassement explicite d'une liste existante, en déplaçant les
objets Qt eux-mêmes avec leurs libellés, surface IDs et propriétés, sans
perdre les ajustements de l'utilisateur.

## Modules

- `iiif_page_selection.py` : clés stables des canvases, tri naturel,
  sélection du sous-ensemble et fusion explicite du contenu OCR.
- `project_dialogs.py` : dialogue `IIIFCanvasPicker`, contrôles des doublons,
  sélection persistante, tri naturel des listes.
- `project_management.py`, `project_config.py` : XML du projet, conversion
  des liens lorsque les fichiers OCR sont copiés dans le dossier projet.
- `iiif_local.py`, `iiif_download_manager.py` : plan de téléchargement réduit.
- `image_sources.py`, `alto_import.py` : fusion des pages OCR sans correspondance
  dangereuse par simple ordre.
- `tei_facsimile.py` : génération des seules surfaces retenues, détection
  très conservatrice des anciennes surfaces amovibles.
- `editeur_tei.py`, `web_viewer/generator.py` : choix de pages identique entre
  logiciel et export web, dialogue facultatif de nettoyage du TEI.
- `tests/test_v0853_iiif_editorial_selection.py` : tests de non-régression.

## Compatibilité et limites

- Les projets existants en `selectionMode="all"` sont inchangés.
- Les deux formats PAGE/ALTO continuent à être reconnus individuellement.
- Le manifeste entier reste en cache, mais seules les images retenues font
  partie du corpus éditorial lorsque la sélection est explicite.
- Aucun service IIIF distant n'a été contacté durant les tests automatisés :
  les téléchargements utilisent un double contrôlé (mock).
- Les interactions PySide6 doivent être testées sur le poste utilisateur.
- L'interface, ses nouvelles commandes et cette fonctionnalité sont
  documentées dans les sept langues livrées avec Varians.

## Mise à jour 0.8.5.4 : associations automatiques non ambiguës

`iiif_page_selection.propose_exact_ocr_links()` compare les noms des images
IIIF (`image` / `service` ou libellé du canvas) aux noms déclarés dans les
fichiers ALTO (`sourceImageInformation/fileName`) et PAGE (`Page/@imageFilename`),
ainsi qu'aux noms des fichiers XML. Seul le **nom de base exact** est accepté :
la casse et l'extension peuvent varier, mais les séparateurs et chiffres
ne sont jamais corrigés ou interprétés comme des indices de folio.

Les associations sûres sont proposées dès la première ouverture du sélecteur
pour les canvases qui ne faisaient pas déjà partie de la sélection enregistrée.
Le bouton d'association automatique permet d'appliquer une nouvelle passe aux
cases vides, y compris pour les sélections existantes, sans écraser les liens
que l'utilisateur a choisis manuellement. Une association délibérément laissée
vide dans une sélection déjà enregistrée reste vide lors de la réouverture.

Les conflits entre noms déclarés, les noms de canvas non uniques, plusieurs
OCR candidats au même canvas et les XML multi-pages sont exclus des suggestions.
Ces cas peuvent être résolus manuellement. Les liens confirmés sont enregistrés
normalement comme `ocrLink` dans `project.xml` ; aucune migration n'est requise.
Le traitement ne consulte pas le réseau et ne sélectionne aucune page par
simple position dans le manifeste.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.
