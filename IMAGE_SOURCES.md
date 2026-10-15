# Sources d’images flexibles — V0.7.0

## Principe

Varians sépare désormais trois ressources qui étaient historiquement très liées :

1. la **source d’image** d’un témoin ;
2. ses données **ALTO / linéation** ;
3. sa **synchronisation** avec le témoin de base (`base_keys`).

Ces ressources sont indépendantes et facultatives. Un témoin peut donc exister
sans image, sans ALTO et sans fichier de synchronisation. C’est notamment le cas
d’une transcription réalisée directement devant un manuscrit en bibliothèque.

La V0.7.0 a introduit le modèle de données et la compatibilité nécessaires. La
création d’une transcription *from scratch* est disponible depuis la V0.7.1 et
l’import graphique d’images locales depuis la V0.7.3 et l’import de Manifest
IIIF Presentation 2/3 depuis la V0.7.4.

## Nouveau bloc `image`

Une page peut déclarer explicitement sa source.

### IIIF

```json
{
  "id": "page-001",
  "alto_width": 2500,
  "alto_height": 3500,
  "image": {
    "type": "iiif",
    "service": "https://example.org/iiif/2/abc",
    "image": "https://example.org/iiif/2/abc/full/full/0/default.jpg",
    "width": 3000,
    "height": 4200,
    "iiif_version": 2,
    "label": "f. 1r"
  },
  "lines": []
}
```

### Fichier local

```json
{
  "id": "page-001",
  "alto_width": 2500,
  "alto_height": 3500,
  "image": {
    "type": "file",
    "path": "images/T1/001.jpg",
    "width": 4032,
    "height": 6048,
    "label": "f. 1r"
  },
  "lines": []
}
```

Le chemin relatif est résolu par rapport à la racine du projet. L’application
de bureau sait lire ce format et, depuis la V0.7.3, l’interface permet de créer
automatiquement cette configuration.

### Aucune image

```json
{
  "id": "page-001",
  "image": {"type": "none"},
  "lines": []
}
```

Le bloc `image` peut également être absent. Dans ce cas, la page est simplement
considérée comme dépourvue de source d’image.

## Compatibilité avec l’ancien format

Les caches existants conservent souvent :

```json
"iiif": {
  "service": "https://...",
  "image": "https://.../full/full/0/default.jpg",
  "width": 3000,
  "height": 4200,
  "iiif_version": 2,
  "label": "f. 1r"
}
```

Ce format reste entièrement accepté. Varians le normalise en mémoire comme une
source `type="iiif"`. Aucune migration des projets existants n’est obligatoire.

## Témoin sans synchronisation

Dans `project.xml`, l’attribut `alignment` d’un témoin devient facultatif :

```xml
<witness id="T1" role="base" label="Témoin de base"/>
```

est maintenant valide.

Si `alignment` est absent :

- le témoin existe normalement dans le projet ;
- l’édition TEI reste entièrement modifiable ;
- Varians ne compare pas le nombre de `<lb>` à un cache ALTO inexistant ;
- la synchronisation des panneaux est simplement inactive pour ce témoin.

Pour compatibilité avec de très anciens projets, si l’attribut est absent mais
qu’un fichier `alignments/<sigle>.json` existe déjà, Varians l’utilise encore.

## Fichiers locaux dans le viewer web

L’application de bureau gère les images locales depuis la V0.7.3. Le paquetage
de ces images dans `web_output/` n’est en revanche pas encore réalisé : le
viewer web continue de fonctionner sans changement pour les sources IIIF
existantes et sera adapté aux fichiers locaux dans une étape ultérieure.


## V0.7.1 — démarrer sans aucune image

Le mode « Nouvelle transcription » peut créer un projet avec un témoin dont la
source d’image est absente et sans fichier d’alignement. L’ajout d’images locales
ou IIIF reste une opération ultérieure : la transcription TEI n’en dépend pas.

## V0.7.2 — source d'image explicite au niveau du témoin

La création et les paramètres de projet permettent maintenant de distinguer
explicitement deux situations au niveau d'un témoin :

```xml
<witness id="A" role="base" label="Manuscrit A">
  <images type="none" />
</witness>
```

signifie que l'utilisateur a volontairement indiqué qu'aucune image n'est
associée à ce témoin pour le moment.

À l'inverse, l'absence de bloc `<images>` conserve le comportement historique
`auto` : Varians peut utiliser les informations d'image présentes dans le
fichier JSON de synchronisation/alignement s'il existe.

Cette distinction permet de démarrer une transcription directement devant le
manuscrit, sans photo ni IIIF, puis d'ajouter les images ultérieurement sans
recréer le projet. Les types `files` et `iiif` sont déjà réservés dans le modèle
de configuration pour les étapes suivantes de la feuille de route.

