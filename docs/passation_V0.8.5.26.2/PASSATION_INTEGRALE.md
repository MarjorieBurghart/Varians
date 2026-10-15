# VARIANS — DOSSIER DE PASSATION INTÉGRAL DE LA BRANCHE V0.8.5.26.2

**Version majeure de référence : V0.8.5.26.2.**  
**Date de constitution : 15 octobre 2026.**  
**Portée : documentation et transmission, sans modification des sources et sans nouvelle roadmap.**

Cette compilation est faite pour lecture continue. Les versions individuelles de chaque chapitre, l'index des symboles, l'archive originale et les rapports de vérification sont également dans le ZIP complet de passation.

## Table des matières

- [0 — Lire en premier](#chapitre-0--lire-en-premier)
- 01 — Architecture fonctionnelle, composants et flux (`DOCUMENTATION/01_ARCHITECTURE_ET_FLUX.md`)
- 02 — Contrats de données et invariants scientifiques (`DOCUMENTATION/02_FORMATS_ET_INVARIANTS_SCIENTIFIQUES.md`)
- 03 — Édition XML, RELAX NG, complétion et diagnostics (`DOCUMENTATION/03_XML_RELAXNG_COMPLETION.md`)
- 04 — Images, IIIF, ALTO/PAGE, géométrie, double page (`DOCUMENTATION/04_IMAGES_IIIF_ALTO_PAGE_ET_DOUBLE_PAGE.md`)
- 05 — Viewer web : contrat complet, synchronisation, recherche et publication (`DOCUMENTATION/05_VIEWER_WEB_SYNCHRONISATION_RECHERCHE.md`)
- 06 — Procédures de maintenance, vérification et livraison (`DOCUMENTATION/06_TESTS_REPRODUCTION_LIVRAISON.md`)
- 07 — Historique, décisions et incidents à ne pas répéter (`DOCUMENTATION/07_HISTORIQUE_INCIDENTS_ET_REGRESSIONS.md`)
- 08 — Internationalisation, sécurité, performance, portabilité (`DOCUMENTATION/08_I18N_SECURITE_PERFORMANCES_PORTABILITE.md`)
- 09 — Gouvernance de la reprise et feuille de route ouverte (`DOCUMENTATION/09_REPRISE_ROADMAP_RECETTE_ET_CRITERES.md`)
- 10 — Provenance, méthodes de contrôle et portée des preuves (`DOCUMENTATION/10_REGISTRE_CONTROLES_ET_PROVENANCE.md`)
- 11 — Inventaire vérifié du code et des tests (`DOCUMENTATION/11_INDEX_SYMBOLIQUE_ET_TESTS.md`)
- Index des documents historiques contenus dans le ZIP original (`DOCUMENTATION/12_INDEX_DOCUMENTS_HISTORIQUES.md`)

---


# Chapitre 0 — Lire en premier

# Varians — passation majeure de la branche V0.8.5.26.2

**Date de constitution du dossier : 15 octobre 2026.**  
**Base technique unique et immuable : `Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip`.**  
**Nature du présent dossier : documentation et inventaire, sans nouvelle version du logiciel, ni modification de ses sources.**

## Message impératif au développeur repreneur

Varians est un éditeur TEI critique généraliste, particulièrement destiné aux éditions de textes médiévaux. Il réunit un éditeur XML/PySide6, une validation et complétion RELAX NG, un aperçu transformé par XSLT, XPath, des manuscrits-images (locaux ou IIIF), leurs coordonnées OCR ALTO/PAGE, une synchronisation physique intertémoins fournie par des JSON, et un viewer web exportable autonome. **Il ne produit pas automatiquement l'apparat critique**, et il est interdit d'inférer des correspondances entre témoins à partir de la proximité, du numéro de page ou d'un texte ressemblant.

La V0.8.5.26.2 constitue la **version de référence fonctionnelle désormais acceptée par l'utilisateur**, après vérifications de l'interface web, de la complétion XML et du correctif du panneau RELAX NG en pratique. Les 479 tests Python passés (2 ignorés) et le contrôle SHA-256 des sources ont également été reproduits indépendamment lors de la préparation de cette passation. Voir toutefois les limites de validation graphique et de corpus réel détaillées dans les rapports.

**La précédente feuille de route est abandonnée/suspendue**. Ne pas réactiver automatiquement les chantiers anciennement annoncés comme V0.8.5.26 XSLT/CSS, V0.8.6 audit, ou les assistants d'apparat. Une nouvelle feuille de route sera discutée avec l'utilisateur ; les documents historiques ne sont pas des commandes de développement.

## Contenu du paquet

- `BASE_SOURCE/` : **ZIP complet original V0.8.5.26.2 non modifié**, plus son empreinte.
- `DOCUMENTATION/` : dix dossiers techniques rédigés pour la reprise, articulés de l'architecture à la recette.
- `DOCUMENTATION/11_INDEX_SYMBOLIQUE_ET_TESTS.md` : index des symboles et des tests généré par analyse des vrais fichiers.
- `VERIFICATION/` : sortie pytest indépendante, rapports d'empreintes, manifeste et procédure de contrôle.
- `PASSATION_INTEGRALE.md` : compilation des documents thématiques, destinée à une lecture continue.

**Ordre de lecture recommandé :** 01 architecture → 02 formats et intégrité → 03 édition et validation → 04 images et géométrie → 05 export web et synchronisation → 06 maintenance/test → 07 incidents → 08 i18n/sécurité → 09 stratégie de reprise. L'index 11 permet ensuite de retrouver rapidement le code.

## Reprise rapide et reproductible

```bash
python -m venv .venv
# Activer le venv selon son système
python -m pip install -r requirements.txt
python -m pip install pytest
python -m pytest -q --disable-warnings
python -m compileall -q .
python editeur_tei.py
# Ou : python editeur_tei.py /chemin/vers/project.xml
python -m web_viewer.generator project.xml
```

Exécuter les commandes **à la racine des sources extraites**, non dans le dossier documentaire. `PySide6` est requis pour l'application graphique ; `lxml` pour les schémas/XSLT ; `pytest` est une dépendance de développement. Les fichiers `.bat` fournis historiquement sont des commodités Windows, pas une dépendance de l'architecture.

## Invariants non négociables

1. **TEI éditoriale et données sources intouchées** par les réglages de vue et de publication ; sauvegarde et modifications scientifiques toujours explicites.
2. **Témoin pivot technique ≠ leçon de base philologique**. La clé physique canonique est `page_id::line` du JSON du pivot ; le secondaire n'est synchronisé que via ses `base_keys` vérifiables.
3. **Images ≠ géométrie OCR ≠ synchronisation** : ces couches sont indépendantes, facultatives et ne prouvent rien l'une sur l'autre.
4. **Parité obligatoire entre desktop et web sur les `<lb/>`** : l'ordre global des jalons pivot suit l'ordre réel des lignes du JSON pivot, et non une numérotation réinventée à chaque `<pb/>`.
5. **Polygones PAGE intacts**, coordonnées indépendantes des bitmaps d'aperçu, une image peut contenir deux parties avec deux `<zone>` TEI.
6. **Préférences locales dans QSettings**, format scientifique dans `project.xml` ; respecter ordre/visibilité de la vue à l'export depuis l'interface.
7. **Sept langues et sept aides** : fr, en, de, ja, cs, it, ru ; ajouter ou corriger les traductions dans leur contexte réel.
8. **Aucune affirmation de vérification graphique native** sans avoir effectivement exécuté PySide6 sur le système concerné.
9. Une version livrée = **archive complète**, tests et documentation mis à jour, bilan d'intégrité et liens réellement vérifiés.

## Hiérarchie des autorités en cas de contradiction

1. **Code et données effectifs du ZIP V0.8.5.26.2**.
2. Tests portant sur ce code et leur exécution indépendante.
3. Addenda de passation les plus récents (`PASSATION_V0_8_5_26_2.md`, etc.).
4. Contrats thématiques historiques, utiles mais parfois antérieurs à un correctif.
5. Suggestions d'anciennes roadmaps : *non actives*.

Des fichiers comme `CODE_MAP.md` portent encore dans leur titre des numéros anciens : ils sont historiquement cumulatifs. Ne pas confondre titre initial et état de la distribution.


---

# 01 — Architecture fonctionnelle, composants et flux

## 1. Système et philosophie

Varians est une application **Python 3 / PySide6 (Qt 6)**, complétée par `lxml` pour RELAX NG, XPath et transformations XSLT. Les modules indépendants de Qt portent progressivement la logique scientifique, afin de rester testables sans interface. La cible est **Windows, Linux et macOS** ; le poste usuel de validation utilisateur est Windows (parfois Spyder), mais aucun chemin absolu Windows ne doit entrer dans les modules cœur.

La racine `editeur_tei.py` demeure un contrôleur UI volumineux (voir l'index symbolique pour sa taille exacte). **Ne pas refondre en bloc ce fichier** : le séparer progressivement avec tests d'invariants et vérification des instances Qt. `web_viewer/generator.py` construit les données du viewer, `web_viewer/legacy_v11_core.py` extrait la lecture à partir de la TEI, et plusieurs scripts JS autonomes sont incorporés dans `viewer.html` au moment de sa génération. Le viewer ne réutilise **pas automatiquement** la feuille XSLT de l'aperçu interne.

## 2. Architecture en couches

```text
project.xml  --project_config.py--> ProjectConfig / WitnessConfig
    |                           |                 |
    |                           |             QSettings (vue locale seulement)
    v                           v
TEI source <---- MainWindow / CodeEditor ----> panneau RELAX NG / RNG / XPath
    |                     |                    (schema_resolution.py,
    |                     |                     relaxng_validation.py,
    |                     |                     rng_completion.py)
    |                     v
    |                ManuscriptPanel[]  <--- image_sources.py / iiif_* / alto_import.py
    |                     ^
    |                     |
    |             JSON sync du pivot + secondaires
    |
    +------> web_viewer/generator.py
                      |-- tei_line_anchors.py / page_resolver.py
                      |-- legacy_v11_core.py : lecture structurée
                      |-- geometry.js : repères et crop
                      |-- iiif.js : plan des images et replis
                      |-- fulltext_search.js : texte, offsets, équivalences
                      '--> web_output/viewer.html + images locales embarquées
```

Chaque bloc opère sur des ressources qui peuvent être absentes. Une image n'implique pas un OCR, un OCR n'implique pas des `base_keys`, et des balises TEI n'impliquent pas une image publiable.

## 3. Responsabilités de modules (principaux)

| Domaine | Modules | Points de contrôle |
|---|---|---|
| Interface XML | `editeur_tei.py` (`CodeEditor`, `MainWindow`) | selection, undo/redo, texte source inchangé lors des vues |
| Panneaux images | `editeur_tei.py` (`ManuscriptPanel`, `DetachedWitnessWindow`) | mêmes instances et zoom après réorganisation |
| Projets | `project_config.py`, `project_management.py`, `project_dialogs.py` | chemins relatifs, schéma, témoins facultatifs, rétrocompatibilité |
| Sauvegardes | `save_io.py` | écriture atomique, `.bak` |
| État scientifique d'alignement | `resource_state.py`, `witness_resource_refresh.py` | JSON brut, actualisation transactionnelle |
| ALTO/PAGE | `alto_import.py` | coordonnées et polygones non dégradés |
| IIIF et images | `image_sources.py`, `iiif_manifest.py`, `iiif_resolution.py`, `iiif_selection.py`, `iiif_local.py`, `iiif_download_manager.py` | Canvas exact, copies indexées, pas d'association par simple position |
| TEI fac-similé | `tei_facsimile.py`, `folio_navigation.py`, `tei_pivot_scaffold.py` | surface, graphic, zones et `pb/@facs` |
| XML et schema | `xml_tag_pairs.py`, `xml_folding.py`, `rng_completion.py`, `schema_resolution.py`, `relaxng_validation.py`, `custom_completion.py` | contexte lexical et absence de suggestion incertaine |
| Aperçu interne | `selection_sync.py`, `tei_formatter.py`, XSLT et CSS dans `rendering/` | `xml:space`, `<lb break="no"/>`, édition inchangée |
| Export web | `web_viewer/*` | clés physiques, visibilité, images et HTML autonome |
| Langues | `i18n.py`, `i18n/*.xml`, `help/*.html` | sept variantes cohérentes |

## 4. Entrée et démarrage

`editeur_tei.py::main()` initialise l'application, la fenêtre de bienvenue ou le dernier projet selon QSettings. Il est possible de lancer directement `python editeur_tei.py project.xml`. L'édition du projet d'exemple, T1/T2/P, n'est **pas** celle des manuscrits réels Mu/F/A/N/L de l'utilisateur.

Les chemins absolus ne sont admis dans les projets anciens que pour la compatibilité ; les nouveaux projets doivent privilégier les chemins relatifs, résolus par `project_config.py`. Ne pas créer de migration automatique destructive.

## 5. Cycle d'un projet et sources de vérité

1. `project_config.load_project` lit la configuration et identifie le pivot par ID.
2. Le chargement assemble les caches JSON, les images et la géométrie ALTO/PAGE **sans ajouter des liaisons intertémoins non établies**.
3. Les ressources IIIF sont résolues à partir des preuves explicites disponibles (service, Canvas, liens choisis, libellé exact unique, index local).
4. L'éditeur conserve une liste ordonnée de lignes physiques du pivot (`flatten_primary`). Les `<lb edRef="#pivot"/>` sont liés à cette liste par **leur ordinal source global**.
5. Les témoins secondaires utilisent leurs véritables `base_keys`; le contrôleur décide ligne ou page selon l'état effectif et la disponibilité du pivot.
6. Le viewer exporte ces mêmes contrats et les images qui sont publiables ; le texte enrichi reste relié aux mêmes clés.

## 6. Affichage desktop et préférences

Depuis la V0.8.5.21, l'interface prévoit pile verticale, panneaux horizontaux, grille deux colonnes et fenêtres détachées. `workspace_layout.py` normalise les décisions, tandis que `MainWindow._apply_witness_panel_order` réorganise les **mêmes objets `ManuscriptPanel`**. La liste et l'ordre des témoins sont stockés dans `QSettings` par chemin de projet ; ils ne changent pas l'ordre scientifique de `ProjectConfig.witnesses`.

La génération web déclenchée par l'interface utilise `self._witness_display_order` filtré par `self._visible_witness_ids`. Le générateur Python en CLI, qui n'a pas l'état Qt courant, prend tous les témoins en ordre de projet lorsque `display_witness_ids=None`. Le pivot masqué demeure un index technique sans panneau affiché.

## 7. Les changements qui appellent plusieurs modules

- Une modification du contrat de clé `page_id::line` touche l'éditeur, `resource_state`, l'indexeur TEI, le JSON et le viewer : **interdire un correctif isolé à un seul niveau**.
- Un changement du recadrage ou d'IIIF doit préserver les sommets PAGE, la géométrie des zones TEI et le choix de colonnes ; vérifier Python **et** JavaScript.
- Un changement de l'apparence ou de l'ordre des panneaux doit préserver `QSettings`, la synchronisation du pivot caché et le mode page des témoins non alignés.
- Un changement du panneau RELAX NG doit invalider les diagnostics obsolètes sans réécrire ni le RNG ni la TEI et sans dégrader Ctrl+S ou F8.

## 8. Dette et arbitrages

- `editeur_tei.py` et `web_viewer/legacy_v11_core.py` restent de gros fichiers historiques : refactorings *uniquement* avec tests de caractérisation d'abord.
- L'interface native Qt n'est pas intégralement couverte par des tests end-to-end multiplateformes.
- Le viewer dépend parfois de serveurs IIIF distants : un HTML autonome ne garantit pas un accès hors ligne aux images.
- Les esquisses historiques de personnalisation XSLT/CSS et d'audit de projet restent de la **documentation de conception**, pas un engagement de développement.


---

# 02 — Contrats de données et invariants scientifiques

## 1. Séparation scientifique des notions

**TEI** = édition et balisage intellectuels. **Images** = fac-similés. **ALTO/PAGE XML** = repérage et géométrie d'OCR/HTR. **JSON de synchronisation** = correspondances physiques validées, préparées notamment par le logiciel distinct Varians-Synchro. Ces quatre couches ne sont ni substituables ni obligatoirement présentes ensemble.

Le *témoin pivot* du logiciel est un index technique de synchronisation ; le choix d'un lemme ou d'une édition de base relève d'une autre opération éditoriale. Ne pas implémenter d'assistant de génération d'apparat critique, expressément écarté lors de la feuille de route antérieure et non réactivé.

## 2. Projet et chemins

La racine XML du projet est `<teiManuscriptProject>` (ou `<project>` historique). Exemple documentaire, à adapter aux témoins effectifs :

```xml
<teiManuscriptProject version="1">
  <title>Mon édition</title>
  <edition file="xml/edition.xml"/>
  <schema type="relaxng" source="xml-model"/>
  <interface language="fr" translationsDir="i18n" fallbackLanguage="en"/>
  <rendering xsltMode="builtin" css="rendering/tei.css" customElements="rendering/custom-elements.xml"/>
  <webViewer outputDir="web_output" filename="viewer.html"/>
  <witnesses base="Mu">
    <witness id="Mu" role="base" label="Manuscrit pivot" alignment="alignments/Mu.json"/>
    <witness id="F" label="Secondaire F" alignment="alignments/F.json"/>
    <witness id="N" label="Non synchronisé"/>
  </witnesses>
</teiManuscriptProject>
```

L'exemple n'est pas un schéma exhaustif : les sources image et ALTO, la sélection IIIF et les associations éditoriales possèdent d'autres attributs/éléments décrits dans `PROJECT_MANAGEMENT.md`, `PAGE_IIIF_LOCAL.md`, `IIIF_CANVAS_SELECTION.md` et dans `project_config.py` (autorité). L'absence d'`alignment` est permise.

`schema/@source` : `xml-model` (détection dans la TEI), `project`/fichier explicite, `none` (validation désactivée). Les anciens projets sans `xsltMode` sont lus en mode `file` pour compatibilité. L'XSLT interne et ses paramètres **ne pilotent pas automatiquement le viewer web**.

## 3. JSON d'alignement

Racine typique :

```json
{"meta":{"format":"tei-manuscript-alignment","format_version":1,
         "witness":"F","base_witness":"Mu","role":"secondary"},
 "pages":[{"id":"physical-A","alto_width":2500,"alto_height":3500,
           "lines":[{"line":18,"order":154,
                     "bbox":{"hpos":110,"vpos":240,"width":790,"height":78},
                     "base_keys":["physical-Mu::9"]}]}]}
```

Clé du pivot = **`page['id'] + '::' + line['line']`**. Une ligne secondaire peut référencer zéro, une ou plusieurs clés, et plusieurs lignes secondaires peuvent pointer vers la même clé. `base_keys` est le champ moderne ; `keys816` est accepté **en lecture seulement**. `meta.base_witness` et `meta.role` décrivent une intention/identité, pas la preuve du lien. L'ancien champ `editorial_tei_alignment` n'est pas un substitut aux clés physiques.

Une page peut avoir `image` de type `file`, `iiif`, `none` ou un bloc IIIF historique, ainsi que des coordonnées `bbox` et `polygon`. Une image absente n'annule pas nécessairement les coordonnées OCR.

## 4. Condition d'activation du mode lignes

- Pivot : fichier JSON de synchronisation présent et **lignes physiques utilisables dans le JSON brut**, avec `page.id` et `line`.
- Secondaire : pivot effectivement actif + JSON secondaire présent + clés `base_keys`/`keys816` résolubles vers des **lignes réellement publiées** du pivot (la chaîne web vérifie explicitement la résolution).
- ALTO importé séparément et cadres visibles **ne suffisent jamais** à activer la navigation synchronisée.
- Témoin sans clés vérifiables = mode pages, sans interpolation et sans faux lien.

Voir `resource_state.py`, puis `web_viewer/generator.py` pour ses contrôles supplémentaires de clés publiées. Certains contrôles intermédiaires comptent les liens présents avant la résolution définitive ; ne pas présenter un simple compteur de `base_keys` comme une preuve d'intégrité complète.

## 5. Correspondance `<lb/>` — JSON pivot — secondaires

Contrat majeur stabilisé en V0.8.5.25.3 : **le n-ième `<lb edRef="#Mu"/>` pertinent de la source XML reçoit la clé de la n-ième ligne physique chargée du JSON pivot, dans l'ordre du cache physique**. Les numéros `line` peuvent être non consécutifs, les identifiants physiques ne correspondent pas forcément à `pb/@n`, et une image double peut être pointée par deux `<pb/>` éditoriaux.

**Interdit :** compter les `<lb/>` depuis 1 à chaque `<pb/>` puis construire de nouvelles chaînes `page_id::numéro`. **Interdit :** supprimer des lignes physiques du pivot parce qu'une page TEI ne possède pas de `@facs` résoluble. Ne pas déduire de liens pour une ligne supplémentaire ; signaler explicitement les écarts.

`web_viewer/tei_line_anchors.py` établit cet index, `legacy_v11_core.py` l'utilise dans la lecture et `generator.py` le répercute dans les données publiées. Le diagnostic `meta.pivot_lb_index` renseigne le nombre de `<lb/>` vus, les lignes physiques, liaisons et écarts. La navigation du viewer s'appuie sur les `data-line` réellement publiés.

## 6. Double page, TEI et zones

Une image double = **une `<surface>` + un seul `<graphic>`**, avec deux zones distinctes `-left` et `-right`, pointées par des `<pb facs="#zone-id"/>`. Les zones sont en pixels **source**, et non dans le repère OCR. Le contrôle de décision de partie en mode lignes tient compte de la géométrie et n'infère pas une partie lorsque la ligne chevauche la séparation ; le seuil historique documenté est 85 % dans une partie et 15 % au plus dans l'autre (vérifier `folio_navigation.py` avant toute modification).

La mise à jour de la séparation doit préserver les IDs, les `<pb/>` existants et les autres zones annotées. La terminologie de l'interface est « partie gauche » / « partie droite », non « page recto/verso » imposée.

## 7. Repères PAGE/ALTO

Le `bbox` et les sommets d'un polygone PAGE ne sont pas interchangeables : le rectangle sert à l'indexation/au crop, mais un contour concave doit conserver ses sommets et leur ordre. Une bbox historique peut ne pas enclore tous les sommets ; l'union avec les sommets est alors nécessaire.

Repère OCR `(W_ocr,H_ocr)` → image `(W_img,H_img)` :

`x_img = x_ocr × W_img/W_ocr` ; `y_img = y_ocr × H_img/H_ocr`.

Le crop est exprimé en pixels source image ; les coordonnées des zones TEI sont déjà des coordonnées source et ne doivent donc **pas** être multipliées une seconde fois. Les bitmaps d'aperçu à basse définition changent l'échelle de dessin, pas le repère physique des lignes. Les voisins affichés doivent rester dans la même page et la même colonne physiques.

## 8. Données réelles et cas diagnostiqués

Les rapports historiques utilisateur sur Mu/F/A/N/L ont montré qu'un export HTML *ancien* contenait des clés texte orphelines et une portion du pivot supprimée ; après régénération réelle avec V0.8.5.25.3, l'index était redevenu cohérent. Ce fait ne prouve pas l'absence de problèmes futurs : **tout test de régression doit vérifier la version effective du générateur et le `viewer.html` régénéré**, et non un ancien fichier HTML resté sur disque.

Un diagnostic historique a aussi signalé le folio `BSB Clm 14713 4v` de Mu avec `image.type=none` ; l'utilisateur a confirmé qu'il s'agissait d'un problème de données et **non d'un bug du viewer**. Des références secondaires à une clé supprimée ont été envisagées après suppression d'une ligne vide ; ne pas les corriger sans inspection des clés exactes. Les nombres de ces rapports ne décrivent pas nécessairement l'état actuel du projet de l'utilisateur.

## 9. Conservation des données

Ne jamais modifier silencieusement la TEI, les JSON, la structure des images, les sources OCR ou les références de folios lors de l'export, du diagnostic, de la navigation ou de la disposition des fenêtres. Éviter la réécriture non sollicitée de chemins absolus historiques. Les fonctions d'audit doivent, si elles voient le jour, être en lecture seule ; l'ancienne roadmap sur ce sujet est suspendue.


---

# 03 — Édition XML, RELAX NG, complétion et diagnostics

## 1. Modules et mécanismes

- `editeur_tei.py::CodeEditor` : composant Qt du texte source, coloration, suggestions, paires, repliage et opérations interactives.
- `editeur_tei.py::MainWindow` : orchestration des panneaux, de F8, de la résolution du schéma, des timers et des actions de sauvegarde.
- `schema_resolution.py` : politique du schéma du projet et `<?xml-model?>` ; résolution des ressources, cache.
- `relaxng_validation.py` : lxml, chargement et validation du RNG, données d'erreurs structurées et cache de schémas.
- `rng_completion.py` : modèle des éléments/attributs/valeurs permis selon la position du curseur et la structure RELAX NG, avec traitements de cas partiellement saisis.
- `custom_completion.py` : extensions de complétion par règles de projet, sans déroger au contrat scientifique du document.
- `xml_tag_pairs.py` : fermeture suggérée, appariement lexical prudent, renommage couplé et mise en évidence dans les deux sens.
- `xml_folding.py` : repliage des blocs visuels sans suppression de caractères dans la TEI.
- `xpath_search.py`, `selection_sync.py`, `tei_formatter.py` : requêtes XPath, liens aperçu/texte et formatage à espaces significatifs protégés.

## 2. Contrat A01 dans V0.8.5.26.2 : cycle des erreurs RNG

Le bogue observé en production : des erreurs déjà corrigées réapparaissaient dans la liste de validation. Le correctif ne consiste **pas** à éliminer des messages ressemblant aux anciens : il invalide les résultats par **révision exacte de `QTextDocument`**.

**Séquence d'exécution :**

1. Un changement du document Qt survient (saisie, `QTextCursor`, annuler/refaire). Les notifications du widget et du document sont dédupliquées par `_last_processed_edit_revision`.
2. `MainWindow._text_changed` marque le travail modifié, invalide le résultat RNG et sa révision, efface immédiatement les lignes du panneau et affiche un état « résultats périmés ».
3. Si la surveillance a été activée par un premier passage au panneau, `rng_refresh_timer` démarre pour **1 250 ms**. Le timer ne dépend plus de la visibilité au moment du changement : l'utilisateur peut être dans XPath ou avoir masqué le panneau.
4. `MainWindow._auto_refresh_rng` revalide la révision courante, sans relancer lorsque le cache concerne déjà celle-ci.
5. `validate_relaxng_document` est protégé contre les appels récursifs par `_rng_validation_in_progress`, puis délègue à `_validate_relaxng_document_impl`.
6. Après résolution du schéma **et après** validation lxml, le code revérifie `revision == editor.document().revision()`. Si la révision a changé entretemps, **le résultat est rejeté**, et un nouveau contrôle est planifié (court délai de rattrapage).
7. Seuls les résultats à jour renseignent `_last_rng_result`, `_last_rng_revision`, `_last_rng_schema_token`, le résumé et le tableau. En cas de document valide, le tableau est vidé et l'état approprié affiché.
8. `show_validation_panel` réactive la surveillance et déclenche immédiatement une validation si la révision n'est pas à jour ; F8 reste le déclencheur manuel et `refresh_schema_cache` recharge volontairement les données de schéma.

**Ne pas régresser** sur la distinction entre résultat « invalide », schéma introuvable/invalide, `lxml` absent, absence de `xml-model`, validation désactivée, XML mal formé et document XML valide mais non conforme au RNG. Tous ces cas disposent de messages et de changements d'état propres.

## 3. Contrat A02 : complétion d'attributs pendant la frappe

Lorsqu'un curseur se trouve dans le **tag ouvrant d'un élément**, la frappe initiale d'un nom d'attribut peut proposer les attributs autorisés par le RNG, filtrés selon le préfixe saisi. Exemple : `<rdg wi` → `wit` si autorisé. L'insertion peut produire `wit=""` avec curseur entre les guillemets. Les suggestions prennent en compte l'élément/contexte, les attributs déjà présents, les préfixes XML et l'état syntaxique partiellement saisi.

`Ctrl+Espace` doit rester un moyen volontaire de demander la complétion contextuelle, et la liste des éléments ne doit **pas** être proposée lorsqu'on est au milieu des attributs d'un tag ouvrant. Les valeurs à listes finies restent un cas distinct des **noms d'attributs**. Ne pas confondre la simple autocomplétion lexicale et l'autorisation réelle par RELAX NG.

Les règles métier du schéma et les extensions projet peuvent être compilées/mémorisées dans le cache ; le changement de schéma ou d'entité importante doit invalider leur contexte. Pour document temporairement mal formé, la complétion reste conservatrice : éviter de supposer un parent ou un attribut non démontré.

## 4. Syntaxe et sécurité XML

- Balises ouvrantes et fermantes homonymes imbriquées : l'appariement repose sur une analyse lexicale prudente, pas sur la première sous-chaîne homonyme rencontrée.
- Commentaires, CDATA, préfixes, autofermantes, tags croisés et balises provisoirement incomplètes exigent la prudence. **Ne pas surligner une correspondance incertaine.**
- Le surlignage est un effet visuel `ExtraSelection`, jamais une modification du texte ou une sélection réelle de plage.
- Le repliage masque des `QTextBlock` mais laisse les caractères intacts. Toute navigation/recherche vers une ligne masquée doit la rendre visible.
- Le formatage doit préserver `xml:space="preserve"`, la sémantique de `<lb break="no"/>` et les espaces significatifs ; éviter la normalisation XML destructrice.
- `xml-model` et schéma explicite possèdent des règles de compatibilité : consulter `RELAXNG_VALIDATION.md`, `RNG_COMPLETION.md`, `PROJECT_MANAGEMENT.md`, et la source comme autorité finale.

## 5. Tests reproductibles

```bash
python -m pytest -q tests/test_v085262_rng_panel_refresh.py
python -m pytest -q tests/test_v08526_interim_features.py
python -m pytest -q tests/test_rng_completion.py tests/test_rng_context_cache.py
python -m pytest -q tests/test_relaxng_validation.py
python -m pytest -q tests/test_v08523_bidirectional_tag_highlight.py tests/test_v08522_xml_folding.py
```

Les tests de cycle V0.8.5.26.2 instrumentent les méthodes réellement présentes dans `editeur_tei.py`, mais utilisent des doublures pour les objets Qt ; **ils ne prouvent pas l'ergonomie native PySide6**. Le retour utilisateur après installation a confirmé que la réapparition des anciennes erreurs *semblait* résolue. Ne transformer ni cette observation ni les tests simulés en garantie universelle.

## 6. Matrice manuelle de réception Windows

1. Introduire une erreur RNG, F8, vérifier message et position.
2. Corriger **panneau ouvert** ; vérifier suppression et validation après l'inactivité.
3. Introduire une erreur, F8, passer dans XPath ou masquer ; corriger ; rouvrir : aucune ancienne erreur.
4. Faire annuler/refaire, puis corriger plusieurs erreurs en succession rapide ; vérifier la bonne révision finale.
5. Modifier le document pendant une résolution de schéma lente ; aucun ancien résultat ne doit réapparaître.
6. Changer de projet, changer de politique de schéma, revenir : aucune erreur d'un projet précédent.
7. Dans `<rdg wi`, vérifier que `wit` apparaît, que `Ctrl+Espace` reste opérant et que l'éditeur ne propose pas les éléments enfants comme attributs.
8. Tester les préfixes `xml:`, les doublons d'attribut, les guillemets, les valeurs énumérées, un schéma absent et un XML temporairement incomplet.

## 7. Risques de changement

Ne pas réintroduire la dépendance « validation automatique seulement quand `validation_panel.isVisible()` ». Ne pas publier de résultat lxml sans vérification de `QTextDocument.revision()`. Ne pas invalider la pile d'annulation, déplacer le curseur ni réécrire le document pendant une validation. Toute optimisation de debounce ou de cache exige au moins un test de concurrence logique révision N→N+1→N+2.


---

# 04 — Images, IIIF, ALTO/PAGE, géométrie, double page

## 1. Trois ressources indépendantes par témoin

1. La source d'image peut être absente (`none`), locale ou fournie par un manifeste/service IIIF.
2. La géométrie ALTO/PAGE peut venir d'un JSON de synchronisation ou de fichiers OCR externes indépendants.
3. La correspondance au pivot exige un JSON possédant de véritables `base_keys`, jamais la simple existence d'ALTO/PAGE.

Tout nouvel import doit préserver une image IIIF sélectionnée lorsque l'ALTO ajouté n'a pas pu être associé à son Canvas. Les pages OCR orphelines figurent dans `unassociated_layout_pages`, sans remplacer une image canonique par un objet vide.

## 2. Modules et trajets des données

- `alto_import.py` : lecture ALTO/PAGE, positions OCR, lignes, identifiants et polygones ; acceptation des sources indépendantes.
- `iiif_manifest.py` : lecture des manifestes Presentation API v2/v3.
- `iiif_selection.py`, `iiif_page_selection.py` : décisions de sélection des images et rapprochements sûrs.
- `iiif_resolution.py` : association déterministe Canvas↔OCR/JSON, via identifiant service/image explicite, `ocrLink`/`pageLink` choisi, libellé exact unique ou index local sûr ; **jamais** par le rang dans une liste.
- `iiif_local.py` : copies IIIF locales indexées, gestion scope all/ocr ; `iiif_download_manager.py` : interface et opérations asynchrones.
- `image_sources.py` : politiques d'image, repères d'origine, crop, limites de colonne/page et résolutions.
- `tei_facsimile.py` et `folio_navigation.py` : liens `<surface>/<graphic>/<zone>/<pb>` et doubles pages ; validation du côté à partir de la géométrie.
- `editeur_tei.py::ManuscriptPanel` : rendu graphique PySide6.
- `web_viewer/geometry.js`, `iiif.js` : rendu de navigateur, crop et politiques de téléchargement.

## 3. Coordonnées : formule et repères

| Repère | Dimension habituelle | Utilisation |
|---|---|---|
| OCR ALTO/PAGE | `alto_width`, `alto_height` | Bbox, sommets du polygone |
| Image source / Canvas | `image.width`, `image.height` | Zones TEI, crop, requête IIIF |
| Bitmap reçu | parfois beaucoup plus petit | affichage et scaling seulement |
| Viewbox/crop | pixels source image | position des contours et fenêtres de lignes |

Si la taille OCR diffère de la taille image, appliquer chaque composante `x × W_img/W_ocr`, `y × H_img/H_ocr`. **Ne jamais transformer une zone TEI déjà exprimée en pixels source**. Une vignette IIIF 490 px ne doit ni déplacer les cadres ni faire grossir arbitrairement la scène.

Le recadrage du viewer retient la ligne courante et, au plus, ses voisines physiques autorisées **sur la même page et dans la même colonne**, avec marge source documentée de **24 pixels** puis bornage à l'image. Une forme PAGE concave reste un polygone SVG ayant tous ses sommets, pas son rectangle minimal.

## 4. Double page et liens TEI

Une `<surface>` correspond à **une seule image**, même si elle comprend deux zones `-left` et `-right`. Un `<pb>` éditorial peut pointer vers la gauche et un autre vers la droite (`@facs`). Deux `<pb>` pour la même image ne doivent **jamais** entraîner une remise à zéro des lignes physiques du pivot.

Le dialogue « Double page… » reste accessible même en mode lignes, affiche une vignette de **l'image entière** et autorise le déplacement d'une barre de séparation. Les zones sont mises à jour de façon sûre sans suppression des autres annotations ni changement des `xml:id` pointés par des `<pb/>` existants.

La partie pertinente n'est pas devinée lorsque la ligne chevauche la séparation ou ne possède pas une géométrie claire ; la politique historique de décision impose au moins 85 % dans la partie retenue et au plus 15 % dans l'autre. Sinon, demander un choix explicite.

## 5. IIIF dans le viewer web

`web_viewer/iiif.js` est incorporé au HTML par le générateur :

- support du format de requête Image API v1/v2/v3 et de la différence `full` / `max` pour l'image entière ;
- demande de région dimensionnée selon le crop et la densité d'affichage, avec limites annoncées par la source/le `info.json` quand disponibles ;
- repli sur région plus légère, image entière recadrée localement, puis vignette ;
- gestion des erreurs 403/404/429/5xx et réseau lent, timeout et abandon des requêtes obsolètes ;
- le PNG/JPEG exporté localement est distinct de l'URL IIIF distante ; une page HTML autonome ne garantit pas la disponibilité des serveurs, des licences et des contrôles d'accès.

**Sécurité/réalisme :** une ressource distante n'est pas implicitement embarquée ni utilisable hors ligne. L'export doit signaler les images IIIF externes et les copies locales effectivement présentes. La suppression de ressources anciennes dans le répertoire de sortie n'est **pas automatique** ; privilégier un répertoire propre si l'on doit diffuser seulement une sélection de témoins.

## 6. Test matrix géométrique minimale

- ALTO rectangulaire et PAGE concave à six sommets, même page/image.
- Rapport OCR/image de 1:2, vignette très basse résolution, zoom fort.
- Ligne au bord d'une colonne avec une ligne voisine physiquement proche dans une autre colonne : celle-ci **ne doit pas** être incluse dans le crop.
- Double page : deux zones d'une seule image, `<pb>` vers chacune, marge de séparation ambiguë.
- Canvas IIIF connu mais OCR non lié : image maintenue, OCR orphelin signalé.
- Images uniquement, sans OCR ou JSON : navigation page préservée.
- JSON secondaire sans `base_keys` : mode pages malgré contours OCR.
- Service IIIF v2/v3 : région réussie ; région 429/403 puis image entière ; échec général et vignette ; bascule rapide de témoin sans image ancienne dans le nouveau panneau.

Tests associés : `tests/test_v08524_web_geometry.py`, `test_v08525_iiif_web.py`, `test_v08514_iiif_alto_independence.py`, `test_v08518_folio_navigation.py`, `test_v08520_double_page_parts.py`, `test_v0859_column_crop.py`, `test_v085_page_iiif_local.py`. Les scripts `tests/manual_v08524_chromium.py`, `manual_v08525_iiif_chromium.py`, etc. servent de scénarios navigateur synthétiques mais ne remplacent pas l'essai sur vrais manuscrits et vrais serveurs.

## 7. Limites historiques connues

Les services IIIF d'institutions peuvent être indisponibles, filtrer les requêtes, refuser CORS ou le recadrage, ou limiter les dimensions. Une panne Gallica/IRHT n'est pas automatiquement un problème Varians. Les effets exacts du gestionnaire natif de fenêtres détachées et de la superposition des cadres doivent encore être validés sur les systèmes cibles selon le contexte d'usage.


---

# 05 — Viewer web : contrat complet, synchronisation, recherche et publication

## 1. Fonction et artefacts

Le viewer web est généré depuis le projet par `web_viewer/generator.py`; son point d'entrée `generate(project_path, output=None, *, display_witness_ids=None)` appelle `load_project`, `build_dataset`, `package_local_images`, `make_html`, puis écrit `viewer.html` en UTF-8. Le HTML intègre des scripts JS de production `geometry.js`, `iiif.js` et `fulltext_search.js` ainsi que ses données JSON. `legacy_v11_core.py` extrait la lecture TEI et les références éditoriales.

Commande autonome :

```bash
python -m web_viewer.generator project.xml
```

Depuis `MainWindow.generate_web_viewer`, l'éditeur vérifie que l'édition courante correspond au projet, sauvegarde les modifications utiles puis transmet `display_witness_ids` d'après l'ordre et la visibilité **effectifs** des panneaux. L'export autonome CLI sans cette liste reprend tous les témoins de la configuration scientifique.

## 2. Format conceptuel des données exportées

Le jeu de données inclut :

- `meta` : titre, pivot, nombre de lignes, indicateurs de mode lignes, `display_witnesses` et métriques de synchronisation (`pivot_lb_index`, erreurs de clés/segments), dépendances IIIF externes et avertissements ;
- `witnesses` : ID, libellé, rôle base/secondary, état `line_sync`, diagnostics, pages, images, lignes, bbox, polygones et `base_keys` ;
- `reading_document` ou représentation de lecture : blocs/segments de texte annotés par `line_key`, positions et références à notes/variantes ;
- métadonnées de la navigation `<pb>`, zones de doubles pages et traductions d'interface.

Les noms des champs exacts doivent être repris du JSON construit dans `build_dataset` ; éviter de considérer cette liste pédagogique comme un schéma figé. Les clés calculées ne remplacent **jamais** les identifiants physiques d'origine.

## 3. Chaîne de synchronisation à ne jamais casser

```text
<li ...> / <lb edRef="#Mu"/> —(rang dans la source TEI)→
ligne physique effective JSON Mu —(clé page_id::line)→
`base_keys` des JSON secondaires F/A/L —(choix de ligne liée)→
rectangle/polygone/image de chacun des témoins —(JS)→
panneaux du viewer visibles et recadrés
```

La correction structurelle V0.8.5.25.3 a rendu ce contrat identique à celui de l'éditeur. Les marqueurs `pb/@n` sont des libellés éditoriaux et **ne doivent pas** servir à recalculer des `line` physiques. `PageResolver` peut interpréter `pb/@facs` pour la navigation par folio/zone, mais cela demeure distinct du chaînage `<lb/>` vers le JSON pivot.

`meta.pivot_lb_index` doit être examiné en priorité lors d'une régression (nombre de `<lb>` versus lignes physiques, count_match, éléments non associés). Un clic sur une clé `data-line` inconnue ne doit pas déclencher un déplacement arbitraire. Si la clé existe et est liée à des lignes des secondaires, la mise à jour des panneaux doit fonctionner même avec le pivot techniquement présent mais visuellement masqué.

**Incident historique majeur :** la V0.8.5.25.1/.2 pouvait afficher les bonnes images en mode lignes sans déplacer correctement les autres témoins au clic ; les tests synthétiques passaient parce qu'ils n'avaient pas reproduit les identifiants de pages du corpus réel. Un ancien `viewer.html` resté dans le dossier peut se faire passer pour une version récente : **toujours régénérer le fichier et vérifier les métadonnées internes avant de conclure à une régression**.

## 4. Paramètres de présentation et pivot caché

`display_witness_ids` :

- `None` ⇒ tous les témoins dans l'ordre de `project.xml` ;
- liste non vide ⇒ les IDs reconnus dans l'ordre exact demandé (pas l'ordre source) ;
- liste vide ⇒ aucun panneau manuscrit affiché.

Les témoins secondaires masqués ne sont pas publiés. Le pivot masqué reste dans les **données techniques minimales nécessaires au calcul de l'index**, mais les liens vers ses images sont retirés, et aucun panneau n'est affiché. Ce comportement est délibéré : supprimer intégralement le pivot casserait les `base_keys` secondaires. L'export d'un dossier existant peut laisser derrière lui d'anciennes images non utilisées ; aucun nettoyage destructif automatique.

## 5. Recherche plein texte A03

`fulltext_search.js` construit un index à partir du **texte de lecture affiché**. Il conserve pour chaque unité d'origine un lien vers sa position (`docPos`, offset UTF-16, `lineKey`). La recherche peut traverser plusieurs segments de balisage TEI sans perdre les offsets. Les occurrences sont affichées dans une liste, surlignées sans altérer la TEI, et la sélection relaie une clé de ligne existante au viewer.

**Modes de comparaison :** sans case cochée, recherche exacte insensible à la casse ; sinon trois équivalences indépendantes **u/v**, **i/j**, **c/t**. Le libellé « Medieval spellings » / « Graphies médiévales » est **un texte d'intitulé et non une quatrième case à cocher** (correction V0.8.5.26.1). `c/t` peut produire beaucoup de faux positifs : ne l'imposer ni globalement ni sans contrôle utilisateur.

Le texte original n'est pas réécrit ; `splitText` injecte uniquement les surlignages `<mark>` avec échappement du contenu, et les attributs `data-line` des éléments demeurent inchangés. Les recherches sont limitées à 5 000 résultats. Les popovers d'annotation et le texte OCR brut non affiché ne sont pas indexés par cette fonction. Un résultat sans clé valide utilise un fallback prudent (pas de synchronisation inventée).

## 6. Géométrie et IIIF

`geometry.js` convertit les repères des sommets et du crop ; `iiif.js` construit la liste de requêtes par taille/région/version d'API et gère replis et annulation. Une image entière obtenue en repli peut être recadrée localement, tandis qu'une réponse régionale fournit directement la zone utile ; le SVG conserve des repères homogènes. Les `image.type=none` correspondent parfois à de vraies données absentes et **ne doivent pas** être systématiquement corrigés comme des bugs d'export.

## 7. Aperçu XSLT interne ≠ viewer web

L'éditeur offre déjà un aperçu interne basé sur XSLT/CSS, avec `rendering/@xsltMode`, `@xslt`, `@css` et `customElements`. Le viewer web a sa **propre** fabrication HTML/JS, car il exige des ancres scientifiques, des événements, des images et des polygones. Les maquettes historiques de personnalisation de l'export ne sont pas des fonctions livrées ni une roadmap décidée.

## 8. Tests et recettes obligatoires

```bash
python -m pytest -q tests/test_v085253_pivot_lb_contract.py
python -m pytest -q tests/test_v085261_web_viewer_presentation.py
python -m pytest -q tests/test_v08526_interim_features.py
python -m pytest -q tests/test_v08524_web_geometry.py tests/test_v08525_iiif_web.py
python -m web_viewer.generator project.xml
```

Cas de recette utilisateur : clics sur plusieurs pages éloignées (Mu, F, A, L), note/variante/référence, pivot masqué, témoin sans lien en mode pages, images absentes, régions IIIF refusées, doubles pages, recherche variante/forme exacte, tous témoins masqués, nouvelles préférences QSettings. Recueillir le HTML **généré dans l'environnement testé**, l'ID de version réel du code et les diagnostics d'index, jamais simplement le titre annoncé de l'archive.


---

# 06 — Procédures de maintenance, vérification et livraison

## 1. Identification et intégrité de la version

Avant toute modification, extraire `BASE_SOURCE/Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip` dans un dossier **neuf**. L'archive de référence comporte **268 membres** et sa somme SHA-256 doit correspondre à `BASE_SOURCE/Varians_V0.8.5.26.2_SHA256.txt`. Vérifier également l'absence d'erreur CRC ZIP. Dans `editeur_tei.py`, `APP_VERSION` vaut `0.8.5.26.2`.

Ne pas réutiliser à la place un dossier Spyder contenant des anciens modules Python en mémoire. Une nouvelle fenêtre Varians peut continuer à charger un ancien `web_viewer/generator.py` depuis un chemin antérieur : contrôler le chemin du module réellement importé si les résultats diffèrent. Un viewer HTML antérieur **reste ancien même si l'application a été mise à jour** : régénérer l'export.

## 2. Dépendances

- Production : Python 3, `PySide6`, `lxml` (fichier `requirements.txt`).
- Développement : `pytest`, plus éventuellement Node.js et Chromium/Playwright pour les essais du viewer.
- Aucun composant Visual Studio/Windows n'est requis dans le cœur Python. Les lanceurs `.bat` ne sont que des aides.
- Pour macOS/Linux : vérifier Qt, fontes locales (notamment caractères japonais), fenêtres détachées, accès fichiers et comportement d'Always-on-top en environnement Wayland.

## 3. Contrôles automatisés

```bash
python -m pytest -q --disable-warnings --maxfail=1
python -m compileall -q .
python -m web_viewer.generator project.xml
```

**Observation indépendante de cette passation** : 479 tests réussis, 2 ignorés, zéro échec ; compilation Python sans erreur. Le rapport texte de l'exécution est joint à `VERIFICATION/pytest_independant.txt`. Les deux tests ignorés ne doivent pas être annoncés comme « réussis ». Une grande partie des contrôles UI Qt repose sur des substitutions, AST ou logique sans Qt ; **ne pas confondre les tests de logique avec un test graphique natif**.

Pour les tests Javascript, vérifier la disponibilité de Node (`node --version`) et utiliser les tests du répertoire `tests/`; certains scripts Playwright nécessitent une installation optionnelle. La sortie `web_output/viewer.html` incluse est une **démonstration**, pas les manuscrits de l'utilisateur.

## 4. Recettes manuelles minimales avant de livrer

| Famille | Action testée | Résultat attendu |
|---|---|---|
| Démarrage | ouvrir/fermer un projet, restaurer le dernier | pas de perte de ressource, pas d'ancien module |
| XML | texte mixte, paires imbriquées, autofermantes | source inchangée, surlignage conservateur |
| Complétion | attribut préfixé, valeur RNG, Ctrl+Espace | contexte exact, insertion sans doublon |
| RNG | F8, correction panneau ouvert puis masqué, annuler/refaire | aucune erreur périmée, nouvelle révision affichée |
| XPath | résultats, clic, passage replié | sélection à bon offset, dévoilement |
| Images | image locale/IIIF sans ALTO | consultation possible en mode pages |
| ALTO/PAGE | import OCR isolé et polygone concave | images préservées, sommets fidèles |
| Synchronisation | `base_keys` valides/absentes/orphelines | lignes correctes ou mode pages prudent |
| Double page | deux zones, fractionnement et `<pb>` | une image, zones stables, décision contrôlée |
| Disposition | vertical/horizontal/grille/détaché | mêmes panneaux et réglages |
| Viewer exporté | texte→lignes secondaires, pivot masqué | `data-line` valide, aucun panel fantôme |
| Recherche web | exact, u/v, i/j, c/t séparément | faux positifs maîtrisés, sélection lié au bon passage |
| Langues | changer à chaud fr/en/de/ja/cs/it/ru | libellés/aides corrects et projet conservé |
| Portabilité | déplacer un projet à chemins relatifs | références résolues, pas d'écriture implicite |

## 5. Cas spéciaux à couvrir

- `<lb/>` du pivot dans des notes, `pb/@n` différant de l'ID JSON, absence de `<pb/>`, double image et numéros physiques non consécutifs.
- JSON déclaré secondaire mais sans `base_keys`, même avec des milliers de boîtes ALTO.
- IIIF dont les images sélectionnées sont valides mais l'OCR ne se rapproche d'aucun Canvas ; le manifeste doit rester canonique.
- Bitmaps réduits à 490 px pour un Canvas de plusieurs milliers de pixels ; les cadres restent alignés.
- Deux fenêtres détachées sur plusieurs moniteurs et changement de langue ; topmost dépend de l'OS.
- Réseau indisponible, 403/404/429/500, servi partiel, bascule rapide de page pendant un téléchargement.
- Références `base_keys` orphelines après suppression éditoriale : diagnostiquer, **ne pas remailler les références automatiquement**.

## 6. Procédure recommandée pour toute évolution

1. Écrire en quelques lignes l'anomalie/priorité **explicitement approuvée** et son scénario de reproduction (ne pas reprendre une ancienne roadmap).
2. Faire un **diff contrôlé** depuis le ZIP de référence ; isoler les modules touchés et les contrats scientifiques affectés.
3. Ajouter des tests de caractérisation avant de transformer la logique ; pour le viewer, prévoir un cas synthétique qui échouait avec l'ancien code et passe avec le nouveau.
4. Préserver une archive originale intacte ; travailler dans un autre dossier.
5. Exécuter suite ciblée puis suite entière ; relever le nombre de tests, les ignorés, les résultats JS et les limites GUI.
6. Mettre à jour toutes les traductions et aides affectées, les fichiers de passation pertinents et le rapport de version.
7. Produire **une archive complète**, sans fichiers `__pycache__`/`.pytest_cache` temporaires, contrôler CRC, nombre de membres, présence des sources et documentation, SHA-256.
8. Donner un essai utilisateur ciblé, puis seulement considérer la nouvelle version stable une fois les retours reçus.

## 7. Règles d'écriture et sauvegarde

`save_io.py` prévoit une sauvegarde atomique et un fichier antérieur `.bak`. Des opérations de rafraîchissement, d'export ou de changement de disposition ne doivent pas modifier le contenu scientifique. Les migrations de `project.xml` doivent être explicites, conservatrices et, lorsqu'elles sont nécessaires, accompagnées de sauvegardes. Ne jamais supprimer automatiquement des images anciennement copiées simplement parce qu'un témoin est masqué dans le dernier export.

## 8. Limites actuelles à déclarer explicitement

- Le test de l'application PySide6 sur Windows/macOS/Linux n'a **pas** été exécuté par l'environnement ayant construit le ZIP de référence ; plusieurs vérifications Chromium synthétiques appartiennent à des étapes antérieures.
- Aucun package de manuscrits scientifiques réels Mu/F/A/N/L n'est inclus dans l'archive. Le test utilisateur a confirmé la reprise correcte du viewer, mais ne couvre pas toutes les zones, toutes les pages ou tous les serveurs.
- L'export web dépend de la qualité et de l'intégrité des données, et de la disponibilité/réglementation des services IIIF.


---

# 07 — Historique, décisions et incidents à ne pas répéter

## 1. Jalons antérieurs utiles à comprendre

| Version | Apport structurant |
|---|---|
| 0.4.2 / 0.5.x | Aperçu interne XSLT/CSS, validation XML/RELAX NG et complétion contextuelle |
| 0.7.x | Ressources indépendantes : images, ALTO, synchronisation facultative ; sources locales et IIIF |
| 0.8.4 | Distinction JSON présent / lignes réellement synchronisées |
| 0.8.5.9–.17 | Sécurité du crop multicolonnes, navigation mixte, respect du manifeste, ordre des témoins, rafraîchissement transactionnel |
| 0.8.5.18–.21 | Double page à zones et dispositions du poste de travail |
| 0.8.5.22–.23 | Repliage XML sûr puis surlignage bidirectionnel des paires |
| **0.8.5.24** | Géométrie PAGE/ALTO, polygones, recadrage web et doubles pages |
| **0.8.5.25** | Chargements IIIF adaptatifs, régions, fallback et annulation |
| **0.8.5.25.1** | Correspondance de folios TEI/Canvas et page physique du viewer |
| **0.8.5.25.2** | Navigation au clic, notes et affichage de la ligne active |
| **0.8.5.25.3** | **Parité de l'index global `<lb/>` pivot entre web et desktop** |
| **0.8.5.26** | Refresh RNG A01, noms d'attributs A02, recherche plein texte médiévale A03 |
| **0.8.5.26.1** | Recherche sans case globale, ordre/visibilité des témoins à l'export |
| **0.8.5.26.2** | **Invalidation robuste des erreurs RELAX NG par révision Qt** |

Ce tableau est une synthèse ; les notes `PASSATION_V0_8_5_*` et les rapports `TEST_REPORT_V0_8_5_*` contenus dans la distribution précisent dates et limites. L'application et son projet d'exemple ont évolué bien au-delà des titres historiques des documents.

## 2. Incident majeur : le viewer n'affichait plus correctement les lignes

Après les améliorations de géométrie/IIIF, les images s'affichaient d'abord en pages complètes ; après des correctifs, elles s'affichaient en mode lignes mais un clic dans le texte ne suivait pas correctement les autres manuscrits. Les corrections successives de clic ou de repérage visuel n'ont pas suffi. **Enseignement : ne pas multiplier des patches sur les effets visibles sans comparer la chaîne de données desktop/web**.

La cause structurelle identifiée en 0.8.5.25.3 : le viewer reconstruisait les identifiants des lignes à partir de `<pb/>` et de la numérotation par page, alors que l'éditeur utilisait l'ordre global des `<lb edRef="#pivot"/>` et les clés **physiques réelles** du JSON. Cette divergence et la suppression de lignes pivot au moment de l'export causaient des `data-line` incohérents.

Un script de diagnostic Spyder sur un ancien `viewer.html` réel a trouvé 701 segments non ancrés et 41 clés textuelles absentes du pivot. Après régénération réelle depuis 0.8.5.25.3, le diagnostic est passé à 0 segment sans clé, 0 clé absente, 226 `<lb/>` pour 226 lignes physiques, avec retour utilisateur confirmant que la navigation semblait fonctionner. **Ne pas confondre ces constats historiques et un état permanent des fichiers manuscrits.**

La source HTML testée initialement n'était pas celle attendue de 0.8.5.25.3 : la nouvelle rubrique `meta.pivot_lb_index` était absente. Enseignement : vérifier le fichier réellement généré et les modules importés, particulièrement avec Spyder et plusieurs distributions extraites.

## 3. Incident distinct : page sans image Mu

Un diagnostic de l'export a repéré une page `BSB Clm 14713 4v` (`image.type=none`, un seul segment géométrique). L'utilisateur a confirmé que c'était un **défaut de données du projet**, non une anomalie du viewer. Un audit ne doit pas transformer tous les `image.type=none` en anomalies du code, ni inventer une URL IIIF.

## 4. Incident : références secondaires vers une clé physique absente

Un export réel récent a montré **une** référence inconnue chez F, A et L malgré un pivot texte désormais cohérent. L'utilisateur a signalé la suppression d'une ligne vide de Mu, explication plausible, **non confirmée sans inspection des clés exactes**. Le bon comportement est de signaler les liens orphelins, d'en déterminer la provenance et de ne pas reconstituer des correspondances par position ni par ressemblance de texte.

## 5. Incident : anciennes erreurs RELAX NG qui reviennent

A01 dans la version 0.8.5.26 a réactualisé la liste, mais une dépendance à la visibilité du panneau demeurait. Après correction pendant que le panneau était masqué, un résultat ancien pouvait réapparaître. La V0.8.5.26.2 invalide l'état à chaque nouvelle révision Qt, relance même si le panneau est masqué après première utilisation, rejette les calculs tardifs et contrôle la réouverture. Le retour utilisateur est positif : **« ça semble résolu »** ; ne pas le décrire comme une preuve de robustesse formelle universelle.

## 6. Demandes d'apparat critique et nouvelle feuille de route

L'utilisateur a explicitement abandonné les modèles/générateurs d'apparat critique, conservant les fonctions XML générales. La feuille de route proposée à l'automne 2026 (personnalisation XSLT/CSS de l'export, audit intégral et empaquetage, etc.) a ensuite été **remise à zéro** à sa demande. Des propositions et documents peuvent subsister dans les sources à valeur historique ; **aucune n'est programmée** jusqu'à nouvelle décision.

