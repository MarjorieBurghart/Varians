# Schéma XSLT 3.0 (complétion des feuilles XSLT)

Varians propose, par Ctrl+Espace, les éléments et attributs d'une feuille XSLT
d'après ce schéma (module `xslt_completion`, V0.9.2.1). Il ne sert pas à
vérifier une feuille : la vérification compile la feuille avec lxml ou Saxon.

## Origine

- `schema-for-xslt30.rnc` : le schéma RELAX NG (syntaxe compacte) publié avec
  la recommandation XSLT 3.0 du W3C, copié tel quel depuis le dépôt
  [w3c/qtspecs](https://github.com/w3c/qtspecs),
  `specifications/xslt-30/src/schema-for-xslt30.rnc`, révision
  `6cef5545618cd2edfd94f32af488a16bb19c598c`.
- `schema-for-xslt30.rng` : le même schéma en syntaxe XML, que lit la
  complétion de Varians.

## Licence

Copyright (c) 2010-2016, Mohamed ZERGAOUI (Innovimax). Licence BSD à trois
clauses : son texte est en tête des deux fichiers, et doit y rester.

## Conversion

Le RNG a été produit ainsi, avec [rnc2rng](https://pypi.org/project/rnc2rng/)
2.7.0 (outil de développement, qui n'est pas installé avec Varians) :

1. les quatre valeurs écrites entre apostrophes (`'#unnamed'`, `'#all'`,
   `'#default'`, `'#current'`), que rnc2rng ne lit pas, sont mises entre
   guillemets, hors commentaires :
   `sed -E "/^[[:space:]]*#/! s/'(#[a-z]+)'/\"\1\"/g" schema-for-xslt30.rnc > guillemets.rnc` ;
2. `rnc2rng guillemets.rnc schema-for-xslt30.rng` ;
3. la déclaration `xmlns:local=""`, que rnc2rng écrit pour l'espace de noms
   vide et qui n'est pas du XML correct, est retirée (l'espace de noms vide
   reste désigné par `ns=""`) ;
4. rnc2rng ne garde pas les commentaires : l'avis de licence est remis en
   tête du RNG, dans un commentaire XML, avec la note d'origine.

Le RNG obtenu est un schéma RELAX NG correct (lxml le compile ;
`tests/test_xslt_completion.py` le vérifie).
