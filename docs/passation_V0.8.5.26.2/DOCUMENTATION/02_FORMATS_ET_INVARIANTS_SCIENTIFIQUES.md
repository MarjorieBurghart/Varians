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
