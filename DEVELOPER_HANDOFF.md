
## Varians V0.8.5.20 — Navigation en image double, ergonomie et sécurité TEI

Consulter `DOUBLE_PAGE_PARTS.md`. `editeur_tei.py` intègre `SplitImagePreview` (QWidget), `SplitPreviewLoader` (QObject slot GUI), les données pixellaires de séparation et l’utilisation de la géométrie des lignes dans « Marquer la page ». `folio_navigation.py` expose `markable_part_for_line`, `inspect_surface_part_split` et `configure_surface_parts`. On refuse tout écrasement des zones TEI non créées par Varians et tout changement de libellé d’une zone déjà référencée par <pb/>. Le séparateur en pixels exacts est un paramètre optionnel, et l’ancienne API split_percent reste disponible. Vérifier l’affichage réel sous Windows/PySide6 (non installé en CI).

# Varians — dossier de transmission développeur

**Version de référence : 0.8.5.12** (documentation historique complétée par les fichiers techniques successifs)

Ce document est destiné à un développeur qui reprend Varians sans avoir suivi son historique. Il décrit la philosophie du logiciel, les contrats de données, l'architecture du code, les invariants de sûreté éditoriale, les principaux workflows et la manière recommandée d'étendre ou de corriger le projet.

Varians est un éditeur XML TEI desktop spécialisé dans l'édition critique et la transcription savante. Il combine édition XML, validation RELAX NG, aperçu XSLT/CSS, gestion de témoins et d'images, ressources ALTO, synchronisation entre témoins et génération d'un viewer web autonome.

L'objectif central n'est pas de cacher la TEI à l'utilisateur, mais de **l'assister sans jamais prendre le contrôle de son texte éditorial**. Les automatismes doivent donc être conservateurs, explicables, réversibles et compatibles avec des documents TEI enrichis manuellement.

---

## 1. Principes de conception

### 1.1. La TEI est la source éditoriale

Le fichier TEI (`xml/edition.xml` dans les projets récents) est le document scientifique. Les fichiers de projet, les caches ALTO, les JSON de synchronisation et les préférences d'interface servent à l'exploiter, mais ne doivent pas réécrire arbitrairement son contenu.

Règle de maintenance : **si un automatisme n'est pas certain de préserver une intention éditoriale, il doit s'abstenir**.

Exemples déjà appliqués :

- un `<facsimile>` existant n'est jamais reconstruit en bloc ; les surfaces manquantes sont ajoutées incrémentalement ;
- une surface TEI déjà enrichie de `<zone>` ou d'autres métadonnées n'est pas remplacée ;
- « Marquer la page » refuse d'agir si le curseur est à l'intérieur d'une balise ;
- le formateur XML n'ajoute jamais de blancs autour de `<lb/>` et respecte `xml:space="preserve"` ;
- les suggestions de `custom-elements.xml` améliorent la saisie mais ne changent jamais la validité RELAX NG.

### 1.2. Ressources indépendantes et progressives

Un témoin peut être créé sans aucune ressource puis être enrichi progressivement. Les couches sont indépendantes :

1. témoin déclaré dans `project.xml` ;
2. images : aucune, locales ou IIIF ;
3. lien page ↔ transcription : `<facsimile>` + `<pb n edRef facs>` ;
4. ALTO : géométrie et texte des lignes physiques ;
5. synchronisation ligne à ligne : JSON avec lignes de référence et `base_keys`.

Ne jamais confondre **ALTO présent** et **synchronisation présente**. Un ALTO peut décrire 200 lignes sans qu'aucune de ces lignes ne soit encore reliée aux `<lb>` de la TEI.

### 1.3. Mode page et mode ligne

Le comportement d'affichage dépend de la ressource réellement exploitable :

- **mode page** : images présentes, avec ou sans ALTO, mais aucune synchronisation ligne utilisable ; afficher la page entière ;
- **mode ligne** : synchronisation ligne à ligne réellement exploitable ; il devient possible de centrer/cadrer une ligne ou un groupe de lignes.

Depuis 0.8.4, la simple présence d'un fichier JSON ne suffit plus. `resource_state.py` décide si la synchronisation est effective en analysant le JSON brut avant superposition d'un ALTO indépendant.

### 1.4. Compatibilité ascendante

Varians a été développé par incréments et accepte plusieurs formes historiques :

- ancien `edition.xml` à la racine ; nouveau `xml/edition.xml` ;
- anciennes images IIIF stockées dans les JSON d'alignement ; nouvelles sources déclarées dans `project.xml` ;
- ancien champ `keys816` lu comme repli ; les nouveaux producteurs doivent écrire `base_keys` ;
- absence historique de `<images>` = mode `auto`, afin de continuer à exploiter les données contenues dans les anciens caches.

Lors d'une évolution de format, préférer **lecture tolérante + écriture dans le format moderne** plutôt qu'une migration destructive à l'ouverture.

### 1.5. Séparer validité et ergonomie

RELAX NG reste l'autorité pour la validité. `custom-elements.xml` fournit seulement des aides de saisie et de formatage propres au projet.

Exemple : une liste `valuesMode="replace"` peut remplacer les valeurs proposées dans l'interface, mais ne rend pas les autres valeurs invalides si le RNG les autorise.

---

## 2. Dépendances, lancement et environnement

Dépendances Python minimales :

```text
PySide6
lxml
```

Sous Windows, les scripts fournis sont :

- `lancer_editeur.bat` : lancement de Varians ;
- `installer_pyside6.bat` : aide à l'installation de PySide6 ;
- `installer_lxml_optionnel.bat` : installation de lxml ;
- `generer_viewer_web.bat` : génération directe du viewer de démonstration/projet.

Point d'entrée principal :

```text
editeur_tei.py
```

Point d'entrée du viewer web :

```text
web_viewer/generator.py
```

Le logiciel vise Windows en priorité, mais le code utilise autant que possible `pathlib`, Qt et Python standard pour rester portable.

---