## 7. Pratiques anti-régression

- Comparer une version connue fonctionnelle **et** la nouvelle, par diff ciblé des fonctions touchées.
- Reconstituer un projet synthétique qui porte les propriétés réelles de l'incident (IDs techniques, folio, multiples zones, numéros de lignes non consécutifs), pas uniquement le projet T1/T2/P de démonstration.
- Examiner la sérialisation des clés dans l'export avant la partie graphique.
- Documenter ce qui est vérifié par des tests Python, Node, Chromium, Qt simulé ou une session Windows réelle ; ces niveaux ne sont pas interchangeables.
- Lorsqu'un utilisateur dit que le résultat ne fonctionne pas, reprendre le diagnostic plutôt que d'empiler des correctifs non démontrés.


---

# 08 — Internationalisation, sécurité, performance, portabilité

## 1. Sept langues, source unique des traductions

Fichiers interface `i18n/fr.xml`, `en.xml`, `de.xml`, `ja.xml`, `cs.xml`, `it.xml`, `ru.xml` et aides `help/{lang}.html`. Les sept catalogues comptaient **629 messages distincts chacun** dans le rapport 0.8.5.26.2. `i18n.py` gère chargement, fallback et changement de langue ; les textes du viewer web sont également exportés et doivent provenir des mêmes politiques de traduction. Les commandes XML, la recherche médiévale et les diagnostics RNG exigent un vocabulaire précis, particulièrement pour les lettres u/v, i/j et c/t qui ne doivent pas être assimilées à une traduction typographique.

