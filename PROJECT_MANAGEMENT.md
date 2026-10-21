# Gestion des projets — V0.4

## Principe

Un **projet** est un dossier indépendant décrit par `project.xml`. Plusieurs projets peuvent coexister sur la même machine et être rouverts depuis le menu **Fichier > Réouvrir un projet récent…**.

La liste des projets récents n'est **pas** enregistrée dans les projets eux-mêmes. C'est une préférence locale de l'application (QSettings), ce qui permet de copier ou partager un projet sans embarquer l'historique personnel de l'utilisateur.

## Nouveau projet…

**Fichier > Nouveau projet…** crée un projet autonome. L'utilisateur choisit :

- le dossier cible (vide) ;
- le titre ;
- le point de départ : une édition TEI existante ou une nouvelle transcription ;
- la langue de l'interface ;
- un ou plusieurs témoins ;
- pour chaque témoin, son sigle, son libellé et, facultativement, le fichier JSON de synchronisation ;
- le témoin de base.

Varians place ensuite dans le nouveau dossier :

- la TEI copiée ou générée sous `xml/edition.xml` ;
- les alignements sous `alignments/<sigle>.json` ;
- les ressources génériques `rendering/` ;
- les catalogues `i18n/` ;
- un dossier `web_output/` ;
- le `project.xml` généré.

Le dossier cible doit être vide afin d'éviter tout écrasement accidentel.

> Dans la V0.4, les alignements doivent déjà exister. Le futur outil d'alignement TEI ↔ ALTO aura précisément pour rôle de les produire.

## Paramètres du projet…

**Fichier > Paramètres du projet…** permet d'éditer graphiquement les informations qui se trouvent dans `project.xml` :

- titre et TEI ;
- langue ;
- XSLT, CSS, `custom-elements.xml` ;
- dossier `i18n/` ;
- sortie du viewer web ;
- liste des témoins et alignements ;
- témoin de base.

Avant l'écriture, l'ancien `project.xml` est sauvegardé sous `project.xml.bak`. Le projet est ensuite rechargé afin que les nouveaux chemins et témoins prennent effet.

Les chemins situés à l'intérieur du dossier du projet sont écrits sous forme **relative**. Les chemins externes restent absolus.

## Projets récents

L'application mémorise jusqu'à **10 projets**. Le projet courant est ajouté automatiquement à la liste lors de son ouverture.

Le sous-menu **Réouvrir un projet récent…** :

- affiche le titre et le chemin de chaque projet ;
- retire automatiquement une entrée si son fichier n'existe plus ;
- propose **Effacer la liste des projets récents**.

Effacer la liste conserve toujours le projet actuellement ouvert comme première entrée.

## Plusieurs éditions / projets

Aucune donnée spécifique à une édition n'est stockée dans l'installation de l'éditeur : chaque dossier de projet conserve ses propres TEI, alignements, rendu et traductions. On peut donc maintenir autant de projets que nécessaire et passer rapidement de l'un à l'autre via la liste des projets récents.

La V0.4 reste une application à **une fenêtre de projet active à la fois**. L'architecture des projets est indépendante et ne suppose pas un unique projet global ; une évolution ultérieure vers plusieurs fenêtres simultanées reste donc possible sans changer le format `project.xml`.

## V0.4.2 — Choix XSLT de l'éditeur / du projet