## 3. Arborescence d'un projet Varians

Projet récent typique :

```text
project.xml
xml/
  edition.xml
images/
  <witness>/...
alto/
  <witness>/...
alignments/
  <witness>.json
iiif/
  <witness>.manifest.json
rendering/
  custom-elements.xml
  tei.css
  [tei-to-html.xsl si XSLT locale]
i18n/
  fr.xml
  en.xml
  de.xml
  ja.xml
  cs.xml
  it.xml
  ru.xml
web_output/
  viewer.html
  images/...
```

`project.xml` contient la configuration du projet, pas les préférences personnelles d'interface. Les témoins affichés et les hauteurs de panneaux sont stockés dans `QSettings`, indexés par le chemin du projet.

---

## 4. Contrat de `project.xml`

Le parseur est `project_config.load_project()`.

Exemple simplifié :

```xml
<teiManuscriptProject>
  <title>Mon édition</title>
  <edition file="xml/edition.xml"/>
  <interface translationsDir="i18n" language="fr" fallbackLanguage="en"/>
  <rendering xsltMode="builtin" css="rendering/tei.css"
             customElements="rendering/custom-elements.xml"/>
  <witnesses base="A1">
    <witness id="A1" role="base" label="Assisi, Sacro convento, 541">
      <images type="files">
        <image file="images/A1/0001.jpg" label="1r" surface="A1-p0001"/>
      </images>
      <alto type="files">
        <file file="alto/A1/0001.xml" label="1r"/>
      </alto>
    </witness>
  </witnesses>
</teiManuscriptProject>
```

### Sources d'images

`<images type="...">` accepte :

- `none` : aucune image, explicitement ;
- `files` : images locales ;
- `iiif` : Manifest IIIF ;
- `auto` : compatibilité historique, chercher éventuellement dans le JSON de synchronisation.

Chaque image locale peut porter :

- `file` : chemin ;
- `label` : folio/page utilisé notamment dans `surface/@n` et `pb/@n` ;
- `surface` : `xml:id` stable de la surface TEI ;
- largeur/hauteur facultatives.

### ALTO

`<alto type="files">` déclare une série de fichiers ALTO indépendants de la synchronisation. L'absence de `<alto>` ou `type="auto"` permet d'utiliser les anciennes lignes présentes dans le JSON d'alignement.

### Synchronisation

Le chemin du JSON reste porté par l'attribut historique `witness/@alignment`. Il est facultatif. Un fichier existant peut néanmoins être vide ou provisoire : utiliser `resource_state.py` avant d'activer le mode ligne.

---

## 5. Modèle TEI utilisé par Varians

### 5.1. Liste des témoins

Les nouveaux projets créés depuis zéro produisent un `listWit` structuré :

```xml
<sourceDesc>
  <listWit>
    <witness xml:id="A1">Assisi, Sacro convento, 541</witness>
  </listWit>
</sourceDesc>
```

Ne pas synchroniser aveuglément ce bloc avec `project.xml` après coup : l'utilisateur peut enrichir les descriptions TEI.

### 5.2. Pages et fac-similé

Le lien page ↔ image est TEI natif :

```xml
<facsimile>
  <surface xml:id="A1-p0001" n="1r">
    <graphic url="../images/A1/0001.jpg"/>
  </surface>
</facsimile>
```

Et dans le texte :

```xml
<pb n="1r" edRef="#A1" facs="#A1-p0001"/>
```

Le `xml:id` de `surface` doit rester stable. Le libellé `@n` peut changer sans casser `@facs`.

Le module `tei_facsimile.py` contient les fonctions de création/fusion et les garde-fous.

### 5.3. Linéation

Les lignes éditoriales de référence sont typiquement :

```xml
<lb edRef="#A1"/>
```

Elles deviennent les ancres canoniques de la synchronisation ligne à ligne. L'ALTO n'est pas, à lui seul, la preuve qu'un `<lb>` donné correspond à une ligne physique donnée.

---

## 6. Contrat JSON de synchronisation

Format de métadonnées moderne :

```json
{
  "meta": {
    "format": "tei-manuscript-alignment",
    "format_version": 1,
    "witness": "B1",
    "role": "secondary"
  },
  "pages": []
}
```

Une ligne secondaire peut contenir :

```json
{
  "id": "B1-p0001-l0023",
  "line": 23,
  "text": "...",
  "bbox": [100, 200, 800, 80],
  "base_keys": [
    "A1-p0001::line17",
    "A1-p0001::line18"
  ],
  "score": 0.91
}
```

Règles :

- `base_keys` peut être vide, contenir une ou plusieurs clés ;
- `keys816` est accepté en lecture uniquement pour compatibilité ;
- les nouveaux outils doivent écrire `base_keys` ;
- une synchronisation peut représenter 1↔1, 1↔n, n↔1 ou absence ;
- l'alignement est une correspondance textuelle/spatiale, **pas** un relevé de variantes critiques.

Voir `ALIGNMENT_FORMAT.md` et `SYNCHRONIZATION.md`.

---

## 7. Cartographie des modules Python

### `editeur_tei.py`

Fichier principal Qt. Il contient encore beaucoup de logique d'interface historique. Il orchestre :

- fenêtre principale et écran d'accueil ;
- barre d'outils/menus ;
- éditeur XML avec numéros de ligne et coloration ;
- aperçu XSLT/CSS et éditeur de fragment ;
- panneaux manuscrits ;
- recherche XML et XPath ;
- validation RNG ;
- complétion ;
- gestion des paires de balises ;
- dialogue d'aide et À propos ;
- préférences de témoins visibles.

**Conseil de maintenance :** éviter d'y ajouter de nouveaux algorithmes lourds. Les extraire dans des modules sans Qt lorsque possible, puis ne garder ici que l'orchestration et les adaptations à `QTextCursor`/widgets.

### `project_config.py`

Lecture immuable du `project.xml` vers des dataclasses (`ProjectConfig`, `WitnessConfig`, etc.). C'est la source de vérité en lecture pour la configuration du projet.

