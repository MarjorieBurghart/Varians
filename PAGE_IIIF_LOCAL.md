# Varians 0.8.5 — PAGE XML et copies de travail IIIF

## Objectifs et invariants

Varians sépare **quatre** ressources : l'édition TEI, les données de disposition des lignes (ALTO ou PAGE), les images et les synchronisations ligne à ligne. L'ajout de PAGE et la mise en cache IIIF ne doit modifier **aucune** des trois autres ressources. Les caches sont recalculables ; les données sources originales demeurent les autorités.

### 1. Import ALTO/PAGE

- Dans « Paramètres du projet → Témoins → Modifier », la section « Transcription géométrique (ALTO / PAGE) » accepte des listes ordonnées de XML. Chaque fichier est identifié d'après sa **racine** (`alto` ou `PcGts`), et non seulement d'après son extension ou l'identité du témoin.
- **ALTO** : coordonnées `TextLine/@HPOS`, `@VPOS`, `@WIDTH`, `@HEIGHT` et, s'il existe, polygone `Shape/Polygon/@POINTS` ; transcription à partir de `String/@CONTENT`, avec prise en compte des espaces `SP`.
- **PAGE XML** : `PcGts/Page`, dimensions `imageWidth`, `imageHeight`, nom d'image `imageFilename` ; lignes `TextLine`, polygones `Coords/@points`, ligne de base éventuelle `Baseline/@points` et transcription `TextEquiv/Unicode` (repli sur les `Word` si absente). L'arborescence des régions est parcourue en ordre XML. Le format de namespace n'est pas figé.
- Les objets normalisés conservent `bbox` (compatibilité avec l'ancien recadrage et les synchronisations), `polygon` (liste de paires de coordonnées) et éventuellement `baseline` ; `alto_id` et `alto` sont maintenus comme **champs internes historiques**, même pour une ligne PAGE, afin de ne pas casser l'API existante. Les rectangles ALTO continuent de fonctionner.
- L'éditeur (Qt, `QGraphicsPolygonItem`) et le viewer web (`SVG polygon`) dessinent des polygones là où ils existent, sinon les rectangles. Les dimensions de la transcription sont converties vers les dimensions d'image.
- Un projet peut utiliser ALTO pour A, PAGE pour B ; on peut aussi mélanger les formats dans les fichiers d'un même témoin.
- `<alto type="files">` et le dossier `alto/<témoin>/` restent délibérément en place pour la **rétrocompatibilité XML** ; ce sont désormais des conteneurs de fichiers de géométrie ALTO/PAGE. Une migration éventuelle vers `<layout>` devra lire l'ancien élément.
- L'identité des pages et les liens de synchronisation (`base_keys`) sont préservés durant la superposition. Aucune synchronisation n'est inventée à partir de la seule présence de PAGE.

### 2. Copie locale des images IIIF

Deux propriétés indépendantes sont stockées **sur les images du témoin** dans `project.xml` :

```xml
<witness id="P" label="Paris">
  <images type="iiif" manifest="https://exemple.org/manifest.json"
          localCopy="true" webLocalCopy="false" />
  <alto type="files"><file file="alto/P/folio-001.page.xml" /></alto>
</witness>
```

- `localCopy="true"` : dans le logiciel Qt, utiliser les images intégrales déjà présentes dans `iiif/local/<témoin>/`, recadrer localement et éviter ainsi les requêtes répétées de fragments IIIF.
- `webLocalCopy="true"` : **uniquement** lors de la génération du viewer, substituer les images locales disponibles aux URL IIIF et copier ces images dans `web_output/images/<témoin>/` pour que l'export soit portable. `false` conserve les images distantes, même si le logiciel utilise une copie locale.
- Depuis la **0.8.5.2**, le gestionnaire IIIF propose « Télécharger les manquantes » (incrémental) et « Actualiser la sélection » (forçage). Son téléchargement asynchrone commence après la sauvegarde du projet et n'empêche plus de travailler. La copie peut être suspendue, reprise ou arrêtée entre les images ; elle se reprend depuis les ressources manquantes.
- Le cache de manifest existant `iiif/<témoin>.manifest.json` est utilisé, même hors connexion ; `iiif/local/<témoin>/index.json` associe un hash de la source de chaque canvas au nom de l'image. Les images elles-mêmes sont stockées sans modifier ni le manifest ni la TEI.
- Si une page manque, le mécanisme de repli **conserve l'URL IIIF distante**. Cela permet une consultation hybride en ligne, mais **la capacité hors ligne exige une copie complète**. Les échecs sont signalés après le téléchargement. La version 0.8.5 ne propose pas de mode « hors ligne strict » bloquant tous les accès distants.
- Le transfert vérifie le protocole HTTP(S), le type de réponse, quelques signatures d'images, refuse les réponses vides et impose une limite par image de 250 Mio. Les fichiers temporaires sont atomiquement remplacés et éliminés en cas d'échec. Une image déjà valide n'est pas écrasée par une requête échouée. La capture n'utilise **ni cookie navigateur ni authentification implicite** ; les images sous droits ou exigeant une session doivent être traitées selon les conditions du service.
- Les serveurs IIIF Image API 2 attendent `full/full/0/default.jpg`, ceux en API 3 `full/max/0/default.jpg` ; la v1 utilise `full/full/0/native.jpg`. `max` correspond à la taille maximale *servie*, éventuellement inférieure au canvas : il ne faut pas promettre la pleine résolution du master conservé par l'institution. Les droits de reproduction demeurent à vérifier par l'utilisateur.

### 3. Fichiers et points d'intégration

| Fichier | Responsabilité |
|---|---|
| `alto_import.py` | `parse_page_file`, `parse_layout_file`, fusion avec synchronisations, cache de géométrie |
| `project_config.py`, `project_management.py` | Lecture et écriture des deux drapeaux IIIF ; listes de fichiers ALTO/PAGE |
| `project_dialogs.py` | Deux cases IIIF indépendantes par témoin ; option d'actualisation ; ajout des XML |
| `iiif_local.py` | Image complète, fichiers temporaires, index atomique, copie incrémentale, superposition locale sans accès réseau |
| `editeur_tei.py` | Progression du téléchargement ; géométrie Qt ; application du mode de travail local |
| `web_viewer/generator.py` | Choix local/distante **spécifique à l'export**, embarquement des fichiers locaux ; polygones SVG |
| `i18n/{fr,en,de,ja,cs,it,ru}.xml`, `help/*.html` | UI et documentation dans les sept langues |

### 4. Vérifications et limites

- Exécuter `python -m pytest -q` depuis le dossier source. La suite 0.8.5 comporte des tests de PAGE, ALTO, mélange des formats, sérialisation XML, copie IIIF, reprise et choix d'export.
- Un parseur ne peut reconstruire les polygones lorsque le fichier PAGE ne fournit aucune géométrie de ligne ; ces lignes gardent un rectangle de repli minimal et doivent être corrigées à la source.
- La détection se fait sur la racine, et les fichiers pris en charge sont **XML ALTO** et **PAGE XML**, pas des archives ZIP OCR-D ou des images binaires.
- La validation de rendu *sur le serveur IIIF réel* et la vérification de la qualité de traduction par des locuteurs natifs sont recommandées. Elles ne sont pas remplacées par les tests unitaires automatiques.
- Les exports ont des fichiers d'images externes relatifs au HTML. Pour transférer un viewer local, conserver le dossier `images/` adjacent au fichier HTML et toutes ses dépendances.


### 5. Validation sur fichiers réels PERO OCR (correctif 0.8.5.1)

Une même image manuscrite (`644 × 892` px) a été fournie avec un ALTO v2 et
un PAGE XML 2019-07-15, tous deux issus de PERO OCR. Les sources du manuscrit
ne sont **pas** intégrées dans la distribution : les tests livrés sont synthétiques.

- Les deux importateurs reconnaissent **39 lignes** ; textes OCR identiques sur
  les 39 lignes ; les 39 boîtes englobantes sont rigoureusement identiques.
- PAGE conserve **39 polygones** (21 à 24 points chacun) et **39 lignes de base**.
  Les 39 polygones ont été contrôlés comme valides et situés dans l'image.
- Chaque ligne présente un UUID commun : `line_<UUID>` (ALTO) versus
  `id_<UUID>` (PAGE), tandis que ses identifiants littéraux diffèrent.
- Le correctif 0.8.5.1 compare d'abord les identifiants exacts et les UUID
  communs **avant** de tenter un repli par ordre. Une permutation de lignes
  conserve donc `base_keys`, `corrected` et le numéro de ligne associé à la
  bonne géométrie, au lieu de transférer la synchronisation à la mauvaise ligne.
- Lorsqu'un candidat et une nouvelle ligne possèdent des UUID bien formés mais
  distincts, le repli par ordre n'attache plus les métadonnées de l'un à
  l'autre. Les lignes anciennes non retrouvées demeurent consultables.
- L'ALTO contient ici des boîtes englobantes et la transcription détaillée par
  mot ; le PAGE fournit les polygones et l'indice de confiance au niveau ligne.
  La qualité philologique de l'OCR n'est pas évaluée par ces tests.

**Limites et précautions** : il ne faut pas charger les deux descriptions de
la **même** image comme deux pages successives d'un témoin : elles décrivent
la même page et produiraient deux entrées. Choisir ALTO *ou* PAGE pour cette
image ; panacher les formats sur des images distinctes est pris en charge.
Pour des réimports où les UUID changent entièrement (par exemple une nouvelle
segmentation OCR), les synchronisations doivent être révisées plutôt que
réattribuées automatiquement sans preuve. Le repli historique par ordre reste
possible pour des identifiants anciens non-UUID : contrôler visuellement
l'alignement après un changement de segmentation.

## 6. V0.8.5.2 — gestionnaire de téléchargements et acquisition sélective

Deux **politiques de sélection**, définies *par témoin*, complètent les cases
indépendantes `localCopy` (application de bureau) et `webLocalCopy` (export) :

- `downloadScope="all"` (par défaut, rétrocompatible) : toutes les images des canvases du manifeste IIIF mis en cache.
- `downloadScope="ocr"` : seulement les canvases rattachés **sans ambiguïté** à une page d'un fichier ALTO ou PAGE déclaré dans `<alto type="files">`. La structure XML historique `<alto>` est conservée pour la compatibilité des anciens projets.

Exemple :

```xml
<witness id="A" label="Assisi 541">
  <images type="iiif" manifest="https://bibliotheque.exemple/manifest"
          localCopy="true" webLocalCopy="false" downloadScope="ocr" />
  <alto type="files">
    <file file="alto/A/Assisi541-test-1r-PAGE.xml" label="1r" />
    <file file="alto/A/Assisi541-test-2r.xml" label="2r" />
  </alto>
</witness>
```

### 6.1 Association sans supposition sur l'ordre

`iiif_selection.select_ocr_pages()` parse réellement chaque fichier fourni avec `parse_layout_file()`.
Les clés candidates proviennent de `Page/@imageFilename` (PAGE),
`sourceImageInformation/fileName` (ALTO), des libellés déclarés et des noms des fichiers.
Elles sont comparées aux libellés du manifeste, noms de canvas et noms d'image.
Les noms sont rapprochés par *nom de base normalisé* ; les folios finaux
(`1r`, `1v`…) peuvent être rapprochés même si le nom du manuscrit précède le folio.
Une correspondance n'est acceptée que si elle est **unique** pour la page OCR.
Pas de repli sur les indices/ordres de fichiers : les couvertures et pages blanches
présentes dans un manifeste ne doivent jamais décaler la sélection.

- Aucune ressource ALTO/PAGE : **0 image sélectionnée**, jamais un téléchargement général implicite.
- OCR non identifiable ou ambigu : diagnostic, image exclue ; les autres images associées restent sélectionnées.
- Le moteur ne convertit pas et n'écrit pas dans les fichiers ALTO/PAGE ni dans le manifeste IIIF.
- Une sélection plus étroite **ne supprime jamais** les copies antérieures déjà téléchargées.

### 6.2 Traitement asynchrone et gestion des reprises

`iiif_local.plan_witness_copy()` est une opération *strictement locale* qui retourne
le nombre total de canvases, la sélection, les copies déjà présentes et les diagnostics.
`iiif_local.download_witness_copy(..., scope=..., layout_files=..., cancel_event=..., pause_event=...)`
exécute les téléchargements, avec un index JSON atomiquement actualisé après chaque image.
Les appels réseau d'images demeurent exclusivement dans `_fetch_image()`.

L'interface `iiif_download_manager.py` est une boîte de dialogue non modale, avec un
`DownloadThread(QThread)` unique par gestionnaire, un témoin choisi ou une file de
plusieurs témoins, une barre de progression, le journal des erreurs, les boutons
**Télécharger les manquantes**, **Tous les témoins**, **Actualiser la sélection**,
**Pause/Reprendre**, **Arrêter**. Elle est accessible par **Fichier → Gestionnaire de
téléchargements IIIF…** et s'ouvre automatiquement après la création ou l'enregistrement
d'un projet demandant une copie locale. Les téléchargements ont lieu dans le thread de
travail, pas dans le fil d'interface Qt. Une requête en cours peut encore attendre le
timeout réseau (25 s) : pause et arrêt sont pris en compte **entre les images**.
Fermer/masquer le gestionnaire ne tue pas le travail. Quitter le projet demande l'arrêt
et attend la fin sûre du travail courant.

Après une opération, `MainWindow.refresh_local_iiif_cache()` répercute les images
nouvelles sur les panneaux sans réouvrir le projet, sans réécrire le TEI et sans
modifier les synchronisations. Le viewer web respecte toujours son choix indépendant
`webLocalCopy` ; l'absence d'une image locale entraîne une URL IIIF distante.

### 6.3 Tests et limites

`tests/test_v0852_iiif_manager.py` vérifie le périmètre sélectif, un manifeste avec
couvertures et feuillets sans OCR, les noms PERO OCR avec suffixes de folio, les
ambiguïtés, le mode complet historique, la reprise, le comportement sans aucun
ALTO/PAGE et la sérialisation rétrocompatible de `downloadScope`.
Les tests automatisés ne remplacent pas une campagne interactive PySide6 ni un essai
réseau contre un serveur IIIF réel (bande passante, accès restreint, erreurs 429/503).


### 7. Sélection éditoriale IIIF explicite (0.8.5.3)

Le manifeste contient le catalogue complet ; le projet indique séparément les canvases réellement retenus. Une liaison explicite `<ocrLink>` permet d’associer un ALTO ou PAGE local à un canvas IIIF indépendamment du nom d’image ou de l’ordre. Seules les images retenues produisent de nouvelles surfaces TEI et participent au téléchargement sélectif. Le logiciel et le viewer web respectent la même sélection. Le tri naturel est proposé pour les listes locales. Un dialogue propose facultativement la suppression des anciennes surfaces automatiques non référencées, uniquement après une sauvegarde datée et une confirmation. Voir **IIIF_CANVAS_SELECTION.md** pour l’architecture, les limites et les procédures de sécurité.
