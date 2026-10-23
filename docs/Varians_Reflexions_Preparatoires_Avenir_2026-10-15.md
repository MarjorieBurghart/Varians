# Varians — Réflexions préparatoires sur l’évolution du logiciel

**Note de cadrage et de synthèse des échanges**  
**Date :** 15 octobre 2026  
**Base de référence :** Varians **V0.8.5.26.2**  
**Statut :** document de réflexion, **pas une roadmap approuvée ni une spécification technique définitive**.

## 1. Point de départ et objectif général

La V0.8.5.26.2 constitue un **jalon majeur et stabilisé** de Varians, assorti d’un dossier de passation technique. Les améliorations récentes de la validation RELAX NG, de la complétion XML et du viewer web ont été éprouvées par l’utilisateur. La feuille de route précédemment envisagée a été abandonnée : il s’agit désormais de **repenser librement les évolutions futures**, sans convertir automatiquement les anciennes idées en travaux programmés.

Deux axes de développement, fortement liés, ont été identifiés :

1. **Passer d’un projet organisé principalement autour d’un unique `edition.xml` à un projet pouvant contenir et éditer plusieurs documents XML, XSLT et ressources associées.**
2. **Permettre de définir des scénarios de transformation XSLT personnalisés, au niveau du projet, dans l’esprit des configurations de transformation d’Oxygen XML Editor.**

L’ambition n’est pas de faire de Varians un éditeur XML généraliste indifférencié. Sa spécialité demeure **l’édition critique et la consultation synchronisée des manuscrits**, mais avec une architecture adaptée aux projets documentaires complexes.

## 2. Décisions et exigences retenues au cours des échanges

Les points ci-dessous constituent les principales **conclusions de principe** des discussions ; ils ne préjugent pas de leur implémentation.

### 2.1. Deux modèles éditoriaux doivent coexister

L’utilisateur a explicitement confirmé qu’un projet devra pouvoir prendre en charge **les deux situations** suivantes, éventuellement simultanément :

- **Une édition logique répartie entre plusieurs fichiers XML**, par exemple un document maître et des chapitres distincts, avec des fichiers d’autorités partagés.
- **Plusieurs éditions TEI autonomes au sein d’un même projet**, chacune susceptible de disposer de ses propres témoins, de son témoin pivot et de ses propres données de synchronisation.

Une structure conceptuelle à trois niveaux a été proposée :

```text
Projet Varians
├── Unité éditoriale A
│   ├── Document maître et/ou fichiers de chapitres
│   ├── Témoins et témoin pivot de A
│   └── Alignements et synchronisation propres à A
├── Unité éditoriale B
│   ├── Documents XML de B
│   ├── Témoins et témoin pivot de B
│   └── Alignements et synchronisation propres à B
└── Ressources communes
    ├── Autorités (personnes, lieux, etc.)
    ├── Schémas de validation
    ├── Feuilles XSLT et feuilles CSS
    └── Autres ressources documentaires
```

La notion d’**« unité éditoriale »** est ici une **proposition de modèle interne** : elle exprime l’autonomie d’une édition logique, même lorsque ses données sont distribuées dans plusieurs fichiers. Son nom exact et sa représentation dans la configuration restent à arrêter.

> **Décision du 23 octobre 2026 :** le second modèle (plusieurs éditions TEI autonomes dans un même projet) est retiré de la feuille de route. Des éditions sans rapport se placent dans des projets séparés ; un corpus de textes transmis par des témoins différents tient dans une seule édition en parties, avec des textes synchronisés à part (V0.9.1.1). Voir `docs/DECISIONS_ASSEMBLAGE.md`.

### 2.2. La simplicité des petits projets est une exigence fondamentale

C’est une condition explicitement soulignée par l’utilisateur : **une personne qui veut simplement transcrire un texte à partir d’une image ne doit pas avoir à comprendre l’architecture multifichier, XInclude ou les scénarios XSLT pour commencer.**

Conséquences attendues :

