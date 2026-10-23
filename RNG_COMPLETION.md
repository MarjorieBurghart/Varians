# Complétion contextuelle RELAX NG — V0.5.7


## Nouveauté V0.5.7 : valeurs d’attributs finies

Quand le curseur se trouve dans une valeur d’attribut entre guillemets, **Ctrl+Espace** peut maintenant proposer les valeurs si le RELAX NG permet de les énumérer explicitement.

Exemple :

```xml
<lb break="n|"/>
```

avec un RNG équivalent à :

```xml
<attribute name="break">
  <choice>
    <value>yes</value>
    <value>no</value>
  </choice>
</attribute>
```

propose `no` (et `yes` si aucun préfixe n’est saisi). La valeur actuellement présente entre les guillemets est remplacée entièrement par la suggestion choisie.

Le moteur suit aussi les `ref` vers des définitions finies et ignore les annotations étrangères telles que `a:documentation` courantes dans les RNG TEI générés.

La stratégie est volontairement conservative : si une branche autorise une valeur ouverte (`text`, `data`, liste libre, etc.), aucune liste partielle n’est présentée comme exhaustive. Les `anyName` / `nsName` restent eux aussi non énumérables.

## Optimisation V0.5.5 : cache lexical incrémental

Le calcul positionnel de V0.5.4 est conservé, mais le scanner XML ne repart plus systématiquement du caractère zéro à chaque **Ctrl+Espace**.

`XmlContextCache` enregistre des points de reprise après des balises complètes, environ tous les 32 Kio. Quand le document est modifié, seuls les points situés à partir de la zone modifiée sont invalidés. Les états précédents — pile des éléments ouverts et enfants directs déjà rencontrés — restent réutilisables.

Sur le fichier d'exemple de développement (~528 000 caractères), le scanner sans cache mesuré près de la fin du document prenait environ 40–50 ms dans l'environnement de test. Après amorçage du cache, le même contexte est typiquement obtenu en ~1–2 ms ; après une modification locale vers la fin du fichier, la reprise reste de l'ordre de quelques millisecondes. Ces chiffres sont indicatifs et dépendront de la machine et du document.

La résolution du schéma est également mise en cache d'après les déclarations `xml-model`. Tant que celles-ci ne changent pas, Ctrl+Espace réutilise la résolution déjà effectuée par F8/l'ouverture du projet au lieu de résoudre à nouveau le même RNG, ce qui est particulièrement important avec un schéma distant. Le bouton de rafraîchissement du schéma continue à forcer une nouvelle résolution.

## Nouveauté V0.5.4 : position exacte dans les séquences

La complétion des éléments par **Ctrl+Espace** ne se contente plus de l'union de tous les enfants possibles du parent. Le moteur conserve maintenant la structure du pattern RELAX NG et calcule les éléments admissibles **à la position du curseur**.

Exemple : pour un contenu RNG équivalent à :

```text
A, B, C
```

les propositions deviennent :

```xml
<parent>|</parent>       -> A
<parent><A/>|</parent>   -> B
<parent><A/><B/>|</parent> -> C
```

Après `C`, aucun autre élément n'est proposé si le pattern est terminé.

Le calcul prend en charge :

- `group` / séquences ;
- `choice` ;
- `optional` ;
- `zeroOrMore` ;
- `oneOrMore` ;
- `interleave` ;
- les `ref` explicites ;
- les patterns chargés depuis les RNG locaux associés (`include` / `externalRef` lorsque résolus localement).

Les attributs et les nœuds texte ne sont pas traités comme des jetons de la séquence d'éléments : ils n'altèrent donc pas l'ordre relatif des balises enfants.

## Curseur au milieu d'un contenu existant

Le scanner lexical relève aussi les **frères directs situés après le curseur** lorsqu'ils sont déjà présents.

Pour un schéma :

```text
A, B?, (C | D), E*, F
```

et un document :

```xml
<parent><A/>|<C/><F/></parent>
```

la liste large après `A` serait `B`, `C` ou `D`. Mais, puisque `<C/><F/>` existe déjà à droite, seule l'insertion de `B` conserve une séquence compatible. V0.5.4 propose donc seulement `B`.

De même, avec :

```text
A, B
```

et :

```xml
<parent><A/>|<B/></parent>
```

aucun nouvel élément n'est proposé : ajouter un second `B` produirait `A, B, B`.