À chaque nouveau libellé : ajouter la même clé dans les sept catalogues, traduire selon sa fonction et non mot à mot, maintenir les sept aides, vérifier la substitution des paramètres (espaces réservés) et tester le changement de langue pendant qu'un projet est ouvert. Conserver la terminologie « témoin pivot » technique, « parties gauche/droite » pour les doubles pages, « lignes synchronisées » seulement quand les clés sont vérifiables.

## 2. Sécurité XML / XSLT

L'aperçu XSLT interne peut utiliser des feuilles intégrées ou de projet. `document()`, `xsl:include` et `xsl:import` créent potentiellement des accès au système ou au réseau ; le parseur XML avec `no_network=True` **ne sécurise pas nécessairement la totalité de l'exécution XSLT**. Tout futur mécanisme de profils d'export devrait définir explicitement des restrictions fichiers/réseau, inclure la protection contre l'expansion d'entités et les résolutions hors racine du projet. Une telle fonctionnalité n'est **pas** une décision de roadmap actuelle.

Les diagnostics et la recherche ne doivent pas écrire dans la source TEI. Les chemins relatifs traversant `..`, les symlinks externes, les collusions casse-insensible et les archives destinées à diffusion demandent une prudence particulière. Les URL d'image/HTML doivent être échappées ou filtrées par protocole ; le moteur IIIF JS possède des contrôles d'URL avant le chargement.