- Création et utilisation d’un projet simple en quelques étapes, avec des paramètres par défaut raisonnables.
- **Aucune obligation** de configurer unités éditoriales, schémas personnalisés, dépendances ou transformations.
- Présentation **progressive** des fonctions avancées lorsqu’elles deviennent nécessaires, plutôt que trois modes de fonctionnement séparés.
- Possibilité d’enrichir progressivement un projet initialement simple, **sans devoir le recréer**.
- Maintien des habitudes de travail des utilisateurs de la V0.8.5.26.2 et prise en charge des projets historiques.
- La complexité éventuelle du modèle interne ne doit pas se répercuter sur l’interface de création de projet.

Ce principe de **« complexité progressive »** devra guider autant l’ergonomie que les tests de non-régression.

### 2.3. Distinguer sources, assemblages et références

La séparation suivante a été présentée puis approuvée comme orientation :

1. **Fichiers sources éditables**, conservés comme documents distincts.
2. **Représentation logique assemblée**, temporaire et dérivée, lorsqu’une édition utilise des inclusions ou plusieurs chapitres.
3. **Dépendances documentaires** et références entre fichiers, sans fusion nécessaire de leur contenu.

Une opération d’assemblage ou de transformation **ne doit pas réécrire silencieusement les fichiers sources**. Elle devra, dans la mesure nécessaire aux diagnostics et à la navigation, conserver l’identification de l’origine des éléments assemblés.

### 2.4. Protéger les invariants scientifiques de Varians

L’évolution vers plusieurs fichiers ou éditions ne doit pas fragiliser les fonctionnalités validées :

- Synchronisation TEI ↔ lignes physiques des témoins par les clés et alignements existants.
- Conservation d’un **ordre cohérent des jalons `<lb/>`** à l’échelle de chaque édition logique, y compris quand les chapitres sont séparés.
- **Absence de mélange accidentel des pivots et alignements** de deux éditions autonomes.
- Respect des témoins non alignés et des modes de navigation appropriés.
- Intégrité des ressources ALTO/PAGE XML, images et références IIIF.
- Absence d’inférences ou de reconstructions silencieuses de correspondances incertaines.

Les modalités techniques exactes du calcul des clés globales, de la provenance des fragments et des opérations d’assemblage demeurent à concevoir et à tester.

## 3. Gestion des documents et de leurs dépendances

### 3.1. Importation et création des ressources

Varians devrait pouvoir **importer** des fichiers existants ou **créer** de nouveaux fichiers XML et XSLT, et leur associer, selon les besoins, des fichiers CSS et des schémas de validation. Les XML auxiliaires n’ont pas tous vocation à représenter une édition TEI complète : un registre d’autorités, par exemple, doit pouvoir être édité comme document autonome.

Les **schémas personnalisés**, notamment RELAX NG, doivent pouvoir être **réellement intégrés au projet**, et non uniquement référencés par un lien fragile. Le traitement de leurs dépendances (`include`, `externalRef`, etc.), le choix entre copie et référencement externe et la gestion de leur provenance restent à spécifier.

### 3.2. Trois familles de relations entre fichiers

| Relation | Exemple | Conséquence envisagée |
|---|---|---|
| **Inclusion structurelle** | Un document maître incorpore des chapitres via XInclude | Constituer, si nécessaire, une vue logique assemblée, sans altérer les sources. |
| **Référence documentaire** | Un passage renvoie à une entrée de `personnes.xml` | Naviguer vers la cible et éventuellement vérifier son existence, sans nécessairement l’inclure. |
| **Dépendance technique** | Une XSLT importe une autre XSLT ; un RNG inclut un autre RNG | Résoudre les fichiers nécessaires à la validation ou à la transformation. |

**XInclude est une possibilité, non une obligation pour toutes les relations documentaires.** Les liens par identifiant (`@ref`, `@corresp`, etc.) doivent rester possibles. Les dépendances peuvent être déclarées ou détectées ; le système ne devrait pas déduire arbitrairement l’appartenance d’un fichier à une édition en fonction de son seul répertoire.