Les nouveaux projets proposent deux sources pour la XSLT :
`xsltMode="builtin"` (pas de copie, mises à jour de l'éditeur prises en compte)
et `xsltMode="file"` (copie indépendante à personnaliser).
Le mode est modifiable dans les paramètres du projet. Les anciens projets sans
`xsltMode` restent automatiquement en `file`, sans écraser leurs personnalisations.
Voir **XSLT_POLICY.md** pour les détails et les limites de portabilité.


## V0.5.0 — Schéma RELAX NG

Un projet peut désormais contenir un élément facultatif :

```xml
<schema type="relaxng" file="schema/edition.rng"/>
```

L’assistant de création propose un champ facultatif pour le RNG. Les paramètres
du projet permettent ensuite d’ajouter, remplacer ou retirer cette association.
L’absence de schéma est parfaitement valide et conserve le comportement V0.4.x.
Voir `RELAXNG_VALIDATION.md`.

## V0.5.1 — Politique de schéma

La gestion du RNG n'est plus limitée à un fichier copié dans le projet. Trois
modes sont enregistrés dans `project.xml` :

```xml
<schema type="relaxng" source="xml-model"/>
<schema type="relaxng" source="project" file="schema/edition.rng"/>
<schema type="relaxng" source="none"/>
```

Le premier est le choix par défaut dans « Nouveau projet… ». Il permet à chaque
édition TEI de rester l'autorité sur son propre schéma via `<?xml-model?>`.

Un projet existant avec `<schema ... file="..."/>` mais sans `source` reste en
mode schéma projet. Un projet plus ancien sans élément `<schema>` passe en mode
automatique `xml-model`; le mode « aucun » peut être choisi explicitement dans
les paramètres du projet.

Le cache des schémas distants est une préférence technique locale de
l'application et n'est pas placé dans le dossier du projet.

## Démarrage sans projet — V0.5.7

L'application ne charge plus automatiquement le `project.xml` d'exemple au démarrage. Sans argument de ligne de commande, elle ouvre une fenêtre d'accueil légère ; les commandes **Nouveau projet…**, **Ouvrir un projet…** et **Réouvrir un projet récent…** restent immédiatement disponibles dans le menu **Fichier**.

Le `project.xml` livré à la racine reste le projet de démonstration historique et peut être ouvert explicitement. Il n'est plus ajouté à la liste des projets récents par un simple démarrage de l'application.

L'ouverture d'un projet remplace la fenêtre d'accueil par la fenêtre de travail maximisée. L'ouverture directe par ligne de commande reste possible :

```text
python editeur_tei.py chemin/vers/project.xml
```


## V0.5.9 — dernier projet ouvert et fermeture explicite

Varians mémorise séparément le **dernier projet encore ouvert**. Si l'application
est quittée alors qu'un projet est actif, ce projet est rouvert au prochain
démarrage. Cette préférence ne remplace pas la liste des dix projets récents.

**Fichier > Fermer le projet** (`Ctrl+W`) applique d'abord le garde-fou habituel
sur les modifications non enregistrées, puis revient à l'écran d'accueil sans
quitter l'application. Le projet reste dans les récents mais la préférence de
réouverture automatique est effacée.

Le projet de démonstration livré avec l'application n'est toujours jamais ouvert
automatiquement lors d'une première utilisation.

## V0.6.3 — Sous-dossier `xml/`

Les nouveaux projets utilisent désormais l'arborescence suivante :

```text
project.xml
xml/
    edition.xml
alignments/
rendering/
i18n/
web_output/
```

Le but est que `project.xml` soit le seul fichier XML directement présenté à la
racine d'un dossier projet : le fichier de configuration ne peut ainsi plus être
confondu avec le document TEI par un utilisateur débutant.

`project.xml` sérialise explicitement :

```xml
<edition file="xml/edition.xml"/>
```

La création d'un nouveau projet crée automatiquement le dossier `xml/` et y
copie la TEI choisie sous le nom `edition.xml`. Les sauvegardes, la validation
RELAX NG, XPath, l'aperçu XSLT et la génération du viewer utilisent le chemin
résolu depuis `project.xml` et ne supposent donc pas que l'édition se trouve à
la racine.

### Compatibilité ascendante

Les projets historiques avec `<edition file="edition.xml"/>` restent pris en
charge sans migration forcée. Varians ouvre et sauvegarde leur fichier à son
emplacement historique. Si un très ancien `project.xml` possède un élément
`<edition/>` sans attribut `file`, Varians préfère `edition.xml` à la racine s'il
existe, puis `xml/edition.xml` sinon.

## V0.7.0 — ressources de témoin facultatives

Un témoin peut désormais être déclaré sans attribut `alignment`. Cela prépare
les projets de transcription où aucune image, aucun ALTO et aucune
synchronisation ne sont encore disponibles.

Exemple :

```xml
<witnesses base="A">
  <witness id="A" role="base" label="Manuscrit A"/>
</witnesses>
```

L’absence de synchronisation n’empêche ni l’ouverture du projet, ni l’édition,
ni la validation TEI. Le compteur de lignes indique alors simplement le nombre
de `<lb>` présents dans la TEI sans imposer un total attendu.

Les dialogues de création et de paramètres acceptent désormais un champ de
synchronisation vide. Les anciens projets restent inchangés.

## V0.7.1 — Nouvelle transcription sans TEI préexistante

**Fichier > Nouveau projet…** propose désormais deux points de départ :

1. **Partir d’une édition TEI existante** : comportement historique ;
2. **Commencer une nouvelle transcription** : aucun fichier XML source n’est demandé.

Dans le second mode, Varians crée automatiquement `xml/edition.xml`. Le fichier
contient un `teiHeader` volontairement minimal (`titleStmt`, `publicationStmt`,
`sourceDesc`) et un corps `<text><body><p>…</p></body></text>` prêt à recevoir la
transcription. Le titre du projet et le témoin de base sont repris dans ce
squelette.

Un témoin reste obligatoire pour définir le contexte du projet, mais son fichier
de synchronisation est facultatif. Il est donc possible de commencer à transcrire
directement devant un manuscrit sans disposer d’image, d’ALTO ni d’alignement.
Ces ressources pourront être ajoutées ultérieurement au même projet.

En mode **xml-model automatique**, le squelette référence le RNG TEI All officiel.
En mode **schéma projet**, la validation utilise le RNG copié dans `schema/`; en
mode **aucun schéma**, aucune instruction `xml-model` n’est ajoutée au TEI.

## V0.7.2 — témoin sans image, choix explicite

Dans la boîte de dialogue d'un témoin, Varians affiche maintenant une ligne
« Source des images » avec notamment « Aucune image pour le moment ». Ce choix
est enregistré dans `project.xml` avec un bloc `<images type="none"/>`.

Les anciens projets n'ont pas ce bloc : ils restent en mode automatique et
continuent d'utiliser les données d'image éventuellement présentes dans leurs
fichiers de synchronisation. Aucune migration n'est imposée.

## V0.7.3 — images locales d’un témoin

Dans la fiche d’un témoin, la source « Images locales » ouvre une liste de pages.
Plusieurs fichiers peuvent être ajoutés d’un coup, réordonnés et renommés par un
libellé éditorial. Le choix « Copier les images dans le projet » est activé par
défaut pour les nouvelles importations.

En mode copie, Varians crée `images/<sigle>/` au sein du projet. En mode référence,
les fichiers restent à leur emplacement d’origine et `project.xml` enregistre les
chemins nécessaires. L’ajout d’images peut être fait lors de la création du projet
ou ultérieurement via **Fichier > Paramètres du projet…**.

Aucun ALTO ni fichier de synchronisation n’est nécessaire pour feuilleter ces
images. Ces ressources restent indépendantes et peuvent être ajoutées plus tard.


## V0.7.4 — Manifest IIIF d’un témoin

La source d’images d’un témoin peut être un Manifest IIIF Presentation 2 ou 3.
Le `project.xml` conserve son URL dans `<images type="iiif" manifest="…"/>`,
tandis qu’une copie de cache est enregistrée dans `iiif/<sigle>.manifest.json`.
Le Manifest peut être ajouté dès la création du projet ou ultérieurement depuis
**Fichier > Paramètres du projet…**. Aucun ALTO ni synchronisation n’est requis.

## V0.7.5 — ALTO indépendant

Un témoin peut désormais déclarer des fichiers ALTO indépendamment des images
et du fichier de synchronisation :

```xml
<witness id="A" role="base" label="Manuscrit A">
  <images type="none"/>
  <alto type="files">
    <file file="alto/A/0001_f1r.xml" label="f. 1r"/>
  </alto>
</witness>
```

L'absence de `<alto>` conserve le comportement historique : Varians utilise les
données ALTO éventuellement présentes dans le JSON de synchronisation.

À l'import, les XML peuvent être copiés dans `alto/<sigle>/` ou référencés à
leur emplacement actuel. Le cache d'analyse est dérivé et conservé sous
`.varians/alto/`; il peut être régénéré à partir des XML sources.

## V0.7.6 — synchronisation ajoutable ultérieurement

Le fichier de synchronisation d'un témoin est désormais explicitement traité
comme une ressource facultative. La fiche du témoin permet de l'ajouter, de le
remplacer ou de le retirer après la création du projet. Pour un projet portable,
Varians peut copier le JSON sous `alignments/<sigle>.json`; une référence externe
reste possible. Ces opérations n'altèrent ni les images ni les ALTO indépendants.


## V0.7.9 — foliotage et surfaces TEI

Pour `images type="files"`, une image peut recevoir `surface="A1-p0001"`. La
colonne Folio/page alimente `surface/@n` et le `pb/@n` inséré par Varians.
L'identifiant de surface reste stable lors des réordonnancements ou corrections
de libellé. Sauvegarder les paramètres complète le `<facsimile>` de l'édition
par fusion incrémentale ; Varians ne supprime ni ne reconstruit un fac-similé
existant. Les conflits d'`xml:id` et XML mal formé sont signalés sans modification.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


> **Varians 0.8.5.3** : la sélection explicite des canvases IIIF et leur association aux OCR indépendamment du nom de fichier sont documentées en détail dans [IIIF_CANVAS_SELECTION.md](IIIF_CANVAS_SELECTION.md). Les projets antérieurs conservent le mode implicite `all`. Ne pas confondre le manifeste (catalogue) avec les pages sélectionnées de l’édition.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.


## V0.8.5.17 — Diagnostic / actualisation

Voir `WITNESS_DIAGNOSTICS.md`. Le module `witness_resource_refresh.py` centralise le rapport indépendant de Qt et la préparation transactionnelle des ressources. L’éditeur conserve sa TEI, sa pile d’annulation et ses panneaux ; il ne commet le rechargement qu’après validation. La synchronisation n’est jamais déduite des seules données ALTO/PAGE.


Varians V0.8.5.18 — Navigation par folios et images doubles
Voir FOLIO_NAVIGATION.md. Une surface peut contenir deux zones de folio ; aucun changement des JSON/ALTO ou des images source.


## Varians V0.8.5.19 — Correction du dialogue « Double page… »

Les zones `<zone>` créées par la commande « Double page… » appartiennent à la TEI de l’édition, même lorsque le témoin a un JSON de synchronisation actif. La commande ne modifie ni project.xml, ni les alignements, ni les images.


## Extension 0.8.5.21 : dispositions de travail

Voir [`WORKSPACE_LAYOUT.md`](WORKSPACE_LAYOUT.md). Les vues verticale, horizontale, grille, les fenêtres individuelles et le mode « Toujours au premier plan » ne changent que les préférences d’affichage `QSettings`. Le même `ManuscriptPanel` est transféré entre parents Qt ; `workspace_layout.py` ne contient pas de logique de synchronisation. Le ratio XML/manuscrits est librement redimensionnable, y compris vers 20 % XML.


## V0.8.7.0 — Documents XML auxiliaires (`<documents>`)

Un projet peut déclarer, à côté de l’édition, des documents XML auxiliaires
(fichier d’autorités, notes, etc.) :

```xml
<documents>
  <document file="xml/personnes.xml" label="Personnes"/>
  <document file="xml/lieux.xml" schema="none"/>
  <document file="xml/notes.xml" schema="file" schemaFile="schema/notes.rng"/>
</documents>
```

- `file` (obligatoire) : chemin relatif au projet ;
- `label` (facultatif) : nom affiché, sinon le nom du fichier ; depuis la
  V0.8.9.0, il se modifie aussi par un clic droit sur l’onglet du document,
  « Renommer l’onglet… » (un nom vide supprime l’attribut) ;
- `schema` (facultatif) : `auto` par défaut (suivre le `<?xml-model?>` du
  document), `none` (aucune validation) ou `file`, avec `schemaFile`.

Les entrées sans fichier, les doublons et l’édition elle-même sont ignorés.
Un projet sans documents auxiliaires n’a pas d’élément `<documents>`, et
Varians ne lui en ajoute jamais. La fenêtre « Paramètres du projet » conserve
les documents déclarés. `project_management.update_project_documents` modifie
cette liste sans toucher au reste du fichier (copie `.bak` préalable).

Limite : une version de Varians antérieure à 0.8.7.0 lit le projet
normalement, mais supprime `<documents>` si l’on y enregistre les paramètres
du projet.

Les onglets masqués et leur ordre (Affichage ▸ « Choisir les documents
affichés… », clic droit ▸ « Masquer l’onglet ») ne sont pas enregistrés dans
`project.xml` : comme la disposition des témoins, c’est une préférence locale
(`QSettings`) propre à chaque projet. L’ordre des `<document>` dans
`project.xml` reste celui de leur ajout.

## V0.8.9.1 — Requêtes XPath nommées (`<xpathQueries>`)

Les requêtes de « Mes requêtes », dans Aide ▸ « Débugger l’apparat… », sont
enregistrées dans le projet, pour être réutilisées et partagées avec lui :

```xml
<xpathQueries>
  <query name="rdg sans @wit">//tei:rdg[not(@wit)]</query>
</xpathQueries>
```

- `name` (obligatoire) : nom affiché dans la liste ; à nom égal, la première
  requête est gardée ;
- le contenu de `<query>` est l’expression XPath 1.0 (préfixe `tei:` pour
  l’espace de noms TEI) ; une requête vide est ignorée.

Un projet sans requête n’a pas d’élément `<xpathQueries>`. Comme pour
`<documents>`, la fenêtre « Paramètres du projet » conserve les requêtes, et
`project_management.update_project_xpath_queries` ne réécrit que cet élément
(copie `.bak` préalable). Une version de Varians antérieure à 0.8.9.1 lit le
projet normalement, mais supprime `<xpathQueries>` si l’on y enregistre les
paramètres du projet.

## V0.9.0.0 — Édition assemblée par XInclude (parties)

L’édition déclarée par `<edition file="…"/>` peut inclure ses parties (un
fichier par sermon, par exemple) selon la norme XInclude :

```xml
<TEI xmlns="http://www.tei-c.org/ns/1.0" xmlns:xi="http://www.w3.org/2001/XInclude">
  …
  <body>
    <xi:include href="sermons/s01.xml"/>                              <!-- fragment -->
    <xi:include href="sermons/s02.xml" xpointer="s02"/>               <!-- par identifiant -->
    <xi:include href="sermons/s03.xml" xpointer="element(/1/2/1/1)"/> <!-- par chemin -->
  </body>
</TEI>
```

- **Rien n’est déclaré dans `project.xml`** : Varians lit les `xi:include`
  de l’édition enregistrée, et les relit après chaque enregistrement de
  l’édition ou d’une partie. Les parties ont chacune leur onglet, nommé
  d’après le fichier. Le format de `project.xml` ne change pas.
- Un fichier à la fois inclus et déclaré dans `<documents>` est traité comme
  une partie (une seule session par fichier) ; s’il cesse d’être inclus, il
  redevient un document auxiliaire. « Renommer l’onglet… » et « Retirer le
  document du projet » ne concernent que les documents auxiliaires.
- Les chemins des `xi:include` sont relatifs à l’édition : « Enregistrer
  l’édition sous » dans un autre dossier le signale avant d’écrire.
- Le schéma d’une partie est celui de l’édition (validation de l’édition
  assemblée, complétion).
- Synchronisation des témoins (V0.9.1.0) : les lignes du pivot sont
  comptées dans l’ordre de l’édition assemblée, d’une partie à l’autre ; les
  JSON d’alignement restent un par témoin pour toute l’édition, et le pivot
  doit contenir les textes dans l’ordre de l’édition. Rien n’est à déclarer.
- Textes synchronisés à part (V0.9.1.1) : un texte qui a son dossier
  `alignments/<nom du fichier du texte>/` (un JSON par témoin, au format
  habituel) est synchronisé à part, sans déclaration. Son pivot est celui
  du projet, sauf exception déclarée à la main :

  ```xml
  <parts>
    <part name="s02" base="B"/>
  </parts>
  ```

  `name` est le nom du fichier du texte, sans extension ; `base`, le sigle
  du pivot. Une déclaration incomplète ou répétée est ignorée ; un pivot
  inconnu n’empêche pas d’ouvrir le projet et est signalé par « État des
  témoins… ». La fenêtre des paramètres du projet conserve `<parts>`. Mode
  d’emploi : aide, « Mettre en place une édition en parties (XInclude) ».

Un projet sans `xi:include` est inchangé.
