# Modèles de document de la TEI livrés avec Varians

**Fichier → Documents XML / XSLT du projet → Nouveau document XML…** propose,
sous « TEI P5 », les modèles de document minimal publiés par le TEI
Consortium : un squelette par déclinaison de la TEI (TEI All, TEI Lite, Bare,
Manuscript description, Corpus…). Ce sont ceux qu'Oxygen XML Editor propose
dans son groupe « TEI P5 » (cadre TEI, dépôt
[github.com/TEIC/oxygen-tei](https://github.com/TEIC/oxygen-tei)) : Oxygen les
reprend, lui aussi, de l'archive publiée de TEI P5.

Le module `document_templates` les lit dans ce dossier. Le nom d'un modèle est
celui de son fichier, sans `.xml`.

## Origine

- Dépôt : [github.com/TEIC/TEI](https://github.com/TEIC/TEI), étiquette
  `P5_Release_4.12.0`.
- Archive publiée, version 4.12.0 :
  `https://github.com/TEIC/TEI/releases/download/P5_Release_4.12.0/tei-4.12.0.zip`
  (empreinte MD5 `a95bad4518894a1e0d58e4ac5eb8121d`, SHA-256
  `0195baccee3b1e3e4f75b21fcf3c7c71cbcd75c796678b6f8c33229da13f66c5`).
- Les 21 fichiers `.xml` de ce dossier sont ceux de
  `xml/tei/custom/templates/` dans cette archive, copiés tels quels (les fins
  de ligne aussi : `.gitattributes`). Ils sont faits, à la publication de TEI
  P5, à partir des fichiers `P5/Exemplars/*.template` du dépôt par la feuille
  `P5/Exemplars/make_template.xsl`, qui ajoute les deux déclarations
  `<?xml-model?>` (schéma RELAX NG et règles Schematron de la déclinaison).
- Ne sont pas repris : les fichiers `.properties` (icônes d'Oxygen),
  `catalog.xml` et les `tei_*.doc.xml` (documentation des déclinaisons), qu'Oxygen
  ne propose pas non plus comme modèles.
- `LICENCE.txt` est le fichier `P5/COPYING.txt` du dépôt à la même étiquette.

## Vérification

Chaque modèle a été validé par lxml (le validateur RELAX NG de Varians)
contre le schéma de sa déclinaison, pris dans la même archive
(`xml/tei/custom/schema/relaxng/`) :

- 20 modèles sont valides ;
- « TEI for writing TEI Customizations » ne l'est pas, volontairement :
  `<schemaSpec ident="">` attend son identifiant (« @ident is required »,
  dit le modèle).

Les schémas de Corpus, ENRICH Manuscript description, Manuscript description
et Speech (`tei_corpus.rng`, `tei_enrich.rng`, `tei_ms.rng`,
`tei_speech.rng`) faisaient tourner libxml2 sans fin (défaut de libxml2,
constaté en 2.9.14 et 2.14.6) ; Varians les compile grâce au correctif de
`relaxng_validation.single_patterns_unwrapped` (détails dans
`DEVELOPER_HANDOFF.md`). Les modèles ont été vérifiés avec ce correctif.

## Ce que Varians change

Rien dans les fichiers. À la création d'un document, ses deux déclarations
`<?xml-model?>` désignent le schéma par `https://www.tei-c.org/…` au lieu de
`http://www.tei-c.org/…` : Varians télécharge ce schéma (une fois, puis le
garde en cache) par une connexion chiffrée. Le reste du document est le
modèle, octet pour octet, textes d'exemple en anglais compris.

## Licence

Les documents du TEI Consortium sont distribués, au choix, sous la licence
[Creative Commons Attribution 3.0 Unported](http://creativecommons.org/licenses/by/3.0/)
ou sous la licence [BSD à deux clauses](http://www.opensource.org/licenses/BSD-2-Clause) :
Copyright 2013 TEI Consortium. Le texte est dans `LICENCE.txt`, qui doit
accompagner ces fichiers.

## Mettre à jour les modèles

Pour une nouvelle version de TEI P5 (ici `X.Y.Z`) :

1. télécharger `tei-X.Y.Z.zip` depuis la page des versions du dépôt TEIC/TEI
   (Releases) ;
2. remplacer les `.xml` de ce dossier par ceux de
   `xml/tei/custom/templates/` de l'archive, sans `catalog.xml` ni les
   `tei_*.doc.xml` ; remplacer `LICENCE.txt` par `P5/COPYING.txt` de
   l'étiquette `P5_Release_X.Y.Z` ;
3. mettre à jour ce LISEZMOI (version, adresse, empreintes) et
   `TEI_TEMPLATES_VERSION` dans `document_templates.py` ;
4. lancer les tests (`tests/test_document_templates.py` contrôle les modèles
   livrés : liste, racines, schémas déclarés).