Un **gestionnaire central des ressources et dépendances** a été proposé afin que l’éditeur, la validation, l’aperçu et les exports utilisent des règles de résolution cohérentes. Cette centralisation relève encore de la conception technique.

### 3.3. Validation à plusieurs niveaux

Il est souhaitable de distinguer :

- **Validation de chaque fichier source** avec son schéma associé, éventuellement conçu pour des fragments.
- **Validation de l’édition assemblée** avec le schéma approprié à l’ensemble.
- **Vérifications de références croisées**, distinctes de la validation RELAX NG proprement dite.

Les erreurs devront renvoyer, autant que possible, **au fichier source et à son emplacement réel**. Les inclusions manquantes, références introuvables et cycles devront être signalés de manière explicite, sans correction automatique hasardeuse.

## 4. Édition multifichier et interface

Une **interface multionglet** a été proposée, avec un explorateur de projet et des panneaux contextuels. Il s’agit d’une orientation ergonomique à étudier, **pas d’une disposition définitivement validée**.

Comportements souhaités :

- Ouvrir et modifier plusieurs fichiers XML ou XSLT au sein d’une même session.
- Conserver les états propres aux documents : modification non enregistrée, annuler/refaire, diagnostics de validation, emplacement courant.
- Adapter automatiquement les panneaux à la ressource active :
  - **chapitre d’une édition synchronisée** : manuscrits pertinents visibles ;
  - **fichier XSLT** : panneaux des manuscrits masqués automatiquement ;
  - **fichier d’autorités ou autre XML auxiliaire** : panneaux de manuscrits masqués par défaut si non pertinents ; aperçu spécifique possible.
- Associer **par document** soit le couple XSLT/CSS habituel, soit une XSLT/CSS particulière, soit aucun aperçu automatique.
- En cas d’édition en plusieurs fichiers, envisager **un aperçu individuel** du document actif et **un aperçu contextualisé** de l’édition logique assemblée ; le choix pourrait dépendre du document ou de l’unité éditoriale.

La distinction entre **préférences purement locales d’affichage** et **associations documentaires portables dans le projet** est à conserver.

## 5. Scénarios de transformation XSLT personnalisés

L’utilisateur souhaite pouvoir configurer **plusieurs scénarios de transformation nommés**, à la manière d’Oxygen. Ils offriraient un moyen de produire des publications particulières, sans imposer un rendu unique.

### 5.1. Paramètres possibles d’un scénario

Les éléments suivants ont été proposés pour discussion :

- Nom du scénario et éventuel document ou périmètre concerné.
- **Source d’entrée** : fichier XML individuel ; fichier après résolution des inclusions ; unité éditoriale assemblée ; document de regroupement explicite.
- Feuille XSLT sélectionnée, avec ses dépendances.
- Paramètres de transformation (nom, valeur) et éventuelle CSS associée au résultat.
- Processeur XSLT, format de sortie et destination des fichiers produits.
- Possibilité d’un aperçu avant publication et de diagnostics d’exécution.

Exemples d’usages : page HTML de personnes, édition HTML/texte, index spécifiques, sortie XML transformée, publication portant sur plusieurs éditions. Pour plusieurs éditions, la source commune devra être explicitement définie ; la transformation automatique d’une liste arbitraire de documents n’est pas présumée.

> **Décision du 23 octobre 2026 :** la source d’un scénario est un fichier ou l’édition (assemblée au besoin) ; la publication portant sur plusieurs éditions d’un même projet n’est plus envisagée (voir section 2.1).

### 5.2. Coexistence avec le viewer web natif

**Le viewer web natif reste une voie de publication distincte**, spécialisée dans la consultation synchronisée des éditions et manuscrits (images, IIIF, géométrie, recherche et navigation).

Les **transformations XSLT personnalisées** formeraient une voie alternative pour des publications ad hoc, **sans devoir reproduire ni altérer** le moteur interactif du viewer standard. Une transformation personnalisée ne doit pas risquer de casser la publication native.

