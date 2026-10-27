# Schéma ISO Schematron (vérification et complétion des fichiers .sch)

Varians vérifie la structure d'un fichier Schematron affiché (F8, module
`schematron_check`, V0.9.2.4) d'après ce schéma, et en tire la complétion
(Ctrl+Espace). Les expressions XPath, elles, sont compilées par Saxon avec
SchXslt2 (voir `resources/schxslt2`).

## Origine

`iso-schematron.rng` est le schéma RELAX NG de l'ISO/IEC 19757-3 (ISO
Schematron, édition 2016), dans la copie livrée avec lxml 6.1.3 :
`lxml/isoschematron/resources/rng/iso-schematron.rng`, empreinte SHA-256
`56c5b13f28b78958890c36e3249c34c169041e42ebcfdce8080f3324ba2bf4de`. lxml y
a déjà rendu facultatif l'élément `properties` (commentaire « edited
(lxml) »).

## Modification

Varians ajoute à `assert` et `report` l'attribut `severity` de l'édition 2020
de la norme, que SchXslt2 applique et que l'aide de Varians présente
(`fatal`, `error`, `warning`, `info`, ou une autre valeur) ; chaque ajout est
précédé du commentaire « edited (Varians) ».

Depuis la V0.9.2.5, il accepte aussi les nouveautés des éditions 2020 et 2025
que SchXslt2 applique (`resources/schxslt2/transpile.xsl`), chacune précédée
du commentaire « edited (Varians, 2020/2025) » :

- `group`, défini comme `pattern`, et `rules` (un ensemble de règles, en
  pratique abstraites), à côté des `pattern` d'un `schema` ;
- `library`, seconde racine possible : un fichier de définitions (groupes,
  règles, diagnostics…) qu'un autre inclut, avec ses `extends/@href` ;
- `param` au niveau du `schema`, à côté des `let`, et `@as` sur `let` et
  `param` ;
- `rule/@visit-each`, `phase/@from` et `phase/@when`,
  `schema/@schematronEdition`.

Les éditions 2020 et 2025 de la norme ne sont pas en accès libre, ni leur
schéma : ces ajouts suivent ce qu'accepte SchXslt2, et ne sont pas une copie
de leur schéma. Un fichier de racine `library` est vérifié comme un fichier
inclus, sans compilation.

Pour refaire la copie : partir du fichier de lxml, placer avant `<grammar>`
la mention de modification (ci-dessous), puis insérer, dans les définitions
`assert` et `report`, juste avant `<ref name="rich"/>` :

```xml
<optional>
  <!-- edited (Varians): severity (ISO/IEC 19757-3:2020) -->
  <attribute name="severity">
    <choice>
      <value>fatal</value>
      <value>error</value>
      <value>warning</value>
      <value>info</value>
      <ref name="non-empty-string"/>
    </choice>
  </attribute>
</optional>
```

Reporter ensuite les ajouts marqués « edited (Varians, 2020/2025) » tels
qu'ils figurent dans la copie livrée (définitions `group`, `rules`,
`library`, choix de la racine, attributs ajoutés), et compléter la mention
de modification en tête du fichier.

## Licence

La notice de l'ISO, en tête du fichier, en autorise la copie, la
modification et la distribution gratuites, pour développer et employer des
logiciels fondés sur le schéma. Elle doit rester dans le fichier, avec, pour
une copie modifiée comme celle-ci, la mention :

> THIS SCHEMA HAS BEEN MODIFIED FROM THE SCHEMA DEFINED IN ISO/IEC 19757-3,
> AND SHOULD NOT BE INTERPRETED AS COMPLYING WITH THAT STANDARD.

`tests/test_schematron_check.py` vérifie que lxml compile ce schéma et que
la mention y figure.