## Document momentanément invalide

Le scanner reste lexical et continue à fonctionner pendant une édition incomplète.

Si les frères déjà présents **à gauche** du curseur constituent une séquence impossible selon le RNG, le moteur ne prétend pas disposer d'un état positionnel fiable. Il revient alors à la liste large historique des enfants du parent afin de conserver une aide utile pendant la réparation du document.

La validation **F8 / Valider RNG** reste l'autorité pour déterminer la validité réelle du document.

## Correctif V0.5.3 conservé : curseur dans une balise ouvrante

La détection distingue toujours explicitement :

- `<rdg|>` : attributs autorisés pour `rdg` ;
- `<rdg |>` : attributs autorisés pour `rdg` ;
- `<rdg wi|>` : attributs autorisés pour `rdg`, filtrés par `wi` ;
- `<rdg>|` : éléments autorisés dans le contenu de `rdg` ;
- `<lb edRef="#T1"|/>` : attributs encore autorisés dans `lb` (correctif V0.5.8).

La présence du `>` situé après le curseur permet de distinguer une balise ouvrante déjà nommée d'un nom d'élément encore incomplet.

## Attributs

Dans une balise ouvrante, Ctrl+Espace propose les attributs explicitement permis par le RNG et retire ceux qui sont déjà présents.

```xml
<rdg wi|
```

peut devenir :

```xml
<rdg wit="|"
```

À l’intérieur d’une valeur citée, Ctrl+Espace passe au mode **valeur d’attribut** et utilise `CompletionModel.allowed_attribute_values()`. Seules les énumérations réellement finies sont proposées.

## Schéma utilisé

La complétion suit la politique du projet :

1. `xml-model` automatique ;
2. RNG explicite du projet ;
3. aucun schéma — complétion désactivée.

Pour un schéma distant, elle travaille sur le miroir local déjà produit par `schema_resolution.py`.

## Architecture

`rng_completion.py` reste totalement indépendant de Qt.

Il contient désormais :

- `load_completion_model()` : analyse statique du RNG ;
- `CompletionModel.child_elements()` : liste large historique ;
- `CompletionModel.child_elements_at()` : calcul positionnel ;
- `CompletionModel.allowed_attribute_values()` : énumérations finies d’attributs ;
- un petit automate régulier interne fondé sur la dérivation des patterns ;
- `analyze_xml_context()` : scanner lexical sans état conservé pour compatibilité et tests ;
- `XmlContextCache` : scanner incrémental utilisé par l'interface pour les appels répétés et invalidation locale.

L'interface Qt transmet simplement ce contexte au modèle puis affiche les propositions retournées.

## Ctrl+E piloté par le RNG — V0.5.9

`Ctrl+E` réutilise désormais le même modèle positionnel que `Ctrl+Espace`. Avant
d'afficher le choix d'élément, l'interface calcule les éléments enfants permis à
la position exacte du curseur (ou au début de la sélection à entourer). Les noms
autorisés sont proposés en premier dans un sélecteur filtrable.

Le champ reste **éditable** : il est toujours possible de saisir manuellement un
nom ou `nom/` pour une balise vide. Cette souplesse est volontaire, car le document
peut être momentanément invalide pendant sa correction et le RNG ne doit pas
transformer `Ctrl+E` en commande bloquante. Une fois l'élément choisi, les attributs
de `custom-elements.xml` sont appliqués exactement comme auparavant.

Si aucun schéma n'est disponible, si sa résolution échoue ou si le contexte ne
permet pas de calculer une liste utile, `Ctrl+E` revient au champ libre historique.

## Limites encore connues

- `anyName` et `nsName` ne fournissent pas de liste finie et ne sont donc pas proposés ;
- les valeurs d’attributs ouvertes (`text`, `data`, listes libres, etc.) ne sont pas énumérées ;
- la complétion est une aide à la saisie, pas un second validateur RELAX NG ;
- lorsqu'une partie déjà présente du document est invalide, une stratégie de repli volontairement permissive peut être utilisée pour ne pas bloquer la correction.

## Feuille de route