### `project_management.py`

Création et sérialisation des projets :

- génération de TEI minimale ;
- écriture de `project.xml` ;
- copie de ressources ;
- préparation des images, ALTO et alignements ;
- création d'un projet portable.

### `project_dialogs.py`

Dialogues Qt de création/modification de projet et de témoins. L'ordre des images/ALTO y est éditable.

### `image_sources.py`

Abstraction de la source image d'une page. Il faut passer par ce module plutôt que supposer qu'une page possède toujours IIIF ou toujours un fichier local.

Responsabilités :

- normaliser une source en `PageImageSource` ;
- produire les requêtes/cibles d'affichage ;
- superposer la politique d'images du témoin à un cache existant ;
- construire les pages autonomes lorsqu'il n'y a pas de synchronisation.

### `iiif_manifest.py`

Lecture IIIF Presentation API 2 et 3. Le Manifest est importé puis mis en cache dans le projet. L'ouverture ultérieure ne doit pas dépendre d'un nouveau téléchargement des métadonnées.

### `alto_import.py`

Parse ALTO, construit un cache normalisé, associe les ALTO aux pages et superpose les lignes à des pages existantes. L'import ALTO ne doit jamais supprimer la couche image ou inventer une synchronisation.

### `resource_state.py`

Petit module critique introduit en 0.8.4. Il distingue :

- ressource de synchronisation présente ;
- synchronisation effectivement exploitable.

Toujours examiner le JSON **brut** avant d'ajouter des lignes provenant d'un ALTO indépendant.

### `tei_facsimile.py`

Gestion TEI native des pages :

- identifiants de surface ;
- génération/fusion incrémentale du `<facsimile>` ;
- insertion prudente de `<pb>` ;
- détection de la page active à une position du curseur.

C'est un module à traiter avec une prudence éditoriale élevée.

### `relaxng_validation.py`

Validation complète RELAX NG via lxml, avec cache de schéma compilé et invalidation quand le schéma principal ou ses dépendances changent.

### `schema_resolution.py`

Détecte les instructions `<?xml-model?>`, résout les schémas locaux/distants, met en cache les RNG distants et leurs dépendances.

Depuis la V0.9.2.3, elle donne aussi les sources des règles Schematron (`schematron_sources` : le RNG employé, puis les déclarations Schematron, sans doublon ; V0.9.2.4 : des `SchematronSource(path, phase)`, la phase venant de l'attribut `phase` d'une déclaration) ; le module `schematron.py` les applique (SchXslt2 et Saxon). Voir `RELAXNG_VALIDATION.md`.

### `rng_completion.py`

Moteur de complétion RELAX NG positionnelle. Il connaît les constructions `group`, `choice`, `optional`, répétitions, `interleave`, références et valeurs finies. Il contient aussi un cache de contexte XML incrémental.

Ne pas remplacer ce moteur par une simple liste de descendants du parent : cela ferait régresser la complétion contextuelle.

### `custom_completion.py`

Lecture de `custom-elements.xml` et fusion avec les suggestions RNG. Gère les valeurs dynamiques, notamment la source `witnesses` pour `@wit`.

### `xml_tag_pairs.py`

Moteur lexical de paires XML utilisable même pendant une phase momentanément non bien formée. Ignore commentaires, CDATA, instructions et déclarations. Sert à :

- surligner la fermeture correspondante ;
- supprimer une enveloppe ;
- renommer ouverture/fermeture de façon couplée ;
- déterminer l'étendue complète d'un résultat XPath.

### `tei_formatter.py`

Formateur TEI conservateur. Il ne cherche pas à produire un joli XML à tout prix : il ne modifie que les espaces structurels considérés sûrs.

Protections prioritaires :

- `xml:space="preserve"` ;
- aucun blanc nouveau autour de `<lb/>` ;
- contenu mixte ;
- incertitude = ne rien modifier.

`custom-elements.xml` peut déclarer `formatting="inline|block|preserve"`, mais une déclaration `block` ne doit jamais contourner les protections absolues.

### `xpath_search.py`

XPath 1.0 avec lxml. Renvoie des `XPathMatch` qui comportent désormais début **et fin** de l'élément source afin qu'un clic sélectionne l'élément complet. Gère un repli automatique pour les expressions simples dans le namespace TEI.

### `selection_sync.py`

Petits algorithmes sans Qt utilisés pour conserver l'identité d'une occurrence lors de la synchronisation XML ↔ XSLT/CSS. La chaîne seule n'est pas suffisante ; Varians utilise le paragraphe et le rang de l'occurrence.

### `save_io.py`

Écriture atomique avec `.bak`. À réutiliser pour toute ressource éditoriale dont une réécriture partielle pourrait être dommageable.

### `i18n.py`

Charge les catalogues XML `i18n/*.xml`. Les fichiers du projet surchargent les fichiers installés clé par clé. Une clé manquante retombe sur la langue de secours, puis sur la clé elle-même.

Les variables utilisent `str.format`. Lors de l'ajout d'une clé traduite, conserver exactement les mêmes placeholders (`{count}`, `{path}`, etc.) dans tous les catalogues.

### `web_viewer/generator.py`

Générateur moderne, piloté par `project.xml`. Il :

- charge la TEI et les ressources ;
- décide mode page/mode ligne ;
- normalise les sources image ;
- emballe les images locales dans `web_output/images/` ;
- sérialise les traductions ;
- produit un HTML autonome.

### `web_viewer/legacy_v11_core.py`

Contient le cœur historique d'extraction TEI et certaines fonctions de compatibilité. Il conserve également beaucoup de code ancien lié au prototype de trois manuscrits. Le générateur moderne n'importe qu'un sous-ensemble de fonctions.

**À ne pas faire :** réintroduire dans le code moderne des constantes ou chemins historiques de ce fichier. Pour une future refactorisation, extraire progressivement les fonctions réellement utilisées dans des modules génériques, accompagnées de tests, puis réduire ce fichier.