## 3. HTML et données exportées

- Sérialiser les données JSON de façon à empêcher qu'une chaîne de contenu termine prématurément un `<script>` HTML ; le générateur neutralise notamment `</`.
- Échapper titres, attributs, HTML de recherche et textes de balisage ; ne pas transformer une entrée TEI en script exécutable.
- Ne pas exposer un chemin local absolu dans un HTML public lorsqu'une ressource est manquante : messages d'export basés sur des noms de fichiers, pas sur le disque personnel de l'utilisateur.
- Un fichier `viewer.html` local peut contenir le contenu du corpus et des métadonnées : éviter sa diffusion sans autorisation.
- Les demandes IIIF sont dépendantes de droits, authentification, politiques de CORS et disponibilité. Une image distante n'est jamais garantie publiable à l'infini ni disponible offline.

## 4. Performance

- Le rafraîchissement RNG est temporisé : **1 250 ms** après changement (une fois surveillance activée), et met en cache les schémas ; ne pas recompiler le RNG à chaque caractère ni laisser publier un résultat périmé.
- La complétion se fonde sur des caches de contexte lexical/modèles RNG ; le changement de projet ou de schéma doit les invalider.
- Les images IIIF sont adaptées à la taille de la fenêtre/région et disposent de plans de repli, annulations et timeouts ; ne pas requérir systématiquement le Canvas entier en définition maximale.
- Les caches IIIF/ALTO et les copies locales reposent sur des index ; éviter de lire/recalculer le manifeste pour chaque sommet affiché.
- Le viewer recherche sur un index calculé depuis le texte visible ; `spansByPosition` évite un parcours intégral des résultats pour chaque fragment ; la limite de 5 000 occurrences est une protection, pas une spécification d'exhaustivité.

