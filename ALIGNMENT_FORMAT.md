# Format d'alignement — version 1

Les fichiers d'alignement constituent le contrat entre le futur outil d'alignement et l'éditeur.

## Racine

```json
{
  "meta": {
    "format": "tei-manuscript-alignment",
    "format_version": 1,
    "witness": "B",
    "base_witness": "A",
    "role": "secondary"
  },
  "pages": []
}
```

## Page

Chaque page conserve les dimensions ALTO et les informations IIIF :

```json
{
  "id": "page-001",
  "alto_width": 2500,
  "alto_height": 3500,
  "iiif": {
    "service": "https://...",
    "image": "https://.../full/full/0/default.jpg",
    "width": 3000,
    "height": 4200,
    "iiif_version": 2,
    "label": "f. 1r"
  },
  "lines": []
}
```

## Ligne du témoin de base

Le témoin de base définit les clés stables utilisées pour synchroniser tout le projet. La clé est actuellement construite comme `page_id::line`.

```json
{
  "line": 12,
  "bbox": {"hpos": 100, "vpos": 200, "width": 800, "height": 80},
  "alto_id": "...",
  "alto": "texte HTR/ALTO"
}
```

## Ligne d'un témoin secondaire

```json
{
  "line": 18,
  "order": 154,
  "bbox": {"hpos": 110, "vpos": 240, "width": 790, "height": 78},
  "alto_id": "...",
  "alto": "texte HTR/ALTO",
  "score": 0.87,
  "base_keys": ["page-001::12", "page-001::13"]
}
```

`base_keys` peut contenir zéro, une ou plusieurs lignes du témoin de base. L'éditeur affiche le centre de ces correspondances et une fenêtre physique de trois lignes.

Pour compatibilité avec les caches historiques du projet Jean de la Rochelle, l'éditeur accepte encore `keys816`, mais le futur outil d'alignement devra produire `base_keys`.

## V0.7.0 — source d’image générique

Le bloc historique `iiif` reste accepté sans modification. Pour les nouveaux
fichiers, Varians accepte également un bloc `image` avec `type` égal à `iiif`,
`file` ou `none`. Voir `IMAGE_SOURCES.md`.

La présence d’un fichier d’alignement n’est plus une condition d’existence d’un
témoin dans `project.xml`. Les `base_keys` restent le contrat de synchronisation
quand un alignement est disponible ; cette évolution ne modifie donc pas leur
sémantique.

## Images locales et alignements — V0.7.3

La source d’image peut désormais être déclarée au niveau du témoin dans
`project.xml`, indépendamment du JSON d’alignement. Si une liste de fichiers
locaux est associée à un témoin possédant déjà des pages ALTO, Varians applique
les images aux pages dans l’ordre sans modifier `lines`, `bbox`, `base_keys` ou
les autres données d’alignement.

## V0.7.5 — ALTO séparé du fichier de synchronisation

Le JSON d'alignement n'est plus le seul moyen de fournir les lignes ALTO. Un
témoin peut déclarer des XML ALTO séparés dans `project.xml`. Varians fusionne
alors les nouvelles bbox/textes ALTO avec le cache d'alignement existant et
préserve `base_keys`, `score`, `order` et l'identifiant de page déjà utilisé par
la synchronisation.

## V0.7.6 — ressource de synchronisation facultative

Le JSON décrit ici n'est plus requis pour déclarer un témoin. Il peut être ajouté
à un témoin existant ultérieurement. Lorsqu'il est présent, `project.xml` le
référence par l'attribut `alignment` du `<witness>`. L'absence de cet attribut
signifie simplement que le témoin n'est pas encore synchronisé avec la base.

## V0.9.1.1 — un JSON par texte

Pour un texte synchronisé à part d'une édition en parties, les JSON sont
rangés dans `alignments/<nom du fichier du texte>/<témoin>.json`, au même
format : le JSON du pivot du texte (celui du projet, ou celui de
`<part name base>`) donne ses lignes de référence, `page_id::line`, qui
correspondent aux `<lb edRef="#pivot"/>` du texte seul ; les `base_keys` des
autres témoins désignent ces lignes. Varians-Synchro les produit sur le
fichier du texte. Le nom du fichier JSON est le sigle déclaré dans
`project.xml` ; un JSON d'un témoin non déclaré est ignoré et signalé.

## V0.9.2.8.2 — témoin nommé par son sigle

`meta.witness` et `meta.base_witness` peuvent nommer le témoin et le pivot
par leur identifiant (attribut `id` de `<witness>` dans `project.xml`) ou par
leur sigle (attribut `siglum`, quand le sigle n'est pas un identifiant XML :
voir PROJECT_MANAGEMENT.md). Le diagnostic ne signale une discordance que si
la valeur n'est ni l'un ni l'autre.