---

## 8. Chaîne de chargement des ressources d'un témoin

Dans le desktop comme dans le viewer web, raisonner dans cet ordre :

1. charger le JSON de synchronisation brut s'il existe ;
2. déterminer l'état de synchronisation effective à partir du JSON brut ;
3. superposer l'ALTO indépendant ;
4. superposer/appliquer la source image ;
5. choisir mode page ou ligne à partir de l'état calculé en 2.

L'étape 2 avant l'étape 3 est essentielle. Sinon les lignes d'un ALTO indépendant pourraient être prises à tort pour une synchronisation.

---

## 9. Viewer desktop : règles d'affichage

### Aucun témoin avec image

Masquer entièrement la zone manuscrits pour libérer l'espace à l'éditeur.

### Plusieurs témoins

Les panneaux sont dans un `QSplitter` vertical. La liste des témoins visibles et les proportions sont des préférences locales par projet.

Un témoin coché mais sans image affichable ne doit pas produire un panneau vide.

### Mode page

Afficher la page complète. Un ALTO peut fournir des cadres facultatifs, mais aucune ligne ne doit être privilégiée sans synchronisation.

La page active est déterminée par le dernier `<pb>` pertinent avant le curseur, en tenant compte de `@edRef` et de `@facs`.

### Mode ligne

Seulement si `resource_state` confirme une synchronisation effective.

---

## 10. Viewer web : parité avec le desktop

Le viewer web doit refléter les mêmes concepts :

- projet sans images : aucune colonne vide ;
- mode page : boutons `← page` et `page →` ;
- mode ligne : boutons `← ligne` et `ligne →` ;
- clic dans le texte : calcul de la page courante indépendamment pour chaque témoin à partir des `<pb edRef>` précédents ;
- images locales copiées dans le paquet d'export ;
- traductions exportées dans le dataset JSON.

Lors de toute correction du desktop portant sur la distinction page/ligne, vérifier explicitement si le viewer web a besoin du même correctif.

---

## 11. Édition XML assistée : invariants

### Paires de balises

- la position immédiatement après `>` n'est pas « dans » la balise ;
- la position immédiatement avant `<` n'est pas « dans » la balise suivante ;
- les balises autofermantes n'ont pas de paire ;
- les éléments imbriqués de même nom doivent être appariés correctement ;
- en cas de structure croisée/ambiguë, ne pas inventer une paire.

### « Marquer la page »

- autorisé dans le texte ou entre deux balises ;
- interdit à l'intérieur de **toute** balise, y compris `<pb>` ;
- ne sert jamais à réaffecter silencieusement un `<pb>` existant ;
- le `<pb>` créé doit contenir `@n`, `@edRef` et `@facs`.

### XPath

Un clic sur un résultat élémentaire doit sélectionner tout l'élément dans le source, ouverture et fermeture comprises. Pour un élément autofermant, sélectionner toute la balise.

### Formateur

Ne jamais introduire de blancs textuels nouveaux autour de `<lb/>`, même sans `break="no"`.

---

## 12. Internationalisation

Depuis 0.8.4.2, l'interface fournie comporte :

- français (`fr`) ;
- anglais (`en`) ;
- allemand (`de`) ;
- japonais (`ja`) ;
- tchèque (`cs`) ;
- italien (`it`) ;
- russe (`ru`).

Format :

```xml
<translations lang="de" label="Deutsch">
  <string key="menu.file">Datei</string>
</translations>
```

Le label est volontairement écrit dans la langue concernée afin que le sélecteur de langue reste compréhensible quelle que soit la langue active.

### Ajout d'une clé

1. ajouter la clé au catalogue anglais et français ;
2. ajouter la même clé aux autres catalogues ;
3. conserver les placeholders exactement ;
4. ajouter/adapter le test de parité des catalogues ;
5. si le libellé est visible dans une fenêtre déjà ouverte, vérifier `retranslate_ui()`.

Les textes TEI/XML, noms de standards (TEI, ALTO, IIIF, XPath, RELAX NG, Schematron, XSLT, CSS) ne doivent pas être « traduits » en termes locaux inventés.

---

## 13. Préférences utilisateur vs données projet

À stocker dans `project.xml` :

- ressources scientifiques et chemins du projet ;
- langue de projet/interface choisie ;
- témoins, rôles, sources image, ALTO, synchronisation ;
- politiques XSLT/RNG.

À stocker dans `QSettings` :

- témoins actuellement visibles ;
- proportions du splitter ;
- maximisation temporaire ;
- retour visuel à la ligne ;
- préférences purement ergonomiques.

Ne pas introduire dans `project.xml` des états de fenêtre propres à une machine ou à un utilisateur.

---

## 14. Validation, schémas et complétion

Trois politiques de schéma :

- `auto` : suivre `<?xml-model?>` ;
- `file` : schéma RNG explicite du projet ;
- `none` : validation RNG désactivée.

La vérification de bien-formé est automatique et asynchrone. F8 lance la validation complète RELAX NG et reste l'autorité.

Le cache de schéma compilé doit être invalidé si le RNG principal **ou une dépendance `include`/`externalRef`** change.

Schematron (V0.9.2.3) : les règles du RNG employé et des déclarations Schematron sont appliquées dans le même passage que le RNG ; une erreur Schematron compte comme une erreur RNG, un avertissement non. Une règle incorrecte (V0.9.2.4 : `ValidationIssue` du domaine `SCHEMATRON_RULES`) a sa ligne dans le panneau sans rendre le document invalide. Un fichier `.sch` affiché est vérifié à la place (`schematron_check_ui`, opération `check_schematron`). Voir `RELAXNG_VALIDATION.md`.

---

## 15. Performances

Les fichiers TEI peuvent être volumineux. Plusieurs optimisations historiques doivent être préservées :

