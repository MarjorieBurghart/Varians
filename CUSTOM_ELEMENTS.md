# `custom-elements.xml` — aide à la saisie du projet

Depuis Varians 0.6.0, `custom-elements.xml` enrichit **Ctrl+E** et **Ctrl+Espace** sans jamais modifier les règles de validité du schéma RELAX NG.

## Principe

Varians distingue explicitement les deux sources dans les listes :

- **RNG** : proposition autorisée par le schéma ;
- **Projet** : convention ou raccourci défini dans `custom-elements.xml` ;
- **RNG + Projet** : proposition présente dans les deux sources.

Une suggestion « Projet » n'est donc pas une affirmation de validité. Inversement, une valeur absente d'une liste projet peut rester parfaitement valide au regard du RNG.

## Éléments et attributs de Ctrl+E

Le format historique reste valide :

```xml
<customElements>
  <element name="rdg">
    <attribute name="wit"/>
  </element>
</customElements>
```

`Ctrl+E` peut proposer `rdg` comme commodité du projet et, une fois l'élément choisi, insère `wit=""` en plaçant le curseur entre les guillemets.

Une valeur par défaut reste possible :

```xml
<attribute name="rend" defaultValue="italic"/>
```

## Valeurs d'attribut suggérées

Des valeurs explicites peuvent être données avec `<value>` :

```xml
<element name="hi">
  <attribute name="rend" valuesMode="replace">
    <value>italic</value>
    <value>bold</value>
  </attribute>
</element>
```

Dans `rend="|"`, `Ctrl+Espace` propose alors `italic` et `bold`.

### `valuesMode="append"`

C'est le comportement par défaut. Les valeurs projet sont ajoutées aux valeurs finies éventuellement connues du RNG.

### `valuesMode="replace"`

La liste projet **remplace uniquement les propositions affichées** par Varians. Elle ne modifie pas le RNG et ne transforme donc pas cette liste en règle de validation.

C'est utile lorsqu'un schéma autorise un domaine très large mais que l'édition suit une convention plus étroite.

## Témoins

Pour les pointeurs comme `rdg/@wit`, les identifiants de témoins sont produits dynamiquement. Depuis V0.8.8.0, le fichier fourni propose les `<witness>` décrits dans la TEI (le `<listWit>`), comme pour `lem/@wit` ; ce sont eux que vérifie la commande « Références » :

```xml
<element name="rdg">
  <attribute name="wit" valuesMode="replace">
    <values source="ids" elements="witness" prefix="#"/>
  </attribute>
</element>
```

La source `witnesses` propose plutôt les témoins déclarés dans `project.xml` (ceux qui ont des images ou une synchronisation), qui peuvent différer du `<listWit>` :

```xml
<values source="witnesses" prefix="#"/>
```

Un projet créé avant V0.8.8.0 garde sa copie de `rendering/custom-elements.xml`, donc l'ancienne règle `source="witnesses"` ; pour adopter la nouvelle, la remplacer par `source="ids" elements="witness"`.

Avec des témoins `T1`, `T2` et `P` décrits dans le `<listWit>`, `Ctrl+Espace` dans :

```xml
<rdg wit="|">
```

propose :

```text
#T1
#T2
#P
```

Si les sigles des témoins changent dans un autre projet, la liste change automatiquement.

## Identifiants des documents du projet

Dans les attributs de référence (`@ref`, `@corresp`, `@target`, `@who`…),
Varians propose déjà les `xml:id` de tous les documents du projet (édition
et documents auxiliaires), limités par défaut au type d'entrée attendu :
`persName/@ref` → `person`, `personGrp`, `persona` ; `placeName/@ref` →
`place` ; `orgName/@ref` → `org` ; `@who` → personnes ; `@wit` et `@edRef`
→ `witness`. La source `ids` règle cette liste pour un attribut :

```xml
<element name="name">
  <attribute name="ref" valuesMode="replace">
    <values source="ids" elements="person place" prefix="#"/>
  </attribute>
</element>
```

`elements` donne les noms locaux des éléments dont les identifiants sont
proposés (sans `elements`, tous). Comme en TEI standard, la valeur est
`#id` pour un identifiant du document affiché, et `fichier.xml#id` (chemin
relatif) pour un identifiant d'un autre document. Avec
`valuesMode="replace"`, seuls ces identifiants sont proposés. Taper `#`
dans la valeur ouvre la liste sans Ctrl+Espace.

## Valeurs TEI recommandées mais non imposées

Le même mécanisme peut servir à fournir des valeurs de travail pour un attribut ouvert par le RNG. Par exemple :

```xml
<element name="lb">
  <attribute name="break" valuesMode="replace">
    <value>yes</value>
    <value>no</value>
    <value>maybe</value>
  </attribute>
</element>
```

Varians les affichera alors comme suggestions **Projet**, et non comme valeurs « autorisées par le RNG ».


## Mise en forme TEI (V0.8.1)

`custom-elements.xml` peut aussi préciser le comportement du bouton **Indenter** :

```xml
<element name="hi" formatting="inline"/>
<element name="teiHeader" formatting="block"/>
<element name="formula" formatting="preserve"/>
```

- `inline` protège une zone destinée au flux textuel ;
- `block` indique une structure que Varians peut indenter si aucun contenu
  textuel réel, `xml:space="preserve"` ou `<lb/>` direct ne l'interdit ;
- `preserve` interdit toute modification de blancs dans le sous-arbre.

Ces indications concernent uniquement la présentation du XML source. Elles ne
changent jamais la validité RELAX NG. La protection de `<lb/>` est absolue :
aucune règle `block` ne peut autoriser l'ajout de blancs autour de cet élément.
