# Formateur TEI sûr — V0.8.1

Le bouton **Indenter** de Varians n'est pas un pretty-printer XML généraliste.
Son objectif est de rendre lisibles les zones structurelles de la TEI sans
modifier silencieusement le contenu textuel de l'édition.

## Principe

Varians ne remplace que des nœuds de texte composés exclusivement de blancs
lorsqu'il peut établir que ces blancs séparent des éléments structurels.

Exemple autorisé :

```xml
<div><head>Titre</head><p>Texte</p></div>
```

peut devenir :

```xml
<div>
  <head>Titre</head>
  <p>Texte</p>
</div>
```

En revanche :

```xml
<p>Et dixit <hi>Dominus</hi> ei.</p>
```

reste inchangé.

## Protections absolues

Le formateur ne modifie pas une zone :

- si elle se trouve sous `xml:space="preserve"` ;
- si l'élément contient directement du texte non blanc ;
- si l'élément contient directement un `<lb/>` ;
- si `custom-elements.xml` déclare l'élément `formatting="preserve"` ou
  `formatting="inline"`.

La règle concernant `<lb/>` est volontairement stricte. Varians n'introduit
jamais de retour à la ligne ni d'espace nouveau avant ou après un `<lb/>`, même
sans `@break="no"`.

## Rôle du RELAX NG

Lorsque le RNG actif est disponible, Varians détermine si le modèle de contenu
d'un élément autorise du texte (`text`, `mixed`, `data`, etc.). Un élément qui
peut contenir du texte est traité par défaut comme une zone potentiellement
mixte, même lorsqu'il est momentanément vide.

Inversement, un élément connu du RNG comme purement structurel peut être
indenté entre ses enfants si aucune protection ci-dessus ne s'applique.

Si le RNG ne permet pas de classer un élément et qu'aucune règle projet ne le
fait explicitement, Varians s'abstient.

## Personnalisation dans `custom-elements.xml`

Chaque `<element>` peut recevoir un attribut `formatting` :

```xml
<element name="hi" formatting="inline"/>
<element name="teiHeader" formatting="block"/>
<element name="formula" formatting="preserve"/>
```

Valeurs :

- `inline` : ne pas introduire de blancs de présentation dans cette zone ;
- `block` : traiter l'élément comme structurel lorsque cela reste sûr ;
- `preserve` : préserver intégralement le sous-arbre ;
- attribut absent : laisser le contenu réel et le RNG décider.

`formatting="block"` ne contourne jamais les protections absolues : il ne peut
pas, par exemple, autoriser l'ajout de blancs autour d'un `<lb/>` ou dans un
contenu direct déjà textuel.

## Bonne formation et Undo

Un XML non bien formé n'est jamais réécrit par le formateur. Le bouton se
contente alors d'afficher un message dans la barre d'état.

Les changements d'indentation sont appliqués en un seul bloc Undo et ne
réécrivent que les blancs structurels retenus par le moteur.