- analyse de bien-formé hors du thread UI après debounce ;
- mise à jour incrémentale des positions `<lb>` quand une modification ne touche pas la structure des balises ;
- cache de contexte pour la complétion ;
- cache des RNG compilés ;
- réutilisation de résultats d'analyse de la même révision ;
- ne pas parser tout le document à chaque déplacement de curseur pour les paires de balises.

Avant d'ajouter un parse complet dans un slot `cursorPositionChanged` ou `contentsChange`, chercher une solution locale/incrémentale.

---

## 16. Écritures et sauvegardes

Pour le TEI et les ressources sensibles, préférer :

1. écrire dans un fichier temporaire dans le même dossier ;
2. conserver/faire tourner un `.bak` lorsque prévu ;
3. remplacer atomiquement la cible.

Ne jamais faire une longue transformation destructive directement dans le fichier source.

`save_io.atomic_write_text_with_backup()` est l'utilitaire standard pour le texte.

---

## 17. Tests

Les tests se trouvent dans `tests/` et sont volontairement nombreux sans dépendre systématiquement de Qt. La philosophie est de tester les algorithmes séparément de l'interface graphique.

Commande :

```bash
python -m pytest -q
```

À chaque version :

- tous les tests existants doivent passer ;
- compiler tous les `.py` avec `py_compile` ;
- vérifier la parité des catalogues i18n et des placeholders ;
- vérifier le viewer de démonstration ;
- si du JavaScript a changé, lancer `node --check` lorsque Node est disponible ;
- tester l'archive avec `unzip -t`.

PySide6 peut être absent de l'environnement CI/de construction. Dans ce cas, ajouter des tests statiques ou des fonctions sans Qt, puis indiquer clairement que le ressenti graphique doit être validé sous Windows.

### Matrice de ressources minimale

Conserver des tests couvrant au moins :

| Images | ALTO | facsimile/pb | JSON sync | Attendu |
|---|---|---|---|---|
| non | non | non | non | TEI seule |
| locales | non | oui | non | mode page |
| IIIF | non | oui | non | mode page |
| oui | oui | oui | non | page entière + ALTO facultatif |
| oui | oui | oui | JSON vide | mode page |
| oui | oui | oui | sync réelle | mode ligne |
| base sync | secondaire sans `base_keys` | oui | JSON secondaire | secondaire en mode page |

---

## 18. Procédure recommandée pour une modification

1. reproduire le problème avec le plus petit jeu de données possible ;
2. décider si la règle appartient au modèle (module sans Qt) ou seulement à l'UI ;
3. écrire d'abord le test du cas qui échoue ;
4. corriger sans casser les formats historiques ;
5. vérifier desktop **et** viewer web si la notion affectée est partagée ;
6. mettre à jour la documentation spécialisée ;
7. exécuter la suite complète.

Pour un changement de format projet ou JSON : documenter explicitement la lecture ancienne et l'écriture nouvelle.

---

## 19. Zones à risque / dette technique

### `editeur_tei.py` très volumineux

Il concentre encore de nombreuses classes Qt. Une refactorisation progressive serait utile, mais doit être menée par extraction testée, pas par réécriture globale.

Candidats :

- contrôleur de validation ;
- contrôleur de recherche ;
- contrôleur de manuscrits/images ;
- construction des menus/barres ;
- gestion des préférences de vue.

### `legacy_v11_core.py`

Il contient de l'historique spécifique au prototype initial. Le code moderne en utilise encore quelques extracteurs. À terme, extraire seulement les fonctions nécessaires dans des modules génériques et réduire ce fichier.

### Schematron

Appliqué depuis la V0.9.2.3 (`schematron.py`, SchXslt2 livré dans `resources/schxslt2/`, Saxon). L'interface distingue bien-formé, validité RNG et règles Schematron (colonne Origine, étiquette Schematron de la barre d'état). Depuis la V0.9.2.4 : phase choisie par l'attribut `phase` d'une déclaration ; fichiers `.sch` ajoutés, créés, vérifiés (F8) et complétés dans Varians (`schematron_check`, `schematron_check_ui`, `schematron_completion`, schéma ISO livré dans `resources/schemas/schematron/`). Depuis la V0.9.2.5 : texte non enregistré d'un fichier de règles ouvert appliqué au document ; boîte « Règles Schematron du document… » (`schematron_rules_dialog`, `xml_model_edit`) pour la phase et les déclarations ; nouveautés 2020/2025 dans le schéma livré ; règles d'un XSD et de ses `xs:include`/`xs:import`. Depuis la V0.9.2.6 : fichiers inclus (`sch:include`, `sch:extends/@href`, inclusions RELAX NG et XSD) lus dans leur texte non enregistré, pour la validation comme pour la vérification d'un `.sch` (`schematron.rules_files`, copies temporaires). Restent hors champ : Schematron 1.5, validation par un XSD, corrections rapides (SQF).

### Outil tiers d'alignement

Varians exploite les synchronisations mais ne doit pas devenir l'atelier complet qui les construit. Un outil compagnon est prévu pour :

- lire le projet Varians ;
- extraire les lignes TEI du témoin de base ;
- lire les ALTO secondaires ;
- proposer/corriger des correspondances 1↔1, 1↔n, n↔1, absence ;
- produire les JSON `tei-manuscript-alignment` avec `base_keys`.

Préserver cette séparation des responsabilités.

---

## 20. Philosophie d'interface

Varians s'adresse à des éditeurs scientifiques qui doivent pouvoir comprendre ce qui est fait à leur texte.

Principes :

- montrer le XML réel ;
- automatiser les opérations répétitives, pas les décisions philologiques ;
- expliquer les erreurs sans bloquer inutilement la sauvegarde ;
- permettre de commencer avec très peu de ressources puis d'en ajouter ;
- masquer les zones d'interface inutiles lorsqu'une ressource manque ;
- garder une terminologie cohérente entre desktop, viewer web et documentation ;
- préférer un refus explicite à une modification automatique ambiguë.

Le logiciel doit être accueillant pour un nouvel utilisateur sans devenir opaque pour un spécialiste TEI.

---

## 21. Checklist de transmission