### 5.3. Moteurs de transformation et sécurité : propositions ouvertes

Il a été suggéré de ne pas limiter l’architecture au seul XSLT 1.0 actuellement associé à `lxml`/libxslt : un moteur supplémentaire compatible XSLT 2.0/3.0, tel que SaxonC, pourrait être examiné. **Aucun choix de moteur ni aucune nouvelle dépendance ne sont arrêtés.**

L’exécution des transformations devra faire l’objet de garanties techniques : résolution contrôlée des imports et documents, gestion des chemins et des accès aux fichiers/réseau, absence d’écriture imprévue, journal d’exécution et reproductibilité. La politique exacte reste à concevoir.

## 6. Compatibilité et migration

Le scénario recommandé consiste à **faire fonctionner les projets historiques inchangés**, en interprétant au besoin leur unique `edition.xml` comme une **unité éditoriale implicite en mémoire**. Il ne faudrait pas imposer une conversion visible ou une restructuration manuelle aux utilisateurs des projets simples.

Les ajouts avancés — nouveau document, seconde unité éditoriale, schéma personnalisé ou scénario XSLT — devraient être activés **à la demande**, par enrichissement du projet existant.

Les chemins des données, l’organisation des fichiers, les références et la sérialisation des nouveaux réglages devront être étudiés pour garantir la **portabilité** des projets Windows/macOS/Linux et la reproductibilité des publications.

## 7. Ordre d’étude envisagé — sans calendrier ni versions décidées

Une succession technique **proposée**, non arrêtée comme roadmap, serait :

1. **Modèle documentaire et contrats de données** : fichiers, unités éditoriales, ressources communes, références, compatibilité avec l’ancien format.
2. **Édition multifichier et dépendances** : interface, schémas associés, inclusions/références, aperçu, synchronisation et diagnostics.
3. **Scénarios de transformation XSLT** : définition, paramètres, moteurs, publications et contrôles de sécurité.

Cette succession reflète les dépendances techniques pressenties ; son éventuel découpage en versions restera à discuter.

## 8. Points encore ouverts

Les échanges n’ont pas encore tranché les questions suivantes :

- Schéma définitif de configuration du projet et nom/identité des unités éditoriales.
- Organisation physique des ressources, politique d’import (copie ou lien) et gestion des fichiers partagés.
- Règles exactes de montage des documents, de résolution XInclude et de conservation de la provenance.
- Traitement des éléments `<lb/>` répartis entre fichiers, des renvois vers le pivot et de la synchronisation de chaque édition.
- Modes de navigation des références entre fichiers et niveau de vérification des identifiants.
- Ergonomie détaillée : explorateur, onglets, aperçu individuel/contextualisé, transitions entre unités éditoriales.
- Schémas de documents fragmentaires et restitution précise des erreurs de validation globale.
- Format persistant, portée et héritage des scénarios XSLT ; choix des moteurs et de leurs dépendances.
- Politique de sécurité pour les ressources locales/distantes et les transformations.
- Stratégie de tests de migration et de non-régression, y compris le parcours **« une image, une transcription, sans options avancées »**.

Aucun de ces points ouverts ne doit être présenté comme déjà implémenté ou définitivement approuvé.

## 9. Conclusion et principe directeur

Les réflexions convergent vers un Varians capable d’héberger **plusieurs fichiers XML, plusieurs éditions autonomes et des ressources communes**, tout en permettant des **publications configurables par scénarios XSLT**. Les relations entre fichiers devront être explicites, vérifiables et respectueuses de l’intégrité scientifique des données.

La contrainte première reste toutefois l’ergonomie :

> **Un projet simple doit rester simple. Les fonctions avancées doivent enrichir Varians sans ajouter d’obstacles à la création d’une transcription élémentaire.**

La **V0.8.5.26.2** demeure le point de référence opérationnel. Ce document sert de **mémoire des discussions et de base pour élaborer une future feuille de route** ; il n’engage ni livraison, ni version, ni choix technique non encore validé.
