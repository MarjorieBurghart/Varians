# Édition XML assistée — V0.8.0

Varians dispose désormais d'un moteur lexical de paires de balises, séparé de
la validation RELAX NG et du parse XML complet. Ce moteur est conçu pour rester
utile pendant la frappe, lorsque le document peut être momentanément non bien
formé.

## Correspondance des balises

`xml_tag_pairs.py` reconnaît les balises ouvrantes, fermantes et autofermantes,
respecte les guillemets d'attributs et ignore commentaires, CDATA, instructions
de traitement et déclarations. Les paires sont établies suivant l'imbrication
XML ; deux éléments de même nom imbriqués ne sont donc pas confondus.

Exemple :

```xml
<seg>
  extérieur
  <seg>intérieur</seg>
</seg>
```

La fermeture du `seg` intérieur reste associée à son ouverture et la fermeture
finale à l'ouverture extérieure.

## Surbrillance de la fermeture

Lorsque le curseur est strictement à l'intérieur d'une balise ouvrante, ou
qu'une sélection est contenue dans cette balise, la fermeture correspondante
est mise en évidence avec le bleu pâle utilisé par les autres sélections de
Varians (`#d9ecff`). Une position immédiatement avant `<` ou après `>` n'est pas
considérée comme située dans la balise.

Cette mise en évidence est une `ExtraSelection` : elle ne modifie jamais la
sélection réelle de l'utilisateur.

## Suppression d'une enveloppe

Si la sélection correspond exactement à toute la balise ouvrante d'un élément
apparié et que cette sélection est supprimée, Varians supprime également la
balise fermante. Le contenu compris entre les deux est conservé strictement.

Ainsi :

```xml
<seg>texte</seg>
```

devient :

```xml
texte
```

L'ouverture et la fermeture sont supprimées dans le même bloc Undo. Les balises
autofermantes (`<lb/>`, `<pb/>`, etc.) n'ont pas de paire et gardent le
comportement d'édition normal.

Le traitement repose sur `QTextDocument.contentsChange` et couvre donc aussi
les suppressions déclenchées autrement qu'avec la touche Suppr : Couper et
commande de suppression du menu contextuel notamment.

## Renommage synchronisé

Une modification limitée au QName de la balise ouvrante est répercutée sur le
QName de sa fermeture :

```xml
<seg type="x">texte</seg>
```

peut devenir, après correction du nom ouvrant :

```xml
<quote type="x">texte</quote>
```

Les attributs et le contenu ne sont jamais réécrits. Le miroir de la fermeture
rejoint l'opération précédente dans la pile Undo, afin qu'un seul Ctrl+Z restaure
les deux noms. Si le QName ouvrant est momentanément entièrement effacé avant
d'être retapé, Varians conserve la paire connue pendant cette courte phase
invalide et rétablit le miroir dès qu'un nouveau QName valide apparaît.

Par prudence, Varians n'invente aucune paire lorsqu'il rencontre une structure
croisée ou ambiguë. Dans ce cas, l'éditeur conserve le comportement de texte
normal et laisse la validation XML/RNG signaler le problème.

## Performance

Le curseur ne déclenche pas un parse complet du fichier : Varians repère
localement la balise ouvrante courante puis ne cherche vers l'avant que sa
fermeture. Pour les modifications, l'éditeur exploite directement les offsets
fournis par `QTextDocument.contentsChange`, sans calculer un diff global du TEI
à chaque frappe.

## Indentation sûre depuis V0.8.1

Le bouton **Indenter** repose sur un moteur séparé (`tei_formatter.py`) qui ne
réécrit jamais le contenu textuel pour obtenir un simple effet visuel. Les
règles détaillées, notamment la protection absolue de `<lb/>`,
`xml:space="preserve"` et les surcharges `formatting` de
`custom-elements.xml`, sont décrites dans `TEI_FORMATTER.md`.

## Complétion des éléments fermants (V0.8.5.13)

Dans l'éditeur XML source **et** l'éditeur de fragments, la saisie de `</`
affiche une suggestion légère (`QCompleter`) contenant le QName du plus proche
élément structurellement ouvert à la position du curseur. **Entrée** ou **Tab**
accepte et insère la suite du nom ainsi que `>` ; **Échap** ferme la liste sans
modifier le document. Un préfixe tel que `</di` est pris en charge ;
**Ctrl+Espace** dans ce contexte propose d'abord la fermeture au lieu de
déclencher une complétion RNG d'élément ou d'attribut.

Par exemple, après `<div><p><lb/></p></`, `div>` est proposé. Les éléments
vides ne s'empilent pas ; les QNames préfixés (par ex. `tei:div`) sont conservés.
Aucun parse XML bien formé ni chargement RNG n'est requis : un scanner lexical
examine le préfixe de texte précédant la balise fermante inachevée. Il ignore
commentaires, CDATA, PI, DOCTYPE et chevrons entre guillemets d'attribut. Une
fermeture croisée, un attribut encore ouvert ou une imbrication indécidable
empêchent toute suggestion plutôt que de risquer une fermeture erronée.

Moteur pur et testable sans Qt : `xml_tag_pairs.closing_tag_suggestion()`
et `complete_closing_tag()` ; intégration graphique dans
`CodeEditor.show_closing_tag_completion()`, `_accept_closing_completion()` et
`keyPressEvent()`. L'insertion est un bloc d'édition annulable. Le reste du
système de complétion RNG et de renommage synchronisé des balises est conservé.

## V0.8.5.22 — Repliage structurel sans modification XML

Chevrons interactifs dans la marge, `Ctrl+Alt+F` (élément), commandes « Replier les éléments structurels » et « Tout déplier » dans Affichage. Une modification du texte réaffiche toutes les lignes. Voir `XML_FOLDING.md`.

## V0.8.5.23 — Mise en évidence bidirectionnelle des balises

Un curseur placé à l’intérieur d’une balise ouvrante ou fermante fait surligner les deux membres de la paire par `QTextEdit.ExtraSelection`. La sélection réelle et le texte restent inchangés. `pair_at_context` réutilise `opening_pair_at_context` pour l’ouverture et `closing_pair_at_context` pour la fermeture. Une pile stricte refuse les fermetures croisées/orphelines avant la position. Les balises autofermantes n’ont pas de paire. Voir `XML_TAG_HIGHLIGHT.md`.