## 5. Portabilité

La compatibilité Windows/macOS/Linux doit être conservée dans les chemins (Pathlib), l'Unicode, le chargement Qt et le traitement des fichiers. Pour Windows/Spyder, il faut pouvoir identifier le chemin de l'interpréteur et le module chargé ; les artefacts `.bat` sont auxiliaires. Sur Linux/Wayland, « Toujours au premier plan » et le placement exact des fenêtres détachées peuvent dépendre du compositeur. Sous macOS, tester les raccourcis, les fenêtres natives et les chemins encodés. Les projets qui pointent vers des ressources locales sous licence ou vers des services IIIF authentifiés ne deviennent pas portables par une simple copie du XML.

## 6. Protection contre les pertes

Réutiliser `save_io.py` pour des sauvegardes atomiques et `.bak`; un simple changement d'export ou de disposition ne doit écrire dans aucune ressource scientifique. Lors de l'import ou du rafraîchissement, utiliser la préparation transactionnelle de `witness_resource_refresh.py`. Les suppressions (images copiées, anciens JSON, zones, lignes, références) doivent être volontaires et tracées, jamais un effet secondaire d'une « optimisation ».


---

# 09 — Gouvernance de la reprise et feuille de route ouverte

## 1. Statut au 15 octobre 2026

**Base de référence : Varians V0.8.5.26.2.** Sa synchronisation web, son ordre/visibilité des témoins, son moteur de recherche à graphies médiévales, la complétion des noms d'attributs XML et le rafraîchissement corrigé du panneau RELAX NG sont les jalons conservés. L'utilisateur a confirmé le fonctionnement du viewer web et a indiqué que le défaut RNG semble résolu. Aucune modification supplémentaire du code n'est décidée dans la présente passation.

**La roadmap antérieure est suspendue intégralement.** La séquence proposée « version XSLT/CSS → audit → empaquetage » n'est plus une consigne. Les notes de conception correspondantes sont conservées pour référence, pas pour exécution automatique.

## 2. Principe d'entrée d'un nouveau chantier

Chaque nouvelle demande devra être discutée avec l'utilisateur avant codage. La fiche de décision recommandée contient :

- **Identifiant** de la demande et formulation exacte de l'utilisateur ;
- problème constaté, objectif recherché et preuve disponible (cas de reproduction, fichiers, captures) ;
- domaines/modèles touchés et risque scientifique de transformation non demandée ;
- comportement attendu à l'écran et sur disque ;
- exclusions explicites, limites de portabilité et droits des images ;
- critère d'acceptation vérifiable (tests Python, HTML, Qt natif, corpus réel) ;
- impact sur les sept langues/aides et sur les documents de transmission ;
- numéro de version envisagé **seulement après choix**, non inféré de vieux tableaux.

## 3. Critères d'une version livrable

Une version ne doit pas être présentée comme stable uniquement parce que les tests statiques passent. Conditions recommandées :

