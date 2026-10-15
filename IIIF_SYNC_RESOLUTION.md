# Varians 0.8.5.5 — Résolution des pages synchronisées vers les Canvas IIIF

## Principe et absence d'appariement positionnel

Un **Canvas IIIF** désigne une ressource de présentation du manifeste ; une
**page de synchronisation** est identifiée par `pages[].id` dans le JSON
`tei-manuscript-alignment` ; une **image affichée** est un service distant
ou un fichier de travail local. Ces trois identités ne sont jamais confondues.
La position d'un Canvas dans un manifeste, même après sélection, **ne permet
jamais de décider** à quelle page de synchronisation il correspond.

Le traitement est effectué sans modifier le JSON de Varians-Synchro : les
`pages[].id`, `lines`, `base_keys`, `bbox` et annotations sont copiés sans
réécriture. L'overlay enrichit chaque page d'un bloc `image`, d'un
`iiif_canvas_key`, d'un `tei_surface_id` lorsqu'un Canvas est connu et d'un
`iiif_resolution` de diagnostic. L'ancien champ `iiif` reste disponible comme
source de métadonnées ; il n'est pas altéré.

## Résolution déterministe (iiif_resolution.py)

Par ordre de priorité :

1. Association explicite `pageLink` du projet ;
2. Identifiant exact du Canvas fourni dans le JSON (ex. `iiif.id`) ;
3. URI du service IIIF Image ;
4. URL de l'image, en normalisant seulement les suffixes **reconnus** de l'API
   Image (région / taille / rotation / qualité), sans élargissement flou ;
5. Liaison explicite avec une ressource ALTO/PAGE localement identifiée ;
6. Libellé de folio littéralement unique, avec normalisation typographique
   prudente et rejet des intitulés mécaniques `Page 123` / `Vue 123` ;
7. À défaut, choix manuel d'un Canvas par l'utilisateur.

Une association plus forte présentant plusieurs candidats bloque la recherche
à ce niveau ; le système ne s'en remet pas à un libellé approximatif. Un
Canvas réclamé par deux pages de synchronisation différentes est refusé,
sauf si une liaison manuelle prioritaire résout la collision. Les références
manuelles à des pages absentes ou des Canvas non sélectionnés sont refusées
par la validation. Les Canvas possédant des URL obsolètes peuvent être
retrouvés par leur service IIIF s'il n'a pas changé.

La résolution prend en charge les deux formes de manifeste IIIF Presentation
API v2 (`sequences[].canvases[]`) et v3 (`items[].type=Canvas`). L'importateur
conserve les URI Canvas fournies par le serveur ; le libellé ne les remplace
jamais.

## Persistance des choix

Dans `project.xml`, pour un témoin en mode `selectionMode="selected"` :

```xml
<images type="iiif" manifest="https://example.org/manifest" selectionMode="selected">
  <canvas ref="https://example.org/canvas/folio-14v" />
  <pageLink page="F-original-page-001" canvas="https://example.org/canvas/folio-14v" />
  <ocrLink file="alto/F-14v.xml" canvas="https://example.org/canvas/folio-14v" />
</images>
```

- `canvas` : page retenue pour l'édition ;
- `pageLink` : identifiant **original** `pages[].id` du JSON de synchronisation ;
- `ocrLink` : chemin ALTO/PAGE vers ce Canvas ;
- l'image téléchargée n'a aucune existence en tant que page distincte.

Les `pageLink` n'apparaissent que lorsqu'un utilisateur établit ou corrige
une association. Les associations automatiques restent recalculables depuis
les identifiants stables. Les `pageLink` explicites sont prioritaires.

## Fonctionnement dans l'éditeur et dans le viewer web

`editeur_tei.MainWindow` et `web_viewer.generator.build_dataset` appliquent
les mêmes fonctions `apply_witness_alto_policy` puis
`apply_witness_image_policy` et, si activé, `apply_working_copy`. Le répertoire
`iiif/local/<sigle>` indexe les téléchargements par identité distante ; si le
fichier est absent, le bloc `image` original reste distant et la ligne est
conservée. Un rechargement de manifeste ne substitue jamais un Canvas par son
indice de liste. Un changement de dimensions déclarées peut réutiliser une
copie locale si l'URL de téléchargement est strictement identique et unique.

Les surfaces TEI sont calculées sur les Canvas éditoriaux sélectionnés. Pour
les projets historiques en mode `all` possédant un JSON de synchronisation,
seuls les Canvas **résolus** de ce JSON servent à créer de nouvelles surfaces.
Les anciennes surfaces ne sont pas automatiquement supprimées. Un nouveau
témoin créé dans l'interface privilégie le mode `selected` ; les anciens
projets en mode `all` restent lisibles.

## Diagnostic utilisateur

Dans le sélecteur de Canvas, les colonnes « Page synchronisée », « Copie locale »
et « État de l'association » complètent les colonnes Canvas / ALTO-PAGE. Le
statut indique si la correspondance vient d'un choix manuel, d'un identifiant,
du service, de l'image ou du libellé, et quelle source sera privilégiée selon
la préférence locale. Les candidats ambigus ne sont pas choisis.

Les erreurs de téléchargement et d'indisponibilité IIIF sont signalées par la
visionneuse ; le sélecteur n'effectue **aucune requête d'accès en direct** pour
tester le serveur et ne garantit donc pas à l'avance sa disponibilité. Une
copie locale non présente est indiquée comme telle. En l'absence d'association
fiable, la page reste navigable avec ses lignes, mais sans image ; l'éditeur
propose de vérifier le Canvas dans les paramètres du témoin.

## Compatibilité, limites et tests

- Aucune conversion des JSON ou modification des `base_keys` ;
- les anciens attributs du projet continuent d'être reconnus ;
- les associations manuelles existantes sont conservées ;
- les nouvelles clés de traduction sont intégrées à `i18n/{fr,en,de,ja,cs,it,ru}.xml` ;
- tests `tests/test_v0855_sync_canvas_resolution.py` pour 469/5, v2/v3,
  résolution Canvas/service/image, ambiguïtés, choix manuel, rechargement,
  copies locales, plusieurs témoins, persistance et surfaces ;
- **PySide6 absent de l'environnement de livraison** : le dialogue doit être
  vérifié en situation réelle (ou dans un banc Qt) avant diffusion générale ;
- les serveurs IIIF de Munich/Fribourg et le JSON exact du projet utilisateur
  n'ont pas été fournis : impossible de revendiquer une validation sur ces
  deux fichiers spécifiques.


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