Avant de remettre Varians à un nouveau mainteneur, vérifier qu'il a :

- le ZIP complet de la dernière version ;
- ce document ;
- `README.txt` ;
- tous les documents spécialisés `*.md` ;
- les tests ;
- au moins un projet de démonstration fonctionnel ;
- si possible un petit projet réel avec images locales + ALTO + synchronisation pour tests manuels.

Le point de départ conseillé pour comprendre le code est :

1. `project_config.py` ;
2. `resource_state.py` ;
3. `image_sources.py` + `alto_import.py` + `tei_facsimile.py` ;
4. `rng_completion.py` + `relaxng_validation.py` ;
5. `web_viewer/generator.py` ;
6. seulement ensuite `editeur_tei.py`.

Cette progression permet de comprendre le modèle avant l'orchestration Qt.


## Extension Varians 0.8.5 — PAGE XML et copies IIIF

Voir **PAGE_IIIF_LOCAL.md** pour les procédures, les formats ALTO/PAGE mixtes, les copies locales IIIF, les deux cases indépendantes par témoin (éditeur / export), les chemins, le protocole de cache et les limites. Les anciens projets restent lisibles sans migration.


## Note de maintenance V0.8.5.1 — passage ALTO ↔ PAGE PERO OCR

Régression identifiée sur une paire de fichiers ALTO/PAGE produits par PERO
pour la même image manuscrite : les identifiants de ligne diffèrent
(`line_<UUID>` / `id_<UUID>`) alors que leurs suffixes UUID, textes et boîtes
englobantes sont identiques. L'ancien `overlay_alto()` conservait les
synchronisations par **rang**, faute d'égalité littérale des IDs. Une
permutation de deux lignes entraînait un rattachement silencieux erroné.

Dans `alto_import.py`, `_line_uuid()` extrait uniquement un UUID canonique
lorsque l'identifiant complet respecte le motif reconnu. `_merge_lines()`
réserve d'abord les correspondances uniques par ID exact puis UUID, et n'utilise
le repli par rang que pour les autres lignes, sans réutiliser les lignes déjà
réservées et sans relier des UUID manifestement différents. Les anciennes
lignes non reconnues sont conservées pour diagnostic. Ne pas supprimer cette
logique de priorité. Les tests correspondants sont dans
`tests/test_v0851_pero_uuid_migration.py`.

Validation automatisée : **181 tests réussis**. Le contrôle des 39 lignes
ALTO/PAGE sur les exemples réels a été effectué pendant le développement ;
les fichiers de manuscrit sont volontairement **absents** de l'archive.

## Passage de relais V0.8.5.2 — téléchargements IIIF sélectifs et asynchrones

Se reporter à `PAGE_IIIF_LOCAL.md` § 6 pour le contrat de `downloadScope`,
la sélection PAGE/ALTO, le thread Qt, l'atomicité de `index.json` et les tests.
Modules nouveaux : `iiif_selection.py` (rapprochement local conservateur)
et `iiif_download_manager.py` (présentation Qt). Le module `iiif_local.py`
reste le seul point d'accès au téléchargement des images. Le modèle
`WitnessDraft` / `WitnessConfig` stocke `iiif_download_scope` en dernier champ
avec valeur par défaut `all`, pour conserver les constructeurs historiques.
La création du projet ne télécharge plus d'images dans le thread principal.
Après sauvegarde des paramètres, l'éditeur ouvre automatiquement le gestionnaire
et met les images localement récupérées à disposition des panneaux sans
réinitialiser le document TEI.

Conserver **absolument** ces invariants lors de futurs correctifs :
absence d'ALTO/PAGE en mode `ocr` => sélection vide, aucun fallback à `all` ;
aucun rapprochement par simple position ordinale ; pas de réécriture des fichiers
ALTO, PAGE, du TEI ni du manifeste IIIF ; images complètes présentes réutilisées ;
`localCopy` et `webLocalCopy` demeurent indépendantes ; diagnostics explicites pour
les pages sans correspondance ; nettoyage sûr lors du changement de projet.


> **Varians 0.8.5.3** : la sélection explicite des canvases IIIF et leur association aux OCR indépendamment du nom de fichier sont documentées en détail dans [IIIF_CANVAS_SELECTION.md](IIIF_CANVAS_SELECTION.md). Les projets antérieurs conservent le mode implicite `all`. Ne pas confondre le manifeste (catalogue) avec les pages sélectionnées de l’édition.


### 0.8.5.4 — Suggestion automatique IIIF ↔ OCR

Le module `iiif_page_selection.propose_exact_ocr_links()` est indépendant de Qt.
Il utilise exclusivement les noms de base exacts (les extensions et la casse
ne comptent pas) issus des URL/labels IIIF et des métadonnées de PAGE/ALTO,
puis du nom du fichier XML. Il rejette les ambiguïtés et honore les associations
manuelles existantes. `IIIFCanvasPicker` préremplit les liens sûrs sur les
nouvelles sélections et propose une commande pour compléter les champs vides.
Ne jamais remplacer ce contrôle par un appariement ordinal ou approximatif.
Les tests ciblés se trouvent dans `tests/test_v0854_iiif_exact_autolink.py`.


## 0.8.5.5 — Association JSON synchronisé ↔ IIIF

Voir [IIIF_SYNC_RESOLUTION.md](IIIF_SYNC_RESOLUTION.md). Le moteur commun `iiif_resolution.py` associe les identifiants de pages des JSON Varians-Synchro à des Canvas IIIF v2/v3 sans appariement positionnel, en conservant les `base_keys`, les copies de travail et les choix éditoriaux. Les associations manuelles `pageLink` sont sauvegardées dans `project.xml`.


## 0.8.5.6 — Initialisation TEI depuis le témoin pivot

Module `tei_pivot_scaffold.py` (indépendant de Qt) : identification stable des pages éditoriales depuis `project_facsimile_pages`, association sans indice positional aux ALTO/PAGE/JSON, décompte des lignes et génération non destructive des jalons `<pb edRef facs>` et `<lb edRef>` sans zones.