1. Sources complètes et même projet de démonstration, tous fichiers utiles présents ; données scientifiques inchangées sauf décision explicite.
2. Tests de régression pertinents et contrôle d'absence de nouveaux échecs ; couverture du cas déclencheur de la correction.
3. Vérification des points transversaux : sauvegarde, `lb`/`base_keys`, images et PAGE/ALTO, dispositions, panneau RNG et recherche, selon périmètre.
4. Compilation Python ; syntaxe JS et tests navigateur si viewer affecté ; essai PySide6 natif quand l'UI est affectée.
5. Traductions/HTML d'aide en sept langues à jour, sans clé manquante.
6. ZIP complet CRC vérifié, SHA-256 fourni, inventaire de provenance, documentation actuelle, informations sur limites de tests.
7. Validation utilisateur sur le corpus réel ou au moins un scénario représentatif avant promotion en référence.

## 4. État des risques ouverts — observation, pas agenda

- Tests GUI multiplateformes natifs moins complets que les tests logiques.
- Fichiers de recherche/alignement peuvent contenir des références historiques orphelines, à diagnostiquer sans réparation automatique.
- Disponibilité et droit d'usage des images IIIF hors du contrôle du logiciel.
- Gros modules historiques difficiles à refondre sans tests de caractérisation.
- Docs historiques portant des promesses anciennement envisagées, désormais sans valeur prescriptive.

Ces constats servent à la vigilance de maintenance. Ils ne constituent **ni une demande ni une priorité de développement**.

## 5. Communication de reprise

Le repreneur doit expliciter pour chaque résultat : « implémenté », « testé automatiquement », « testé dans un navigateur synthétique », « testé par l'utilisateur Windows », « documenté comme hypothèse » ou « proposé sans décision ». En particulier, des compteurs de tests ne prouvent pas la validité de toutes les correspondances scientifiques d'un projet réel ; un `image.type=none` n'est pas forcément un bug du code ; une ancienne exportation peut ne pas refléter la nouvelle version.

## 6. Première session conseillée au repreneur

1. Vérifier le ZIP original, les versions et le rapport de tests de ce dossier ; ne pas modifier les sources.
2. Exécuter le projet de démonstration, ouvrir la TEI, inspecter quelques panneaux et générer un viewer frais.
3. Parcourir `MainWindow.sync_panels_to_cursor`, `flatten_primary`, `web_viewer.tei_line_anchors`, `build_dataset`, et les diagnostics `pivot_lb_index` pour comprendre le contrat le plus délicat.
4. Tester délibérément une erreur RNG corrigée panneau visible/masqué et une suggestion d'attribut, comme premiers parcours Qt.
5. Reproduire un viewer avec pivot masqué et secondaires affichés, puis un clic de recherche médiévale conduisant à la bonne ligne.
6. **Demander la nouvelle feuille de route au porteur du projet**, sans reprendre celle des documents anciens.

## 7. Points à ne pas interpréter comme des autorisations

Le fait que des documents de conception décrivent des profils d'export personnalisés, un audit scientifique, un système de génération d'apparat ou une migration du format JSON ne signifie pas qu'ils sont prévus. Ne pas modifier la TEI, ni les archives/manuscrits, pour satisfaire des tests de démonstration sans autorisation. La reprise doit préserver l'autonomie scientifique de l'éditeur et celle de Varians-Synchro.


---

# 10 — Provenance, méthodes de contrôle et portée des preuves

## 1. Référence primaire

Nom de l'archive source : `Varians_V0.8.5.26.2_Correctif_Validation_RELAX_NG_Complete.zip`.

Cette archive est recopiée **octet pour octet** dans `BASE_SOURCE/`. Les fichiers documentaires supplémentaires de la présente passation ne sont pas des modifications du logiciel ; leur présence ne doit pas être interprétée comme un lancement de nouvelle version.

Valeurs observées indépendamment :

