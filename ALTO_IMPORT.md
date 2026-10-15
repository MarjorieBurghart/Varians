# Import ALTO — V0.7.5

## Principe

ALTO est une ressource facultative et indépendante : un témoin peut avoir des
images sans ALTO, des ALTO sans images, ou les deux. La synchronisation entre
témoins reste elle aussi indépendante.

## Import

Dans les paramètres d'un témoin, choisir **Fichiers ALTO séparés**, puis ajouter
les XML. Ils peuvent être copiés dans le projet (`alto/<témoin>/`) ou rester à
leur emplacement actuel.

Varians lit les versions ALTO usuelles sans dépendre du namespace exact. Il
extrait notamment `Page`, `TextLine`, `String/@CONTENT`, les dimensions de page
et les coordonnées `HPOS`, `VPOS`, `WIDTH`, `HEIGHT`.

## Association aux images

Si `sourceImageInformation/fileName` est présent, Varians privilégie cette
information pour associer l'ALTO à une image locale de même nom. Sinon, il
utilise l'ordre des pages. L'ordre peut être corrigé dans le dialogue du témoin.

## Synchronisation existante

Si le témoin possède déjà un JSON de synchronisation, Varians conserve les
identifiants de page, `base_keys`, scores et autres métadonnées, tout en mettant
à jour le texte et la géométrie provenant du nouvel ALTO.

## V0.7.8 — distinction ALTO / synchronisation

L'import d'un ALTO sur le témoin de base ne transforme plus implicitement cette
ressource en synchronisation avec les `<lb>` de l'édition. Tant qu'aucun JSON de
synchronisation explicite n'est déclaré, Varians considère la navigation ALTO
comme autonome. Le contrôle structurel du nombre de `<lb>` reste libre.

Si images locales et ALTO sont présents ensemble, toutes les pages sont
conservées. L'association par nom d'image reste prioritaire, puis l'ordre sert
de repli. L'ajout d'un ALTO ne supprime ni ne remplace la couche image.


## V0.7.9 — ALTO sans synchronisation

La présence de lignes ALTO n'active plus un affichage par ligne. Tant qu'aucun
JSON de synchronisation n'existe, Varians reste en mode page : l'image complète
est affichée et les rectangles de toutes les lignes ALTO peuvent être superposés
facultativement. La page courante est déterminée par `<pb facs>` lorsqu'il existe.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


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