Les dialogues `NewProjectDialog` et `ProjectSettingsDialog` présentent une case de préparation volontaire, la case `<lb/>` activée lorsque la préparation est choisie, et un aperçu avec confirmation et sauvegarde datée. `editeur_tei.py` intervient après la création/sauvegarde des surfaces existantes. Aucune donnée de synchronisation n'est modifiée. Pour des invariants et scénarios détaillés, consulter `TEI_PIVOT_SCAFFOLD.md` et `tests/test_v0856_pivot_scaffold.py`.


## 0.8.5.7 — Affichage des commandes de préparation du pivot

**Correctif purement GUI**, construit sur l'archive complète 0.8.5.6.
Dans `project_dialogs.py`, les choix `pivot_prepare` / `pivot_lines` sont
désormais dans un `QGroupBox` en haut de la création (sous le mode) et
avant la liste des témoins dans les paramètres. `QScrollArea` protège
contre l'écrêtage vertical ; les boutons de validation restent hors de
la zone défilante. Les champs et le modèle de projet ne changent pas.
Le titre visible des dialogues porte le numéro 0.8.5.7 pour faciliter
les diagnostics lorsque Spyder conserve des modules d'une ancienne version.
Pas de modification du moteur `tei_pivot_scaffold.py`.


## Correctif 0.8.5.8 — JSON de pages partielles

Dans `tei_pivot_scaffold.py`, `_synced_line_count()` dénombre les éléments
physiques documentés par `pages[].lines` ; l’intervalle `line=41..68` donne
28 balises `<lb edRef="#Mu"/>` et non 0. Une lacune est signalée, mais ne
provoque jamais la création des numéros absents. Numéros invalides ou doublons
=> aucun `<lb/>` issu du JSON. Les `<lb/>` générés sont sans `@n` et sans
`@facs`; l’association à la page reste portée par `<pb facs="#surface">`.

Les pages du JSON sans ligne ne sont pas exclues si leur `<surface>` appartient
aux images sélectionnées ; si aucune surface ne correspond, avertissement dans
l’aperçu, sans ajout de page fantôme. Les identifiants `base_keys`,
les données JSON et les transcriptions existantes restent intacts.

Tests : `tests/test_v0858_partial_sync_scaffold.py`, plus les tests existants.
Essai graphique sous Windows / PySide6 encore nécessaire.


## V0.8.5.9 — Diagnostic de cadrage aux changements de colonne

Source du correctif : `image_sources.py`, fonctions `_same_physical_page`,
`_adjacent_line_continuity`, `display_window_indices`. L'affichage Qt reste
piloté par `ManuscriptPanel.reload()` puis `crop_for_items()` dans
`editeur_tei.py`. Ne pas remplacer ce garde-fou par une simple fenêtre
`range(center-1, center+2)` : aux changements de colonne, les lignes successives
sur le plan éditorial ne sont pas voisines sur le plan spatial. Les indices JSON
et les synchronisations demeurent intacts. Le correctif fonctionne avec les
rectangles dérivés des polygones PAGE aussi bien qu'avec les rectangles ALTO.

Dans l'attente des essais graphiques sous Windows, vérifier que l'affichage
`16r, ligne 28` ne saute plus au bord de la colonne précédente et que la ligne
ciblée reste correctement encadrée en mode « Cadres ».


### V0.8.5.10 — Cadres et sélection de la ligne réellement synchronisée

Voir `DISPLAY_NAVIGATION.md` pour les invariants et les fonctions pures.
Les modifications de l'affichage sont confinées à `editeur_tei.ManuscriptPanel`
et `image_sources.py`. Les boutons Cadres sont **par témoin**. Orange = vrai
appariement JSON ; bleu = navigation manuelle sur une ligne non appariée.
Le modèle du document et les fichiers de synchronisation ne sont jamais mutés.
La sortie Web affiche actuellement les surlignages comme rectangles, même
si la vue PySide6 prend en charge les polygones PAGE.


## Passation V0.8.5.11 — Navigation mixte pages et lignes
Ne jamais revenir au `if base_alignment_available: ... else: ...` exclusif dans `sync_panels_to_cursor()`. Le suivi page doit être appliqué aux seuls témoins `sync_enabled=False` même en présence d'un pivot synchronisé. Un `pb` d'un témoin ne doit pas déplacer les autres, et aucun `@n` ambigu ne doit provoquer de substitution. Voir `MIXED_NAVIGATION.md` et `tests/test_v08511_mixed_page_line.py`.


## V0.8.5.12 — Navigation par couple de folio, panneaux défilables et vocabulaire

- La colonne des témoins utilise une `QScrollArea` contenant le splitter de
  témoins, sans remplacer les panneaux ni leurs connexions. Le calcul de son
  étendue minimale est dans `witness_layout.py` ; `_update_witness_scroll_extent`
  gère la visibilité des témoins et le mode « agrandir ».
- Les indices de folio restent **locaux à leur témoin** : `@edRef` sélectionne
  l'espace de noms, `@n` identifie la page dans cet espace. `@facs` est
  prioritaire et obligatoire si les libellés d'un même témoin sont ambigus.
  Cette logique existait en V0.8.5.11 ; la présente version la documente et
  la protège par des tests reproduisant plusieurs `@n="3r"` identiques.
- « Manuscrit pivot » indique uniquement l'ancre de synchronisation : il n'est
  pas le « manuscrit de base » au sens philologique. La nouvelle terminologie
  a été appliquée aux chaînes visibles et aux sept aides (`fr/en/de/ja/cs/it/ru`),
  avec une infobulle d'explication dans la sélection du témoin.
- Les champs techniques historiques (`project.base_witness`, `role=base`,
  `base_keys`, `base_alignment_available`) sont volontairement **inchangés**,
  pour éviter toute migration destructrice des sessions et JSON Varians-Synchro.