- **268 fichiers** dans l'archive ZIP ; contrôle CRC : aucune erreur ;
- `APP_VERSION = "0.8.5.26.2"` dans `editeur_tei.py` ;
- dépendances déclarées : `PySide6`, `lxml` ;
- `python -m pytest -q --disable-warnings --maxfail=1` : **479 passed, 2 skipped** (exécuté dans l'environnement documentaire, sortie jointe) ;
- `python -m compileall -q ...` : réussite ;
- les sept langues d'interface et les sept aides HTML sont dans la distribution ;
- le rapport d'origine indiquait **629 entrées de catalogue par langue** et l'absence de modification du viewer web dans la version .2.

Le manifeste SHA-256 et le rapport d'inventaire machine produits pendant cette passation rendent ces constats reproductibles. Un rapport de tests peut varier en temps d'exécution selon le poste.

## 2. Distinction vérification / retour d'usage / hypothèse

| Affirmation | Nature de la preuve | Portée |
|---|---|---|
| Archive V0.8.5.26.2 identifiée | SHA-256, CRC, `APP_VERSION` | Base exacte et non modifiée |
| Suite Python 479/2 | exécution indépendante | Tests présents dans cette distribution, hors couverture GUI native |
| XML validé après corrections | retour utilisateur + tests ciblés | Résolution pratique plausible et retenue, non preuve de tous les cas futurs |
| Recherche `u/v`, `i/j`, `c/t` | tests JS/Chromium synthétiques antérieurs et retour utilisateur | Parcours de recherche et surlignage validés dans scénarios connus |
| Ordre/visibilité du viewer | essais Chromium synthétiques et confirmation utilisateur | Fonction du viewer retenue |
| Parité `<lb/>` pivot | tests Python, diagnostic HTML réel, confirmation utilisateur | Retour à une cohérence observée ; surveiller nouveaux corpus |
| JSON secondaires sans clé | contrat source | Mode pages volontaire, sans inventer de lignes |
| Validité des images IIIF distantes | dépend du serveur et des droits | Pas de garantie hors ligne ni d'accès permanent |
| Toute l'UI Qt macOS/Linux | non testée physiquement ici | Ne pas l'annoncer validée |

## 3. Protection des données utilisateurs

La distribution ZIP contient des fichiers d'exemple `T1/T2/P`. Les vrais manuscrits Mu/F/A/N/L ne sont pas incorporés comme corpus scientifique à cette passation. Les diagnostics partagés dans les échanges ont donné des nombres de lignes, de clés et des identifiants, mais **ne remplacent pas les vrais fichiers** et n'autorisent pas à reconstruire le projet réel. Ne pas publier de manuscrits, de scans sous droits, ni d'URLs authentifiées dans la documentation sans permission.

## 4. Maintenance documentaire

À chaque version future, compléter un addendum qui indique explicitement : base exacte, fichiers source modifiés, comportement antérieur/nouveau, hypothèses éliminées, tests précis, limites, statut d'essai utilisateur, nouvelle empreinte. Ajouter l'addendum à un handover consolidé si la version devient un nouveau jalon majeur. Ne jamais écraser l'archive originale ni réécrire l'histoire : les notes antérieures restent consultables mais doivent être qualifiées par leur date et version.


---

# 11 — Inventaire vérifié du code et des tests

Généré par analyse syntaxique AST des fichiers Python **réels** de la V0.8.5.26.2 ; cet index est un instrument de navigation, pas une documentation d’API stable.

- **110 modules Python** analysés (sources et tests inclus).
- **35 fichiers Python hors tests**.
- **75 fichiers Python sous tests/**.

## Sources et modules web

| Fichier | Lignes | Classes définies | Fonctions de niveau module | Méthodes de classe |
|---|---:|---:|---:|---:|
| `alto_import.py` | 523 | 1 | 22 | 0 |
| `custom_completion.py` | 211 | 4 | 4 | 8 |
| `editeur_tei.py` | 7855 | 23 | 39 | 314 |
| `folio_navigation.py` | 349 | 1 | 8 | 0 |
| `i18n.py` | 104 | 2 | 1 | 6 |
| `iiif_download_manager.py` | 268 | 2 | 0 | 17 |
| `iiif_local.py` | 262 | 0 | 13 | 0 |
| `iiif_manifest.py` | 192 | 1 | 11 | 0 |
| `iiif_page_selection.py` | 209 | 0 | 7 | 0 |
| `iiif_resolution.py` | 442 | 1 | 9 | 0 |
| `iiif_selection.py` | 99 | 0 | 6 | 0 |
| `image_sources.py` | 685 | 1 | 23 | 1 |
| `project_config.py` | 366 | 4 | 5 | 4 |
| `project_dialogs.py` | 1336 | 6 | 1 | 55 |
| `project_management.py` | 699 | 4 | 12 | 0 |
| `relaxng_validation.py` | 270 | 3 | 13 | 0 |
| `resource_state.py` | 98 | 1 | 5 | 0 |
| `rng_completion.py` | 1272 | 6 | 25 | 30 |
| `save_io.py` | 59 | 0 | 1 | 0 |
| `schema_resolution.py` | 221 | 2 | 6 | 2 |
| `selection_sync.py` | 46 | 0 | 3 | 0 |
| `tei_facsimile.py` | 574 | 2 | 20 | 0 |
| `tei_formatter.py` | 265 | 3 | 7 | 4 |
| `tei_pivot_scaffold.py` | 378 | 2 | 9 | 1 |
| `web_viewer/__init__.py` | 3 | 0 | 0 | 0 |
| `web_viewer/generator.py` | 521 | 0 | 6 | 0 |
| `web_viewer/legacy_v11_core.py` | 1613 | 0 | 38 | 0 |
| `web_viewer/page_resolver.py` | 142 | 1 | 2 | 2 |
| `web_viewer/tei_line_anchors.py` | 59 | 1 | 2 | 1 |
| `witness_layout.py` | 42 | 0 | 3 | 0 |
| `witness_resource_refresh.py` | 255 | 2 | 8 | 0 |
| `workspace_layout.py` | 26 | 0 | 3 | 0 |
| `xml_folding.py` | 89 | 1 | 4 | 0 |
| `xml_tag_pairs.py` | 588 | 4 | 20 | 4 |
| `xpath_search.py` | 300 | 4 | 9 | 0 |

## Symboles de production (classes et fonctions de module)

### `alto_import.py`
Classes : `AltoParsedFile` (L203)
Fonctions : `_local` (L20), `_num` (L24), `_safe_id` (L34), `_norm` (L40), `_first_text` (L46), `_line_text` (L53), `_polygon_bbox` (L72), `_points` (L92), `_bbox_from_points` (L105), `_child` (L115), `parse_page_file` (L119), `parse_layout_file` (L189), `parse_alto_file` (L209), `build_alto_cache` (L273), `_page_keys` (L289), `_line_uuid` (L313), `_merge_lines` (L323), `overlay_alto` (L396), `source_signature` (L472), `cache_path` (L481), `load_or_build_cache` (L486), `apply_witness_alto_policy` (L512)

### `custom_completion.py`
Classes : `DynamicValues` (L48), `CustomAttributeSpec` (L55), `CustomElementSpec` (L72), `CustomCompletionConfig` (L81)
Fonctions : `_local_qname` (L39), `_name_matches` (L43), `load_custom_completion` (L133), `merge_suggestion_sources` (L190)

### `editeur_tei.py`
Classes : `XMLHighlighter` (L324), `LineNumberArea` (L347), `CodeEditor` (L361), `XmlHealthSignals` (L1123), `XmlHealthWorker` (L1128), `FetchSignals` (L1164), `FetchWorker` (L1169), `ImageSceneView` (L1265), `SplitImagePreview` (L1365), `SplitPreviewLoader` (L1458), `WitnessHeader` (L1519), `ManuscriptPanel` (L1543), `ClickablePreview` (L2198), `FormattedEditionWidget` (L2522), `CompletionDialog` (L3431), `CtrlEConfigDialog` (L3521), `SoftwareHelpDialog` (L3583), `AboutDialog` (L3739), `DetachedWitnessWindow` (L3759), `WitnessVisibilityDialog` (L3818), `WitnessDiagnosticDialog` (L3913), `MainWindow` (L3989), `WelcomeWindow` (L7575)
Fonctions : `_install_light_selection_palette` (L143), `_t` (L152), `_settings` (L162), `recent_project_paths` (L166), `remember_recent_project` (L181), `remove_recent_project` (L187), `clear_recent_projects` (L191), `last_open_project_path` (L195), `remember_open_project` (L216), `forget_open_project` (L220), `load_json` (L224), `flatten_primary` (L229), `flatten_secondary` (L241), `scaled_bbox` (L254), `scaled_polygon` (L289), `crop_for_items` (L302), `iiif_image_request` (L319), `find_in_plain_editor` (L922), `find_in_rich_editor` (L979), `_selection_xml_to_visible_text` (L1058), `_rich_selection_pattern` (L1078), `_xml_selection_pattern` (L1096), `_iiif_split_preview_request` (L1476), `load_split_thumbnail` (L1491), `paragraph_spans` (L2107), `resolve_css_variables` (L2118), `inject_edit_markers` (L2130), `make_line_segments_clickable` (L2163), `lxml_available` (L2445), `transform_with_xslt` (L2453), `_selected_text_for_dictionary` (L3609), `_open_external` (L3646), `_open_latin_dictionary` (L3650), `_show_software_help` (L3656), `_varians_font` (L3660), `_scaled_logo_label` (L3672), `_build_varians_card` (L3684), `_show_about` (L3755), `main` (L7819)

### `folio_navigation.py`
Classes : `Folio` (L20)
Fonctions : `_local` (L27), `folios_for_witness` (L31), `folio_at_position` (L83), `split_surface_into_folios` (L135), `scene_rect_for_folio` (L194), `markable_part_for_line` (L208), `inspect_surface_part_split` (L249), `configure_surface_parts` (L290)

### `i18n.py`
Classes : `LanguageInfo` (L22), `I18nManager` (L28)
Fonctions : `load_i18n` (L102)

### `iiif_download_manager.py`
Classes : `DownloadThread` (L18), `IIIFDownloadManager` (L52)

### `iiif_local.py`
Fonctions : `_safe_id` (L23), `store_dir` (L27), `index_path` (L31), `remote_key` (L35), `_request_url` (L41), `_read_index` (L51), `_valid_entry` (L61), `local_image_path` (L82), `apply_working_copy` (L86), `_image_extension` (L110), `_fetch_image` (L124), `plan_witness_copy` (L157), `download_witness_copy` (L204)

### `iiif_manifest.py`
Classes : `IIIFManifest` (L13)
Fonctions : `_text_label` (L21), `_service_info` (L37), `_service_limits` (L52), `_first_v3_image` (L68), `parse_manifest` (L83), `fetch_manifest` (L134), `cache_path` (L146), `write_cache` (L151), `read_cache` (L157), `import_manifest` (L166), `overlay_manifest` (L176)

### `iiif_page_selection.py`
Fonctions : `canvas_key` (L13), `natural_key` (L18), `exact_image_stem` (L29), `propose_exact_ocr_links` (L52), `selected_manifest_pages` (L120), `_canonical_path` (L135), `selected_page_overlay` (L139)

### `iiif_resolution.py`
Classes : `Resolution` (L19)
Fonctions : `_uri` (L26), `_iiif_image_identity` (L39), `_service_of_image_url` (L61), `_label` (L66), `_page_meta` (L72), `resolve_pages` (L79), `_merge_detached_ocr_pages` (L195), `_layout_only_manifest_pages` (L264), `overlay_resolved_manifest` (L374)

### `iiif_selection.py`
Fonctions : `_stem` (L18), `_norm` (L27), `_folio` (L34), `_page_names` (L44), `_ocr_names` (L50), `select_ocr_pages` (L56)

### `image_sources.py`
Classes : `PageImageSource` (L23)
Fonctions : `_as_int` (L43), `_resolve_file` (L50), `page_image_source` (L62), `page_label` (L114), `page_image_dimensions` (L119), `image_scene_reference_crop` (L127), `_gallica_highres_url` (L150), `page_image_request` (L159), `full_page_target` (L254), `normalized_image_block` (L267), `_local_entries` (L303), `_match_key` (L328), `_associate_local_entries` (L338), `apply_witness_image_policy` (L370), `page_navigation_items` (L495), `_same_physical_page` (L514), `_adjacent_line_continuity` (L528), `effective_line_bbox` (L574), `valid_matched_indices` (L602), `matched_line_center` (L617), `visible_line_frame_indices` (L634), `display_window_indices` (L640), `image_only_items` (L669)

### `project_config.py`
Classes : `LocalImageConfig` (L16), `AltoFileConfig` (L24), `WitnessConfig` (L29), `ProjectConfig` (L76)
Fonctions : `has_line_synchronization` (L57), `_resolve` (L110), `_parse_schema` (L115), `load_project` (L152), `update_project_language` (L349)

### `project_dialogs.py`
Classes : `PathRow` (L22), `IIIFCanvasPicker` (L48), `WitnessEditDialog` (L308), `WitnessTable` (L846), `NewProjectDialog` (L1078), `ProjectSettingsDialog` (L1200)
Fonctions : `run_pivot_scaffold_dialog` (L1036)

### `project_management.py`
Classes : `LocalImageDraft` (L20), `AltoFileDraft` (L28), `WitnessDraft` (L33), `ProjectDraft` (L69)
Fonctions : `minimal_tei_text` (L95), `write_minimal_tei` (L154), `portable_path` (L173), `write_project_xml` (L183), `_safe_filename` (L318), `prepare_alignment_files_for_project` (L330), `prepare_local_images_for_project` (L364), `prepare_alto_files_for_project` (L423), `prepare_iiif_manifests_for_project` (L490), `create_portable_project` (L510), `create_new_transcription_project` (L634), `create_local_xslt_if_needed` (L676)

### `relaxng_validation.py`
Classes : `ValidationIssue` (L25), `ValidationResult` (L35), `_CompiledSchema` (L45)
Fonctions : `lxml_available` (L57), `clear_relaxng_cache` (L61), `relaxng_cache_info` (L79), `relaxng_schema_token` (L88), `_issue_from_log` (L93), `_unique_issues` (L104), `_file_uri_to_path` (L116), `_dependency_path` (L126), `_stat_signature` (L141), `_discover_schema_dependencies` (L152), `_schema_dependency_signature` (L182), `_compiled_relaxng` (L204), `validate_relaxng` (L225)

### `resource_state.py`
Classes : `SynchronizationState` (L67)
Fonctions : `primary_sync_line_count` (L16), `secondary_sync_link_count` (L34), `effective_base_line_sync` (L51), `effective_secondary_line_sync` (L56), `synchronization_state` (L76)

### `rng_completion.py`
Classes : `_Pattern` (L109), `CompletionModel` (L279), `_GrammarIndex` (L416), `XmlCompletionContext` (L797), `_XmlScanCheckpoint` (L1072), `XmlContextCache` (L1078)
Fonctions : `_local` (L47), `_is_rng_node` (L51), `_local_qname` (L56), `_names_match` (L60), `_href_path` (L64), `_explicit_names` (L81), `_token` (L119), `_choice` (L124), `_seq` (L141), `_interleave` (L159), `_star` (L177), `_nullable` (L186), `_all_token_names` (L201), `_first_names` (L212), `_derive` (L233), `_consume` (L269), `load_completion_model` (L788), `adapt_pointer_list_value_context` (L812), `format_pointer_list_insertion` (L889), `_find_tag_end` (L917), `_pop_stack` (L934), `_following_direct_children` (L945), `_attribute_context` (L1013), `_analyze_xml_context_from` (L1143), `analyze_xml_context` (L1262)

### `save_io.py`
Fonctions : `atomic_write_text_with_backup` (L10)

### `schema_resolution.py`
Classes : `XmlModelDeclaration` (L29), `SchemaResolution` (L47)
Fonctions : `detect_xml_models` (L58), `default_schema_cache_dir` (L79), `_url_cache_path` (L88), `_fetch_remote_rng` (L99), `_local_href_path` (L150), `resolve_schema` (L161)

### `selection_sync.py`
Fonctions : `containing_span_index` (L10), `occurrence_index_for_position` (L19), `choose_occurrence` (L31)

### `tei_facsimile.py`
Classes : `FacsimilePage` (L227), `FacsimileSyncReport` (L235)
Fonctions : `valid_xml_id` (L32), `safe_id_component` (L36), `default_surface_id` (L45), `_attr` (L49), `_pointer_tokens` (L55), `facsimile_ref_at_position` (L59), `_xml_escape_attr` (L121), `_set_or_add_attr` (L125), `_markup_spans` (L138), `position_inside_xml_markup` (L190), `upsert_pb_at_position` (L201), `_graphic_url` (L243), `project_facsimile_pages` (L255), `_surface_open_tags` (L321), `_tei_prefix` (L330), `_indent_before` (L335), `sync_facsimile_text` (L341), `sync_facsimile_file` (L493), `previous_surface_labels` (L506), `removable_generated_iiif_surfaces` (L516)

### `tei_formatter.py`
Classes : `_Node` (L34), `FormatReplacement` (L50), `FormatResult` (L57)
Fonctions : `_local_qname` (L29), `_build_tree` (L84), `_xml_space_preserve` (L113), `_custom_formatting` (L118), `_rng_text_state` (L130), `_direct_gaps` (L149), `format_tei_xml` (L161)

### `tei_pivot_scaffold.py`
Classes : `PivotPage` (L26), `PivotScaffoldPlan` (L34)
Fonctions : `_resolve` (L45), `_source_names` (L50), `_unique_name_match` (L60), `_load_sync_pages` (L82), `_synced_line_count` (L99), `build_pivot_plan` (L140), `scaffold_is_empty` (L289), `render_pivot_scaffold` (L305), `write_pivot_scaffold` (L357)

### `web_viewer/__init__.py`
Pas de classe ou fonction définie au niveau module (voir contenu).

### `web_viewer/generator.py`
Fonctions : `build_dataset` (L35), `_safe_web_name` (L422), `package_local_images` (L426), `make_html` (L470), `generate` (L485), `main` (L507)

### `web_viewer/legacy_v11_core.py`
Fonctions : `lname` (L105), `clean_text` (L110), `normalize` (L114), `bigrams` (L122), `similarity` (L129), `wit_tokens` (L139), `witness_matches` (L145), `choose_file` (L149), `choose_output` (L171), `extract_witness_labels` (L184), `flatten_editorial_text` (L195), `notes_inside` (L219), `extract_corrected_pages` (L229), `variant_tooltip` (L430), `extract_htr_pages` (L447), `parse_alto` (L494), `align_monotonic` (L521), `align_htr_to_alto` (L559), `label_to_string` (L592), `parse_manifest` (L607), `folio_tokens` (L678), `normalize_label` (L683), `match_canvas` (L689), `normalize_medieval_piece` (L739), `normalize_medieval` (L748), `witness_matches_loose` (L752), `choose_parallel_reading` (L764), `build_parallel_witness_stream` (L778), `project_positions` (L838), `_archive_xml_entries` (L866), `match_single_folio_canvas` (L887), `build_secondary_alignment` (L904), `extract_reading_document` (L1075), `attach_variant_metadata_to_runs` (L1381), `load_json` (L1393), `build_dataset_fast` (L1398), `make_html` (L1564), `main` (L1575)

### `web_viewer/page_resolver.py`
Classes : `PageResolver` (L27)
Fonctions : `_local` (L18), `_unique` (L22)

### `web_viewer/tei_line_anchors.py`
Classes : `AnchorReport` (L22)
Fonctions : `_local_name` (L17), `build_pivot_lb_index` (L40)

### `witness_layout.py`
Fonctions : `minimum_witness_stack_height` (L10), `normalized_witness_order` (L21), `ordered_visible_witnesses` (L38)

### `witness_resource_refresh.py`
Classes : `RuntimeState` (L82), `WitnessDiagnostic` (L162)
Fonctions : `read_alignment_json` (L24), `flatten_primary` (L44), `flatten_secondary` (L54), `line_keys` (L66), `sync_fingerprint` (L76), `assemble_resources` (L96), `diagnostic_rows` (L178), `changed_witnesses` (L251)

### `workspace_layout.py`
Fonctions : `normalize_workspace_mode` (L7), `workspace_slots` (L11), `normalized_detached_witnesses` (L18)

### `xml_folding.py`
Classes : `FoldRegion` (L17)
Fonctions : `foldable_xml_regions` (L26), `region_at_header` (L71), `region_for_cursor` (L76), `visible_line_numbers` (L82)

### `xml_tag_pairs.py`
Classes : `XmlTagToken` (L23), `XmlTagPair` (L45), `RenameMirror` (L51), `ClosingTagSuggestion` (L486)
Fonctions : `_find_markup_end` (L63), `scan_xml_tags` (L102), `_inside_special_markup` (L149), `_parse_element_tag_at` (L161), `_opening_near_position` (L186), `matching_closing_tag` (L196), `tag_pairs` (L228), `_selection_bounds` (L248), `opening_pair_at_context` (L257), `closing_pair_at_context` (L286), `pair_at_context` (L337), `exact_selected_opening_pair` (L355), `opening_tag_at` (L372), `single_change_span` (L377), `opening_pair_for_name_change` (L400), `closing_rename_mirror_for_change` (L423), `closing_rename_mirror` (L462), `apply_rename_mirror` (L478), `closing_tag_suggestion` (L503), `complete_closing_tag` (L574)

### `xpath_search.py`
Classes : `XPathUnavailable` (L23), `XPathQueryError` (L27), `XPathMatch` (L32), `XPathSearchResult` (L42)
Fonctions : `_local_name` (L51), `_find_tag_end` (L57), `_opening_tags` (L74), `_rewrite_unprefixed_tei_steps` (L110), `_element_range_map` (L141), `_path_position_map` (L158), `_display_path` (L185), `_preview` (L209), `search_xpath` (L217)

## Méthodes majeures de `editeur_tei.py`

**CodeEditor** : `_check_attribute_completion_cursor` (L410), `show_attribute_completion` (L429), `_accept_attribute_completion` (L444), `_check_closing_completion_cursor` (L469), `show_closing_tag_completion` (L477), `_accept_closing_completion` (L503), `_apply_xml_fold_visibility` (L602), `toggle_xml_fold` (L625), `unfold_all_xml` (L650), `fold_all_xml` (L656)

**ManuscriptPanel** : `set_folios` (L1774), `_folio_combo_changed` (L1796), `_request_split_folio` (L1801), `set_folio` (L1813), `_current_folio` (L1835), `_redraw_scene` (L2017)

**MainWindow** : `_build_xpath_panel` (L4387), `show_xpath_panel` (L4457), `hide_xpath_panel` (L4460), `focus_xpath_search` (L4464), `run_xpath_search` (L4473), `goto_xpath_result` (L4527), `show_validation_panel` (L4617), `hide_validation_panel` (L4630), `_auto_refresh_rng` (L4680), `validate_relaxng_manual` (L4695), `validate_relaxng_document` (L4724), `_validate_relaxng_document_impl` (L4738), `_resolve_completion_schema` (L4892), `_completion_model_for_schema` (L4916), `_custom_completion_config` (L4926), `_custom_witness_ids` (L4944), `format_xml_source` (L4956), `show_rng_completion` (L5088), `_apply_rng_completion` (L5218), `_load_witness_display_order` (L5266), `_save_witness_display_order` (L5278), `_apply_witness_panel_order` (L5284), `_restore_workspace_sizes` (L5396), `_restore_main_splitter_ratio` (L5433), `_toggle_detached_witness` (L5449), `_detach_witness` (L5456), `_dock_witness` (L5487), `_save_detached_witness_ids` (L5507), `_restore_detached_witnesses` (L5511), `_dock_all_witnesses` (L5530), `_available_image_witness_ids` (L5544), `_load_visible_witness_ids` (L5547), `_save_visible_witness_ids` (L5566), `_load_witness_size_map` (L5572), `_remember_witness_splitter_sizes` (L5589), `_update_witness_scroll_extent` (L5605), `_restore_witness_splitter_sizes` (L5630), `_apply_witness_visibility` (L5639), `choose_visible_witnesses` (L5681), `_toggle_witness_panel_maximize` (L5696), `generate_web_viewer` (L6112), `open_iiif_download_manager` (L6245), `_xml_occurrences_in_paragraph` (L6509), `_select_xml_text_in_paragraph` (L6548), `_select_xml_text_near_ordinal` (L6580), `_cursor_changed` (L6611), `_text_changed` (L6615), `_apply_xml_health_result` (L6710), `_async_xml_health_finished` (L6775), `_refresh_folio_navigation` (L6789), `_split_double_folio` (L6880), `sync_panels_to_cursor` (L7043), `refresh_local_iiif_cache` (L7087), `_witness_resource_snapshot` (L7130), `show_witness_diagnostics` (L7140), `refresh_witness_synchronizations` (L7144), `goto_xml_from_base` (L7300)

## Méthodes majeures de `web_viewer/generator.py`

Exports haut niveau : `build_dataset`, `make_html`, `generate`, `main` ; vérifier les lignes ci-dessus.


## Tests par version (noms réels)

### 0.8.5.26.2
- `tests/test_v085262_rng_panel_refresh.py` — 184 lignes, 6 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)

### 0.8.5.26.x
- `tests/test_v085261_web_viewer_presentation.py` — 95 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08526_interim_features.py` — 90 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08526_web_page_anchor_resolution.py` — 179 lignes, 8 fonctions `test_*` de niveau module

### 0.8.5.25.x
- `tests/test_v085252_text_click.py` — 50 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v085253_pivot_lb_contract.py` — 115 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08525_i18n_export.py` — 17 lignes, 1 fonctions `test_*` de niveau module
- `tests/test_v08525_iiif_web.py` — 104 lignes, 6 fonctions `test_*` de niveau module

### 0.8.5.24
- `tests/test_v08524_web_geometry.py` — 186 lignes, 9 fonctions `test_*` de niveau module

### Plus anciens et transversaux
- `tests/test_ctrl_e_sans_qt.py` — 236 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_custom_completion.py` — 73 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_recherche_sans_qt.py` — 87 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_recherche_xslt_joiner_sans_qt.py` — 113 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_relaxng_validation.py` — 118 lignes, 0 fonctions `test_*` de niveau module
- `tests/test_rng_completion.py` — 352 lignes, 20 fonctions `test_*` de niveau module
- `tests/test_rng_context_cache.py` — 44 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_save_io.py` — 24 lignes, 1 fonctions `test_*` de niveau module
- `tests/test_selection_onglets_sans_qt.py` — 40 lignes, 0 fonctions `test_*` de niveau module
- `tests/test_spyder_import_isolation.py` — 61 lignes, 0 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v057_startup_help.py` — 39 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v058_features.py` — 29 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v059_features.py` — 36 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v060_features.py` — 32 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v061_features.py` — 60 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v063_project_layout.py` — 84 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v064_fragment_wrap.py` — 18 lignes, 2 fonctions `test_*` de niveau module
- `tests/test_v070_image_sources.py` — 119 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v071_new_transcription.py` — 111 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v072_no_image_witness.py` — 91 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v073_local_images.py` — 112 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v074_iiif_manifest.py` — 65 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v075_alto_import.py` — 121 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v076_optional_sync.py` — 88 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v077_stabilization.py` — 74 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v078_resource_pages.py` — 102 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v079_facsimile_pages.py` — 259 lignes, 19 fonctions `test_*` de niveau module
- `tests/test_v080_xml_tag_pairs.py` — 112 lignes, 12 fonctions `test_*` de niveau module
- `tests/test_v081_tei_formatter.py` — 121 lignes, 10 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v082_page_sync.py` — 94 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v083_display_navigation.py` — 69 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v0841_xpath_help.py` — 66 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v0842_i18n_handoff.py` — 86 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v084_consolidation.py` — 176 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v08510_frame_visibility.py` — 79 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08511_mixed_page_line.py` — 201 lignes, 7 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08512_scroll_pivot_name.py` — 120 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v08513_xml_closing_completion.py` — 105 lignes, 10 fonctions `test_*` de niveau module
- `tests/test_v08514_iiif_alto_independence.py` — 225 lignes, 13 fonctions `test_*` de niveau module
- `tests/test_v08515_iiif_preview_scale_and_sync_diagnostics.py` — 87 lignes, 8 fonctions `test_*` de niveau module
- `tests/test_v08516_witness_order.py` — 272 lignes, 12 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08517_diagnostic_refresh.py` — 367 lignes, 16 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08518_folio_navigation.py` — 157 lignes, 20 fonctions `test_*` de niveau module
- `tests/test_v08519_split_dialog.py` — 200 lignes, 8 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v0851_pero_uuid_migration.py` — 62 lignes, 3 fonctions `test_*` de niveau module
- `tests/test_v08520_double_page_parts.py` — 273 lignes, 19 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08521_workspace.py` — 282 lignes, 11 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08522_xml_folding.py` — 137 lignes, 8 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v08523_bidirectional_tag_highlight.py` — 90 lignes, 9 fonctions `test_*` de niveau module
- `tests/test_v0852_iiif_manager.py` — 130 lignes, 6 fonctions `test_*` de niveau module
- `tests/test_v0853_iiif_editorial_selection.py` — 225 lignes, 10 fonctions `test_*` de niveau module
- `tests/test_v0854_iiif_exact_autolink.py` — 106 lignes, 9 fonctions `test_*` de niveau module (des méthodes de tests peuvent également exister)
- `tests/test_v0855_sync_canvas_resolution.py` — 280 lignes, 14 fonctions `test_*` de niveau module
- `tests/test_v0856_pivot_scaffold.py` — 236 lignes, 16 fonctions `test_*` de niveau module
- `tests/test_v0857_pivot_visibility.py` — 50 lignes, 4 fonctions `test_*` de niveau module
- `tests/test_v0858_partial_sync_scaffold.py` — 107 lignes, 5 fonctions `test_*` de niveau module
- `tests/test_v0859_column_crop.py` — 79 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_v085_page_iiif_local.py` — 183 lignes, 7 fonctions `test_*` de niveau module
- `tests/test_xpath_search.py` — 51 lignes, 5 fonctions `test_*` de niveau module

## Fichiers complémentaires

Répertoires : `alignments/`, `xml/`, `rendering/`, `resources/`, `help/`, `i18n/`, `web_output/`, `web_viewer/`, `tests/`.

L’inventaire exact des **268 membres ZIP**, y compris les données et les documents hérités, figure dans `VERIFICATION/INVENTAIRE_ZIP_SOURCE.txt`.


---

# Index des documents historiques contenus dans le ZIP original

Ces documents sont consultables en extrayant `BASE_SOURCE/*.zip`. Plusieurs ont des intitulés anciens et des recommandations obsolètes. La source V0.8.5.26.2 puis les addenda récents font autorité.

- `ALIGNMENT_FORMAT.md` — Format d'alignement — version 1
- `ALTO_IMPORT.md` — Import ALTO — V0.7.5
- `CODE_MAP.md` — Varians — carte rapide du code (V0.8.5.0)
- `CONSOLIDATION.md` — Document historique
- `CUSTOM_ELEMENTS.md` — `custom-elements.xml` — aide à la saisie du projet
- `DEVELOPER_HANDOFF.md` — Varians V0.8.5.20 — Navigation en image double, ergonomie et sécurité TEI
- `DISPLAY_NAVIGATION.md` — Varians V0.8.3 — Affichage et navigation de travail
- `DOUBLE_PAGE_PARTS.md` — Navigation en image double — V0.8.5.20
- `FACSIMILE_PAGES.md` — Pages TEI et fac-similé — V0.8.2
- `FOLIO_NAVIGATION.md` — Navigation par parties de manuscrit — Varians V0.8.5.20
- `I18N_FORMAT.md` — Internationalisation — format des catalogues XML
- `IIIF_CANVAS_SELECTION.md` — Varians 0.8.5.4 — Pages éditoriales et associations IIIF ↔ ALTO/PAGE
- `IIIF_SYNC_RESOLUTION.md` — Varians 0.8.5.5 — Résolution des pages synchronisées vers les Canvas IIIF
- `IMAGE_SOURCES.md` — Sources d’images flexibles — V0.7.0
- `MIXED_NAVIGATION.md` — Varians V0.8.5.11 — Navigation mixte par témoin
- `PAGE_IIIF_LOCAL.md` — Varians 0.8.5 — PAGE XML et copies de travail IIIF
- `PASSATION_V0_8_5_24.md` — Varians — Passation de développement V0.8.5.24
- `PASSATION_V0_8_5_25.md` — Passation Varians V0.8.5.25 — 14 octobre 2026
- `PASSATION_V0_8_5_25_1.md` — Passation technique — Varians V0.8.5.25.1
- `PASSATION_V0_8_5_25_2.md` — Varians V0.8.5.25.2 — note de passation
- `PASSATION_V0_8_5_25_3.md` — VARIANS V0.8.5.25.3 — Note de passation complète du correctif
- `PASSATION_V0_8_5_26.md` — VARIANS — PASSATION V0.8.5.26 (VERSION INTERMÉDIAIRE)
- `PASSATION_V0_8_5_26_1.md` — VARIANS — PASSATION V0.8.5.26.1 (ERGONOMIE DE LA RECHERCHE ET ORDRE DES TÉMOINS)
- `PASSATION_V0_8_5_26_2.md` — VARIANS V0.8.5.26.2 — PASSATION DU CORRECTIF RELAX NG
- `PROJECT_AUDIT_PLAN.md` — Varians — Proposition d'audit scientifique des projets
- `PROJECT_MANAGEMENT.md` — Gestion des projets — V0.4
- `RELAXNG_VALIDATION.md` — Validation RELAX NG — V0.5.1
- `RNG_COMPLETION.md` — Complétion contextuelle RELAX NG — V0.5.7
- `ROADMAP_EN_REDEFINITION.md` — Varians — feuille de route en redéfinition
- `ROADMAP_REVISED_2026_10.md` — ARCHIVE HISTORIQUE — FEUILLE DE ROUTE ABANDONNÉE LE 14 OCTOBRE 2026
- `SYNCHRONIZATION.md` — Synchronisation facultative — V0.7.6
- `TEI_FORMATTER.md` — Formateur TEI sûr — V0.8.1
- `TEI_PIVOT_SCAFFOLD.md` — Varians 0.8.5.8 — Préparation de la transcription TEI depuis le témoin pivot
- `WEB_EXPORT_CUSTOMIZATION_DESIGN.md` — Varians — Proposition pour le viewer web et les exports XSLT/CSS
- `WEB_VIEWER_FULLTEXT_SEARCH.md` — Viewer web — moteur de recherche plein texte A03
- `WEB_VIEWER_GEOMETRY.md` — Varians V0.8.5.24 — Contrat de géométrie du viewer web
- `WEB_VIEWER_IIIF.md` — Varians 0.8.5.25 — IIIF haute résolution dans le viewer web
- `WEB_VIEWER_LINE_SYNC_FIX.md` — Varians 0.8.5.25.1 — Correctif de résolution des lignes TEI dans le viewer web
- `WEB_VIEWER_PIVOT_LB_PARITY.md` — VARIANS — V0.8.5.25.3 — Parité des jalons `<lb/>` entre éditeur et viewer web
- `WEB_VIEWER_TEXT_CLICK_FIX.md` — Varians V0.8.5.25.2 — clic texte ↔ images manuscrites du viewer web
- `WITNESS_DIAGNOSTICS.md` — VARIANS V0.8.5.17 — DIAGNOSTIC DES TÉMOINS ET ACTUALISATION
- `WORKSPACE_LAYOUT.md` — Varians V0.8.5.21 — Dispositions des témoins et fenêtres détachées
- `XML_EDITING.md` — Édition XML assistée — V0.8.0
- `XML_FOLDING.md` — Varians 0.8.5.22 — Repliage structurel XML
- `XML_TAG_HIGHLIGHT.md` — Varians V0.8.5.23 — Surbrillance bidirectionnelle des paires XML
- `XSLT_POLICY.md` — XSLT de l’application ou XSLT personnalisée — V0.4.2