1. **Position exacte dans les séquences RNG — réalisée en V0.5.4** ;
2. **Complétion des valeurs d’attributs finies — réalisée en V0.5.7** ;
3. **Intégration du RNG dans `Ctrl+E` — réalisée en V0.5.9** ;
4. **Enrichissement par `custom-elements.xml` — réalisé en V0.6.0** : les
   suggestions de commodité sont affichées séparément des règles de validité RNG,
   avec listes d’attributs explicites ou dynamiques et mode `append`/`replace`.

Les optimisations de performances V0.5.5/V0.5.6 ont été réalisées en parallèle
de cette feuille de route fonctionnelle.

## Enrichissement par `custom-elements.xml` — V0.6.0

`Ctrl+E` et `Ctrl+Espace` fusionnent désormais deux sources **explicitement distinguées** dans le sélecteur :

- **RNG** : le schéma autorise cette proposition ;
- **Projet** : `custom-elements.xml` la propose comme commodité éditoriale ;
- **RNG + Projet** : les deux sources concordent.

La couche Projet ne change jamais la validation RELAX NG. Elle peut en revanche rendre l'interface volontairement plus restrictive. Pour une valeur d'attribut :

```xml
<attribute name="wit" valuesMode="replace">
  <values source="witnesses" prefix="#"/>
</attribute>
```

`valuesMode="replace"` remplace la liste **affichée** par Ctrl+Espace ; il ne modifie pas l'ensemble des valeurs valides selon le RNG. `valuesMode="append"` (défaut) ajoute au contraire les suggestions Projet aux valeurs finies connues du RNG.

La source dynamique `witnesses` lit les identifiants déclarés dans `project.xml`. Ainsi `rdg/@wit` peut proposer `#T1`, `#T2`, `#P` dans le projet d'exemple sans que ces sigles soient codés dans Varians. Voir `CUSTOM_ELEMENTS.md`.


## Listes de pointeurs — V0.6.1

Lorsque toutes les valeurs proposées pour un attribut commencent par `#`, Varians
les traite comme une liste de pointeurs séparés par des espaces. Les pointeurs
déjà présents dans la valeur (y compris à droite du curseur) sont exclus des
propositions afin d'éviter les doublons.

Ainsi, avec les valeurs projet `#T1`, `#T2`, `#P` :

```xml
<rdg wit="#T2|">toto</rdg>
```

propose `#T1` et `#P`, puis insère automatiquement l'espace nécessaire. Avec :

```xml
<rdg wit="#T2 #T|">toto</rdg>
```

seul le token partiel `#T` est remplacé. Cette logique concerne la commodité de
saisie et ne modifie jamais la validité RELAX NG.

## V0.8.5.26 — Noms d’attributs pendant la frappe
Le texte partiel d’un attribut dans une balise ouvrante déclenche une proposition filtrée issue du modèle RNG actif ; les aides personnalisées restent accessibles par Ctrl+Espace. Un attribut déjà présent est exclu ; ni valeur d’attribut ni balise fermante ne déclenchent ce menu. Entrée/Tab insère un nom suivi de guillemets ; Ctrl+Espace conserve ses dialogues antérieurs.

## V0.9.2.1 — Feuilles XSLT, nom tapé devant une autre balise

**Feuilles XSLT.** Pour une feuille XSLT affichée, la complétion ne suit pas
un `xml-model` : elle lit le schéma XSLT 3.0 du W3C livré avec Varians
(`resources/schemas/xslt30`), par `xslt_completion.StylesheetCompletionModel`,
qui offre à `completion_ui` la même interface que le modèle RNG
(`child_elements_at`, `allowed_attributes`, `allowed_attribute_values`). Les
noms reçoivent le préfixe XSLT de la feuille ; un élément d’un autre espace de
noms est un élément résultat littéral (instructions et attributs `xsl:*`) ;
une feuille `version="1.0"` ne reçoit qu’XSLT 1.0. Les éléments personnalisés
du projet (`custom-elements.xml`) ne sont pas proposés. Voir
`XSLT_SCENARIOS.md`.

**Nom tapé devant une autre balise.** `<h|</p>` (ou `<h|` puis, à la ligne,
`</p>`) est un nom d’élément en cours de saisie : Ctrl+Espace propose les
éléments qui commencent par `h`. Auparavant, le `>` de la balise suivante
faisait prendre `h` pour un élément complet dont on cherchait les attributs.
Le `>` situé après le curseur ne compte que s’il n’est précédé d’aucun `<`
(`<rdg|>` reste un contexte d’attribut).