Tests : `tests/test_v08512_scroll_pivot_name.py` + suite historique ; GUI non
exécutée en l'absence de PySide6 dans l'environnement de validation.

### V0.8.5.13 — Saisie des balises fermantes

L'éditeur source et l'éditeur de fragment héritent de `CodeEditor`.
`xml_tag_pairs.closing_tag_suggestion(text, pos)` calcule, sans Qt, la
fermeture sûre du QName ouvert le plus proche lorsque le texte avant le
curseur finit par `</` suivi d'un éventuel préfixe. Aucun RNG n'est requis.
`QCompleter` affiche le QName suivi de `>` ; `activated[str]` réévalue
systématiquement le contexte avant toute modification pour empêcher une
suggestion périmée. L'éditeur insère le résultat comme une modification
annulable. Les commentaires, CDATA, attributs incomplets et structures
croisées sont volontairement exclus. Ctrl+Espace dans `</...` prend ce chemin
avant celui de RELAX NG. Tests : `tests/test_v08513_xml_closing_completion.py`.


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


### V0.8.5.16 — visibilité et ordre indépendants des panneaux

Voir `DISPLAY_NAVIGATION.md` et `tests/test_v08516_witness_order.py`.
L'ordre du `QSplitter` est une propriété d'interface `witnessOrder` stockée
par projet dans `QSettings`. Il ne faut jamais réordonner `project.witnesses`
ni changer `base_id` pour répondre à une demande d'ordre visuel. Les tailles
sont attachées à chaque sigle et non à son rang ; ne pas recréer les panneaux
lors des mouvements (les états et les signaux seraient perdus).


## V0.8.5.17 — Diagnostic / actualisation

Voir `WITNESS_DIAGNOSTICS.md`. Le module `witness_resource_refresh.py` centralise le rapport indépendant de Qt et la préparation transactionnelle des ressources. L’éditeur conserve sa TEI, sa pile d’annulation et ses panneaux ; il ne commet le rechargement qu’après validation. La synchronisation n’est jamais déduite des seules données ALTO/PAGE.


Varians V0.8.5.18 — Navigation par folios et images doubles
Voir FOLIO_NAVIGATION.md. Une surface peut contenir deux zones de folio ; aucun changement des JSON/ALTO ou des images source.


## Varians V0.8.5.20 — Correction du dialogue « Double page… »

Correctif du dialogue double-page : ne jamais conditionner la capacité à décrire le fac-similé au mode de synchronisation du témoin. Ne pas réinitialiser `center_index`/`base_keys` après création des zones sur un témoin synchronisé. Tests de vraie méthode Qt extraits par AST : `tests/test_v08519_split_dialog.py`.


## Extension 0.8.5.21 : dispositions de travail

Voir [`WORKSPACE_LAYOUT.md`](WORKSPACE_LAYOUT.md). Les vues verticale, horizontale, grille, les fenêtres individuelles et le mode « Toujours au premier plan » ne changent que les préférences d’affichage `QSettings`. Le même `ManuscriptPanel` est transféré entre parents Qt ; `workspace_layout.py` ne contient pas de logique de synchronisation. Le ratio XML/manuscrits est librement redimensionnable, y compris vers 20 % XML.

## V0.8.5.22 — Repliage XML

Nouveau module pur `xml_folding.py` ; prise en charge Qt dans `CodeEditor`, chevrons en marge, trois actions dans le menu Affichage ; refus des balises sur des lignes partagées. Voir `XML_FOLDING.md`.

## V0.8.5.23 — Surlignage bidirectionnel des paires XML

La nouvelle fonction `pair_at_context` est strictement destinée au surlignage et ne change pas les outils de renommage, suppression synchronisée et repliage. Le côté fermeture exige une analyse du préfixe à l’aide d’une pile de QName ; un mismatch entraîne un résultat nul. `CodeEditor.highlightCurrentLine` place deux sélections purement visuelles de même couleur, sans modifier les offsets ni l’historique. Cf. `XML_TAG_HIGHLIGHT.md`. Le moteur de génération d'apparat critique envisagé antérieurement est retiré de la feuille de route.

## Addendum V0.8.5.24 (14 octobre 2026)
Reprendre désormais V0.8.5.24. Géométrie et fenêtre de contexte web : `web_viewer/geometry.js`, embarqué par `web_viewer/generator.py`. Polygones PAGE et bbox de recadrage unifiées avec les scènes du bureau ; limites de colonnes/pages calées sur `display_window_indices`. Tests croisés Python/Node et essai Chromium sans erreur JS ; non testé sur Windows PySide6. Prochains chantiers : IIIF haute résolution et erreurs serveur V0.8.5.25, personnalisation web V0.8.5.26 à discuter, audit V0.8.6. Modèles d’apparat critique explicitement exclus.

## Passation V0.8.5.26
Lire `PASSATION_V0_8_5_26.md`, `WEB_VIEWER_FULLTEXT_SEARCH.md` et `ROADMAP_EN_REDEFINITION.md`. La roadmap 2026-10 précédente est conservée uniquement comme archive historique. Base de travail : 0.8.5.26 ; tous les tests non-Qt doivent passer avant évolution.

## Addendum — V0.8.5.26.2 : diagnostics RELAX NG périmés

Le panneau RNG ne doit jamais afficher le tableau correspondant à une ancienne révision du `QTextDocument`. Les signaux `QPlainTextEdit.textChanged` et `QTextDocument.contentsChanged` aboutissent à `_text_changed`, qui déduplique les événements par numéro de révision Qt, invalide le cache de résultat et efface les lignes du tableau. Dès la première activation du panneau, le contrôle différé fonctionne même si le panneau est masqué. La réouverture vérifie la dernière révision. Le validateur compare les révisions avant publication, y compris après résolution du schéma, qui peut être lente ; il rejette les résultats tardifs. La validation F8 reste explicite et aucun texte XML n'est réécrit. La suite de tests est exécutable hors Qt, mais un essai PySide6 réel sur Windows reste impératif.