Le choix explicite `none` est également appliqué au rendu : si un ancien JSON
de synchronisation contient encore un bloc IIIF, Varians conserve les lignes
ALTO et les `base_keys`, mais masque la source d'image. Le fichier JSON n'est
pas modifié sur disque. Cela permet de dissocier réellement synchronisation et
fac-similé.

## V0.7.3 — import et affichage d’images locales

La fiche d’un témoin accepte maintenant une source **Images locales**. L’utilisateur
sélectionne plusieurs fichiers (JPEG, PNG, TIFF, BMP ou WebP), peut modifier leur
libellé et les réordonner. L’ordre de la liste devient l’ordre des pages du témoin.

Deux politiques sont proposées :

- **Copier les images dans le projet** (recommandé) : les fichiers sont copiés sous
  `images/<sigle>/` avec un préfixe numérique qui préserve l’ordre d’import ;
- **Référencer les fichiers existants** : `project.xml` conserve leurs chemins sans
  dupliquer les fichiers. Un chemin externe peut donc être absolu.

Le format sérialisé est explicite et indépendant des données ALTO :

```xml
<witness id="A" role="base" label="Manuscrit A">
  <images type="files">
    <image file="images/A/0001_IMG_001.jpg" label="f. 1r" />
    <image file="images/A/0002_IMG_002.jpg" label="f. 1v" />
  </images>
</witness>
```

Lorsque le témoin ne possède aucun fichier d’alignement/ALTO, Varians construit
en mémoire des pages autonomes à partir de cette liste : elles sont feuilletables,
zoomables et ouvrables comme des fac-similés normaux, mais elles ne créent aucune
fausse ligne de synchronisation. La navigation image est alors indépendante du
curseur XML.

Lorsqu’un fichier d’alignement existe déjà, les fichiers locaux remplacent en
mémoire la source d’image des pages, **dans le même ordre**, sans modifier les
lignes ALTO ni les `base_keys`. Le JSON d’alignement n’est pas réécrit.

L’application utilise l’auto-transformation du lecteur Qt pour respecter
l’orientation EXIF des photographies locales lors de l’affichage.

Le viewer web ne paquetage pas encore ces fichiers locaux dans `web_output/` :
cette partie reste une étape ultérieure. L’application de bureau est, elle,
fonctionnelle avec ces images dès la V0.7.3.


## V0.7.4 — import de Manifest IIIF

La fiche d’un témoin accepte une URL de **Manifest IIIF**. Varians prend en charge
les structures Presentation API 2 (`sequences/canvases`) et Presentation API 3
(`items/Canvas/AnnotationPage`). Les labels multilingues de la version 3 sont
réduits à un libellé d’affichage, et le service Image API est identifié en version
1, 2 ou 3 lorsqu’il est déclaré.

La configuration reste concise :

```xml
<witness id="A" role="base" label="Manuscrit A">
  <images type="iiif" manifest="https://example.org/manifest.json" />
</witness>
```

À l’import, une copie locale des métadonnées est enregistrée sous
`iiif/A.manifest.json`. Cette copie contient l’URL source et le JSON du Manifest.
Varians utilise ce cache lors des ouvertures suivantes et ne bloque donc pas le
chargement du projet sur une requête réseau. Le bouton **Charger / actualiser**
permet de tester explicitement une URL depuis la fiche du témoin ; enregistrer
un nouveau Manifest le télécharge également si aucun cache compatible n’existe.

Lorsqu’un témoin possède déjà un JSON d’alignement, les canvases du Manifest sont
associés aux pages **par ordre**. Les `id` des pages existantes, les données ALTO,
les lignes et les `base_keys` sont conservés. Sans alignement, Varians crée des
pages autonomes feuilletables à partir des canvases.

## V0.7.5 — relation images / ALTO

ALTO n'est pas une source d'image : les deux ressources sont indépendantes.
Lorsqu'images locales et ALTO sont tous deux disponibles, Varians tente d'abord
de faire correspondre le nom de l'image locale avec
`Description/sourceImageInformation/fileName` de l'ALTO. Les pages restantes
sont associées dans l'ordre déclaré. Cela permet de corriger manuellement une
association simplement en réordonnant la liste des ALTO ou des images.

## V0.7.8 — pages et navigation locale

La liste de pages résultante conserve l'union des ressources disponibles : une
image locale ne disparaît pas lorsqu'un ALTO est ajouté, et un ALTO non apparié
peut subsister comme page ressource distincte. Lorsqu'une synchronisation existe,
les identifiants de pages et `base_keys` déjà établis restent prioritaires.

Une page photographique sans ligne ALTO est maintenant affichée **seule** dans
le panneau manuscrit. Les flèches précédent/suivant parcourent les pages une à
une et le statut indique `page n/N`. La fenêtre historique ±1 est conservée
uniquement pour les lignes ALTO, où elle représente réellement un contexte de
trois lignes.

