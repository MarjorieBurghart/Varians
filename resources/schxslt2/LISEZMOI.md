# SchXslt2 livré avec Varians

Varians applique les règles Schematron d'un schéma (V0.9.2.3) : celles qui
sont intégrées au RNG employé pour la validation (`tei_all.rng` en contient
91 groupes) et celles des déclarations `xml-model` de type Schematron. Le
module `schematron` les fait passer par SchXslt2, qui transforme une
Schematron en feuille XSLT 3.0 ; Saxon (paquet `saxonche`, déjà employé par
les scénarios de transformation) l'applique ensuite au document.

SchXslt2 tient en un seul fichier, `transpile.xsl`, livré ici tel quel.

## Origine

- Projet : SchXslt2, de David Maus, successeur de SchXslt 1.x
  ([codeberg.org/schxslt/schxslt2](https://codeberg.org/schxslt/schxslt2)).
- Version 1.11.2, publiée sur Maven Central :
  `https://repo1.maven.org/maven2/name/dmaus/schxslt/schxslt2/1.11.2/schxslt2-1.11.2.jar`
  (empreinte SHA-1 publiée `026ddbdcabd65ec3baef03b1364a7d2307cec198`).
- `transpile.xsl` est le fichier `content/transpile.xsl` de cette archive,
  sans modification : 58 728 octets, empreinte SHA-256
  `b0e07b08298db37b39d7d83223cb6d7cc54c47a3b590db3e732bd0e43043b224`.

## Licence

SchXslt2 est distribué sous la licence MIT : « Copyright (C) by David Maus ».
Le texte complet de la licence est en tête de `transpile.xsl` et doit y
rester.

## Réglages employés par Varians

`schematron.py` compile `transpile.xsl` une fois par processus, avec deux
paramètres statiques :

- `schxslt:compact-report` à vrai : le rapport (SVRL) ne contient que les
  messages et les erreurs ;
- `schxslt:terminate-validation-on-error` à faux : une erreur d'exécution
  d'une règle est écrite dans le rapport (`svrl:error`) au lieu d'arrêter
  Saxon ; Varians la signale comme une erreur des règles.

Les autres paramètres gardent leur valeur par défaut (phase : celle de
`defaultPhase`, sinon toutes les règles).

## Refaire ce dossier

Pour une nouvelle version (ici `X.Y.Z`) :

1. télécharger `schxslt2-X.Y.Z.jar` depuis Maven Central
   (`https://repo1.maven.org/maven2/name/dmaus/schxslt/schxslt2/X.Y.Z/`) et
   comparer son empreinte SHA-1 à celle du fichier `.jar.sha1` publié à côté ;
2. extraire `content/transpile.xsl` de l'archive (c'est un fichier zip) et
   remplacer celui de ce dossier ;
3. vérifier que la notice de licence est toujours en tête du fichier et que
   les paramètres ci-dessus existent encore ;
4. mettre à jour ce LISEZMOI (version, adresse, empreintes : SHA-256 de
   `transpile.xsl`, par exemple avec `sha256sum`) ;
5. lancer les tests (`tests/test_schematron.py` contrôle ce dossier et
   l'application des règles).
