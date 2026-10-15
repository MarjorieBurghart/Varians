VARIANS V0.8.4 — CONSOLIDATION DES MODES DE PROJET
===================================================

Objet
-----
V0.8.4 ne cherche pas à ajouter un nouveau workflow. Elle verrouille le continuum
construit depuis V0.7.0 et garantit qu'une ressource facultative ne peut plus
faire basculer le projet dans un mode plus précis qu'elle ne le permet réellement.

Principe central : présence ≠ synchronisation exploitable
----------------------------------------------------------
Un fichier `alignment="…json"` peut exister tout en étant vide ou provisoire.
De même, un ALTO contient des lignes numérotées sans pour autant établir une
correspondance avec les `<lb>` de la TEI.

V0.8.4 distingue donc :

1. la présence de la ressource JSON ;
2. son contenu de synchronisation effectif ;
3. les ALTO/images ajoutés indépendamment par-dessus.

Le JSON est évalué AVANT superposition des ALTO :

- témoin de base : le mode ligne exige au moins une ligne de référence possédant
  une page identifiée et un numéro `line` ;
- témoin secondaire : le mode ligne exige au moins une ligne portant un
  `base_keys` non vide (ou `keys816` en lecture rétrocompatible) ;
- sans ces données, Varians reste en mode page lorsqu'une image est disponible.

Cela évite notamment qu'un JSON vide + ALTO fasse croire à une synchronisation.

Matrice fonctionnelle consolidée
---------------------------------

| TEI | Images | ALTO | JSON sync | Résultat attendu |
|-----|--------|------|-----------|------------------|
| oui | non | non | non | édition textuelle seule |
| oui | locales | non | non | mode page |
| oui | IIIF | non | non | mode page |
| oui | locales/IIIF | oui | non | page entière + géométrie ALTO facultative |
| oui | locales/IIIF | oui | JSON vide | mode page, jamais faux mode ligne |
| oui | facultatives | facultatif | base avec vraies lignes | base en mode ligne |
| oui | facultatives | facultatif | secondaire sans base_keys | secondaire en mode page |
| oui | facultatives | facultatif | secondaire avec base_keys | secondaire en mode ligne |

Desktop / viewer web
--------------------
Les deux environnements appliquent désormais les mêmes critères d'activation du
mode ligne. Un témoin secondaire dont le JSON ne contient aucune correspondance
`base_keys` n'est plus annoncé comme synchronisé par le viewer web alors que le
desktop le traitait déjà comme non synchronisé.

Rétrocompatibilité
------------------
- Le champ historique `keys816` reste lu ; les nouveaux outils doivent produire
  `base_keys`.
- Les anciens projets sans bloc `<images>` restent en mode `auto`.
- Aucun format de `project.xml` ni de JSON n'est modifié par cette consolidation.
- Le nouveau module `resource_state.py` est interne et ne nécessite aucune
  migration de projet.

Garde-fou important
-------------------
Un ALTO indépendant ne doit jamais déterminer à lui seul le nombre attendu de
`<lb>` dans l'édition, ni activer un recadrage ligne-à-ligne. La synchronisation
est une information distincte de la segmentation physique ALTO.