Point important : un ALTO indépendant n'est pas une synchronisation avec la TEI.
Il ne fixe donc plus le nombre attendu de `<lb>` et ne synchronise pas le curseur
XML tant qu'aucun JSON de synchronisation explicite n'a été fourni.


## V0.7.9 — surface TEI et mode page

Une image de projet peut désormais porter un `surface_id` stable. Les images
locales l'enregistrent dans `project.xml` avec l'attribut `surface`; les pages
normalisées exposent `tei_surface_id`. En l'absence de synchronisation JSON,
`page_navigation_items()` construit une entrée par page, même lorsqu'un ALTO
contient des lignes. Le panneau affiche alors la page complète ; les lignes ALTO
ne sont que des cadres facultatifs.

La relation éditoriale avec la transcription n'est pas stockée dans un second
format propriétaire : elle est portée par `<facsimile>` et `<pb facs>`. Voir
`FACSIMILE_PAGES.md`.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


> **Varians 0.8.5.3** : la sélection explicite des canvases IIIF et leur association aux OCR indépendamment du nom de fichier sont documentées en détail dans [IIIF_CANVAS_SELECTION.md](IIIF_CANVAS_SELECTION.md). Les projets antérieurs conservent le mode implicite `all`. Ne pas confondre le manifeste (catalogue) avec les pages sélectionnées de l’édition.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.


## V0.8.5.9 — Fenêtre géométrique de visualisation

Le choix des lignes voisines de la ligne synchronisée est effectué par
`display_window_indices()` avant de construire la requête d'image. Le
recadrage ne traverse plus les limites de page et évite de traverser les
changements de colonne détectés par la géométrie OCR. La méthode fonctionne
indifféremment pour les sources locales et pour les services IIIF : la géométrie
reste exprimée dans les coordonnées du document OCR, puis est redimensionnée
par `scaled_bbox()`. Le calcul du recadrage et les sources d'images existants
restent inchangés.


## V0.8.5.14 — ALTO/PAGE indépendant et conservation des images IIIF

Cas corrigé : un témoin L sans JSON s'affichait via le manifeste IIIF et ses
copies locales. Après ajout de fichiers ALTO/PAGE, le cache OCR nouvellement
peuplé prenait implicitement la place du catalogue d'images ; faute de
correspondance sûre entre ses noms et les Canvas, la couche IIIF pouvait
attribuer `image.type=none` à toutes les pages et ne plus afficher les images.

Pour les caches de type `varians-layout-cache` (sans alignement éditorial),
`iiif_resolution._layout_only_manifest_pages()` garde désormais la sélection
IIIF comme source canonique et y superpose seulement la géométrie résolue :
  - `@id` de Canvas, service et image IIIF ;
  - `ocrLink` explicite ;
  - libellé de folio exact et unique ;
  - nom exact du fichier image téléchargé, vérifié par l'index local IIIF.
L'index local est lu une seule fois ; tous les contrôles sont hors ligne.
Les identifiants de page et de surface issus du manifeste restent stables.
Les identifiants de page répétés dans plusieurs ALTO/PAGE ne sont jamais une
preuve de correspondance ; des identifiants temporaires ne servent qu'à rendre
l'analyse du contexte non ambiguë.

Les ressources non identifiées sont conservées en mémoire dans
`cache['unassociated_layout_pages']` et dénombrées dans
`cache['meta']['iiif_unassociated_layout_count']`. Elles ne deviennent pas des
pseudo-pages vides et ne remplacent jamais une image IIIF. Une infobulle
multilingue dans l'en-tête du panneau informe l'utilisateur qu'il faut
associer les fichiers OCR aux Canvas dans les paramètres du témoin.
Cette distinction ne touche pas au traitement des synchronisations JSON
`tei-manuscript-alignment`, dont les `base_keys` et identifiants demeurent
strictement protégés. L'éditeur et le viewer web utilisent le même correctif.

Tests : `tests/test_v08514_iiif_alto_independence.py` (manifeste complet ou
sélection, import ALTO avant/après, copies locales avec/sans association,
liens OCR manuels, conflits, IDs ALTO répétés, export web, intégrité des JSON).

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

## Addendum V0.8.5.24 — bordures exactes PAGE et web
Pour tout crop, la bbox de dessin tient compte des sommets polygonaux, y compris lorsque la bbox historique est plus petite. Un item sans géométrie exploitable désactive le recadrage plutôt que produire un faux cadre près de (0,0). Le lecteur web utilise 24 px de marge comme Qt, et la même notion de continuité physique pour choisir ses voisins. Voir `WEB_VIEWER_GEOMETRY.md`.
